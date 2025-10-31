"""
improved_soil_input_ui.py
==========================

Enhanced Streamlit UI for soil parameter input.
Eliminates confusing comma/semicolon format with:
1. Interactive table input
2. Copy-paste from Excel support
3. Visual profile preview
4. Clear validation

Replace your current soil input code with these functions.
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from lpa_v50_v4 import SoilLayer, SoilPoint

# ============================================================================
# METHOD 1: INTERACTIVE TABLE INPUT (RECOMMENDED)
# ============================================================================

def create_soil_input_table():
    """
    Create an interactive table for soil input.
    Much more intuitive than comma/semicolon format.
    
    Returns:
    --------
    layers : List[SoilLayer]
        Parsed soil layers
    """
    
    st.subheader("🏗️ Soil Profile Input")
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        ["Interactive Table", "Paste from Excel", "Upload CSV"],
        horizontal=True
    )
    
    if input_method == "Interactive Table":
        return _interactive_table_input()
    elif input_method == "Paste from Excel":
        return _paste_from_excel_input()
    else:
        return _upload_csv_input()


def _interactive_table_input():
    """Interactive table where users add rows one by one."""
    
    st.write("**Add soil layers using the form below:**")
    
    # Initialize session state for storing layers
    if 'soil_layers_data' not in st.session_state:
        st.session_state.soil_layers_data = []
    
    # Form to add new layer
    with st.form("add_layer_form"):
        st.write("**Add New Layer:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            layer_name = st.text_input("Layer Name", value="", placeholder="e.g., Soft Clay")
            soil_type = st.selectbox("Soil Type", ["clay", "silt", "sand"])
            z_top = st.number_input("Top Depth (m)", value=0.0, step=0.1)
            z_bot = st.number_input("Bottom Depth (m)", value=10.0, step=0.1)
        
        with col2:
            st.write("**Unit Weight (kN/m³)**")
            gamma_top = st.number_input("γ at top", value=7.0, step=0.5, key="gamma_top")
            gamma_bot = st.number_input("γ at bottom", value=8.0, step=0.5, key="gamma_bot")
        
        with col3:
            if soil_type in ["clay", "silt"]:
                st.write("**Undrained Shear Strength (kPa)**")
                su_top = st.number_input("Su at top", value=10.0, step=5.0, key="su_top")
                su_bot = st.number_input("Su at bottom", value=50.0, step=5.0, key="su_bot")
                phi_top, phi_bot = None, None
            else:
                st.write("**Friction Angle (degrees)**")
                phi_top = st.number_input("φ at top", value=30.0, step=1.0, key="phi_top")
                phi_bot = st.number_input("φ at bottom", value=35.0, step=1.0, key="phi_bot")
                su_top, su_bot = None, None
        
        submitted = st.form_submit_button("➕ Add Layer")
        
        if submitted:
            if not layer_name:
                st.error("Please enter a layer name")
            elif z_bot <= z_top:
                st.error("Bottom depth must be greater than top depth")
            else:
                # Add to session state
                layer_data = {
                    'name': layer_name,
                    'soil_type': soil_type,
                    'z_top': z_top,
                    'z_bot': z_bot,
                    'gamma_top': gamma_top,
                    'gamma_bot': gamma_bot,
                    'su_top': su_top,
                    'su_bot': su_bot,
                    'phi_top': phi_top,
                    'phi_bot': phi_bot
                }
                st.session_state.soil_layers_data.append(layer_data)
                st.success(f"✅ Added layer: {layer_name}")
    
    # Display current layers
    if st.session_state.soil_layers_data:
        st.write("---")
        st.write("**Current Soil Profile:**")
        
        # Create display dataframe
        display_data = []
        for i, layer in enumerate(st.session_state.soil_layers_data):
            display_data.append({
                '#': i+1,
                'Name': layer['name'],
                'Type': layer['soil_type'],
                'Top (m)': layer['z_top'],
                'Bot (m)': layer['z_bot'],
                'γ_top': layer['gamma_top'],
                'γ_bot': layer['gamma_bot'],
                'Su_top' if layer['soil_type'] in ['clay', 'silt'] else 'φ_top': 
                    layer['su_top'] if layer['soil_type'] in ['clay', 'silt'] else layer['phi_top'],
                'Su_bot' if layer['soil_type'] in ['clay', 'silt'] else 'φ_bot': 
                    layer['su_bot'] if layer['soil_type'] in ['clay', 'silt'] else layer['phi_bot']
            })
        
        df_display = pd.DataFrame(display_data)
        st.dataframe(df_display, use_container_width=True)
        
        # Delete layer option
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🗑️ Clear All Layers"):
                st.session_state.soil_layers_data = []
                st.rerun()
        
        with col2:
            layer_to_delete = st.number_input("Delete layer #", min_value=1, 
                                             max_value=len(st.session_state.soil_layers_data),
                                             step=1, key="delete_idx")
            if st.button("🗑️ Delete Selected"):
                st.session_state.soil_layers_data.pop(layer_to_delete - 1)
                st.rerun()
        
        # Convert to SoilLayer objects
        return _convert_to_soil_layers(st.session_state.soil_layers_data)
    
    else:
        st.info("👆 Add your first soil layer using the form above")
        return []


def _paste_from_excel_input():
    """Allow users to paste data directly from Excel."""
    
    st.write("**Paste soil data from Excel/CSV:**")
    st.write("Expected format:")
    st.code("""
