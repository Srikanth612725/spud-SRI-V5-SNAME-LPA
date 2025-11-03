"""
lpa_v50_v4.py - Version 4 (Enhanced with Failure Mode Detection)
=================================================================

All V3 features PLUS:
- Punch-through detection (clay/clay and sand/clay)
- Squeezing detection with depth ranges
- Enhanced DataFrame output with YES/NO indicators

VERSION 4 ENHANCEMENTS:
1. detect_failure_modes() - Identifies squeezing/punch-through events
2. Enhanced CSV output with clear YES/NO columns
3. Depth ranges for each failure mode
4. Improved reporting for engineering analysis

All SNAME compliance corrections from V3 are preserved.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import numpy as np
import pandas as pd
from scipy import interpolate

# ---------------- Version 50 switches (user-togglable from UI) ----------------
USE_MIN_CU_POINT_AVG_DEFAULT = True
APPLY_PHI_REDUCTION_DEFAULT   = False
APPLY_WINDWARD_FACTOR_DEFAULT = False
APPLY_SQUEEZE_TRIGGER_DEFAULT = True

# ---------------- SNAME Nc' Tables C6.1 to C6.6 ----------------
# [Same tables as V3 - included for completeness]
NC_PRIME_TABLES = {
    30: np.array([
        [0, 0.0, 5.51, 6.38, 7.22, 8.03, 8.78, np.nan],
        [0, 0.2, 5.70, 6.56, 7.40, 8.20, 8.95, np.nan],
        [0, 0.5, 5.94, 6.80, 7.63, 8.43, 9.18, np.nan],
        [0, 1.0, 6.29, 7.14, 7.79, 8.76, 9.50, np.nan],
        [0, 2.0, 6.85, 7.70, 8.51, 9.29, 10.03, np.nan],
        [0, 5.0, 7.98, 8.81, 9.61, 10.38, 11.10, np.nan],
        [1, 0.0, 9.02, 10.46, 11.84, 13.19, 14.46, np.nan],
        [1, 0.2, 8.89, 10.27, 11.61, 12.90, 14.13, np.nan],
        [1, 0.5, 8.73, 10.05, 11.32, 12.55, 13.72, np.nan],
        [1, 1.0, 8.55, 9.78, 10.98, 12.14, 13.24, np.nan],
        [1, 2.0, 8.38, 9.51, 10.61, 11.68, 12.68, np.nan],
        [1, 5.0, 8.39, 9.39, 10.37, 11.30, 12.19, np.nan],
        [2, 0.0, 12.51, 14.51, 16.44, 18.31, 20.10, np.nan],
        [2, 0.2, 11.53, 13.33, 15.08, 16.79, 18.40, np.nan],
        [2, 0.5, 10.58, 12.19, 13.76, 15.27, 16.72, np.nan],
        [2, 1.0, 9.67, 11.09, 12.47, 13.80, 15.08, np.nan],
        [2, 2.0, 8.87, 10.10, 11.30, 12.45, 13.54, np.nan],
        [2, 5.0, 8.44, 9.48, 10.18, 11.44, 12.35, np.nan],
        [3, 0.0, 15.98, 18.56, 21.03, 23.42, 25.71, np.nan],
        [3, 0.2, 13.76, 15.92, 18.02, 20.05, 22.00, np.nan],
        [3, 0.5, 11.89, 13.72, 15.49, 17.21, 18.85, np.nan],
        [3, 1.0, 10.33, 11.87, 13.36, 14.80, 16.18, np.nan],
        [3, 2.0, 9.11, 10.39, 11.64, 12.83, 13.98, np.nan],
        [3, 5.0, 8.46, 9.51, 10.52, 11.49, 12.42, np.nan],
        [4, 0.0, 19.46, 22.57, 25.62, 28.52, 31.32, np.nan],
        [4, 0.2, 15.68, 18.14, 20.54, 22.86, 25.08, np.nan],
        [4, 0.5, 12.87, 14.86, 16.79, 18.66, 20.44, np.nan],
        [4, 1.0, 10.77, 12.38, 13.96, 15.47, 16.91, np.nan],
        [4, 2.0, 9.26, 10.57, 11.84, 13.06, 14.23, np.nan],
        [4, 5.0, 8.47, 9.52, 10.54, 11.52, 12.46, np.nan],
        [5, 0.0, 22.94, 26.61, 30.20, 33.63, 36.92, np.nan],
        [5, 0.2, 17.33, 20.06, 22.72, 25.29, 27.75, np.nan],
        [5, 0.5, 13.64, 15.75, 17.80, 19.78, 21.68, np.nan],
        [5, 1.0, 11.08, 12.77, 14.38, 15.94, 17.43, np.nan],
        [5, 2.0, 9.35, 10.68, 11.97, 13.21, 14.40, np.nan],
        [5, 5.0, 8.47, 9.53, 10.56, 11.55, 12.48, np.nan],
    ]),
    60: np.array([
        [0, 0.0, 4.96, 5.45, 5.90, 6.32, 6.69, np.nan],
        [0, 0.2, 5.19, 5.67, 6.12, 6.53, 6.90, np.nan],
        [0, 0.5, 5.50, 5.96, 6.40, 6.81, 7.18, np.nan],
        [0, 1.0, 5.90, 6.37, 6.81, 7.21, 7.57, np.nan],
        [0, 2.0, 6.55, 7.01, 7.43, 7.84, 8.18, np.nan],
        [0, 5.0, 7.81, 8.25, 8.66, 9.05, 9.39, np.nan],
        [1, 0.0, 6.51, 7.15, 7.77, 8.34, 8.87, np.nan],
        [1, 0.2, 6.59, 7.23, 7.83, 8.38, 8.89, np.nan],
        [1, 0.5, 6.70, 7.30, 7.88, 8.42, 8.91, np.nan],
        [1, 1.0, 6.84, 7.41, 7.96, 8.47, 8.94, np.nan],
        [1, 2.0, 7.05, 7.58, 8.12, 8.59, 9.03, np.nan],
        [1, 5.0, 7.55, 8.08, 8.54, 8.98, 9.39, np.nan],
        [2, 0.0, 8.02, 8.84, 9.60, 10.32, 10.99, np.nan],
        [2, 0.2, 7.73, 8.49, 9.21, 9.88, 10.50, np.nan],
        [2, 0.5, 7.50, 8.18, 8.84, 9.46, 10.03, np.nan],
        [2, 1.0, 7.29, 7.91, 8.53, 9.09, 9.61, np.nan],
        [2, 2.0, 7.20, 7.76, 8.33, 8.83, 9.30, np.nan],
        [2, 5.0, 7.49, 8.03, 8.50, 8.95, 9.37, np.nan],
        [3, 0.0, 9.54, 10.50, 11.42, 12.29, 13.10, np.nan],
        [3, 0.2, 8.70, 9.56, 10.38, 11.14, 11.85, np.nan],
        [3, 0.5, 8.03, 8.80, 9.53, 10.20, 10.82, np.nan],
        [3, 1.0, 7.56, 8.21, 8.86, 9.45, 10.00, np.nan],
        [3, 2.0, 7.27, 7.85, 8.44, 8.94, 9.43, np.nan],
        [3, 5.0, 7.47, 8.01, 8.49, 8.94, 9.36, np.nan],
        [4, 0.0, 11.02, 12.16, 13.24, 14.26, 15.18, np.nan],
        [4, 0.2, 9.52, 10.48, 11.38, 12.22, 13.00, np.nan],
        [4, 0.5, 8.44, 9.26, 10.04, 10.75, 11.41, np.nan],
        [4, 1.0, 7.74, 8.41, 9.08, 9.69, 10.26, np.nan],
        [4, 2.0, 7.31, 7.90, 8.49, 9.01, 9.51, np.nan],
        [4, 5.0, 7.45, 8.00, 8.48, 8.94, 9.35, np.nan],
        [5, 0.0, 12.52, 13.83, 15.06, 16.20, 17.26, np.nan],
        [5, 0.2, 10.23, 11.26, 12.25, 13.15, 13.99, np.nan],
        [5, 0.5, 8.78, 9.63, 10.43, 11.17, 11.87, np.nan],
        [5, 1.0, 7.84, 8.55, 9.24, 9.86, 10.45, np.nan],
        [5, 2.0, 7.32, 7.94, 8.53, 9.06, 9.56, np.nan],
        [5, 5.0, 7.44, 7.99, 8.47, 8.93, 9.35, np.nan],
    ]),
    90: np.array([
        [0, 0.0, 5.02, 5.36, 5.67, 5.95, 6.17, np.nan],
        [0, 0.2, 5.28, 5.61, 5.91, 6.18, 6.41, np.nan],
        [0, 0.5, 5.59, 5.93, 6.23, 6.49, 6.71, np.nan],
        [0, 1.0, 6.03, 6.36, 6.66, 6.92, 7.14, np.nan],
        [0, 2.0, 6.71, 7.05, 7.32, 7.58, 7.79, np.nan],
        [0, 5.0, 8.03, 8.32, 8.60, 8.86, 9.05, np.nan],
        [1, 0.0, 6.05, 6.47, 6.87, 7.22, 7.53, np.nan],
        [1, 0.2, 6.21, 6.62, 7.00, 7.36, 7.65, np.nan],
        [1, 0.5, 6.38, 6.79, 7.16, 7.50, 7.79, np.nan],
        [1, 1.0, 6.61, 6.99, 7.36, 7.68, 7.97, np.nan],
        [1, 2.0, 6.93, 7.30, 7.64, 7.95, 8.21, np.nan],
        [1, 5.0, 7.57, 7.94, 8.25, 8.53, 8.78, np.nan],
        [2, 0.0, 7.03, 7.54, 8.01, 8.45, 8.82, np.nan],
        [2, 0.2, 6.94, 7.43, 7.88, 8.28, 8.65, np.nan],
        [2, 0.5, 6.88, 7.35, 7.76, 8.14, 8.46, np.nan],
        [2, 1.0, 6.88, 7.29, 7.69, 8.03, 8.35, np.nan],
        [2, 2.0, 6.99, 7.37, 7.73, 8.06, 8.33, np.nan],
        [2, 5.0, 7.49, 7.86, 8.18, 8.47, 8.72, np.nan],
        [3, 0.0, 8.00, 8.59, 9.14, 9.65, 10.08, np.nan],
        [3, 0.2, 7.57, 8.10, 8.60, 9.05, 9.45, np.nan],
        [3, 0.5, 7.24, 7.73, 8.17, 8.59, 8.94, np.nan],
        [3, 1.0, 7.04, 7.47, 7.88, 8.24, 8.57, np.nan],
        [3, 2.0, 7.02, 7.41, 7.78, 8.11, 8.39, np.nan],
        [3, 5.0, 7.46, 7.83, 8.15, 8.44, 8.46, np.nan],
        [4, 0.0, 8.96, 9.64, 10.25, 10.82, 11.33, np.nan],
        [4, 0.2, 8.11, 8.68, 9.22, 9.70, 10.14, np.nan],
        [4, 0.5, 7.50, 8.01, 8.48, 8.92, 9.29, np.nan],
        [4, 1.0, 7.15, 7.58, 8.01, 8.38, 8.72, np.nan],
        [4, 2.0, 7.03, 7.43, 7.80, 8.14, 8.42, np.nan],
        [4, 5.0, 7.44, 7.81, 8.13, 8.42, 8.67, np.nan],
        [5, 0.0, 9.93, 10.66, 11.35, 12.00, 12.56, np.nan],
        [5, 0.2, 8.55, 9.17, 9.74, 10.26, 10.75, np.nan],
        [5, 0.5, 7.71, 8.24, 8.72, 9.17, 9.57, np.nan],
        [5, 1.0, 7.22, 7.67, 8.09, 8.47, 8.82, np.nan],
        [5, 2.0, 7.04, 7.44, 7.82, 8.16, 8.44, np.nan],
        [5, 5.0, 7.42, 7.80, 8.12, 8.41, 8.66, np.nan],
    ]),
    120: np.array([
        [0, 0.0, 5.25, 5.51, 5.73, 5.92, 6.05, np.nan],
        [0, 0.2, 5.52, 5.77, 5.99, 6.17, 6.30, np.nan],
        [0, 0.5, 5.85, 6.10, 6.31, 6.49, 6.62, np.nan],
        [0, 1.0, 6.31, 6.55, 6.76, 6.93, 7.05, np.nan],
        [0, 2.0, 7.01, 7.24, 7.44, 7.61, 7.72, np.nan],
        [0, 5.0, 8.32, 8.55, 8.75, 8.90, 8.99, np.nan],
        [1, 0.0, 6.04, 6.36, 6.65, 6.89, 7.09, np.nan],
        [1, 0.2, 6.24, 6.55, 6.82, 7.07, 7.26, np.nan],
        [1, 0.5, 6.45, 6.76, 7.02, 7.26, 7.45, np.nan],
        [1, 1.0, 6.72, 7.01, 7.27, 7.48, 7.66, np.nan],
        [1, 2.0, 7.10, 7.37, 7.61, 7.82, 7.97, np.nan],
        [1, 5.0, 7.82, 8.08, 8.29, 8.49, 8.61, np.nan],
        [2, 0.0, 6.79, 7.16, 7.50, 7.80, 8.04, np.nan],
        [2, 0.2, 6.80, 7.16, 7.47, 7.75, 7.97, np.nan],
        [2, 0.5, 6.83, 7.17, 7.46, 7.72, 7.94, np.nan],
        [2, 1.0, 6.91, 7.22, 7.49, 7.74, 7.92, np.nan],
        [2, 2.0, 7.12, 7.40, 7.65, 7.87, 8.03, np.nan],
        [2, 5.0, 7.72, 7.99, 8.21, 8.41, 8.53, np.nan],
        [3, 0.0, 7.51, 7.93, 8.31, 8.66, 8.93, np.nan],
        [3, 0.2, 7.27, 7.65, 8.00, 8.31, 8.57, np.nan],
        [3, 0.5, 7.09, 7.45, 7.76, 8.05, 8.27, np.nan],
        [3, 1.0, 7.02, 7.34, 7.63, 7.88, 8.08, np.nan],
        [3, 2.0, 7.11, 7.41, 7.67, 7.89, 8.06, np.nan],
        [3, 5.0, 7.68, 7.95, 8.17, 8.38, 8.51, np.nan],
        [4, 0.0, 8.22, 8.69, 9.11, 9.49, 9.81, np.nan],
        [4, 0.2, 7.66, 8.07, 8.44, 8.77, 9.03, np.nan],
        [4, 0.5, 7.28, 7.65, 7.98, 8.27, 8.53, np.nan],
        [4, 1.0, 7.08, 7.42, 7.71, 7.97, 8.18, np.nan],
        [4, 2.0, 7.12, 7.41, 7.68, 7.90, 8.08, np.nan],
        [4, 5.0, 7.66, 7.93, 8.15, 8.36, 8.49, np.nan],
        [5, 0.0, 8.91, 9.43, 9.89, 10.31, 10.67, np.nan],
        [5, 0.2, 7.99, 8.43, 8.82, 9.18, 9.95, np.nan],
        [5, 0.5, 7.43, 7.81, 8.15, 8.45, 8.72, np.nan],
        [5, 1.0, 7.13, 7.47, 7.77, 8.03, 8.25, np.nan],
        [5, 2.0, 7.12, 7.42, 7.69, 7.91, 8.09, np.nan],
        [5, 5.0, 7.64, 7.91, 8.14, 8.34, 8.48, np.nan],
    ]),
    150: np.array([
        [0, 0.0, 5.55, 5.74, 5.89, 6.01, 6.05, np.nan],
        [0, 0.2, 5.82, 6.00, 6.16, 6.26, 6.30, np.nan],
        [0, 0.5, 6.16, 6.34, 6.49, 6.59, 6.61, np.nan],
        [0, 1.0, 6.62, 6.80, 6.94, 7.03, 7.05, np.nan],
        [0, 2.0, 7.32, 7.49, 7.62, 7.71, 7.72, np.nan],
        [0, 5.0, 8.65, 8.81, 8.93, 8.99, 8.99, np.nan],
        [1, 0.0, 6.22, 6.46, 6.67, 6.84, 6.97, np.nan],
        [1, 0.2, 6.43, 6.67, 6.87, 7.04, 7.15, np.nan],
        [1, 0.5, 6.67, 6.90, 7.09, 7.25, 7.36, np.nan],
        [1, 1.0, 6.96, 7.18, 7.36, 7.51, 7.60, np.nan],
        [1, 2.0, 7.36, 7.57, 7.73, 7.86, 7.95, np.nan],
        [1, 5.0, 8.12, 8.31, 8.44, 8.56, 8.61, np.nan],
        [2, 0.0, 6.82, 7.11, 7.35, 7.57, 7.73, np.nan],
        [2, 0.2, 6.90, 7.16, 7.40, 7.59, 7.74, np.nan],
        [2, 0.5, 6.98, 7.23, 7.45, 7.63, 7.76, np.nan],
        [2, 1.0, 7.10, 7.34, 7.54, 7.70, 7.82, np.nan],
        [2, 2.0, 7.35, 7.57, 7.74, 7.89, 7.99, np.nan],
        [2, 5.0, 8.01, 8.21, 8.35, 8.47, 8.53, np.nan],
        [3, 0.0, 7.40, 7.72, 7.98, 8.24, 8.43, np.nan],
        [3, 0.2, 7.27, 7.56, 7.81, 8.03, 8.21, np.nan],
        [3, 0.5, 7.18, 7.45, 7.68, 7.88, 8.03, np.nan],
        [3, 1.0, 7.18, 7.43, 7.63, 7.81, 7.94, np.nan],
        [3, 2.0, 7.35, 7.57, 7.75, 7.90, 8.00, np.nan],
        [3, 5.0, 7.97, 8.16, 8.31, 8.43, 8.49, np.nan],
        [4, 0.0, 7.94, 8.30, 8.58, 8.88, 9.10, np.nan],
        [4, 0.2, 7.58, 7.89, 8.16, 8.40, 8.59, np.nan],
        [4, 0.5, 7.34, 7.62, 7.86, 8.07, 8.23, np.nan],
        [4, 1.0, 7.23, 7.49, 7.70, 7.88, 8.01, np.nan],
        [4, 2.0, 7.34, 7.56, 7.75, 7.90, 8.00, np.nan],
        [4, 5.0, 7.94, 8.13, 8.29, 8.41, 8.47, np.nan],
        [5, 0.0, 8.48, 8.86, 9.19, 9.48, 9.74, np.nan],
        [5, 0.2, 7.83, 8.16, 8.44, 8.69, 8.90, np.nan],
        [5, 0.5, 7.45, 7.74, 7.99, 8.20, 8.37, np.nan],
        [5, 1.0, 7.27, 7.53, 7.74, 7.93, 8.07, np.nan],
        [5, 2.0, 7.34, 7.56, 7.75, 7.91, 8.01, np.nan],
        [5, 5.0, 7.93, 8.12, 8.27, 8.40, 8.46, np.nan],
    ]),
    180: np.array([
        [0, 0.0, 5.86, 5.97, 6.03, 6.05, 6.05, np.nan],
        [0, 0.2, 6.13, 6.24, 6.29, 6.30, 6.30, np.nan],
        [0, 0.5, 6.47, 6.57, 6.61, 6.61, 6.61, np.nan],
        [0, 1.0, 6.93, 7.02, 7.05, 7.05, 7.05, np.nan],
        [0, 2.0, 7.63, 7.70, 7.71, 7.71, 7.71, np.nan],
        [0, 5.0, 8.94, 8.99, 8.99, 8.99, 8.99, np.nan],
        [1, 0.0, 6.47, 6.65, 6.79, 6.90, 6.95, np.nan],
        [1, 0.2, 6.69, 6.87, 7.00, 7.10, 7.14, np.nan],
        [1, 0.5, 6.94, 7.11, 7.23, 7.32, 7.35, np.nan],
        [1, 1.0, 7.24, 7.39, 7.51, 7.58, 7.60, np.nan],
        [1, 2.0, 7.64, 7.79, 7.88, 7.93, 7.94, np.nan],
        [1, 5.0, 8.32, 8.52, 8.60, 8.61, 8.61, np.nan],
        [2, 0.0, 6.98, 7.20, 7.39, 7.53, 7.63, np.nan],
        [2, 0.2, 7.08, 7.30, 7.46, 7.59, 7.68, np.nan],
        [2, 0.5, 7.20, 7.39, 7.55, 7.66, 7.72, np.nan],
        [2, 1.0, 7.36, 7.53, 7.67, 7.76, 7.80, np.nan],
        [2, 2.0, 7.63, 7.78, 7.90, 7.96, 7.98, np.nan],
        [2, 5.0, 8.27, 8.43, 8.50, 8.53, 8.53, np.nan],
        [3, 0.0, 7.45, 7.69, 7.91, 8.08, 8.21, np.nan],
        [3, 0.2, 7.40, 7.62, 7.81, 7.96, 8.07, np.nan],
        [3, 0.5, 7.37, 7.58, 7.75, 7.88, 7.96, np.nan],
        [3, 1.0, 7.42, 7.61, 7.75, 7.86, 7.91, np.nan],
        [3, 2.0, 7.62, 7.78, 7.90, 7.97, 7.99, np.nan],
        [3, 5.0, 8.23, 8.38, 8.46, 8.49, 8.49, np.nan],
        [4, 0.0, 7.87, 8.15, 8.38, 8.58, 8.73, np.nan],
        [4, 0.2, 7.64, 7.89, 8.09, 8.26, 8.39, np.nan],
        [4, 0.5, 7.50, 7.71, 7.89, 8.03, 8.13, np.nan],
        [4, 1.0, 7.46, 7.65, 7.80, 7.92, 7.98, np.nan],
        [4, 2.0, 7.61, 7.77, 7.89, 7.97, 8.00, np.nan],
        [4, 5.0, 8.19, 8.36, 8.44, 8.47, 8.47, np.nan],
        [5, 0.0, 8.27, 8.57, 8.83, 9.05, 9.23, np.nan],
        [5, 0.2, 7.85, 8.10, 8.32, 8.50, 8.64, np.nan],
        [5, 0.5, 7.59, 7.81, 8.00, 8.15, 8.25, np.nan],
        [5, 1.0, 7.49, 7.68, 7.84, 7.96, 8.02, np.nan],
        [5, 2.0, 7.60, 7.77, 7.89, 7.97, 8.00, np.nan],
        [5, 5.0, 8.18, 8.35, 8.43, 8.46, 8.46, np.nan],
    ]),
}

ALPHA_VALUES = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])


def interpolate_nc_prime(beta: float, alpha: float, D_over_2R: float,
                        rho2R_over_cum: float) -> float:
    """Interpolate Nc' value from SNAME tables C6.1-C6.6."""
    beta = min(180, max(30, beta))
    alpha = min(1.0, max(0.0, alpha))
    D_over_2R = min(2.5, max(0.0, D_over_2R))
    rho2R_over_cum = min(5.0, max(0.0, rho2R_over_cum))
    
    available_betas = sorted(NC_PRIME_TABLES.keys())
    if beta in available_betas:
        beta_lower = beta_upper = beta
    else:
        beta_upper = min([b for b in available_betas if b >= beta])
        beta_lower = max([b for b in available_betas if b <= beta])
    
    def get_nc_for_beta(b: float) -> float:
        table = NC_PRIME_TABLES[int(b)]
        rho_vals = np.unique(table[:, 0])
        D_vals = np.unique(table[:, 1])
        nc_grid = np.zeros((len(rho_vals), len(D_vals)))
        
        for i, rho in enumerate(rho_vals):
            for j, D in enumerate(D_vals):
                row_mask = (table[:, 0] == rho) & (table[:, 1] == D)
                if not np.any(row_mask):
                    continue
                
                row = table[row_mask][0]
                nc_values = row[2:8]
                valid_mask = ~np.isnan(nc_values)
                if np.any(valid_mask):
                    valid_alphas = ALPHA_VALUES[valid_mask]
                    valid_ncs = nc_values[valid_mask]
                    
                    if alpha <= valid_alphas[0]:
                        nc_grid[i, j] = valid_ncs[0]
                    elif alpha >= valid_alphas[-1]:
                        nc_grid[i, j] = valid_ncs[-1]
                    else:
                        nc_grid[i, j] = np.interp(alpha, valid_alphas, valid_ncs)
        
        interp_func = interpolate.RectBivariateSpline(rho_vals, D_vals, nc_grid, kx=1, ky=1)
        return float(interp_func(rho2R_over_cum, D_over_2R)[0, 0])
    
    nc_lower = get_nc_for_beta(beta_lower)
    if beta_lower == beta_upper:
        return nc_lower
    
    nc_upper = get_nc_for_beta(beta_upper)
    beta_ratio = (beta - beta_lower) / (beta_upper - beta_lower)
    return nc_lower + beta_ratio * (nc_upper - nc_lower)


