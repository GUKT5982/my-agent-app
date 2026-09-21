"""Record a test run as JSON and rebuild the test-report index page.

The hand-written reports in `docs/test-reports/` are snapshots: each says
what one run looked like, and nothing says whether things are getting better
or worse. This runs the suite, keeps the result as machine-readable JSON, and
regenerates `docs/test-reports/index.html` from every run recorded so far, so
the trend is visible at a glance.

The index has the data baked into it - it opens straight from disk with no
server and no fetching.

Usage:
    python scripts/record_test_run.py
    python scripts/record_test_run.py --target tests/unit_tests --label "before prompt change"
    python scripts/record_test_run.py --rebuild-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORTS_DIR = Path(__file__).resolve().parents[1] / "docs" / "test-reports"


def run_pytest(target: str, junit_path: Path) -> int:
    """Run the suite, writing JUnit XML. Returns pytest's exit code."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        target,
        "-q",
        f"--junit-xml={junit_path}",
    ]
    print("$ " + " ".join(cmd))
    completed = subprocess.run(cmd, cwd=REPORTS_DIR.parents[1])
    return completed.returncode


def parse_junit(xml_path: Path, label: str) -> dict[str, Any]:
    """Turn pytest's JUnit XML into the run summary the index page reads."""
    root = ET.parse(xml_path).getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    if suite is None:
        raise ValueError(f"No <testsuite> in {xml_path}")

    def count(name: str) -> int:
        return int(suite.get(name, "0") or 0)

    totals = {
        "tests": count("tests"),
        "failed": count("failures"),
        "errors": count("errors"),
        "skipped": count("skipped"),
    }
    totals["passed"] = (
        totals["tests"] - totals["failed"] - totals["errors"] - totals["skipped"]
    )

    per_file: dict[str, dict[str, Any]] = {}
    skips: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    for case in suite.iter("testcase"):
        classname = case.get("classname", "")
        # "tests.unit_tests.test_form_filling" -> "tests/unit_tests/test_form_filling.py"
        module = (
            classname.split(".")[:-1] if "::" in classname else classname.split(".")
        )
        file_name = "/".join(module) + ".py" if module else "(unknown)"
        entry = per_file.setdefault(
            file_name,
            {
                "name": file_name,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "duration": 0.0,
            },
        )
        entry["duration"] = round(
            entry["duration"] + float(case.get("time", "0") or 0), 2
        )

        test_id = f"{classname}::{case.get('name', '')}"
        skipped = case.find("skipped")
        failure = case.find("failure")
        error = case.find("error")

        if skipped is not None:
            entry["skipped"] += 1
            skips.append({"test": test_id, "message": skipped.get("message", "")})
        elif failure is not None or error is not None:
            node = failure if failure is not None else error
            assert node is not None
            entry["failed"] += 1
            failures.append({"test": test_id, "message": node.get("message", "")})
        else:
            entry["passed"] += 1

    now = datetime.now(timezone.utc)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        "label": label,
        "totals": totals,
        "duration_seconds": round(float(suite.get("time", "0") or 0), 2),
        "suites": sorted(per_file.values(), key=lambda s: str(s["name"])),
        "skips": skips,
        "failures": failures,
    }


def load_runs() -> list[dict[str, Any]]:
    """Every recorded run, oldest first."""
    runs: list[dict[str, Any]] = []
    for path in sorted(REPORTS_DIR.glob("*-run.json")):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Skipping unreadable report {path.name}: {exc}", file=sys.stderr)
    runs.sort(key=lambda r: str(r.get("timestamp", "")))
    return runs


def find_written_reports() -> dict[str, str]:
    """Hand-written HTML reports, keyed by the date in their file name."""
    found: dict[str, str] = {}
    for path in REPORTS_DIR.glob("*.html"):
        if path.name == "index.html":
            continue
        found[path.name[:10]] = path.name
    return found


def build_index(runs: list[dict[str, Any]]) -> str:
    """Render the index page with the run history baked in."""
    payload = json.dumps(
        {"runs": runs, "written_reports": find_written_reports()},
        ensure_ascii=False,
    )
    return _INDEX_TEMPLATE.replace("/*__DATA__*/", payload)


