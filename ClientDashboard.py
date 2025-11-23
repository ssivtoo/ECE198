import tkinter as tk
from tkinter import font as tkfont
import random


def classify(light: int, sound: int):
    """
    Same idea as your interpret(): convert numbers into statuses.
    """
    # Light
    if light < 200:
        light_status = "Dark"
    elif light < 600:
        light_status = "Medium"
    else:
        light_status = "Bright"

    # Noise
    if sound < 200:
        sound_status = "Quiet"
    elif sound < 600:
        sound_status = "Normal"
    else:
        sound_status = "Loud"

    return {
        "light": light,
        "sound": sound,
        "light_status": light_status,
        "sound_status": sound_status,
    }


def status_color(status: str) -> str:
    s = status.lower()
    if s in ("dark", "medium", "quiet", "normal", "ok"):
        return "#c8f7c5"   # green-ish
    if s in ("bright", "loud", "high"):
        return "#ff0000"   # yellow-ish
    if s in ("low",):
        return "#ff0000"   # red-ish
    return "#ff0000"       # white


class MonitorGUI:
    def __init__(self, root):
        self.root = root

        self.root.title("Bedside Environment Monitor (TEST MODE)")
        self.root.geometry("900x450")

        # fonts
        self.title_font = tkfont.Font(size=18, weight="bold")
        self.value_font = tkfont.Font(size=24, weight="bold")
        self.status_font = tkfont.Font(size=14, weight="bold")

        # Title
        tk.Label(
            root,
            text="ROOM ENVIRONMENT STATUS (TEST DATA)",
            font=self.title_font,
        ).pack(pady=10)

        # frame for 3 boxes
        boxes = tk.Frame(root)
        boxes.pack(expand=True, fill="both", pady=5)
        boxes.columnconfigure(0, weight=1)
        boxes.columnconfigure(1, weight=1)
        boxes.columnconfigure(2, weight=1)

        # LIGHT box
        self.light_box = self._make_box(boxes, 0, "LIGHT")

        # NOISE box
        self.noise_box = self._make_box(boxes, 1, "NOISE")

        # HYDRATION placeholder box
        self.hyd_box = self._make_box(boxes, 2, "HYDRATION (coming soon)")
        self.hyd_box["value"].config(text="--")
        self.hyd_box["status"].config(text="Status: (inactive)")

        # alert label
        self.alert_font = tkfont.Font(size=24, weight="bold")  # BIG FONT

        self.alert_label = tk.Label(
            root,
            text="ALERT: WAITING FOR DATA...",
            font=self.alert_font,
            bd=4,
            relief="groove",
            padx=20,
            pady=20,
            fg="white",
            bg="#333333",   # dark background to pop visually
            wraplength=900,
        )

        self.alert_label.pack(pady=10, fill="x", padx=20)

        # start periodic updates
        self.update_loop()

    def _make_box(self, parent, col, title):
        frame = tk.Frame(parent, bd=2, relief="groove", padx=20, pady=20)
        frame.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")

        title_label = tk.Label(frame, text=title, font=self.title_font)
        title_label.pack()

        value_label = tk.Label(frame, text="--", font=self.value_font)
        value_label.pack(pady=10)

        status_label = tk.Label(frame, text="Status: --", font=self.status_font)
        status_label.pack()

        return {"frame": frame, "value": value_label, "status": status_label}

    def update_loop(self):
        """
        TEST MODE:
        generate fake random values for light and sound
        so you can see the GUI working without Arduino.
        """
        light = random.randint(0, 800)
        sound = random.randint(0, 800)

        info = classify(light, sound)
        self.update_ui(info)

        # run again after 500 ms
        self.root.after(500, self.update_loop)

    def update_ui(self, info: dict):
        # update LIGHT
        self._update_box(
            self.light_box,
            str(info["light"]),
            info["light_status"],
        )

        # update NOISE
        self._update_box(
            self.noise_box,
            str(info["sound"]),
            info["sound_status"],
        )

        # hydration box stays static for now

        # nurse alert
        alerts = []
        if info["sound_status"] == "Loud":
            alerts.append("Room is too noisy.")
        if info["light_status"] == "Bright":
            alerts.append("Room is too bright for rest.")

        
        if alerts:
            msg = " | ".join(alerts).upper()
            self.alert_label.config(
            text=f"ALERT: {msg}",
            bg="#ff0000",   # RED background when alerting
            fg="white")
        else:
            self.alert_label.config(
            text="ENVIRONMENT IS WITHIN TARGET RANGE",
            bg="#008000",   # GREEN background when safe
            fg="white"
        )


    def _update_box(self, box, value_text, status_text):
        box["value"].config(text=value_text)
        box["status"].config(text=f"Status: {status_text}")

        bg = status_color(status_text)
        box["frame"].config(bg=bg)
        for w in box["frame"].winfo_children():
            w.config(bg=bg)


if __name__ == "__main__":
    root = tk.Tk()
    app = MonitorGUI(root)
    root.mainloop()