# ---------------- Data models ----------------
@dataclass
class Spudcan:
    rig_name: str
    B: float
    A: float
    tip_elev: float
    preload_MN: float
    beta: Optional[float] = None
    alpha: Optional[float] = None

@dataclass
class SoilPoint:
    z: float
    v: float

@dataclass
class SoilLayer:
    name: str
    z_top: float
    z_bot: float
    soil_type: str
    gamma: List[SoilPoint] = field(default_factory=list)
    su:    List[SoilPoint] = field(default_factory=list)
    phi:   List[SoilPoint] = field(default_factory=list)

# ---------------- Helpers ----------------
def _interp(depth: float, prof: List[SoilPoint]) -> float:
    if not prof:
        return np.nan
    prof = sorted(prof, key=lambda p: p.z)
    if depth <= prof[0].z:
        return prof[0].v
    for i in range(1, len(prof)):
        if depth <= prof[i].z:
            z1, v1 = prof[i-1].z, prof[i-1].v
            z2, v2 = prof[i].z, prof[i].v
            if z2 == z1:
                return v1
            return v1 + (depth - z1) * (v2 - v1) / (z2 - z1)
    return prof[-1].v

def _avg_over(z1: float, z2: float, prof: List[SoilPoint], dz: float = 0.05) -> float:
    if not prof or z2 <= z1:
        return np.nan
    zs = np.arange(z1, z2 + 1e-9, dz)
    vals = np.array([_interp(z, prof) for z in zs], dtype=float)
    vals = vals[~np.isnan(vals)]
    return float(vals.mean()) if vals.size else np.nan

