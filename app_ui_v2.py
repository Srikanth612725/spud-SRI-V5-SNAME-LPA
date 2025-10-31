"""
app_ui_v2.py - Spud-SRI Version 2
==================================

Enhanced Streamlit interface with two major upgrades:

UPGRADE 1: Zero load until tip penetration
- The penetration curve correctly starts at zero load until the widest
  section of the spudcan enters the soil.

UPGRADE 2: Advanced Nc' calculation from SNAME Tables C6.1-C6.6
- New input fields for spudcan cone angle (β) and surface roughness (α)
- Automatic calculation of embedment depth ratio and strength gradient
- More accurate bearing capacity prediction in normally consolidated clays

Run this script with `streamlit run app_ui_v2.py` to launch the app.
"""

import io
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from lpa_v50_v4 import (
    Spudcan, SoilPoint, SoilLayer,
    compute_envelopes, penetration_results,
    USE_MIN_CU_POINT_AVG_DEFAULT, APPLY_PHI_REDUCTION_DEFAULT,
    APPLY_WINDWARD_FACTOR_DEFAULT, APPLY_SQUEEZE_TRIGGER_DEFAULT,
)

st.set_page_config(
    page_title="spud-SRI V2 / Leg Penetration (SNAME)",
    page_icon="💎",
)

st.title("spud-SRI · Leg Penetration (SNAME) · Version 2")
st.caption("✨ Upgraded with zero-load tip penetration and advanced Nc' from Tables C6.1-C6.6")

with st.sidebar:
    st.subheader("Analysis switches")
    use_min_cu = st.checkbox("Use min(Su point, Su B/2 avg)", value=USE_MIN_CU_POINT_AVG_DEFAULT,
                             help="Conservative default for undrained strength.")
    phi_reduce = st.checkbox("Apply 5° reduction to ϕ′", value=APPLY_PHI_REDUCTION_DEFAULT,
                             help="Optional conservatism for sands.")
    windward80 = st.checkbox("Windward factor 0.8 on REAL", value=APPLY_WINDWARD_FACTOR_DEFAULT,
                             help="Applies 0.8 to the governing REAL capacity only.")
    squeeze_trig = st.checkbox("Enforce squeezing geometric trigger", value=APPLY_SQUEEZE_TRIGGER_DEFAULT)
    
    st.divider()
    st.subheader("Analysis parameters")
    dz = st.number_input("Depth step Δz (m)", value=0.25, min_value=0.05, max_value=2.0, step=0.05)
    dmax = st.number_input("Max analysis depth (m)", value=30.0, min_value=5.0, max_value=200.0, step=1.0)

st.markdown("#### Spudcan inputs")
cols = st.columns(5)
rig = cols[0].text_input("Rig name", "Rig-1")
B   = cols[1].number_input("Diameter B (m)", value=8.0, min_value=0.1, step=0.1)
A   = cols[2].number_input("Area A (m²)", value=float(np.pi*(B**2)/4.0), min_value=0.01, step=0.1,
                           help="Projected area of widest section. Defaults to πB²/4.")
tip = cols[3].number_input("Tip elevation (m)", value=1.5, min_value=0.0, step=0.1,
                           help="Distance from tip to widest section; added to analysis depth for tip penetration.")
Pmn = cols[4].number_input("Preload per leg (MN)", value=80.0, min_value=1.0, step=1.0)

