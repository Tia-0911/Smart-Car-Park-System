import sys
import os

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

import time
import requests
import RPi.GPIO as GPIO

from gpio_config import ULTRASONIC


# ============================================================
# SMART CAR PARK - ULTRASONIC SENSOR CONTROLLER
# ============================================================

BACKEND_URL = "http://10.27.34.79:8080"

DEVICE_API_KEY = "smart-parking-pi-test-2026"

DETECTION_DISTANCE_CM = 14

# Time between ultrasonic sensors
SENSOR_GAP = 1.5

# Time between complete sensor cycles
CYCLE_INTERVAL = 3


# ============================================================
# SENSOR CONFIGURATION
# ============================================================

SENSORS = {
    "sensor1": {
        "id": "PARK_A01",
        "name": "Parking Slot 1"
    },

    "sensor2": {
        "id": "PARK_A02",
        "name": "Parking Slot 2"
    },

    "sensor3": {
        "id": "PARK_A03",
        "name": "Parking Slot 3"
    },

    "sensor4": {
        "id": "PARK_A04",
        "name": "Parking Slot 4"
    },

    "sensor5": {
        "id": "ENTRANCE_01",
        "name": "Entrance"
    },

    "sensor6": {
        "id": "EXIT_01",
        "name": "Exit"
    }
}


# ============================================================
# BACKEND HEADERS
# ============================================================

HEADERS = {
    "X-Device-API-Key": DEVICE_API_KEY
}


# ============================================================
# GPIO SETUP
# ============================================================

GPIO.setmode(GPIO.BCM)

for sensor_name in SENSORS:

    trig_pin = ULTRASONIC[sensor_name]["trig"]
    echo_pin = ULTRASONIC[sensor_name]["echo"]

    GPIO.setup(trig_pin, GPIO.OUT)
    GPIO.setup(echo_pin, GPIO.IN)

    GPIO.output(trig_pin, GPIO.LOW)


# Give sensors time to initialise
time.sleep(2)


# ============================================================
# READ ONE ULTRASONIC SENSOR
# ============================================================

def read_distance(sensor_name):
    """
    Read distance from one HC-SR04 sensor.
    Returns distance in centimetres.
    Returns None if no echo is received.
    """

    trig_pin = ULTRASONIC[sensor_name]["trig"]
    echo_pin = ULTRASONIC[sensor_name]["echo"]

    # --------------------------------------------------------
    # Trigger ultrasonic pulse
    # --------------------------------------------------------

    GPIO.output(trig_pin, GPIO.HIGH)

    time.sleep(0.00001)

    GPIO.output(trig_pin, GPIO.LOW)

    # --------------------------------------------------------
    # Wait for ECHO HIGH
    # --------------------------------------------------------

    timeout = time.monotonic() + 0.1

    while GPIO.input(echo_pin) == GPIO.LOW:

        if time.monotonic() > timeout:
            return None

    pulse_start = time.monotonic()

    # --------------------------------------------------------
    # Wait for ECHO LOW
    # --------------------------------------------------------

    timeout = time.monotonic() + 0.1

    while GPIO.input(echo_pin) == GPIO.HIGH:

        if time.monotonic() > timeout:
            return None

    pulse_end = time.monotonic()

    # --------------------------------------------------------
    # Calculate distance
    # --------------------------------------------------------

    pulse_duration = pulse_end - pulse_start

    distance = (pulse_duration * 34300) / 2

    return round(distance, 2)


# ============================================================
# DETERMINE SENSOR STATUS
# ============================================================

def get_sensor_status(distance):

    if distance is None:
        return "error"

    if distance <= DETECTION_DISTANCE_CM:
        return "detected"

    return "clear"


# ============================================================
# SEND SENSOR DATA TO DJANGO
# ============================================================

def send_sensor_data(sensor_id, distance, status):

    url = f"{BACKEND_URL}/api/device/sensors/update/"

    payload = {
        "sensor_id": sensor_id,
        "value": status
    }

    try:

        response = requests.post(
            url,
            headers=HEADERS,
            json=payload,
            timeout=5
        )

        if response.status_code in (200, 201):

            distance_text = (
                f"{distance:.2f} cm"
                if distance is not None
                else "None cm"
            )

            print(
                f"{sensor_id:<12} | "
                f"Distance: {distance_text:>10} | "
                f"Status: {status:<8} | "
                f"Backend: OK"
            )

            return True

        print(
            f"{sensor_id:<12} | "
            f"Backend ERROR | "
            f"HTTP {response.status_code}"
        )

        return False

    except requests.RequestException as error:

        print(
            f"{sensor_id:<12} | "
            f"Backend connection error | "
            f"{error}"
        )

        return False


# ============================================================
# PRINT SENSOR CONFIGURATION
# ============================================================

def print_sensor_configuration():

    print("==============================================")
    print("       SMART CAR PARK SENSOR CONTROLLER")
    print("==============================================")

    print(f"Backend   : {BACKEND_URL}")

    print(
        f"Detection : <= {DETECTION_DISTANCE_CM} cm"
    )

    print(
        f"Sensor gap: {SENSOR_GAP * 1000:.0f} ms"
    )

    print(
        f"Cycle     : {CYCLE_INTERVAL:.1f} second"
    )

    print()

    print("Active Sensors:")
    print()

    for sensor_name, sensor in SENSORS.items():

        trig_pin = ULTRASONIC[sensor_name]["trig"]
        echo_pin = ULTRASONIC[sensor_name]["echo"]

        print(
            f"{sensor_name:<10} | "
            f"{sensor['id']:<12} | "
            f"{sensor['name']:<17} | "
            f"TRIG GPIO {trig_pin:<2} | "
            f"ECHO GPIO {echo_pin}"
        )

    print()

    print("All 6 ultrasonic sensors are ACTIVE.")
    print("Sensors will be triggered sequentially.")
    print("Waiting for sensor readings...")
    print()


# ============================================================
# MAIN CONTROLLER
# ============================================================

def run_ultrasonic_controller():

    print_sensor_configuration()

    while True:

        cycle_start = time.monotonic()

        # ====================================================
        # READ ALL SIX SENSORS SEQUENTIALLY
        # ====================================================

        for sensor_name, sensor in SENSORS.items():

            sensor_id = sensor["id"]

            # ------------------------------------------------
            # Read sensor
            # ------------------------------------------------

            distance = read_distance(sensor_name)

            # ------------------------------------------------
            # Determine status
            # ------------------------------------------------

            status = get_sensor_status(distance)

            # ------------------------------------------------
            # Send to backend
            # ------------------------------------------------

            send_sensor_data(
                sensor_id,
                distance,
                status
            )

            # ------------------------------------------------
            # Give ultrasonic waves time to settle
            # ------------------------------------------------

            time.sleep(SENSOR_GAP)

        # ====================================================
        # MAINTAIN APPROXIMATELY ONE-SECOND CYCLE
        # ====================================================

        elapsed = time.monotonic() - cycle_start

        remaining = CYCLE_INTERVAL - elapsed

        if remaining > 0:
            time.sleep(remaining)


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    try:

        run_ultrasonic_controller()

    except KeyboardInterrupt:

        print()
        print("==============================================")
        print("Ultrasonic controller stopped by user.")
        print("==============================================")

    except Exception as error:

        print()
        print(
            f"Controller error: {error}"
        )

    finally:

        GPIO.cleanup()

        print(
            "GPIO cleanup completed."
        )