def _layer_index(z: float, layers: List[SoilLayer]) -> int:
    for i, L in enumerate(layers):
        if L.z_top <= z < L.z_bot:
            return i
    return len(layers) - 1

def _has_su_here(z: float, layers: List[SoilLayer]) -> bool:
    i = _layer_index(z, layers)
    val = _interp(z, layers[i].su)
    return np.isfinite(val) and val > 0

def _has_phi_here(z: float, layers: List[SoilLayer]) -> bool:
    i = _layer_index(z, layers)
    val = _interp(z, layers[i].phi)
    return np.isfinite(val) and val > 0

def _gamma_prime(z: float, layers: List[SoilLayer]) -> float:
    i = _layer_index(z, layers)
    return _interp(z, layers[i].gamma)

def _overburden(z: float, layers: List[SoilLayer], dz: float = 0.1) -> float:
    if z <= 0:
        return 0.0
    zs = np.arange(0.0, z + 1e-9, dz)
    gammas = np.array([_gamma_prime(zi, layers) for zi in zs], dtype=float)
    gammas[np.isnan(gammas)] = 0.0
    return float(np.trapz(gammas, zs))

def _calculate_rho_2R_over_cum(z: float, B: float, layers: List[SoilLayer]) -> float:
    c_um = _interp(0.0, layers[_layer_index(0.0, layers)].su)
    if not np.isfinite(c_um) or c_um <= 0:
        return 0.0
    
    z1 = z
    z2 = z + B / 2.0
    
    su1 = _interp(z1, layers[_layer_index(z1, layers)].su)
    su2 = _interp(z2, layers[_layer_index(z2, layers)].su)
    
    if not np.isfinite(su1) or not np.isfinite(su2):
        return 0.0
    
    rho = (su2 - su1) / max(z2 - z1, 1e-6)
    return float(rho * B / c_um)