# NEW: Advanced Nc' parameters (Upgrade 2)
st.markdown("##### 🆕 Advanced Nc' parameters (optional)")
with st.expander("Configure advanced bearing capacity factors (SNAME Tables C6.1-C6.6)", expanded=False):
    st.markdown("""
    **When to use:** For more accurate bearing capacity prediction in normally consolidated clays.
    
    **Parameters:**
    - **β (Beta)**: Spudcan equivalent cone angle
    - **α (Alpha)**: Surface roughness factor (0.0 = fully smooth, 1.0 = fully rough)
    
    **Calculated automatically:**
    - **D/2R**: Embedment depth ratio at each analysis depth
    - **ρ2R/c_um**: Strength gradient parameter from your Su profile
    
    Leave unchecked to use the default Nc = 5.14 approach.
    """)
    
    use_advanced_nc = st.checkbox("Enable advanced Nc' calculation", value=False,
                                 help="Uses SNAME Tables C6.1-C6.6 for bearing capacity factors")
    
    if use_advanced_nc:
        col_beta, col_alpha = st.columns(2)
        
        with col_beta:
            beta_deg = st.selectbox(
                "Cone angle β (degrees)",
                options=[30, 60, 90, 120, 150, 180],
                index=2,  # default to 90°
                help="Equivalent cone angle of spudcan. For multi-cone spudcans, use equivalent single cone."
            )
            
            st.caption("**Guidance:** Flat spudcan=180°, typical=90-120°, sharp=30-60°")
        
        with col_alpha:
            alpha = st.slider(
                "Roughness α",
                min_value=0.0,
                max_value=1.0,
                value=0.4,
                step=0.1,
                help="Surface roughness: 0.0=smooth, 1.0=fully rough. Typical 'double cone' spudcans ≈ 0.4"
            )
            
            st.caption("**Guidance:** Smooth=0.0-0.2, typical=0.4, rough=0.8-1.0")
    else:
        beta_deg = None
        alpha = None

spud = Spudcan(rig_name=rig, B=B, A=A, tip_elev=tip, preload_MN=Pmn,
               beta=beta_deg, alpha=alpha)

st.markdown("#### Soil profile")
st.caption("Add layers from seabed downward. The app will calculate ρ automatically from your Su profile.")

# Layer builder
if "layers" not in st.session_state:
    st.session_state.layers = []

def _add_layer():
    st.session_state.layers.append({
        "name": f"Layer {len(st.session_state.layers)+1}",
        "z_top": 0.0 if not st.session_state.layers else st.session_state.layers[-1]["z_bot"],
        "z_bot": (0.0 if not st.session_state.layers else st.session_state.layers[-1]["z_bot"]) + 2.0,
        "type": "clay",
        "gamma_pairs": "0,10.0; 2,10.0",
        "su_pairs":    "0,30;   2,35",
        "phi_pairs":   "",
    })

def _parse_pairs(s: str):
    s = (s or "").strip()
    if not s:
        return []
    pts = []
    for tok in s.split(";"):
        tok = tok.strip()
        if not tok:
            continue
        d, v = tok.split(",")
        pts.append(SoilPoint(float(d.strip()), float(v.strip())))
    return pts

st.button("➕ Add layer", on_click=_add_layer)
for i, L in enumerate(st.session_state.layers):
    with st.expander(f"Layer {i+1}", expanded=True):
        c1, c2, c3, c4 = st.columns([1.2,1.2,1.2,1.2])
        L["name"]  = c1.text_input("Name", L["name"], key=f"name{i}")
        L["z_top"] = c2.number_input("z_top (m)", value=float(L["z_top"]), key=f"z1{i}", step=0.1)
        L["z_bot"] = c3.number_input("z_bot (m)", value=float(L["z_bot"]), key=f"z2{i}", step=0.1)
        L["type"]  = c4.selectbox("Type", ["clay","sand","silt","unknown"], index=["clay","sand","silt","unknown"].index(L["type"]), key=f"type{i}")
        L["gamma_pairs"] = st.text_input("γ′ pairs 'z,val; z,val; ...'  (kN/m³)", L["gamma_pairs"], key=f"g{i}")
        L["su_pairs"]    = st.text_input("Su pairs 'z,val; z,val; ...'  (kPa)", L["su_pairs"],    key=f"su{i}")
        L["phi_pairs"]   = st.text_input("ϕ′ pairs 'z,val; z,val; ...' (deg)", L["phi_pairs"],   key=f"phi{i}")

