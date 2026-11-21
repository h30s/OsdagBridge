"""Layout QA for generated OsdagBridge design-report PDFs.

Detects the two page-layout defects that were reported against the report:

1. Body text (e.g. a table cell such as a girder label "G4") that spills into the
   footer band at the bottom of a page.
2. The "* Software default value" footer note overlapping the last body line.

Requires poppler's ``pdftotext`` on PATH (``conda install poppler`` /
``apt install poppler-utils``).

Usage:
    python tools/report_layout_check.py Report_After.pdf
Exit status is 0 when the layout is clean, 1 when problems are found.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from typing import List

PAGE_HEIGHT_PT = 841.89        # A4
BOTTOM_MARGIN_PT = 72.0        # 1 in, see reports/styles.py DOCUMENT["margin"]
TOLERANCE_PT = 6.0             # descender / baseline slack, not a real intrusion
FOOTER_TOKENS = {"Osdag", "|", "FOSSEE", "Indian", "Institute", "of", "Technology",
                 "Bombay", "Page", "*", "Software", "default", "value"}

_WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')


@dataclass
class Problem:
    page: int
    message: str

    def __str__(self) -> str:
        return f"page {self.page}: {self.message}"


def _pages(pdf_path: str) -> List[str]:
    xml = subprocess.run(["pdftotext", "-bbox", pdf_path, "-"], capture_output=True,
                         text=True, check=True).stdout
    return re.split(r"<page ", xml)[1:]


def check(pdf_path: str) -> List[Problem]:
    """Return every layout problem found in *pdf_path* (empty list = clean)."""
    limit = PAGE_HEIGHT_PT - BOTTOM_MARGIN_PT
    problems: List[Problem] = []
    for number, page in enumerate(_pages(pdf_path), start=1):
        words = [(float(m[1]), float(m[2]), float(m[3]), float(m[4]), m[5].strip())
                 for m in _WORD.finditer(page)]
        # ignore empty / invisible tokens (e.g. soft hyphens: Unicode category "C*")
        words = [w for w in words if w[4] and not all(unicodedata.category(c).startswith("C") for c in w[4])]
        body = [w for w in words if w[4] not in FOOTER_TOKENS and not w[4].isdigit()]
        for _x0, _y0, _x1, y1, text in body:
            if y1 > limit + TOLERANCE_PT:
                problems.append(Problem(number, f"body text '{text}' (bottom {y1:.1f}pt) is inside "
                                                f"the footer band (> {limit + TOLERANCE_PT:.1f}pt)"))
        note = [w for w in words if w[4] == "Software"]
        if note:
            note_top = min(w[1] for w in note)
            above = [w for w in body if w[1] < note_top - 1]
            bottom = max((w[3] for w in above), default=0.0)
            if bottom > note_top + 0.5:
                problems.append(Problem(number, f"default-value note (top {note_top:.1f}pt) overlaps "
                                                f"body text (bottom {bottom:.1f}pt)"))
    return problems


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    problems = check(argv[1])
    for p in problems:
        print(p)
    print(f"{len(_pages(argv[1]))} pages checked, {len(problems)} layout problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
