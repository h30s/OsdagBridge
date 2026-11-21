# =============================================================================
# OsdagBridge report - programmatic charts
# =============================================================================
# Builds the bar charts embedded in the PDF design report:
#   * Utilization-ratio (UR = Demand / Capacity) summary, Section 5.5
#   * Material quantity charts, Chapter 7
#
# Colours, sizes and fonts come from styles.CHARTS (single source of truth).
# Uses matplotlib's object API (Figure + Agg canvas) rather than pyplot so it is
# safe to call from the report worker thread of the GUI.
# =============================================================================

from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from osdagbridge.core.reports.styles import CHARTS

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

# Primary elements shown in the UR summary, in display order.
UR_ELEMENTS = ("Steel Plate Girders", "Concrete Deck Slab", "Cross Bracing", "End Diaphragms")


def parse_number(cell) -> Optional[float]:
    """First number found in a table cell string (LaTeX markup tolerated), else None."""
    if cell is None:
        return None
    m = _NUMBER.search(str(cell))
    return float(m.group(0)) if m else None


def element_of(label: str) -> Optional[str]:
    """Map a Table 5.22 row label to one of UR_ELEMENTS."""
    s = label.lower()
    if s.startswith("girder"):
        return "Steel Plate Girders"
    if s.startswith("deck") or "(slab)" in s:
        return "Concrete Deck Slab"
    if s.startswith("cross bracing"):
        return "Cross Bracing"
    if s.startswith("end diaphragm"):
        return "End Diaphragms"
    return None


def _base_figure(figsize) -> Tuple[Figure, object]:
    fig = Figure(figsize=figsize, dpi=CHARTS["dpi"])
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.tick_params(labelsize=CHARTS["font_size"])
    ax.grid(axis="y", color=CHARTS["grid"], linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig, ax


def _save(fig: Figure, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, bbox_inches="tight", dpi=CHARTS["dpi"], facecolor="white")
    return path


def _ur_color(ur: float) -> str:
    return CHARTS["pass"] if ur <= 1.0 else CHARTS["fail"]


def _threshold_line(ax) -> None:
    ax.axhline(1.0, color=CHARTS["threshold"], linestyle="--", linewidth=1.4, zorder=3)


def _threshold_legend(ax, extra: Sequence = ()) -> None:
    handles = [
        Patch(facecolor=CHARTS["pass"], label="Pass (UR ≤ 1.0)"),
        Patch(facecolor=CHARTS["fail"], label="Fail (UR > 1.0)"),
        Line2D([0], [0], color=CHARTS["threshold"], linestyle="--", linewidth=1.4,
               label="UR = 1.0 limit"),
    ] + list(extra)
    ax.legend(handles=handles, fontsize=CHARTS["font_size"] - 1, frameon=False,
              loc="upper right")


def ur_governing_chart(rows: Iterable[Tuple[str, Optional[float]]], out_path: str) -> Optional[str]:
    """Bar per primary element = the highest UR among its checks.

    rows: (Table 5.22 row label, UR or None). Elements with no numeric UR are
    drawn as an empty slot labelled 'n/a' so the chart always shows all four.
    Returns the PNG path, or None if no element has any data.
    """
    gov: Dict[str, Optional[float]] = {e: None for e in UR_ELEMENTS}
    for label, ur in rows:
        el = element_of(label)
        if el and ur is not None and (gov[el] is None or ur > gov[el]):
            gov[el] = ur
    if all(v is None for v in gov.values()):
        return None

    fig, ax = _base_figure(CHARTS["figsize_wide"])
    xs = range(len(UR_ELEMENTS))
    vals = [gov[e] if gov[e] is not None else 0.0 for e in UR_ELEMENTS]
    bars = ax.bar(xs, vals, width=0.55, color=[_ur_color(v) if gov[e] is not None else "#FFFFFF"
                                               for e, v in zip(UR_ELEMENTS, vals)],
                  edgecolor=CHARTS["neutral"], linewidth=0.6, zorder=2)
    for bar, e in zip(bars, UR_ELEMENTS):
        if gov[e] is None:
            ax.text(bar.get_x() + bar.get_width() / 2, 0.03, "n/a", ha="center", va="bottom",
                    fontsize=CHARTS["font_size"], color=CHARTS["neutral"])
        else:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{gov[e]:.2f}", ha="center", va="bottom", fontsize=CHARTS["font_size"],
                    fontweight="bold", zorder=4,
                    bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.85))
    _threshold_line(ax)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([e.replace(" ", "\n", 1) for e in UR_ELEMENTS], fontsize=CHARTS["font_size"])
    ax.set_ylabel("Utilization Ratio (UR = Demand / Capacity)", fontsize=CHARTS["font_size"])
    ax.set_ylim(0, max(1.25, max(vals) * 1.2))
    ax.set_title("Governing Utilization Ratio by Primary Element",
                 fontsize=CHARTS["font_size"] + 1, fontweight="bold")
    _threshold_legend(ax)
    return _save(fig, out_path)


