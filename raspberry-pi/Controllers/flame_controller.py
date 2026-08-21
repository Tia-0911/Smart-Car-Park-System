import time
import requests
import RPi.GPIO as GPIO

from gpio_config import FLAME_SENSOR, BUZZER


# ============================================================
# BACKEND CONFIGURATION
# ============================================================

BACKEND_URL = "http://10.27.34.79:8080"

DEVICE_API_KEY = "smart-parking-pi-test-2026"

SENSOR_UPDATE_URL = (
    f"{BACKEND_URL}/api/device/sensors/update/"
)

POLL_INTERVAL = 2

REQUEST_TIMEOUT = 5


# ============================================================
# SENSOR CONFIGURATION
# ============================================================

# GPIO pins come from gpio_config.py

FLAME_SENSOR_PIN = FLAME_SENSOR["pin"]

BUZZER_PIN = BUZZER["pin"]

SENSOR_ID = "FIRE_01"

SENSOR_TYPE = "fire"

SENSOR_LOCATION = "Parking Area"


# ============================================================
# DEVICE AUTHENTICATION
# ============================================================

HEADERS = {
    "X-Device-API-Key": DEVICE_API_KEY,
    "Content-Type": "application/json",
}


# ============================================================
# GPIO SETUP
# ============================================================

def setup_gpio():

    GPIO.setmode(GPIO.BCM)

    GPIO.setup(
        FLAME_SENSOR_PIN,
        GPIO.IN
    )

    GPIO.setup(
        BUZZER_PIN,
        GPIO.OUT,
        initial=GPIO.LOW
    )


# ============================================================
# FLAME SENSOR
# ============================================================

def flame_detected():

    value = GPIO.input(
        FLAME_SENSOR_PIN
    )

    # Most digital flame sensor modules:
    #
    # LOW  = flame detected
    # HIGH = no flame
    #

    return value == GPIO.LOW


# ============================================================
# BUZZER
# ============================================================

def buzzer_on():

    GPIO.output(
        BUZZER_PIN,
        GPIO.HIGH
    )


def buzzer_off():

    GPIO.output(
        BUZZER_PIN,
        GPIO.LOW
    )


# ============================================================
# SEND SENSOR DATA TO BACKEND
# ============================================================

def send_sensor_data(detected):

    if detected:

        value = "detected"

        condition_status = "abnormal"

    else:

        value = "clear"

        condition_status = "normal"


    payload = {

        "sensor_id":
        SENSOR_ID,

        "sensor_type":
        SENSOR_TYPE,

        "location":
        SENSOR_LOCATION,

        "value":
        value,

        "status":
        "active",

        "connection_status":
        "online",

        "condition_status":
        condition_status,

    }


    print()
    print(
        "Sending sensor data:"
    )

    print(
        payload
    )


    try:

        response = requests.post(

            SENSOR_UPDATE_URL,

            headers=HEADERS,

            json=payload,

            timeout=REQUEST_TIMEOUT

        )


        if response.status_code in (
            200,
            201
        ):

            print(
                "Sensor data sent successfully."
            )

            print(
                response.json()
            )

            return True


        print(
            f"Backend rejected data: "
            f"HTTP {response.status_code}"
        )

        print(
            response.text
        )

        return False


    except requests.RequestException as error:

        print(
            f"Backend connection error: "
            f"{error}"
        )

        return False


# ============================================================
# MAIN CONTROLLER
# ============================================================

def run():

    print()
    print(
        "========================================"
    )

    print(
        "       SMART PARKING FLAME CONTROLLER"
    )

    print(
        "========================================"
    )

    print(
        f"Backend       : {BACKEND_URL}"
    )

    print(
        f"Flame Sensor  : GPIO {FLAME_SENSOR_PIN}"
    )

    print(
        f"Buzzer        : GPIO {BUZZER_PIN}"
    )

    print(
        f"Sensor ID     : {SENSOR_ID}"
    )

    print(
        f"Sensor Type   : {SENSOR_TYPE}"
    )

    print(
        "========================================"
    )


    setup_gpio()

    previous_state = None


    try:

        while True:

            detected = flame_detected()


            # =================================================
            # FLAME DETECTED
            # =================================================

            if detected:

                print(
                    "🔥 FLAME DETECTED!"
                )

                buzzer_on()


            # =================================================
            # NO FLAME
            # =================================================

            else:

                print(
                    "No flame detected."
                )

                buzzer_off()


            # =================================================
            # SEND ONLY WHEN STATE CHANGES
            # =================================================

            if detected != previous_state:

                print(
                    "Flame state changed."
                )

                send_sensor_data(
                    detected
                )

                previous_state = detected


            time.sleep(
                POLL_INTERVAL
            )


    except KeyboardInterrupt:

        print()
        print(
            "Flame controller stopped."
        )


    finally:

        buzzer_off()

        GPIO.cleanup()

        print(
            "GPIO cleanup completed."
        )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    run()