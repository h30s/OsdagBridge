"""Tests for the design verdict, the honest executive summary and the reviewer-found fixes."""

import os
from types import SimpleNamespace

import pytest

from osdagbridge.core.reports import drawings, styles, verdict
from osdagbridge.core.reports.chap2 import ch2_input_parameters  # noqa: F401  (import smoke test)
from osdagbridge.core.reports.chap4 import ch4_analysis
from osdagbridge.core.reports.executive_summary import executive_summary
from osdagbridge.core.reports.report_utils import (
    _render_mm, design_lane_count, load_case_sort_key)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------
# verdict: one source of truth for pass / fail
# --------------------------------------------------------------------------
RECORDS = [
    ("Girder --- Moment", 0.20), ("Girder --- Fatigue", 1.58),
    ("Deck --- Punching Shear", 0.34), ("Crack Width (slab)", 0.94),
    ("Cross Bracing --- Tension", 0.13), ("Cross Bracing --- Slenderness", None),
]


def test_element_verdicts_per_element():
    by = {v.element: v for v in verdict.element_verdicts(RECORDS)}
    assert by["Steel Plate Girders"].status == "Fail"
    assert by["Steel Plate Girders"].governing == "Fatigue"
    assert (by["Steel Plate Girders"].n_checks, by["Steel Plate Girders"].n_failing) == (2, 1)
    assert by["Concrete Deck Slab"].status == "Pass" and by["Concrete Deck Slab"].max_ur == 0.94
    assert by["Cross Bracing"].n_checks == 1                 # a check without a UR is not counted


def test_element_without_data_is_not_evaluated_never_pass():
    by = {v.element: v for v in verdict.element_verdicts(RECORDS)}
    assert by["End Diaphragms"].status == "Not evaluated"
    assert by["End Diaphragms"].max_ur is None


def test_overall_status():
    assert verdict.overall_status(verdict.element_verdicts(RECORDS)) == "Fail"
    ok = [("Girder --- Moment", 0.5), ("Deck --- Punching Shear", 0.4)]
    assert verdict.overall_status(verdict.element_verdicts(ok)) == "Pass"
    assert verdict.overall_status(verdict.element_verdicts([])) == "Not evaluated"


def test_failing_checks_sorted_worst_first():
    recs = [("Girder --- A", 1.1), ("Girder --- B", 1.9), ("Girder --- C", 0.5)]
    assert [lbl for lbl, _ in verdict.failing_checks(recs)] == ["Girder --- B", "Girder --- A"]


@pytest.mark.parametrize("ur,band", [(None, "none"), (0.2, "ok"), (0.90, "ok"), (0.95, "warn"),
                                     (1.0, "warn"), (1.01, "fail")])
def test_ur_band_boundaries(ur, band):
    assert verdict.ur_band(ur) == band


def test_ur_cell_uses_band_colours_and_skips_placeholders():
    assert styles.ur_cell(None, "0.5") == "0.5"
    assert styles.ur_cell(0.5, "---") == "---"
    assert "urOk" in styles.ur_cell(0.5, "0.50")
    assert "urWarn" in styles.ur_cell(0.95, "0.95")
    assert "urFail" in styles.ur_cell(1.5, "1.50")


def test_shaded_last_column_keeps_its_right_border():
    """colortbl paints a last-column background over a plain '|' border; the summary
    table must end its column spec with RIGHT_RULE (a rule drawn as a separator)."""
    import os
    src = open(os.path.join(os.path.dirname(styles.__file__), 'chap5.py'), encoding='utf-8').read()
    assert 'p{1.6cm}""" + RIGHT_RULE' in src
    assert styles.RIGHT_RULE.startswith('!{') and 'vrule' in styles.RIGHT_RULE


# --------------------------------------------------------------------------
# executive summary no longer hard-codes "pass"
# --------------------------------------------------------------------------
def _summary(records):
    return executive_summary({}, {}, {}, ur_records=records)


def test_failing_design_never_reports_pass_for_that_element():
    tex = _summary(RECORDS)
    assert "DESIGN DOES NOT SATISFY ALL CHECKS" in tex
    assert "Girder design pass" not in tex and "Deck design pass" not in tex   # the old hard-coded lines
    assert r"\failtext{Fail}" in tex
    assert "Not evaluated" in tex                                               # end diaphragms: no data


def test_passing_design_summary():
    tex = _summary([("Girder --- Moment", 0.5), ("Deck --- Punching Shear", 0.4)])
    assert "DESIGN SATISFIES ALL EVALUATED CHECKS" in tex
    assert r"\failtext" not in tex


