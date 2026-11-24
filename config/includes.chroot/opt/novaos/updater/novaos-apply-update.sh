#!/bin/bash
# يُستدعى عبر sudo من updater.py فقط. يثبّت حزمة .deb محددة ويحدّث ملف النسخة.
set -euo pipefail
DEB_PATH="${1:?يجب تمرير مسار ملف .deb}"
NEW_VERSION="${2:?يجب تمرير رقم النسخة}"
LOG_FILE="/var/log/novaos/updater.log"

mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date -Is)] تطبيق $DEB_PATH -> $NEW_VERSION" >> "$LOG_FILE"

if [[ ! -f "$DEB_PATH" ]]; then
  echo "ملف الحزمة غير موجود: $DEB_PATH" >> "$LOG_FILE"
  exit 1
fi

apt-get install -y --allow-downgrades "$DEB_PATH" >> "$LOG_FILE" 2>&1
echo "$NEW_VERSION" > /etc/novaos/version

echo "[$(date -Is)] تم بنجاح." >> "$LOG_FILE"
