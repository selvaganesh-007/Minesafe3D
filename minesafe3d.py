#!/usr/bin/env python3
"""
================================================================================
SIH HACKATHON EDITION: MINESAFE-3D LIVE MINE DIGITAL TWIN & DRIVER HUD (V3.1)
================================================================================
Integrated Hardware & Software Stack:
  - System Platform: Ubuntu 24.04 LTS | Middleware: ROS 2 Jazzy
  - Main Compute: NVIDIA Jetson AGX Orin 64GB (CUDA 12.4 + TensorRT 10.0)
  - Primary Sensors: TI IWR2944 4D mmWave Radar, Teledyne FLIR Boson 640 LWIR,
                     u-blox ZED-F9P RTK-GNSS, Xsens Sirius AHRS
  - Safety Norms: ISO 21815 Collision Avoidance & DGMS India Mining Norms
================================================================================
"""

import http.server
import json
import math
import random
import socket
import socketserver
import threading
import time
import webbrowser
import os 

# ==============================================================================
# 1. HARDWARE PIPELINE & TELEMETRY ENGINE
# ==============================================================================

class SIHMineSystemBackend:
    def __init__(self):
        self.ego_speed_kmh = 24.0
        self.opposite_speed_kmh = 18.0
        self.target_dist_m = 35.0
        self.human_incursion = False
        self.human_dist_m = 14.0
        self.environmental_mode = "Heavy Dust"
        self.camera_view = "Driver HUD"
        self.road_roughness_iri = 2.15
        self.pneumatic_purge_active = False
        self.purge_timer = 0

    def update_config(self, payload):
        if "ego_speed" in payload:
            self.ego_speed_kmh = float(payload["ego_speed"])
        if "opposite_speed" in payload:
            self.opposite_speed_kmh = float(payload["opposite_speed"])
        if "target_dist" in payload:
            self.target_dist_m = float(payload["target_dist"])
        if "human_incursion" in payload:
            self.human_incursion = bool(payload["human_incursion"])
        if "human_dist" in payload:
            self.human_dist_m = float(payload["human_dist"])
        if "env_mode" in payload:
            self.environmental_mode = payload["env_mode"]
        if "camera_view" in payload:
            self.camera_view = payload["camera_view"]
        if "road_roughness" in payload:
            self.road_roughness_iri = float(payload["road_roughness"])
        if "trigger_purge" in payload and payload["trigger_purge"]:
            self.pneumatic_purge_active = True
            self.purge_timer = 12

    def compute_telemetry(self):
        if self.pneumatic_purge_active:
            self.purge_timer -= 1
            if self.purge_timer <= 0:
                self.pneumatic_purge_active = False
            purge_str = "AIR-PURGE ACTIVE [6.8 BAR PULSE]"
        else:
            purge_str = "OPTICAL PURGE NOMINAL (6.2 BAR)"

        if self.human_incursion:
            active_threat_dist = self.human_dist_m
            threat_name = "PEDESTRIAN WORKER (HUMAN-01)"
            rel_speed_mps = self.ego_speed_kmh / 3.6
        else:
            active_threat_dist = self.target_dist_m
            threat_name = "HT-204 (CAT 777G DUMP TRUCK)"
            rel_speed_mps = (self.ego_speed_kmh + self.opposite_speed_kmh) / 3.6

        ttc_sec = active_threat_dist / rel_speed_mps if rel_speed_mps > 0.01 else 99.9

        if self.human_incursion or ttc_sec < 2.5:
            cas_level = "RED"
            if self.human_incursion:
                cas_status = "CRITICAL: PEDESTRIAN IN ROADWAY - ISO 21815 LEVEL 3 BRAKE ASSIST ACTIVATED"
            else:
                cas_status = "CRITICAL: ISO 21815 LEVEL 3 BRAKE ASSIST ACTIVATED"
        elif ttc_sec < 5.0:
            cas_level = "YELLOW"
            cas_status = "WARNING: ISO 21815 LEVEL 2 PROXIMITY ADVISORY"
        else:
            cas_level = "GREEN"
            cas_status = "PATH CLEAR - ISO 21815 LEVEL 1 NORMAL OPERATION"

        left_berm_m = round(2.10 + random.uniform(-0.02, 0.02), 2)
        right_berm_m = round(1.85 + random.uniform(-0.02, 0.02), 2)
        dgms_status = "COMPLIANT (Berm >1.5m Requirement)" if (left_berm_m >= 1.5 and right_berm_m >= 1.5) else "DGMS SAFETY VIOLATION"

        is_low_vis = self.environmental_mode in ["Heavy Dust", "Dense Fog", "Zero-Vis Night"]

        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S IST"),
            "hardware_stack": {
                "compute": "NVIDIA Jetson AGX Orin 64GB",
                "os": "Ubuntu 24.04 LTS (ROS 2 Jazzy)",
                "gpu_util_pct": round(52.0 + random.uniform(-2.0, 4.0), 1),
                "trt_latency_ms": round(3.1 + random.uniform(-0.1, 0.2), 1),
                "gnss_status": "u-blox ZED-F9P RTK FIXED (±1.2 cm)",
                "imu_status": "Xsens Sirius AHRS @ 400 Hz",
                "air_purge": purge_str
            },
            "kinematics": {
                "ego_speed_kmh": round(self.ego_speed_kmh, 1),
                "opposite_speed_kmh": round(self.opposite_speed_kmh, 1),
                "rel_speed_kmh": round(self.ego_speed_kmh + (0 if self.human_incursion else self.opposite_speed_kmh), 1),
                "target_dist_m": round(self.target_dist_m, 1),
                "active_threat_dist_m": round(active_threat_dist, 1),
                "threat_name": threat_name,
                "human_incursion": self.human_incursion,
                "human_dist_m": round(self.human_dist_m, 1),
                "ttc_sec": round(ttc_sec, 1),
                "cas_status": cas_status,
                "cas_level": cas_level,
                "env_mode": self.environmental_mode,
                "is_low_vis": is_low_vis,
                "camera_view": self.camera_view
            },
            "road_analytics": {
                "road_grade_pct": -4.8,
                "cross_slope_deg": +2.9,
                "left_berm_m": left_berm_m,
                "right_berm_m": right_berm_m,
                "dgms_status": dgms_status,
                "iri_index": round(self.road_roughness_iri, 2),
                "surface_condition": "Optimal Haul Road" if self.road_roughness_iri < 3.0 else "Severe Roughness / Washboard Hazard"
            }
        }

backend = SIHMineSystemBackend()

# ==============================================================================
# 2. HTTP SERVER & API
# ==============================================================================

class SIHHUDRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(backend.compute_telemetry()).encode("utf-8"))
        elif self.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_HUD_INTERFACE.encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/config":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            try:
                backend.update_config(json.loads(body))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "updated"}).encode("utf-8"))
            except Exception:
                self.send_response(400)
                self.end_headers()

# ==============================================================================
# 3. HIGH-PERFORMANCE FRONTEND HUD INTERFACE
# ==============================================================================

