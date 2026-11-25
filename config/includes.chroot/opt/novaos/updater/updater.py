#!/usr/bin/env python3
"""
NovaOS Updater
يفحص جدول updates في Supabase، يقارن النسخة الحالية، يحمّل حزمة .deb من
GitHub Releases، يتحقق من sha256 وتوقيع minisign، ثم يطبّق التحديث عبر
helper مُصرّح بـ sudo، مع الاحتفاظ بنسخة سابقة للـ rollback.
"""
import json
import os
import subprocess
import sys
import urllib.request
import hashlib
import shutil

CONFIG_PATH = "/etc/novaos/config.json"
CURRENT_VERSION_FILE = "/etc/novaos/version"
CACHE_DIR = "/var/cache/novaos/updates"
APPLY_HELPER = "/opt/novaos/updater/novaos-apply-update.sh"
MINISIGN_PUBKEY_PATH = "/etc/novaos/novaos-minisign.pub"  # المفتاح العام فقط (وليس الخاص)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_current_version():
    try:
        with open(CURRENT_VERSION_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


def version_tuple(v):
    parts = []
    for p in v.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _supabase_headers(key):
    headers = {"apikey": key}
    if key.startswith("eyJ"):  # مفتاح JWT قديم (anon)؛ المفاتيح الجديدة sb_... تُرسل في apikey فقط
        headers["Authorization"] = f"Bearer {key}"
    return headers


def fetch_latest_update(supabase_url, anon_key, channel):
    """يستعلم REST API الخاص بـ Supabase عن أحدث صف في channel معيّن."""
    endpoint = (
        f"{supabase_url}/rest/v1/updates"
        f"?channel=eq.{channel}&order=created_at.desc&limit=1"
    )
    req = urllib.request.Request(
        endpoint,
        headers=_supabase_headers(anon_key),
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    return rows[0] if rows else None


def download_file(url, dest_path):
    print(f"[*] تحميل: {url}")
    urllib.request.urlretrieve(url, dest_path)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_minisign(deb_path, sig_path):
    if not os.path.exists(MINISIGN_PUBKEY_PATH):
        print("[!] لا يوجد مفتاح minisign عام مثبّت - سيتم تخطي التحقق من التوقيع.", file=sys.stderr)
        return False
    try:
        subprocess.run(
            ["minisign", "-V", "-p", MINISIGN_PUBKEY_PATH, "-m", deb_path, "-x", sig_path],
            check=True, capture_output=True,
        )
        return True
    except FileNotFoundError:
        print("[!] أداة minisign غير مثبتة.", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"[!] فشل التحقق من التوقيع: {e.stderr.decode(errors='ignore')}", file=sys.stderr)
        return False


def check_and_apply(dry_run=False):
    cfg = load_config()
    updates_cfg = cfg.get("updates", {})
    supabase_url = updates_cfg["supabase_url"]
    anon_key = updates_cfg["supabase_anon_key"]
    channel = updates_cfg.get("channel", "stable")

    current = get_current_version()
    print(f"[*] النسخة الحالية: {current} (قناة: {channel})")

    row = fetch_latest_update(supabase_url, anon_key, channel)
    if not row:
        print("[*] لا يوجد أي تحديث مسجّل لهذه القناة.")
        return

    latest_version = row["version"]
    if version_tuple(latest_version) <= version_tuple(current):
        print(f"[*] النظام محدّث بالفعل (أحدث نسخة متاحة: {latest_version}).")
        return

    print(f"[*] يوجد تحديث جديد: {latest_version}")
    print(f"    النوع: {row.get('kind', 'feature')}")
    print(f"    ملاحظات: {row.get('notes', '-')}")

    if dry_run:
        print("[*] وضع dry-run: لن يتم التحميل أو التطبيق.")
        return

    os.makedirs(CACHE_DIR, exist_ok=True)
    deb_name = f"novaos-apps_{latest_version}.deb"
    deb_path = os.path.join(CACHE_DIR, deb_name)
    sig_path = deb_path + ".minisig"

    release_url = row["release_url"].rstrip("/")
    download_file(f"{release_url}/{deb_name}", deb_path)

    try:
        download_file(f"{release_url}/{deb_name}.minisig", sig_path)
        signature_ok = verify_minisign(deb_path, sig_path)
    except Exception:
        signature_ok = False
        print("[!] لم يتم العثور على ملف توقيع minisign منفصل.", file=sys.stderr)

    # التحقق من sha256 إلزامي دائماً
    actual_sha = sha256_of(deb_path)
    expected_sha = row["sha256"]
    if actual_sha != expected_sha:
        print(
            f"[!] فشل التحقق من SHA256!\n"
            f"    المتوقع: {expected_sha}\n"
            f"    الفعلي:  {actual_sha}\n"
            f"    سيتم إلغاء التحديث حفاظاً على سلامة النظام.",
            file=sys.stderr,
        )
        os.remove(deb_path)
        sys.exit(1)

    if not signature_ok:
        print(
            "[!] تحذير: لم يتم التحقق من التوقيع الرقمي (minisign). "
            "سيُطبَّق التحديث بناءً على تطابق SHA256 فقط. "
            "لتفعيل التحقق الكامل، ثبّت المفتاح العام في:\n"
            f"    {MINISIGN_PUBKEY_PATH}",
            file=sys.stderr,
        )

    # نسخة احتياطية للـ rollback: نحتفظ بالحزمة السابقة المثبتة إن وُجدت
    backup_marker = os.path.join(CACHE_DIR, "previous_version.txt")
    with open(backup_marker, "w") as f:
        f.write(current)

    print("[*] تطبيق التحديث عبر helper مُصرّح...")
    result = subprocess.run(["sudo", "-n", APPLY_HELPER, deb_path, latest_version], check=False)
    if result.returncode != 0:
        print("[!] فشل تطبيق التحديث. راجع /var/log/novaos/updater.log", file=sys.stderr)
        sys.exit(1)

    print(f"[✓] تم التحديث بنجاح إلى النسخة {latest_version}")


def rollback():
    backup_marker = os.path.join(CACHE_DIR, "previous_version.txt")
    if not os.path.exists(backup_marker):
        print("[!] لا توجد نسخة سابقة محفوظة للـ rollback.", file=sys.stderr)
        sys.exit(1)
    with open(backup_marker) as f:
        prev_version = f.read().strip()
    print(f"[*] محاولة التراجع إلى النسخة: {prev_version}")
    prev_deb = os.path.join(CACHE_DIR, f"novaos-apps_{prev_version}.deb")
    if not os.path.exists(prev_deb):
        print(f"[!] ملف الحزمة السابقة غير موجود في الكاش: {prev_deb}", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run(["sudo", "-n", APPLY_HELPER, prev_deb, prev_version], check=False)
    if result.returncode == 0:
        print(f"[✓] تم التراجع بنجاح إلى {prev_version}")
    else:
        print("[!] فشل التراجع.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NovaOS Updater")
    parser.add_argument("action", choices=["check", "apply", "rollback"], default="check", nargs="?")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.action == "rollback":
        rollback()
    else:
        check_and_apply(dry_run=args.dry_run or args.action == "check")
