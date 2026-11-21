# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

import os

from osdagbridge.core.reports import charts as _charts, verdict as _verdict
from osdagbridge.core.reports.report_utils import _fig_or_placeholder, _render_value, _tex, get_girder_entries
from osdagbridge.core.reports.styles import (
    figure_block, fail_text, fit_colspec, pass_text, ur_cell, verdict_banner)
from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_SD_SECTION_DESIGNATION,
    KEY_SPAN,
    KEY_STRUCTURE_TYPE,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_GIRDER_SPACING,
    KEY_TS_NO_OF_GIRDERS
)


def _max_float(values):
    """Return the largest value coercible to float, or None if there are none."""
    out = None
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if out is None or f > out:
            out = f
    return out


def _max_member_efficiency(pair_designs):
    """Maximum Osdag 'efficiency' (utilization ratio) over a cross-bracing or
    end-diaphragm result dump (nested pair -> member -> force_type -> raw).
    Reads already-computed results only; nothing is recalculated here."""
    from osdagbridge.core.bridge_types.plate_girder.results_data import _extract_osdag_summary
    if not isinstance(pair_designs, dict):
        return None
    best = None
    for members in pair_designs.values():
        if not isinstance(members, dict):
            continue
        for force_types in members.values():
            if not isinstance(force_types, dict):
                continue
            for raw in force_types.values():
                try:
                    val = _extract_osdag_summary(raw or {}).get("efficiency")
                    if val is None:
                        continue
                    f = float(val)
                except (TypeError, ValueError, AttributeError):
                    continue
                if best is None or f > best:
                    best = f
    return best


_ELEMENT_PREFIX = {"Steel Plate Girders": "Girder", "Concrete Deck Slab": "Deck",
                   "Cross Bracing": "Cross Bracing", "End Diaphragms": "End Diaphragm"}


def _verdict_banner(overall, verdicts, ur_records) -> str:
    """Boxed overall verdict with the number of checks and the worst failing check."""
    n_checks = sum(v.n_checks for v in verdicts)
    failing = _verdict.failing_checks(ur_records)
    headline = {"Pass": "DESIGN SATISFIES ALL EVALUATED CHECKS",
                "Fail": "DESIGN DOES NOT SATISFY ALL CHECKS"}.get(overall, "DESIGN NOT EVALUATED")
    if n_checks == 0:
        detail = _tex("No utilization ratios were available for this report.")
    elif failing:
        worst = _tex(_verdict.clean_label(failing[0][0]))
        detail = (f"{n_checks} checks evaluated; {len(failing)} exceed UR = 1.0. "
                  f"Worst: {worst} (UR = {failing[0][1]:.2f}).")
    else:
        detail = f"{n_checks} checks evaluated; all within UR $\\leq$ 1.0."
    return verdict_banner(overall, headline, detail)


def _outcomes_block(verdicts, images_dir) -> str:
    """Per-element outcome table (derived from the results, never hard-coded) + chart."""
    spec = fit_colspec(r"|L{4.2cm}|C{2.6cm}|C{1.9cm}|L{4.6cm}|C{2.0cm}|")
    rows = []
    for v in verdicts:
        if v.status == "Pass":
            status = pass_text("Pass")
        elif v.status == "Fail":
            status = fail_text("Fail")
        else:
            status = r"\textcolor{noteGrey}{Not evaluated}"
        ur = ur_cell(v.max_ur, f"{v.max_ur:.2f}") if v.max_ur is not None else "---"
        gov = _tex(v.governing) if v.governing else "---"
        rows.append(f"{_tex(v.element)} & {status} & {ur} & {gov} & "
                    f"{v.n_failing} / {v.n_checks} \\\\[3pt]\n\\hline")
    tex = (r"\noindent" + "\n" + r"\begin{tabular}{" + spec + "}\n\\hline\n"
           + r"\rowcolor{tableHead}\textbf{Element} & \textbf{Status} & \textbf{Max UR} & "
             r"\textbf{Governing check} & \textbf{Failing} \\[3pt]" + "\n\\hline\n"
           + "\n".join(rows) + "\n\\end{tabular}\n"
           + r"\par\vspace{0.3em}\noindent\textit{Status is derived from the utilization ratios of Section 5.5 "
             r"(UR = Demand / Capacity; $\leq$ 1.0 passes).}" + "\n")
    if images_dir:
        chart_rows = [(_ELEMENT_PREFIX[v.element] + " --- governing", v.max_ur) for v in verdicts]
        path = _charts.ur_governing_chart(chart_rows, os.path.join(images_dir, "ur_summary_exec.png"))
        if path:
            tex += "\n" + figure_block("images/ur_summary_exec.png",
                                       "Governing utilization ratio of each primary element.", r"0.78\textwidth",
                                       numbered=False)
    return tex


