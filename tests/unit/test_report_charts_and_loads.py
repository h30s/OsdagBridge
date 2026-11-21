"""Tests for report charts (UR + quantities), live-load tables and the IRC 6 braking fix."""

import os

import pytest

from osdagbridge.core.reports import charts
from osdagbridge.core.reports.chap3 import live_load_tables
from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _is_png(path):
    with open(path, "rb") as fh:
        return fh.read(8) == PNG_MAGIC


# --------------------------------------------------------------------------
# UR charts (requirement 4)
# --------------------------------------------------------------------------
ROWS = [
    ("Girder --- Moment", 0.20), ("Girder --- Shear", 0.53), ("Girder --- Fatigue", 1.58),
    ("Deck --- Punching Shear", 0.34), ("Crack Width (slab)", 0.71),
    ("Cross Bracing --- Tension", 0.13), ("End Diaphragm --- Moment", 0.46),
]


def test_parse_number_handles_latex_and_placeholders():
    assert charts.parse_number(r"\failtext{1.58}") == 1.58
    assert charts.parse_number("0.94") == 0.94
    assert charts.parse_number("---") is None
    assert charts.parse_number("N/A") is None
    assert charts.parse_number(None) is None


@pytest.mark.parametrize("label,expected", [
    ("Girder --- Moment", "Steel Plate Girders"),
    ("Deck --- Flexure (sagging)", "Concrete Deck Slab"),
    ("Transverse Shear (slab)", "Concrete Deck Slab"),
    ("Crack Width (slab)", "Concrete Deck Slab"),
    ("Cross Bracing --- Slenderness", "Cross Bracing"),
    ("End Diaphragm --- Shear", "End Diaphragms"),
    ("Something else", None),
])
def test_element_mapping(label, expected):
    assert charts.element_of(label) == expected


def test_ur_charts_are_written_as_png(tmp_path):
    p1 = charts.ur_governing_chart(ROWS, str(tmp_path / "gov.png"))
    p2 = charts.ur_checks_chart(ROWS, str(tmp_path / "checks.png"))
    assert p1 and p2 and _is_png(p1) and _is_png(p2)


def test_ur_charts_return_none_without_data(tmp_path):
    assert charts.ur_governing_chart([("Girder --- Moment", None)], str(tmp_path / "a.png")) is None
    assert charts.ur_checks_chart([], str(tmp_path / "b.png")) is None
    assert not os.listdir(tmp_path)


def test_ur_governing_chart_survives_missing_elements(tmp_path):
    only_girders = [("Girder --- Moment", 0.5)]
    assert _is_png(charts.ur_governing_chart(only_girders, str(tmp_path / "g.png")))


# --------------------------------------------------------------------------
# Quantity charts (requirement 5)
# --------------------------------------------------------------------------
QTY = {"steel_girders_wt_total": "32.89", "bracing_top_wt_total": "0.20",
       "bracing_bot_wt_total": "0.20", "bracing_diag_wt_total": "0.07",
       "concrete_deck_vol_total": "63.00", "rebar_deck_wt_total": "7.56"}


def test_quantity_charts_written(tmp_path):
    assert _is_png(charts.steel_tonnage_chart(QTY, str(tmp_path / "steel.png")))
    assert _is_png(charts.concrete_vs_rebar_chart(QTY, str(tmp_path / "cr.png")))


def test_quantity_charts_handle_not_available(tmp_path):
    na = {k: "N.A." for k in QTY}
    assert charts.steel_tonnage_chart(na, str(tmp_path / "s.png")) is None
    assert charts.concrete_vs_rebar_chart(na, str(tmp_path / "c.png")) is None


# --------------------------------------------------------------------------
# Live-load tables (requirement 3)
# --------------------------------------------------------------------------
def _tables(**kw):
    inputs = {"geometry.footpath": kw.pop("footpath", None), "loading.live_load.eccentricity": 1.2}
    return live_load_tables(inputs, kw.pop("vehicles", ["Class A", "Class 70R (Wheeled)"]),
                            1.207, 1.100, kw.pop("lanes", 2), kw.pop("braking_t", 11.08))


def test_vehicle_and_footpath_tables_are_separate():
    tex = _tables()
    assert tex.count(r"\begin{longtable}") == 3
    assert "Live Loads -- Vehicular (IRC 6)" in tex
    assert "Live Loads -- Associated Vehicular Parameters" in tex
    assert "Live Loads -- Footpath" in tex
    assert tex.index("Vehicular (IRC 6)") < tex.index("Footpath")


def test_only_selected_vehicles_are_listed():
    tex = _tables(vehicles=["Class A"])
    assert "Class A" in tex
    assert "Class 70R (Wheeled)" not in tex and "Class AA" not in tex   # only selected classes are rows


def test_parameters_table_has_unit_column_and_values():
    tex = _tables()
    assert r"\textbf{Unit}" in tex
    assert "kN" in tex and "108.69" in tex          # 11.08 t * 9.81
    assert "Centrifugal force" in tex and "Not considered" in tex
    assert "1.207" in tex and "1.100" in tex         # impact factors per class


def test_footpath_table_when_no_footpath():
    assert "Not applicable" in _tables(footpath=None)


# --------------------------------------------------------------------------
# IRC 6 braking force bug (UnboundLocalError for every lane count; unit is N)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("lanes", [1, 2, 3, 4])
def test_braking_force_does_not_raise(lanes):
    assert IRC6_2017.cl_211_2_braking_force(lanes) > 0


def test_braking_force_is_in_newtons():
    """20 % of the Class A train (55.4 t-force) = 11.08 t = ~108.7 kN."""
    assert IRC6_2017.cl_211_2_braking_force(1) == pytest.approx(108_694.8, rel=1e-3)
