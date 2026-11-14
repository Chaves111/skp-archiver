# Session Metadata & Environment Specs

Task: بناء وتشغيل نظام أرشفة آلي، تتبع إصدارات، قفل أمني (Read-Only)، وتنبيه ذكي لملفات SketchUp الهندسية.
Deliverable & Output Path: ./06_3D_Models_Visuals/SketchUp/skp_project_index.json & progress.md
Acceptance Checks:
1. مسح ملفات .skp في مجلد 03_WIP.
2. ترحيل الملفات الأقدم من 14 يوماً إلى 04_Milestones.
3. قفل الصلاحيات تلقائياً (Read-Only) على الملفات المرحلة.
4. رصد الملفات التي تتجاوز 150 ميجابايت للتنبيه بضرورة التنظيف (Purge).
5. إرسال تنبيه بريدي فقط عند ترحيل ملفات جديدة أو حدوث خطأ تقني.
Source Material: ./06_3D_Models_Visuals/SketchUp/03_WIP
Allowed Changes: مجلدات المشروع المحددة ضمن نطاق 06_3D_Models_Visuals/SketchUp فقط.
Run Limit: 3 محاولات إعادة تشغيل عند فشل بوابة النقل.

## Active Permission Matrix
- File System Reads: [x] Allowed inside ./06_3D_Models_Visuals/SketchUp/
- File System Writes: [x] Restricted to 04_Milestones, skp_project_index.json, and progress.md
- Network / API Calls: [x] SMTP / Gmail API enabled for conditional alerts only
- Subprocess Execution: [x] Local Python Environment / Task Scheduler

## Runtime Parameters
| Parameter | Value | Source |
| :--- | :--- | :--- |
| `project_root` | مسار مجلد SketchUp | `SKP_PROJECT_ROOT` أو وسيط سطر الأوامر |
| `days_threshold` | 14 يوماً | `run_weekly.py` |
| `size_limit_mb` | 150 ميجابايت | `run_weekly.py` |
| `MAX_GATE_ATTEMPTS` | 3 | `skp_archiver_master.py` |
| `SMTP_HOST` | `smtp.gmail.com` | `SKP_SMTP_SERVER` |
| `SMTP_PORT` | 587 (STARTTLS) | `SKP_SMTP_PORT` |
| `EMAIL_ENABLED` | `false` افتراضياً | `SKP_EMAIL_ENABLED` |

## Secrets Policy
لا تُخزَّن كلمة مرور التطبيقات (App Password) داخل ملفات المشروع أو مستودع Git.
تُمرَّر حصراً عبر متغيرات البيئة أو Task Scheduler الخاص بالنظام.
