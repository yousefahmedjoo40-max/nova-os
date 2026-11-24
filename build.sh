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
apt-get install -y live-build live-config live-boot debootstrap \
  dosfstools mtools squashfs-tools xorriso isolinux syslinux-efi grub-pc-bin \
  grub-efi-amd64-bin grub-efi-ia32-bin ca-certificates debian-archive-keyring

echo "[*] تنظيف أي بناء سابق..."
lb clean --purge || true
rm -rf cache .build

echo "[*] إعداد lb config..."
lb config \
  --distribution "$BOOKWORM" \
  --architecture amd64 \
  --binary-images iso-hybrid \
  --archive-areas "main contrib non-free non-free-firmware" \
  --mirror-bootstrap "http://deb.debian.org/debian/" \
  --mirror-binary "http://deb.debian.org/debian/" \
  --mirror-chroot "http://deb.debian.org/debian/" \
  --mirror-chroot-security "http://deb.debian.org/debian-security/" \
  --debootstrap-options "--keyring=/usr/share/keyrings/debian-archive-keyring.gpg --variant=minbase" \
  --debian-installer live \
  --bootappend-live "boot=live components quiet splash username=novaos hostname=novaos" \
  --iso-application "$DISTRO_LABEL" \
  --iso-volume "$DISTRO_LABEL" \
  --iso-publisher "NovaOS Project" \
  --memtest none \
  --win32-loader false

# debootstrap's minbase variant omits coreutils; live-build needs /usr/bin/env in chroot.
mkdir -p config/package-lists
if ! grep -qxF 'coreutils' config/package-lists/novaos.list.chroot; then
  sed -i '/# ===== نظام عام =====/a coreutils' config/package-lists/novaos.list.chroot
fi

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
