import serial
import time
import tkinter as tk

# ---------- SERIAL SETTINGS ----------
PORT = "/dev/cu.usbmodem14101"   # e.g. "COM3" on Windows
BAUD = 115200


# ---------- PARSE ARDUINO LINE ----------
# Arduino sends: lavg,smag,weight
def parse_line(line: str):
    parts = line.split(",")
    if len(parts) != 3:
        return None
    try:
        light = int(parts[0])
        noise = int(parts[1])
        weight = float(parts[2])
        return light, noise, weight
    except ValueError:
        return None


class RoomEnvironmentGUI:
    def __init__(self, root, ser):
        self.root = root
        self.ser = ser

        self.root.title("Room Environment Status")
        self.root.geometry("1000x550")

        # ----- baselines -----
        self.light_baseline = None
        self.noise_baseline = None
        self.weight_baseline = None  # full bottle

        self.calibrating = True
        self.samples_needed = 20
        self.sample_list = []

        # ----- hydration drink‑rate tracking -----
        self.weight_history = []       # (time, weight)
        self.last_weight = None
        self.last_drink_time = None

        self.reminder_active = False
        self.reminder_time = None
        self.nurse_escalation = False
        self.critical_alert = False

        # thresholds
        self.DRINK_EVENT_DROP_RATIO = 0.05   # 5% of full bottle
        self.REFILL_RISE_RATIO = 0.20       # 20% refill
        self.REMINDER_DELAY_SEC = 2 * 60 * 60   # 2 hours
        self.REMINDER_ESCALATE_SEC = 10 * 60    # 10 minutes
        self.CRITICAL_RATIO = 0.20              # <20% = critical
        self.TARGET_2H_PCT = 60.0               # should drink 60% in 2h

        # refresh every 1.5s
        self.update_ms = 1500

        # ---------- UI ----------
        title = tk.Label(
            root,
            text="ROOM ENVIRONMENT STATUS",
            font=("Helvetica", 24, "bold"),
        )
        title.pack(pady=15)

        main = tk.Frame(root)
        main.pack(expand=True, fill="both", padx=20, pady=10)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=1)

        self.light_box = self._make_box(main, 0, "LIGHT")
        self.noise_box = self._make_box(main, 1, "NOISE")
        self.hydr_box = self._make_box(main, 2, "HYDRATION")

        self.env_frame = tk.Frame(root, bd=3, relief="ridge")
        self.env_frame.pack(fill="x", padx=20, pady=15)

        self.env_label = tk.Label(
            self.env_frame,
            text="ENVIRONMENT NORMAL (calibrating...)",
            font=("Helvetica", 16, "bold"),
        )
        self.env_label.pack(padx=10, pady=10)

        self.update_loop()

    def _make_box(self, parent, col, title):
        frame = tk.Frame(parent, bd=2, relief="groove")
        frame.grid(row=0, column=col, sticky="nsew", padx=10, pady=10)

        title_label = tk.Label(frame, text=title, font=("Helvetica", 18, "bold"))
        title_label.pack(pady=(10, 5))

        value_label = tk.Label(frame, text="--", font=("Helvetica", 26, "bold"))
        value_label.pack(pady=5)

        status_label = tk.Label(
            frame,
            text="STATUS: --",
            font=("Helvetica", 14, "bold"),
        )
        status_label.pack(pady=(5, 15))

        return {"frame": frame, "value": value_label, "status": status_label}

    # ---------- MAIN LOOP ----------
    def update_loop(self):
        raw = ""
        try:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            pass

        data = parse_line(raw) if raw else None

        if data:
            light, noise, weight = data
            now = time.time()

            if self.calibrating:
                self.sample_list.append((light, noise, weight))
                if len(self.sample_list) >= self.samples_needed:
                    self.set_baselines(now)
            else:
                self.handle_measurement(light, noise, weight, now)

        self.root.after(self.update_ms, self.update_loop)

    # ---------- BASELINES ----------
    def set_baselines(self, now):
        n = len(self.sample_list)
        self.light_baseline = sum(s[0] for s in self.sample_list) / n
        self.noise_baseline = sum(s[1] for s in self.sample_list) / n
        self.weight_baseline = sum(s[2] for s in self.sample_list) / n

        self.calibrating = False
        self.sample_list = []

        self.last_weight = self.weight_baseline
        self.last_drink_time = now
        self.weight_history = [(now, self.weight_baseline)]

        self.env_frame.config(bg="#00ff00")
        self.env_label.config(
            text="ENVIRONMENT NORMAL",
            bg="#00ff00",
            fg="#000000",
        )

    # ---------- MEASUREMENT HANDLING ----------
    def handle_measurement(self, light, noise, weight, now):
        # store hydration history (keep last 3h)
        self.weight_history.append((now, weight))
        cutoff = now - 3 * 60 * 60
        self.weight_history = [w for w in self.weight_history if w[0] >= cutoff]

        # light + noise status from baselines
        light_status, light_red = self.classify_light(light)
        noise_status, noise_red = self.classify_noise(noise)

        # hydration fullness ratio
        ratio = 1.0
        if self.weight_baseline and self.weight_baseline != 0:
            ratio = max(0.0, min(1.0, weight / self.weight_baseline))

        # detect drink or refill events
        self.detect_drink_or_refill(weight, now)

        # update hydration drink‑rate / alerts
        self.update_hydration_logic(weight, ratio, now)

        # hydration tile status (NORMAL / LOW)
        hydr_status, hydr_red = self.classify_hydration_tile(ratio)

        # update tiles (values only)
        self.update_box(self.light_box, light, light_status, light_red)
        self.update_box(self.noise_box, noise, noise_status, noise_red)
        self.update_box(self.hydr_box, f"{int(ratio * 100)}%", hydr_status, hydr_red)

        # global bar
        self.update_environment_bar(light_red, noise_red, hydr_red, ratio)

        self.last_weight = weight

    # ---------- CLASSIFICATION ----------
    def classify_light(self, value):
        margin = 0.5 * abs(self.light_baseline)
        if value > self.light_baseline + margin:
            return "TOO BRIGHT", True
        else:
            return "NORMAL", False

    def classify_noise(self, value):
        margin = 0.5 * abs(self.noise_baseline)
        if value > self.noise_baseline + margin:
            return "LOUD", True
        else:
            return "NORMAL", False

    def classify_hydration_tile(self, ratio):
        # LOW if <20% or any hydration alert active
        if (
            ratio < self.CRITICAL_RATIO
            or self.reminder_active
            or self.nurse_escalation
            or self.critical_alert
        ):
            return "LOW", True
        else:
            return "NORMAL", False

    # ---------- HYDRATION LOGIC ----------
    def detect_drink_or_refill(self, weight, now):
        if self.last_weight is None or self.weight_baseline is None:
            return

        diff = self.last_weight - weight      # positive = lighter (drank)
        rise = weight - self.last_weight      # positive = heavier (refill)

        drink_drop = self.DRINK_EVENT_DROP_RATIO * self.weight_baseline
        refill_rise = self.REFILL_RISE_RATIO * self.weight_baseline

        # drink event
        if diff >= drink_drop:
            self.last_drink_time = now
            self.reminder_active = False
            self.reminder_time = None
            self.nurse_escalation = False

        # refill event
        if rise >= refill_rise:
            self.weight_baseline = weight
            self.weight_history = [(now, weight)]
            self.last_drink_time = now
            self.reminder_active = False
            self.reminder_time = None
            self.nurse_escalation = False
            self.critical_alert = False

    def update_hydration_logic(self, current_weight, ratio, now):
        # critical if bottle < 20%
        self.critical_alert = ratio < self.CRITICAL_RATIO

        # 2‑hour drink rate
        two_hours_ago = now - 2 * 60 * 60
        past_weights = [w for t, w in self.weight_history if t <= two_hours_ago]
        if past_weights:
            start_weight = past_weights[-1]
        else:
            start_weight = self.weight_history[0][1] if self.weight_history else current_weight

        consumed = max(0.0, start_weight - current_weight)
        consumed_pct_2h = 0.0
        if self.weight_baseline and self.weight_baseline != 0:
            consumed_pct_2h = (consumed / self.weight_baseline) * 100.0

        if self.last_drink_time is None:
            self.last_drink_time = now
        time_since_drink = now - self.last_drink_time

        # poor drink rate -> reminder
        if (
            time_since_drink >= self.REMINDER_DELAY_SEC
            and consumed_pct_2h < self.TARGET_2H_PCT
            and not self.reminder_active
        ):
            self.reminder_active = True
            self.reminder_time = now

        # reminder ignored for 10 min -> nurse escalation
        if self.reminder_active and self.reminder_time is not None:
            if (now - self.reminder_time >= self.REMINDER_ESCALATE_SEC
                    and self.last_drink_time < self.reminder_time):
                self.nurse_escalation = True

    # ---------- UI HELPERS ----------
    def update_box(self, box, value, status_text, is_red):
        color = "#ff0000" if is_red else "#00ff00"
        # Color the entire box
        box["frame"].config(bg=color)
        # Text blends into the box (same background)
        box["value"].config(
            text=str(value),
            bg=color,
            fg="black",   # black text
            font=("Helvetica", 26, "bold")
        )
        box["status"].config(
            text=f"STATUS: {status_text}",
            bg=color,
            fg="black",   # black text
            font=("Helvetica", 14, "bold")
        )

    def update_environment_bar(self, light_red, noise_red, hydr_red, ratio):
        if noise_red:
            text = "ALERT: ROOM IS TOO NOISY! CHECK IN ON THE PATIENT IMMEDIATELY!"
            bg = "#ff0000"
            fg = "#ffffff"
        elif light_red:
            text = "ALERT: ROOM IS TOO BRIGHT! ADJUST THE LIGHTS FOR THE PATIENT."
            bg = "#ff0000"
            fg = "#ffffff"
        elif hydr_red:
            if self.critical_alert or ratio < self.CRITICAL_RATIO:
                text = "ALERT: HYDRATION CRITICAL! REFILL THE WATER BOTTLE NOW."
            elif self.nurse_escalation:
                text = "ALERT: PATIENT IGNORED HYDRATION REMINDERS. NURSE CHECK REQUIRED."
            elif self.reminder_active:
                text = "REMINDER: PATIENT SHOULD DRINK WATER TO STAY HYDRATED."
            else:
                text = "ALERT: HYDRATION LOW. CHECK THE PATIENT'S WATER LEVEL."
            bg = "#ff0000"
            fg = "#ffffff"
        else:
            text = "ENVIRONMENT NORMAL"
            bg = "#00ff00"
            fg = "#000000"

        self.env_frame.config(bg=bg)
        self.env_label.config(text=text, bg=bg, fg=fg)


# ---------- MAIN ----------
def main():
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        root = tk.Tk()
        app = RoomEnvironmentGUI(root, ser)
        root.mainloop()


if __name__ == "__main__":
    main()
