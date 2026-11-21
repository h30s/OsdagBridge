"""Report QA matrix: generate the design report for several bridge geometries and check each.

For every case this runs tools/generate_sample_report.py (real design, real PDF) and
reports pages, LaTeX errors and layout problems (text in the footer band). A change to
the report generator is safe when every row is clean.

    python tools/report_qa_matrix.py --out qa_out            # default cases
    python tools/report_qa_matrix.py --cases 20:7.5 30:7.5 45:12

Exit status 0 when all cases have 0 LaTeX errors and 0 layout problems, else 1.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

DEFAULT_CASES = ["20:7.5", "30:7.5", "36:9.0", "42:12.0", "50:15.0"]   # span(m):carriageway(m)


def run_case(span: float, carriageway: float, out_dir: str) -> dict:
    stem = f"Report_{span:g}m_{carriageway:g}m"
    cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "generate_sample_report.py"),
           "--span", str(span), "--carriageway", str(carriageway), "--out", out_dir, "--stem", stem]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    for line in reversed(proc.stdout.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    return {"error": (proc.stderr or proc.stdout)[-300:], "span": span, "carriageway": carriageway}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", nargs="*", default=DEFAULT_CASES, help="span:carriageway pairs (m)")
    ap.add_argument("--out", default="qa_out")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    rows, ok = [], True
    for case in args.cases:
        span, cw = (float(x) for x in case.split(":"))
        print(f"running {span:g} m span, {cw:g} m carriageway ...", flush=True)
        r = run_case(span, cw, args.out)
        rows.append(r)
        if "error" in r or r.get("latex_errors") or r.get("layout_problems"):
            ok = False

    print("\n| Span (m) | Carriageway (m) | Pages | LaTeX errors | Layout problems | Time (s) |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        if "error" in r:
            print(f"| {r['span']:g} | {r['carriageway']:g} | FAILED: {r['error'][:60]!r} | | | |")
        else:
            print(f"| {r['span']:g} | {r['carriageway']:g} | {r['pages']} | {r['latex_errors']} | "
                  f"{r['layout_problems']} | {r['seconds']} |")
    print("\nALL CLEAN" if ok else "\nPROBLEMS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
