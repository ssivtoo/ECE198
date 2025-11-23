import serial
import tkinter as tk

# ---------------- SERIAL SETTINGS ----------------

# CHANGE THIS TO YOUR ACTUAL ARDUINO PORT
PORT = "/dev/cu.usbmodem14101"   # e.g. "COM3" on Windows
BAUD = 115200


# ---------------- PARSE ARDUINO LINE ----------------
# Arduino sends: lavg,smag,weight
# Example: "601,71,-442.49"

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


# ---------------- GUI APP ----------------

class BaselineMonitor:
    def __init__(self, root, ser):
        self.root = root
        self.ser = ser

        self.root.title("Baseline Monitor (Light / Noise / Hydration)")
        self.root.geometry("850x450")

        # baseline values (set after calibration)
        self.light_baseline = None
        self.noise_baseline = None
        self.weight_baseline = None

        # collect first N readings for baseline
        self.calibrating = True
        self.samples_needed = 20        # how many readings for baseline
        self.sample_list = []           # list of (light, noise, weight)

        # update intervals
        self.update_ms = 500            # fast while calibrating
        self.update_ms_after_baseline = 30000   # 30 seconds

        # ------------- UI -------------
        title = tk.Label(
            root,
            text="Monitoring Noise, Light & Hydration (Baseline Based)",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=10)

        self.info_label = tk.Label(
            root,
            text="Calibrating baseline from first few seconds...",
            font=("Arial", 11)
        )
        self.info_label.pack(pady=5)

        main = tk.Frame(root)
        main.pack(expand=True, fill="both", padx=10, pady=10)

        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=1)

        self.light_box = self._make_box(main, 0, "LIGHT")
        self.noise_box = self._make_box(main, 1, "NOISE")
        self.hydr_box = self._make_box(main, 2, "HYDRATION (Bottle Weight)")

        # start update loop
        self.update_loop()

    def _make_box(self, parent, col, title):
        """Create one card for Light / Noise / Hydration."""
        frame = tk.Frame(parent, bd=2, relief="groove", padx=10, pady=10)
        frame.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)

        t = tk.Label(frame, text=title, font=("Arial", 13, "bold"))
        t.pack()

        baseline_label = tk.Label(frame, text="Baseline: --", font=("Arial", 11))
        baseline_label.pack(pady=3)

        current_label = tk.Label(frame, text="Current: --", font=("Arial", 11))
        current_label.pack(pady=3)

        delta_label = tk.Label(frame, text="Change: --", font=("Arial", 11))
        delta_label.pack(pady=3)

        status_label = tk.Label(frame, text="Status: --", font=("Arial", 11, "bold"))
        status_label.pack(pady=3)

        return {
            "frame": frame,
            "baseline": baseline_label,
            "current": current_label,
            "delta": delta_label,
            "status": status_label,
        }

    # ---------------- MAIN LOOP ----------------

    def update_loop(self):
        """Read from serial and either calibrate or update UI."""
        raw = ""
        try:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            pass

        data = parse_line(raw) if raw else None

        if data:
            light, noise, weight = data

            if self.calibrating:
                self.sample_list.append((light, noise, weight))
                remaining = self.samples_needed - len(self.sample_list)

                if remaining > 0:
                    self.info_label.config(
                        text=f"Calibrating baseline... {remaining} samples left"
                    )
                else:
                    self.set_baselines_from_samples()
            else:
                self.update_boxes(light, noise, weight)

        self.root.after(self.update_ms, self.update_loop)

    # ---------------- BASELINE ----------------

    def set_baselines_from_samples(self):
        """Average the first N samples to get baseline for all 3."""
        n = len(self.sample_list)
        if n == 0:
            return

        self.light_baseline = sum(s[0] for s in self.sample_list) / n
        self.noise_baseline = sum(s[1] for s in self.sample_list) / n
        self.weight_baseline = sum(s[2] for s in self.sample_list) / n

        self.calibrating = False
        self.sample_list = []

        self.info_label.config(
            text="Baselines set from first few seconds. Now checking every 30 seconds."
        )

        self.light_box["baseline"].config(
            text=f"Baseline: {self.light_baseline:.1f}"
        )
        self.noise_box["baseline"].config(
            text=f"Baseline: {self.noise_baseline:.1f}"
        )
        self.hydr_box["baseline"].config(
            text=f"Baseline (full): {self.weight_baseline:.1f} g"
        )

        # slow down checks to every 30 seconds
        self.update_ms = self.update_ms_after_baseline

    # ---------------- UPDATE UI ----------------

    def update_boxes(self, light, noise, weight):
        # LIGHT (higher = worse)
        self._update_one(
            self.light_box,
            current=light,
            baseline=self.light_baseline,
            higher_is_bad=True
        )

        # NOISE (higher = worse)
        self._update_one(
            self.noise_box,
            current=noise,
            baseline=self.noise_baseline,
            higher_is_bad=True
        )

        # HYDRATION (lower = worse)
        self._update_one(
            self.hydr_box,
            current=weight,
            baseline=self.weight_baseline,
            higher_is_bad=False,
            is_weight=True
        )

    # ---------------- LOGIC (MARGIN = 0.5, PURE RED/GREEN) ----------------

    def _update_one(self, box, current, baseline,
                    higher_is_bad=True, is_weight=False):
        """
        Compare current value to baseline using a 50% margin.
        Anything outside baseline ± 0.5*baseline = RED
        Anything inside = GREEN
        """

        if is_weight:
            box["current"].config(text=f"Current: {current:.1f} g")
            baseline_text = f"Baseline (full): {baseline:.1f} g"
        else:
            box["current"].config(text=f"Current: {current:.1f}")
            baseline_text = f"Baseline: {baseline:.1f}"

        box["baseline"].config(text=baseline_text)

        delta = current - baseline
        box["delta"].config(text=f"Change: {delta:+.1f}")

        # margin = 50% of baseline
        margin = 0.50 * abs(baseline)

        # PURE colors only
        if higher_is_bad:
            # light/noise: higher than baseline+margin is bad
            if current > baseline + margin:
                status = "Above baseline"
                color = "#ff0000"   # PURE RED
            else:
                status = "Within baseline range"
                color = "#00ff00"   # PURE GREEN
        else:
            # hydration: lower than baseline-margin means water used (bad)
            if current < baseline - margin:
                status = "Below baseline (water used)"
                color = "#ff0000"   # PURE RED
            else:
                status = "Within baseline range"
                color = "#00ff00"   # PURE GREEN

        box["status"].config(text=f"Status: {status}")
        box["frame"].config(bg=color)
        for w in box["frame"].winfo_children():
            w.config(bg=color)


# ---------------- MAIN ENTRY ----------------

def main():
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        root = tk.Tk()
        app = BaselineMonitor(root, ser)
        root.mainloop()


if __name__ == "__main__":
    main()