_DEFAULT_MEYERHOF = pd.DataFrame({
    "D_over_B": [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0],
    "N":        [0.0,  2.0,  3.0,  3.6,  4.0,  4.7,  5.1],
})

def _meyerhof_N(d_over_B: float, table: Optional[pd.DataFrame]) -> float:
    df = table if table is not None else _DEFAULT_MEYERHOF
    x = np.asarray(df["D_over_B"], dtype=float)
    y = np.asarray(df["N"], dtype=float)
    if d_over_B <= x[0]:
        return float(y[0])
    if d_over_B >= x[-1]:
        return float(y[-1])
    j = np.searchsorted(x, d_over_B)
    x1, x2 = x[j-1], x[j]
    y1, y2 = y[j-1], y[j]
    return float(y1 + (d_over_B - x1) * (y2 - y1) / (x2 - x1))

def _Nq(phi_rad: float) -> float:
    return np.exp(np.pi * np.tan(phi_rad)) * np.tan(np.pi/4 + phi_rad/2)**2

def _Ngamma(phi_rad: float) -> float:
    return 2.0 * (_Nq(phi_rad) + 1.0) * np.tan(phi_rad)

# ---------------- Capacities (kN) ----------------
def clay_capacity(spud: Spudcan, z: float, layers: List[SoilLayer],
                  use_min_cu: bool, backflow_zero: bool) -> Optional[float]:
    B, A = spud.B, spud.A
    if B <= 0 or A <= 0:
        return None
    
    if z < spud.tip_elev:
        return 0.0
    
    i = _layer_index(z, layers)
    if not _has_su_here(z, layers):
        return None
    
    cu_point = _interp(z, layers[i].su)
    cu_avg   = _avg_over(z, z + B/2.0, layers[i].su)
    cu_eff   = np.nanmin([cu_point, cu_avg]) if use_min_cu else cu_avg
    
    if not np.isfinite(cu_eff) or cu_eff <= 0:
        return None
    
    if spud.beta is not None and spud.alpha is not None:
        D_over_2R = z / max(B/2.0, 1e-6)
        D_over_2R = min(D_over_2R, 2.5)
        rho2R_over_cum = _calculate_rho_2R_over_cum(z, B, layers)
        Nc = interpolate_nc_prime(spud.beta, spud.alpha, D_over_2R, rho2R_over_cum)
        sc = 1.2
        dc = 1.0
    else:
        Nc, sc = 5.14, 1.2
        if B > 0:
            d_over_B = z / B
            dc = 1.0 + 0.4 * d_over_B if d_over_B <= 1.0 else 1.0 + 0.4 * np.arctan(d_over_B)
        else:
            dc = 1.0
    
    p0 = 0.0 if backflow_zero else _overburden(z, layers)
    Fv = (cu_eff * Nc * sc * dc + p0) * A
    return float(Fv)

