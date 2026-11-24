# NovaOS

توزيعة Linux مخصصة مبنية على Debian 12 (Bookworm)، تدعم Live Boot والتثبيت
عبر Calamares، مع إدارة حرارة/أداء ذكية، مساعد نظام بالذكاء الاصطناعي
(Gemini)، نظام تحديثات عبر Supabase + GitHub Releases، ودعم جاهز لـ Minecraft.

## المحتويات
- `build.sh` — سكربت بناء الإيزو محلياً عبر live-build.
- `.github/workflows/build-iso.yml` — بناء تلقائي عند كل تاغ + رفع Release.
- `config/` — كل تهيئة live-build (حزم، hooks، ملفات مضمّنة).
- `supabase/schema.sql` — جدول التحديثات مع Row Level Security كامل.
- `docs/` — توثيق البناء، اختبار VirtualBox، وقائمة الاختبارات.

راجع `docs/BUILD.md` للبدء.

⚠️ **تذكير أمني**: لا تضع مفاتيح Gemini API أو مفتاح `service_role` الخاص
بـ Supabase داخل هذا المستودع أبداً. راجع `docs/BUILD.md` لمعرفة أين
تُدار هذه المفاتيح بأمان.