def ur_checks_chart(rows: Iterable[Tuple[str, Optional[float]]], out_path: str) -> Optional[str]:
    """One bar per individual check, grouped by primary element."""
    items: List[Tuple[str, str, float]] = []
    for label, ur in rows:
        el = element_of(label)
        if el and ur is not None:
            items.append((el, label, ur))
    if not items:
        return None
    items.sort(key=lambda t: UR_ELEMENTS.index(t[0]))

    fig, ax = _base_figure((CHARTS["figsize_wide"][0], CHARTS["figsize_wide"][1] + 1.6))
    xs = list(range(len(items)))
    ax.bar(xs, [t[2] for t in items], width=0.7, color=[_ur_color(t[2]) for t in items],
           edgecolor=CHARTS["neutral"], linewidth=0.5, zorder=2)
    for x, (_, _, ur) in zip(xs, items):
        ax.text(x, ur + 0.02, f"{ur:.2f}", ha="center", va="bottom",
                fontsize=CHARTS["font_size"] - 2, zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.85))
    # element separators + group labels under the rotated tick labels
    for el in UR_ELEMENTS:
        idx = [i for i, it in enumerate(items) if it[0] == el]
        if not idx:
            continue
        if idx[0] > 0:
            ax.axvline(idx[0] - 0.5, color=CHARTS["grid"], linewidth=1.0, zorder=1)
        ax.annotate(el.replace(" ", "\n", 1), xy=((idx[0] + idx[-1]) / 2, 0), xycoords=("data", "axes fraction"),
                    xytext=(0, -78), textcoords="offset points", ha="center", va="top",
                    fontsize=CHARTS["font_size"] - 2, fontweight="bold", color=CHARTS["neutral"],
                    linespacing=1.1)
    _threshold_line(ax)
    short = [re.sub(r"^(Girder|Deck|Cross Bracing|End Diaphragm)\s*---\s*", "", t[1]) for t in items]
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{s}" for s in short], rotation=60, ha="right",
                       fontsize=CHARTS["font_size"] - 2)
    ax.set_ylabel("Utilization Ratio", fontsize=CHARTS["font_size"])
    ax.set_ylim(0, max(1.25, max(t[2] for t in items) * 1.2))
    ax.set_title("Utilization Ratio of Each Design Check", fontsize=CHARTS["font_size"] + 1,
                 fontweight="bold")
    _threshold_legend(ax)
    return _save(fig, out_path)


# ----------------------------------------------------------------------------
# Material quantities (Chapter 7)
# ----------------------------------------------------------------------------
def qty_value(quantities: dict, key: str) -> Optional[float]:
    """Numeric value for a BOQ key; None for 'N.A.' / missing."""
    return parse_number(quantities.get(key))