HTML_HUD_INTERFACE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MineSafe-3D: Iron Ore Mine Live Digital Twin HUD [SIH Edition V3.1]</title>
    <style>
        :root {
            --bg-dark: #020610;
            --panel-bg: rgba(8, 14, 28, 0.92);
            --panel-border: rgba(0, 240, 255, 0.3);
            --cyan: #00f0ff;
            --amber: #ffaa00;
            --red: #ff003c;
            --green: #00ff88;
            --text-main: #f8fafc;
            --text-muted: #64748b;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Consolas', 'Monaco', monospace; user-select: none; }
        body { background-color: var(--bg-dark); color: var(--text-main); height: 100vh; overflow: hidden; }

        #app-container { display: grid; grid-template-rows: 54px 1fr 28px; height: 100vh; width: 100vw; }

        /* Top Bar */
        header { background: rgba(4, 8, 18, 0.98); border-bottom: 1px solid var(--panel-border); backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: space-between; padding: 0 16px; z-index: 30; }
        .branding { display: flex; align-items: center; gap: 10px; }
        .branding h1 { font-size: 14px; font-weight: 900; letter-spacing: 1.2px; color: #fff; text-transform: uppercase; }
        .badge { background: rgba(0, 240, 255, 0.1); border: 1px solid var(--cyan); color: var(--cyan); font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 3px; }

        /* ISO Threat Banner */
        .cas-alert { padding: 5px 16px; border-radius: 4px; font-weight: 800; font-size: 11px; letter-spacing: 1px; display: flex; align-items: center; gap: 10px; transition: all 0.25s ease; }
        .cas-GREEN { background: rgba(0, 255, 136, 0.12); border: 1.5px solid var(--green); color: var(--green); box-shadow: 0 0 12px rgba(0, 255, 136, 0.2); }
        .cas-YELLOW { background: rgba(255, 170, 0, 0.18); border: 1.5px solid var(--amber); color: var(--amber); box-shadow: 0 0 16px rgba(255, 170, 0, 0.3); }
        .cas-RED { background: rgba(255, 0, 60, 0.28); border: 2px solid var(--red); color: #ff5277; box-shadow: 0 0 22px rgba(255, 0, 60, 0.6); animation: pulse 0.35s infinite alternate; }
        @keyframes pulse { from { opacity: 0.65; } to { opacity: 1; } }

        /* Layout Grid */
        main { display: grid; grid-template-columns: 360px 1fr 340px; gap: 8px; padding: 8px; overflow: hidden; position: relative; }
        
        .panel { background: var(--panel-bg); border: 1px solid var(--panel-border); border-radius: 6px; padding: 10px; backdrop-filter: blur(14px); display: flex; flex-direction: column; justify-content: space-between; gap: 8px; z-index: 10; }
        .panel-header { font-size: 10px; font-weight: 800; text-transform: uppercase; color: var(--cyan); letter-spacing: 1px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(0, 240, 255, 0.18); padding-bottom: 4px; }

        /* Sensor Canvases */
        .flir-box { width: 100%; height: 130px; background: #000; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; position: relative; }
        #flir-canvas { width: 100%; height: 100%; }
        .flir-tag { position: absolute; top: 4px; left: 4px; font-size: 8px; font-weight: 800; background: rgba(0,0,0,0.85); padding: 2px 6px; color: var(--amber); border: 1px solid var(--amber); z-index: 5; }

        .radar-box { width: 100%; height: 105px; background: #010814; border: 1px solid rgba(0, 240, 255, 0.2); border-radius: 4px; position: relative; }
        #radar-canvas { width: 100%; height: 100%; }

        .profile-box { width: 100%; height: 105px; background: rgba(0,0,0,0.5); border: 1px solid rgba(0, 240, 255, 0.2); border-radius: 4px; position: relative; }
        #profile-canvas { width: 100%; height: 100%; }

        /* Data Card */
        .card { background: rgba(12, 20, 36, 0.85); border: 1px solid rgba(255,255,255,0.08); border-left: 3px solid var(--cyan); padding: 6px 9px; border-radius: 4px; }
        .card h4 { font-size: 9px; color: var(--text-muted); text-transform: uppercase; }
        .card .val { font-size: 12px; font-weight: 800; color: #fff; margin-top: 2px; }
        .card .sub { font-size: 8px; color: var(--green); margin-top: 2px; }

        /* Center 3D Digital Twin Viewport */
        #viewport-wrapper { width: 100%; height: 100%; border-radius: 6px; overflow: hidden; position: relative; background: #010308; border: 1px solid var(--panel-border); }
        #webgl-canvas { width: 100%; height: 100%; display: block; }

        /* Non-Overlapping Top HUD Header inside 3D Viewport */
        .hud-top-bar {
            position: absolute;
            top: 10px;
            left: 10px;
            right: 10px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            pointer-events: none;
            z-index: 25;
        }

        #atmos-warning-banner {
            background: rgba(255, 170, 0, 0.25);
            border: 1.5px solid var(--amber);
            color: #ffe600;
            padding: 5px 12px;
            border-radius: 4px;
            font-size: 9.5px;
            font-weight: 900;
            letter-spacing: 0.8px;
            backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 0 16px rgba(255, 170, 0, 0.4);
            animation: warnPulse 1s infinite alternate;
            max-width: 55%;
        }
        @keyframes warnPulse { from { opacity: 0.75; } to { opacity: 1.0; } }

        .top-hud-overlay { display: flex; gap: 6px; }
        .hud-stat { background: rgba(4, 8, 18, 0.92); border: 1px solid var(--cyan); padding: 4px 8px; border-radius: 4px; text-align: center; backdrop-filter: blur(8px); }
        .hud-stat .lbl { font-size: 7.5px; font-weight: 800; color: var(--text-muted); text-transform: uppercase; }
        .hud-stat .val { font-size: 11.5px; font-weight: 800; color: var(--cyan); }

        /* Dynamic Floating 3D AR Target Callout */
        #target-ar-tag {
            position: absolute;
            top: 0; left: 0;
            pointer-events: none;
            transform: translate(-50%, -100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 20;
            transition: opacity 0.15s ease-out;
        }
        .ar-box {
            border: 1.5px solid var(--cyan);
            background: rgba(4, 12, 24, 0.88);
            padding: 5px 9px;
            border-radius: 4px;
            box-shadow: 0 0 14px rgba(0, 240, 255, 0.4);
            text-align: center;
            min-width: 140px;
        }
        .ar-id { font-size: 10px; font-weight: 900; color: var(--amber); }
        .ar-stat { font-size: 9px; font-weight: 700; color: #fff; margin-top: 1px; }
        .ar-pointer { width: 2px; height: 18px; background: var(--cyan); margin-top: 2px; box-shadow: 0 0 8px var(--cyan); }

        /* Windshield Crosshair Overlay for Driver HUD Mode */
        #windshield-crosshair {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            width: 140px; height: 140px;
            pointer-events: none;
            opacity: 0.65;
            display: block;
            z-index: 14;
        }

        /* Controls UI */
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 4px; }
        .hud-btn { background: rgba(16, 26, 44, 0.8); border: 1px solid #1e293b; color: #94a3b8; font-size: 9px; font-weight: 800; padding: 6px 2px; border-radius: 4px; cursor: pointer; text-align: center; transition: all 0.2s; }
        .hud-btn:hover { background: rgba(28, 46, 78, 1); color: #fff; }
        .hud-btn.active { background: #0088cc; border-color: var(--cyan); color: #fff; box-shadow: 0 0 10px rgba(0, 240, 255, 0.35); }

        .ped-btn { background: rgba(255, 0, 60, 0.15); border: 1px solid var(--red); color: #ff5277; font-size: 9.5px; font-weight: 800; padding: 7px; border-radius: 4px; cursor: pointer; width: 100%; margin-top: 6px; text-transform: uppercase; text-align: center; }
        .ped-btn:hover { background: rgba(255, 0, 60, 0.35); }
        .ped-btn.active { background: var(--red); color: #fff; box-shadow: 0 0 16px rgba(255,0,60,0.8); }

        .slider-group { margin-top: 5px; }
        .slider-group label { display: flex; justify-content: space-between; font-size: 9px; color: var(--text-muted); font-weight: 700; margin-bottom: 2px; }
        .slider-group input[type=range] { width: 100%; accent-color: var(--cyan); cursor: pointer; }

        .purge-btn { background: rgba(0, 240, 255, 0.1); border: 1px solid var(--cyan); color: var(--cyan); font-size: 9px; font-weight: 800; padding: 6px; border-radius: 4px; cursor: pointer; width: 100%; margin-top: 6px; text-transform: uppercase; text-align: center; }
        .purge-btn:hover { background: rgba(0, 240, 255, 0.25); }

        /* Footer Telemetry */
        footer { background: rgba(4, 8, 18, 0.98); border-top: 1px solid var(--panel-border); display: flex; align-items: center; justify-content: space-between; padding: 0 16px; font-size: 8.5px; color: var(--text-muted); z-index: 30; }
        footer span { color: #e2e8f0; font-weight: 700; }
    </style>
    <!-- Three.js + OrbitControls CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>

<div id="app-container">
    <header>
        <div class="branding">
            <h1>MINESAFE-3D DIGITAL TWIN V3.1</h1>
            <span class="badge">ROS 2 JAZZY</span>
            <span class="badge" style="border-color: var(--green); color: var(--green);">JETSON AGX ORIN</span>
            <span class="badge" style="border-color: var(--amber); color: var(--amber);">MULTI-SPECTRAL FUSION</span>
        </div>
        <div id="cas-banner" class="cas-alert cas-GREEN">
            <span id="cas-text">PATH CLEAR - ISO 21815 LEVEL 1 NORMAL OPERATION</span>
            <span style="opacity:0.3;">|</span>
            <span>TTC: <span id="cas-ttc">99.9s</span></span>
        </div>
    </header>

    <main>
        <!-- Left Panel -->
        <div class="panel">
            <div>
                <div class="panel-header">
                    <span>FLIR Boson 640 LWIR Thermal Vision</span>
                    <span style="color:var(--amber);">8-14μm</span>
                </div>
                <div class="flir-box" style="margin-top:5px;">
                    <div class="flir-tag" id="flir-tag-text">YOLOv8-TRT: TARGET HT-204 [128.5°C]</div>
                    <canvas id="flir-canvas"></canvas>
                </div>
            </div>

            <div>
                <div class="panel-header">
                    <span>TI IWR2944 4D Radar Doppler Spectrum</span>
                    <span style="color:var(--cyan);">77-81 GHz</span>
                </div>
                <div class="radar-box" style="margin-top:5px;">
                    <canvas id="radar-canvas"></canvas>
                </div>
            </div>

            <div>
                <div class="panel-header">Road Geometry Cross-Section (PCL Slice)</div>
                <div class="profile-box" style="margin-top:5px;">
                    <canvas id="profile-canvas"></canvas>
                </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 5px;">
                <div class="card">
                    <h4>DGMS SAFETY BERM HEIGHT COMPLIANCE</h4>
                    <div class="val">Left: <span id="berm-l">2.10m</span> | Right: <span id="berm-r">1.85m</span></div>
                    <div class="sub" id="dgms-tag">✔ DGMS Compliant (>1.5m Requirement)</div>
                </div>

                <div class="card">
                    <h4>SURFACE ROUGHNESS INDEX (IRI)</h4>
                    <div class="val" id="iri-text">Optimal Haul Road (IRI: 2.15)</div>
                </div>
            </div>
        </div>

        <!-- Center 3D Digital Twin Viewport -->
        <div id="viewport-wrapper">
            <canvas id="webgl-canvas"></canvas>

            <div class="hud-top-bar">
                <!-- Atmospheric Warning Banner -->
                <div id="atmos-warning-banner" style="display: flex;">
                    <span>⚠️ VISIBILITY CRITICAL: HEAVY DUST</span>
                    <span style="opacity:0.4;">|</span>
                    <span style="color:var(--cyan);">RADAR + LWIR FUSION ACTIVE</span>
                </div>

                <!-- Top Telemetry Stats Overlay -->
                <div class="top-hud-overlay">
                    <div class="hud-stat">
                        <div class="lbl">Ego Speed</div>
                        <div class="val" id="hud-speed">24.0 km/h</div>
                    </div>
                    <div class="hud-stat">
                        <div class="lbl">Road Grade</div>
                        <div class="val">-4.8 %</div>
                    </div>
                    <div class="hud-stat">
                        <div class="lbl">Cross Slope</div>
                        <div class="val">+2.9°</div>
                    </div>
                </div>
            </div>

            <!-- Windshield AR Overlay Crosshair -->
            <svg id="windshield-crosshair" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="28" fill="none" stroke="#00f0ff" stroke-width="1.2" stroke-dasharray="4 3"/>
                <line x1="50" y1="10" x2="50" y2="30" stroke="#00f0ff" stroke-width="1.5"/>
                <line x1="50" y1="70" x2="50" y2="90" stroke="#00f0ff" stroke-width="1.5"/>
                <line x1="10" y1="50" x2="30" y2="50" stroke="#00f0ff" stroke-width="1.5"/>
                <line x1="70" y1="50" x2="90" y2="50" stroke="#00f0ff" stroke-width="1.5"/>
                <circle cx="50" cy="50" r="3" fill="#00f0ff"/>
            </svg>

            <!-- Dynamic Floating 3D AR Target Callout -->
            <div id="target-ar-tag">
                <div class="ar-box" id="ar-card">
                    <div class="ar-id" id="ar-id-text">🎯 TARGET: HT-204</div>
                    <div class="ar-stat">DIST: <span id="ar-dist" style="color:var(--cyan);">35.0 m</span></div>
                    <div class="ar-stat">REL VEL: <span id="ar-vel" style="color:var(--amber);">-42.0 km/h</span></div>
                </div>
                <div class="ar-pointer" id="ar-pointer-bar"></div>
            </div>
        </div>

        <!-- Right Panel -->
        <div class="panel">
            <div>
                <div class="panel-header">Interactive Simulation HUD Controls</div>

                <div style="margin-top:5px;">
                    <label style="font-size:9px; color:var(--text-muted); font-weight:700; display:block; margin-bottom:2px;">HUD CAMERA PERSPECTIVE</label>
                    <div class="btn-grid">
                        <div class="hud-btn active" id="btn-cabin" onclick="setCameraView('Driver HUD')">In-Cabin HUD</div>
                        <div class="hud-btn" id="btn-bev" onclick="setCameraView('3D BEV')">✈ Top-Down BEV</div>
                        <div class="hud-btn" id="btn-opp" onclick="setCameraView('Opposite Vehicle')">🎥 Oncoming Cam</div>
                        <div class="hud-btn" id="btn-orbit" onclick="setCameraView('Free Orbit')">🔄 Free Orbit</div>
                    </div>
                </div>

                <!-- Pedestrian Hazard Incursion Toggle -->
                <button class="ped-btn" id="btn-ped-toggle" onclick="toggleHumanIncursion()">🚶 Simulate Pedestrian Hazard Incursion</button>

                <div style="margin-top:6px;">
                    <label style="font-size:9px; color:var(--text-muted); font-weight:700; display:block; margin-bottom:2px;">ATMOSPHERIC DUST / FOG COND.</label>
                    <div class="btn-grid">
                        <div class="hud-btn" id="btn-env-clear" onclick="setEnvMode('Clear')">Clear Sun</div>
                        <div class="hud-btn active" id="btn-env-dust" onclick="setEnvMode('Heavy Dust')">Iron Dust</div>
                        <div class="hud-btn" id="btn-env-fog" onclick="setEnvMode('Dense Fog')">Dense Fog</div>
                        <div class="hud-btn" id="btn-env-night" onclick="setEnvMode('Zero-Vis Night')">Zero-Vis Night</div>
                    </div>
                </div>

                <div class="slider-group">
                    <label><span>Oncoming Vehicle Distance (HT-204):</span><span id="lbl-dist" style="color:var(--cyan);">35.0 m</span></label>
                    <input type="range" id="slider-dist" min="5" max="85" value="35" step="0.5" oninput="syncConfig()">
                </div>

                <div class="slider-group" id="ped-slider-group" style="display:none;">
                    <label><span>Pedestrian Distance:</span><span id="lbl-ped-dist" style="color:var(--red);">14.0 m</span></label>
                    <input type="range" id="slider-ped-dist" min="4" max="40" value="14" step="0.5" oninput="syncConfig()">
                </div>

                <div class="slider-group">
                    <label><span>Ego Truck Speed:</span><span id="lbl-ego-speed" style="color:var(--cyan);">24.0 km/h</span></label>
                    <input type="range" id="slider-ego-speed" min="0" max="50" value="24" step="0.5" oninput="syncConfig()">
                </div>

                <div class="slider-group">
                    <label><span>Oncoming Truck Speed:</span><span id="lbl-opp-speed" style="color:var(--cyan);">18.0 km/h</span></label>
                    <input type="range" id="slider-opp-speed" min="0" max="40" value="18" step="0.5" oninput="syncConfig()">
                </div>

                <div class="slider-group">
                    <label><span>Simulate Surface Roughness (IRI):</span><span id="lbl-iri" style="color:var(--cyan);">2.15</span></label>
                    <input type="range" id="slider-iri" min="1.0" max="6.0" value="2.15" step="0.1" oninput="syncConfig()">
                </div>

                <button class="purge-btn" onclick="triggerPurge()">💨 Pulse Pneumatic Optical Purge</button>
            </div>

            <div>
                <div class="panel-header">ROS 2 Topic Data Streams</div>
                <div style="font-size:8px; color:#94a3b8; display:flex; flex-direction:column; gap:2px; margin-top:4px;">
                    <div style="display:flex; justify-content:space-between;"><span>/sensor/radar_4d/points</span><span style="color:var(--cyan);">20 Hz</span></div>
                    <div style="display:flex; justify-content:space-between;"><span>/sensor/flir/thermal/raw</span><span style="color:var(--cyan);">30 Hz</span></div>
                    <div style="display:flex; justify-content:space-between;"><span>/perception/pedestrian_tracks</span><span style="color:var(--red);">50 Hz</span></div>
                    <div style="display:flex; justify-content:space-between;"><span>/control/iso21815/cas_state</span><span style="color:var(--green);">50 Hz</span></div>
                </div>
            </div>

            <div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:4px;">
                <div class="panel-header">Hardware Diagnostics</div>
                <div style="font-size:8px; color:var(--text-muted); margin-top:3px; display:flex; flex-direction:column; gap:2px;">
                    <div>Compute Node: <span id="sys-gpu" style="color:#fff;">AGX Orin (52% GPU)</span></div>
                    <div>TensorRT Latency: <span id="sys-trt" style="color:#fff;">3.1 ms</span></div>
                    <div>GNSS RTK: <span style="color:var(--green);">u-blox ZED-F9P (±1.2cm)</span></div>
                    <div>Optical Protection: <span id="sys-purge" style="color:var(--green);">PNEUMATIC NOMINAL</span></div>
                </div>
            </div>
        </div>
    </main>

    <footer>
        <div>HARDWARE: <span>NVIDIA Jetson AGX Orin 64GB</span> | SLAM: <span>Radar-Inertial ICP</span> | PROTECTION: <span>IP67 Enclosure + Pneumatic Purge</span></div>
        <div id="sys-timestamp">2026-09-27 06:55:00 IST</div>
    </footer>
</div>

<script>
    let isHumanIncursion = false;

    // ==========================================================================
    // 1. FLIR LWIR THERMAL CANVAS SIMULATOR
    // ==========================================================================
    const flirCanvas = document.getElementById('flir-canvas');
    const fCtx = flirCanvas.getContext('2d');

    function resizeFlir() {
        flirCanvas.width = flirCanvas.clientWidth;
        flirCanvas.height = flirCanvas.clientHeight;
    }
    resizeFlir();

    function drawFlirFrame(dist, isHuman, humanDist) {
        const w = flirCanvas.width;
        const h = flirCanvas.height;
        if (!w || !h) return;

        fCtx.fillStyle = '#040208';
        fCtx.fillRect(0, 0, w, h);

        fCtx.fillStyle = '#160a28';
        fCtx.beginPath();
        fCtx.moveTo(0, h);
        fCtx.lineTo(w * 0.38, h * 0.38);
        fCtx.lineTo(w * 0.62, h * 0.38);
        fCtx.lineTo(w, h);
        fCtx.fill();

        const scale = Math.max(0.18, 1.0 - (dist / 85.0));
        const tw = 58 * scale;
        const th = 48 * scale;
        const tx = (w * 0.65) - (tw / 2);
        const ty = (h * 0.42) - (th / 2);

        const rad = fCtx.createRadialGradient(tx + tw/2, ty + th*0.6, 2, tx + tw/2, ty + th*0.6, tw*0.65);
        rad.addColorStop(0, '#ffffff');
        rad.addColorStop(0.25, '#fff200');
        rad.addColorStop(0.55, '#ff3c00');
        rad.addColorStop(0.85, '#770055');
        rad.addColorStop(1, 'transparent');

        fCtx.fillStyle = rad;
        fCtx.beginPath();
        fCtx.arc(tx + tw/2, ty + th*0.6, tw*0.65, 0, Math.PI * 2);
        fCtx.fill();

        if (isHuman) {
            const hScale = Math.max(0.25, 1.0 - (humanDist / 45.0));
            const hw = 22 * hScale;
            const hh = 42 * hScale;
            const hx = (w * 0.45) - (hw / 2);
            const hy = (h * 0.72) - (hh / 2);

            fCtx.fillStyle = '#ffffff';
            fCtx.beginPath();
            fCtx.ellipse(hx + hw/2, hy + hh*0.3, hw*0.3, hh*0.2, 0, 0, Math.PI*2);
            fCtx.fillRect(hx + hw*0.2, hy + hh*0.3, hw*0.6, hh*0.5);
            fCtx.fill();

            fCtx.strokeStyle = '#ff003c';
            fCtx.lineWidth = 2;
            fCtx.strokeRect(hx - 4, hy - 4, hw + 8, hh + 8);
            
            document.getElementById('flir-tag-text').innerText = `YOLOv8-TRT: HAZARD PEDESTRIAN [37.2°C]`;
            document.getElementById('flir-tag-text').style.color = 'var(--red)';
            document.getElementById('flir-tag-text').style.borderColor = 'var(--red)';
        } else {
            fCtx.strokeStyle = '#ffaa00';
            fCtx.lineWidth = 1.5;
            fCtx.strokeRect(tx, ty, tw, th);

            document.getElementById('flir-tag-text').innerText = `YOLOv8-TRT: TARGET HT-204 [128.5°C]`;
            document.getElementById('flir-tag-text').style.color = 'var(--amber)';
            document.getElementById('flir-tag-text').style.borderColor = 'var(--amber)';
        }
    }

    // ==========================================================================
    // 2. RADAR DOPPLER CANVAS
    // ==========================================================================
    const radarCanvas = document.getElementById('radar-canvas');
    const rCtx = radarCanvas.getContext('2d');

    function resizeRadar() {
        radarCanvas.width = radarCanvas.clientWidth;
        radarCanvas.height = radarCanvas.clientHeight;
    }
    resizeRadar();

    function drawRadarHeatmap(dist, isHuman, humanDist) {
        const w = radarCanvas.width;
        const h = radarCanvas.height;
        if (!w || !h) return;

        rCtx.fillStyle = '#010814';
        rCtx.fillRect(0, 0, w, h);

        rCtx.strokeStyle = 'rgba(0, 240, 255, 0.15)';
        rCtx.lineWidth = 1;
        for(let r=20; r<w; r+=25) {
            rCtx.beginPath();
            rCtx.arc(w/2, h, r, Math.PI, 2 * Math.PI);
            rCtx.stroke();
        }

        const relY = h - (dist / 85.0 * h * 0.85);
        const radGrad = rCtx.createRadialGradient(w/2 + 25, relY, 1, w/2 + 25, relY, 16);
        radGrad.addColorStop(0, '#00f0ff');
        radGrad.addColorStop(0.4, '#00ff88');
        radGrad.addColorStop(1, 'transparent');
        rCtx.fillStyle = radGrad;
        rCtx.beginPath();
        rCtx.arc(w/2 + 25, relY, 16, 0, Math.PI*2);
        rCtx.fill();

        if (isHuman) {
            const hRelY = h - (humanDist / 85.0 * h * 0.85);
            const hGrad = rCtx.createRadialGradient(w/2 - 10, hRelY, 1, w/2 - 10, hRelY, 12);
            hGrad.addColorStop(0, '#ff003c');
            hGrad.addColorStop(0.5, '#ffaa00');
            hGrad.addColorStop(1, 'transparent');
            rCtx.fillStyle = hGrad;
            rCtx.beginPath();
            rCtx.arc(w/2 - 10, hRelY, 12, 0, Math.PI*2);
            rCtx.fill();

            rCtx.fillStyle = '#ff003c';
            rCtx.font = '8px monospace';
            rCtx.fillText(`MICRO-DOPPLER GAIT: PEDESTRIAN DETECTED`, 8, 12);
        } else {
            rCtx.fillStyle = '#00f0ff';
            rCtx.font = '8px monospace';
            rCtx.fillText(`DOPPLER PEAK: -${(dist*0.4).toFixed(1)} m/s`, 8, 12);
        }
    }

    // ==========================================================================
    // 3. ROAD PROFILE & BERM CANVAS
    // ==========================================================================
    const profCanvas = document.getElementById('profile-canvas');
    const pCtx = profCanvas.getContext('2d');

    function resizeProfile() {
        profCanvas.width = profCanvas.clientWidth;
        profCanvas.height = profCanvas.clientHeight;
    }
    resizeProfile();

    function drawRoadProfile(leftBerm, rightBerm, iri) {
        const w = profCanvas.width;
        const h = profCanvas.height;
        if (!w || !h) return;

        pCtx.clearRect(0, 0, w, h);

        pCtx.strokeStyle = 'rgba(0, 240, 255, 0.1)';
        pCtx.lineWidth = 1;
        for(let x=0; x<w; x+=30) { pCtx.beginPath(); pCtx.moveTo(x,0); pCtx.lineTo(x,h); pCtx.stroke(); }

        const baseline = h - 16;
        const scaleY = 15;

        pCtx.strokeStyle = '#00f0ff';
        pCtx.lineWidth = 2;
        pCtx.beginPath();

        pCtx.moveTo(10, baseline);
        pCtx.lineTo(25, baseline - (leftBerm * scaleY));
        pCtx.lineTo(45, baseline - (leftBerm * scaleY));
        pCtx.lineTo(60, baseline);

        const roadPoints = 32;
        const startX = 60;
        const endX = w - 60;
        const stepX = (endX - startX) / roadPoints;

        for(let i=0; i<=roadPoints; i++) {
            const rx = startX + (i * stepX);
            const noise = (Math.random() - 0.5) * (iri * 1.3);
            const ry = baseline + noise;
            pCtx.lineTo(rx, ry);
        }

        pCtx.lineTo(w - 60, baseline);
        pCtx.lineTo(w - 45, baseline - (rightBerm * scaleY));
        pCtx.lineTo(w - 25, baseline - (rightBerm * scaleY));
        pCtx.lineTo(w - 10, baseline);
        pCtx.stroke();

        pCtx.fillStyle = '#00ff88';
        pCtx.font = '8px monospace';
        pCtx.fillText(`L-BERM: ${leftBerm}m`, 20, 12);
        pCtx.fillText(`R-BERM: ${rightBerm}m`, w - 85, 12);
    }

    // ==========================================================================
    // 4. THREE.JS REALISTIC 3D MINE DIGITAL TWIN ENGINE
    // ==========================================================================
    const wrapper = document.getElementById('viewport-wrapper');
    const canvas = document.getElementById('webgl-canvas');

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x02050c);

    const sceneFog = new THREE.FogExp2(0x02050c, 0.012);
    scene.fog = sceneFog;

    // Set camera near-plane to 0.05m to prevent close-range geometry clipping
    const camera = new THREE.PerspectiveCamera(52, wrapper.clientWidth / wrapper.clientHeight, 0.05, 500);
    const renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    renderer.setSize(wrapper.clientWidth, wrapper.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enabled = false;

    // Environmental Lighting
    scene.add(new THREE.AmbientLight(0xffe8d6, 0.65));
    const sun = new THREE.DirectionalLight(0xffa855, 1.1);
    sun.position.set(60, 80, 40);
    scene.add(sun);

    // Crowned Real Haul Road Surface
    const roadW = 26.0;
    const roadL = 260;
    const roadGeo = new THREE.PlaneGeometry(roadW, roadL, 60, 120);
    
    const posAttr = roadGeo.attributes.position;
    for (let i = 0; i < posAttr.count; i++) {
        let x = posAttr.getX(i);
        let distFromCenter = Math.abs(x);
        let crownY = Math.max(0, 0.45 - (distFromCenter / (roadW / 2)) * 0.45);
        posAttr.setZ(i, crownY);
    }
    roadGeo.computeVertexNormals();

    const roadMat = new THREE.MeshStandardMaterial({ color: 0x3b140c, roughness: 0.92 });
    const roadMesh = new THREE.Mesh(roadGeo, roadMat);
    roadMesh.rotation.x = -Math.PI / 2;
    roadMesh.position.z = roadL / 2 - 10;
    scene.add(roadMesh);

    // Tire Track Rut Lines
    const trackGeo = new THREE.PlaneGeometry(1.2, roadL);
    const trackMat = new THREE.MeshBasicMaterial({ color: 0x220a05, opacity: 0.6, transparent: true });
    
    [-5.5, -1.5, 1.5, 5.5].forEach(xOffset => {
        const track = new THREE.Mesh(trackGeo, trackMat);
        track.rotation.x = -Math.PI / 2;
        track.position.set(xOffset, 0.06, roadL / 2 - 10);
        scene.add(track);
    });

    // Terraced Open-Cast Highwalls
    const wallGeo = new THREE.BoxGeometry(22, 10, roadL);
    const wallMat = new THREE.MeshStandardMaterial({ color: 0x240d07, roughness: 0.98 });
    
    const leftWall = new THREE.Mesh(wallGeo, wallMat);
    leftWall.position.set(-(roadW/2 + 12), 5.0, roadL/2 - 10);
    scene.add(leftWall);

    const rightWall = new THREE.Mesh(wallGeo, wallMat);
    rightWall.position.set((roadW/2 + 12), 5.0, roadL/2 - 10);
    scene.add(rightWall);

    // Dynamic Safety Berm Meshes
    const bermGeo = new THREE.BoxGeometry(2.2, 2.4, roadL);
    const bermMat = new THREE.MeshStandardMaterial({ color: 0x541c11, roughness: 0.95 });
    
    const leftBermMesh = new THREE.Mesh(bermGeo, bermMat);
    leftBermMesh.position.set(-(roadW/2 + 1.1), 1.2, roadL/2 - 10);
    scene.add(leftBermMesh);

    const rightBermMesh = new THREE.Mesh(bermGeo, bermMat);
    rightBermMesh.position.set((roadW/2 + 1.1), 1.2, roadL/2 - 10);
    scene.add(rightBermMesh);

    // Roadside Reflector Delineator Posts
    const postGeo = new THREE.CylinderGeometry(0.08, 0.08, 1.8);
    const postMat = new THREE.MeshStandardMaterial({ color: 0xffffff });
    const refMat = new THREE.MeshBasicMaterial({ color: 0xffaa00 });

    for(let z = 10; z < 200; z += 20) {
        [-12.2, 12.2].forEach(x => {
            const post = new THREE.Mesh(postGeo, postMat);
            post.position.set(x, 0.9, z);
            scene.add(post);

            const ref = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.3, 0.1), refMat);
            ref.position.set(x, 1.5, z);
            scene.add(ref);
        });
    }

    // Heavy Haul Machinery Builder
    function createHeavyHauler(colorHex) {
        const truck = new THREE.Group();
        truck.wheels = [];

        // Main Body Chassis
        const bodyGeo = new THREE.BoxGeometry(4.6, 2.6, 8.8);
        const bodyMat = new THREE.MeshStandardMaterial({ color: colorHex, roughness: 0.4 });
        const body = new THREE.Mesh(bodyGeo, bodyMat);
        body.position.y = 2.2;
        truck.add(body);

        // Dump Bed
        const bedGeo = new THREE.BoxGeometry(5.0, 2.4, 7.6);
        const bedMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 });
        const bed = new THREE.Mesh(bedGeo, bedMat);
        bed.position.set(0, 4.0, -0.6);
        truck.add(bed);

        // Operator Cabin (Positioned at local x=+1.3, z=+3.0)
        const cabGeo = new THREE.BoxGeometry(2.0, 1.8, 2.4);
        const cabMat = new THREE.MeshStandardMaterial({ color: 0x0f172a });
        const cab = new THREE.Mesh(cabGeo, cabMat);
        cab.position.set(1.3, 3.8, 3.0);
        truck.add(cab);

        // Beacon
        const beaconGeo = new THREE.CylinderGeometry(0.2, 0.2, 0.4, 12);
        const beaconMat = new THREE.MeshBasicMaterial({ color: 0xffaa00 });
        const beacon = new THREE.Mesh(beaconGeo, beaconMat);
        beacon.position.set(1.3, 4.8, 3.0);
        truck.add(beacon);

        // Rotating Wheels
        const tireGeo = new THREE.CylinderGeometry(1.2, 1.2, 1.1, 24);
        const tireMat = new THREE.MeshStandardMaterial({ color: 0x080c14, roughness: 0.9 });
        
        const wheelPositions = [
            [-2.4, 1.2, 2.8], [2.4, 1.2, 2.8],
            [-2.4, 1.2, -2.8], [2.4, 1.2, -2.8]
        ];
        wheelPositions.forEach(pos => {
            const tire = new THREE.Mesh(tireGeo, tireMat);
            tire.rotation.z = Math.PI / 2;
            tire.position.set(...pos);
            truck.add(tire);
            truck.wheels.push(tire);
        });

        // Headlight Beams
        const headlightGeo = new THREE.ConeGeometry(3.8, 26, 16, 1, true);
        headlightGeo.rotateX(-Math.PI / 2);
        headlightGeo.translate(0, 0, 13);
        const headlightMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.16, side: THREE.DoubleSide });

        const beamL = new THREE.Mesh(headlightGeo, headlightMat);
        beamL.position.set(-1.5, 2.3, 4.4);
        truck.add(beamL);

        const beamR = new THREE.Mesh(headlightGeo, headlightMat);
        beamR.position.set(1.5, 2.3, 4.4);
        truck.add(beamR);

        return truck;
    }

    // Human Mine Worker Mesh Builder
    function createMineWorker() {
        const worker = new THREE.Group();

        // Legs
        const legMat = new THREE.MeshStandardMaterial({ color: 0x1e293b });
        const legL = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 1.0), legMat);
        legL.position.set(-0.2, 0.5, 0);
        worker.add(legL);

        const legR = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 1.0), legMat);
        legR.position.set(0.2, 0.5, 0);
        worker.add(legR);

        // High-Vis Safety Vest
        const vestMat = new THREE.MeshStandardMaterial({ color: 0xccff00, roughness: 0.3 });
        const torso = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.9, 0.35), vestMat);
        torso.position.y = 1.45;
        worker.add(torso);

        const stripeMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.67, 0.15, 0.37), stripeMat);
        stripe.position.y = 1.45;
        worker.add(stripe);

        // Head & Hardhat
        const headMat = new THREE.MeshStandardMaterial({ color: 0xd2b48c });
        const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 16, 16), headMat);
        head.position.y = 2.05;
        worker.add(head);

        const hatMat = new THREE.MeshStandardMaterial({ color: 0xff0000, roughness: 0.2 });
        const hardhat = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.26, 0.18, 16), hatMat);
        hardhat.position.y = 2.2;
        worker.add(hardhat);

        return worker;
    }

    // Ego Truck (Blue)
    const egoTruck = createHeavyHauler(0x0088cc);
    egoTruck.position.set(-3.5, 0, 0);
    scene.add(egoTruck);

    // Oncoming Truck Group (Yellow CAT)
    const oppositeGroup = new THREE.Group();
    const oppositeTruck = createHeavyHauler(0xffab00);
    oppositeTruck.rotation.y = Math.PI;
    oppositeGroup.add(oppositeTruck);

    // Target Bounding Box
    const boxWireMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff, wireframe: true, transparent: true, opacity: 0.8 });
    const target3DBox = new THREE.Mesh(new THREE.BoxGeometry(5.4, 5.0, 9.4), boxWireMat);
    target3DBox.position.y = 2.5;
    oppositeGroup.add(target3DBox);

    oppositeGroup.position.set(3.5, 0, 35.0);
    scene.add(oppositeGroup);

    // Human Hazard Object
    const humanGroup = new THREE.Group();
    const mineWorkerMesh = createMineWorker();
    humanGroup.add(mineWorkerMesh);

    const pedBoxMat = new THREE.MeshBasicMaterial({ color: 0xff003c, wireframe: true });
    const pedBox = new THREE.Mesh(new THREE.BoxGeometry(1.4, 2.6, 1.4), pedBoxMat);
    pedBox.position.y = 1.3;
    humanGroup.add(pedBox);

    const pedRingMat = new THREE.MeshBasicMaterial({ color: 0xff003c, side: THREE.DoubleSide });
    const pedRing = new THREE.Mesh(new THREE.RingGeometry(1.2, 1.5, 24), pedRingMat);
    pedRing.rotation.x = -Math.PI / 2;
    pedRing.position.y = 0.08;
    humanGroup.add(pedRing);

    humanGroup.position.set(-2.2, 0, 14.0);
    humanGroup.visible = false;
    scene.add(humanGroup);

    // Trajectory Vector Line
    const lineMat = new THREE.LineDashedMaterial({ color: 0x00f0ff, dashSize: 1.5, gapSize: 0.8, linewidth: 2 });
    const lineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-3.5, 0.2, 0),
        new THREE.Vector3(3.5, 0.2, 35)
    ]);
    const trajectoryLine = new THREE.Line(lineGeo, lineMat);
    trajectoryLine.computeLineDistances();
    scene.add(trajectoryLine);

    // Airborne Dust / Fog System
    const dustCount = 2500;
    const dustGeo = new THREE.BufferGeometry();
    const dustPos = new Float32Array(dustCount * 3);
    for(let i=0; i<dustCount*3; i+=3) {
        dustPos[i] = (Math.random() - 0.5) * 80.0;
        dustPos[i+1] = Math.random() * 20.0;
        dustPos[i+2] = Math.random() * 180.0;
    }
    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3));
    const dustMat = new THREE.PointsMaterial({ color: 0xc25e00, size: 0.24, transparent: true, opacity: 0.42 });
    const dustParticles = new THREE.Points(dustGeo, dustMat);
    scene.add(dustParticles);

    // ==========================================================================
    // 5. RE-ENGINEERED UNBUFFERED CAMERA CONTROLLERS
    // ==========================================================================
    let currentCamView = "Driver HUD";

    function setCameraView(view) {
        currentCamView = view;
        
        document.querySelectorAll('.hud-btn').forEach(b => b.classList.remove('active'));
        if (view === 'Driver HUD') document.getElementById('btn-cabin').classList.add('active');
        if (view === '3D BEV') document.getElementById('btn-bev').classList.add('active');
        if (view === 'Opposite Vehicle') document.getElementById('btn-opp').classList.add('active');
        if (view === 'Free Orbit') document.getElementById('btn-orbit').classList.add('active');

        const crosshair = document.getElementById('windshield-crosshair');
        if (view === 'Driver HUD') {
            crosshair.style.display = 'block';
            controls.enabled = false;
        } else if (view === 'Free Orbit') {
            crosshair.style.display = 'none';
            controls.enabled = true;
            controls.target.set(0, 2.0, isHumanIncursion ? humanGroup.position.z : oppositeGroup.position.z / 2);
            controls.update();
        } else {
            crosshair.style.display = 'none';
            controls.enabled = false;
        }

        syncConfig();
    }

    function updateCameraFrame() {
        const oppZ = oppositeGroup.position.z;
        const humZ = humanGroup.position.z;

        if (currentCamView === "Driver HUD") {
            // Driver cabin position: Ego is at x=-3.5, cab center is local x=+1.3 (World x = -2.2)
            // Mounted right at windshield glass level (z = 4.45, y = 4.10) OUTSIDE geometry bounding boxes
            camera.position.set(-2.2, 4.10, 4.45);
            const focusZ = isHumanIncursion ? humZ : Math.max(oppZ, 25.0);
            const focusX = isHumanIncursion ? -2.2 : 3.5;
            camera.lookAt(focusX, 2.0, focusZ);

        } else if (currentCamView === "3D BEV") {
            // High overhead Bird's Eye View looking straight down
            const centerZ = isHumanIncursion ? (humZ / 2) : (oppZ / 2);
            camera.position.set(0, 72.0, centerZ + 0.1);
            camera.lookAt(0, 0, centerZ);

        } else if (currentCamView === "Opposite Vehicle") {
            // Oncoming truck HT-204 front bumper position (World x = 2.2, z = oppZ - 4.65)
            // Positioned cleanly outside bumper facing Ego truck
            camera.position.set(2.2, 3.80, oppZ - 4.65);
            camera.lookAt(-2.2, 2.2, 0);
        }
    }

    // Dynamic 3D AR Target Marker Projection
    const arTag = document.getElementById('target-ar-tag');
    const arCard = document.getElementById('ar-card');
    const arPointer = document.getElementById('ar-pointer-bar');
    const targetVec = new THREE.Vector3();

    function update3DTargetMarker(casLevel, threatDist, relVel, threatName) {
        if (isHumanIncursion) {
            humanGroup.getWorldPosition(targetVec);
            targetVec.y += 2.8;
        } else {
            oppositeGroup.getWorldPosition(targetVec);
            targetVec.y += 5.0;
        }

        targetVec.project(camera);

        if (targetVec.z > 1.0) {
            arTag.style.opacity = '0';
            return;
        }

        const x = (targetVec.x * 0.5 + 0.5) * wrapper.clientWidth;
        const y = (-(targetVec.y * 0.5) + 0.5) * wrapper.clientHeight;

        arTag.style.left = `${x}px`;
        arTag.style.top = `${y}px`;
        arTag.style.opacity = '1';

        document.getElementById('ar-id-text').innerText = isHumanIncursion ? "⚠️ HAZARD: PEDESTRIAN DETECTED" : "🎯 TARGET: HT-204";
        document.getElementById('ar-dist').innerText = threatDist.toFixed(1) + ' m';
        document.getElementById('ar-vel').innerText = `-${relVel.toFixed(1)} km/h`;

        let activeColor = '#00f0ff';
        if (casLevel === 'RED' || isHumanIncursion) activeColor = '#ff003c';
        else if (casLevel === 'YELLOW') activeColor = '#ffaa00';

        arCard.style.borderColor = activeColor;
        arPointer.style.background = activeColor;
        arPointer.style.boxShadow = `0 0 10px ${activeColor}`;
        boxWireMat.color.setHex(casLevel === 'RED' ? 0xff003c : (casLevel === 'YELLOW' ? 0xffaa00 : 0x00f0ff));
    }

    function setEnvMode(mode) {
        document.querySelectorAll('#btn-env-clear, #btn-env-dust, #btn-env-fog, #btn-env-night').forEach(b => b.classList.remove('active'));

        const warnBanner = document.getElementById('atmos-warning-banner');

        if (mode === "Clear") {
            sceneFog.density = 0.002;
            dustParticles.material.opacity = 0.05;
            warnBanner.style.display = 'none';
            document.getElementById('btn-env-clear').classList.add('active');
        } else if (mode === "Heavy Dust") {
            sceneFog.density = 0.012;
            dustParticles.material.color.setHex(0xc25e00);
            dustParticles.material.opacity = 0.42;
            warnBanner.style.display = 'flex';
            warnBanner.children[0].innerText = "⚠️ VISIBILITY CRITICAL: HEAVY DUST";
            document.getElementById('btn-env-dust').classList.add('active');
        } else if (mode === "Dense Fog") {
            sceneFog.density = 0.028;
            dustParticles.material.color.setHex(0xaaaaaa);
            dustParticles.material.opacity = 0.70;
            warnBanner.style.display = 'flex';
            warnBanner.children[0].innerText = "⚠️ VISIBILITY CRITICAL: DENSE FOG";
            document.getElementById('btn-env-fog').classList.add('active');
        } else if (mode === "Zero-Vis Night") {
            sceneFog.density = 0.045;
            dustParticles.material.color.setHex(0x050505);
            dustParticles.material.opacity = 0.90;
            warnBanner.style.display = 'flex';
            warnBanner.children[0].innerText = "⚠️ VISIBILITY CRITICAL: NIGHT OPER.";
            document.getElementById('btn-env-night').classList.add('active');
        }
        syncConfig(mode);
    }

    function toggleHumanIncursion() {
        isHumanIncursion = !isHumanIncursion;
        const btn = document.getElementById('btn-ped-toggle');
        const pedSlider = document.getElementById('ped-slider-group');

        if (isHumanIncursion) {
            btn.classList.add('active');
            btn.innerText = "🛑 DISMISS PEDESTRIAN HAZARD";
            pedSlider.style.display = 'block';
            humanGroup.visible = true;
        } else {
            btn.classList.remove('active');
            btn.innerText = "🚶 SIMULATE PEDESTRIAN HAZARD INCURSION";
            pedSlider.style.display = 'none';
            humanGroup.visible = false;
        }
        syncConfig();
    }

    function triggerPurge() {
        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trigger_purge: true })
        });
    }

    function syncConfig(selectedEnvMode = null) {
        const distVal = document.getElementById('slider-dist').value;
        const pedDistVal = document.getElementById('slider-ped-dist').value;
        const egoSpeedVal = document.getElementById('slider-ego-speed').value;
        const oppSpeedVal = document.getElementById('slider-opp-speed').value;
        const iriVal = document.getElementById('slider-iri').value;

        document.getElementById('lbl-dist').innerText = parseFloat(distVal).toFixed(1) + ' m';
        document.getElementById('lbl-ped-dist').innerText = parseFloat(pedDistVal).toFixed(1) + ' m';
        document.getElementById('lbl-ego-speed').innerText = parseFloat(egoSpeedVal).toFixed(1) + ' km/h';
        document.getElementById('lbl-opp-speed').innerText = parseFloat(oppSpeedVal).toFixed(1) + ' km/h';
        document.getElementById('lbl-iri').innerText = parseFloat(iriVal).toFixed(2);

        const payload = {
            target_dist: distVal,
            human_incursion: isHumanIncursion,
            human_dist: pedDistVal,
            ego_speed: egoSpeedVal,
            opposite_speed: oppSpeedVal,
            road_roughness: iriVal,
            camera_view: currentCamView
        };
        if (selectedEnvMode) payload["env_mode"] = selectedEnvMode;

        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).catch(err => console.error(err));
    }

    let globalTelemetry = null;

    function pollTelemetry() {
        fetch('/api/telemetry')
            .then(res => res.json())
            .then(data => {
                globalTelemetry = data;

                document.getElementById('sys-timestamp').innerText = data.timestamp;
                document.getElementById('cas-ttc').innerText = data.kinematics.ttc_sec + 's';
                document.getElementById('cas-text').innerText = data.kinematics.cas_status;
                
                const casBanner = document.getElementById('cas-banner');
                casBanner.className = 'cas-alert cas-' + data.kinematics.cas_level;

                document.getElementById('hud-speed').innerText = data.kinematics.ego_speed_kmh + ' km/h';
                document.getElementById('berm-l').innerText = data.road_analytics.left_berm_m + 'm';
                document.getElementById('berm-r').innerText = data.road_analytics.right_berm_m + 'm';
                document.getElementById('iri-text').innerText = `${data.road_analytics.surface_condition} (IRI: ${data.road_analytics.iri_index})`;

                document.getElementById('sys-gpu').innerText = `AGX Orin (${data.hardware_stack.gpu_util_pct}% GPU)`;
                document.getElementById('sys-trt').innerText = data.hardware_stack.trt_latency_ms + ' ms';
                document.getElementById('sys-purge').innerText = data.hardware_stack.air_purge;

                const tDist = data.kinematics.target_dist_m;
                const hDist = data.kinematics.human_dist_m;
                oppositeGroup.position.z = tDist;
                humanGroup.position.z = hDist;

                const posArr = trajectoryLine.geometry.attributes.position.array;
                if (data.kinematics.human_incursion) {
                    posArr[3] = -2.2; posArr[4] = 0.2; posArr[5] = hDist;
                    lineMat.color.setHex(0xff003c);
                } else {
                    posArr[3] = 3.5; posArr[4] = 0.2; posArr[5] = tDist;
                    lineMat.color.setHex(0x00f0ff);
                }
                trajectoryLine.geometry.attributes.position.needsUpdate = true;
                trajectoryLine.computeLineDistances();

                update3DTargetMarker(data.kinematics.cas_level, data.kinematics.active_threat_dist_m, data.kinematics.rel_speed_kmh, data.kinematics.threat_name);

                drawFlirFrame(tDist, data.kinematics.human_incursion, hDist);
                drawRadarHeatmap(tDist, data.kinematics.human_incursion, hDist);
                drawRoadProfile(data.road_analytics.left_berm_m, data.road_analytics.right_berm_m, data.road_analytics.iri_index);
            })
            .catch(err => console.error(err));
    }

    window.addEventListener('resize', () => {
        camera.aspect = wrapper.clientWidth / wrapper.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(wrapper.clientWidth, wrapper.clientHeight);
        resizeFlir();
        resizeRadar();
        resizeProfile();
    });

    let animClock = 0;
    function animate() {
        requestAnimationFrame(animate);
        animClock += 0.05;

        if (controls.enabled) {
            controls.update();
        } else {
            updateCameraFrame();
        }

        const iri = parseFloat(document.getElementById('slider-iri').value);
        const vibY = Math.sin(animClock * 16) * (iri * 0.012);
        egoTruck.position.y = vibY;
        oppositeTruck.position.y = vibY;

        if (isHumanIncursion) {
            mineWorkerMesh.position.y = Math.sin(animClock * 6) * 0.04;
        }

        const egoSpd = parseFloat(document.getElementById('slider-ego-speed').value);
        const oppSpd = parseFloat(document.getElementById('slider-opp-speed').value);
        egoTruck.wheels.forEach(w => w.rotation.x += egoSpd * 0.012);
        oppositeTruck.wheels.forEach(w => w.rotation.x += oppSpd * 0.012);

        if (globalTelemetry) {
            update3DTargetMarker(globalTelemetry.kinematics.cas_level, globalTelemetry.kinematics.active_threat_dist_m, globalTelemetry.kinematics.rel_speed_kmh, globalTelemetry.kinematics.threat_name);
        }

        renderer.render(scene, camera);
    }

    setInterval(pollTelemetry, 100);
    animate();