def sand_capacity(spud: Spudcan, z: float, layers: List[SoilLayer],
                  apply_phi_reduction: bool) -> Optional[float]:
    B, A = spud.B, spud.A
    if B <= 0 or A <= 0:
        return None
    
    if z < spud.tip_elev:
        return 0.0
    
    i = _layer_index(z, layers)
    if not _has_phi_here(z, layers):
        return None
    phi = _interp(z, layers[i].phi)
    if not np.isfinite(phi) or phi <= 0:
        return None
    if apply_phi_reduction:
        phi = max(0.0, phi - 5.0)
    phi_rad = np.deg2rad(phi)
    Nq = _Nq(phi_rad)
    Ng = _Ngamma(phi_rad)
    gamma_p = _gamma_prime(z, layers)
    p0 = _overburden(z, layers)
    sq, sg, dq, dg = 1.0 + np.tan(phi_rad), 0.6, 1.0 + 2.0*np.tan(phi_rad)*(1-np.sin(phi_rad))**2*(z/max(B,1e-6)), 1.0
    Fv = (0.5 * gamma_p * B * Ng * sg * dg + p0 * Nq * sq * dq) * A
    return float(max(Fv, 0.0))

def squeeze_capacity(spud: Spudcan, z: float, layers: List[SoilLayer],
                     enforce_trigger: bool, backflow_zero: bool) -> Optional[float]:
    if z < spud.tip_elev:
        return 0.0
    
    idx = _layer_index(z, layers)
    if idx + 1 >= len(layers):
        return None
    top, bot = layers[idx], layers[idx+1]
    if top.soil_type not in ("clay", "silt"):
        return None
    B, A = spud.B, spud.A
    cu_t = _avg_over(z, z + B/2.0, top.su)
    cu_b = _avg_over(top.z_bot, top.z_bot + B/2.0, bot.su)
    if not np.isfinite(cu_t) or not np.isfinite(cu_b):
        return None
    if cu_b <= 1.5 * cu_t:
        return None
    T = top.z_bot - z
    if T <= 0:
        return None
    if enforce_trigger:
        if B < 3.45 * T * (1.0 + 1.025 * (z / max(B,1e-6))):
            return None
    p0 = 0.0 if backflow_zero else _overburden(z, layers)
    Fv = A * ((5.0 + 0.33*(B/T) + 1.2*(z/max(B,1e-6))) * cu_t + p0)
    return float(Fv)