_INDEX_TEMPLATE = """<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Runs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Thai:wght@400;500;600&display=swap">
<style>
  :root {
    color-scheme: light;
    --ground: #f4f6f3; --card: #fcfdfb; --ink: #1b2320; --muted: #56625c;
    --faint: #7f8a84; --rule: #dce2dd; --track: #e5eae5; --accent: #2d5b88;
    --pass: #1d7a4b; --skip: #8f5d00; --fail: #b42318; --note-bg: #e9ede9;
    --sans: "IBM Plex Sans Thai", "Noto Sans Thai", "Leelawadee UI", Tahoma, sans-serif;
    --mono: "IBM Plex Mono", ui-monospace, Consolas, "Courier New", monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --ground: #111513; --card: #171c19; --ink: #e3e8e4; --muted: #9fa9a3;
      --faint: #737e78; --rule: #2a322e; --track: #222925; --accent: #8db3db;
      --pass: #62cb92; --skip: #e2ab4a; --fail: #f2796c; --note-bg: #1c221f;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --ground: #111513; --card: #171c19; --ink: #e3e8e4; --muted: #9fa9a3;
    --faint: #737e78; --rule: #2a322e; --track: #222925; --accent: #8db3db;
    --pass: #62cb92; --skip: #e2ab4a; --fail: #f2796c; --note-bg: #1c221f;
  }

  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--ground); color: var(--ink);
    font-family: var(--sans); font-size: 0.9375rem; line-height: 1.7;
    padding-block: 40px 72px; padding-inline: 16px;
  }
  .page { max-width: 880px; margin-inline: auto; display: flex; flex-direction: column; gap: 40px; }
  h1, h2 { margin: 0; text-wrap: balance; }
  p { margin: 0; }
  code, .mono { font-family: var(--mono); }
  .eyebrow { font-size: 0.75rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
  h1 { font-size: 1.875rem; line-height: 1.35; font-weight: 600; }
  h2 { font-size: 1.125rem; font-weight: 600; line-height: 1.4; }
  .lead { color: var(--muted); max-width: 64ch; }
  .caption { color: var(--faint); font-size: 0.8125rem; line-height: 1.6; }

  .hero { display: flex; flex-direction: column; gap: 4px; }
  .hero .value { font-size: 3rem; line-height: 1.1; font-weight: 600; }
  section { display: flex; flex-direction: column; gap: 14px; }
  .sec-head { display: flex; flex-direction: column; gap: 2px; }

  .runs { display: flex; flex-direction: column; gap: 1px; background: var(--rule); border: 1px solid var(--rule); border-radius: 12px; overflow: hidden; }
  .run {
    background: var(--card); padding: 12px 16px;
    display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 4px 16px; align-items: center;
  }
  .run .when { font-family: var(--mono); font-size: 0.8125rem; }
  .run .label { font-size: 0.75rem; color: var(--faint); }
  .run .bar { height: 10px; border-radius: 5px; background: var(--track); }
  .run .bar > div { height: 10px; border-radius: 0 4px 4px 0; background: var(--c, var(--pass)); min-width: 2px; }
  .run .num { font-family: var(--mono); font-size: 0.8125rem; font-variant-numeric: tabular-nums; color: var(--muted); white-space: nowrap; }
  .run .num b { color: var(--ink); font-weight: 500; }
  .run a { color: var(--accent); font-size: 0.75rem; }

  table { border-collapse: collapse; width: 100%; font-size: 0.8125rem; }
  th, td { padding: 6px 12px; text-align: left; border-bottom: 1px solid var(--rule); }
  th { color: var(--muted); font-weight: 600; font-size: 0.75rem; }
  td.n { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; }
  .wrap { border: 1px solid var(--rule); border-radius: 12px; overflow: auto; background: var(--card); }

  .note { background: var(--note-bg); border-radius: 10px; padding: 12px 16px; display: flex; flex-direction: column; gap: 4px; }
  .note .t { font-family: var(--mono); font-size: 0.75rem; overflow-wrap: anywhere; }
  .note .t.skip { color: var(--skip); }
  .note .t.fail { color: var(--fail); }
  .empty { color: var(--faint); font-size: 0.875rem; }

  @media (max-width: 620px) {
    .run { grid-template-columns: minmax(0, 1fr) auto; }
    .run .bar { grid-column: 1 / -1; }
  }
</style>
</head>
<body>
<div class="page">
  <header>
    <p class="eyebrow">my-agent-app</p>
    <h1>Test Runs</h1>
    <p class="lead">ผลรันเทสต์ทุกครั้งที่บันทึกไว้ด้วย <code>scripts/record_test_run.py</code> — ดูว่าแนวโน้มดีขึ้นหรือแย่ลง ไม่ใช่แค่ผลของวันเดียว</p>
  </header>

  <div class="hero">
    <p class="eyebrow">ผลล่าสุด</p>
    <p class="value" id="heroValue">—</p>
    <p class="caption" id="heroSub"></p>
  </div>

  <section>
    <div class="sec-head">
      <h2>ประวัติการรัน</h2>
      <p class="caption">แถบคือสัดส่วนเทสต์ที่ผ่านจากทั้งหมด · แดงหมายถึงรอบนั้นมีเทสต์ fail</p>
    </div>
    <div class="runs" id="runs"></div>
  </section>

  <section>
    <div class="sec-head">
      <h2>รายไฟล์ (รอบล่าสุด)</h2>
    </div>
    <div class="wrap">
      <table>
        <thead><tr><th>ไฟล์</th><th style="text-align:right">ผ่าน</th><th style="text-align:right">fail</th><th style="text-align:right">skip</th><th style="text-align:right">วินาที</th></tr></thead>
        <tbody id="suites"></tbody>
      </table>
    </div>
  </section>

  <section id="notesSection">
    <div class="sec-head">
      <h2>ที่ยังไม่ผ่าน / ถูก skip (รอบล่าสุด)</h2>
    </div>
    <div id="notes"></div>
  </section>
</div>

<script id="data" type="application/json">/*__DATA__*/</script>
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var runs = DATA.runs || [];
  var written = DATA.written_reports || {};

  function el(t, c, x) { var n = document.createElement(t); if (c) n.className = c; if (x != null) n.textContent = x; return n; }
  function $(id) { return document.getElementById(id); }

  if (!runs.length) {
    $("heroValue").textContent = "ยังไม่มีข้อมูล";
    $("heroSub").textContent = "รัน python scripts/record_test_run.py หนึ่งครั้งเพื่อเริ่มเก็บประวัติ";
    return;
  }

  var latest = runs[runs.length - 1];
  var t = latest.totals;
  var broken = t.failed + t.errors;
  $("heroValue").textContent = broken ? broken + " fail" : t.passed + " ผ่าน";
  $("heroSub").textContent = latest.date + " · ผ่าน " + t.passed + " / fail " + broken +
    " / skip " + t.skipped + " จาก " + t.tests + " เทสต์ · " + latest.duration_seconds + " วินาที";

  var host = $("runs");
  runs.slice().reverse().forEach(function (r) {
    var tt = r.totals;
    var bad = tt.failed + tt.errors;
    var row = el("div", "run");
    row.style.setProperty("--c", bad ? "var(--fail)" : "var(--pass)");

    var when = el("div");
    when.appendChild(el("p", "when", r.date));
    if (r.label) when.appendChild(el("p", "label", r.label));
    var link = written[r.date];
    if (link) {
      var a = document.createElement("a");
      a.href = link;
      a.textContent = "รายงานฉบับเต็ม";
      when.appendChild(a);
    }
    row.appendChild(when);

    var bar = el("div", "bar");
    var fill = el("div");
    fill.style.width = (tt.tests ? Math.max(2, Math.round(100 * tt.passed / tt.tests)) : 2) + "%";
    bar.appendChild(fill);
    row.appendChild(bar);

    var num = el("span", "num");
    num.innerHTML = "<b>" + tt.passed + "</b>/" + tt.tests +
      (bad ? " · fail " + bad : "") + (tt.skipped ? " · skip " + tt.skipped : "");
    row.appendChild(num);
    host.appendChild(row);
  });

  var tb = $("suites");
  (latest.suites || []).forEach(function (s) {
    var tr = document.createElement("tr");
    tr.appendChild(el("td", null, s.name));
    tr.appendChild(el("td", "n", String(s.passed)));
    tr.appendChild(el("td", "n", String(s.failed)));
    tr.appendChild(el("td", "n", String(s.skipped)));
    tr.appendChild(el("td", "n", String(s.duration)));
    tb.appendChild(tr);
  });

  var notes = $("notes");
  var any = false;
  (latest.failures || []).forEach(function (f) {
    any = true;
    var box = el("div", "note");
    box.appendChild(el("p", "t fail", f.test));
    if (f.message) box.appendChild(el("p", "t", f.message));
    notes.appendChild(box);
  });
  if ((latest.skips || []).length) {
    any = true;
    var box = el("div", "note");
    latest.skips.forEach(function (s) {
      box.appendChild(el("p", "t skip", s.test + " — " + s.message));
    });
    notes.appendChild(box);
  }
  if (!any) notes.appendChild(el("p", "empty", "รอบล่าสุดผ่านหมด ไม่มี skip"));
})();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", default="tests/", help="what to run (default: tests/)"
    )
    parser.add_argument("--label", default="", help="a short note about this run")
    parser.add_argument(
        "--rebuild-only",
        action="store_true",
        help="regenerate index.html from the runs already recorded, without running pytest",
    )
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not args.rebuild_only:
        with tempfile.TemporaryDirectory() as tmp:
            junit_path = Path(tmp) / "junit.xml"
            exit_code = run_pytest(args.target, junit_path)
            if not junit_path.is_file():
                print("pytest produced no report; nothing recorded.", file=sys.stderr)
                sys.exit(exit_code or 1)
            run = parse_junit(junit_path, args.label)

        out = REPORTS_DIR / f"{run['date']}-run.json"
        out.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
        totals = run["totals"]
        print(
            f"\nRecorded {out.name}: {totals['passed']} passed, "
            f"{totals['failed'] + totals['errors']} failed, {totals['skipped']} skipped"
        )

    runs = load_runs()
    index = REPORTS_DIR / "index.html"
    index.write_text(build_index(runs), encoding="utf-8")
    print(f"Rebuilt {index} from {len(runs)} recorded run(s)")


if __name__ == "__main__":
    main()