def executive_summary(input_dict, output_dict, fig_paths, ur_records=None, images_dir=None) -> str:
    plan_fig = _fig_or_placeholder(fig_paths.get('girder_top'), 'Figure 1 -- Overall Bridge Plan')
    cs_fig = _fig_or_placeholder(fig_paths.get('cross_section'),
                                  'Figure 2 -- Typical Cross-Section (with girder, deck, barriers, footpath)')
    geom_fig = _fig_or_placeholder(fig_paths.get('final_geometry'),
                                    'Figure 3 -- 3D View of Bridge Superstructure')

    # All girders share the same section, governing check, and UR.
    # The section designation is produced by the designer pipeline, so it lives
    # in output_dict (not input_dict).
    sec = _render_value(output_dict, KEY_SD_SECTION_DESIGNATION)

    # ── Pull the stored result dicts once, then work off these locals ─────────
    # (no value is recomputed here — the pipeline already filled these in).
    design_results = output_dict.get("design_results", {}) or {}
    per_girder     = design_results.get("per_girder", {}) or {}
    deck_results   = output_dict.get("deck_design_results", {}) or {}
    cb_results     = output_dict.get("crossbracing_design_results", {}) or {}
    ed_results     = output_dict.get("end_diaphragm_design_results", {}) or {}

    # Overall Design Status — girder checks only: Pass if every check passes,
    # otherwise Fail with the names of the failing checks. Each check carries a
    # pre-computed {name, dcr, status}.
    failing = []                        # failing check names (order-preserving, deduped)
    gov_name, gov_dcr = "", None
    girder_max_ur = None
    for g, gd in per_girder.items():
        if str(g).startswith("EB"):     # skip edge-beam pseudo girders
            continue
        for chk in (gd.get("checks") or []):
            try:
                _val = chk.get("dcr")
                if _val is None:
                    dcr = None
                else:
                    dcr = float(_val)
            except (TypeError, ValueError):
                dcr = None
            name = str(chk.get("name", "")).strip()
            is_fail = ("FAIL" in str(chk.get("status", "")).upper()) or (dcr is not None and dcr > 1.0)
            if is_fail and name and name not in failing:
                failing.append(name)
            if dcr is not None:
                if gov_dcr is None or dcr > gov_dcr:
                    gov_dcr, gov_name = dcr, name
                if girder_max_ur is None or dcr > girder_max_ur:
                    girder_max_ur = dcr

    if not per_girder:
        overall_design_status = ""
    elif failing:
        overall_design_status = "Fail (" + ", ".join(failing) + ")"
    else:
        overall_design_status = "Pass"

    # Overall Utilization Ratio — the maximum UR across all bridge components,
    # tagged with the governing component (e.g. "1.05 (Deck slab)").
    component_urs = []                  # (ur_value, component_label)
    if girder_max_ur is not None:
        component_urs.append((girder_max_ur, "Girder"))
    deck_max = _max_float([v for k, v in deck_results.items() if str(k).startswith("ur_")])
    if deck_max is not None:
        component_urs.append((deck_max, "Deck slab"))
    for results, label in ((cb_results, "Cross bracing"), (ed_results, "End diaphragm")):
        m = _max_member_efficiency(results)
        if m is not None:
            component_urs.append((m, label))
    if component_urs:
        max_ur, max_label = max(component_urs, key=lambda t: t[0])
        overall_utilization_ratio = f"{max_ur:.2f} ({max_label})"
    else:
        overall_utilization_ratio = ""

    # ── Verdict: ONE source of truth shared with Table 5.22 and the UR charts ──
    # Chapter 5 supplies the UR records; if it was not generated, fall back to the
    # maxima computed above. An element without data is "Not evaluated", never "Pass".
    if ur_records is None:
        ur_records = [("Girder --- governing", girder_max_ur), ("Deck --- governing", deck_max),
                      ("Cross Bracing --- governing", _max_member_efficiency(cb_results)),
                      ("End Diaphragm --- governing", _max_member_efficiency(ed_results))]
    verdicts = _verdict.element_verdicts(ur_records)
    overall = _verdict.overall_status(verdicts)
    top = _verdict.governing_overall(verdicts)
    if top is not None:
        overall_utilization_ratio = f"{top.max_ur:.2f} ({top.element})"
    if overall == "Fail" and not failing:        # a non-girder element fails
        overall_design_status = "Fail (" + ", ".join(
            _verdict.clean_label(lbl) for lbl, _ in _verdict.failing_checks(ur_records)[:4]) + ")"
    elif overall == "Pass" and not overall_design_status:
        overall_design_status = "Pass"
    banner_tex = _verdict_banner(overall, verdicts, ur_records)
    outcomes_tex = _outcomes_block(verdicts, images_dir)

    gov = _tex(gov_name) if gov_name not in (None, '', 'None') else ''
    ur = _tex(overall_utilization_ratio) if overall_utilization_ratio else ''

    # --- Dynamic Table 1: fetch backend-populated labels via exact suffix pattern ---
    # defaults.py populates: KEY_MP_GD_SELECT_GIRDER + '.G{i}' = 'G{i}'
    #                        KEY_MP_GD_MEMBER_ID     + '.G{i}.M1' = 'G{i}M1'
    labels = get_girder_entries(input_dict)
    if not labels:
        labels = [("", "")]
    n_cols = len(labels)

    # Column widths: row-label column fixed at 2.8cm; girder columns share remainder
    label_col_cm = 2.8
    # Available width ≈ 15.0cm for A4 with 1in margins; each girder col gets equal share
    girder_col_cm = round(max(1.5, (15.0 - label_col_cm) / n_cols), 1)
    col_spec = '|C{' + str(label_col_cm) + 'cm}|' + '|'.join(['C{' + str(girder_col_cm) + 'cm}'] * n_cols) + '|'

    # Header row
    hdr_cells = ' &\n  '.join([r'\textbf{' + _tex(lbl) + '}' for lbl, _ in labels])
    header_row = r'  \textbf{} &' + '\n  ' + hdr_cells + r' \\' + '\n'

    # Member ID row
    mid_cells = ' & '.join([_tex(mid) for _, mid in labels])
    member_id_row = 'Member ID & ' + mid_cells + r' \\' + '\n'

    # Section / Governing Check / UR rows
    sec_cells = ' & '.join([sec] * n_cols)
    sections = f"Section Designation & {sec_cells} \\\\"
    gov_cells = ' & '.join([gov] * n_cols)
    gov_checks = f"Governing Check & {gov_cells} \\\\"
    ur_cells = ' & '.join([ur] * n_cols)
    urs = f"Utilization Ratio & {ur_cells} \\\\"

    table1 = (r'\noindent\textbf{Table 1 -- Final Bridge Geometry (after optimization)}' + '\n\n'
              r'\vspace{0.4em}' + '\n'
              r'\noindent' + '\n'
              r'\begin{tabular}{' + col_spec + '}\n'
              r'\hline' + '\n'
              + header_row +
              r'\hline' + '\n'
              + member_id_row +
              r'\hline' + '\n'
              + sections + '\n'
              r'\hline' + '\n'
              + gov_checks + '\n'
              r'\hline' + '\n'
              + urs + '\n'
              r'\hline' + '\n'
              r'\end{tabular}')

    return r"""
\newpage
{\centering\Large\bfseries Executive Summary\par}
\addcontentsline{toc}{chapter}{Executive Summary}
\vspace{0.8em}

This section provides a concise summary of the bridge design, key inputs, governing loads, and final design outcomes.

""" + banner_tex + r"""
\section*{Project Overview}
\addcontentsline{toc}{section}{Project Overview}
\label{sec:project-overview}


\begin{tabular}{|L{5.5cm}|L{8.5cm}|}
\hline
\textbf{Bridge Type} & """ + (_render_value(input_dict, KEY_STRUCTURE_TYPE)) + r""" \\
\hline
\textbf{Design Standard} & IRC 5, IRC 6, IRC 22, IRC 24, IS 800 \\
\hline
\textbf{Span} & """ + (_render_value(input_dict, KEY_SPAN, ' m')) + r""" \\
\hline
\textbf{Carriageway Width} & """ + (_render_value(input_dict, KEY_CARRIAGEWAY_WIDTH, ' m')) + r""" \\
\hline
\textbf{No. of Girders} & """ + (_render_value(input_dict, KEY_TS_NO_OF_GIRDERS)) + r""" \\
\hline
\textbf{Girder Spacing} & """ + (_render_value(input_dict, KEY_TS_GIRDER_SPACING, ' m')) + r""" \\
\hline
\textbf{Deck Thickness} & """ + (_render_value(input_dict, KEY_TS_DECK_THICKNESS, ' mm')) + r""" \\
\hline
\textbf{Overall Design Status} & """ + (_tex(overall_design_status)) + r""" \\
\hline
\textbf{Governing Check} & """ + gov + r""" \\
\hline
\textbf{Overall Utilization Ratio (max)} & """ + ur + r""" \\
\hline
\end{tabular}


""" + plan_fig + r"""

\newpage

""" + cs_fig + '\n\n' + geom_fig + '\n\n' + table1 + r"""

\vspace{0.4em}
\noindent\textit{Note: Utilization ratio (UR) = demand / capacity. A value $< 1.0$ indicates a passing check.}

\vspace{1em}

\section*{Key Design Outcomes Summary}
\addcontentsline{toc}{section}{Key Design Outcomes Summary}
\label{sec:key-outcomes}

""" + outcomes_tex + r"""

\section*{Design Assumptions and Limitations}
\addcontentsline{toc}{section}{Design Assumptions and Limitations}
\label{sec:assumptions}

\begin{itemize}
\item Additional inputs not provided by the user were assumed by software per IRC/IS code defaults or practical consideration.
\item Grillage analysis was performed using OSPGrillage assuming simply supported I-girders.
\item Substructure and foundation design are not included in this report.
\item Splice connections and bearings are not designed in this version.
\end{itemize}

% Restore numbered chapter format
\titleformat{\chapter}[block]{\normalfont\Large\bfseries\centering}{\thechapter}{1em}{}
\titlespacing*{\chapter}{0pt}{-30pt}{10pt}
"""
