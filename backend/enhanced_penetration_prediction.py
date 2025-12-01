"""
enhanced_penetration_prediction.py
==================================

Advanced penetration prediction that addresses:
1. Punch-through zones and breakthrough potential
2. Re-entry feasibility analysis
3. Dynamic effects and overshoot
4. Conservative range reporting

This module extends lpa_v50_v4.py with more realistic predictions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class PenetrationPrediction:
    """Enhanced penetration prediction results."""
    static_depth: float  # First intersection with preload
    dynamic_lower: float  # Minimum expected depth (conservative)
    dynamic_upper: float  # Maximum expected depth (conservative)
    final_range: str  # Human-readable range
    warnings: List[str]  # Engineering warnings
    punch_through_zones: List[Tuple[float, float]]  # (start, end) depths
    re_entry_possible: bool  # Whether multiple penetrations are feasible
    recommended_design_depth: float  # Conservative value for design


def analyze_penetration_enhanced(
    df: pd.DataFrame,
    preload_MN: float,
    tip_offset_m: float = 0.0,
    overshoot_factor: float = 0.10,  # 10% overshoot for inertia
    max_overshoot_m: float = 3.0,  # Maximum 3m overshoot
    reentry_strength_threshold: float = 2.0  # 2x strength prevents re-entry
) -> PenetrationPrediction:
    """
    Enhanced penetration prediction with failure mode analysis.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Output from compute_envelopes() with V4 failure columns
    preload_MN : float
        Preload per leg in MN
    tip_offset_m : float
        Distance from tip to widest section
    overshoot_factor : float
        Fraction of depth for overshoot estimation (default 10%)
    max_overshoot_m : float
        Maximum overshoot distance in meters
    reentry_strength_threshold : float
        Strength ratio above which re-entry is considered impossible
    
    Returns:
    --------
    PenetrationPrediction
        Enhanced prediction with ranges and warnings
    """
    
    warnings = []
    punch_through_zones = []
    
    # Step 1: Find all intersections with preload line
    intersections = _find_all_intersections(df, preload_MN)
    
    if not intersections:
        # No intersection found - preload too high
        max_capacity = df['real_MN'].max()
        warnings.append(f"⚠️ Preload ({preload_MN:.1f} MN) exceeds maximum capacity ({max_capacity:.1f} MN)")
        warnings.append("Spudcan will penetrate to maximum analyzed depth")
        
        return PenetrationPrediction(
            static_depth=df['depth'].max(),
            dynamic_lower=df['depth'].max(),
            dynamic_upper=df['depth'].max(),
            final_range=f"> {df['depth'].max():.1f}m (exceeds analysis depth)",
            warnings=warnings,
            punch_through_zones=[],
            re_entry_possible=False,
            recommended_design_depth=df['depth'].max()
        )
    
    # First intersection (static equilibrium prediction)
    first_depth = intersections[0]
    
    # Step 2: Check for punch-through zones near first intersection
    punch_zones = _find_punch_through_zones_after(df, first_depth, distance_ahead=10.0)
    
    if punch_zones:
        for pz_start, pz_end in punch_zones:
            punch_through_zones.append((pz_start, pz_end))
            
            # Check if punch-through is imminent (within 2m)
            if pz_start - first_depth < 2.0:
                warnings.append(f"🚨 PUNCH-THROUGH ZONE at {pz_start:.1f}-{pz_end:.1f}m (just below predicted depth)")
                warnings.append("   → Breakthrough likely - expect penetration to end of weak zone")
                
                # Adjust upper bound to end of punch-through zone
                dynamic_upper = pz_end
                dynamic_lower = first_depth
                
                return PenetrationPrediction(
                    static_depth=first_depth,
                    dynamic_lower=dynamic_lower,
                    dynamic_upper=dynamic_upper,
                    final_range=f"{dynamic_lower:.1f} to {dynamic_upper:.1f}m",
                    warnings=warnings,
                    punch_through_zones=punch_through_zones,
                    re_entry_possible=False,
                    recommended_design_depth=dynamic_upper  # Use upper bound for design
                )
    
    # Step 3: Check for overshoot into strong layer
    estimated_overshoot = min(first_depth * overshoot_factor, max_overshoot_m)
    
    # Check soil strength just below first intersection
    below_zone = df[(df['depth'] > first_depth) & 
                    (df['depth'] <= first_depth + estimated_overshoot)]
    
    if not below_zone.empty:
        avg_capacity_below = below_zone['real_MN'].mean()
        strength_ratio = avg_capacity_below / preload_MN
        
        if strength_ratio > 1.5:  # Strong soil below
            warnings.append(f"ℹ️ Strong soil below first intersection (capacity {strength_ratio:.1f}x preload)")
            warnings.append(f"   → Minimal overshoot expected: ~{estimated_overshoot:.1f}m")
            
            dynamic_upper = first_depth + estimated_overshoot
        else:
            # Weak soil below - might penetrate deeper
            dynamic_upper = first_depth + 2.0 * estimated_overshoot
            warnings.append(f"⚠️ Weak soil continues below - deeper penetration possible")
    else:
        dynamic_upper = first_depth + estimated_overshoot
    
    dynamic_lower = first_depth
    
    # Step 4: Check for re-entry scenarios (multiple intersections)
    if len(intersections) > 1:
        second_depth = intersections[1]
        
        # Analyze soil between first and second intersections
        between_zone = df[(df['depth'] > first_depth) & 
                         (df['depth'] < second_depth)]
        
        if not between_zone.empty:
            avg_capacity_between = between_zone['real_MN'].mean()
            strength_ratio_between = avg_capacity_between / preload_MN
            
            if strength_ratio_between > reentry_strength_threshold:
                # Strong layer prevents re-entry
                warnings.append(f"✓ Re-entry prevented by strong layer ({strength_ratio_between:.1f}x preload)")
                warnings.append(f"   → Capacity at {first_depth:.1f}-{second_depth:.1f}m too high for penetration")
                warnings.append(f"   → Final depth: {dynamic_lower:.1f} to {dynamic_upper:.1f}m")
                
                re_entry_possible = False
            else:
                # Weak layer - re-entry possible
                warnings.append(f"⚠️ MULTIPLE WEAK ZONES DETECTED")
                warnings.append(f"   → First intersection: {first_depth:.1f}m")
                warnings.append(f"   → Second intersection: {second_depth:.1f}m")
                warnings.append(f"   → Intermediate strength only {strength_ratio_between:.1f}x preload")
                warnings.append(f"   → Deeper penetration to {second_depth:.1f}m is possible")
                
                dynamic_upper = second_depth
                re_entry_possible = True
        else:
            re_entry_possible = False
    else:
        re_entry_possible = False
    
    # Step 5: Check for squeezing zones
    squeezing_depths = df[df['squeezing_active'] == 'YES']['depth'].values
    if len(squeezing_depths) > 0:
        sq_in_range = squeezing_depths[(squeezing_depths >= dynamic_lower) & 
                                       (squeezing_depths <= dynamic_upper)]
        if len(sq_in_range) > 0:
            warnings.append(f"⚠️ Squeezing detected in predicted range ({sq_in_range.min():.1f}-{sq_in_range.max():.1f}m)")
            warnings.append("   → Monitor penetration rate during installation")
    
    # Step 6: Final recommendations
    final_range = f"{dynamic_lower:.1f} to {dynamic_upper:.1f}m"
    recommended_depth = dynamic_upper  # Conservative choice
    
    # Add summary
    if dynamic_upper - dynamic_lower < 1.0:
        warnings.append(f"✓ Narrow prediction range ({dynamic_upper - dynamic_lower:.1f}m) - high confidence")
    elif dynamic_upper - dynamic_lower < 3.0:
        warnings.append(f"ℹ️ Moderate prediction range ({dynamic_upper - dynamic_lower:.1f}m) - typical variability")
    else:
        warnings.append(f"⚠️ Large prediction range ({dynamic_upper - dynamic_lower:.1f}m) - consider additional analysis")
    
    return PenetrationPrediction(
        static_depth=first_depth,
        dynamic_lower=dynamic_lower,
        dynamic_upper=dynamic_upper,
        final_range=final_range,
        warnings=warnings,
        punch_through_zones=punch_through_zones,
        re_entry_possible=re_entry_possible,
        recommended_design_depth=recommended_depth
    )


def _find_all_intersections(df: pd.DataFrame, preload_MN: float) -> List[float]:
    """Find all depths where capacity crosses preload line."""
    
    depths = df['depth'].values
    capacity = df['real_MN'].values
    
    # Remove NaN values
    mask = ~np.isnan(capacity)
    depths = depths[mask]
    capacity = capacity[mask]
    
    if len(capacity) < 2:
        return []
    
    intersections = []
    
    # Find crossings from below to above
    for i in range(len(capacity) - 1):
        if capacity[i] < preload_MN <= capacity[i+1]:
            # Linear interpolation to find exact crossing
            if capacity[i+1] != capacity[i]:
                frac = (preload_MN - capacity[i]) / (capacity[i+1] - capacity[i])
                crossing_depth = depths[i] + frac * (depths[i+1] - depths[i])
                intersections.append(crossing_depth)
    
    return intersections


def _find_punch_through_zones_after(
    df: pd.DataFrame, 
    start_depth: float, 
    distance_ahead: float = 10.0
) -> List[Tuple[float, float]]:
    """
    Find punch-through zones within distance_ahead of start_depth.
    
    Returns list of (start_depth, end_depth) tuples for each zone.
    """
    
    # Get data within range
    search_zone = df[(df['depth'] >= start_depth) & 
                     (df['depth'] <= start_depth + distance_ahead)]
    
    zones = []
    
    # Check for clay/clay punch-through
    cc_active = search_zone[search_zone['punch_clay_clay_active'] == 'YES']
    if not cc_active.empty:
        zones.append((cc_active['depth'].min(), cc_active['depth'].max()))
    
    # Check for sand/clay punch-through
    sc_active = search_zone[search_zone['punch_sand_clay_active'] == 'YES']
    if not sc_active.empty:
        zones.append((sc_active['depth'].min(), sc_active['depth'].max()))
    
    # Merge overlapping zones
    if zones:
        zones = _merge_overlapping_zones(zones)
    
    return zones


def _merge_overlapping_zones(zones: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Merge overlapping depth ranges."""
    
    if not zones:
        return []
    
    # Sort by start depth
    zones = sorted(zones, key=lambda x: x[0])
    
    merged = [zones[0]]
    
    for current in zones[1:]:
        last = merged[-1]
        
        # Check for overlap
        if current[0] <= last[1]:
            # Merge
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            # No overlap
            merged.append(current)
    
    return merged