def punchthrough_capacity(spud: Spudcan, z: float, layers: List[SoilLayer],
                          backflow_zero: bool) -> Optional[float]:
    if z < spud.tip_elev:
        return 0.0
    
    idx = _layer_index(z, layers)
    if idx + 1 >= len(layers):
        return None
    top, bot = layers[idx], layers[idx+1]
    H = top.z_bot - z
    if H <= 0:
        return None
    B, A = spud.B, spud.A

    if top.soil_type in ("clay","silt") and bot.soil_type in ("clay","silt"):
        cu_t = _avg_over(z, z + B/2.0, top.su)
        cu_b = _avg_over(top.z_bot, top.z_bot + B/2.0, bot.su)
        if not np.isfinite(cu_t) or not np.isfinite(cu_b):
            return None
        if cu_t <= cu_b:
            return None
        Nc, sc = 5.14, 1.2
        p0b = 0.0 if backflow_zero else _overburden(z + H, layers)
        Fv = A * (3.0*(H/max(B,1e-6))*cu_t + Nc*sc*(1.0 + 0.2*((z+H)/max(B,1e-6))) * cu_b + p0b)
        
        Fv_upper = clay_capacity(spud, z, layers, use_min_cu=True, backflow_zero=backflow_zero)
        if Fv_upper is not None:
            Fv = min(Fv, Fv_upper)
        
        return float(Fv)

    if top.soil_type == "sand" and bot.soil_type in ("clay","silt"):
        Fv_b = clay_capacity(spud, z + H, layers, use_min_cu=True, backflow_zero=False)
        if Fv_b is None:
            return None
        gamma_s = _gamma_prime(top.z_bot, layers)
        p0_s   = _overburden(z, layers)
        cu_c   = _avg_over(top.z_bot, top.z_bot + B/2.0, bot.su)
        if not np.isfinite(gamma_s) or not np.isfinite(cu_c):
            return None
        KsTanPhi = (3.0 * cu_c) / (max(B,1e-6) * max(gamma_s,1e-6))
        Fv = Fv_b - A * H * gamma_s + 2.0 * (H/max(B,1e-6)) * (H*gamma_s + 2.0*p0_s) * KsTanPhi * A
        return float(Fv)

    return None

# ============== VERSION 4: FAILURE MODE DETECTION ==============

