import time
import requests

from sensors.dht22 import read_sensor


# ============================================================
# BACKEND CONFIGURATION
# ============================================================

BACKEND_URL = "http://10.27.34.79:8080"

DEVICE_API_KEY = "smart-parking-pi-test-2026"

POLL_INTERVAL = 5


# ============================================================
# SENSOR CONFIGURATION
# ============================================================

SENSOR_UPDATE_ENDPOINT = (
    "/api/device/sensors/update/"
)


TEMPERATURE_SENSOR_ID = "TEMPERATURE_01"
HUMIDITY_SENSOR_ID = "HUMIDITY_01"

SENSOR_LOCATION = "Environment"


# ============================================================
# DEVICE AUTHENTICATION
# ============================================================

HEADERS = {
    "X-Device-API-Key": DEVICE_API_KEY,
    "Content-Type": "application/json"
}


# ============================================================
# READ DHT22
# ============================================================

def get_dht22_data():

    try:

        data = read_sensor()

        if data is None:

            print(
                "DHT22 reading failed."
            )

            return None

        temperature = data.get(
            "temperature"
        )

        humidity = data.get(
            "humidity"
        )

        if temperature is None:

            print(
                "Temperature reading is invalid."
            )

            return None

        if humidity is None:

            print(
                "Humidity reading is invalid."
            )

            return None

        return {
            "temperature": temperature,
            "humidity": humidity
        }

    except Exception as error:

        print(
            f"DHT22 sensor error: {error}"
        )

        return None


# ============================================================
# SEND ONE SENSOR READING
# ============================================================

def send_sensor_reading(
    sensor_id,
    sensor_type,
    value
):

    url = (
        f"{BACKEND_URL}"
        f"{SENSOR_UPDATE_ENDPOINT}"
    )

    payload = {

        "sensor_id": sensor_id,

        "sensor_type": sensor_type,

        "location": SENSOR_LOCATION,

        "value": str(value),

        "status": "active",

        "connection_status": "online",

        "condition_status": "normal"
    }

    try:

        response = requests.post(

            url,

            headers=HEADERS,

            json=payload,

            timeout=5
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code in (200, 201):

            print(
                f"{sensor_type} data sent successfully."
            )

            return True

        # ----------------------------------------------------
        # BACKEND ERROR
        # ----------------------------------------------------

        print(
            f"Failed to send {sensor_type} data."
        )

        print(
            f"HTTP {response.status_code}"
        )

        print(
            response.text
        )

        return False

    except requests.RequestException as error:

        print(
            f"Backend connection error: {error}"
        )

        return False


# ============================================================
# SEND DHT22 DATA
# ============================================================

def send_dht22_data(data):

    if data is None:

        return False

    temperature = data[
        "temperature"
    ]

    humidity = data[
        "humidity"
    ]

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print()
    print(
        "----------------------------------------"
    )

    print(
        f"Temperature : "
        f"{temperature:.1f} °C"
    )

    print(
        f"Humidity    : "
        f"{humidity:.1f} %"
    )

    print(
        "----------------------------------------"
    )

    # --------------------------------------------------------
    # SEND TEMPERATURE
    # --------------------------------------------------------

    temperature_success = send_sensor_reading(

        TEMPERATURE_SENSOR_ID,

        "temperature",

        temperature
    )

    # --------------------------------------------------------
    # SEND HUMIDITY
    # --------------------------------------------------------

    humidity_success = send_sensor_reading(

        HUMIDITY_SENSOR_ID,

        "humidity",

        humidity
    )

    return (
        temperature_success
        and humidity_success
    )


# ============================================================
# PROCESS SENSOR
# ============================================================

def process_dht22():

    data = get_dht22_data()

    if data is None:

        return False

    return send_dht22_data(
        data
    )


# ============================================================
# MAIN DHT22 CONTROLLER
# ============================================================

def run_dht22_controller():

    print()
    print(
        "========================================"
    )

    print(
        "       SMART PARKING DHT22 CONTROLLER"
    )

    print(
        "========================================"
    )

    print(
        f"Backend       : {BACKEND_URL}"
    )

    print(
        "Sensor        : DHT22"
    )

    print(
        f"Temperature ID: "
        f"{TEMPERATURE_SENSOR_ID}"
    )

    print(
        f"Humidity ID   : "
        f"{HUMIDITY_SENSOR_ID}"
    )

    print(
        f"Location      : {SENSOR_LOCATION}"
    )

    print(
        f"Poll interval : "
        f"{POLL_INTERVAL} seconds"
    )

    print(
        "Backend sync  : ENABLED"
    )

    print(
        "========================================"
    )

    print(
        "Waiting for DHT22 readings..."
    )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    while True:

        process_dht22()

        time.sleep(
            POLL_INTERVAL
        )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    try:

        run_dht22_controller()

    except KeyboardInterrupt:

        print()
        print(
            "DHT22 controller stopped by user."
        )

    except Exception as error:

        print()
        print(
            f"Controller error: {error}"
        )

    finally:

        print(
            "DHT22 controller stopped."
        )