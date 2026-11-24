#!/bin/bash
# يُستدعى عبر sudo فقط من تطبيق AI Assistant لقراءة المفتاح وقت الإرسال للـ API.
set -euo pipefail
KEY_FILE="/etc/novaos/ai.key"
if [[ ! -f "$KEY_FILE" ]]; then
  echo "NO_KEY" 
  exit 2
fi
cat "$KEY_FILE"
