#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Master SketchUp Archiver — Unified Architectural Archive & Version Control
==========================================================================
نظام أرشفة معماري آلي لملفات SketchUp (.skp) مبني على معمارية Agent Graph:
    Node_01 -> Node_02 -> Node_03 -> Node_04
مع بوابات حتمية (Deterministic Gates)، قفل صلاحيات (Read-Only)،
تنبيه بريدي مشروط، وفهرسة JSON.

الاستخدام البرمجي:
    from skp_archiver_master import MasterSketchUpArchiver
    MasterSketchUpArchiver(project_root=...).run_pipeline()

الاعتماديات: مكتبة Python القياسية فقط (Standard Library).
"""

import json
import os
import shutil
import smtplib
import stat
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# الحد الأقصى لمحاولات إعادة القفل/التحقق داخل البوابة (Run Limit: 3)
MAX_GATE_ATTEMPTS = 3

# المجلدات الفرعية القياسية داخل نطاق نظام SketchUp
STANDARD_SUBDIRS = [
    "01_Imports_CAD",
    "02_Components_Library",
    "03_WIP",
    "04_Milestones",
    "05_Exports",
]


def is_writable(path):
    """فحص حتمي لصلاحية الكتابة عبر بتات الصلاحيات (لا يعتمد على os.access
    الذي يُرجع True دائماً عند التشغيل بصلاحيات root)."""
    try:
        return bool(os.stat(path).st_mode & stat.S_IWRITE)
    except OSError:
        return False


class MasterSketchUpArchiver:
    """محرك الأرشفة الرئيسي: ترحيل، قفل، فهرسة، وتنبيه مشروط."""

    def __init__(
        self,
        project_root,
        days_threshold=14,
        size_limit_mb=150,
        email_config=None,
    ):
        self.project_root = os.path.abspath(project_root)
        self.wip_dir = os.path.join(self.project_root, "03_WIP")
        self.milestones_dir = os.path.join(self.project_root, "04_Milestones")
        self.index_db = os.path.join(self.project_root, "skp_project_index.json")
        self.progress_file = os.path.join(self.project_root, "progress.md")

        self.days_threshold = days_threshold
        self.size_limit_mb = size_limit_mb
        self.email_config = email_config or {}

        self.logs = []
        self.has_error = False
        self.archived_count = 0
        self.total_indexed = 0
        self.email_sent = False

        # ضمان وجود الهيكل الأساسي (Node_00 ضمني: تهيئة البيئة)
        for sub in STANDARD_SUBDIRS:
            os.makedirs(os.path.join(self.project_root, sub), exist_ok=True)

    # ------------------------------------------------------------------ #
    #  أدوات مساعدة
    # ------------------------------------------------------------------ #
    def _set_read_only(self, file_path):
        """ضبط صلاحيات الملف ليصبح للقراءة فقط (Read-Only)."""
        try:
            os.chmod(file_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            return True
        except Exception as exc:  # noqa: BLE001 - يجب تسجيل أي فشل نظامي
            self.has_error = True
            self.logs.append(
                "[ERROR] تعذر ضبط صلاحيات Read-Only للملف "
                f"{os.path.basename(file_path)}: {exc}"
            )
            return False

    def _lock_with_retries(self, dst_path):
        """قفل الملف مع إعادة المحاولة حتى MAX_GATE_ATTEMPTS مرات."""
        for attempt in range(1, MAX_GATE_ATTEMPTS + 1):
            self._set_read_only(dst_path)
            if not is_writable(dst_path):
                self.logs.append(
                    f"[PASS] تم تأكيد القفل (Read-Only) في المحاولة {attempt}/{MAX_GATE_ATTEMPTS}."
                )
                return True
            self.logs.append(
                f"[WARN] المحاولة {attempt}/{MAX_GATE_ATTEMPTS} لم تُثبّت القفل على "
                f"{os.path.basename(dst_path)}."
            )
        return False

    def _gate_verify_transfer(self, src_path, dst_path):
        """بوابة تحقق حتمية لسلامة النقل والصلاحيات.

        Gate Required: Destination Size > 0 & Write Perm == False
        """
        if os.path.exists(src_path):
            return "FAIL_SOURCE_STILL_PRESENT"
        if not os.path.exists(dst_path):
            return "FAIL_DEST_MISSING"
        if os.path.getsize(dst_path) <= 0:
            return "FAIL_EMPTY_DEST"
        if is_writable(dst_path):
            return "FAIL_STILL_WRITABLE"
        return "PASS_SECURED"

    def _resolve_destination(self, dst_path):
        """تجنّب الكتابة فوق نسخة مؤرشفة موجودة بنفس الاسم."""
        if not os.path.exists(dst_path):
            return dst_path
        base_name, ext = os.path.splitext(dst_path)
        counter = 2
        candidate = f"{base_name}_v{counter}{ext}"
        while os.path.exists(candidate):
            counter += 1
            candidate = f"{base_name}_v{counter}{ext}"
        return candidate

    # ------------------------------------------------------------------ #
    #  Node_01 + Node_02: المسح والترحيل والقفل
    # ------------------------------------------------------------------ #
    def _run_scan_and_migrate(self):
        cutoff_date = datetime.now() - timedelta(days=self.days_threshold)

        for file in sorted(os.listdir(self.wip_dir)):
            if not file.lower().endswith(".skp"):
                continue

            src_path = os.path.join(self.wip_dir, file)
            if not os.path.isfile(src_path):
                continue

            # Gate: File Exists & Read Access == True
            if not os.access(src_path, os.R_OK):
                self.has_error = True
                self.logs.append(f"[FAIL] تعذر قراءة الملف: {file} (بوابة Node_01).")
                continue

            mod_date = datetime.fromtimestamp(os.path.getmtime(src_path))
            if mod_date >= cutoff_date:
                continue  # لا يزال نشطاً داخل WIP

            base_name, ext = os.path.splitext(file)
            new_name = f"{base_name}_LOCKED_{mod_date.strftime('%Y%m%d')}{ext}"
            dst_path = self._resolve_destination(
                os.path.join(self.milestones_dir, new_name)
            )

            try:
                shutil.move(src_path, dst_path)
            except Exception as exc:  # noqa: BLE001
                self.has_error = True
                self.logs.append(f"[FAIL] فشل ترحيل الملف {file}: {exc}")
                continue

            self._lock_with_retries(dst_path)
            gate_status = self._gate_verify_transfer(src_path, dst_path)

            if gate_status == "PASS_SECURED":
                self.archived_count += 1
                self.logs.append(
                    f"[PASS] ترحيل وقفل الملف: {file} -> {os.path.basename(dst_path)} "
                    f"({gate_status})"
                )
            else:
                self.has_error = True
                self.logs.append(
                    f"[FAIL] فشل بوابة التحقق لنقل الملف: {file} -> "
                    f"{os.path.basename(dst_path)} ({gate_status})"
                )

    # ------------------------------------------------------------------ #
    #  Node_03: الفهرسة الحتمية الشاملة
    # ------------------------------------------------------------------ #
    def _run_indexing(self):
        catalog = []

        for dirpath, _, filenames in os.walk(self.project_root):
            for file in filenames:
                if not file.lower().endswith(".skp"):
                    continue

                full_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(full_path, self.project_root)
                stage = rel_path.split(os.sep)[0]
                size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2)

                locked = not is_writable(full_path)
                if locked:
                    status = "Locked (Read-Only)"
                elif size_mb > self.size_limit_mb:
                    status = f"Requires Purge (>{self.size_limit_mb}MB)"
                else:
                    status = "Normal (Editable)"

                catalog.append(
                    {
                        "file_name": file,
                        "stage": stage,
                        "size_mb": size_mb,
                        "last_modified": datetime.fromtimestamp(
                            os.path.getmtime(full_path)
                        ).isoformat(),
                        "status": status,
                        "relative_path": rel_path,
                    }
                )

        catalog.sort(key=lambda item: item["relative_path"])

        # Gate: JSON Schema Valid & Parsable
        payload = json.dumps(catalog, ensure_ascii=False, indent=4)
        json.loads(payload)  # تحقق حتمي قبل الكتابة

        with open(self.index_db, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")

        self.total_indexed = len(catalog)
        return catalog

    # ------------------------------------------------------------------ #
    #  progress.md: سجل الحالة والأدلة
    # ------------------------------------------------------------------ #
    def _write_progress_report(self):
        summary_text = (
            f"Total Indexed: {self.total_indexed} | "
            f"Newly Archived & Locked: {self.archived_count} | "
            f"Error State: {self.has_error}"
        )

        with open(self.progress_file, "w", encoding="utf-8") as handle:
            handle.write("# Active Progress & Gate Evidence Log\n\n")
            handle.write(f"- **Last Execution:** {datetime.now().isoformat(timespec='seconds')}\n")
            handle.write(f"- **Total Indexed Models:** {self.total_indexed}\n")
            handle.write(f"- **Newly Secured to Milestones:** {self.archived_count}\n")
            handle.write(f"- **Email Alert Sent:** {'Yes' if self.email_sent else 'No (conditional trigger not met)'}\n")
            handle.write(
                "- **System Health:** "
                f"{'⚠️ Error Detected' if self.has_error else '✅ Optimal'}\n\n"
            )
            handle.write("## Execution & Gate Logs\n")
            if not self.logs:
                handle.write("- No file migrations triggered during this cycle.\n")
            for log in self.logs:
                handle.write(f"- {log}\n")

        return summary_text

    # ------------------------------------------------------------------ #
    #  Node_04: التنبيه البريدي المشروط
    # ------------------------------------------------------------------ #
    def _send_conditional_email(self, archived_count, total_files, summary):
        """إرسال تنبيه عبر SMTP فقط عند الترحيل الفعلي أو حدوث خطأ تقني."""
        if not self.email_config.get("enabled"):
            print("[WARN] التنبيه البريدي غير مفعّل في الإعدادات.")
            self.logs.append("[INFO] تم تخطي الإرسال: التنبيه البريدي غير مفعّل.")
            return False

        missing = [
            key
            for key in ("sender_email", "app_password", "receiver_email", "smtp_server")
            if not self.email_config.get(key)
        ]
        if missing:
            self.has_error = True
            self.logs.append(
                "[ERROR] إعدادات البريد ناقصة (مفقود: " + ", ".join(missing) + ")."
            )
            return False

        try:
            status_prefix = (
                "⚠️ خطأ في نظام الأرشفة"
                if self.has_error
                else f"📦 أرشفة جديدة ({archived_count} ملفات)"
            )
            subject = f"{status_prefix} - {datetime.now().strftime('%Y-%m-%d')}"

            body = (
                "تقرير نظام الأرشفة المعمارية الآلي (SketchUp):\n\n"
                f"- الحالة: {'يوجد خطأ يتطلب المراجعة' if self.has_error else 'تم ترحيل وقفل ملفات قديمة بنجاح'}\n"
                f"- إجمالي النماذج المفهرسة: {total_files}\n"
                f"- الملفات المرحلة لـ Milestones: {archived_count}\n\n"
                f"ملخص السجل:\n{summary}\n\n"
                "التفاصيل الكاملة محفوظة في ملف progress.md داخل مجلد المشروع."
            )

            message = MIMEMultipart()
            message["From"] = self.email_config["sender_email"]
            message["To"] = self.email_config["receiver_email"]
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain", "utf-8"))

            server = smtplib.SMTP(
                self.email_config["smtp_server"],
                int(self.email_config.get("smtp_port", 587)),
                timeout=30,
            )
            server.starttls()
            server.login(
                self.email_config["sender_email"], self.email_config["app_password"]
            )
            server.send_message(message)
            server.quit()

            self.email_sent = True
            print("[SUCCESS] تم إرسال التنبيه البريدي المشروط بنجاح.")
            self.logs.append("[PASS] تم إرسال التنبيه البريدي المشروط.")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] فشل إرسال البريد الإلكتروني: {exc}")
            self.logs.append(f"[ERROR] فشل إرسال البريد الإلكتروني: {exc}")
            return False

    # ------------------------------------------------------------------ #
    #  تشغيل المسار الكامل
    # ------------------------------------------------------------------ #
    def run_pipeline(self):
        if not os.path.isdir(self.project_root):
            raise FileNotFoundError(f"مسار المشروع غير موجود: {self.project_root}")

        print(f"[INFO] بدء مسار الأرشفة: {self.project_root}")

        try:
            # Node_01 + Node_02
            self._run_scan_and_migrate()
            # Node_03
            self._run_indexing()
            summary = self._write_progress_report()

            # Node_04 — الشرط: archived > 0 أو خطأ
            if self.archived_count > 0 or self.has_error:
                self._send_conditional_email(
                    self.archived_count, self.total_indexed, summary
                )
                self._write_progress_report()
            else:
                print(
                    "[INFO] تمت الفهرسة بنجاح. لا توجد ملفات جديدة للترحيل، "
                    "تم تخطي الإشعار البريدي."
                )

        except Exception as exc:  # noqa: BLE001
            self.has_error = True
            error_msg = f"[CRITICAL ERROR] خطأ غير متوقع في مسار الأرشفة: {exc}"
            print(error_msg)
            self.logs.append(error_msg)
            try:
                self._write_progress_report()
            except Exception:  # noqa: BLE001
                print("[ERROR] تعذر كتابة progress.md.")
            self._send_conditional_email(
                self.archived_count, self.total_indexed, error_msg
            )
            try:
                self._write_progress_report()
            except Exception:  # noqa: BLE001
                pass

        print(
            f"[DONE] ملفات مفهرسة: {self.total_indexed} | "
            f"مرحّلة: {self.archived_count} | "
            f"حالة النظام: {'ERROR' if self.has_error else 'OK'}"
        )
        return not self.has_error

    # ------------------------------------------------------------------ #
    #  أداة بحث فورية داخل الفهرس
    # ------------------------------------------------------------------ #
    def search_model(self, keyword):
        if not os.path.exists(self.index_db):
            return []
        with open(self.index_db, "r", encoding="utf-8") as handle:
            catalog = json.load(handle)
        keyword = keyword.lower()
        return [item for item in catalog if keyword in item["file_name"].lower()]


if __name__ == "__main__":
    # تشغيل سريع: python skp_archiver_master.py <مسار_مجلد_SketchUp>
    if len(sys.argv) < 2:
        print("الاستخدام: python skp_archiver_master.py <project_root>")
        raise SystemExit(2)
    ok = MasterSketchUpArchiver(sys.argv[1]).run_pipeline()
    raise SystemExit(0 if ok else 1)
