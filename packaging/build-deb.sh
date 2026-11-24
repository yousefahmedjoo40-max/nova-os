#!/bin/bash
# packaging/build-deb.sh
# يبني حزمة novaos-apps_<version>.deb من نفس الملفات المستخدمة في الإيزو
# (config/includes.chroot/opt/novaos + الـ systemd units + desktop files).
# الاستخدام: ./packaging/build-deb.sh <version>  (مثال: ./packaging/build-deb.sh 1.0.1)
set -euo pipefail

VERSION="${1:?مرر رقم النسخة، مثال: 1.0.1}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_ROOT="$REPO_ROOT/packaging/pkgroot"
OUT_DEB="$REPO_ROOT/novaos-apps_${VERSION}.deb"

rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/opt"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/etc/systemd/system"

# 1) ملف control بنفس رقم النسخة
sed "s/__VERSION__/$VERSION/" "$REPO_ROOT/packaging/DEBIAN/control.template" \
  > "$PKG_ROOT/DEBIAN/control"

# 2) نسخ تطبيقات /opt/novaos (نفس المصدر المستخدم في بناء الإيزو)
cp -r "$REPO_ROOT/config/includes.chroot/opt/novaos" "$PKG_ROOT/opt/"

# 3) نسخ اختصارات القائمة
cp "$REPO_ROOT/config/includes.chroot/usr/share/applications/"*.desktop \
  "$PKG_ROOT/usr/share/applications/"

# 4) نسخ وحدات systemd
cp "$REPO_ROOT/config/includes.chroot/etc/systemd/system/"*.service \
  "$REPO_ROOT/config/includes.chroot/etc/systemd/system/"*.timer \
  "$PKG_ROOT/etc/systemd/system/" 2>/dev/null || true

# 5) سكربتات postinst/postrm لتفعيل/إعادة تشغيل الخدمات بعد التثبيت
cat > "$PKG_ROOT/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e
chmod +x /opt/novaos/*/*.sh /opt/novaos/*/*.py 2>/dev/null || true
systemctl daemon-reload || true
systemctl try-restart thermalctl.service || true
exit 0
POSTINST
chmod 755 "$PKG_ROOT/DEBIAN/postinst"

# صلاحيات ملكية نظيفة (root:root) ليتوافق مع dpkg
chmod -R go-w "$PKG_ROOT"

echo "[*] بناء الحزمة: $OUT_DEB"
dpkg-deb --root-owner-group --build "$PKG_ROOT" "$OUT_DEB"

echo "[✓] تم بناء: $OUT_DEB"
echo "$OUT_DEB"
