"""
Bedside Delirium Prevention Monitor — Nurse Station Dashboard

Reads light, noise, and hydration data from an Arduino over serial,
computes a composite delirium risk score, and displays live trends.
All session data is persisted to SQLite for post-shift review.
"""

from __future__ import annotations

import datetime
import json
import time
from collections import deque
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import serial

import analytics
import database as db

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "config.json"

_DEFAULTS: dict = {
    "serial": {"port": "COM3", "baud": 115200, "timeout": 1},
    "thresholds": {
        "light_margin_factor": 0.5,
        "noise_margin_factor": 0.5,
        "empty_pct": 5.0,
        "slow_rate_pct_per_hr": 10.0,
        "refill_rise_min_pct": 10.0,
    },
    "calibration": {"samples": 20},
    "ui": {"update_ms": 500, "chart_history_points": 120},
}


def load_config() -> dict:
    cfg = {s: dict(v) for s, v in _DEFAULTS.items()}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            loaded = json.load(f)
        for section, values in loaded.items():
            if section in cfg:
                cfg[section].update(values)
    return cfg


# ──────────────────────────────────────────────────────────────────────────────
# Serial parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_line(line: str) -> tuple[int, int, float] | None:
    """Parse 'light,noise,weight_raw' CSV from Arduino → (light, noise, pct)."""
    parts = line.split(",")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), float(parts[2]) / 10.23
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Colour palette
# ──────────────────────────────────────────────────────────────────────────────

_BG       = "#f0f4f8"
_HDR_BG   = "#1a365d"
_GOOD_BG  = "#c6f6d5"; _GOOD_FG  = "#22543d"
_WARN_BG  = "#feebc8"; _WARN_FG  = "#7b341e"
_CRIT_BG  = "#fed7d7"; _CRIT_FG  = "#742a2a"
_ALERT_BG = "#c53030"; _ALERT_FG = "#ffffff"
_OK_BG    = "#276749"; _OK_FG    = "#ffffff"
_BLUE_BG  = "#ebf8ff"; _BLUE_FG  = "#2b6cb0"

_F_TITLE  = ("Helvetica", 12, "bold")
_F_VALUE  = ("Helvetica", 30, "bold")
_F_STATUS = ("Helvetica", 11, "bold")
_F_SMALL  = ("Helvetica", 9)


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────────────────────────