def detect_failure_modes(
    spud: Spudcan,
    layers: List[SoilLayer],
    max_depth: float,
    dz: float = 0.25,
    squeeze_trigger: bool = APPLY_SQUEEZE_TRIGGER_DEFAULT,
) -> Dict[str, any]:
    """
    Detect squeezing and punch-through events throughout the profile.
    
    Returns a dictionary with:
    - squeezing_detected: bool
    - squeezing_depth_start: float or None
    - squeezing_depth_end: float or None
    - punch_clay_clay_detected: bool
    - punch_clay_clay_depth_start: float or None
    - punch_clay_clay_depth_end: float or None
    - punch_sand_clay_detected: bool
    - punch_sand_clay_depth_start: float or None
    - punch_sand_clay_depth_end: float or None
    """
    n = int(np.floor(max_depth / dz)) + 1
    depths = np.round(np.linspace(0.0, n*dz, n+1)[:n], 6)
    
    # Track failure modes
    squeeze_depths = []
    punch_cc_depths = []  # clay over clay
    punch_sc_depths = []  # sand over clay
    
    for z in depths:
        # Check squeezing
        idx = _layer_index(z, layers)
        if idx + 1 < len(layers):
            top, bot = layers[idx], layers[idx+1]
            
            # Squeezing check (soft over strong clay)
            if top.soil_type in ("clay", "silt") and bot.soil_type in ("clay", "silt"):
                cu_t = _avg_over(z, z + spud.B/2.0, top.su)
                cu_b = _avg_over(top.z_bot, top.z_bot + spud.B/2.0, bot.su)
                
                if np.isfinite(cu_t) and np.isfinite(cu_b) and cu_b > 1.5 * cu_t:
                    T = top.z_bot - z
                    if T > 0:
                        trigger_ok = True
                        if squeeze_trigger:
                            trigger_ok = spud.B >= 3.45 * T * (1.0 + 1.025 * (z / max(spud.B,1e-6)))
                        
                        if trigger_ok:
                            squeeze_depths.append(z)
            
            # Punch-through clay/clay check (strong over weak)
            if top.soil_type in ("clay", "silt") and bot.soil_type in ("clay", "silt"):
                cu_t = _avg_over(z, z + spud.B/2.0, top.su)
                cu_b = _avg_over(top.z_bot, top.z_bot + spud.B/2.0, bot.su)
                
                if np.isfinite(cu_t) and np.isfinite(cu_b) and cu_t > cu_b:
                    punch_cc_depths.append(z)
            
            # Punch-through sand/clay check
            # Punch-through sand/clay check - CORRECTED
            if top.soil_type == "sand" and bot.soil_type in ("clay", "silt"):
                H = top.z_bot - z
                if H > 0:
                    # Calculate capacities to compare
                    Fpt = punchthrough_capacity(spud, z, layers, backflow_zero=False)
                    Fs = sand_capacity(spud, z, layers, apply_phi_reduction=False)
                    
                    # Only flag if punch capacity < sand capacity
                    if Fpt is not None and Fs is not None and Fpt < Fs:
                        punch_sc_depths.append(z)
            #if top.soil_type == "sand" and bot.soil_type in ("clay", "silt"):
                #'H = top.z_bot - z
                #'if H > 0:
                 #   'punch_sc_depths.append(z)
    
    # Consolidate continuous ranges
    def get_range(depths_list):
        if not depths_list:
            return None, None
        return min(depths_list), max(depths_list)
    
    sq_start, sq_end = get_range(squeeze_depths)
    pcc_start, pcc_end = get_range(punch_cc_depths)
    psc_start, psc_end = get_range(punch_sc_depths)
    
    return {
        "squeezing_detected": len(squeeze_depths) > 0,
        "squeezing_depth_start": sq_start,
        "squeezing_depth_end": sq_end,
        "punch_clay_clay_detected": len(punch_cc_depths) > 0,
        "punch_clay_clay_depth_start": pcc_start,
        "punch_clay_clay_depth_end": pcc_end,
        "punch_sand_clay_detected": len(punch_sc_depths) > 0,
        "punch_sand_clay_depth_start": psc_start,
        "punch_sand_clay_depth_end": psc_end,
    }

