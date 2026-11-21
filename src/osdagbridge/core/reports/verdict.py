# =============================================================================
# OsdagBridge report - design verdict (single source of truth for pass / fail)
# =============================================================================
# The executive summary, the UR charts and Table 5.22 must never disagree. All of
# them are therefore derived from ONE list of records:
#
#     records = [(row label, utilization ratio or None), ...]
#
# which chapter 5 builds from the numbers behind Table 5.22. This module turns
# those records into per-element and overall verdicts. Nothing here is
# hard-coded: an element with no data is reported as "Not evaluated", never as
# "Pass".
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from osdagbridge.core.reports.charts import UR_ELEMENTS, element_of

UR_LIMIT = 1.0                       # UR = Demand / Capacity; <= 1.0 passes
WARN_BAND = 0.90                     # amber band: 0.90 < UR <= 1.0 passes but is close to the limit

Record = Tuple[str, Optional[float]]


@dataclass(frozen=True)
class ElementVerdict:
    element: str
    max_ur: Optional[float]
    governing: str                    # label of the check with the highest UR ("" if none)
    n_checks: int
    n_failing: int

    @property
    def status(self) -> str:
        if self.max_ur is None:
            return "Not evaluated"
        return "Pass" if self.max_ur <= UR_LIMIT else "Fail"


def ur_band(ur: Optional[float]) -> str:
    """'ok' | 'warn' | 'fail' | 'none' - used for heat-shading UR cells."""
    if ur is None:
        return "none"
    if ur > UR_LIMIT:
        return "fail"
    return "warn" if ur > WARN_BAND else "ok"


def clean_label(label: str) -> str:
    """'Girder --- Moment' -> 'Moment' (the element prefix is shown separately)."""
    import re
    return re.sub(r"^(Girder|Deck|Cross Bracing|End Diaphragm)\s*---\s*", "", label).strip()


def element_verdicts(records: Iterable[Record]) -> List[ElementVerdict]:
    """One verdict per primary element, in the fixed display order."""
    best = {e: None for e in UR_ELEMENTS}      # element -> (ur, label)
    count = {e: 0 for e in UR_ELEMENTS}
    failing = {e: 0 for e in UR_ELEMENTS}
    for label, ur in records:
        el = element_of(label)
        if el is None or ur is None:
            continue
        count[el] += 1
        failing[el] += ur > UR_LIMIT
        if best[el] is None or ur > best[el][0]:
            best[el] = (ur, label)
    return [ElementVerdict(e, best[e][0] if best[e] else None,
                           clean_label(best[e][1]) if best[e] else "", count[e], failing[e])
            for e in UR_ELEMENTS]


def overall_status(verdicts: Sequence[ElementVerdict]) -> str:
    """'Fail' if any element fails, 'Pass' if some are evaluated and none fail, else 'Not evaluated'."""
    states = {v.status for v in verdicts}
    if "Fail" in states:
        return "Fail"
    return "Pass" if "Pass" in states else "Not evaluated"


def failing_checks(records: Iterable[Record]) -> List[Tuple[str, float]]:
    """All checks with UR > 1.0, worst first."""
    out = [(label, ur) for label, ur in records if ur is not None and ur > UR_LIMIT]
    return sorted(out, key=lambda t: t[1], reverse=True)


def governing_overall(verdicts: Sequence[ElementVerdict]) -> Optional[ElementVerdict]:
    """The element with the highest utilization ratio (None if nothing was evaluated)."""
    ev = [v for v in verdicts if v.max_ur is not None]
    return max(ev, key=lambda v: v.max_ur) if ev else None
