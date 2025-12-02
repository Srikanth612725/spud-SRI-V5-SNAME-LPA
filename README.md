# ⚓ Spud-SRI v6.6: Professional Leg Penetration Analysis

**A commercial-grade web platform for offshore geotechnical engineering.**

[![Live App](https://img.shields.io/badge/Live_App-Netlify-00C7B7?style=for-the-badge&logo=netlify)](https://spud-sri-v6.netlify.app/)
[![Status](https://img.shields.io/badge/Status-Production_Ready-success?style=for-the-badge)]()

**Spud-SRI** replaces legacy spreadsheets with a modern, cloud-native application for predicting Jack-Up Rig leg penetration. It performs complex **SNAME-compliant** calculations with a beautiful, interactive dashboard.

---

## 🚀 Key Features

* **📄 Generative PDF Reports:** Instantly generate professional A4 design reports containing soil profiles, geometry, and results.
* **📊 Live Stratigraphy Visualizer:** Watch the soil column and spudcan graphics update in real-time as you type.
* **🌍 Multi-Point Soil Modeling:** Input unlimited $S_u$ and $\gamma'$ data points per layer for realistic offshore profiles.
* **⚠️ Risk Detection:** Automatic warning system for **Punch-Through** and **Squeezing** failure modes.
* **📈 Zero-Load Modeling:** Accurate modeling of tip resistance starting from the tip offset.

## 🛠️ Architecture

This project uses a **Hybrid Architecture** to combine the speed of a modern web app with the calculation power of Python.

* **Frontend (The Face):** React, Vite, Mantine UI (Hosted on **Netlify**)
* **Backend (The Brain):** Python 3.11, FastAPI, Pandas, SciPy (Hosted on **Render**)
