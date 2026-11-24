#!/bin/bash
# NovaOS - إعداد Minecraft عند أول تشغيل (Prism Launcher + OpenJDK 21 + JVM flags محسّنة)
set -euo pipefail

SILENT_IF_READY=false
if [[ "${1:-}" == "--silent-if-ready" ]]; then
  SILENT_IF_READY=true
fi

PRISM_FLATPAK_ID="org.prismlauncher.PrismLauncher"
MARKER_FILE="$HOME/.config/novaos/minecraft-setup-done"

if [[ -f "$MARKER_FILE" ]]; then
  $SILENT_IF_READY && exit 0
  echo "تم إعداد Minecraft مسبقاً. سيتم فتح Prism Launcher فقط."
  flatpak run "$PRISM_FLATPAK_ID" &
  exit 0
fi

echo "=== NovaOS: إعداد Minecraft (أول تشغيل) ==="

if ! flatpak list | grep -q "$PRISM_FLATPAK_ID"; then
  echo "[*] تثبيت Prism Launcher عبر Flatpak..."
  flatpak install -y --noninteractive flathub "$PRISM_FLATPAK_ID"
fi

# حساب ذاكرة JVM المقترحة: نصف الرام الكلي، بحد أقصى 8 جيجا وحد أدنى 2 جيجا
TOTAL_RAM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
SUGGESTED_MB=$((TOTAL_RAM_MB / 2))
if (( SUGGESTED_MB > 8192 )); then SUGGESTED_MB=8192; fi
if (( SUGGESTED_MB < 2048 )); then SUGGESTED_MB=2048; fi

# Aikar's flags (مُحسّنة لخوادم/عملاء Minecraft على JVM حديث)
AIKAR_FLAGS="-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 \
-XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch \
-XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M \
-XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 \
-XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 \
-XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem \
-XX:MaxTenuringThreshold=1"

CONFIG_DIR="$HOME/.var/app/${PRISM_FLATPAK_ID}/config/PrismLauncher"
mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_DIR/novaos-jvm-args.txt" << JVMARGS
# أُنشئ تلقائياً من سكربت first-run.sh - عدّله يدوياً إن أردت لاحقاً
-Xms${SUGGESTED_MB}M -Xmx${SUGGESTED_MB}M $AIKAR_FLAGS
JVMARGS

echo "[*] اقتراح ذاكرة JVM: ${SUGGESTED_MB}MB (من إجمالي ${TOTAL_RAM_MB}MB رام)"
echo "    افتح Prism Launcher > Settings > Java وألصق محتوى الملف التالي في JVM Arguments:"
echo "    $CONFIG_DIR/novaos-jvm-args.txt"

# تفعيل GameMode تلقائياً إن وُجد
if command -v gamemoded >/dev/null 2>&1; then
  systemctl --user enable --now gamemoded 2>/dev/null || true
  echo "[*] GameMode مفعّل. شغّل Minecraft عبر: gamemoderun <أمر التشغيل>"
fi

mkdir -p "$(dirname "$MARKER_FILE")"
touch "$MARKER_FILE"

echo "[✓] اكتمل إعداد Minecraft. جارٍ فتح Prism Launcher..."
flatpak run "$PRISM_FLATPAK_ID" &