def steel_tonnage_chart(quantities: dict, out_path: str) -> Optional[str]:
    """Structural steel weight (MT) of girders, cross bracing and end diaphragms."""
    girders = qty_value(quantities, "steel_girders_wt_total")
    bracing_parts = [qty_value(quantities, k) for k in
                     ("bracing_top_wt_total", "bracing_bot_wt_total", "bracing_diag_wt_total")]
    bracing = sum(p for p in bracing_parts if p is not None) if any(p is not None for p in bracing_parts) \
        else qty_value(quantities, "steel_bracing_wt_total")
    diaphragm = qty_value(quantities, "end_diaphragm_wt_total")   # not produced by the BOQ yet
    data = [("Girders", girders), ("Cross Bracing", bracing), ("End Diaphragms", diaphragm)]
    if all(v is None for _, v in data):
        return None

    fig, ax = _base_figure(CHARTS["figsize_two_panel"])
    colors = CHARTS["series"]
    top = max((v for _, v in data if v is not None), default=1.0)
    for i, (name, val) in enumerate(data):
        if val is None:
            ax.bar(i, 0, width=0.5)
            ax.text(i, top * 0.03, "N.A.", ha="center", va="bottom", fontsize=CHARTS["font_size"],
                    color=CHARTS["neutral"])
        else:
            ax.bar(i, val, width=0.5, color=colors[i % len(colors)], zorder=2)
            ax.text(i, val + top * 0.02, f"{val:.2f}", ha="center", va="bottom",
                    fontsize=CHARTS["font_size"], fontweight="bold")
    ax.set_xticks(range(len(data)))
    ax.set_xticklabels([n for n, _ in data], fontsize=CHARTS["font_size"])
    ax.set_ylabel("Structural steel (MT)", fontsize=CHARTS["font_size"])
    ax.set_ylim(0, top * 1.2)
    ax.set_title("Structural Steel Tonnage", fontsize=CHARTS["font_size"] + 1, fontweight="bold")
    return _save(fig, out_path)


def concrete_vs_rebar_chart(quantities: dict, out_path: str) -> Optional[str]:
    """Deck concrete volume (m3) next to reinforcement steel weight (MT).

    Different units, so two y-axes (left: concrete, right: rebar).
    """
    conc = qty_value(quantities, "concrete_deck_vol_total")
    rebar = qty_value(quantities, "rebar_deck_wt_total")
    if conc is None and rebar is None:
        return None
    fig, ax = _base_figure(CHARTS["figsize_two_panel"])
    ax2 = ax.twinx()
    ax2.spines["top"].set_visible(False)
    ax2.tick_params(labelsize=CHARTS["font_size"])
    c1, c2 = CHARTS["series"][1], CHARTS["series"][2]
    if conc is not None:
        ax.bar(0, conc, width=0.45, color=c1, zorder=2)
        ax.text(0, conc * 1.02, f"{conc:.2f} m³", ha="center", va="bottom",
                fontsize=CHARTS["font_size"], fontweight="bold")
    if rebar is not None:
        ax2.bar(1, rebar, width=0.45, color=c2, zorder=2)
        ax2.text(1, rebar * 1.02, f"{rebar:.2f} MT", ha="center", va="bottom",
                 fontsize=CHARTS["font_size"], fontweight="bold")
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(0, (conc or 1.0) * 1.25)
    ax2.set_ylim(0, (rebar or 1.0) * 1.25)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Deck concrete", "Reinforcement steel"], fontsize=CHARTS["font_size"])
    ax.set_ylabel("Concrete volume (m³)", fontsize=CHARTS["font_size"], color=c1)
    ax2.set_ylabel("Reinforcement weight (MT)", fontsize=CHARTS["font_size"], color=c2)
    ax.set_title("Concrete Volume vs Reinforcement Steel Weight", fontsize=CHARTS["font_size"] + 1,
                 fontweight="bold")
    return _save(fig, out_path)
