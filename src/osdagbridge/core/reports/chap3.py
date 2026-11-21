# =============================================================================
# Chapter 3: Loads and Load Combinations
# Extracted from report_generator.py — DO NOT add business logic here.
# =============================================================================

from osdagbridge.core.reports.styles import longtable_head, fail_text, pass_text, table_note
from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_FOOTPATH,
    KEY_LL_ECCENTRICITY,
    KEY_CB_LOAD,
    KEY_LL_CUSTOM_VEHICLES,
    KEY_LL_FOOTPATH_PRESSURE_MODE,
    KEY_LL_FOOTPATH_PRESSURE_VALUE,
    KEY_LL_IRC_70R_BOGIE,
    KEY_LL_IRC_70R_TRACKED,
    KEY_LL_IRC_70R_WHEELED,
    KEY_LL_IRC_AA_TRACKED,
    KEY_LL_IRC_AA_WHEELED,
    KEY_LL_IRC_CLASS_A,
    KEY_LL_IRC_CLASS_FATIGUE,
    KEY_LL_IRC_CLASS_SV,
    KEY_MATERIAL_DECK_DENSITY,
    KEY_MATERIAL_GIRDER_DENSITY,
    KEY_PL_SELF_WEIGHT_FACTOR,
    KEY_RL_LOAD_VALUE,
    KEY_SL_DAMPING,
    KEY_SL_DEAD_LOAD_MODE,
    KEY_SL_DEAD_LOAD_VALUE,
    KEY_SL_HORIZONTAL_COEFF,
    KEY_SL_IMPORTANCE_FACTOR,
    KEY_SL_LIVE_LOAD_MODE,
    KEY_SL_LIVE_LOAD_VALUE,
    KEY_SL_SEISMIC_ZONE,
    KEY_SL_SOIL_TYPE,
    KEY_SL_SPECTRAL_COEFF,
    KEY_SL_TIME_PERIOD,
    KEY_SL_VERTICAL_COEFF,
    KEY_SL_ZONE_FACTOR,
    KEY_SPAN,
    KEY_TL_BRIDGE_TEMP_MAX,
    KEY_TL_BRIDGE_TEMP_MIN,
    KEY_TL_HIGHEST_MAX_TEMP,
    KEY_TL_LOWEST_MIN_TEMP,
    KEY_TL_TEMP_FALL,
    KEY_TL_TEMP_RISE,
    KEY_WC_LD_LANE_TABLE_COUNT,
    KEY_WC_MATERIAL,
    KEY_WC_THICKNESS,
    KEY_WL_AVG_EXPOSED_HEIGHT,
    KEY_WL_BASIC_WIND_SPEED,
    KEY_WL_HOURLY_MEAN_WIND,
    KEY_WL_HOURLY_WIND_PRESSURE,
    KEY_WL_LONGITUDINAL_WIND_FORCE,
    KEY_WL_TERRAIN_TYPE,
    KEY_WL_TRANSVERSE_WIND_FORCE,
    KEY_WL_VERTICAL_WIND_FORCE
)

from osdagbridge.core.reports.report_utils import _tex, _render_value


# -----------------------------------------------------------------------------
# Live-load tables (vehicular and footpath are separate tables)
# -----------------------------------------------------------------------------
_VEHICLE_REF = {
    "Class A": "IRC 6 Cl. 204.1",
    "Class 70R (Wheeled)": "IRC 6 Cl. 204.1",
    "Class 70R (Tracked)": "IRC 6 Cl. 204.1",
    "Class 70R (Bogie)": "IRC 6 Cl. 204.1",
    "Class AA (Wheeled)": "IRC 6 Cl. 204.1",
    "Class AA (Tracked)": "IRC 6 Cl. 204.1",
    "Class SV": "IRC 6 Cl. 204.5",
    "Class Fatigue": "IRC 6 Cl. 204.6",
}
_NA = "---"


def _impact_for(name, impact_a, impact_aa):
    """Impact factor (1+IM) for one vehicle class; '---' when not applicable."""
    if name == "Class A":
        val = impact_a
    elif name.startswith(("Class 70R", "Class AA")):
        val = impact_aa
    else:
        val = None
    return f"{val:.3f}" if val is not None else _NA


def _footpath_pressure(input_dict):
    """Footpath live-load intensity in kN/m^2 (float) or None."""
    from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017
    mode = str(input_dict.get(KEY_LL_FOOTPATH_PRESSURE_MODE, "")).strip().lower()
    value = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_VALUE, "")
    try:
        if mode in ("as per irc 6", "as per irc6", "automatic"):
            return float(IRC6_2017.cl_206_1_footway_load())
        if value not in (None, ""):
            return float(value)
    except Exception:
        pass
    return None


