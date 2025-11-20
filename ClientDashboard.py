class MonitorGUI:
    def __init__(self, root, ser):
        self.root = root
        self.ser = ser

        self.root.title("Bedside Environment Monitor")
        self.root.geometry("900x450")

        # Fonts
        self.title_font = tkfont.Font(size=18, weight="bold")
        self.value_font = tkfont.Font(size=24, weight="bold")
        self.status_font = tkfont.Font(size=14, weight="bold")

        # Title
        tk.Label(
            root,
            text="ROOM ENVIRONMENT STATUS (LIGHT / NOISE / HYDRATION*)",
            font=self.title_font,
        ).pack(pady=10)

        # Frame for 3 boxes
        boxes = tk.Frame(root)
        boxes.pack(expand=True, fill="both", pady=5)
        boxes.columnconfigure(0, weight=1)
        boxes.columnconfigure(1, weight=1)
        boxes.columnconfigure(2, weight=1)

        # LIGHT box
        self.light_box = self._make_box(boxes, 0, "LIGHT")

        # NOISE box
        self.noise_box = self._make_box(boxes, 1, "NOISE")

        # HYDRATION box (UI only for now)
        self.hyd_box = self._make_box(boxes, 2, "HYDRATION*")
        self.hyd_box["value"].config(text="--")
        self.hyd_box["status"].config(text="Status: (coming soon)")

        # Nurse alert label
        self.alert_label = tk.Label(
            root,
            text="Waiting for data...",
            font=self.status_font,
            bd=2,
            relief="groove",
            padx=10,
            pady=10,
            wraplength=800,
        )
        self.alert_label.pack(pady=10, fill="x", padx=20)

        # Start periodic updates
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
        Periodically:
        - read a line from serial
        - parse and classify it
        - update the GUI
        """
        try:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            raw = ""

        if raw:
            data = parse_line(raw)
            if data:
                light, sound = data         # for now, only 2 values
                info = classify(light, sound)
                self.update_ui(info)
                # optional: still print console meaning if you want
                # print(interpret(light, sound))

        self.root.after(200, self.update_loop)  # 0.2s

    def update_ui(self, info: dict):
        # Light
        self._update_box(
            self.light_box,
            str(info["light"]),
            info["light_status"],
        )

        # Noise
        self._update_box(
            self.noise_box,
            str(info["sound"]),
            info["sound_status"],
        )

        # Hydration – no data yet; example for future:
        #
        # self._update_box(
        #     self.hyd_box,
        #     str(info["hydration"]),
        #     info["hydration_status"],
        # )

        # Nurse alert text
        alerts = []
        if info["sound_status"] == "Loud":
            alerts.append("Room is too noisy.")
        if info["light_status"] == "Bright":
            alerts.append("Room is too bright for rest.")
        # if "hydration_status" in info and info["hydration_status"] == "Low":
        #     alerts.append("Patient may need to drink water.")

        if alerts:
            self.alert_label.config(text="  |  ".join(alerts))
        else:
            self.alert_label.config(text="Environment is within target range.")

    def _update_box(self, box, value_text, status_text):
        box["value"].config(text=value_text)
        box["status"].config(text=f"Status: {status_text}")

        bg = status_color(status_text)
        box["frame"].config(bg=bg)
        for w in box["frame"].winfo_children():
            w.config(bg=bg)


# ================== MAIN ==================

def main():
    with serial.Serial(PORT, BAUD, timeout=0.5) as ser:
        root = tk.Tk()
        app = MonitorGUI(root, ser)
        root.mainloop()

if __name__ == "__main__":
    main()