st.divider()

do_run = st.button("Run analysis", type="primary")
if do_run:
    # Build SoilLayer list
    layers = []
    for L in st.session_state.layers:
        layers.append(
            SoilLayer(
                name=L["name"],
                z_top=float(L["z_top"]),
                z_bot=float(L["z_bot"]),
                soil_type=L["type"],
                gamma=_parse_pairs(L["gamma_pairs"]),
                su=_parse_pairs(L["su_pairs"]),
                phi=_parse_pairs(L["phi_pairs"]),
            )
        )

    if not layers:
        st.error("Please add at least one soil layer.")
        st.stop()

    # Compute
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

    # Penetration results
    pen = penetration_results(spud, df)

    # --- Results summary ---
    with st.container():
        st.subheader("Results")
        cols = st.columns(3)
        cols[0].metric("Preload per leg", f"{spud.preload_MN:.2f} MN")
        
        if pen["tip_range_min"] is not None and pen["tip_range_max"] is not None and pen["tip_range_min"] != pen["tip_range_max"]:
            cols[1].metric("Tip penetration range", f"{pen['tip_range_min']:.2f} – {pen['tip_range_max']:.2f} m")
        elif pen["tip_range_min"] is not None:
            cols[1].metric("Tip penetration", f"{pen['tip_range_min']:.2f} m")
        else:
            cols[1].metric("Tip penetration", "—")
        
        if use_advanced_nc:
            cols[2].metric("Nc' method", f"β={beta_deg}°, α={alpha:.1f}")
        else:
            cols[2].metric("Nc' method", "Default (5.14)")

    # --- Info message about upgrades ---
    if use_advanced_nc:
        st.info("🎯 **V2 Upgrades Active:** Zero-load until tip penetration + Advanced Nc' from SNAME tables")
    else:
        st.info("✅ **V2 Upgrade Active:** Zero-load until tip penetration (enable advanced Nc' above for full V2)")

    # --- Compact, high-DPI chart (Matplotlib) ---
    fig, ax = plt.subplots(figsize=(4.2, 6.2), dpi=200)
    ax.plot(df["idle_clay_MN"], df["depth"], lw=0.8, ls="-", color="0.6", label="Idle Clay")
    ax.plot(df["idle_sand_MN"], df["depth"], lw=0.8, ls="--", color="0.6", label="Idle Sand")
    ax.plot(df["real_MN"], df["depth"], lw=1.8, color="#0033cc", label="REAL (governing)")

    # preload line
    ax.axvline(spud.preload_MN, ymin=0, ymax=1, color="red", lw=1.2, ls="--", label="Preload")

    # Add horizontal line at tip_elev to show where capacity starts
    if spud.tip_elev > 0:
        ax.axhline(spud.tip_elev, xmin=0, xmax=1, color="orange", lw=1.0, ls=":", 
                  label=f"Tip offset ({spud.tip_elev:.2f}m)")

    ax.set_xlabel("Leg load (MN)")
    ax.set_ylabel("Penetration of widest section (m)")
    ax.invert_yaxis()
    ax.grid(True, ls=":", lw=0.6, color="0.7")
    ax.set_xlim(left=0)
    ax.legend(loc="upper right", fontsize=7, frameon=True)
    st.pyplot(fig, clear_figure=True)

    # --- Table & downloads ---
    st.subheader("Detailed table")
    st.dataframe(df, use_container_width=True, height=320)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name=f"{spud.rig_name}_v2_results.csv", mime="text/csv")

    # Summary note
    st.caption(
        "**Version 2 Notes:** "
        "Capacity is zero until penetration reaches tip offset. "
        "REAL equals the minimum of valid candidates (clay/sand) after special-mode reductions. "
        "When advanced Nc' is enabled, bearing capacity factors are interpolated from SNAME Tables C6.1-C6.6 "
        "based on spudcan geometry and automatically calculated embedment/strength-gradient parameters."
    )
