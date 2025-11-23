import serial
import time
import tkinter as tk

# ---------- SERIAL SETTINGS ----------
PORT = "/dev/cu.usbmodem101"
BAUD = 115200


# ---------- PARSE ARDUINO LINE ----------
# Arduino sends: light,sound,weight_pct (0-100 after your calibration)
def parse_line(line):
    parts = line.split(",")
    if len(parts) != 3:
        return None
    try:
        light = int(parts[0])
        noise = int(parts[1])
        weight = float(parts[2])/10.23
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
        self.light_baseline = 0.0
        self.noise_baseline = 0.0
        self.weight_baseline = 0.0

        self.calibrating = True
        self.samples_needed = 20
        self.sample_list = []

        # ----- hydration tracking (percent-based) -----
        self.last_weight_pct = None
        self.last_refill_time = None
        self.refill_level_pct = None
        self.drink_rate_per_hr = 0.0
        self.drink_rate_slow = False
        self.is_empty = False
        self.last_lcd_msg = None  # avoid spamming LCD

        # thresholds
        self.EMPTY_THRESHOLD = 5.0           # <=5% means empty
        self.SLOW_RATE_THRESHOLD = 10.0      # <10%/hr is too slow
        self.REFILL_RISE_MIN = 10.0          # rise by 10% = refill

        # refresh every 0.5s
        self.update_ms = 500

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

        print(now, end="")
        print(data)

        self.root.after(self.update_ms, self.update_loop)

    # ---------- BASELINES ----------
    def set_baselines(self, now):
        n = len(self.sample_list)
        self.light_baseline = sum(s[0] for s in self.sample_list) / n
        self.noise_baseline = sum(s[1] for s in self.sample_list) / n
        avg_weight_pct = sum(s[2] for s in self.sample_list) / n
        self.weight_baseline = avg_weight_pct

        self.calibrating = False
        self.sample_list = []

        # treat baseline as a fresh refill
        self.last_weight_pct = avg_weight_pct
        self.last_refill_time = now
        self.refill_level_pct = avg_weight_pct
        self.drink_rate_per_hr = 0.0
        self.drink_rate_slow = False
        self.is_empty = avg_weight_pct <= self.EMPTY_THRESHOLD

        self.env_frame.config(bg="#00ff00")
        self.env_label.config(
            text="ENVIRONMENT NORMAL",
            bg="#00ff00",
            fg="#000000",
        )

    # ---------- MEASUREMENT HANDLING ----------
    def handle_measurement(self, light, noise, weight, now):
        # clamp weight to 0-100% after your calibration
        current_pct = max(0.0, min(100.0, weight))

        # light + noise status from baselines
        light_status, light_red = self.classify_light(light)
        noise_status, noise_red = self.classify_noise(noise)

        # update hydration drink rate / alerts using percent
        self.update_hydration_state(current_pct, now)

        # hydration tile status (NORMAL / LOW)
        hydr_status, hydr_red = self.classify_hydration_tile(current_pct)

        # build hydration status text with rate (e.g., "LOW (8.5%/hr)")
        rate_str = f"{self.drink_rate_per_hr:.1f}%/hr"
        hydr_status_text = f"{hydr_status} ({rate_str})"

        # update tiles (values only)
        self.update_box(self.light_box, light, light_status, light_red)
        self.update_box(self.noise_box, noise, noise_status, noise_red)
        self.update_box(self.hydr_box, f"{int(current_pct)}%", hydr_status_text, hydr_red)

        # global bar
        self.update_environment_bar(light_red, noise_red, hydr_red)

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

    def classify_hydration_tile(self, current_pct):
        if self.is_empty or self.drink_rate_slow:
            return "LOW", True
        return "NORMAL", False

    # ---------- HYDRATION LOGIC ----------
    def update_hydration_state(self, current_pct, now):
        """
        Use percent directly:
          - Detect refill when the level jumps.
          - Compute drink rate (%/hr) since last refill.
          - Flag empty when under threshold.
        """
        if self.last_refill_time is None:
            self.last_refill_time = now
            self.refill_level_pct = current_pct

        if self.last_weight_pct is None:
            self.last_weight_pct = current_pct

        # Detect refill as a rise of at least REFILL_RISE_MIN percent.
        rise = current_pct - self.last_weight_pct
        if rise >= self.REFILL_RISE_MIN:
            self.last_refill_time = now
            self.refill_level_pct = current_pct

        elapsed_sec = max(1.0, now - self.last_refill_time)
        elapsed_hours = elapsed_sec / 60.0                      # change this to accelerate time
                                                                # 3600.0 for normal hour
        consumed = max(0.0, self.refill_level_pct - current_pct)
        self.drink_rate_per_hr = consumed / elapsed_hours
        self.drink_rate_slow = self.drink_rate_per_hr < self.SLOW_RATE_THRESHOLD and self.drink_rate_per_hr != 0
        self.is_empty = current_pct <= self.EMPTY_THRESHOLD
        self.last_weight_pct = current_pct

    # ---------- SERIAL → ARDUINO (LCD MESSAGES) ----------
    def send_lcd_message(self, msg: str):
        """
        Send a short text command to the Arduino so it can display
        something on the LCD. The Arduino sketch should read a line
        from Serial and react to these messages.
        """
        if not self.ser:
            return
        try:
            self.ser.write((msg + "\n").encode("utf-8"))
        except Exception:
            # if serial is gone, just ignore
            pass

    # ---------- UI HELPERS ----------
    def update_box(self, box, value, status_text, is_red):
        color = "#ff0000" if is_red else "#00ff00"
        box["frame"].config(bg=color)
        box["value"].config(text=str(value), bg=color)
        box["status"].config(text=f"STATUS: {status_text}", bg=color)

    def update_environment_bar(self, light_red, noise_red, hydr_red):
        """
        Decide the main environment status text AND a short LCD message
        to send to the Arduino (for a 16x2 style display).
        """
        lcd_msg = None

        if noise_red:
            text = "ALERT: ROOM IS TOO NOISY! CHECK IN ON THE PATIENT IMMEDIATELY!"
            bg = "#ff0000"
            fg = "#ffffff"
            lcd_msg = "NOISY"
        elif light_red:
            text = "ALERT: ROOM IS TOO BRIGHT! ADJUST THE LIGHTS FOR THE PATIENT."
            bg = "#ff0000"
            fg = "#ffffff"
            lcd_msg = "TOO BRIGHT"
        elif hydr_red:
            if self.is_empty:
                text = "ALERT: HYDRATION CRITICAL! REFILL THE WATER BOTTLE NOW."
                lcd_msg = "REFILL NOW"
            elif self.drink_rate_slow:
                text = "ALERT: DRINKING TOO SLOW. REMIND THE PATIENT."
                lcd_msg = "DRINK MORE"
            else:
                text = "ALERT: HYDRATION LOW. CHECK THE PATIENT'S WATER LEVEL."
                lcd_msg = "LOW WATER"
            bg = "#ff0000"
            fg = "#ffffff"
        else:
            text = "ENVIRONMENT NORMAL"
            bg = "#00ff00"
            fg = "#000000"
            lcd_msg = "OK"

        self.env_frame.config(bg=bg)
        self.env_label.config(text=text, bg=bg, fg=fg)

        # Only send when message changes to avoid spamming the serial link
        if lcd_msg is not None and lcd_msg != self.last_lcd_msg:
            self.send_lcd_message(lcd_msg)
            self.last_lcd_msg = lcd_msg


# ---------- MAIN ----------
def main():
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        root = tk.Tk()
        app = RoomEnvironmentGUI(root, ser)
        root.mainloop()


if __name__ == "__main__":
    main()