def live_load_tables(input_dict, vehicles, impact_a, impact_aa, lanes, braking_t):
    """Return LaTeX for the vehicular and footpath live-load tables."""
    # ---- Table: vehicle classes selected in Additional Inputs -> Loading ----
    veh_rows = []
    for i, name in enumerate(vehicles, start=1):
        ref = _VEHICLE_REF.get(name, "User defined")
        veh_rows.append(rf"{i} & {_tex(name)} & {_tex(ref)} & {_impact_for(name, impact_a, impact_aa)} \\[6pt]" + "\n\\hline")
    if not veh_rows:
        veh_rows.append(r"--- & No vehicle class selected & --- & --- \\[6pt]" + "\n\\hline")
    t_veh = (longtable_head(
        r"|C{1.2cm}|L{5.4cm}|C{4.0cm}|C{4.0cm}|",
        r"\textbf{Live Loads -- Vehicular (IRC 6)}",
        r"\textbf{S.N.} & \textbf{Vehicle Class} & \textbf{Reference} & \textbf{Impact Factor (1+IM)}")
        + "\n".join(veh_rows) + "\n\\end{longtable}\n"
        + table_note(r"Vehicle classes are those selected in Additional Inputs $\rightarrow$ Loading. "
                     r"Impact factors per IRC 6 Cl. 208.2 (Class A) and Cl. 208.3 (Class 70R / AA)."))

    # ---- Table: parameters common to vehicular loading, with unit column ----
    lanes_txt = str(int(lanes)) if lanes not in (None, "") else _NA
    if braking_t is not None:
        braking_kn, braking_tn = f"{braking_t * 9.81:.2f}", f"{braking_t:.2f}"
    else:
        braking_kn = braking_tn = _NA
    ecc = input_dict.get(KEY_LL_ECCENTRICITY)
    ecc_txt = _render_value(input_dict, KEY_LL_ECCENTRICITY) if ecc not in (None, "") else _NA
    par_rows = [
        ("Number of design lanes", lanes_txt, "--", "IRC 6 Table 6"),
        ("Braking force", braking_kn, "kN", "IRC 6 Cl. 211.2"),
        ("Braking force (equivalent)", braking_tn, "tonne", "IRC 6 Cl. 211.2"),
        ("Centrifugal force", "Not considered", "--", "IRC 6 Cl. 212 (straight alignment)"),
        ("Eccentricity of live load", ecc_txt, "m", "---"),
    ]
    body = "\n".join(
        rf"\textnormal{{{p}}} & {v} & {u} & {_tex(r)} \\[6pt]" + "\n\\hline" for p, v, u, r in par_rows)
    t_par = (longtable_head(
        r"|L{5.0cm}|C{3.4cm}|C{2.0cm}|L{5.0cm}|",
        r"\textbf{Live Loads -- Associated Vehicular Parameters}",
        r"\textbf{Parameter} & \textbf{Value} & \textbf{Unit} & \textbf{Reference}")
        + body + "\n\\end{longtable}\n"
        + table_note("Centrifugal force applies to bridges on a curve; no curvature is defined in the model."))

    # ---- Table: footpath live load ----
    fp_mode = input_dict.get(KEY_FOOTPATH)
    has_fp = str(fp_mode).strip().lower() not in ("", "none")
    pressure = _footpath_pressure(input_dict)
    if has_fp:
        fp_rows = [
            ("Footpath provision", _tex(str(fp_mode)), "--", "---"),
            ("Footpath live load intensity",
             f"{pressure:.3f}" if pressure is not None else _NA, "kN/m\\textsuperscript{2}", "IRC 6 Cl. 206.1"),
        ]
    else:
        fp_rows = [("Footpath provision", "None", "--", "---"),
                   ("Footpath live load intensity", "Not applicable", "--", "IRC 6 Cl. 206.1")]
    body = "\n".join(
        rf"\textnormal{{{p}}} & {v} & {u} & {_tex(r)} \\[6pt]" + "\n\\hline" for p, v, u, r in fp_rows)
    t_fp = (longtable_head(
        r"|L{5.0cm}|C{3.4cm}|C{2.0cm}|L{5.0cm}|",
        r"\textbf{Live Loads -- Footpath}",
        r"\textbf{Parameter} & \textbf{Value} & \textbf{Unit} & \textbf{Reference}")
        + body + "\n\\end{longtable}\n")
    return t_veh + "\n\\vspace{1em}\n" + t_par + "\n\\vspace{1em}\n" + t_fp


