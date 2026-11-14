#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
التشغيل الأسبوعي المجدول لنظام الأرشفة المعمارية (SketchUp).

    python run_weekly.py
    python run_weekly.py "D:\\Projects\\2026_Project_Name\\06_3D_Models_Visuals\\SketchUp"

يمكن تجاوز المسار عبر متغير البيئة SKP_PROJECT_ROOT،
وإعدادات البريد عبر المتغيرات: SKP_EMAIL_ENABLED, SKP_SMTP_SERVER,
SKP_SMTP_PORT, SKP_SENDER_EMAIL, SKP_APP_PASSWORD, SKP_RECEIVER_EMAIL.
"""

import os
import sys

from skp_archiver_master import MasterSketchUpArchiver

# 1. المسار المطلق لمجلد SketchUp داخل المشروع المعماري (مجلد Google Drive المحلي)
DEFAULT_PROJECT_ROOT = (
    r"G:\My Drive\Projects\2026_Project_Name\06_3D_Models_Visuals\SketchUp"
)

# 2. إعدادات البريد الإلكتروني للتنبيه المشروط (App Password من Gmail)
EMAIL_SETTINGS = {
    "enabled": os.environ.get("SKP_EMAIL_ENABLED", "false").strip().lower()
    in ("1", "true", "yes", "on"),
    "smtp_server": os.environ.get("SKP_SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.environ.get("SKP_SMTP_PORT", "587")),
    "sender_email": os.environ.get("SKP_SENDER_EMAIL", ""),
    "app_password": os.environ.get("SKP_APP_PASSWORD", ""),
    "receiver_email": os.environ.get("SKP_RECEIVER_EMAIL", ""),
}


def resolve_project_root():
    """ترتيب الأولوية: وسيط سطر الأوامر > متغير البيئة > المسار الافتراضي."""
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    env_root = os.environ.get("SKP_PROJECT_ROOT", "").strip()
    if env_root:
        return env_root
    return DEFAULT_PROJECT_ROOT


def main():
    project_root = resolve_project_root()

    if project_root == DEFAULT_PROJECT_ROOT:
        print(
            "[INFO] يتم استخدام المسار الافتراضي. عدّل DEFAULT_PROJECT_ROOT أو "
            "مرّر المسار كوسيط أو اضبط SKP_PROJECT_ROOT."
        )

    if not os.path.isdir(project_root):
        print(f"[ERROR] المسار غير موجود: {project_root}")
        print("        أنشئ المجلد أو صحّح المسار ثم أعد التشغيل.")
        return 2

    if EMAIL_SETTINGS["enabled"] and not all(
        EMAIL_SETTINGS[key] for key in ("sender_email", "app_password", "receiver_email")
    ):
        print(
            "[WARN] التنبيه البريدي مفعّل لكن بيانات الدخول ناقصة. "
            "سيتم تعطيل البريد لهذه الدورة."
        )
        EMAIL_SETTINGS["enabled"] = False

    archiver = MasterSketchUpArchiver(
        project_root=project_root,
        days_threshold=14,   # ترحيل الملفات التي لم تُعدّل منذ 14 يوماً
        size_limit_mb=150,   # تنبيه Purge للملفات الأكبر من 150 ميجابايت
        email_config=EMAIL_SETTINGS,
    )

    ok = archiver.run_pipeline()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
