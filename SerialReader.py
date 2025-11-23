import serial

PORT = "/dev/cu.usbmodem101"
BAUD = 115200

def parse_line(line: str):
    """
    Input:  '532,123,45.5'
    Output: (light, sound, weight) as ints/floats
    """
    parts = line.split(",")
    if len(parts) != 3:
        return None

    try:
        sound = int(parts[0])
        light = int(parts[1])
        weight = float(parts[2])
        return light, sound, weight
    except ValueError:
        return None

def interpret(light: int, sound: int, weight: float) -> str:
    """
    Turn raw numbers into simple meaning.
    You can change these thresholds to whatever you want.
    """
    if light < 200:
        light_status = "Dark"
    elif light < 600:
        light_status = "Medium"
    else:
        light_status = "Bright"

    if sound < 200:
        sound_status = "Quiet"
    elif sound < 600:
        sound_status = "Normal"
    else:
        sound_status = "Loud"

    if weight < 10:
        weight_status = "Empty"
    elif weight < 200:
        weight_status = "Partial"
    else:
        weight_status = "Full"

    return f"Light: {light} ({light_status}), Sound: {sound} ({sound_status}), Weight: {weight:.1f}g ({weight_status})"

def main():
    try:
        with serial.Serial(PORT, BAUD, timeout=1) as ser:
            print("Connected to", PORT, "- press Ctrl+C to quit")
            while True:
                try:
                    # read one line from serial
                    raw_bytes = ser.readline()
                except serial.SerialException as e:
                    # handle unplug / serial error without crashing
                    print("Serial connection lost:", e)
                    print("Exiting cleanly.")
                    break

                if not raw_bytes:
                    continue  # nothing this loop

                raw = raw_bytes.decode("utf-8", errors="ignore").strip()

                data = parse_line(raw)
                if not data:
                    print("Bad line:", raw)
                    continue

                light, sound, weight = data
                meaning = interpret(light, sound, weight)
                print(meaning)

    except serial.SerialException as e:
        # could not open port, or other error at start
        print(f"Could not open serial port {PORT}: {e}")
    except KeyboardInterrupt:
        # user hit Ctrl+C
        print("\nStopped by user.")

if __name__ == "__main__":
    main()