def ch3_loads(input_dict):
    # Live load vehicle names mapping
    vehicles = []
    if input_dict.get(KEY_LL_IRC_CLASS_A):
        vehicles.append("Class A")
    if input_dict.get(KEY_LL_IRC_70R_WHEELED):
        vehicles.append("Class 70R (Wheeled)")
    if input_dict.get(KEY_LL_IRC_70R_TRACKED):
        vehicles.append("Class 70R (Tracked)")
    if input_dict.get(KEY_LL_IRC_AA_WHEELED):
        vehicles.append("Class AA (Wheeled)")
    if input_dict.get(KEY_LL_IRC_AA_TRACKED):
        vehicles.append("Class AA (Tracked)")
    if input_dict.get(KEY_LL_IRC_CLASS_SV):
        vehicles.append("Class SV")
    if input_dict.get(KEY_LL_IRC_70R_BOGIE):
        vehicles.append("Class 70R (Bogie)")
    if input_dict.get(KEY_LL_IRC_CLASS_FATIGUE):
        vehicles.append("Class Fatigue")
    
    custom = input_dict.get(KEY_LL_CUSTOM_VEHICLES)
    if custom and isinstance(custom, list):
        for c in custom:
            if isinstance(c, dict) and c.get('name'):
                vehicles.append(c['name'])
            elif isinstance(c, str):
                vehicles.append(c)
                
    vehicles_str = ", ".join(vehicles) if vehicles else "None"

    from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017
    span = input_dict.get(KEY_SPAN)
    impact_factor_str = ""
    impact_a = impact_aa = None
    if span not in (None, ""):
        try:
            span_m = float(span)
            factors = []
            if input_dict.get(KEY_LL_IRC_CLASS_A):
                im_a = IRC6_2017.cl_208_2_impact_factor(span_m)
                factors.append(f"Class A: {1.0 + im_a:.3f}")
                impact_a = 1.0 + im_a
            is_wheeled_heavy = (
                input_dict.get(KEY_LL_IRC_70R_WHEELED) or 
                input_dict.get(KEY_LL_IRC_AA_WHEELED) or 
                input_dict.get(KEY_LL_IRC_70R_BOGIE)
            )
            is_tracked_heavy = (
                input_dict.get(KEY_LL_IRC_70R_TRACKED) or 
                input_dict.get(KEY_LL_IRC_AA_TRACKED)
            )
            if is_wheeled_heavy or is_tracked_heavy:
                im_aa = IRC6_2017.cl_208_3_impact_factor(span_m)
                factors.append(f"Class AA/70R: {1.0 + im_aa:.3f}")
                impact_aa = 1.0 + im_aa
            
            if factors:
                impact_factor_str = ", ".join(factors)
            else:
                impact_factor_str = "N/A"
        except Exception:
            impact_factor_str = "N/A"
    else:
        impact_factor_str = "N/A"

    lanes = None
    try:
        lanes = IRC6_2017.table_6(float(input_dict.get(KEY_CARRIAGEWAY_WIDTH)))
    except Exception:
        lanes = input_dict.get(KEY_WC_LD_LANE_TABLE_COUNT)
    braking_force_str = ""
    braking_force_t = None
    if lanes not in (None, ""):
        try:
            lanes_int = int(lanes)
            # cl_211_2_braking_force() works from wheel loads in N, so it returns Newtons.
            braking_force_N = IRC6_2017.cl_211_2_braking_force(lanes_int)
            braking_force_kN = braking_force_N / 1000.0
            braking_force_t = braking_force_kN / 9.81   # tonne-force, for display
            braking_force_str = f"{braking_force_kN:.2f} kN ({braking_force_t:.2f} tonnes)"
        except Exception:
            braking_force_str = "N/A"
    else:
        braking_force_str = "N/A"

    fp_mode  = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_MODE, "")
    fp_value = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_VALUE, "")
    if str(fp_mode).strip().lower() in ("as per irc 6", "as per irc6", "automatic"):
        try:
            fp_str = f"{IRC6_2017.cl_206_1_footway_load():.3f} kN/m² (IRC 6 Cl. 206.1)"
        except Exception:
            fp_str = "N/A"
    elif fp_value not in (None, ""):
        fp_str = f"{fp_value} kN/m²"
    else:
        fp_str = "N/A"

    # Vz / Pz — prefer stored computed values; fall back to IRC6 Table 12
    vz_val = input_dict.get(KEY_WL_HOURLY_MEAN_WIND)
    pz_val = input_dict.get(KEY_WL_HOURLY_WIND_PRESSURE)
    if not vz_val or not pz_val:
        try:
            _vb  = input_dict.get(KEY_WL_BASIC_WIND_SPEED) or input_dict.get('wind_speed')
            _h   = input_dict.get(KEY_WL_AVG_EXPOSED_HEIGHT)
            _ter = {
                "Plain Terrain": "plain",
                "Terrain with Obstructions": "obstructed",
            }.get(str(input_dict.get(KEY_WL_TERRAIN_TYPE, "")).strip(), "plain")
            _res = IRC6_2017.table_12(float(_h), _ter, float(_vb))
            if not vz_val:
                vz_val = _res.get("Vz")
            if not pz_val:
                pz_val = _res.get("Pz")
        except Exception:
            pass
    vz_str = f"{float(vz_val):.2f} m/s" if vz_val not in (None, "") else "N/A"
    pz_str = f"{float(pz_val):.2f} N/m²" if pz_val not in (None, "") else "N/A"

    # Table 3.5 — Seismic: prefer stored computed values; fall back to IRC6 cl_218_5_1
    sl_zone_factor = input_dict.get(KEY_SL_ZONE_FACTOR)
    sl_spectral    = input_dict.get(KEY_SL_SPECTRAL_COEFF)
    sl_ah          = input_dict.get(KEY_SL_HORIZONTAL_COEFF)
    sl_av          = input_dict.get(KEY_SL_VERTICAL_COEFF)
    if not sl_ah or not sl_zone_factor:
        try:
            _zone = input_dict.get(KEY_SL_SEISMIC_ZONE) or input_dict.get('seismic_zone')
            _zmap = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
            _z    = str(_zone).strip().upper()
            if _z.isdigit():
                _z = _zmap.get(_z)
            _smap = {"Type I – Rocky or Hard": 1, "Type II – Medium Soil": 2, "Type III – Soft Soil": 3}
            _st   = _smap.get(str(input_dict.get(KEY_SL_SOIL_TYPE, "")), 1)
            _tp   = input_dict.get(KEY_SL_TIME_PERIOD)
            _damp = input_dict.get(KEY_SL_DAMPING) or "5"
            _dl_v = input_dict.get(KEY_SL_DEAD_LOAD_VALUE)
            _ll_v = input_dict.get(KEY_SL_LIVE_LOAD_VALUE)
            _dead = float(_dl_v) if str(input_dict.get(KEY_SL_DEAD_LOAD_MODE, "")) == "Custom" and _dl_v else 0.0
            _live = float(_ll_v) if str(input_dict.get(KEY_SL_LIVE_LOAD_MODE, "")) == "Custom" and _ll_v else 0.0
            _res  = IRC6_2017.cl_218_5_1(zone=f"Zone {_z}", soil_type=_st, dead_load_kN=_dead,
                        live_load_kN=_live, period_T=float(_tp) if _tp else None,
                        damping_percent=float(_damp))
            if not sl_zone_factor:
                sl_zone_factor = _res.get("Z")
            if not sl_spectral:
                sl_spectral    = _res.get("Sa_g_adjusted")
            if not sl_ah:
                sl_ah          = _res.get("Ah")
            if not sl_av:
                sl_av          = round(_res.get("Ah", 0) * 2 / 3, 4)
        except Exception:
            pass

    def _sl(v, unit=""):
        return f"{float(v):.4f}{unit}" if v not in (None, "") else "N/A"

    # Table 3.6 — Temperature: compute effective bridge temp range from shade temps
    tl_temp_min = tl_temp_max = tl_rise = tl_fall = "N/A"
    try:
        _tmax = input_dict.get(KEY_TL_HIGHEST_MAX_TEMP) or input_dict.get('shade_temp_max')
        _tmin = input_dict.get(KEY_TL_LOWEST_MIN_TEMP)  or input_dict.get('shade_temp_min')
        if _tmax and _tmin:
            _res    = IRC6_2017.cl_215_2_effective_bridge_temperature(
                          float(_tmax), float(_tmin), 'metallic', False)
            _bt_min = _res.get('T_min', 0)
            _bt_max = _res.get('T_max', 0)
            _mean   = (_bt_max + _bt_min) / 2.0
            tl_temp_min = f"{_bt_min:.2f}"
            tl_temp_max = f"{_bt_max:.2f}"
            tl_rise     = f"{_bt_max - _mean:.2f}"
            tl_fall     = f"{_mean - _bt_min:.2f}"
    except Exception:
        pass

    # --- Table 3.7: Load Combinations (dynamically generated from IRC 6) ---
    _LOAD_LABEL_MAP = {
        'dead_load':         'DL',
        'surfacing':         'SIDL',
        'live_load':         'LL',
        'wind_load':         'WL',
        'thermal_load':      'TL',
        'vehicle_collision': 'VC',
        'barge_impact':      'BI',
        'floating_bodies':   'FB',
        'seismic':           'EQ',
    }

    def _fmt_factors(factors):
        """Format a factors dict into a compact load-case string for the table."""
        parts = []
        for load, val in factors.items():
            label = _LOAD_LABEL_MAP.get(load, load.upper())
            if isinstance(val, dict):  # permanent load with adding/relieving
                add = val.get('adding')
                rel = val.get('relieving')
                add_s = f"{add:.2f}" if add is not None else '--'
                rel_s = f"{rel:.2f}" if rel is not None else '--'
                parts.append(f"{label}({add_s}/{rel_s})")
            else:
                if val is None:
                    continue  # skip N/A factors
                parts.append(f"{label}({val:.2f})")
        return ' + '.join(parts)

    uls_combos = IRC6_2017.uls_load_combinations()
    sls_combos = IRC6_2017.sls_load_combinations()
    lc_rows = []
    for i, combo in enumerate(uls_combos, start=1):
        cases = _fmt_factors(combo['factors'])
        lc_rows.append(
            f"ULS-{i:02d}" + r" & " + cases + r" \\[6pt]" + "\n"
            + r"\hline"
        )
    for i, combo in enumerate(sls_combos, start=1):
        cases = _fmt_factors(combo['factors'])
        lc_rows.append(
            f"SLS-{i:02d}" + r" & " + cases + r" \\[6pt]" + "\n"
            + r"\hline"
        )

    lc_rows_str = "\n".join(lc_rows)

    return r"""
\chapter{Loads and Load Combinations}

This section summarizes all loads applied to the bridge and the load combinations considered for analysis and design.

\vspace{1em}
""" + longtable_head(r"""|L{5.5cm}|p{10.0cm}|""", r"""\textbf{Dead Load -- Self Weight}""", r"""\textbf{Parameter} & \textbf{Value} \\""") + r"""
\textnormal{Steel Self-Weight Applied} & """ + (_render_value(input_dict, KEY_MATERIAL_GIRDER_DENSITY, ' kN/m\\textsuperscript{3}')) + r""" \\[6pt]
\hline
\textnormal{Concrete Deck Weight} & """ + (_render_value(input_dict, KEY_MATERIAL_DECK_DENSITY, ' kN/m\\textsuperscript{3}')) + r""" \\[6pt]
\hline
\textnormal{Self-Weight Factor} & """ + (_render_value(input_dict, KEY_PL_SELF_WEIGHT_FACTOR)) + r""" \\[6pt]
\hline
\end{longtable}

\vspace{1em}
""" + longtable_head(r"""|L{5.5cm}|p{10.0cm}|""", r"""\textbf{Dead Load for Surfacing (DW)}""", r"""\textbf{Parameter} & \textbf{Value} \\""") + r"""
\textnormal{Wearing Course Load} & """ + (_render_value(input_dict, KEY_WC_MATERIAL)) + r""" x """ + (_render_value(input_dict, KEY_WC_THICKNESS)) + r""" \\[6pt]
\hline
\textnormal{Additional SIDL (Crash Barrier)} & """ + (_render_value(input_dict, KEY_CB_LOAD)) + r""" kN/m per barrier \\[6pt]
\hline
\textnormal{Railing Load} & """ + (_render_value(input_dict, KEY_RL_LOAD_VALUE)) + r""" kN/m\sdstar{} \\[6pt]
\hline
\end{longtable}

\vspace{1em}
""" + live_load_tables(input_dict, vehicles, impact_a, impact_aa, lanes, braking_force_t) + r"""
\vspace{1em}
""" + longtable_head(r"""|L{5.5cm}|p{10.0cm}|""", r"""\textbf{Wind Load (WL) --- per IRC 6}""", r"""\textbf{Parameter} & \textbf{Value} \\""") + r"""
\textnormal{Basic Wind Speed, Vb} & """ + (_render_value(input_dict,'wind_speed', ' m/s')) + r""" [from Project Location] \\[6pt]
\hline
\textnormal{Terrain Type} & """ + (_render_value(input_dict, KEY_WL_TERRAIN_TYPE)) + r""" \\[6pt]
\hline
\textnormal{Average Exposed Height, H (m)} & """ + (_render_value(input_dict, KEY_WL_AVG_EXPOSED_HEIGHT, ' m')) + r""" \\[6pt]
\hline
\textnormal{Hourly Mean Wind Speed, Vz} & """ + (_render_value(input_dict, KEY_WL_HOURLY_MEAN_WIND, ' m/s')) + r""" \\[6pt]
\hline
\textnormal{Hourly Wind Pressure, Pz} & """ + (_render_value(input_dict, KEY_WL_HOURLY_WIND_PRESSURE, ' N/m\\textsuperscript{2}')) + r""" \\[6pt]
\hline
\textnormal{Transverse Wind Force} & """ + (_render_value(input_dict, KEY_WL_TRANSVERSE_WIND_FORCE, ' kN')) + r""" \\[6pt]
\hline
\textnormal{Longitudinal Wind Force} & """ + (_render_value(input_dict, KEY_WL_LONGITUDINAL_WIND_FORCE, ' kN')) + r""" \\[6pt]
\hline
\textnormal{Vertical Wind Force} & """ + (_render_value(input_dict, KEY_WL_VERTICAL_WIND_FORCE, ' kN')) + r""" \\[6pt]
\hline
\end{longtable}

\vspace{1em}
""" + longtable_head(r"""|L{5.5cm}|p{10.0cm}|""", r"""\textbf{Earthquake Load (EL) --- per IRC 6}""", r"""\textbf{Parameter} & \textbf{Value} \\""") + r"""
\textnormal{Seismic Zone} & """ + (_render_value(input_dict,'seismic_zone')) + r""" [from Project Location] \\[6pt]
\hline
\textnormal{Zone Factor, Z} & """ + (_render_value(input_dict, KEY_SL_ZONE_FACTOR)) + r""" \\[6pt]
\hline
\textnormal{Importance Factor, I} & """ + (_render_value(input_dict, KEY_SL_IMPORTANCE_FACTOR)) + r""" \\[6pt]
\hline
\textnormal{Type of Soil} & """ + (_render_value(input_dict, KEY_SL_SOIL_TYPE)) + r""" \\[6pt]
\hline
\textnormal{Sa/g} & """ + (_render_value(input_dict, KEY_SL_SPECTRAL_COEFF)) + r""" \\[6pt]
\hline
\textnormal{Horizontal Seismic Coefficient, Ah} & """ + (_render_value(input_dict, KEY_SL_HORIZONTAL_COEFF)) + r""" \\[6pt]
\hline
\textnormal{Vertical Seismic Coefficient, Av} & """ + (_render_value(input_dict, KEY_SL_VERTICAL_COEFF)) + r""" \\[6pt]
\hline
\textnormal{Horizontal Seismic Force (longitudinal)} & --- \\[6pt]
\hline
\textnormal{Horizontal Seismic Force (transverse)} & --- \\[6pt]
\hline
\end{longtable}

\vspace{1em}
""" + longtable_head(r"""|L{5.5cm}|p{10.0cm}|""", r"""\textbf{Temperature Load (TL) --- per IRC 6}""", r"""\textbf{Parameter} & \textbf{Value} \\""") + r"""
\textnormal{Maximum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_max')) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Minimum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_min')) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Effective Bridge Temp. Range} & """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MIN)) + r""" to """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MAX)) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Temperature Rise / Fall for Design} & +""" + (_render_value(input_dict, KEY_TL_TEMP_RISE)) + r""" $^\circ$C / \textminus{}""" + (_render_value(input_dict, KEY_TL_TEMP_FALL)) + r""" $^\circ$C \\[6pt]
\hline
\end{longtable}

\vspace{1em}
""" + longtable_head(r"""|C{4.0cm}|p{11.5cm}|""", r"""\textbf{Load Combinations}""", r"""\textbf{Combination ID} & \textbf{Load Cases} \\[6pt]""") + r"""
""" + lc_rows_str + r"""
\end{longtable}

\noindent\textit{Note: All IRC 6 load combinations are auto-generated by OsdagBridge. User-defined custom combinations, if any, are appended.}
"""


