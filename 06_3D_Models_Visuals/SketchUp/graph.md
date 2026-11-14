# Graph Execution Specification

## Nodes Definition
- Node_01: [Baseline Scan] مسح مجلد العمل النشط 03_WIP واستخراج أحجام وتواريخ تعديل ملفات SketchUp (.skp).
- Node_02: [Migration & Lock] ترحيل الملفات الأقدم من 14 يوماً إلى 04_Milestones وتطبيق خاصية القراءة فقط (Read-Only).
- Node_03: [Deterministic Indexing] تحديث ملف skp_project_index.json ومراقبة الملفات التي تتجاوز 150 ميجابايت وتحتاج تنظيف (Purge).
- Node_04: [Conditional Alerting] إرسال تنبيه عبر البريد الإلكتروني فقط عند نجاح الترحيل الفعلي لملفات جديدة أو حدوث خطأ تقني.

## Edges & Dependency Flow
- Node_01 -> Node_02 (Gate Required: File Age > 14 Days & Path Verification)
- Node_02 -> Node_03 (Gate Required: Read-Only Permission Check & Size Evaluation)
- Node_03 -> Node_04 (Gate Required: Index JSON Schema Validity & Change/Error Detection)

## Node & Gate Status Matrix

| Node ID | Scope / Target File | Gate Evaluator | Max Retries | Status |
| :--- | :--- | :--- | :--- | :--- |
| `node_01` | `03_WIP/*.skp` | File Exists & Read Access == True | 3 | `ready` |
| `node_02` | `04_Milestones/*` | Destination Size > 0 & Write Perm == False | 3 | `ready` |
| `node_03` | `skp_project_index.json` | JSON Schema Valid & Parsable | 1 | `ready` |
| `node_04` | Email Alert Target | Conditional Trigger (Archived > 0 or Error) | 1 | `ready` |

## Proved Rules (Learning Edges)
1. Rule 01: قفل الصلاحيات (Read-Only) عبر `os.chmod` يمنع تماماً التعديل العرضي على النسخ المؤرشفة في Milestones.
2. Rule 02: التنبيه البريدي المشروط يمنع إزعاج المستخدم برسائل دورية عندما يكون المجلد مستقراً ولا توجد ملفات جديدة للترحيل.
3. Rule 03: الصيغة القياسية لتسمية الملفات هي `[ProjectCode]_SKP_[Phase]_[Scope]_[Date]_[Rev#].skp`.
