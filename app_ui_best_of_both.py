# spud-SRI · Best-of-Both UI (V2.1)
"""
Merged Streamlit interface that keeps ALL functionality from app_ui_v2.py
and replaces the soil-profile section with the improved table/paste/upload
workflow from improved_soil_input_ui.py — including the visual preview.

- Preserves: min Su vs B/2 avg, 5° phi reduction, windward 0.8, squeeze trigger
- Preserves: Advanced Nc' (β, α) from SNAME Tables C6.1–C6.6
- Adds: Modern soil input (interactive table, paste, CSV) with preview
- Adds: Safer imports across lpa_v50_v3 / v4 and helpful validations

Run:
    streamlit run app_ui_best_of_both.py
"""

import io
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ---- Engine/library imports with compatibility fallbacks ----
# Geometry & computation API
try:
    from lpa_v50_v3 import (
        Spudcan, SoilPoint, SoilLayer,
        compute_envelopes, penetration_results,
        USE_MIN_CU_POINT_AVG_DEFAULT, APPLY_PHI_REDUCTION_DEFAULT,
        APPLY_WINDWARD_FACTOR_DEFAULT, APPLY_SQUEEZE_TRIGGER_DEFAULT,
    )
    _LIB_VER = "v50_v3"
except Exception:
    # Fallback to v4 names if that's what the project uses
    from lpa_v50_v4 import (
        Spudcan, SoilPoint, SoilLayer,
        compute_envelopes, penetration_results,
        USE_MIN_CU_POINT_AVG_DEFAULT, APPLY_PHI_REDUCTION_DEFAULT,
        APPLY_WINDWARD_FACTOR_DEFAULT, APPLY_SQUEEZE_TRIGGER_DEFAULT,
    )
    _LIB_VER = "v50_v4"

# Soil input UI (modern table/paste/upload + preview)
try:
    from improved_soil_input_ui import create_soil_input_table, plot_soil_profile_preview
    _SOIL_UI = "external"
except Exception:
    # Minimal emergency fallback (shouldn't be needed in user project)
    _SOIL_UI = "fallback"
    def create_soil_input_table():
        st.warning("Improved soil UI module not found; using a minimal fallback.")
        if "layers" not in st.session_state:
            st.session_state.layers = []
        if st.button("➕ Add demo clay layer"):
            st.session_state.layers.append(
                SoilLayer(
                    name=f"Layer {len(st.session_state.layers)+1}",
                    z_top=0.0, z_bot=5.0, soil_type="clay",
                    gamma=[SoilPoint(0, 8.0), SoilPoint(5, 8.5)],
                    su=[SoilPoint(0, 20.0), SoilPoint(5, 40.0)],
                    phi=[]
                )
            )
        return st.session_state.layers

    def plot_soil_profile_preview(layers):
        if not layers:
            st.info("No layers to preview.")
            return
        depths = []
        suvals = []
        for L in layers:
            if L.soil_type in ("clay", "silt") and L.su:
                d = np.linspace(L.z_top, L.z_bot, 10)
                su_top = L.su[0].v
                su_bot = L.su[-1].v
                su = su_top + (su_bot - su_top) * (d - L.z_top) / (L.z_bot - L.z_top)
                depths.append(d)
                suvals.append(su)
        fig, ax = plt.subplots(figsize=(4,6), dpi=140)
        for d, su in zip(depths, suvals):
            ax.plot(su, d, lw=2)
        ax.set_xlabel("Su (kPa)")
        ax.set_ylabel("Depth (m)")
        ax.invert_yaxis()
        ax.grid(alpha=0.3, linestyle=":")
        st.pyplot(fig)


st.set_page_config(
    page_title="spud-SRI · Best-of-Both UI (V2.1)",
    page_icon="💎",
    layout="wide",
)

st.title("spud-SRI · Leg Penetration (SNAME) · Best-of-Both UI (V2.1)")
st.caption("Keeps all advanced switches + advanced Nc′, with a better soil input experience.")
st.caption(f"Engine library: {_LIB_VER} · Soil UI: {_SOIL_UI}")

