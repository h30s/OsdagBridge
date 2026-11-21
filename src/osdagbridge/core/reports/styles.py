# =============================================================================
# OsdagBridge report - centralized style system (single source of truth)
# =============================================================================
# Every formatting decision of the PDF design report lives in this module:
# page geometry, fonts, colour palette, table metrics, header/footer, status
# colouring, chart palette and the LaTeX helpers (longtable heads, notes,
# figure boxes) that the chapter generators call.
#
# RULE: chapter / section generator files must NOT hard-code fonts, colours,
# paddings, margins or table styles. They import them from here, so a global
# restyle (e.g. a new brand colour or tighter tables) is a one-line edit.
#
# Layout of this file
#   1. DOCUMENT   - class, paper, margins, font size, line spacing
#   2. COLORS     - named palette (also exported to LaTeX as \definecolor)
#   3. TABLES     - padding, rule widths, row heights, header shading
#   4. HEADER_FOOTER - running header / footer content and geometry
#   5. CHARTS     - matplotlib palette and sizes for embedded figures
#   6. LaTeX builders - preamble(), longtable_head(), status helpers, ...
# =============================================================================

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

# ----------------------------------------------------------------------------
# 1. DOCUMENT
# ----------------------------------------------------------------------------
DOCUMENT = {
    "class": "report",
    "font_size": "12pt",
    "paper": "a4paper",
    "margin": "1in",
    # Footer needs room for the optional "* Software default value" note AND
    # the footer text; a larger footskip keeps body text from reaching it.
    "footskip": "40pt",
    "headheight": "14.5pt",
    "line_stretch": "1.15",
}

# ----------------------------------------------------------------------------
# 2. COLORS  (HTML hex, no '#')
# ----------------------------------------------------------------------------
COLORS: Dict[str, str] = {
    "osdagGreen": "91B014",     # brand colour: rules, footer text
    "statusPass": "1B7F3B",     # PASS text
    "statusFail": "C62828",     # FAIL text
    "tableHead": "EEF3DB",      # light osdagGreen tint for table header rows
    "noteGrey": "555555",       # table notes
    "statusInfo": "1F5FA8",     # informational log lines
    "urOk": "E3F1D6",           # UR heat map: <= 0.90
    "urWarn": "FFF1CC",         # UR heat map: 0.90 < UR <= 1.00 (passes, close to the limit)
    "urFail": "F8D7D7",         # UR heat map: > 1.00
}

# ----------------------------------------------------------------------------
# 3. TABLES
# ----------------------------------------------------------------------------
TABLES = {
    "tabcolsep": "6pt",         # horizontal cell padding
    "arraystretch": "1.12",     # row height multiplier
    "extrarowheight": "0.6pt",
    "arrayrulewidth": "0.5pt",
    "lt_pre": "0pt",            # space above a longtable
    "lt_post": "6pt",           # space below a longtable
    "header_gap": "6pt",        # gap after the header row
    "needspace_lines": 5,       # start a table on a new page if < N lines left
    "colspec_default": "|C{2.5cm}|C{3.5cm}|C{3.5cm}|C{4.2cm}|C{1.8cm}|",
    "arraystretch_dense": "1.25",
}

# Horizontal cell padding (pt) per table density. Wide tables use tighter
# padding; longtable_head() uses it to fit the column widths to the page.
TABLE_DENSITY = {"normal": 6.0, "compact": 4.0, "dense": 3.5, "denser": 3.0}

# Usable text width: A4 (21.0 cm) minus two 1-inch margins.
TEXT_WIDTH_CM = 21.0 - 2 * 2.54

# ----------------------------------------------------------------------------
# 4. HEADER / FOOTER
# ----------------------------------------------------------------------------
HEADER_FOOTER = {
    "head_rule": "1pt",
    "foot_rule": "1pt",
    "footer_left": r"Osdag $|$ FOSSEE $|$ Indian Institute of Technology Bombay",
    "default_value_note": r"* Software default value",
}

