"""Unit tests for the report style system (reports/styles.py) and its helpers."""

import glob
import os
import re

import pytest

from osdagbridge.core.reports import styles

REPORTS_DIR = os.path.join(os.path.dirname(styles.__file__))
CHAPTER_FILES = sorted(glob.glob(os.path.join(REPORTS_DIR, "chap*.py"))
                       + [os.path.join(REPORTS_DIR, "executive_summary.py")])


# --------------------------------------------------------------------------
# longtable_head: repeated headers (requirement 1)
# --------------------------------------------------------------------------
def test_longtable_head_repeats_header_on_every_page():
    tex = styles.longtable_head(r"|C{2cm}|L{4cm}|", r"\textbf{Demo}", r"\textbf{A} & \textbf{B} \\[6pt]")
    assert tex.count(r"\textbf{A} & \textbf{B}") == 2, "header must appear in first head and in \\endhead"
    assert r"\endfirsthead" in tex and r"\endhead" in tex
    assert tex.index(r"\endfirsthead") < tex.index(r"\endhead")
    assert r"\caption*" in tex and "continued" in tex      # unnumbered continuation caption


def test_longtable_head_normalises_trailing_row_end():
    a = styles.longtable_head("|C{2cm}|", "C", r"\textbf{A} \\")
    b = styles.longtable_head("|C{2cm}|", "C", r"\textbf{A}")
    assert a == b


def test_longtable_head_caption_followed_by_row_end():
    """A bare \\caption before \\hline is what caused 'Misplaced \\noalign' errors."""
    tex = styles.longtable_head("|C{2cm}|", r"\textbf{Cap}", "A")
    assert r"\caption{\textbf{Cap}}\\" in tex


# --------------------------------------------------------------------------
# fit_colspec: tables never exceed the text width
# --------------------------------------------------------------------------
def _total_width_cm(spec, density="normal"):
    widths = [float(w) for w in re.findall(r"\{([0-9.]+)cm\}", spec)]
    n = len(widths)
    pad = 2 * styles.TABLE_DENSITY[density] * 2.54 / 72.27
    return sum(widths) + n * pad


def test_fit_colspec_shrinks_wide_tables():
    wide = r"|C{2.5cm}|C{3.5cm}|C{3.5cm}|>{\centering\arraybackslash}p{4.2cm}|C{1.8cm}|"
    fitted = styles.fit_colspec(wide)
    assert fitted != wide
    assert _total_width_cm(fitted) <= styles.TEXT_WIDTH_CM
    assert r">{\centering\arraybackslash}" in fitted      # column modifiers survive


def test_fit_colspec_leaves_narrow_tables_alone():
    narrow = r"|C{2cm}|L{4cm}|"
    assert styles.fit_colspec(narrow) == narrow


@pytest.mark.parametrize("density", sorted(styles.TABLE_DENSITY))
def test_fit_colspec_respects_density(density):
    spec = r"|C{2.0cm}|L{1.8cm}|C{2.2cm}|C{3.0cm}|C{1.8cm}|C{1.8cm}|C{1.2cm}|C{1.8cm}|"
    assert _total_width_cm(styles.fit_colspec(spec, density), density) <= styles.TEXT_WIDTH_CM


# --------------------------------------------------------------------------
# status colouring
# --------------------------------------------------------------------------
def test_status_helpers_use_palette_commands():
    assert styles.pass_text() == r"\passtext{PASS}"
    assert styles.fail_text() == r"\failtext{FAIL}"
    assert styles.status_text(True) == styles.pass_text()
    assert styles.status_text(False) == styles.fail_text()
    assert styles.status_text(None) == "---"


# --------------------------------------------------------------------------
# preamble
# --------------------------------------------------------------------------
def test_preamble_defines_palette_and_footer_geometry():
    tex = styles.preamble("Proj", "J-1", "2026-01-01", "Rev 0")
    for name, hexv in styles.COLORS.items():
        assert r"\definecolor{%s}{HTML}{%s}" % (name, hexv) in tex
    assert "footskip=" in tex and r"\begin{document}" in tex
    assert "Proj" in tex and "J-1" in tex


def test_preamble_does_not_force_page_break_before_longtable():
    """\\needspace before longtable strands the table head at a page bottom."""
    tex = styles.preamble("P", "J", "D", "R")
    assert r"\BeforeBeginEnvironment{longtable}" not in tex


def test_preamble_footer_note_is_inside_footer_not_pulled_into_body():
    tex = styles.preamble("P", "J", "D", "R")
    assert r"\vspace{-20pt}" not in tex     # the old negative skip dragged the note into the body


# --------------------------------------------------------------------------
# single source of truth: chapters must not hard-code formatting
# --------------------------------------------------------------------------
FORBIDDEN = [
    (r"\textcolor{red}", "use styles.fail_text()"),
    (r"\textcolor{blue}", "use the statusInfo palette colour"),
    (r"\definecolor", "define colours in styles.COLORS"),
    (r"\setlength{\tabcolsep}", "use styles.tabcolsep_cmd()"),
    (r"\renewcommand{\arraystretch}", "use styles.dense_table_setup()"),
    (r"\begin{longtable}", "use styles.longtable_head() (repeating header + width fit)"),
]


@pytest.mark.parametrize("path", CHAPTER_FILES, ids=os.path.basename)
def test_chapters_do_not_hardcode_formatting(path):
    src = open(path, encoding="utf-8").read()
    for needle, hint in FORBIDDEN:
        if path.endswith("chap4.py") and needle == r"\begin{longtable}":
            continue      # chap4 has one two-row-header table with its own repeating header
        assert needle not in src, f"{os.path.basename(path)} contains {needle!r}: {hint}"
