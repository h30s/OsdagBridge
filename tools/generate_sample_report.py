"""Generate a complete OsdagBridge design report from the command line (no GUI clicks).

Runs the real design pipeline headlessly (Qt "offscreen", the same code path as the
Design button), attaches the analysis plots exactly like the desktop app does, builds
the PDF report and runs the layout checker on it.

    python tools/generate_sample_report.py --span 30 --carriageway 7.5 --out out/ --stem Report

Prints one JSON line with the result (pages, LaTeX errors, layout problems, verdict),
which tools/report_qa_matrix.py collects. Needs pdflatex (and poppler's pdftotext for
the layout check) on PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Sample project inputs: what the project-location dialog would fill in.
SAMPLE_LOCATION = {
    "method": "location_name",
    "data": {"district": "Mumbai", "state": "Maharashtra", "latitude": 19.076, "longitude": 72.8777},
    "weather_data": {"zone": "III", "wind_speed": 44, "max_temp": 43, "min_temp": 10,
                     "latitude": 19.076, "longitude": 72.8777},
}


def run_design(span: float, carriageway: float, skew: float):
    """Run the design pipeline exactly as the Design button does. Returns the backend."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication(sys.argv)

    from osdagbridge.desktop.resources import resources_rc  # noqa: F401  (registers Qt resources)
    from osdagbridge.core.bridge_types.plate_girder.defaults import solve_extend_basic_input_dict
    from osdagbridge.core.bridge_types.plate_girder.plategirderbridge import PlateGirderBridge
    from osdagbridge.desktop.ui.template_page import CustomWindow

    win = CustomWindow("OsdagBridge", PlateGirderBridge)
    d = win.input_dict
    d["geometry.span"] = float(span)
    d["geometry.carriageway_width"] = float(carriageway)
    d["geometry.skew_angle"] = float(skew)
    d["project.location"] = SAMPLE_LOCATION
    win.input_dock._prime_material_inputs()
    solve_extend_basic_input_dict(d)
    win._sync_compute_results_to_input_dict()

    backend = win.backend
    backend.set_input(d)
    backend.design()
    return backend


def build_report(backend, out_dir: str, stem: str) -> dict:
    """Create the PDF; returns {pdf, tex, log, verdict}."""
    from osdagbridge.core.bridge_types.plate_girder.plot_generator import capture_report_figures
    from osdagbridge.core.reports import report_generator as rg

    nodes, members = backend.get_nodes_members()
    figures = capture_report_figures(backend.get_results_dataset(), nodes, members,
                                     edge_dist=backend.get_edge_dist(), eng_scale=1.0)

    # keep the LaTeX working directory so its .log can be inspected afterwards
    keep = os.path.join(out_dir, "_latex_" + stem)
    os.makedirs(keep, exist_ok=True)

    class _KeepDir:
        def __init__(self, *a, **k):
            self.path = tempfile.mkdtemp(prefix="rep_", dir=keep)

        def __enter__(self):
            return self.path

        def __exit__(self, *exc):
            return False

    rg.tempfile.TemporaryDirectory = _KeepDir

    meta = rg.ReportMetadata(
        project_name="Sample Highway Bridge", project_location="", designer="Design Engineer",
        client="Sample Client", company="Sample Consultants", group_name="", subtitle="Rev 0",
        job_number="JOB-001", additional_comments="", logo_path=None,
        report_date=time.strftime("%Y-%m-%d"), reviewer="Reviewer")
    options = rg.ReportOptions(sections=["loads", "analysis", "design_checks", "drawings"],
                               include_figures=True, include_toc=True, include_pdf=True)
    request = rg.ReportRequest(metadata=meta, options=options, output_dir=out_dir, file_stem=stem)

    output = dict(backend.output_dict)
    output["analysis_summary"] = {"load_cases": getattr(backend, "_lc_summary", None) or {},
                                  "reactions": getattr(backend, "_reaction_summary", None) or {}}
    payload = rg.build_report_payload(request, backend.input_dict.copy(), output)
    payload.figure_data = dict(figures)
    result = rg.generate_report(payload, request)

    logs = sorted(f for f in _walk(keep, stem + ".log"))
    return {"pdf": result.pdf_path, "tex": result.tex_path, "log": logs[-1] if logs else None}


def _walk(root: str, name: str):
    for base, _dirs, files in os.walk(root):
        if name in files:
            yield os.path.join(base, name)


def summarize(pdf: str, log: str, elapsed: float) -> dict:
    import subprocess
    import report_layout_check
    errors = None
    if log and os.path.exists(log):
        errors = sum(1 for line in open(log, encoding="utf-8", errors="replace") if line.startswith("!"))
    pages = None
    try:
        info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
        pages = int(next(ln.split()[1] for ln in info.splitlines() if ln.startswith("Pages")))
    except Exception:
        pass
    try:
        layout = len(report_layout_check.check(pdf))
    except Exception:
        layout = None
    return {"pdf": pdf, "pages": pages, "latex_errors": errors, "layout_problems": layout,
            "seconds": round(elapsed, 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--span", type=float, default=30.0, help="span in metres")
    ap.add_argument("--carriageway", type=float, default=7.5, help="carriageway width in metres")
    ap.add_argument("--skew", type=float, default=0.0, help="skew angle in degrees")
    ap.add_argument("--out", default="report_out", help="output directory")
    ap.add_argument("--stem", default="Report", help="output file name without extension")
    args = ap.parse_args(argv)

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    started = time.time()
    backend = run_design(args.span, args.carriageway, args.skew)
    built = build_report(backend, out_dir, args.stem)
    if not built["pdf"]:
        print(json.dumps({"error": "no PDF produced", "tex": built["tex"]}))
        return 1
    summary = summarize(built["pdf"], built["log"], time.time() - started)
    summary.update(span=args.span, carriageway=args.carriageway, skew=args.skew)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":      # required: the design stage uses multiprocessing (spawn)
    sys.exit(main())