# ===============================
# Sidebar — Analysis switches
# ===============================
with st.sidebar:
    st.subheader("Analysis switches")
    use_min_cu = st.checkbox(
        "Use min(Su point, Su B/2 avg)", 
        value=True if 'USE_MIN_CU_POINT_AVG_DEFAULT' not in globals() else USE_MIN_CU_POINT_AVG_DEFAULT,
        help="Conservative default for undrained strength (controls idle clay)."
    )
    phi_reduce = st.checkbox(
        "Apply 5° reduction to ϕ′", 
        value=True if 'APPLY_PHI_REDUCTION_DEFAULT' not in globals() else APPLY_PHI_REDUCTION_DEFAULT,
        help="Optional conservatism for sands (idle sand)."
    )
    windward80 = st.checkbox(
        "Windward factor 0.8 on REAL", 
        value=True if 'APPLY_WINDWARD_FACTOR_DEFAULT' not in globals() else APPLY_WINDWARD_FACTOR_DEFAULT,
        help="Applies 0.8 to the governing REAL capacity only."
    )
    squeeze_trig = st.checkbox(
        "Enforce squeezing geometric trigger", 
        value=True if 'APPLY_SQUEEZE_TRIGGER_DEFAULT' not in globals() else APPLY_SQUEEZE_TRIGGER_DEFAULT,
        help="Applies geometric screening consistent with squeezing onset."
    )

    st.divider()
    st.subheader("Analysis parameters")
    dz = st.number_input("Depth step Δz (m)", value=0.25, min_value=0.05, max_value=2.0, step=0.05)
    dmax = st.number_input("Max analysis depth (m)", value=30.0, min_value=5.0, max_value=200.0, step=1.0)

# ===============================
# Spudcan inputs
# ===============================
st.markdown("### 1) Spudcan inputs")
cols = st.columns(5)
rig = cols[0].text_input("Rig name", "Rig-1")
B   = cols[1].number_input("Diameter B (m)", value=8.0, min_value=0.1, step=0.1)
A_default = float(np.pi*(B**2)/4.0)
A   = cols[2].number_input("Area A (m²)", value=A_default, min_value=0.01, step=0.1,
                           help="Projected area of widest section. Defaults to πB²/4.")
tip = cols[3].number_input("Tip offset to widest (m)", value=1.5, min_value=0.0, step=0.1,
                           help="Zero load until this penetration is reached (tip-to-widest offset).")
Pmn = cols[4].number_input("Preload per leg (MN)", value=80.0, min_value=1.0, step=1.0)

# ===============================
# Advanced Nc′ parameters
# ===============================
st.markdown("#### Advanced Nc′ (optional)")
with st.expander("Configure advanced bearing capacity factors (SNAME Tables C6.1–C6.6)", expanded=False):
    st.markdown("""
Use this to get more accurate bearing capacity in normally consolidated clays.

- **β (Beta)**: Spudcan equivalent cone angle
- **α (Alpha)**: Surface roughness factor (0.0 = smooth, 1.0 = rough)

App will auto-compute embedment ratio and strength gradient from your Su profile.
Leave disabled to use **Nc = 5.14**.
    """.strip())
    use_advanced_nc = st.checkbox("Enable advanced Nc′ calculation", value=False)
    if use_advanced_nc:
        c1, c2 = st.columns(2)
        with c1:
            beta_deg = st.selectbox(
                "Cone angle β (degrees)",
                options=[30, 60, 90, 120, 150, 180],
                index=2,  # default 90°
                help="Flat=180°, typical=90–120°, sharp=30–60°"
            )
        with c2:
            alpha = st.slider(
                "Roughness α", 0.0, 1.0, 0.4, 0.1,
                help="0.0=smooth, 1.0=rough (typical double-cone ≈ 0.4)"
            )
    else:
        beta_deg = None
        alpha = None

spud = Spudcan(rig_name=rig, B=B, A=A, tip_elev=tip, preload_MN=Pmn,
               beta=beta_deg, alpha=alpha)

# ===============================
# Soil profile (improved UI)
# ===============================
st.markdown("### 2) Soil profile (improved)")
layers = create_soil_input_table()
if layers:
    plot_soil_profile_preview(layers)

# Inline basic validations to catch common mistakes early
def _basic_layer_checks(layers):
    msgs = []
    for i, L in enumerate(layers, start=1):
        if L.z_bot <= L.z_top:
            msgs.append(f"Layer {i} ('{getattr(L, 'name', '?')}') has z_bot ≤ z_top.")
        if L.soil_type == "sand" and not L.phi:
            msgs.append(f"Layer {i} ('{getattr(L, 'name', '?')}') is sand but has no φ profile.")
        if L.soil_type in ("clay","silt") and not L.su:
            msgs.append(f"Layer {i} ('{getattr(L, 'name', '?')}') is fine-grained but has no Su profile.")
    return msgs

if layers:
    problems = _basic_layer_checks(layers)
    if problems:
        st.error("Please fix the following issues before running:")
        for p in problems:
            st.write("• ", p)