# ----------------------------------------------------------------------------
# 5. CHARTS (matplotlib) - hex colours with '#'
# ----------------------------------------------------------------------------
CHARTS = {
    "dpi": 200,
    "figsize_wide": (6.4, 3.4),
    "figsize_two_panel": (6.4, 3.0),
    "font_size": 9,
    "pass": "#" + COLORS["osdagGreen"],     # bars with UR <= 1.0
    "fail": "#" + COLORS["statusFail"],     # bars with UR > 1.0
    "threshold": "#C62828",                 # UR = 1.0 reference line
    "neutral": "#5B6B7A",
    "series": ["#91B014", "#3E7CB1", "#E0A030", "#8E5EA2", "#5B6B7A"],
    "grid": "#D9D9D9",
}


# ----------------------------------------------------------------------------
# 6. LaTeX builders
# ----------------------------------------------------------------------------

def _fill(template: str, values: Dict[str, object]) -> str:
    """Replace <<key>> tokens (LaTeX uses % and {} heavily, so no str.format)."""
    out = template
    for key, val in values.items():
        out = out.replace("<<%s>>" % key, str(val))
    return out

def color_definitions() -> str:
    return "\n".join(
        r"\definecolor{%s}{HTML}{%s}" % (name, hexv) for name, hexv in COLORS.items()
    )


def preamble_packages() -> str:
    return _fill(r"""
\documentclass[<<font_size>>,<<paper>>]{<<class>>}

% Packages
\usepackage[<<paper>>, margin=<<margin>>, footskip=<<footskip>>, headheight=<<headheight>>]{geometry}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{booktabs}
\usepackage{array}
\usepackage{tabularx}
\usepackage{float}
\usepackage{fancyhdr}
\usepackage[hidelinks]{hyperref}
\usepackage{xcolor}
\usepackage{setspace}
\usepackage{enumitem}
\usepackage{caption}

\captionsetup{
    labelfont=bf,
    justification=raggedright,
    singlelinecheck=false,
    format=plain
}
\usepackage{subcaption}
\usepackage{multirow}
\usepackage{colortbl}
\usepackage{longtable}
\setlength{\LTleft}{\fill}
\setlength{\LTright}{\fill}
\usepackage{titlesec}
\usepackage{titletoc}
\usepackage{lastpage}
\usepackage{makecell}
\usepackage{etoolbox}
\usepackage{needspace}
""", DOCUMENT)


def preamble_tables() -> str:
    return _fill(r"""
\numberwithin{table}{chapter}
\numberwithin{figure}{chapter}
% Table layout and spacing: consistent padding, row height, and longtable pre/post skips
\setlength{\tabcolsep}{<<tabcolsep>>}
\renewcommand{\arraystretch}{<<arraystretch>>}
\setlength{\LTpre}{<<lt_pre>>}
\setlength{\LTpost}{<<lt_post>>}
% Table rules (outline thickness) and small extra row height for clarity
\setlength{\arrayrulewidth}{<<arrayrulewidth>>}
\setlength{\extrarowheight}{<<extrarowheight>>}

% Floating tables keep a minimum amount of room. NOTE: do NOT add \needspace
% before longtable: it fights longtable's own page-break logic and strands the
% table head at the bottom of a page (duplicated "(continued)" header).
\BeforeBeginEnvironment{table}{\needspace{<<needspace_lines>>\baselineskip}}
""", TABLES)


def _running_header_footer(style: str, pn: str, jn: str, rd: str, rv: str) -> str:
    h = HEADER_FOOTER
    return _fill(r"""
\fancypagestyle{<<style>>}{
  \fancyhf{}
  \fancyhead[L]{<<pn>> $|$ <<jn>>}
  \fancyhead[R]{<<rd>> $|$ <<rv>>}
  \fancyfoot[L]{\color{osdagGreen}<<footer_left>>}
  \fancyfoot[R]{\color{osdagGreen}Page \thepage\ of \pageref{LastPage}}
  \renewcommand{\headrule}{\color{osdagGreen}\hrule width\headwidth height <<head_rule>> \vspace{2pt}}
  \renewcommand{\footrule}{%
    \color{osdagGreen}\hrule width\headwidth height <<foot_rule>> \vspace{3pt}%
    \ifbool{hasSDonPage}{%
      \hbox to \headwidth{\textcolor{black}{\footnotesize\textit{<<default_value_note>>}}\hfil}%
      \vspace{3pt}%
    }{}%
  }
}
""", dict(h, style=style, pn=pn, jn=jn, rd=rd, rv=rv))


