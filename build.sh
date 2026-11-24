#!/bin/bash
# build.sh - NovaOS ISO builder (Debian 12 Bookworm live-build)
set -euo pipefail

DISTRO_NAME="novaos"
DISTRO_LABEL="NovaOS"
BOOKWORM="bookworm"

if [[ $EUID -ne 0 ]]; then
  echo "[!] شغّل هذا السكربت بصلاحيات root: sudo ./build.sh" >&2
  exit 1
fi

echo "[*] تثبيت أدوات live-build إن لم تكن موجودة..."
apt-get update
apt-get install -y live-build debootstrap \
  dosfstools mtools squashfs-tools xorriso isolinux syslinux-efi grub-pc-bin \
  grub-efi-amd64-bin grub-efi-ia32-bin ca-certificates debian-archive-keyring

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
  --bootappend-live "boot=live components quiet splash username=novaos hostname=novaos" \
  --iso-application "$DISTRO_LABEL" \
  --iso-volume "$DISTRO_LABEL" \
  --iso-publisher "NovaOS Project" \
  --memtest none \
  --win32-loader false

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
