# النشر التلقائي للتحديثات (GitHub Actions)

ملف `.github/workflows/publish-update.yml` يتفعّل تلقائياً **فقط** لما تدفع
(push) تغييراً إلى أي من هذه المسارات على فرع `main`:

- `VERSION`
- `config/includes.chroot/opt/novaos/**` (أي تطبيق: ThermalCtl، AI Assistant، Updater، Minecraft)
- `config/includes.chroot/usr/share/applications/**`
- `config/includes.chroot/etc/systemd/system/**`
- `packaging/**`

يعني: لو عدّلت أي سطر في `thermalctl_daemon.py` مثلاً ودفعته لفرع main،
الـ workflow يشتغل لوحده، ويعمل الآتي بالترتيب:

1. يقرأ رقم النسخة من ملف `VERSION` في جذر المشروع.
2. يبني حزمة `.deb` فعلية من نفس ملفات `/opt/novaos` الحالية
   (عبر `packaging/build-deb.sh`).
3. يحسب SHA256 للحزمة.
4. يوقّعها بـ minisign.
5. يرفعها كـ GitHub Release بتاج `update-vX.Y.Z`.
6. يسجّل الصف في جدول `updates` بـ Supabase مباشرة عبر REST API
   باستخدام `service_role` key (مُخزّن كسر GitHub Secret، مش في الكود أبداً).

بعد كده، أي جهاز فيه NovaOS هياخد التحديث لوحده تلقائياً من `novaos-updater.timer`
(أو فوراً عبر `sudo python3 /opt/novaos/updater/updater.py check`).

## الأسرار المطلوبة (Repo Settings → Secrets and variables → Actions)

| اسم السر                     | القيمة |
|-------------------------------|--------|
| `SUPABASE_URL`                 | رابط مشروعك، مثال: `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY`    | مفتاح `service_role` من Project Settings → API (ليس anon) |
| `MINISIGN_SECRET_KEY_B64`      | ملف `novaos.key` الخاص بـ minisign، مُرمّز Base64 بالكامل |
| `MINISIGN_PASSWORD`            | كلمة مرور مفتاح minisign (اتركها فارغة لو المفتاح بدون كلمة مرور) |

### توليد `MINISIGN_SECRET_KEY_B64`
```bash
minisign -G -p novaos.pub -s novaos.key   # مرة واحدة فقط
base64 -w0 novaos.key                     # انسخ الناتج كاملاً كقيمة السر
```
احفظ `novaos.key` نفسه في مكان آمن خارج أي مستودع Git، واحتفظ بـ `novaos.pub`
لوضعه داخل الإيزو في `/etc/novaos/novaos-minisign.pub` (الموجود فعلاً ضمن
`config/includes.chroot`، فقط ضيف الملف هناك يدوياً مرة واحدة).

## رفع رقم النسخة قبل كل تحديث

```bash
echo "1.0.1" > VERSION
git add VERSION
git commit -m "bump version to 1.0.1"
git push origin main
```

هذا السطر الوحيد (إلى جانب أي تعديل فعلي في `/opt/novaos`) كافٍ لتشغيل كل
سلسلة البناء والتوقيع والنشر والتسجيل تلقائياً.

## ⚠️ تنبيه مهم

- هذا الـ workflow يبني حزمة التطبيقات فقط (`/opt/novaos` وما يتعلق بها)،
  وليس إعادة بناء الإيزو كاملة — فتح `build-iso.yml` (المرتبط بالتاغات
  `vX.Y.Z`) يبقى منفصلاً لإصدارات التوزيعة الكبرى.
- السياسة في `supabase/schema.sql` تمنع أي كتابة بمفتاح `anon`، فلو حصل خطأ
  في السر `SUPABASE_SERVICE_ROLE_KEY` هيفشل الـ step الأخير برسالة 401/403
  واضحة في اللوج، ولن يُكتب أي صف خاطئ.
