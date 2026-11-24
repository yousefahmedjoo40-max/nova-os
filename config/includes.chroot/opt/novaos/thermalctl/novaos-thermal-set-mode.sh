#!/bin/bash
# يُستدعى عبر sudo من thermalctl_gui.py لكتابة الوضع المطلوب فقط.
set -euo pipefail
MODE="${1:-}"
MODE_FILE="/etc/novaos/thermal_mode.conf"
case "$MODE" in
  silent|balanced|performance)
    mkdir -p "$(dirname "$MODE_FILE")"
    echo "$MODE" > "$MODE_FILE"
    echo "تم ضبط الوضع إلى: $MODE"
    ;;
  *)
    echo "وضع غير صالح: $MODE (استخدم silent|balanced|performance)" >&2
    exit 1
    ;;
esac