def preamble(pn: str, jn: str, rd: str, rv: str) -> str:
    """Full LaTeX preamble up to and including \\begin{document}.

    pn/jn/rd/rv are already LaTeX-escaped project name, job number, date, rev.
    """
    h = HEADER_FOOTER
    return (
        preamble_packages()
        + preamble_tables()
        + "\n" + color_definitions() + "\n"
        + _running_header_footer("main", pn, jn, rd, rv)
        + _running_header_footer("plain", pn, jn, rd, rv)
        + _fill(r"""
\fancypagestyle{firstpage}{
  \fancyhf{}
  \renewcommand{\headrulewidth}{0pt}
  \fancyfoot[L]{\color{osdagGreen}<<footer_left>>}
  \fancyfoot[R]{\color{osdagGreen}Page \thepage\ of \pageref{LastPage}}
  \renewcommand{\footrule}{\color{osdagGreen}\hrule width\headwidth height <<foot_rule>> \vspace{3pt}}
}
\pagestyle{main}
\setstretch{<<line_stretch>>}
""", dict(h, **DOCUMENT))
        + r"""
% Custom Commands
\newcommand{\placeholder}[1]{\textit{\textless #1\textgreater}}
\newcommand{\todo}[1]{\colorbox{yellow}{TODO: #1}}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcolumntype{C}[1]{>{\centering\arraybackslash}p{#1}}
\newcolumntype{R}[1]{>{\raggedleft\arraybackslash}p{#1}}

% Status colouring (used via \passtext / \failtext)
\newcommand{\passtext}[1]{\textcolor{statusPass}{#1}}
\newcommand{\failtext}[1]{\textcolor{statusFail}{\textbf{#1}}}

% Software-default asterisk
\newcommand{\sdstar}{\textsuperscript{*}}
\newbool{hasSDonPage}
\boolfalse{hasSDonPage}
\newcommand{\markSD}{\global\booltrue{hasSDonPage}}
\renewcommand{\sdstar}{\textsuperscript{*}\markSD{}}
\AddToHook{shipout/before}{\global\boolfalse{hasSDonPage}}

\title{\Large\textbf{OsdagBridge} \\ \normalsize Open Source Software for Steel Girder Bridge Design \\ \vspace{2cm} \large Design Report}
\author{}
\date{}

\begin{document}
"""
    )


# ---- status helpers --------------------------------------------------------
def fail_text(text: str = "FAIL") -> str:
    """LaTeX for a failing status cell."""
    return r"\failtext{%s}" % text


def pass_text(text: str = "PASS") -> str:
    """LaTeX for a passing status cell."""
    return r"\passtext{%s}" % text


def status_text(ok: Optional[bool], pass_label: str = "PASS", fail_label: str = "FAIL",
                unknown: str = "---") -> str:
    """PASS / FAIL / unknown, coloured from the palette."""
    if ok is None:
        return unknown
    return pass_text(pass_label) if ok else fail_text(fail_label)


# ---- table helpers ---------------------------------------------------------
_PT_TO_CM = 2.54 / 72.27


def tabcolsep_cmd(density: str = "normal") -> str:
    r"""LaTeX that sets the cell padding for a table density (see TABLE_DENSITY)."""
    return r"\setlength{\tabcolsep}{%gpt}" % TABLE_DENSITY[density]


def dense_table_setup() -> str:
    """Small type + tight padding for very wide tables (e.g. summary of demands)."""
    return "\n".join([r"\footnotesize", tabcolsep_cmd("denser"),
                      r"\renewcommand{\arraystretch}{" + TABLES["arraystretch_dense"] + "}"])


def fit_colspec(colspec: str, density: str = "normal", text_width_cm: float = TEXT_WIDTH_CM) -> str:
    """Scale the fixed column widths (e.g. ``p{4.2cm}``) so the table fits the text width.

    Column widths are given in cm; each column also costs 2*tabcolsep of padding and
    a rule. If the table is already narrower than the text width it is unchanged.
    """
    import re
    widths = [float(w) for w in re.findall(r"\{([0-9.]+)cm\}", colspec)]
    if not widths:
        return colspec
    n = len(widths)
    pad = 2 * TABLE_DENSITY[density] * _PT_TO_CM
    rule = float(TABLES["arrayrulewidth"].replace("pt", "")) * _PT_TO_CM
    overhead = n * pad + (n + 1) * rule + 0.05            # + small safety margin
    available = text_width_cm - overhead
    total = sum(widths)
    if total <= available:
        return colspec
    scale = available / total
    return re.sub(r"\{([0-9.]+)cm\}", lambda m: "{%.2fcm}" % (float(m.group(1)) * scale), colspec)


