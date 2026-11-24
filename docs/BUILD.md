# بناء NovaOS

## البناء محلياً (على Debian/Ubuntu)

```bash
git clone <رابط_المستودع> novaos && cd novaos
chmod +x build.sh
sudo ./build.sh
```

- يحتاج ~20-40 دقيقة واتصال إنترنت جيد (يحمّل كل الحزم من مرايا Debian).
- يحتاج مساحة قرص فارغة ≥ 15GB (الكاش + الصورة النهائية).
- الناتج: `novaos-YYYYMMDD.iso` + `novaos-YYYYMMDD.iso.sha256` في جذر المشروع.
- لإعادة بناء نظيفة: `sudo lb clean --purge` قبل تشغيل `build.sh` مجدداً.

## البناء على GitHub Actions

1. ادفع تاغ بصيغة `vX.Y.Z`:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
2. الـ workflow في `.github/workflows/build-iso.yml` يبني الإيزو تلقائياً
   على `ubuntu-22.04`، ثم يرفعه كـ GitHub Release مرفقاً بملف `.sha256`.
3. يمكنك أيضاً تشغيله يدوياً من تبويب Actions عبر `workflow_dispatch`.

## قبل إضافة مفتاح Gemini أو مفاتيح Supabase

- **لا تضع** `ai.key` أو مفتاح `service_role` الخاص بـ Supabase في أي ملف
  داخل هذا المستودع أو داخل صورة الـ ISO.
- عدّل `config/includes.chroot/etc/novaos/config.json` فقط بقيم
  `supabase_url` و`supabase_anon_key` (المفتاح العام للقراءة فقط).
- مفتاح Gemini يُدخل من المستخدم بعد الإقلاع عبر شاشة إعدادات "AI Assistant".

## تخصيص اسم التوزيعة

كل الملفات تستخدم `novaos` / `NovaOS` كاسم افتراضي. لتغييره:
```bash
grep -rl "novaos\|NovaOS" . | xargs sed -i 's/novaos/اسمك_الجديد/g; s/NovaOS/اسمك_الجديد/g'
```
ثم راجع يدوياً `build.sh` وملف `config/package-lists/*.list.chroot`.