def test_summary_without_any_data_does_not_claim_pass():
    tex = _summary([])
    assert "DESIGN NOT EVALUATED" in tex
    assert "SATISFIES" not in tex


# --------------------------------------------------------------------------
# unit bug: design() stores girder dimensions in metres
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value,expected", [(1.67, "1670 mm"), (0.022, "22 mm"), (0.51, "510 mm"),
                                            (1670.0, "1670 mm"), ("1.67", "1670 mm")])
def test_render_mm_converts_metres(value, expected):
    assert _render_mm({"k": value}, "k") == expected


def test_render_mm_blank_and_text():
    assert _render_mm({}, "k") == ""
    assert "All" in _render_mm({"k": "All"}, "k")


# --------------------------------------------------------------------------
# deterministic load-case order (the analysis returns a set)
# --------------------------------------------------------------------------
def test_load_case_order_is_stable_and_sensible():
    names = ["SLS_QP_1", "BASIC_10", "BASIC_2", "Envelope SLS", "1.0 DL", "Envelope ULS", "SEISMIC_1", "XYZ"]
    ordered = sorted(names, key=load_case_sort_key)
    assert ordered == ["Envelope ULS", "Envelope SLS", "1.0 DL", "BASIC_2", "BASIC_10", "SEISMIC_1",
                       "SLS_QP_1", "XYZ"]
    assert sorted(reversed(names), key=load_case_sort_key) == ordered      # independent of input order


# --------------------------------------------------------------------------
# lane count, Table 4.2
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cw,lanes", [(3.5, 1), (7.5, 2), (11.0, 3)])
def test_design_lane_count(cw, lanes):
    assert design_lane_count({"geometry.carriageway_width": cw}) == lanes


def test_design_lane_count_missing():
    assert design_lane_count({}) is None


def test_table_4_2_is_filled_from_the_reaction_summary():
    asum = {"load_cases": {}, "reactions": {"Envelope ULS": {"left_kN": -1308.88, "right_kN": 1042.068},
                                            "1.0 DL": {"left_kN": -703.407, "right_kN": 703.407}}}
    bridge = SimpleNamespace(input_dict={}, output_dict={})
    tex = ch4_analysis(asum, {}, bridge, 30.0)
    assert "-1308.880" in tex and "1042.068" in tex and "-703.407" in tex
    assert tex.index("Envelope ULS") < tex.index("1.0 DL")                   # key cases first


# --------------------------------------------------------------------------
# schematic drawings (fallback for CAD views)
# --------------------------------------------------------------------------
SAMPLE = {
    "typical_section.no_of_girders": 4, "typical_section.girder_spacing": 2.1,
    "typical_section.deck_overhang": 1.05, "typical_section.overall_bridge_width": 8.4,
    "typical_section.deck_thickness": 250.0, "typical_section.crash_barrier.width": 0.45,
    "typical_section.crash_barrier.height": 1.1, "typical_section.wearing_course.thickness": 50.0,
    "geometry.span": 30.0, "geometry.carriageway_width": 7.5, "geometry.skew_angle": 0.0,
    "member_properties.girder_details.section_input.depth.G1.M1": 1.67,
    "member_properties.girder_details.section_input.top_flange_width.G1.M1": 0.51,
    "member_properties.girder_details.section_input.top_flange_thickness.G1.M1": 0.022,
    "member_properties.girder_details.section_input.bottom_flange_width.G1.M1": 0.51,
    "member_properties.girder_details.section_input.bottom_flange_thickness.G1.M1": 0.022,
    "member_properties.girder_details.section_input.web_thickness.G1.M1": 0.01,
    "member_properties.cross_bracing_details.spacing.G1G2.B1M1": 15.0,
}


def _is_png(path):
    with open(path, "rb") as fh:
        return fh.read(8) == PNG_MAGIC


def test_schematics_are_rendered(tmp_path):
    out = drawings.render_schematics(SAMPLE, str(tmp_path))
    assert set(out) == {"cross_section", "girder_top", "longitudinal_elevation"}
    assert all(_is_png(p) for p in out.values())


def test_schematics_support_skew_and_mm_girder_dimensions(tmp_path):
    d = dict(SAMPLE, **{"geometry.skew_angle": 20.0,
                        "member_properties.girder_details.section_input.depth.G1.M1": 1670.0})
    out = drawings.render_schematics(d, str(tmp_path))
    assert "girder_top" in out and _is_png(out["girder_top"])


def test_schematics_never_raise_on_bad_input(tmp_path):
    assert drawings.render_schematics({}, str(tmp_path)) == {}
    assert drawings.render_schematics({"geometry.span": "abc"}, str(tmp_path)) == {}
    assert not any(f.endswith(".png") for f in os.listdir(tmp_path))
