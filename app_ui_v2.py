"""
app_ui_v2_enhanced.py - Spud-SRI Version 2 (ENHANCED)
=======================================================

Enhanced Streamlit interface with improved soil profile input that allows
multiple data points per parameter within each layer.

Key improvements:
- Multiple γ', Su, and φ' data points within each layer
- Better representation of complex soil profiles
- Maintains compatibility with existing computation engine

Run this script with `streamlit run app_ui_v2_enhanced.py` to launch the app.
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
    page_title="spud-SRI V5 / Leg Penetration (SNAME)",
    page_icon="💎",
)

st.title("spud-SRI · Leg Penetration (SNAME) · Version 2 Enhanced")
st.caption("✨ Upgraded with zero-load tip penetration, advanced Nc', and flexible soil profile input")

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

# Define helper functions at module level
def _parse_pairs(s: str):
    """Parse string pairs like '0,10.0; 2,10.0' into SoilPoint list."""
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

def _convert_to_layers(layers_data):
    """Convert layer data to SoilLayer objects (compatible with existing code)."""
    
    soil_layers = []
    
    for data in layers_data:
        # Create SoilLayer object
        layer = SoilLayer(
            name=data['name'],
            z_top=data['z_top'],
            z_bot=data['z_bot'],
            soil_type=data['type'],
            gamma=data.get('gamma_points', []),
            su=data.get('su_points', []),
            phi=data.get('phi_points', [])
        )
        
        soil_layers.append(layer)
    
    return soil_layers

def _enhanced_interactive_input():
    """Enhanced interactive table input - allows multiple data points per parameter."""
    
    # Initialize session state for advanced input
    if 'soil_layers_enhanced' not in st.session_state:
        st.session_state.soil_layers_enhanced = []
    
    # Add new layer button
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("➕ Add New Layer", use_container_width=True, type="primary"):
            st.session_state.soil_layers_enhanced.append({
                'name': f"Layer {len(st.session_state.soil_layers_enhanced)+1}",
                'type': 'clay',
                'z_top': 0.0 if not st.session_state.soil_layers_enhanced else st.session_state.soil_layers_enhanced[-1]['z_bot'],
                'z_bot': (0.0 if not st.session_state.soil_layers_enhanced else st.session_state.soil_layers_enhanced[-1]['z_bot']) + 10.0,
                'gamma_points': [],
                'su_points': [],
                'phi_points': []
            })
            st.rerun()
    
    # Display and edit layers
    for idx, layer in enumerate(st.session_state.soil_layers_enhanced):
        with st.expander(f"**{layer['name']}** ({layer['type']}, {layer['z_top']:.1f}-{layer['z_bot']:.1f}m)", expanded=True):
            
            # Basic layer properties
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                layer['name'] = st.text_input("Layer name", value=layer['name'], key=f"name_enh_{idx}")
            
            with col2:
                layer['type'] = st.selectbox("Type", ["clay", "silt", "sand"], 
                                            index=["clay", "silt", "sand"].index(layer['type']), 
                                            key=f"type_enh_{idx}")
            
            with col3:
                layer['z_top'] = st.number_input("Top (m)", value=layer['z_top'], step=0.5, key=f"ztop_enh_{idx}")
            
            with col4:
                layer['z_bot'] = st.number_input("Bottom (m)", value=layer['z_bot'], step=0.5, key=f"zbot_enh_{idx}")
            
            st.markdown("---")
            
            # Data points for each parameter
            tabs = st.tabs(["γ' (kN/m³)", "Su (kPa)" if layer['type'] in ['clay', 'silt'] else "φ' (deg)", "Actions"])
            
            # Gamma prime tab
            with tabs[0]:
                st.markdown("**Submerged unit weight data points**")
                
                # Add data point form
                with st.form(f"add_gamma_{idx}"):
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        new_z = st.number_input("Depth (m)", value=layer['z_top'], 
                                              min_value=layer['z_top'], max_value=layer['z_bot'], 
                                              step=0.5, key=f"gamma_z_new_{idx}")
                    with col2:
                        new_val = st.number_input("γ' (kN/m³)", value=8.0, step=0.5, key=f"gamma_v_new_{idx}")
                    with col3:
                        if st.form_submit_button("Add Point", use_container_width=True):
                            if 'gamma_points' not in layer:
                                layer['gamma_points'] = []
                            layer['gamma_points'].append(SoilPoint(new_z, new_val))
                            layer['gamma_points'].sort(key=lambda p: p.z)
                            st.rerun()
                
                # Display existing points
                if layer.get('gamma_points'):
                    df_gamma = pd.DataFrame([
                        {'Depth (m)': p.z, 'γ\' (kN/m³)': p.v, 'Delete': f"🗑️ {i}"}
                        for i, p in enumerate(layer['gamma_points'])
                    ])
                    st.dataframe(df_gamma[['Depth (m)', 'γ\' (kN/m³)']], use_container_width=True, hide_index=True)
                    
                    # Delete point
                    if len(layer['gamma_points']) > 0:
                        del_idx = st.number_input("Delete point #", min_value=1, 
                                                 max_value=len(layer['gamma_points']), 
                                                 value=1, step=1, key=f"del_gamma_{idx}")
                        if st.button(f"Delete Point #{del_idx}", key=f"del_gamma_btn_{idx}"):
                            layer['gamma_points'].pop(del_idx - 1)
                            st.rerun()
                else:
                    st.info("No data points yet. Add points above.")
            
            # Strength parameter tab
            with tabs[1]:
                if layer['type'] in ['clay', 'silt']:
                    st.markdown("**Undrained shear strength data points**")
                    param_name = 'su_points'
                    param_label = 'Su (kPa)'
                    default_val = 30.0
                else:
                    st.markdown("**Friction angle data points**")
                    param_name = 'phi_points'
                    param_label = 'φ\' (deg)'
                    default_val = 30.0
                
                # Add data point form
                with st.form(f"add_param_{idx}"):
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        new_z = st.number_input("Depth (m)", value=layer['z_top'], 
                                              min_value=layer['z_top'], max_value=layer['z_bot'], 
                                              step=0.5, key=f"param_z_new_{idx}")
                    with col2:
                        new_val = st.number_input(param_label, value=default_val, step=5.0, key=f"param_v_new_{idx}")
                    with col3:
                        if st.form_submit_button("Add Point", use_container_width=True):
                            if param_name not in layer:
                                layer[param_name] = []
                            layer[param_name].append(SoilPoint(new_z, new_val))
                            layer[param_name].sort(key=lambda p: p.z)
                            st.rerun()
                
                # Display existing points
                if layer.get(param_name):
                    df_param = pd.DataFrame([
                        {'Depth (m)': p.z, param_label: p.v}
                        for i, p in enumerate(layer[param_name])
                    ])
                    st.dataframe(df_param, use_container_width=True, hide_index=True)
                    
                    # Delete point
                    if len(layer[param_name]) > 0:
                        del_idx = st.number_input("Delete point #", min_value=1, 
                                                 max_value=len(layer[param_name]), 
                                                 value=1, step=1, key=f"del_param_{idx}")
                        if st.button(f"Delete Point #{del_idx}", key=f"del_param_btn_{idx}"):
                            layer[param_name].pop(del_idx - 1)
                            st.rerun()
                else:
                    st.info("No data points yet. Add points above.")
            
            # Actions tab
            with tabs[2]:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"🗑️ Delete Layer", key=f"del_layer_{idx}", use_container_width=True):
                        st.session_state.soil_layers_enhanced.pop(idx)
                        st.rerun()
                
                with col2:
                    # Add quick fill option
                    if st.button(f"🎯 Auto-fill with linear profile", key=f"autofill_{idx}", use_container_width=True):
                        # Auto-fill with top and bottom values
                        if not layer.get('gamma_points'):
                            layer['gamma_points'] = [
                                SoilPoint(layer['z_top'], 7.0),
                                SoilPoint(layer['z_bot'], 8.0)
                            ]
                        
                        if layer['type'] in ['clay', 'silt'] and not layer.get('su_points'):
                            layer['su_points'] = [
                                SoilPoint(layer['z_top'], 20.0),
                                SoilPoint(layer['z_bot'], 50.0)
                            ]
                        elif layer['type'] == 'sand' and not layer.get('phi_points'):
                            layer['phi_points'] = [
                                SoilPoint(layer['z_top'], 30.0),
                                SoilPoint(layer['z_bot'], 35.0)
                            ]
                        st.rerun()
    
    # Summary of all layers
    if st.session_state.soil_layers_enhanced:
        st.markdown("---")
        st.markdown("### Profile Summary")
        
        summary_data = []
        for i, layer in enumerate(st.session_state.soil_layers_enhanced):
            summary_data.append({
                '#': i+1,
                'Name': layer['name'],
                'Type': layer['type'],
                'Depths': f"{layer['z_top']:.1f}-{layer['z_bot']:.1f}m",
                'γ\' points': len(layer.get('gamma_points', [])),
                'Su points': len(layer.get('su_points', [])) if layer['type'] in ['clay', 'silt'] else '—',
                'φ\' points': len(layer.get('phi_points', [])) if layer['type'] == 'sand' else '—'
            })
        
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
        
        # Clear all button
        if st.button("🗑️ Clear All Layers", use_container_width=True):
            st.session_state.soil_layers_enhanced = []
            st.rerun()
        
        return _convert_to_layers(st.session_state.soil_layers_enhanced)
    else:
        st.info("👆 Click 'Add New Layer' to start building your soil profile")
        return []

def _paste_input_enhanced():
    """Enhanced paste data from Excel/CSV with multiple points per layer."""
    
    st.write("**Expected format (multiple points per parameter):**")
    st.code("""Layer, Type, z_top, z_bot, Parameter, Depth1, Value1, Depth2, Value2, ...
