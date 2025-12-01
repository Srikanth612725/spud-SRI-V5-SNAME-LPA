from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import numpy as np
import io
import base64
import matplotlib.pyplot as plt

# --- Import your existing logic ---
from lpa_v50_v4 import (
    Spudcan, SoilLayer, SoilPoint, compute_envelopes
)
from enhanced_penetration_prediction import analyze_penetration_enhanced
from improved_plotting_v4 import plot_penetration_curve_v4, add_failure_mode_annotations

app = FastAPI(title="Spud-SRI API", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data Models ---
class SoilPointModel(BaseModel):
    z: float
    v: float

class SoilLayerInput(BaseModel):
    name: str
    z_top: float
    z_bot: float
    soil_type: str
    gamma: List[SoilPointModel] = []
    su: List[SoilPointModel] = []
    phi: List[SoilPointModel] = []

class SpudcanInput(BaseModel):
    rig_name: str
    B: float
    A: float
    tip_elev: float
    preload_MN: float
    beta: Optional[float] = None
    alpha: Optional[float] = None

class AnalysisSettings(BaseModel):
    max_depth: float = 50.0
    dz: float = 0.25
    use_min_cu: bool = True
    phi_reduction: bool = False
    windward_factor: bool = False
    squeeze_trigger: bool = True

class CalculationRequest(BaseModel):
    spudcan: SpudcanInput
    layers: List[SoilLayerInput]
    settings: AnalysisSettings

@app.post("/calculate-penetration")
def calculate_penetration(req: CalculationRequest):
    try:
        # 1. Reconstruct Inputs
        internal_layers = []
        for l in req.layers:
            # Sort points by depth to be safe
            l.gamma.sort(key=lambda p: p.z)
            l.su.sort(key=lambda p: p.z)
            l.phi.sort(key=lambda p: p.z)

            internal_layers.append(SoilLayer(
                name=l.name,
                z_top=l.z_top,
                z_bot=l.z_bot,
                soil_type=l.soil_type,
                gamma=[SoilPoint(p.z, p.v) for p in l.gamma],
                su=[SoilPoint(p.z, p.v) for p in l.su],
                phi=[SoilPoint(p.z, p.v) for p in l.phi]
            ))

        internal_spud = Spudcan(
            rig_name=req.spudcan.rig_name,
            B=req.spudcan.B,
            A=req.spudcan.A,
            tip_elev=req.spudcan.tip_elev,
            preload_MN=req.spudcan.preload_MN,
            beta=req.spudcan.beta,
            alpha=req.spudcan.alpha
        )

        # 2. Run Math Engine
        df = compute_envelopes(
            spud=internal_spud,
            layers=internal_layers,
            max_depth=req.settings.max_depth,
            dz=req.settings.dz,
            use_min_cu=req.settings.use_min_cu,
            phi_reduction=req.settings.phi_reduction,
            windward_factor=req.settings.windward_factor,
            squeeze_trigger=req.settings.squeeze_trigger
        )

        # 3. Run Predictions
        prediction = analyze_penetration_enhanced(
            df=df,
            preload_MN=internal_spud.preload_MN,
            tip_offset_m=internal_spud.tip_elev
        )

        # 4. Generate Plot
        fig, ax = plot_penetration_curve_v4(
            df=df,
            preload_MN=internal_spud.preload_MN,
            tip_offset_m=internal_spud.tip_elev,
            rig_name=internal_spud.rig_name,
            fig_height=6,
            fig_width=8
        )
        add_failure_mode_annotations(ax, df)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight', dpi=150) # Higher DPI for better look
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)

        # 5. Generate CSV (Server-Side)
        csv_string = df.to_csv(index=False)

        return {
            "prediction": {
                "static_depth": prediction.static_depth,
                "dynamic_range": prediction.final_range,
                "design_depth": prediction.recommended_design_depth,
                "warnings": prediction.warnings
            },
            "plot_image": img_str,
            "csv_data": csv_string  # <-- NEW: Sending the file directly
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