</script>
</body>
</html>
"""

# ==============================================================================
# 5. EXECUTION LAUNCHER WITH PORT AUTO-BINDING
# ==============================================================================

def find_available_port(start_port=8080, max_tries=20):
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

def main():
    # Detect port assigned by cloud host (Render, Railway, Koyeb), or fallback to local port search
    env_port = os.environ.get("PORT")
    PORT = int(env_port) if env_port else find_available_port(8080)
    
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), SIHHUDRequestHandler) as httpd:
        url = f"http://localhost:{PORT}"
        print("\n" + "="*84)
        print(" MINESAFE-3D DIGITAL TWIN & HUD V3.1 (SIH EVALUATION READY)")
        print(f" SERVER PORT: {PORT}")
        print(" Platform Stack: Ubuntu 24.04 LTS | ROS 2 Jazzy | Jetson AGX Orin 64GB")
        print(" Camera Modes: In-Cabin HUD | 3D BEV | Oncoming Cam | Free Orbit (GEOMETRY FIXED)")
        print(" Safety Norms: ISO 21815 CAS | DGMS India Mining Norms")
        print("="*84 + "\n")
        
        # Open browser automatically ONLY if running locally on your PC
        if not env_port:
            threading.Thread(target=lambda: (time.sleep(1.0), webbrowser.open(url))).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nTerminating MineSafe-3D Engine...")

if __name__ == "__main__":
    main()