# ============================================================================
# STREAMLIT DISPLAY FUNCTIONS
# ============================================================================

def display_penetration_results_enhanced(prediction: PenetrationPrediction, tip_offset: float):
    """Display enhanced penetration results in Streamlit."""
    
    import streamlit as st
    
    st.subheader("📍 Enhanced Penetration Prediction")
    
    # Main results
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Static Prediction", f"{prediction.static_depth:.2f} m",
                 help="First intersection with preload line (equilibrium)")
    
    with col2:
        st.metric("Dynamic Range", prediction.final_range,
                 help="Expected range considering dynamic effects")
    
    with col3:
        st.metric("Design Depth", f"{prediction.recommended_design_depth:.2f} m",
                 help="Conservative value for foundation design",
                 delta=f"+{prediction.recommended_design_depth - prediction.static_depth:.2f}m")
    
    # Tip penetration
    st.write("---")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.write("**Widest Section Penetration:**")
        st.write(f"- Static: {prediction.static_depth:.2f} m")
        st.write(f"- Range: {prediction.dynamic_lower:.2f} to {prediction.dynamic_upper:.2f} m")
    
    with col_b:
        st.write("**Tip Penetration:**")
        tip_static = prediction.static_depth + tip_offset
        tip_lower = prediction.dynamic_lower + tip_offset
        tip_upper = prediction.dynamic_upper + tip_offset
        st.write(f"- Static: {tip_static:.2f} m")
        st.write(f"- Range: {tip_lower:.2f} to {tip_upper:.2f} m")
    
    # Warnings and recommendations
    if prediction.warnings:
        st.write("---")
        st.write("**Engineering Warnings & Recommendations:**")
        
        for warning in prediction.warnings:
            if "🚨" in warning:
                st.error(warning)
            elif "⚠️" in warning:
                st.warning(warning)
            elif "ℹ️" in warning or "✓" in warning:
                st.info(warning)
            else:
                st.write(warning)
    
    # Punch-through zones
    if prediction.punch_through_zones:
        st.write("---")
        st.write("**Detected Punch-Through Zones:**")
        for i, (start, end) in enumerate(prediction.punch_through_zones, 1):
            st.write(f"{i}. Depth {start:.1f}m to {end:.1f}m (thickness: {end-start:.1f}m)")
    
    # Re-entry analysis
    if prediction.re_entry_possible:
        st.write("---")
        st.error("🚨 **MULTIPLE PENETRATION DEPTHS POSSIBLE**")
        st.write("Multiple weak zones detected. Further analysis recommended.")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage_in_app():
    """
    Example of how to use this in your app_ui_v2.py
    
    Add this after computing the envelope:
    """
    
    # After running compute_envelopes():
    # df = compute_envelopes(spud, layers, max_depth=50.0)
    
    # Use enhanced prediction instead of basic penetration_results()
    from enhanced_penetration_prediction import (
        analyze_penetration_enhanced, 
        display_penetration_results_enhanced
    )
    
    # Get enhanced prediction
    prediction = analyze_penetration_enhanced(
        df=df,
        preload_MN=spud.preload_MN,
        tip_offset_m=spud.tip_elev,
        overshoot_factor=0.10,  # 10% overshoot
        max_overshoot_m=3.0,  # Max 3m
        reentry_strength_threshold=2.0  # 2x strength prevents re-entry
    )
    
    # Display results
    display_penetration_results_enhanced(prediction, spud.tip_elev)
    
    # Still create the plot
    from improved_plotting_v4 import create_streamlit_plot_with_controls
    create_streamlit_plot_with_controls(df, spud, prediction)
