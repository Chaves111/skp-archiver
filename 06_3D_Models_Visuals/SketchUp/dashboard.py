#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
لوحة مراقبة نظام الأرشفة المعمارية (SketchUp Archive Dashboard)
================================================================
خادم صغير بمكتبة Python القياسية فقط، يقرأ skp_project_index.json
ويعرض الملفات المؤرشفة، والملفات التي تحتاج تنظيفاً (Purge).

    python dashboard.py
    python dashboard.py --root "G:\\...\\06_3D_Models_Visuals\\SketchUp" --port 8080

ثم افتح: http://127.0.0.1:8080
"""

import argparse
import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>لوحة الأرشفة المعمارية — SketchUp</title>
<style>
  :root {
    --bg: #f4f2ee; --card: #ffffff; --ink: #1d2430; --muted: #6b7480;
    --line: #e3ded6; --accent: #1f4d3f; --warn: #b4531f; --lock: #2f6b57;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Segoe UI", "Tahoma", system-ui, sans-serif;
    padding: 28px 20px 60px;
  }
  .wrap { max-width: 1080px; margin: 0 auto; }
  header { display: flex; flex-wrap: wrap; gap: 14px; align-items: baseline; justify-content: space-between; }
  h1 { font-size: 24px; margin: 0; letter-spacing: -.2px; }
  h1 span { color: var(--muted); font-weight: 400; font-size: 15px; display: block; margin-top: 4px; }
  button {
    border: 1px solid var(--line); background: var(--card); color: var(--ink);
    padding: 9px 16px; border-radius: 8px; font: inherit; font-size: 14px; cursor: pointer;
  }
  button:hover { border-color: var(--accent); color: var(--accent); }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 22px 0 8px; }
  .stat { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; }
  .stat b { display: block; font-size: 28px; line-height: 1.2; margin-bottom: 4px; }
  .stat small { color: var(--muted); font-size: 13px; }
  .stat.warn b { color: var(--warn); }
  .stat.lock b { color: var(--lock); }
  section { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; margin-top: 16px; }
  section h2 { font-size: 16px; margin: 0 0 4px; }
  section p.hint { color: var(--muted); font-size: 13px; margin: 0 0 14px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: right; padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; font-size: 12.5px; letter-spacing: .2px; }
  tr:last-child td { border-bottom: none; }
  td.num { white-space: nowrap; font-variant-numeric: tabular-nums; }
  code { background: #f6f4f0; padding: 2px 6px; border-radius: 5px; font-size: 12.5px; direction: ltr; display: inline-block; }
  .tag { display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 12px; white-space: nowrap; }
  .tag.purge { background: #fbeee4; color: var(--warn); }
  .tag.locked { background: #e9f2ee; color: var(--lock); }
  .tag.normal { background: #eef1f5; color: #48525f; }
  .empty { color: var(--muted); font-size: 14px; padding: 6px 0; }
  .error { border-color: #e6c5b3; background: #fdf4ef; color: #8a3d12; }
  footer { color: var(--muted); font-size: 12.5px; margin-top: 20px; text-align: center; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>لوحة الأرشفة المعمارية
      <span>نظام إصدارات SketchUp — البوابات الحتمية وحالة القفل</span>
    </h1>
    <button id="refresh">تحديث البيانات</button>
  </header>

  <div class="stats">
    <div class="stat"><b id="s-total">—</b><small>إجمالي النماذج المفهرسة</small></div>
    <div class="stat lock"><b id="s-locked">—</b><small>ملفات مقفلة في Milestones</small></div>
    <div class="stat warn"><b id="s-purge">—</b><small>تحتاج تنظيفاً (أكبر من 150 م.ب)</small></div>
    <div class="stat"><b id="s-size">—</b><small>الحجم الكلي (ميجابايت)</small></div>
  </div>

  <div id="notice"></div>

  <section id="sec-purge">
    <h2>ملفات تحتاج تنظيفاً (Purge)</h2>
    <p class="hint">تجاوزت 150 ميجابايت — نظّف مكوّناتها غير المستخدمة أو صدّرها ثم احذف النسخة الثقيلة.</p>
    <div id="t-purge"></div>
  </section>

  <section id="sec-locked">
    <h2>الأرشيف المقفل (Milestones)</h2>
    <p class="hint">ملفات تجاوزت 14 يوماً وتم ترحيلها وتثبيتها للقراءة فقط.</p>
    <div id="t-locked"></div>
  </section>

  <section id="sec-wip">
    <h2>ملفات العمل النشط</h2>
    <p class="hint">لا تزال قابلة للتعديل داخل مراحل المشروع.</p>
    <div id="t-wip"></div>
  </section>

  <footer>يتم التحديث من skp_project_index.json · <span id="stamp">—</span></footer>
</div>

<script>
const fmt = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(n);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function table(rows, emptyText) {
  if (!rows.length) return '<div class="empty">' + emptyText + '</div>';
  const body = rows.map((r) => {
    const cls = r.status.startsWith('Locked') ? 'locked' : (r.status.startsWith('Requires') ? 'purge' : 'normal');
    return '<tr>'
      + '<td><code>' + esc(r.file_name) + '</code><div style="color:#8a929c;font-size:12px;margin-top:4px">' + esc(r.relative_path) + '</div></td>'
      + '<td class="num">' + fmt(r.size_mb) + ' MB</td>'
      + '<td class="num">' + esc((r.last_modified || '').slice(0, 10)) + '</td>'
      + '<td><span class="tag ' + cls + '">' + esc(r.status) + '</span></td>'
      + '</tr>';
  }).join('');
  return '<table><thead><tr><th>الملف</th><th>الحجم</th><th>آخر تعديل</th><th>الحالة</th></tr></thead><tbody>'
    + body + '</tbody></table>';
}

async function load() {
  const notice = document.getElementById('notice');
  notice.innerHTML = '';
  try {
    const res = await fetch('api/index', { cache: 'no-store' });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || ('HTTP ' + res.status));
    const data = await res.json();
    const items = Array.isArray(data) ? data : [];

    const locked = items.filter((i) => i.status.startsWith('Locked'));
    const purge = items.filter((i) => i.status.startsWith('Requires'));
    const wip = items.filter((i) => !i.status.startsWith('Locked') && !i.status.startsWith('Requires'));
    const totalMB = items.reduce((sum, i) => sum + (i.size_mb || 0), 0);

    document.getElementById('s-total').textContent = fmt(items.length);
    document.getElementById('s-locked').textContent = fmt(locked.length);
    document.getElementById('s-purge').textContent = fmt(purge.length);
    document.getElementById('s-size').textContent = fmt(totalMB);

    purge.sort((a, b) => b.size_mb - a.size_mb);
    document.getElementById('t-purge').innerHTML = table(purge, 'لا توجد ملفات ثقيلة — كل شيء ضمن الحد.');
    document.getElementById('t-locked').innerHTML = table(locked, 'لا توجد ملفات مؤرشفة بعد.');
    document.getElementById('t-wip').innerHTML = table(wip, 'مجلد العمل فارغ.');
    document.getElementById('stamp').textContent = 'آخر قراءة: ' + new Date().toLocaleString('ar-EG');
  } catch (err) {
    notice.innerHTML = '<section class="error"><h2>تعذر قراءة الفهرس</h2>'
      + '<p class="hint">' + esc(err.message) + ' — شغّل <code>run_weekly.py</code> أولاً لتوليد skp_project_index.json.</p></section>';
    ['s-total', 's-locked', 's-purge', 's-size'].forEach((id) => document.getElementById(id).textContent = '—');
    ['t-purge', 't-locked', 't-wip'].forEach((id) => document.getElementById(id).innerHTML = '');
  }
}

document.getElementById('refresh').addEventListener('click', load);
load();
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    project_root = "."
    server_version = "SKPArchiverDashboard/1.0"

    def _send(self, status, body, content_type="text/html; charset=utf-8"):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802 - واجهة http.server
        path = self.path.split("?", 1)[0].rstrip("/") or "/"

        if path == "/":
            self._send(200, PAGE_TEMPLATE)
            return

        if path == "/api/index":
            index_path = os.path.join(self.project_root, "skp_project_index.json")
            if not os.path.exists(index_path):
                self._send_json(
                    404,
                    {"error": "ملف skp_project_index.json غير موجود بعد."},
                )
                return
            try:
                with open(index_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError) as exc:
                self._send_json(500, {"error": f"تعذر تحليل الفهرس: {exc}"})
                return
            self._send_json(200, data)
            return

        self._send_json(404, {"error": "المسار غير موجود."})

    def log_message(self, fmt, *args):  # هادئ: لا نطبع كل طلب
        pass


def main():
    parser = argparse.ArgumentParser(description="لوحة مراقبة أرشيف SketchUp")
    parser.add_argument(
        "--root",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="مجلد SketchUp الذي يحتوي skp_project_index.json",
    )
    parser.add_argument("--host", default="127.0.0.1", help="العنوان (0.0.0.0 للمشاركة)")
    parser.add_argument("--port", type=int, default=8080, help="المنفذ")
    parser.add_argument("--check", action="store_true", help="فحص الفهرس والخروج")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    index_path = os.path.join(root, "skp_project_index.json")

    if args.check:
        if not os.path.exists(index_path):
            print(f"[ERROR] لا يوجد فهرس في {root}")
            return 1
        with open(index_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        print(f"[OK] الفهرس صالح: {len(data)} ملف — {index_path}")
        return 0

    DashboardHandler.project_root = root
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"[INFO] اللوحة تعمل على: http://{args.host}:{args.port}")
    print(f"[INFO] تقرأ من: {index_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] إيقاف اللوحة.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
