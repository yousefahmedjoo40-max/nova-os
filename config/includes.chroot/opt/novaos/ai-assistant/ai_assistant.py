#!/usr/bin/env python3
"""
AI Assistant - NovaOS
مساعد نظام يستخدم Google Gemini API لشرح الأخطاء واقتراح أوامر،
مع تأكيد إلزامي من المستخدم قبل تنفيذ أي أمر.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import json
import os
import subprocess
import threading
import urllib.request
import urllib.error

CONFIG_PATH = "/etc/novaos/config.json"
SET_KEY_HELPER = "/opt/novaos/ai-assistant/novaos-ai-set-key.sh"
GET_KEY_HELPER = "/opt/novaos/ai-assistant/novaos-ai-get-key.sh"

DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_model_name():
    cfg = load_config()
    return cfg.get("ai", {}).get("model", DEFAULT_MODEL)


def get_base_url():
    cfg = load_config()
    return cfg.get("ai", {}).get("api_base_url", DEFAULT_BASE_URL)


def get_api_key():
    """يقرأ المفتاح عبر helper مُصرّح له بـ sudo NOPASSWD (محصور الوظيفة)."""
    try:
        out = subprocess.run(
            ["sudo", "-n", GET_KEY_HELPER],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if out == "NO_KEY" or not out:
            return None
        return out
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        return None


def save_api_key(key: str):
    proc = subprocess.run(
        ["sudo", "-n", SET_KEY_HELPER],
        input=key, text=True, capture_output=True,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def call_gemini(prompt: str, system_errors_context: str = ""):
    """ينادي Gemini API. يرفع استثناء بنص واضح عند أي فشل (نت/مفتاح)."""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "لا يوجد مفتاح API محفوظ. اذهب إلى الإعدادات وأدخل مفتاح Gemini أولاً."
        )

    model = get_model_name()
    base_url = get_base_url()
    url = f"{base_url}/models/{model}:generateContent?key={api_key}"

    full_prompt = prompt
    if system_errors_context:
        full_prompt = (
            "أنت مساعد نظام تشغيل NovaOS (مبني على Debian). اشرح الخطأ التالي بوضوح، "
            "واقترح أوامر محتملة للحل، لكن لا تنفذ أي شيء بنفسك أبداً:\n\n"
            f"سياق الخطأ:\n{system_errors_context}\n\nسؤال المستخدم: {prompt}"
        )

    payload = json.dumps({
        "contents": [{"parts": [{"text": full_prompt}]}]
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        raise RuntimeError("تعذّر الاتصال بالإنترنت. تحقق من اتصال الشبكة وحاول مجدداً.")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError("مفتاح API غير صحيح أو غير مفعّل. تحقق منه في الإعدادات.")
        raise RuntimeError(f"خطأ من خدمة Gemini (HTTP {e.code}).")

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError("رد غير متوقع من الخدمة.")

    return text


def extract_suggested_commands(ai_text: str):
    """يبحث في الرد عن أسطر داخل كتل كود ```bash ... ``` كأوامر مقترحة."""
    commands = []
    lines = ai_text.splitlines()
    in_block = False
    for line in lines:
        if line.strip().startswith("```"):
            in_block = not in_block
            continue
        if in_block and line.strip():
            commands.append(line.strip())
    return commands


class AIAssistantWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="AI Assistant - NovaOS")
        self.set_default_size(560, 600)
        self.set_border_width(10)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.pack_start(header, False, False, 0)
        header.pack_start(Gtk.Label(label=f"الموديل الحالي: {get_model_name()}"), False, False, 0)
        settings_btn = Gtk.Button(label="⚙ الإعدادات")
        settings_btn.connect("clicked", self.open_settings)
        header.pack_end(settings_btn, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        root.pack_start(scroller, True, True, 0)

        self.chat_buffer = Gtk.TextBuffer()
        self.chat_view = Gtk.TextView(buffer=self.chat_buffer)
        self.chat_view.set_editable(False)
        self.chat_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scroller.add(self.chat_view)

        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        root.pack_start(input_box, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("اسأل عن خطأ أو اطلب اقتراح أوامر...")
        self.entry.connect("activate", self.on_send)
        input_box.pack_start(self.entry, True, True, 0)

        send_btn = Gtk.Button(label="إرسال")
        send_btn.connect("clicked", self.on_send)
        input_box.pack_start(send_btn, False, False, 0)

        self.pending_commands = []

    def append_chat(self, who, text):
        end = self.chat_buffer.get_end_iter()
        self.chat_buffer.insert(end, f"\n[{who}]\n{text}\n")

    def on_send(self, *_):
        prompt = self.entry.get_text().strip()
        if not prompt:
            return
        self.entry.set_text("")
        self.append_chat("أنت", prompt)
        self.append_chat("النظام", "...جارٍ التفكير")

        def worker():
            try:
                reply = call_gemini(prompt)
                error = None
            except RuntimeError as e:
                reply = None
                error = str(e)

            def update_ui():
                # إزالة سطر "جارٍ التفكير" الأخير بشكل مبسط عبر إضافة الرد الفعلي
                if error:
                    self.append_chat("خطأ", error)
                else:
                    self.append_chat("المساعد", reply)
                    commands = extract_suggested_commands(reply)
                    if commands:
                        self.pending_commands = commands
                        self.show_command_confirmation(commands)
                return False

            GLib.idle_add(update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def show_command_confirmation(self, commands):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="المساعد اقترح الأوامر التالية. هل تريد تنفيذها الآن؟",
        )
        dialog.format_secondary_text("\n".join(commands))
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            self.run_commands(commands)
        else:
            self.append_chat("النظام", "تم إلغاء تنفيذ الأوامر بناءً على طلبك.")

    def run_commands(self, commands):
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30
                )
                output = result.stdout + result.stderr
                self.append_chat("تنفيذ", f"$ {cmd}\n{output.strip()}")
            except Exception as e:
                self.append_chat("خطأ تنفيذ", f"$ {cmd}\n{e}")

    def open_settings(self, *_):
        dialog = Gtk.Dialog(title="إعدادات AI Assistant", transient_for=self, flags=0)
        dialog.add_buttons(
            "إلغاء", Gtk.ResponseType.CANCEL, "حفظ", Gtk.ResponseType.OK
        )
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_border_width(10)

        box.add(Gtk.Label(label="مفتاح Gemini API (لن يُعرض بعد الحفظ):"))
        key_entry = Gtk.Entry()
        key_entry.set_visibility(False)
        box.add(key_entry)

        box.add(Gtk.Label(label="اسم الموديل:"))
        model_entry = Gtk.Entry()
        model_entry.set_text(get_model_name())
        box.add(model_entry)

        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            new_key = key_entry.get_text().strip()
            if new_key:
                ok, msg = save_api_key(new_key)
                self.append_chat("النظام", "تم حفظ المفتاح بأمان." if ok else f"فشل حفظ المفتاح: {msg}")
            new_model = model_entry.get_text().strip()
            if new_model and new_model != get_model_name():
                self._update_model_in_config(new_model)
                self.append_chat("النظام", f"تم تحديث الموديل إلى: {new_model}")
        dialog.destroy()

    def _update_model_in_config(self, new_model):
        cfg = load_config()
        cfg.setdefault("ai", {})["model"] = new_model
        try:
            # يتطلب صلاحية كتابة على /etc/novaos/config.json (مملوك root:sudo مثلاً)
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except PermissionError:
            self.append_chat(
                "خطأ",
                "لا توجد صلاحية كتابة على ملف الإعدادات. "
                "شغّل التطبيق كـ sudo أو عدّل صلاحيات الملف.",
            )


def main():
    win = AIAssistantWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
