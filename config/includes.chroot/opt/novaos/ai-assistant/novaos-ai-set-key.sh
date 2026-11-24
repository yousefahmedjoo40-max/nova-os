#!/bin/bash
# يُستدعى فقط عبر sudo من تطبيق AI Assistant لحفظ المفتاح بأمان.
# الاستخدام: novaos-ai-set-key.sh   (يقرأ المفتاح من stdin، سطر واحد)
set -euo pipefail
KEY_FILE="/etc/novaos/ai.key"
umask 077
read -r API_KEY
if [[ -z "${API_KEY:-}" ]]; then
  echo "لم يتم إدخال مفتاح" >&2
  exit 1
fi
printf '%s' "$API_KEY" > "$KEY_FILE"
chmod 600 "$KEY_FILE"
chown root:root "$KEY_FILE"
echo "تم حفظ المفتاح بنجاح."
