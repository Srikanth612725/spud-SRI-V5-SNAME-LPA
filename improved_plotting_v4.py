"""
improved_plotting_v4.py
=======================

Enhanced plotting functions for Spud-SRI V4 with:
1. Clean graph showing only REAL curve + Preload line
2. Interactive scale controls
3. Better readability

Use these functions in your Streamlit app (app_ui_v2.py)
"""

import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def plot_penetration_curve_v4(
    df: pd.DataFrame,
    preload_MN: float,
    tip_offset_m: float,
    rig_name: str = "Jack-Up Rig",
    x_max: float = None,
    y_max: float = None,
    fig_width: float = 10,
    fig_height: float = 8
):
    """
    Create a clean, professional penetration curve plot.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Output from compute_envelopes()
    preload_MN : float
        Preload value in MN
    tip_offset_m : float
        Distance from tip to widest section (m)
    rig_name : str
        Name for plot title
    x_max : float, optional
        Maximum x-axis value (MN). If None, auto-scales.
    y_max : float, optional
        Maximum y-axis value (m). If None, auto-scales.
    fig_width : float
        Figure width in inches
    fig_height : float
        Figure height in inches
    
    Returns:
    --------
    fig, ax : matplotlib figure and axis objects
    """
    
    # Create figure
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    
    # Extract data
    depths = df["depth"].values
    real_capacity = df["real_MN"].values
    
    # Filter out NaN values
    valid_mask = ~np.isnan(real_capacity)
    depths_clean = depths[valid_mask]
    real_clean = real_capacity[valid_mask]
    
    # Plot REAL capacity curve (thick blue line)
    ax.plot(real_clean, depths_clean, 
            linewidth=3, 
            color='#1f77b4',  # Professional blue
            label='REAL (governing)', 
            zorder=3)
    
    # Plot Preload line (red dashed)
    if x_max is not None:
        x_preload = x_max
    else:
        x_preload = max(real_clean.max() * 1.2, preload_MN * 1.2)
    
    ax.axvline(x=preload_MN, 
               color='red', 
               linestyle='--', 
               linewidth=2, 
               label=f'Preload ({preload_MN:.1f} MN)',
               zorder=2)
    
    # Plot tip offset (orange dashed horizontal line)
    ax.axhline(y=tip_offset_m, 
               color='orange', 
               linestyle=':', 
               linewidth=1.5, 
               label=f'Tip offset ({tip_offset_m:.2f}m)',
               zorder=1)
    
    # Formatting
    ax.set_xlabel('Leg Load (MN)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Penetration of widest section (m)', fontsize=14, fontweight='bold')
    ax.set_title(f'{rig_name} - Leg Penetration Analysis', 
                 fontsize=16, fontweight='bold', pad=20)
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    
    # Invert y-axis (depth increases downward)
    ax.invert_yaxis()
    
    # Set limits
    if x_max is not None:
        ax.set_xlim(0, x_max)
    else:
        ax.set_xlim(0, real_clean.max() * 1.1)
    
    if y_max is not None:
        ax.set_ylim(y_max, 0)
    else:
        ax.set_ylim(depths_clean.max() * 1.05, 0)
    
    # Legend
    ax.legend(loc='lower right', fontsize=11, framealpha=0.9)
    
    # Tight layout
    plt.tight_layout()
    
    return fig, ax


