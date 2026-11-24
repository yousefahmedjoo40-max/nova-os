#!/usr/bin/env python3
"""
ThermalCtl Daemon - NovaOS
يقرأ الحرارة/الاستهلاك، يكتب حالة حية إلى /run/novaos/thermal_status.json،
ويطبّق أوضاع الأداء (Silent / Balanced / Performance) عبر cpufreq و TLP.
يعمل كخدمة systemd: thermalctl.service
"""
import json
import os
import subprocess
import time
import glob
import logging
import signal
import sys

STATUS_PATH = "/run/novaos/thermal_status.json"
MODE_FILE = "/etc/novaos/thermal_mode.conf"
LOG_PATH = "/var/log/novaos/thermalctl.log"
POLL_INTERVAL = 2.0

MODES = {
    "silent": {
        "governor": "powersave",
        "max_freq_pct": 60,
        "turbo": False,
    },
    "balanced": {
        "governor": "schedutil",
        "max_freq_pct": 100,
        "turbo": True,
    },
    "performance": {
        "governor": "performance",
        "max_freq_pct": 100,
        "turbo": True,
    },
}

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("thermalctl")

running = True


def handle_sigterm(signum, frame):
    global running
    running = False


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


def read_cpu_temps():
    """يحاول lm-sensors أولاً، ثم /sys/class/thermal كبديل."""
    temps = []
    try:
        out = subprocess.check_output(["sensors", "-j"], stderr=subprocess.DEVNULL)
        data = json.loads(out)
        for chip, readings in data.items():
            for key, vals in readings.items():
                if isinstance(vals, dict):
                    for sub_k, sub_v in vals.items():
                        if sub_k.endswith("_input") and isinstance(sub_v, (int, float)):
                            temps.append(float(sub_v))
    except Exception as e:
        log.debug("sensors -j غير متاح: %s", e)

    if not temps:
        for zone in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            try:
                with open(zone) as f:
                    raw = int(f.read().strip())
                    temps.append(raw / 1000.0)
            except Exception:
                continue

    return temps


def read_cpu_usage():
    try:
        import psutil
        return psutil.cpu_percent(interval=None)
    except ImportError:
        return None


def read_ram_usage():
    try:
        import psutil
        return psutil.virtual_memory().percent
    except ImportError:
        return None


def read_gpu_info():
    """يحاول قراءة حرارة/استهلاك GPU عبر nvidia-smi إن وُجد، أو يرجع None."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        temp_str, util_str = [x.strip() for x in out.split(",")]
        return {"temp": float(temp_str), "usage": float(util_str)}
    except Exception:
        return None


def get_current_mode():
    try:
        with open(MODE_FILE) as f:
            mode = f.read().strip()
            if mode in MODES:
                return mode
    except FileNotFoundError:
        pass
    return "balanced"


def set_cpu_governor(governor):
    cpu_paths = glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor")
    for p in cpu_paths:
        try:
            with open(p, "w") as f:
                f.write(governor)
        except PermissionError:
            log.warning("لا توجد صلاحية كتابة على %s (تأكد من تشغيل الدايمون كـ root)", p)
        except FileNotFoundError:
            pass  # قد لا يدعم المعالج cpufreq (شائع داخل الأجهزة الافتراضية)


def set_turbo(enabled: bool):
    # Intel: /sys/devices/system/cpu/intel_pstate/no_turbo (0=تشغيل التوربو)
    intel_path = "/sys/devices/system/cpu/intel_pstate/no_turbo"
    amd_path = "/sys/devices/system/cpu/cpufreq/boost"
    if os.path.exists(intel_path):
        try:
            with open(intel_path, "w") as f:
                f.write("0" if enabled else "1")
        except PermissionError:
            log.warning("لا توجد صلاحية للتحكم في intel_pstate turbo")
    elif os.path.exists(amd_path):
        try:
            with open(amd_path, "w") as f:
                f.write("1" if enabled else "0")
        except PermissionError:
            log.warning("لا توجد صلاحية للتحكم في cpufreq boost")
    else:
        log.info("لا يوجد دعم turbo معروف في هذا الجهاز (طبيعي داخل VM)")


def apply_mode(mode_name):
    cfg = MODES.get(mode_name, MODES["balanced"])
    log.info("تطبيق الوضع: %s", mode_name)
    set_cpu_governor(cfg["governor"])
    set_turbo(cfg["turbo"])
    # TLP: نفعّل TLP نفسه دائماً لكن نمرر له تلميح الوضع عبر متغير بيئة لمن يريد تخصيصه لاحقاً
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "tlp"], check=False)
        subprocess.run(["tlp", mode_name if mode_name != "balanced" else "start"],
                        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        log.info("TLP غير مثبت")


def write_status(temps, cpu_usage, ram_usage, gpu_info, mode, sensors_available):
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    status = {
        "timestamp": time.time(),
        "sensors_available": sensors_available,
        "cpu_temp_avg": round(sum(temps) / len(temps), 1) if temps else None,
        "cpu_temp_max": round(max(temps), 1) if temps else None,
        "cpu_usage_pct": cpu_usage,
        "ram_usage_pct": ram_usage,
        "gpu": gpu_info,
        "mode": mode,
    }
    tmp_path = STATUS_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(status, f)
    os.replace(tmp_path, STATUS_PATH)


def main():
    log.info("بدء تشغيل thermalctl daemon")
    last_mode = None
    no_sensors_warned = False

    while running:
        temps = read_cpu_temps()
        sensors_available = len(temps) > 0

        if not sensors_available and not no_sensors_warned:
            log.warning(
                "لم يتم العثور على أي حساسات حرارة (طبيعي داخل VirtualBox/VMware). "
                "سيستمر عرض باقي الإحصائيات بدون بيانات حرارة."
            )
            no_sensors_warned = True

        cpu_usage = read_cpu_usage()
        ram_usage = read_ram_usage()
        gpu_info = read_gpu_info()
        mode = get_current_mode()

        if mode != last_mode:
            apply_mode(mode)
            last_mode = mode

        # حماية تلقائية: لو الحرارة تجاوزت 90°م نقفل التوربو فوراً بغض النظر عن الوضع
        if temps and max(temps) >= 90:
            log.warning("حرارة مرتفعة جداً (%.1f°م) - قفل التوربو تلقائياً", max(temps))
            set_turbo(False)

        write_status(temps, cpu_usage, ram_usage, gpu_info, mode, sensors_available)
        time.sleep(POLL_INTERVAL)

    log.info("إيقاف thermalctl daemon")


if __name__ == "__main__":
    main()