class RoomEnvironmentGUI:
    def __init__(self, root: tk.Tk, ser: serial.Serial | None, config: dict):
        self.root = root
        self.ser = ser
        self.cfg = config
        thr = config["thresholds"]
        ui  = config["ui"]

        # thresholds
        self.EMPTY_THRESHOLD    = thr["empty_pct"]
        self.SLOW_RATE          = thr["slow_rate_pct_per_hr"]
        self.REFILL_RISE_MIN    = thr["refill_rise_min_pct"]
        self.LIGHT_MARGIN       = thr["light_margin_factor"]
        self.NOISE_MARGIN       = thr["noise_margin_factor"]
        self.update_ms          = ui["update_ms"]
        self.history_len        = ui["chart_history_points"]

        # calibration
        self.light_baseline: float = 0.0
        self.noise_baseline: float = 0.0
        self.calibrating: bool = True
        self.samples_needed: int = config["calibration"]["samples"]
        self.sample_list: list[tuple] = []

        # hydration state
        self.last_weight_pct:  float | None = None
        self.last_refill_time: float | None = None
        self.refill_level_pct: float | None = None
        self.drink_rate_per_hr: float = 0.0
        self.drink_rate_slow: bool = False
        self.is_empty: bool = False

        # dedup guards
        self.last_lcd_msg:   str | None = None
        self.last_alert_key: str | None = None

        # rolling history buffers
        self.risk_history: deque[int] = deque(maxlen=self.history_len)

        # session
        db.initialize_db()
        self.session_id = db.start_session()
        self.session_start = time.time()

        # chart refresh cadence (every N sensor ticks)
        self._chart_tick = 0
        self._chart_every = max(1, int(2000 / self.update_ms))  # ~2 s

        self._build_ui()
        self.update_loop()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.title("Bedside Delirium Prevention Monitor")
        self.root.geometry("1150x720")
        self.root.configure(bg=_BG)
        self.root.resizable(True, True)

        # Header
        hdr = tk.Frame(self.root, bg=_HDR_BG, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr,
            text="BEDSIDE DELIRIUM PREVENTION MONITOR",
            font=("Helvetica", 15, "bold"),
            bg=_HDR_BG, fg="white",
        ).pack(side="left", padx=18, pady=14)
        self.session_label = tk.Label(
            hdr, text="Session: 00:00:00",
            font=_F_SMALL, bg=_HDR_BG, fg="#90cdf4",
        )
        self.session_label.pack(side="right", padx=18)

        # Sensor + risk tiles
        tile_row = tk.Frame(self.root, bg=_BG)
        tile_row.pack(fill="x", padx=12, pady=(10, 0))
        for i in range(4):
            tile_row.columnconfigure(i, weight=1)

        self.light_tile = self._make_sensor_tile(tile_row, 0, "LIGHT")
        self.noise_tile = self._make_sensor_tile(tile_row, 1, "NOISE")
        self.hydr_tile  = self._make_sensor_tile(tile_row, 2, "HYDRATION")
        self.risk_tile  = self._make_risk_tile(tile_row, 3)

        # Chart
        chart_frame = tk.LabelFrame(
            self.root,
            text="  Risk Score History  ",
            bg=_BG, font=("Helvetica", 9, "bold"),
            padx=4, pady=4,
        )
        chart_frame.pack(fill="both", expand=True, padx=12, pady=6)

        self.fig = Figure(figsize=(10, 2.0), dpi=90, facecolor="#ffffff")
        self.ax  = self.fig.add_subplot(111)
        self._draw_chart_axes()
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Environment alert bar
        self.env_frame = tk.Frame(self.root, bd=0)
        self.env_frame.pack(fill="x", padx=12, pady=(0, 5))
        self.env_label = tk.Label(
            self.env_frame,
            text="CALIBRATING — collecting baseline samples…",
            font=("Helvetica", 13, "bold"),
            bg="#718096", fg="white", pady=8,
        )
        self.env_label.pack(fill="x")

        # Alert log + export
        bottom = tk.Frame(self.root, bg=_BG)
        bottom.pack(fill="both", padx=12, pady=(0, 10))

        log_hdr = tk.Frame(bottom, bg=_BG)
        log_hdr.pack(fill="x", pady=(0, 3))
        tk.Label(
            log_hdr, text="Alert Log",
            font=("Helvetica", 10, "bold"), bg=_BG,
        ).pack(side="left")
        tk.Button(
            log_hdr,
            text="Export Session CSV",
            command=self._export_csv,
            font=_F_SMALL,
            bg="#2b6cb0", fg="white",
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="right")

        cols = ("Time", "Type", "Severity", "Message")
        self.alert_tree = ttk.Treeview(
            bottom, columns=cols, show="headings", height=4,
        )
        for col, width in zip(cols, (75, 100, 80, 650)):
            self.alert_tree.heading(col, text=col)
            self.alert_tree.column(col, width=width, anchor="w")
        self.alert_tree.tag_configure("HIGH",     background="#fed7d7")
        self.alert_tree.tag_configure("MODERATE", background="#feebc8")
        sb = ttk.Scrollbar(bottom, orient="vertical", command=self.alert_tree.yview)
        self.alert_tree.configure(yscrollcommand=sb.set)
        self.alert_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _make_sensor_tile(self, parent: tk.Frame, col: int, title: str) -> dict:
        outer = tk.Frame(parent, bg=_GOOD_BG, bd=0)
        outer.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)
        title_lbl = tk.Label(outer, text=title, font=_F_TITLE, bg=_GOOD_BG, fg=_GOOD_FG)
        title_lbl.pack(pady=(10, 2))
        val_lbl = tk.Label(outer, text="--", font=_F_VALUE, bg=_GOOD_BG, fg=_GOOD_FG)
        val_lbl.pack()
        status_lbl = tk.Label(outer, text="STATUS: --", font=_F_STATUS, bg=_GOOD_BG, fg=_GOOD_FG)
        status_lbl.pack(pady=(2, 12))
        return {"outer": outer, "title": title_lbl, "val": val_lbl, "status": status_lbl}

    def _make_risk_tile(self, parent: tk.Frame, col: int) -> dict:
        outer = tk.Frame(parent, bg=_BLUE_BG, bd=0)
        outer.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)
        title_lbl = tk.Label(
            outer, text="DELIRIUM RISK",
            font=_F_TITLE, bg=_BLUE_BG, fg=_BLUE_FG,
        )
        title_lbl.pack(pady=(10, 2))
        score_lbl = tk.Label(outer, text="--", font=_F_VALUE, bg=_BLUE_BG, fg=_BLUE_FG)
        score_lbl.pack()
        level_lbl = tk.Label(
            outer, text="CALIBRATING",
            font=_F_STATUS, bg=_BLUE_BG, fg=_BLUE_FG,
        )
        level_lbl.pack(pady=(2, 12))
        return {"outer": outer, "title": title_lbl, "score": score_lbl, "level": level_lbl}

    # ── Main loop ─────────────────────────────────────────────────────────────

    def update_loop(self) -> None:
        raw = ""
        if self.ser:
            try:
                raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
            except Exception:
                pass

        data = parse_line(raw) if raw else None
        now  = time.time()

        if data:
            light, noise, weight = data
            if self.calibrating:
                self.sample_list.append((light, noise, weight))
                if len(self.sample_list) >= self.samples_needed:
                    self._set_baselines(now)
            else:
                self._handle_measurement(light, noise, weight, now)

        # session clock
        elapsed = int(now - self.session_start)
        h, rem = divmod(elapsed, 3600)
        m, s   = divmod(rem, 60)
        self.session_label.config(text=f"Session: {h:02d}:{m:02d}:{s:02d}")

        # chart refresh
        self._chart_tick += 1
        if self._chart_tick >= self._chart_every:
            self._chart_tick = 0
            self._refresh_chart()

        self.root.after(self.update_ms, self.update_loop)

    # ── Calibration ───────────────────────────────────────────────────────────

    def _set_baselines(self, now: float) -> None:
        n = len(self.sample_list)
        self.light_baseline = sum(s[0] for s in self.sample_list) / n
        self.noise_baseline = sum(s[1] for s in self.sample_list) / n
        avg_w = sum(s[2] for s in self.sample_list) / n

        self.calibrating      = False
        self.sample_list      = []
        self.last_weight_pct  = avg_w
        self.last_refill_time = now
        self.refill_level_pct = avg_w
        self.is_empty         = avg_w <= self.EMPTY_THRESHOLD

    # ── Measurement handling ──────────────────────────────────────────────────

    def _handle_measurement(
        self, light: int, noise: int, weight: float, now: float
    ) -> None:
        current_pct = max(0.0, min(100.0, weight))

        light_status, light_red = self._classify_light(light)
        noise_status, noise_red = self._classify_noise(noise)
        self._update_hydration(current_pct, now)
        hydr_status,  hydr_red  = self._classify_hydration()

        score         = analytics.compute_risk_score(
            light_red, noise_red, hydr_red, self.is_empty, self.drink_rate_slow
        )
        level, _color = analytics.risk_level(score)

        db.log_reading(self.session_id, light, noise, current_pct, score)
        self.risk_history.append(score)

        rate_str = f"{self.drink_rate_per_hr:.1f} %/hr"
        self._update_sensor_tile(self.light_tile, str(light),        light_status, light_red)
        self._update_sensor_tile(self.noise_tile, str(noise),        noise_status, noise_red)
        self._update_sensor_tile(
            self.hydr_tile,
            f"{int(current_pct)}%",
            f"{hydr_status}  ({rate_str})",
            hydr_red,
        )
        self._update_risk_tile_ui(score, level)
        self._update_env_bar(light_red, noise_red, hydr_red, score, level)

    # ── Classification ────────────────────────────────────────────────────────

    def _classify_light(self, value: int) -> tuple[str, bool]:
        margin = self.LIGHT_MARGIN * abs(self.light_baseline)
        if value > self.light_baseline + margin:
            return "TOO BRIGHT", True
        return "NORMAL", False

    def _classify_noise(self, value: int) -> tuple[str, bool]:
        margin = self.NOISE_MARGIN * abs(self.noise_baseline)
        if value > self.noise_baseline + margin:
            return "LOUD", True
        return "NORMAL", False

    def _classify_hydration(self) -> tuple[str, bool]:
        if self.is_empty or self.drink_rate_slow:
            return "LOW", True
        return "NORMAL", False

    # ── Hydration logic ───────────────────────────────────────────────────────

    def _update_hydration(self, current_pct: float, now: float) -> None:
        if self.last_refill_time is None:
            self.last_refill_time = now
            self.refill_level_pct = current_pct
        if self.last_weight_pct is None:
            self.last_weight_pct = current_pct

        rise = current_pct - self.last_weight_pct
        if rise >= self.REFILL_RISE_MIN:
            self.last_refill_time = now
            self.refill_level_pct = current_pct

        elapsed_hours = max(1.0, now - self.last_refill_time) / 3600.0
        consumed = max(0.0, self.refill_level_pct - current_pct)
        self.drink_rate_per_hr = consumed / elapsed_hours
        self.drink_rate_slow   = 0 < self.drink_rate_per_hr < self.SLOW_RATE
        self.is_empty          = current_pct <= self.EMPTY_THRESHOLD
        self.last_weight_pct   = current_pct

    # ── Serial → Arduino ──────────────────────────────────────────────────────

    def _send_lcd(self, msg: str) -> None:
        if msg == self.last_lcd_msg or not self.ser:
            return
        try:
            self.ser.write((msg + "\n").encode("utf-8"))
            self.last_lcd_msg = msg
        except Exception:
            pass

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _tile_colors(self, is_red: bool) -> tuple[str, str]:
        return (_CRIT_BG, _CRIT_FG) if is_red else (_GOOD_BG, _GOOD_FG)

    def _update_sensor_tile(
        self, tile: dict, value: str, status: str, is_red: bool
    ) -> None:
        bg, fg = self._tile_colors(is_red)
        for widget in (tile["outer"], tile["title"], tile["val"], tile["status"]):
            widget.config(bg=bg)
        for widget in (tile["title"], tile["val"], tile["status"]):
            widget.config(fg=fg)
        tile["val"].config(text=value)
        tile["status"].config(text=f"STATUS: {status}")

    def _update_risk_tile_ui(self, score: int, level: str) -> None:
        tile = self.risk_tile
        if level == "HIGH":
            bg, fg = _CRIT_BG, _CRIT_FG
        elif level == "MODERATE":
            bg, fg = _WARN_BG, _WARN_FG
        else:
            bg, fg = _GOOD_BG, _GOOD_FG
        for widget in (tile["outer"], tile["title"], tile["score"], tile["level"]):
            widget.config(bg=bg)
        for widget in (tile["title"], tile["score"], tile["level"]):
            widget.config(fg=fg)
        tile["score"].config(text=str(score))
        tile["level"].config(text=level)

    def _update_env_bar(
        self,
        light_red: bool,
        noise_red: bool,
        hydr_red: bool,
        score: int,
        level: str,
    ) -> None:
        alert_type = sev = amsg = None

        if noise_red:
            text = "ALERT: ROOM IS TOO NOISY — CHECK IN ON THE PATIENT IMMEDIATELY"
            lcd  = "NOISY"
            alert_type, sev, amsg = "NOISE", "HIGH", "Room noise exceeded safe threshold"
        elif light_red:
            text = "ALERT: ROOM IS TOO BRIGHT — ADJUST LIGHTS FOR PATIENT COMFORT"
            lcd  = "TOO BRIGHT"
            alert_type, sev, amsg = "LIGHT", "MODERATE", "Light level exceeded baseline by >50%"
        elif hydr_red:
            if self.is_empty:
                text = "ALERT: HYDRATION CRITICAL — REFILL THE WATER BOTTLE NOW"
                lcd  = "REFILL NOW"
                sev  = "HIGH"
                amsg = "Bottle below 5% capacity"
            else:
                rate = self.drink_rate_per_hr
                text = "ALERT: DRINKING RATE LOW — PLEASE REMIND THE PATIENT TO DRINK"
                lcd  = "DRINK MORE"
                sev  = "MODERATE"
                amsg = f"Drink rate {rate:.1f}%/hr is below the 10%/hr target"
            alert_type = "HYDRATION"
        else:
            text = f"ENVIRONMENT NORMAL   |   Risk Score: {score} / 100   |   Level: {level}"
            lcd  = "OK"

        is_alert = noise_red or light_red or hydr_red
        bar_bg = _ALERT_BG if is_alert else _OK_BG
        bar_fg = _ALERT_FG if is_alert else _OK_FG
        self.env_frame.config(bg=bar_bg)
        self.env_label.config(text=text, bg=bar_bg, fg=bar_fg)

        self._send_lcd(lcd)

        alert_key = f"{alert_type}:{sev}" if alert_type else None
        if alert_key and alert_key != self.last_alert_key:
            self.last_alert_key = alert_key
            db.log_alert(self.session_id, alert_type, sev, amsg)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.alert_tree.insert(
                "", 0, values=(ts, alert_type, sev, amsg), tags=(sev,)
            )
        elif not alert_key:
            self.last_alert_key = None

    # ── Chart ─────────────────────────────────────────────────────────────────

    def _draw_chart_axes(self) -> None:
        self.ax.set_facecolor("#ffffff")
        self.ax.set_ylim(0, 105)
        self.ax.set_xlabel("Seconds ago", fontsize=8)
        self.ax.set_ylabel("Risk Score", fontsize=8)
        self.ax.tick_params(labelsize=7)
        self.fig.tight_layout(pad=0.6)

    def _refresh_chart(self) -> None:
        if len(self.risk_history) < 2:
            return
        self.ax.clear()
        self._draw_chart_axes()

        scores = list(self.risk_history)
        dt     = self.update_ms / 1000.0
        xs     = [-(len(scores) - 1 - i) * dt for i in range(len(scores))]

        self.ax.axhline(60, color="#e53e3e", linewidth=0.8, linestyle="--", alpha=0.6)
        self.ax.axhline(30, color="#dd6b20", linewidth=0.8, linestyle="--", alpha=0.6)
        self.ax.text(xs[0], 62, "High",     fontsize=7, color="#e53e3e", alpha=0.75)
        self.ax.text(xs[0], 32, "Moderate", fontsize=7, color="#dd6b20", alpha=0.75)

        self.ax.plot(xs, scores, color="#e53e3e", linewidth=1.8, zorder=3)
        self.ax.fill_between(xs, scores, alpha=0.13, color="#e53e3e")
        self.ax.set_xlim(xs[0], 0)
        self.canvas.draw_idle()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        today = datetime.date.today().isoformat()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"delirium_monitor_session_{self.session_id}_{today}.csv",
        )
        if path:
            db.export_session_csv(self.session_id, path)
            stats = db.get_session_stats(self.session_id)
            messagebox.showinfo(
                "Export Complete",
                f"Session data saved to:\n{path}\n\n"
                f"Readings: {stats.get('total', 0)}\n"
                f"Avg risk score: {(stats.get('avg_risk') or 0):.1f}\n"
                f"Peak risk score: {stats.get('peak_risk', 0)}\n"
                f"Avg hydration: {(stats.get('avg_hydration') or 0):.1f}%",
            )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()
    sc = config["serial"]
    try:
        ser: serial.Serial | None = serial.Serial(sc["port"], sc["baud"], timeout=sc["timeout"])
    except serial.SerialException as exc:
        print(f"Serial unavailable ({exc}). Running in demo mode — no live data.")
        ser = None

    root = tk.Tk()
    app  = RoomEnvironmentGUI(root, ser, config)

    def on_close() -> None:
        db.end_session(app.session_id)
        if ser and ser.is_open:
            ser.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
