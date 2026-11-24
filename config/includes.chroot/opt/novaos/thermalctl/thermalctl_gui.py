#!/usr/bin/env python3
"""
ThermalCtl GUI - NovaOS
واجهة GTK3 لعرض الحرارة/الاستهلاك والتحكم في الوضع وMangoHud وFPS cap.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import json
import os
import subprocess

STATUS_PATH = "/run/novaos/thermal_status.json"
MANGOHUD_CONF = os.path.expanduser("~/.config/MangoHud/MangoHud.conf")
SET_MODE_HELPER = "/opt/novaos/thermalctl/novaos-thermal-set-mode.sh"


class ThermalCtlWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="ThermalCtl - NovaOS")
        self.set_default_size(420, 420)
        self.set_border_width(16)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(root)

        # ---- حالة الحساسات ----
        self.sensor_warning = Gtk.Label(label="")
        self.sensor_warning.set_line_wrap(True)
        root.pack_start(self.sensor_warning, False, False, 0)

        # ---- بطاقات القراءات ----
        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        root.pack_start(grid, False, False, 0)

        self.lbl_cpu_temp = Gtk.Label(label="CPU: --°م")
        self.lbl_gpu_temp = Gtk.Label(label="GPU: --°م")
        self.lbl_cpu_usage = Gtk.Label(label="استهلاك المعالج: --٪")
        self.lbl_ram_usage = Gtk.Label(label="استهلاك الذاكرة: --٪")

        for i, lbl in enumerate(
            [self.lbl_cpu_temp, self.lbl_gpu_temp, self.lbl_cpu_usage, self.lbl_ram_usage]
        ):
            lbl.set_xalign(0)
            grid.attach(lbl, 0, i, 1, 1)

        # ---- أوضاع الأداء ----
        mode_label = Gtk.Label(label="وضع الأداء:")
        mode_label.set_xalign(0)
        root.pack_start(mode_label, False, False, 0)

        self.mode_combo = Gtk.ComboBoxText()
        for m, display in [
            ("silent", "هادئ (Silent)"),
            ("balanced", "متوازن (Balanced)"),
            ("performance", "أداء عالٍ (Performance)"),
        ]:
            self.mode_combo.append(m, display)
        self.mode_combo.set_active_id("balanced")
        self.mode_combo.connect("changed", self.on_mode_changed)
        root.pack_start(self.mode_combo, False, False, 0)

        # ---- MangoHud / FPS cap ----
        mh_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.pack_start(mh_box, False, False, 0)

        self.mangohud_switch = Gtk.Switch()
        self.mangohud_switch.connect("state-set", self.on_mangohud_toggled)
        mh_box.pack_start(Gtk.Label(label="تفعيل MangoHud (FPS Overlay):"), False, False, 0)
        mh_box.pack_start(self.mangohud_switch, False, False, 0)

        fps_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.pack_start(fps_box, False, False, 0)
        fps_box.pack_start(Gtk.Label(label="حد الإطارات (FPS cap, 0=بدون حد):"), False, False, 0)
        self.fps_spin = Gtk.SpinButton.new_with_range(0, 360, 1)
        self.fps_spin.set_value(0)
        self.fps_spin.connect("value-changed", self.on_fps_changed)
        fps_box.pack_start(self.fps_spin, False, False, 0)

        # تحديث دوري كل ثانيتين
        GLib.timeout_add_seconds(2, self.refresh_status)
        self.refresh_status()

    def refresh_status(self):
        if not os.path.exists(STATUS_PATH):
            self.sensor_warning.set_markup(
                "<b>⚠ خدمة thermalctld غير نشطة بعد.</b> جارٍ الانتظار..."
            )
            return True

        try:
            with open(STATUS_PATH) as f:
                status = json.load(f)
        except (json.JSONDecodeError, OSError):
            return True

        if not status.get("sensors_available"):
            self.sensor_warning.set_markup(
                "<b>⚠ لا توجد حساسات حرارة على هذا الجهاز.</b>\n"
                "هذا متوقع داخل الأجهزة الافتراضية (VirtualBox/VMware) لأنها لا تُظهر "
                "حرارة فيزيائية حقيقية. ستظل بقية القراءات (المعالج/الذاكرة) تعمل بشكل طبيعي."
            )
        else:
            self.sensor_warning.set_text("")

        cpu_t = status.get("cpu_temp_avg")
        self.lbl_cpu_temp.set_text(f"CPU: {cpu_t}°م" if cpu_t is not None else "CPU: غير متاح")

        gpu = status.get("gpu")
        if gpu:
            self.lbl_gpu_temp.set_text(f"GPU: {gpu['temp']}°م / استخدام {gpu['usage']}٪")
        else:
            self.lbl_gpu_temp.set_text("GPU: غير متاح (لا يوجد nvidia-smi)")

        cpu_u = status.get("cpu_usage_pct")
        self.lbl_cpu_usage.set_text(
            f"استهلاك المعالج: {cpu_u}٪" if cpu_u is not None else "استهلاك المعالج: --"
        )

        ram_u = status.get("ram_usage_pct")
        self.lbl_ram_usage.set_text(
            f"استهلاك الذاكرة: {ram_u}٪" if ram_u is not None else "استهلاك الذاكرة: --"
        )

        current_mode = status.get("mode")
        if current_mode and self.mode_combo.get_active_id() != current_mode:
            self.mode_combo.set_active_id(current_mode)

        return True  # استمرار التايمر

    def on_mode_changed(self, combo):
        mode = combo.get_active_id()
        if not mode:
            return
        try:
            subprocess.run(["sudo", "-n", SET_MODE_HELPER, mode], check=True)
        except subprocess.CalledProcessError as e:
            self._show_error(f"تعذّر تطبيق الوضع: {e}")
        except FileNotFoundError:
            self._show_error("سكربت ضبط الوضع غير موجود.")

    def on_mangohud_toggled(self, switch, state):
        os.makedirs(os.path.dirname(MANGOHUD_CONF), exist_ok=True)
        if state:
            with open(MANGOHUD_CONF, "w") as f:
                f.write("fps\ncpu_temp\ngpu_temp\ncpu_load\ngpu_load\nram\nframetime\n")
                fps_cap = int(self.fps_spin.get_value())
                if fps_cap > 0:
                    f.write(f"fps_limit={fps_cap}\n")
        else:
            if os.path.exists(MANGOHUD_CONF):
                os.remove(MANGOHUD_CONF)
        return False

    def on_fps_changed(self, spin):
        if self.mangohud_switch.get_active():
            self.on_mangohud_toggled(self.mangohud_switch, True)

    def _show_error(self, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=msg,
        )
        dialog.run()
        dialog.destroy()


def main():
    win = ThermalCtlWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
