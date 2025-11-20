import serial

PORT = "/dev/cu.usbmodem14101"
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
        light = int(parts[0])
        sound = int(parts[1])
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
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        print("Connected to", PORT)
        while True:
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw:
                continue   # nothing received this loop

            data = parse_line(raw)
            if not data:
                print("Bad line:", raw)
                continue

            light, sound, weight = data
            meaning = interpret(light, sound, weight)
            print(meaning)

if __name__ == "__main__":
    main()