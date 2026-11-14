# 🏛️ Unified Architectural Archive System — SketchUp SKP Archiver

نظام أرشفة معماري آلي وإدارة إصدارات لملفات **SketchUp (`.skp`)**، مُستوحى من ممارسات
مكاتب مثل **BIG** و **Norman Foster**، ومُهيكل وفق معمارية **Andrej Karpathy Agent Graph**
مع بوابات حتمية (Deterministic Gates) وقفل صلاحيات (Read-Only) وتنبيه بريدي مشروط.

> يعتمد على مكتبة Python القياسية فقط — لا حاجة لأي تثبيت إضافي.

---

## الهيكل الهندسي القياسي

```
.
├── 01_Admin_Contracts
├── 02_Site_Data
├── 03_Concept_Design
├── 04_Schematic_Design
├── 05_Detailed_Design
├── 06_3D_Models_Visuals
│   └── SketchUp
│       ├── 01_Imports_CAD
│       ├── 02_Components_Library
│       ├── 03_WIP                 ← مجلد العمل النشط
│       ├── 04_Milestones          ← الأرشيف المقفل (Read-Only)
│       ├── 05_Exports
│       ├── config.md              ← إعدادات الجلسة ومصفوفة الصلاحيات
│       ├── graph.md               ← عقد الرسم البياني والبوابات
│       ├── checks.md              ← قائمة التحقق والقبول
│       ├── progress.md            ← سجل الحالة والأدلة (يُحدَّث آلياً)
│       ├── skp_archiver_master.py ← المحرك الرئيسي
│       └── run_weekly.py          ← نقطة التشغيل الأسبوعي
├── 07_Cost_Estimation
└── 08_Submissions
```

## كيف يعمل النظام

| العقدة | الوظيفة | البوابة الحتمية |
| :--- | :--- | :--- |
| `Node_01` | مسح ملفات `.skp` داخل `03_WIP` | الملف موجود وقابل للقراءة |
| `Node_02` | ترحيل ما تجاوز **14 يوماً** إلى `04_Milestones` + قفل Read-Only | الحجم > 0 وصلاحية الكتابة = False |
| `Node_03` | فهرسة `skp_project_index.json` ورصد الملفات > **150 MB** | JSON صالح وقابل للتحليل |
| `Node_04` | تنبيه بريدي **مشروط** فقط عند ترحيل فعلي أو خطأ | Trigger شرطي |

المخرجات: `skp_project_index.json` و `progress.md` داخل مجلد `06_3D_Models_Visuals/SketchUp`.
الملف المرحّل يُعاد تسميته إلى `<الاسم>_LOCKED_<YYYYMMDD>.skp` ويُضبط على `444`.

## التشغيل

```bash
# افتراضياً يستخدم المسار المكتوب في DEFAULT_PROJECT_ROOT
python 06_3D_Models_Visuals/SketchUp/run_weekly.py

# أو مرّر مسار مجلد SketchUp مباشرة
python 06_3D_Models_Visuals/SketchUp/run_weekly.py "/path/to/06_3D_Models_Visuals/SketchUp"

# أو عبر متغير البيئة
SKP_PROJECT_ROOT="/path/to/SketchUp" python 06_3D_Models_Visuals/SketchUp/run_weekly.py

# تشغيل سريع للمحرك وحده (تنبيهات معطّلة)
python 06_3D_Models_Visuals/SketchUp/skp_archiver_master.py "/path/to/SketchUp"
```

كود الخروج: `0` عند نجاح كل البوابات، `1` عند وجود خطأ، `2` عند مسار غير صالح.

## التنبيه البريدي (اختياري ومشروط)

لا تُخزَّن كلمة المرور داخل المستودع. اضبط متغيرات البيئة قبل التشغيل:

```bash
export SKP_EMAIL_ENABLED=true
export SKP_SENDER_EMAIL="you@gmail.com"
export SKP_APP_PASSWORD="xxxx xxxx xxxx xxxx"   # App Password من أمان حساب Google
export SKP_RECEIVER_EMAIL="you@gmail.com"
export SKP_SMTP_SERVER="smtp.gmail.com"          # اختياري
export SKP_SMTP_PORT="587"                        # اختياري
```

إن كان `SKP_EMAIL_ENABLED` غير مفعّل، يعمل النظام بالكامل بدون بريد.

## الجدولة الأسبوعية

**Windows — Task Scheduler**
```
Program:  python
Arguments: "C:\path\to\06_3D_Models_Visuals\SketchUp\run_weekly.py"
Start in:  C:\path\to\06_3D_Models_Visuals\SketchUp
Trigger:   Weekly — Saturday 08:00
```

**Linux / macOS — cron**
```cron
0 8 * * 6 cd /path/to/06_3D_Models_Visuals/SketchUp && /usr/bin/python3 run_weekly.py >> archive.log 2>&1
```

## القواعد المعتمدة (Learning Edges)

1. **Rule 01** — `os.chmod(444)` يمنع التعديل العرضي على النسخ المؤرشفة في `04_Milestones`.
2. **Rule 02** — التنبيه البريدي مشروط: لا إزعاج عندما يكون المجلد مستقراً.
3. **Rule 03** — صيغة التسمية القياسية: `[ProjectCode]_SKP_[Phase]_[Scope]_[Date]_[Rev#].skp`.

> ⚠️ تنبيه: بعد القفل لا يمكن لـ SketchUp الحفظ فوق الملف المؤرشف. لفتحه للتعديل، انسخه
> أولاً إلى `03_WIP` وأعد تسميته حسب قاعدة التسمية القياسية.