def create_streamlit_plot_with_controls(df: pd.DataFrame, spud, results: dict):
    """
    Streamlit-integrated plotting function with interactive controls.
    
    Use this in your app_ui_v2.py file.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Output from compute_envelopes()
    spud : Spudcan
        Spudcan object with preload and geometry
    results : dict
        Output from penetration_results()
    
    Example Usage in Streamlit:
    ---------------------------
    from improved_plotting_v4 import create_streamlit_plot_with_controls
    
    # After computing results:
    create_streamlit_plot_with_controls(df, spud, results)
    """
    
    st.subheader("📊 Interactive Penetration Curve")
    
    # Create three columns for controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # X-axis (Load) controls
        st.write("**X-Axis (Load) Scale:**")
        auto_x = st.checkbox("Auto-scale X", value=True, key="auto_x")
        if not auto_x:
            max_load = df["real_MN"].max() * 1.5
            x_max = st.slider("Max Load (MN)", 
                            min_value=float(spud.preload_MN), 
                            max_value=float(max_load),
                            value=float(max_load * 0.7),
                            step=10.0)
        else:
            x_max = None
    
    with col2:
        # Y-axis (Depth) controls
        st.write("**Y-Axis (Depth) Scale:**")
        auto_y = st.checkbox("Auto-scale Y", value=True, key="auto_y")
        if not auto_y:
            max_depth = df["depth"].max()
            y_max = st.slider("Max Depth (m)", 
                            min_value=10.0, 
                            max_value=float(max_depth),
                            value=float(max_depth * 0.7),
                            step=5.0)
        else:
            y_max = None
    
    with col3:
        # Plot size controls
        st.write("**Plot Size:**")
        fig_width = st.slider("Width", min_value=6, max_value=16, value=10, step=1)
        fig_height = st.slider("Height", min_value=6, max_value=16, value=8, step=1)
    
    # Create the plot
    fig, ax = plot_penetration_curve_v4(
        df=df,
        preload_MN=spud.preload_MN,
        tip_offset_m=spud.tip_elev,
        rig_name=spud.rig_name,
        x_max=x_max,
        y_max=y_max,
        fig_width=fig_width,
        fig_height=fig_height
    )
    
    # Display in Streamlit
    st.pyplot(fig)
    plt.close(fig)
    
    # Add penetration results below plot
    st.write("---")
    st.subheader("📍 Predicted Penetration Depths")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.metric("Clay Penetration (widest section)", 
                 f"{results['z_clay']:.2f} m" if results['z_clay'] else "N/A")
        st.metric("Clay Penetration (tip)", 
                 f"{results['tip_clay']:.2f} m" if results['tip_clay'] else "N/A")
    
    with col_b:
        st.metric("Sand Penetration (widest section)", 
                 f"{results['z_sand']:.2f} m" if results['z_sand'] else "N/A")
        st.metric("Sand Penetration (tip)", 
                 f"{results['tip_sand']:.2f} m" if results['tip_sand'] else "N/A")
    
    # Range summary
    if results['z_range_min'] is not None:
        st.info(f"""
        **Penetration Range:**
        - Widest section: {results['z_range_min']:.2f}m to {results['z_range_max']:.2f}m
        - Tip: {results['tip_range_min']:.2f}m to {results['tip_range_max']:.2f}m
        """)


def add_failure_mode_annotations(ax, df: pd.DataFrame):
    """
    Add visual annotations for failure modes to existing plot.
    
    Call this AFTER creating the main plot if you want to highlight
    regions where squeezing or punch-through occur.
    
    Parameters:
    -----------
    ax : matplotlib axis
        Axis object to add annotations to
    df : pd.DataFrame
        Output from compute_envelopes() with V4 failure mode columns
    
    Example:
    --------
    fig, ax = plot_penetration_curve_v4(...)
    add_failure_mode_annotations(ax, df)
    st.pyplot(fig)
    """
    
    depths = df["depth"].values
    
    # Find squeezing zones
    squeeze_mask = df["squeezing_active"] == "YES"
    if squeeze_mask.any():
        squeeze_depths = depths[squeeze_mask]
        if len(squeeze_depths) > 0:
            y_min, y_max = squeeze_depths.min(), squeeze_depths.max()
            ax.axhspan(y_min, y_max, alpha=0.2, color='yellow', 
                      label='Squeezing zone')
    
    # Find clay/clay punch-through zones
    punch_cc_mask = df["punch_clay_clay_active"] == "YES"
    if punch_cc_mask.any():
        punch_cc_depths = depths[punch_cc_mask]
        if len(punch_cc_depths) > 0:
            y_min, y_max = punch_cc_depths.min(), punch_cc_depths.max()
            ax.axhspan(y_min, y_max, alpha=0.2, color='red', 
                      label='Punch-through (clay/clay)')
    
    # Find sand/clay punch-through zones
    punch_sc_mask = df["punch_sand_clay_active"] == "YES"
    if punch_sc_mask.any():
        punch_sc_depths = depths[punch_sc_mask]
        if len(punch_sc_depths) > 0:
            y_min, y_max = punch_sc_depths.min(), punch_sc_depths.max()
            ax.axhspan(y_min, y_max, alpha=0.2, color='orange', 
                      label='Punch-through (sand/clay)')
    
    # Update legend to include new items
    ax.legend(loc='lower right', fontsize=10, framealpha=0.9)


# ============ Example usage in Streamlit app ============

def example_streamlit_integration():
    """
    Example of how to integrate this into your app_ui_v2.py
    
    Replace your existing plotting code with this:
    """
    
    # After computing results:
    # df = compute_envelopes(spud, layers, max_depth=50.0, ...)
    # results = penetration_results(spud, df)
    
    # Option 1: Simple plot with interactive controls
    from improved_plotting_v4 import create_streamlit_plot_with_controls
    create_streamlit_plot_with_controls(df, spud, results)
    
    # Option 2: Custom plot with failure mode annotations
    """
    from improved_plotting_v4 import plot_penetration_curve_v4, add_failure_mode_annotations
    
    fig, ax = plot_penetration_curve_v4(
        df=df,
        preload_MN=spud.preload_MN,
        tip_offset_m=spud.tip_elev,
        rig_name=spud.rig_name
    )
    
    # Add failure mode zones
    add_failure_mode_annotations(ax, df)
    
    # Display
    st.pyplot(fig)
    plt.close(fig)
    """