def _strip_row_end(row: str) -> str:
    """Remove a trailing '\\\\' (and optional [..pt]) from a table row string."""
    import re
    return re.sub(r"\s*\\\\(\[[^\]]*\])?\s*$", "", row.strip())


def longtable_head(colspec: str, caption: str, header: str, *, shade: bool = True,
                   density: str = "normal", fit: bool = True) -> str:
    r"""Opening of a longtable whose header row repeats on every page.

    Emits ``\begin{longtable}``, the caption, the header row, ``\endfirsthead``,
    a continuation caption + header row, and ``\endhead``. The caller appends
    the body rows and ``\end{longtable}``.

    colspec  - column spec, e.g. r"|C{2cm}|L{5cm}|" (widths are auto-fitted to the page)
    caption  - caption LaTeX (may contain \textbf{...})
    header   - header row cells separated by '&' (a trailing '\\' is optional)
    density  - key of TABLE_DENSITY matching the tabcolsep in force for this table
    """
    gap = TABLES["header_gap"]
    row = _strip_row_end(header)
    shade_cmd = r"\rowcolor{tableHead}" if shade else ""
    head_row = shade_cmd + row + r" \\[" + gap + "]"
    spec = fit_colspec(colspec, density) if fit else colspec
    return "\n".join([
        r"\begin{longtable}{" + spec + "}",
        r"\caption{" + caption + r"}\\",
        r"\hline",
        head_row,
        r"\hline",
        r"\endfirsthead",
        r"\caption*{" + caption + r" \textit{(continued)}}\\",
        r"\hline",
        head_row,
        r"\hline",
        r"\endhead",
    ]) + "\n"


def ur_cell(ur, text: str) -> str:
    r"""Heat-shade a utilization-ratio table cell (full-cell background, needs colortbl).

    ur may be None (no shading). Bands: <= 0.90 green, <= 1.00 amber, > 1.00 red.
    If the cell is in the LAST column of a table, end that column spec with
    RIGHT_RULE instead of "|": colortbl paints a last-column background over the
    table's right border, a rule drawn as a column separator is drawn on top.
    """
    if ur is None or text.strip() in ("", "---"):
        return text
    name = "urOk" if ur <= 0.90 else ("urWarn" if ur <= 1.0 else "urFail")
    return r"\cellcolor{" + name + "}" + text


# Right-hand table border that survives a shaded last-column cell (see ur_cell).
RIGHT_RULE = r"!{\vrule width\arrayrulewidth}"


def verdict_banner(status: str, headline: str, detail: str) -> str:
    """Boxed overall verdict. status: 'Pass' | 'Fail' | anything else (neutral grey)."""
    colour = {"Pass": "statusPass", "Fail": "statusFail"}.get(status, "noteGrey")
    return "\n".join([
        r"\begin{center}",
        r"\fcolorbox{" + colour + "}{" + colour + r"!8}{\begin{minipage}{0.94\textwidth}\centering",
        r"{\large\bfseries\textcolor{" + colour + "}{" + headline + "}}\\\\[3pt]",
        detail,
        r"\end{minipage}}",
        r"\end{center}",
    ]) + "\n"


def figure_block(rel_path: str, caption: str, width: str = r"0.92\textwidth", numbered: bool = True) -> str:
    """Numbered, centred figure ([H] keeps it right where it is generated)."""
    return "\n".join([
        r"\begin{figure}[H]",
        r"\centering",
        r"\includegraphics[width=" + width + "]{" + rel_path.replace("\\", "/") + "}",
        (r"\caption{" if numbered else r"\caption*{") + caption + "}",
        r"\end{figure}",
    ]) + "\n"


def table_note(text: str) -> str:
    """Small italic note placed directly under a table."""
    return r"\noindent\textit{" + text + "}"
