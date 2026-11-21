# =============================================================================
# OsdagBridge report - programmatic engineering schematics
# =============================================================================
# Fallback drawings for the report, generated to scale from the design inputs:
#   * typical cross-section   (figure key 'cross_section')
#   * plan view               (figure key 'girder_top')
#   * longitudinal elevation  (figure key 'longitudinal_elevation')
#
# The desktop app attaches CAD screenshots when it can. When a view is missing
# (e.g. a report generated from the command line / headless), these schematics
# fill the slot instead of an empty "PLACEHOLDER" box. They are simplified line
# drawings, not CAD exports, and say so in the footer of each image.
#
# Colours and fonts come from styles.CHARTS (single source of truth).
# =============================================================================

from __future__ import annotations

import logging
import math
import os
from typing import Dict, Optional

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Rectangle

from osdagbridge.core.reports.styles import CHARTS

CONCRETE = "#D9D9D9"
STEEL = "#5B6B7A"
BARRIER = "#B8B8B8"
LINE = "#303030"
NOTE = "Schematic generated from the design inputs (to scale, simplified)."


def _f(value, default=None) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(d: dict, *keys, default=None):
    for k in keys:
        v = _f(d.get(k))
        if v is not None:
            return v
    return default


def _girder_dims(d: dict) -> Dict[str, float]:
    """Girder dimensions in metres. design() stores them in m; values >= 10 are mm."""
    def dim(name, default):
        v = _f(d.get(f"member_properties.girder_details.section_input.{name}.G1.M1"))
        if v is None:
            return default
        return v / 1000.0 if v >= 10.0 else v
    return {"D": dim("depth", 1.5), "bft": dim("top_flange_width", 0.4), "tft": dim("top_flange_thickness", 0.02),
            "bfb": dim("bottom_flange_width", 0.4), "tfb": dim("bottom_flange_thickness", 0.02),
            "tw": dim("web_thickness", 0.012)}


def _geometry(d: dict) -> Dict[str, float]:
    n = int(_f(d.get("typical_section.no_of_girders"), 0) or 0)
    spacing = _f(d.get("typical_section.girder_spacing"), 0.0)
    overhang = _f(d.get("typical_section.deck_overhang"), 0.0)
    width = _f(d.get("typical_section.overall_bridge_width"))
    if width is None and n:
        width = (n - 1) * spacing + 2 * overhang
    return {
        "n": n, "spacing": spacing, "overhang": overhang, "width": width or 0.0,
        "deck_t": (_f(d.get("typical_section.deck_thickness"), 250.0) or 250.0) / 1000.0,
        "cb_w": _f(d.get("typical_section.crash_barrier.width"), 0.45),
        "cb_h": _f(d.get("typical_section.crash_barrier.height"), 1.1),
        "wc_t": (_f(d.get("typical_section.wearing_course.thickness"), 50.0) or 50.0) / 1000.0,
        "span": _f(d.get("geometry.span"), 0.0), "skew": _f(d.get("geometry.skew_angle"), 0.0) or 0.0,
        "carriageway": _f(d.get("geometry.carriageway_width"), 0.0),
    }