Soft Clay, clay, 0, 10, gamma, 0, 7.0, 5, 7.5, 10, 8.0
Soft Clay, clay, 0, 10, su, 0, 20, 3, 25, 6, 30, 10, 40
Sand, sand, 10, 20, gamma, 10, 9.0, 15, 9.3, 20, 9.5
Sand, sand, 10, 20, phi, 10, 32, 15, 33, 20, 35""", language="csv")
    
    pasted = st.text_area("Paste CSV data:", height=200, placeholder="Layer, Type, z_top, z_bot, Parameter...")
    
    if pasted:
        try:
            from io import StringIO
            lines = pasted.strip().split('\n')
            
            # Parse into layer structure
            layers_dict = {}
            
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 7:  # Minimum: name, type, z_top, z_bot, param, one depth-value pair
                    continue
                
                name = parts[0]
                soil_type = parts[1].lower()
                z_top = float(parts[2])
                z_bot = float(parts[3])
                param_type = parts[4].lower()
                
                # Create unique key for layer
                layer_key = f"{name}_{z_top}_{z_bot}"
                
                # Initialize layer if not exists
                if layer_key not in layers_dict:
                    layers_dict[layer_key] = {
                        'name': name,
                        'type': soil_type,
                        'z_top': z_top,
                        'z_bot': z_bot,
                        'gamma_points': [],
                        'su_points': [],
                        'phi_points': []
                    }
                
                # Parse depth-value pairs
                points = []
                for i in range(5, len(parts), 2):
                    if i+1 < len(parts):
                        depth = float(parts[i])
                        value = float(parts[i+1])
                        points.append(SoilPoint(depth, value))
                
                # Add points to appropriate parameter
                if param_type in ['gamma', 'γ', "γ'"]:
                    layers_dict[layer_key]['gamma_points'].extend(points)
                elif param_type in ['su', 'cu']:
                    layers_dict[layer_key]['su_points'].extend(points)
                elif param_type in ['phi', 'φ', "φ'"]:
                    layers_dict[layer_key]['phi_points'].extend(points)
            
            # Convert to list
            layers_data = list(layers_dict.values())
            
            # Sort points within each layer
            for layer in layers_data:
                layer['gamma_points'].sort(key=lambda p: p.z)
                layer['su_points'].sort(key=lambda p: p.z)
                layer['phi_points'].sort(key=lambda p: p.z)
            
            st.success(f"✅ Parsed {len(layers_data)} layers")
            
            # Show preview
            preview_data = []
            for i, layer in enumerate(layers_data):
                preview_data.append({
                    '#': i+1,
                    'Name': layer['name'],
                    'Type': layer['type'],
                    'Depths': f"{layer['z_top']:.1f}-{layer['z_bot']:.1f}m",
                    'γ\' points': len(layer['gamma_points']),
                    'Su points': len(layer['su_points']) if layer['type'] in ['clay', 'silt'] else '—',
                    'φ\' points': len(layer['phi_points']) if layer['type'] == 'sand' else '—'
                })
            
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)
            
            return _convert_to_layers(layers_data)
            
        except Exception as e:
            st.error(f"Error parsing data: {str(e)}")
            st.write("Please check format and try again.")
            return []
    
    return []

def soil_input_widget_enhanced():
    """
    Enhanced interactive soil input widget with multiple data points per parameter.
    Returns list of SoilLayer objects compatible with existing code.
    """
    
    st.markdown("#### Soil profile")
    st.caption("Add layers with multiple measurement points per parameter for accurate representation")
    
    # Input method tabs
    tab1, tab2 = st.tabs(["📊 Interactive Table", "📋 Paste from Excel"])
    
    with tab1:
        layers = _enhanced_interactive_input()
    
    with tab2:
        layers = _paste_input_enhanced()
    
    return layers

# ============= Choose Input Method =============
st.markdown("#### Soil Profile Input Method")
input_method = st.radio(
    "Select input method:",
    ["Simple Layer Builder", "Enhanced Interactive (Multiple Points)"],
    horizontal=True,
    help="Enhanced method allows multiple data points per parameter within each layer"
)

if input_method == "Simple Layer Builder":
    # ============= SIMPLE LAYER BUILDER =============
    st.markdown("##### Soil profile")
    st.caption("Add layers from seabed downward. Use semicolon-separated pairs for data points.")
    
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
    
    st.button("➕ Add layer", on_click=_add_layer)
    for i, L in enumerate(st.session_state.layers):
        with st.expander(f"Layer {i+1}", expanded=True):
            c1, c2, c3, c4 = st.columns([1.2,1.2,1.2,1.2])
            L["name"]  = c1.text_input("Name", L["name"], key=f"name{i}")
            L["z_top"] = c2.number_input("z_top (m)", value=float(L["z_top"]), key=f"z1{i}", step=0.1)
            L["z_bot"] = c3.number_input("z_bot (m)", value=float(L["z_bot"]), key=f"z2{i}", step=0.1)
            L["type"]  = c4.selectbox("Type", ["clay","sand","silt","unknown"], 
                                      index=["clay","sand","silt","unknown"].index(L["type"]), key=f"type{i}")
            L["gamma_pairs"] = st.text_input("γ′ pairs 'z,val; z,val; ...'  (kN/m³)", L["gamma_pairs"], key=f"g{i}",
                                            help="Example: 0,7.0; 5,7.5; 10,8.0")
            L["su_pairs"]    = st.text_input("Su pairs 'z,val; z,val; ...'  (kPa)", L["su_pairs"],    key=f"su{i}",
                                            help="Example: 0,20; 3,25; 6,30; 10,40")
            L["phi_pairs"]   = st.text_input("ϕ′ pairs 'z,val; z,val; ...' (deg)", L["phi_pairs"],   key=f"phi{i}",
                                            help="Example: 10,32; 15,33; 20,35")
    
    # Store method for run analysis
    st.session_state.input_method = "simple"

else:
    # ============= ENHANCED INTERACTIVE WIDGET =============
    soil_input_widget_enhanced()
    st.session_state.input_method = "enhanced"

st.divider()

# ============= Run Analysis Button =============
do_run = st.button("Run analysis", type="primary")
if do_run:
    # Build SoilLayer list based on input method
    if st.session_state.get('input_method') == 'simple':
        # Simple method - from st.session_state.layers
        layers = []
        if 'layers' in st.session_state:
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
    else:
        # Enhanced method - convert directly from session state
        if 'soil_layers_enhanced' in st.session_state:
            layers = _convert_to_layers(st.session_state.soil_layers_enhanced)
        else:
            layers = []
    
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
