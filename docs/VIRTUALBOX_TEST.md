# تجربة NovaOS على VirtualBox

## إنشاء الجهاز الافتراضي
1. New VM → النوع: Linux، الإصدار: Debian (64-bit).
2. الذاكرة: 4096MB كحد أدنى (8192MB مفضّل لتجربة Minecraft/Blender).
3. المعالج: 2 أنوية على الأقل.
4. الفيديو: فعّل **3D Acceleration**، واجعل ذاكرة الفيديو 128MB.
5. النظام → Enable EFI (special OS features) لتجربة الإقلاع بـ UEFI،
   أو اتركه معطّلاً لتجربة BIOS التقليدي (الإيزو هجين يدعم الاثنين).
6. التخزين: أضف ملف `novaos-*.iso` كـ CD/DVD قابل للإقلاع.

## الشبكة
- الوضع الافتراضي **NAT** يكفي لاختبار الإنترنت (لتحديثات APT، Gemini API،
  Supabase، تحميل Minecraft).
- لتجربة WiFi الحقيقي: VirtualBox لا يمرّر كروت WiFi فعلياً كـ WiFi، بل
  كـ Ethernet افتراضي حتى مع USB passthrough لمحول WiFi خارجي (محدودية
  معروفة في VirtualBox). لتجربة واقعية لإدارة WiFi:
  - استخدم **USB Passthrough** (Devices → USB) لتمرير دونجل WiFi USB
    فعلي للـ VM، مع تثبيت الإضافات (Extension Pack) أولاً.
  - أو اختبر الـ WiFi على جهاز حقيقي مباشرة (الطريقة الموصى بها فعلياً).

## ملاحظات حول ما لا يعمل داخل VM
- **lm-sensors / الحرارة الفعلية**: لا توجد حساسات فيزيائية، لذلك
  `thermalctl` سيعرض تحذير "لا توجد حساسات" وهذا سلوك متوقع وليس عطلاً.
- **التحكم في المراوح / fancontrol**: غير قابل للتطبيق داخل VM إطلاقاً.
- **nvidia-driver الفعلي / Vulkan GPU حقيقي**: الجهاز الافتراضي يعرض GPU
  وهمي (VBoxSVGA/VMSVGA)، فلن يُحمَّل درايفر nvidia الحقيقي، و Vulkan
  سيعمل ببرمجيات (software rendering) فقط أو لا يعمل، حسب إعدادات 3D
  Acceleration.
- **MangoHud FPS overlay**: يعمل تقنياً لكن الأرقام غير ذات معنى بدون GPU حقيقي.
- **auto-cpufreq / turbo boost**: VirtualBox لا يعرض `intel_pstate` أو
  `cpufreq/boost` حقيقيين عادة، فالدايمون سيسجّل ذلك في اللوج ولن يتعطل.
- **Guest Additions (virtualbox-guest-x11)**: يجب تفعيل "Insert Guest
  Additions CD" من قائمة Devices بعد الإقلاع إن أردت دقة شاشة ديناميكية
  وحافظة مشتركة.

## خطوات الاختبار السريع
1. أقلع من الإيزو → اختر "Live" لتجربة بدون تثبيت، أو "Install" لتشغيل Calamares.
2. تحقق من الاتصال بالإنترنت عبر أيقونة الشبكة (nm-applet).
3. افتح **ThermalCtl** وتأكد من ظهور رسالة "لا توجد حساسات" (متوقع).
4. افتح **AI Assistant** → الإعدادات → أدخل مفتاح Gemini تجريبي → جرّب سؤالاً.
5. افتح **NovaOS Updater** من القائمة وتأكد من اتصاله بـ Supabase (سيحتاج
   رابط Supabase حقيقي في config.json).
6. افتح **Minecraft** وتأكد من تثبيت Prism Launcher تلقائياً.
