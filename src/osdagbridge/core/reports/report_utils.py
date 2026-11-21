from osdagbridge.core.utils.common import (
    KEY_MP_GD_MEMBER_ID,
    KEY_MP_GD_SELECT_GIRDER,
    KEY_MP_GIRDER_DEPTH,
    KEY_TS_NO_OF_GIRDERS
)


# Applied AFTER escaping, so the inserted $...$ math is not itself escaped.
_UNICODE_TO_TEX = {
    '≤': r'$\leq$', '≥': r'$\geq$', '±': r'$\pm$', '≠': r'$\neq$',
    '°': r'$^{\circ}$', 'μ': r'$\mu$', 'Ω': r'$\Omega$',
    '²': r'$^{2}$', '³': r'$^{3}$', '–': '--', '—': '---',
    '→': r'$\rightarrow$',
}


def _tex(value):
    """Escape a Python value for safe LaTeX embedding."""
    s = str(value) if value is not None else ''
    if not s:
        return r''
    # Normalise non-ASCII glyphs from section designations (e.g. "∠ 100 ⅹ 100ⅹ 10")
    # that pdflatex cannot render.
    for uni, ascii_ in [('∠', 'L'), ('ⅹ', 'x'), ('×', 'x')]:
        s = s.replace(uni, ascii_)
    s = s.replace('\\', r'\textbackslash{}')
    for ch, esc in [('&', r'\&'), ('%', r'\%'), ('$', r'\$'), ('#', r'\#'),
                    ('{', r'\{'), ('}', r'\}'),          
                    ('_', r'\_\allowbreak{}'),            
                    ('~', r'\textasciitilde{}'), ('^', r'\^{}')]:
        s = s.replace(ch, esc)
    s = s.replace(':', r':\allowbreak{}')
    # Unicode math/typographic symbols pdflatex (T1/OT1) cannot typeset.
    for uni, tex in _UNICODE_TO_TEX.items():
        s = s.replace(uni, tex)
    return s


_LC_GROUPS = ("envelope uls", "envelope sls", "1.0 dl", "1.0 dw", "sw", "dd", "1.0 ll", "basic", "accidental",
              "seismic", "sls_rare", "sls_frequent", "sls_qp")


def load_case_sort_key(name):
    """Stable display order for load cases (the analysis returns them in set order,
    which changes from run to run). Envelopes, permanent loads, live load, then the
    ULS / accidental / seismic / SLS combinations, each sorted by their number."""
    import re
    n = str(name).strip().lower()
    group = next((i for i, g in enumerate(_LC_GROUPS) if n == g or n.startswith(g)), len(_LC_GROUPS))
    nums = tuple(int(x) for x in re.findall(r"\d+", n))
    return (group, nums, n)


def design_lane_count(input_dict):
    """Number of design lanes (IRC 6 Table 6) from the carriageway width, or None.

    The UI lane counter (KEY_WC_LD_LANE_TABLE_COUNT) is not stored in the design
    dictionary, so the report derives the count the same way the analysis does.
    """
    try:
        from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017
        return int(IRC6_2017.table_6(float(input_dict.get("geometry.carriageway_width"))))
    except Exception:
        return None


def _render_mm(source_dict, key, unit=" mm"):
    """Girder dimensions for display, in mm.

    PlateGirderBridge.design() converts girder section dimensions from mm to SI
    metres in the input dictionary, so a design report built afterwards sees
    e.g. 1.67 for a 1670 mm depth. Values below 10 are therefore metres (no steel
    girder dimension is below 10 mm or above 10 m); larger values are already mm.
    Non-numeric values (e.g. "All") are shown as-is.
    """
    val = source_dict.get(key)
    if val in ("", None):
        return ""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return _tex(val)          # e.g. "All": no unit
    if abs(f) < 10.0:
        f *= 1000.0
    return f"{f:g}" + unit


def _render_value(source_dict, key, unit=""):
    val = source_dict.get(key)
    if val in ("", None):
        return ""
    return _tex(val) + unit


def get_girder_entries(input_dict):
    """
    Retrieve all girder labels and member IDs from backend keys.

    Usage Example:
    --------------------------
    girder_entries = get_girder_entries(bridge.input_dict)
    
    # 1. Fallback handling (if backend hasn't populated keys yet)
    if not girder_entries:
        n = int(bridge.input_dict.get(KEY_TS_NO_OF_GIRDERS, 1))
        girder_entries = [(f"Girder {i}", f"M1") for i in range(1, n + 1)]
        
    # 2. Get total number of girders safely
    n_girders = len(girder_entries)
    
    # 3. Iterate over the girders to build table rows
    for lbl, mid in girder_entries:
        # lbl will be e.g., "G1", mid will be e.g., "G1M1"
        # Access girder specific keys dynamically:
        # val = input_dict.get(f"{KEY_MP_GIRDER_DEPTH}.{lbl}.{mid}")
        pass

    Returns:
        List[Tuple[str, str]]
    """
    n = int(input_dict.get(KEY_TS_NO_OF_GIRDERS, 0))

    entries = []

    for i in range(1, n + 1):
        entries.append(
            (
                input_dict.get(f"{KEY_MP_GD_SELECT_GIRDER}.G{i}", ""),
                input_dict.get(f"{KEY_MP_GD_MEMBER_ID}.G{i}.M1", ""),
            )
        )

    return entries


def _fig_or_placeholder(path, caption, width=r'0.9\textwidth'):
    """Embed figure if path is provided (file already copied to assets), else show placeholder box.
    path is the relative path as pdflatex will see it (e.g. 'assets/plan.png').
    """
    if path:
        p = path.replace('\\', '/')
        return (r'\begin{figure}[H]' + '\n'
                r'\centering' + '\n'
                r'\includegraphics[width=' + width + ']{' + p + '}\n'
                r'\caption*{' + caption + '}\n'
                r'\end{figure}')
    return (r'\begin{figure}[H]' + '\n'
            r'\centering' + '\n'
            r'\fbox{\parbox{0.97\textwidth}{' + '\n'
            r'\textit{[ PLACEHOLDER: ' + caption + r' ]}' + '\n'
            r'}}' + '\n'
            r'\caption*{' + caption + '}\n'
            r'\end{figure}')

def _fig_embed(path, caption, width=r'\textwidth', height=None):
    """Embed a real figure when path is provided (already copied); otherwise use an fbox placeholder."""
    if path:
        p = path.replace('\\', '/')
        opts = 'width=' + width
        if height:
            opts += ',height=' + height + ',keepaspectratio'
        return (r'\begin{figure}[H]' + '\n'
                r'\vspace{-0.5em}' + '\n'
                r'\centering' + '\n'
                r'\includegraphics[' + opts + ']{' + p + '}\n'
                r'\vspace{0.5em}' + '\n'
                r'\caption*{\small ' + caption + '}\n'
                r'\vspace{-0.5em}' + '\n'
                r'\end{figure}')
    # fbox placeholder — matches template exactly
    return (r'\noindent\fbox{\parbox{0.97\textwidth}{' + '\n'
            r'\textit{[ PLACEHOLDER: ' + caption + r' ]}' + '\n'
            r'}}' + '\n\\par\\medskip')