st.divider()

# ===============================
# Run analysis
# ===============================
c_run, c_info = st.columns([1, 3])
do_run = c_run.button("▶ Run analysis", type="primary", disabled=not layers or bool(_basic_layer_checks(layers)))
if c_info.button("Show what will be applied"):
    st.info(
        f"Settings:\n"
        f"- min Su vs B/2 avg: {'ON' if use_min_cu else 'OFF'}\n"
        f"- φ reduction (5°): {'ON' if phi_reduce else 'OFF'}\n"
        f"- Windward 0.8 on REAL: {'ON' if windward80 else 'OFF'}\n"
        f"- Squeezing trigger: {'ON' if squeeze_trig else 'OFF'}\n"
        f"- Advanced Nc′: {'ON' if use_advanced_nc else 'OFF'}"
    )

if do_run:
    # Compute envelopes
    try:
        df = compute_envelopes(
            spud=spud,
            layers=layers,
            max_depth=dmax,
            dz=dz,
            use_min_cu=use_min_cu,
            phi_reduction=phi_reduce,
            windward_factor=windward80,
            squeeze_trigger=squeeze_trig,
            meyerhof_table=None,
        )
    except Exception as e:
        st.exception(e)
        st.stop()

    # Penetration results
    try:
        pen = penetration_results(spud, df)
    except Exception as e:
        st.exception(e)
        st.stop()

    # --- Results summary ---
    with st.container():
        st.subheader("Results")
        cols = st.columns(3)
        cols[0].metric("Preload per leg", f"{spud.preload_MN:.2f} MN")
        
        tip_min = pen.get("tip_range_min", None)
        tip_max = pen.get("tip_range_max", None)
        if tip_min is not None and tip_max is not None and tip_min != tip_max:
            cols[1].metric("Tip penetration range", f"{tip_min:.2f} – {tip_max:.2f} m")
        elif tip_min is not None:
            cols[1].metric("Tip penetration", f"{tip_min:.2f} m")
        else:
            cols[1].metric("Tip penetration", "—")
        
        if use_advanced_nc:
            cols[2].metric("Nc′ method", f"β={beta_deg}°, α={alpha:.1f}")
        else:
            cols[2].metric("Nc′ method", "Default (5.14)")

    # --- Upgrade notes ---
    if use_advanced_nc:
        st.info("🎯 **Upgrades Active:** Zero-load until tip offset + Advanced Nc′ from SNAME tables")
    else:
        st.info("✅ **Upgrade Active:** Zero-load until tip offset (enable Advanced Nc′ above to use SNAME tables)")

    # --- Chart ---
    fig, ax = plt.subplots(figsize=(4.6, 6.6), dpi=200)
    if "idle_clay_MN" in df.columns:
        ax.plot(df["idle_clay_MN"], df["depth"], lw=0.9, ls="-", color="0.6", label="Idle Clay")
    if "idle_sand_MN" in df.columns:
        ax.plot(df["idle_sand_MN"], df["depth"], lw=0.9, ls="--", color="0.6", label="Idle Sand")
    ax.plot(df["real_MN"], df["depth"], lw=1.8, color="#0033cc", label="REAL (governing)")
    ax.axvline(spud.preload_MN, ymin=0, ymax=1, color="red", lw=1.2, ls="--", label="Preload")

    if getattr(spud, "tip_elev", 0) and spud.tip_elev > 0:
        ax.axhline(spud.tip_elev, xmin=0, xmax=1, color="orange", lw=1.0, ls=":",
                   label=f"Tip offset ({spud.tip_elev:.2f} m)")

    ax.set_xlabel("Leg load (MN)")
    ax.set_ylabel("Penetration of widest section (m)")
    ax.invert_yaxis()
    ax.grid(True, ls=":", lw=0.6, color="0.7")
    ax.set_xlim(left=0)
    ax.legend(loc="upper right", fontsize=7, frameon=True)
    st.pyplot(fig, clear_figure=True)

    # --- Table & download ---
    st.subheader("Detailed table")
    st.dataframe(df, use_container_width=True, height=360)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name=f"{spud.rig_name}_best_of_both_results.csv", mime="text/csv")

    # --- Summary note ---
    st.caption(
        "Notes: Capacity is zero until penetration reaches tip offset. "
        "REAL equals the minimum of valid candidates (clay/sand) after special-mode reductions. "
        "When Advanced Nc′ is enabled, bearing factors are interpolated from SNAME Tables C6.1–C6.6 "
        "based on spudcan geometry and auto-computed embedment/strength-gradient parameters."
    )