def _fig(w, h):
    fig = Figure(figsize=(w, h), dpi=CHARTS["dpi"])
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _save(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.text(0.5, 0.005, NOTE, ha="center", va="bottom", fontsize=CHARTS["font_size"] - 3,
             color=CHARTS["neutral"], style="italic")
    fig.savefig(path, bbox_inches="tight", dpi=CHARTS["dpi"], facecolor="white")
    return path


def _dim_h(ax, x0, x1, y, text, off=0.0, fs=7):
    """Horizontal dimension line with end ticks and a centred label."""
    ax.annotate("", xy=(x0, y), xytext=(x1, y), arrowprops=dict(arrowstyle="<->", lw=0.7, color=LINE))
    ax.text((x0 + x1) / 2, y + off, text, ha="center", va="bottom" if off >= 0 else "top", fontsize=fs)


def _dim_v(ax, x, y0, y1, text, off=0.0, fs=7, ha="left"):
    ax.annotate("", xy=(x, y0), xytext=(x, y1), arrowprops=dict(arrowstyle="<->", lw=0.7, color=LINE))
    ax.text(x + off, (y0 + y1) / 2, text, ha=ha, va="center", fontsize=fs, rotation=90)


# ----------------------------------------------------------------------------
# Typical cross-section
# ----------------------------------------------------------------------------
def cross_section(d: dict, out_path: str) -> Optional[str]:
    g, gd = _geometry(d), _girder_dims(d)
    if g["n"] < 2 or g["width"] <= 0:
        return None
    W, t = g["width"], g["deck_t"]
    fig, ax = _fig(6.4, 3.6)

    # deck slab, wearing course, crash barriers
    ax.add_patch(Rectangle((0, 0), W, t, fc=CONCRETE, ec=LINE, lw=0.6))
    ax.add_patch(Rectangle((g["cb_w"], t), W - 2 * g["cb_w"], g["wc_t"], fc="#9A9A9A", ec=LINE, lw=0.4))
    for x0 in (0.0, W - g["cb_w"]):
        ax.add_patch(Rectangle((x0, t), g["cb_w"], g["cb_h"], fc=BARRIER, ec=LINE, lw=0.6, hatch="///"))

    # plate girders (top flange, web, bottom flange) hanging below the deck
    xs = [g["overhang"] + i * g["spacing"] for i in range(g["n"])]
    for i, xc in enumerate(xs, start=1):
        D, tw = gd["D"], gd["tw"]
        ax.add_patch(Rectangle((xc - gd["bft"] / 2, -gd["tft"]), gd["bft"], gd["tft"], fc=STEEL, ec=LINE, lw=0.4))
        ax.add_patch(Rectangle((xc - tw / 2, -(D - gd["tfb"])), tw, D - gd["tft"] - gd["tfb"], fc=STEEL, ec=LINE, lw=0.4))
        ax.add_patch(Rectangle((xc - gd["bfb"] / 2, -D), gd["bfb"], gd["tfb"], fc=STEEL, ec=LINE, lw=0.4))
        ax.text(xc, -D - 0.12, f"G{i}", ha="center", va="top", fontsize=8, fontweight="bold")

    D = gd["D"]
    top = t + g["cb_h"]
    # dimensions
    _dim_h(ax, 0, W, top + 0.35, f"Overall width {W:g} m", off=0.05)
    _dim_h(ax, g["cb_w"], W - g["cb_w"], top + 0.05, f"Carriageway {g['carriageway']:g} m", off=0.05)
    _dim_h(ax, xs[0], xs[1], -D - 0.55, f"{g['spacing']:g} m c/c", off=-0.05)
    _dim_h(ax, 0, xs[0], -D - 0.55, f"{g['overhang']:g} m", off=-0.05)
    _dim_h(ax, xs[-1], W, -D - 0.55, f"{g['overhang']:g} m", off=-0.05)
    _dim_v(ax, W + 0.3, 0, t, "", fs=6)
    ax.text(W + 0.5, t / 2, f"Deck {t * 1000:g} mm", ha="left", va="center", fontsize=7)
    _dim_v(ax, W + 0.3, -D, 0, f"Girder depth {D * 1000:g} mm", off=0.3, fs=7)
    ax.set_xlim(-0.8, W + 2.6)
    ax.set_ylim(-D - 1.3, top + 0.9)
    ax.set_title("Typical Cross-Section", fontsize=CHARTS["font_size"] + 1, fontweight="bold")
    return _save(fig, out_path)


# ----------------------------------------------------------------------------
# Plan view
# ----------------------------------------------------------------------------
def plan(d: dict, out_path: str) -> Optional[str]:
    g = _geometry(d)
    L, W = g["span"], g["width"]
    if not L or W <= 0 or g["n"] < 2:
        return None
    shear = math.tan(math.radians(g["skew"]))
    tx = lambda x, y: x + y * shear          # skewed abutment lines

    fig, ax = _fig(6.4, 2.6)
    ax.add_patch(Polygon([(tx(0, 0), 0), (tx(L, 0), 0), (tx(L, W), W), (tx(0, W), W)],
                         closed=True, fc=CONCRETE, ec=LINE, lw=0.8, alpha=0.55))
    ys = [g["overhang"] + i * g["spacing"] for i in range(g["n"])]
    for i, y in enumerate(ys, start=1):
        ax.plot([tx(0, y), tx(L, y)], [y, y], color=STEEL, lw=2.2, solid_capstyle="butt")
        ax.text(tx(0, y) - 0.5, y, f"G{i}", ha="right", va="center", fontsize=8, fontweight="bold")

    # transverse members: end diaphragms at both supports + intermediate cross bracing
    spacing_keys = [k for k in d if str(k).startswith("member_properties.cross_bracing_details.spacing.")]
    cb_s = _f(d.get(spacing_keys[0])) if spacing_keys else None
    xs = [0.0, L]
    if cb_s and cb_s > 0:
        k = 1
        while k * cb_s < L - 1e-6:
            xs.insert(len(xs) - 1, k * cb_s)
            k += 1
    for x in xs:
        end = x in (0.0, L)
        for y0, y1 in zip(ys[:-1], ys[1:]):
            style = dict(color="#C0504D" if end else "#E0A030", lw=1.0 if end else 0.8)
            ax.plot([tx(x, y0), tx(x, y1)], [y0, y1], **style)
    ax.plot([], [], color="#C0504D", label="End diaphragm")
    ax.plot([], [], color="#E0A030", label="Intermediate cross bracing")
    ax.plot([], [], color=STEEL, lw=2.2, label="Plate girder")
    ax.legend(fontsize=CHARTS["font_size"] - 2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.02), ncol=3)
    _dim_h(ax, 0, L, -0.9, f"Span {L:g} m", off=-0.1, fs=8)
    _dim_v(ax, -2.2, 0, W, f"{W:g} m", off=-0.25, fs=8, ha="right")
    if g["skew"]:
        ax.text(L, W + 0.3, f"Skew {g['skew']:g}°", ha="right", fontsize=7)
    ax.set_xlim(-4.0, L + max(2.0, abs(W * shear)) + 1)
    ax.set_ylim(-1.8, W + 1.2)
    ax.set_title("Plan View", fontsize=CHARTS["font_size"] + 1, fontweight="bold")
    return _save(fig, out_path)