Name, Type, Top(m), Bot(m), γ_top, γ_bot, Su_top/φ_top, Su_bot/φ_bot
Soft Clay, clay, 0, 10, 7.0, 7.5, 10, 50
Stiff Clay, clay, 10, 20, 8.0, 8.5, 60, 100
Sand, sand, 20, 30, 9.0, 9.5, 32, 35
    """)
    
    pasted_data = st.text_area("Paste your data here:", height=200, 
                               placeholder="Name, Type, Top(m), Bot(m), γ_top, γ_bot, Su/φ_top, Su/φ_bot")
    
    if pasted_data:
        try:
            # Parse pasted data
            from io import StringIO
            df = pd.read_csv(StringIO(pasted_data), skipinitialspace=True)
            
            # Validate columns
            expected_cols = ['Name', 'Type', 'Top(m)', 'Bot(m)', 'γ_top', 'γ_bot']
            for col in expected_cols:
                if col not in df.columns:
                    st.error(f"Missing column: {col}")
                    return []
            
            # Convert to layer data
            layers_data = []
            for _, row in df.iterrows():
                soil_type = str(row['Type']).lower().strip()
                
                layer_data = {
                    'name': str(row['Name']),
                    'soil_type': soil_type,
                    'z_top': float(row['Top(m)']),
                    'z_bot': float(row['Bot(m)']),
                    'gamma_top': float(row['γ_top']),
                    'gamma_bot': float(row['γ_bot']),
                }
                
                # Get strength parameter column name
                strength_col_top = [c for c in df.columns if 'top' in c.lower() and c not in expected_cols]
                strength_col_bot = [c for c in df.columns if 'bot' in c.lower() and c not in expected_cols]
                
                if soil_type in ['clay', 'silt']:
                    layer_data['su_top'] = float(row[strength_col_top[0]]) if strength_col_top else None
                    layer_data['su_bot'] = float(row[strength_col_bot[0]]) if strength_col_bot else None
                    layer_data['phi_top'] = None
                    layer_data['phi_bot'] = None
                else:
                    layer_data['phi_top'] = float(row[strength_col_top[0]]) if strength_col_top else None
                    layer_data['phi_bot'] = float(row[strength_col_bot[0]]) if strength_col_bot else None
                    layer_data['su_top'] = None
                    layer_data['su_bot'] = None
                
                layers_data.append(layer_data)
            
            st.success(f"✅ Parsed {len(layers_data)} layers successfully!")
            
            # Display preview
            st.dataframe(df, use_container_width=True)
            
            return _convert_to_soil_layers(layers_data)
            
        except Exception as e:
            st.error(f"Error parsing data: {str(e)}")
            st.write("Please check the format and try again.")
            return []
    
    return []


def _upload_csv_input():
    """Allow users to upload a CSV file."""
    
    st.write("**Upload a CSV file with soil data:**")
    
    # Provide template
    if st.button("📥 Download Template CSV"):
        template = pd.DataFrame({
            'Name': ['Soft Clay', 'Stiff Clay', 'Sand'],
            'Type': ['clay', 'clay', 'sand'],
            'Top(m)': [0, 10, 20],
            'Bot(m)': [10, 20, 30],
            'γ_top': [7.0, 8.0, 9.0],
            'γ_bot': [7.5, 8.5, 9.5],
            'Su_top (clay) or φ_top (sand)': [10, 60, 32],
            'Su_bot (clay) or φ_bot (sand)': [50, 100, 35]
        })
        
        csv = template.to_csv(index=False)
        st.download_button("Download", csv, "soil_profile_template.csv", "text/csv")
    
    uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
    
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            
            # Similar parsing as paste method
            layers_data = []
            for _, row in df.iterrows():
                soil_type = str(row['Type']).lower().strip()
                
                layer_data = {
                    'name': str(row['Name']),
                    'soil_type': soil_type,
                    'z_top': float(row['Top(m)']),
                    'z_bot': float(row['Bot(m)']),
                    'gamma_top': float(row['γ_top']),
                    'gamma_bot': float(row['γ_bot']),
                }
                
                # Get strength parameters
                strength_col = [c for c in df.columns if 'Su' in c or 'φ' in c or 'phi' in c.lower()]
                
                if soil_type in ['clay', 'silt']:
                    layer_data['su_top'] = float(row[strength_col[0]]) if len(strength_col) > 0 else None
                    layer_data['su_bot'] = float(row[strength_col[1]]) if len(strength_col) > 1 else layer_data['su_top']
                    layer_data['phi_top'] = None
                    layer_data['phi_bot'] = None
                else:
                    layer_data['phi_top'] = float(row[strength_col[0]]) if len(strength_col) > 0 else None
                    layer_data['phi_bot'] = float(row[strength_col[1]]) if len(strength_col) > 1 else layer_data['phi_top']
                    layer_data['su_top'] = None
                    layer_data['su_bot'] = None
                
                layers_data.append(layer_data)
            
            st.success(f"✅ Loaded {len(layers_data)} layers from file!")
            st.dataframe(df, use_container_width=True)
            
            return _convert_to_soil_layers(layers_data)
            
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            return []
    
    return []


def _convert_to_soil_layers(layers_data):
    """Convert layer data dictionaries to SoilLayer objects."""
    
    soil_layers = []
    
    for data in layers_data:
        gamma_points = [
            SoilPoint(data['z_top'], data['gamma_top']),
            SoilPoint(data['z_bot'], data['gamma_bot'])
        ]
        
        su_points = []
        phi_points = []
        
        if data['soil_type'] in ['clay', 'silt']:
            if data['su_top'] is not None and data['su_bot'] is not None:
                su_points = [
                    SoilPoint(data['z_top'], data['su_top']),
                    SoilPoint(data['z_bot'], data['su_bot'])
                ]
        else:
            if data['phi_top'] is not None and data['phi_bot'] is not None:
                phi_points = [
                    SoilPoint(data['z_top'], data['phi_top']),
                    SoilPoint(data['z_bot'], data['phi_bot'])
                ]
        
        layer = SoilLayer(
            name=data['name'],
            z_top=data['z_top'],
            z_bot=data['z_bot'],
            soil_type=data['soil_type'],
            gamma=gamma_points,
            su=su_points,
            phi=phi_points
        )
        
        soil_layers.append(layer)
    
    return soil_layers


# ============================================================================
# VISUAL PROFILE PREVIEW
# ============================================================================

def plot_soil_profile_preview(layers):
    """
    Create a visual preview of the soil profile.
    Shows layers, depths, and strength parameters.
    """
    
    if not layers:
        st.warning("No layers to display")
        return
    
    st.subheader("📊 Soil Profile Preview")
    
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 8))
    
    # Plot 1: Layer stratigraphy
    colors = {'clay': '#8B4513', 'silt': '#D2691E', 'sand': '#F4A460'}
    
    for layer in layers:
        color = colors.get(layer.soil_type, '#gray')
        ax1.barh(y=-(layer.z_top + layer.z_bot)/2, 
                 width=1, 
                 height=(layer.z_bot - layer.z_top),
                 color=color, 
                 alpha=0.7,
                 edgecolor='black')
        
        # Add layer name
        mid_depth = (layer.z_top + layer.z_bot) / 2
        ax1.text(0.5, -mid_depth, layer.name, 
                ha='center', va='center', fontweight='bold', fontsize=9)
    
    ax1.set_ylim(-max([l.z_bot for l in layers]) * 1.05, 0)
    ax1.set_xlim(0, 1)
    ax1.set_ylabel('Depth (m)', fontweight='bold')
    ax1.set_title('Stratigraphy', fontweight='bold')
    ax1.set_xticks([])
    ax1.grid(axis='y', alpha=0.3)
    ax1.invert_yaxis()
    
    # Plot 2: Unit weight profile
    for layer in layers:
        depths = np.linspace(layer.z_top, layer.z_bot, 10)
        gammas = [next((p.v for p in layer.gamma if p.z == layer.z_top), None) + 
                  (next((p.v for p in layer.gamma if p.z == layer.z_bot), None) - 
                   next((p.v for p in layer.gamma if p.z == layer.z_top), None)) * 
                  (d - layer.z_top) / (layer.z_bot - layer.z_top) 
                  for d in depths]
        ax2.plot(gammas, depths, linewidth=2, label=layer.name)
    
    ax2.set_xlabel('Unit Weight (kN/m³)', fontweight='bold')
    ax2.set_ylabel('Depth (m)', fontweight='bold')
    ax2.set_title('Unit Weight Profile', fontweight='bold')
    ax2.grid(alpha=0.3)
    ax2.invert_yaxis()
    ax2.legend(fontsize=8, loc='lower right')
    
    # Plot 3: Strength profile
    for layer in layers:
        depths = np.linspace(layer.z_top, layer.z_bot, 10)
        
        if layer.soil_type in ['clay', 'silt'] and layer.su:
            su_top = next((p.v for p in layer.su if p.z == layer.z_top), None)
            su_bot = next((p.v for p in layer.su if p.z == layer.z_bot), None)
            
            if su_top is not None and su_bot is not None:
                strengths = [su_top + (su_bot - su_top) * (d - layer.z_top) / (layer.z_bot - layer.z_top) 
                           for d in depths]
                ax3.plot(strengths, depths, linewidth=2, label=f"{layer.name} (Su)")
        
        elif layer.soil_type == 'sand' and layer.phi:
            phi_top = next((p.v for p in layer.phi if p.z == layer.z_top), None)
            phi_bot = next((p.v for p in layer.phi if p.z == layer.z_bot), None)
            
            if phi_top is not None and phi_bot is not None:
                strengths = [phi_top + (phi_bot - phi_top) * (d - layer.z_top) / (layer.z_bot - layer.z_top) 
                           for d in depths]
                ax3.plot(strengths, depths, linewidth=2, label=f"{layer.name} (φ)", linestyle='--')
    
    ax3.set_xlabel('Strength (Su: kPa, φ: deg)', fontweight='bold')
    ax3.set_ylabel('Depth (m)', fontweight='bold')
    ax3.set_title('Strength Profile', fontweight='bold')
    ax3.grid(alpha=0.3)
    ax3.invert_yaxis()
    ax3.legend(fontsize=8, loc='lower right')
    
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()


# ============================================================================
# EXAMPLE USAGE IN APP
# ============================================================================

def example_app_integration():
    """
    Example of how to use this in your app_ui_v2.py
    
    Replace your current soil input section with:
    """
    
    st.title("Spud-SRI V4 - Leg Penetration Analysis")
    
    # Spudcan input (keep your existing code here)
    st.header("1️⃣ Spudcan Parameters")
    # ... your existing spudcan input code ...
    
    # NEW SOIL INPUT (Replace your old code with this)
    st.header("2️⃣ Soil Profile")
    
    # Use the improved input function
    layers = create_soil_input_table()
    
    # Show visual preview
    if layers:
        plot_soil_profile_preview(layers)
        
        # Validation check
        st.success(f"✅ Soil profile loaded: {len(layers)} layers")
        
        # Now proceed with analysis
        st.header("3️⃣ Run Analysis")
        if st.button("🚀 Compute Penetration"):
            # Your existing analysis code here
            # df = compute_envelopes(spud, layers, ...)
            # results = penetration_results(spud, df)
            pass
    else:
        st.info("👆 Please add soil layers above to continue")


if __name__ == "__main__":
    # For testing this module standalone
    st.set_page_config(page_title="Improved Soil Input", layout="wide")
    example_app_integration()
