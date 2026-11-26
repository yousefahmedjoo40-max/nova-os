#!/bin/bash
# build.sh - NeonOS ISO builder (Debian 12 Bookworm live-build)
set -euo pipefail

DISTRO_NAME="neonos"
DISTRO_LABEL="NeonOS"
BOOKWORM="bookworm"

if [[ $EUID -ne 0 ]]; then
  echo "[!] شغّل هذا السكربت بصلاحيات root: sudo ./build.sh" >&2
  exit 1
fi

echo "[*] تثبيت أدوات live-build إن لم تكن موجودة..."
apt-get update
apt-get install -y curl debootstrap \
  dosfstools mtools squashfs-tools xorriso isolinux syslinux-efi grub-pc-bin \
  grub-efi-amd64-bin grub-efi-ia32-bin ca-certificates debian-archive-keyring syslinux syslinux-utils

echo "[*] تثبيت live-build الحديث من Debian 12 (نسخة Ubuntu قديمة جداً)..."
CUR_VER=$(dpkg-query -W -f='${Version}' live-build 2>/dev/null || echo "none")
if [[ "$CUR_VER" != 1:202* ]]; then
  BASE="http://deb.debian.org/debian/pool/main/l/live-build/"
  DEB_NAME=$(curl -fsSL "$BASE" | grep -o 'live-build_20230502[^"<]*_all\.deb' | head -n1 || true)
  [[ -z "$DEB_NAME" ]] && DEB_NAME="live-build_20230502_all.deb"
  echo "[*] تحميل $DEB_NAME"
  curl -fsSL -o /tmp/live-build.deb "${BASE}${DEB_NAME}"
  apt-get install -y /tmp/live-build.deb
fi

LB_VER=$(dpkg-query -W -f='${Version}' live-build 2>/dev/null || echo "none")
echo "[*] نسخة live-build: $LB_VER"
if [[ "$LB_VER" == 3.* || "$LB_VER" == "none" ]]; then
  echo "[!] نسخة live-build قديمة جداً ولا تدعم Debian 12." >&2
  echo "[!] غيّر runs-on في ملف الـ workflow إلى ubuntu-24.04" >&2
  exit 1
fi

echo "[*] التأكد من مفتاح توقيع Debian..."
if [[ ! -f /usr/share/keyrings/debian-archive-keyring.gpg ]]; then
  if [[ -f /usr/share/keyrings/debian-archive-keyring.pgp ]]; then
    ln -sf /usr/share/keyrings/debian-archive-keyring.pgp /usr/share/keyrings/debian-archive-keyring.gpg
  else
    echo "[!] مفتاح debian-archive-keyring غير موجود" >&2
    exit 1
  fi
fi

echo "[*] تنظيف أي بناء سابق..."
lb clean --purge || true
rm -rf cache .build

echo "[*] إعداد lb config..."
lb config \
  --mode debian \
  --system live \
  --mirror-bootstrap "http://deb.debian.org/debian/" \
  --mirror-chroot "http://deb.debian.org/debian/" \
  --mirror-chroot-security "http://security.debian.org/debian-security" \
  --mirror-binary "http://deb.debian.org/debian/" \
  --mirror-binary-security "http://security.debian.org/debian-security" \
  --distribution "$BOOKWORM" \
  --architecture amd64 \
  --binary-images iso-hybrid \
  --archive-areas "main contrib non-free non-free-firmware" \
  --debian-installer none \
  --bootappend-live "boot=live components quiet splash username=neon hostname=neonos" \
  --iso-application "$DISTRO_LABEL" \
  --iso-volume "$DISTRO_LABEL" \
  --iso-publisher "NeonOS Project" \
  --memtest none \
  --win32-loader false

echo "[*] ضبط صلاحيات سكربتات المشروع..."
chmod +x config/hooks/live/*.hook.chroot 2>/dev/null || true
find config/includes.chroot/opt -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} + 2>/dev/null || true

echo "[*] فحص الحزم مقابل مستودع Debian 12 (يحذف أي حزمة غير موجودة تلقائياً)..."
python3 - << 'PYEOF'
import glob, lzma, os, sys, urllib.request
mirror = os.environ.get("DEBIAN_MIRROR", "http://deb.debian.org/debian")
avail = set()
try:
    for area in ["main", "contrib", "non-free", "non-free-firmware"]:
        url = f"{mirror}/dists/bookworm/{area}/binary-amd64/Packages.xz"
        text = lzma.decompress(urllib.request.urlopen(url, timeout=90).read()).decode("utf-8", "ignore")
        for line in text.splitlines():
            if line.startswith("Package: "):
                avail.add(line[9:].strip())
            elif line.startswith("Provides: "):
                for item in line[10:].split(","):
                    avail.add(item.strip().split(" ")[0])
except Exception as e:
    print(f"[!] تعذّر فحص الحزم ({e}) - سنكمل بدون فحص")
    sys.exit(0)

for path in glob.glob("config/package-lists/*.list.chroot"):
    kept, dropped = [], []
    for line in open(path, encoding="utf-8").read().splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            kept.append(line); continue
        if name in avail:
            kept.append(line)
        else:
            dropped.append(name)
    open(path, "w", encoding="utf-8").write("\n".join(kept) + "\n")
    for d in dropped:
        print(f"[!] حزمة غير موجودة في Debian 12 وتم تخطيها: {d}")
print("[✓] انتهى فحص الحزم")
PYEOF

echo "[*] بدء البناء... قد يأخذ وقتاً طويلاً."
lb build 2>&1 | tee build.log

ISO_FILE=$(ls -1 live-image-amd64.hybrid.iso 2>/dev/null || true)
if [[ -z "$ISO_FILE" ]]; then
  echo "[!] فشل العثور على ملف ISO الناتج. راجع build.log" >&2
  exit 1
fi

FINAL_NAME="${DISTRO_NAME}-$(date +%Y%m%d).iso"
mv "$ISO_FILE" "$FINAL_NAME"
sha256sum "$FINAL_NAME" > "${FINAL_NAME}.sha256"

echo "[✓] تم بناء الإيزو بنجاح: $FINAL_NAME"
echo "[✓] بصمة SHA256: $(cat "${FINAL_NAME}.sha256")"