# ---------------- Master sweep with V4 enhancements ----------------
def compute_envelopes(
    spud: Spudcan,
    layers: List[SoilLayer],
    max_depth: float,
    dz: float = 0.25,
    use_min_cu: bool = USE_MIN_CU_POINT_AVG_DEFAULT,
    phi_reduction: bool = APPLY_PHI_REDUCTION_DEFAULT,
    windward_factor: bool = APPLY_WINDWARD_FACTOR_DEFAULT,
    squeeze_trigger: bool = APPLY_SQUEEZE_TRIGGER_DEFAULT,
    meyerhof_table: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Returns a dataframe with per-depth results. Capacities stored in MN.
    
    V4 Enhancement: Adds YES/NO columns for failure modes at each depth.
    """
    n = int(np.floor(max_depth / dz)) + 1
    depths = np.round(np.linspace(0.0, n*dz, n+1)[:n], 6)
    out: Dict[str, list] = {
        "depth": [],
        "idle_clay_MN": [],
        "idle_sand_MN": [],
        "real_MN": [],
        "gov": [],
        "backflow": [],
        "squeeze_MN": [],
        "punch_MN": [],
        "real_clay_only_MN": [],
        "real_sand_only_MN": [],
        # V4: New columns for failure mode indicators
        "squeezing_active": [],
        "punch_clay_clay_active": [],
        "punch_sand_clay_active": [],
    }

    for z in depths:
        N = _meyerhof_N(z / max(spud.B,1e-6), meyerhof_table)
        cu_avg = np.nan
        gamma_avg = np.nan
        if _has_su_here(z, layers):
            i = _layer_index(z, layers)
            cu_avg = _avg_over(z, z + spud.B/2.0, layers[i].su)
            gamma_avg = _avg_over(z, z + spud.B/2.0, layers[i].gamma)
        backflow = False
        if np.isfinite(cu_avg) and np.isfinite(gamma_avg) and gamma_avg > 0:
            backflow = z > (N * cu_avg) / gamma_avg

        Fc = clay_capacity(spud, z, layers, use_min_cu=use_min_cu, backflow_zero=backflow)
        Fs = sand_capacity(spud, z, layers, apply_phi_reduction=phi_reduction)

        Fsq = squeeze_capacity(spud, z, layers, enforce_trigger=squeeze_trigger, backflow_zero=backflow)
        Fpt = punchthrough_capacity(spud, z, layers, backflow_zero=backflow)

        # V4: Track which failure modes are active at this depth
        squeezing_active = "NO"
        punch_cc_active = "NO"
        punch_sc_active = "NO"
        
        idx = _layer_index(z, layers)
        if idx + 1 < len(layers):
            top, bot = layers[idx], layers[idx+1]
            
            # Check squeezing
            if Fsq is not None and Fsq > 0:
                squeezing_active = "YES"
            
            # Check punch-through clay/clay
            if top.soil_type in ("clay","silt") and bot.soil_type in ("clay","silt"):
                cu_t = _avg_over(z, z + spud.B/2.0, top.su)
                cu_b = _avg_over(top.z_bot, top.z_bot + spud.B/2.0, bot.su)
                if np.isfinite(cu_t) and np.isfinite(cu_b) and cu_t > cu_b:
                    punch_cc_active = "YES"
            
            # Check punch-through sand/clay

            # Check punch-through sand/clay
            if top.soil_type == "sand" and bot.soil_type in ("clay","silt"):
                H = top.z_bot - z
                if H > 0 and Fpt is not None and Fpt > 0:
                    # CRITICAL FIX: Only flag if punch capacity < sand capacity
                    # (indicates capacity DROP = actual punch-through risk)
                    if Fs is not None and Fpt < Fs:
                        punch_sc_active = "YES"
                    else:
                        punch_sc_active = "NO"  # Capacity stable/increases - no risk
            #if top.soil_type == "sand" and bot.soil_type in ("clay","silt"):
               # H = top.z_bot - z
              #  if H > 0 and Fpt is not None and Fpt > 0:
                   # punch_sc_active = "YES"

        real_clay = None
        if Fc is not None:
            real_clay = Fc
            if Fsq is not None:
                real_clay = min(real_clay, Fsq)
            if Fpt is not None and layers[_layer_index(z, layers)].soil_type != "sand":
                real_clay = min(real_clay, Fpt)

        real_sand = None
        if Fs is not None:
            real_sand = Fs
            if Fpt is not None and layers[_layer_index(z, layers)].soil_type == "sand":
                real_sand = min(real_sand, Fpt)

        if windward_factor:
            if real_clay is not None:
                real_clay *= 0.8
            if real_sand is not None:
                real_sand *= 0.8

        gov = ""
        real = None
        if (real_clay is not None) and (real_sand is not None):
            if real_clay <= real_sand:
                real = real_clay; gov = "Clay-governed"
            else:
                real = real_sand; gov = "Sand-governed"
        elif real_clay is not None:
            real = real_clay; gov = "Clay-only"
        elif real_sand is not None:
            real = real_sand; gov = "Sand-only"

        out["depth"].append(z)
        out["idle_clay_MN"].append(np.nan if Fc is None else Fc/1000.0)
        out["idle_sand_MN"].append(np.nan if Fs is None else Fs/1000.0)
        out["real_MN"].append(np.nan if real is None else real/1000.0)
        out["gov"].append(gov if gov else "NA")
        out["backflow"].append("Yes" if backflow else "No")
        out["squeeze_MN"].append(np.nan if Fsq is None else Fsq/1000.0)
        out["punch_MN"].append(np.nan if Fpt is None else Fpt/1000.0)
        out["real_clay_only_MN"].append(np.nan if real_clay is None else real_clay/1000.0)
        out["real_sand_only_MN"].append(np.nan if real_sand is None else real_sand/1000.0)
        
        # V4: Add failure mode indicators
        out["squeezing_active"].append(squeezing_active)
        out["punch_clay_clay_active"].append(punch_cc_active)
        out["punch_sand_clay_active"].append(punch_sc_active)

    return pd.DataFrame(out)

# ---------------- Penetration utility ----------------
def _penetration_for_load_MN(df: pd.DataFrame, col: str, load_MN: float) -> Optional[float]:
    x = df[col].to_numpy(dtype=float)
    z = df["depth"].to_numpy(dtype=float)
    mask = np.isfinite(x)
    x = x[mask]; z = z[mask]
    if x.size < 2:
        return None
    if load_MN > x.max():
        return None
    j = np.where(x >= load_MN)[0]
    if j.size == 0:
        return None
    j = j[0]
    if j == 0:
        return float(z[0])
    x1, x2 = x[j-1], x[j]
    z1, z2 = z[j-1], z[j]
    if x2 == x1:
        return float(z2)
    return float(z1 + (load_MN - x1) * (z2 - z1) / (x2 - x1))

def penetration_results(spud: Spudcan, df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Returns analysis-depth and tip-penetration results (m)."""
    P = spud.preload_MN
    z_clay = _penetration_for_load_MN(df, "real_clay_only_MN", P)
    z_sand = _penetration_for_load_MN(df, "real_sand_only_MN", P)

    res: Dict[str, Optional[float]] = {
        "z_clay": None if z_clay is None else float(z_clay),
        "z_sand": None if z_sand is None else float(z_sand),
        "tip_clay": None if z_clay is None else float(z_clay + spud.tip_elev),
        "tip_sand": None if z_sand is None else float(z_sand + spud.tip_elev),
        "z_range_min": None,
        "z_range_max": None,
        "tip_range_min": None,
        "tip_range_max": None,
    }
    candidates = [v for v in [z_clay, z_sand] if v is not None]
    if candidates:
        res["z_range_min"] = min(candidates)
        res["z_range_max"] = max(candidates)
        res["tip_range_min"] = res["z_range_min"] + spud.tip_elev
        res["tip_range_max"] = res["z_range_max"] + spud.tip_elev
    return res
