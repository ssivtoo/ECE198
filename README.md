# Bedside Delirium Prevention Monitor

A real-time IoT patient monitoring system that continuously tracks environmental and hydration risk factors linked to hospital delirium — an often-overlooked condition affecting 1 in 3 ICU patients.

## The Problem

Hospital delirium is triggered by disrupted sleep (noise, light) and dehydration. Current clinical practice relies on **periodic manual checks** — leaving dangerous conditions undetected for hours. We built a system that catches them in under a second.

## System Architecture

```
Arduino (sensors) ──serial──► Python Dashboard ──► SQLite DB
     │                              │
  Grove Light                  Risk Score
  Grove Sound                  Live Chart
  Potentiometer                Alert Log
  RGB LCD ◄────── LCD commands ─────┘
```

## Features

- **Adaptive baseline calibration** — auto-calibrates to ambient room conditions on startup; no manual threshold tuning required
- **Composite delirium risk score (0–100)** — weighted algorithm across noise (40 pts), light (25 pts), and hydration (35 pts) with LOW / MODERATE / HIGH classification
- **Real-time trend chart** — embedded matplotlib visualization of risk score history with threshold reference lines
- **Bidirectional serial communication** — Python dashboard pushes status commands to the Arduino RGB LCD in real time
- **SQLite session persistence** — every sensor reading and alert event is logged with timestamps for post-shift clinical review
- **One-click CSV export** — full session data with summary statistics (avg/peak risk, avg hydration)
- **23 automated unit tests** — pytest suite covering risk scoring, level classification, and trend detection edge cases

## Stack

| Layer | Technology |
|---|---|
| Firmware | Arduino C++ (Grove sensors, HX711, RGB LCD) |
| Dashboard | Python 3, tkinter, matplotlib |
| Persistence | SQLite (WAL mode, indexed) |
| Communication | Serial (115200 baud, CSV protocol) |
| Testing | pytest |

## Getting Started

**Hardware:** Arduino Uno, Grove Sound Sensor (A0), Grove Light Sensor (A1), Potentiometer (A3), Grove RGB LCD

```bash
pip install -r requirements.txt
```

1. Flash `Sensor_Reader/Sensor_Reader.ino` to the Arduino via Arduino IDE
2. Update `"port"` in `config.json` to match your serial port (e.g. `COM3` or `/dev/cu.usbmodem101`)
3. Run the dashboard:

```bash
python ClientDashboard.py
```

Run the test suite:

```bash
pytest tests/ -v
```

## Configuration

All thresholds are externalized in `config.json` — no code changes needed to tune sensor sensitivity, hydration targets, or serial settings.

## Clinical Context

Built for ECE 198 (University of Waterloo) with reference to published delirium risk factor research. The three monitored parameters — noise, light, and hydration — are among the most actionable non-pharmacological delirium prevention targets identified in ICU literature.