# ----------------------------------------------------------------------------
# Longitudinal elevation
# ----------------------------------------------------------------------------
def elevation(d: dict, out_path: str) -> Optional[str]:
    g, gd = _geometry(d), _girder_dims(d)
    L = g["span"]
    if not L:
        return None
    D, t = gd["D"], g["deck_t"]
    fig, ax = _fig(6.4, 1.9)
    ax.add_patch(Rectangle((0, 0), L, t, fc=CONCRETE, ec=LINE, lw=0.6))
    ax.add_patch(Rectangle((0, -D), L, D, fc=STEEL, ec=LINE, lw=0.6, alpha=0.85))
    for x in (0.0, L):                                      # supports
        ax.add_patch(Polygon([(x, -D), (x - 0.45, -D - 0.65), (x + 0.45, -D - 0.65)], closed=True,
                             fc="white", ec=LINE, lw=0.8))
    _dim_h(ax, 0, L, t + 0.55, f"Span {L:g} m", off=0.05, fs=8)
    _dim_v(ax, L + 0.9, -D, 0, f"{D * 1000:g} mm", off=0.4, fs=7)
    ax.set_xlim(-1.5, L + 2.4)
    ax.set_ylim(-D - 1.1, t + 1.3)
    ax.set_title("Longitudinal Elevation", fontsize=CHARTS["font_size"] + 1, fontweight="bold")
    return _save(fig, out_path)


def render_schematics(input_dict: dict, out_dir: str) -> Dict[str, str]:
    """Render all schematics that can be drawn from *input_dict*.

    Returns {figure key: png path}. A drawing that cannot be built (missing or
    invalid geometry) is skipped, never raised, so report generation continues.
    """
    jobs = {"cross_section": cross_section, "girder_top": plan, "longitudinal_elevation": elevation}
    out: Dict[str, str] = {}
    for key, fn in jobs.items():
        try:
            path = fn(input_dict, os.path.join(out_dir, f"schematic_{key}.png"))
        except Exception as exc:                             # never break the report for a drawing
            logging.getLogger(__name__).warning("schematic '%s' skipped: %s", key, exc)
            path = None
        if path:
            out[key] = path
    return out
