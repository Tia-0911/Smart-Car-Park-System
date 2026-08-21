import time
import requests
import RPi.GPIO as GPIO


# ============================================================
# IMPORT LED FUNCTIONS
# ============================================================

from actuators.led import (
    setup_leds,
    led_on,
    led_off,
    all_leds_off,
)


# ============================================================
# BACKEND CONFIGURATION
# ============================================================

BACKEND_URL = "http://10.27.34.79:8080"

DEVICE_API_KEY = "smart-parking-pi-test-2026"

POLL_INTERVAL = 3

REQUEST_TIMEOUT = 7


# ============================================================
# BACKEND ENDPOINT
# ============================================================

LED_COMMANDS_URL = (
    f"{BACKEND_URL}/api/device/leds/commands/"
)


def claim_url(command_id):
    return (
        f"{BACKEND_URL}"
        f"/api/device/leds/commands/"
        f"{command_id}/claim/"
    )


def acknowledge_url(command_id):
    return (
        f"{BACKEND_URL}"
        f"/api/device/leds/commands/"
        f"{command_id}/acknowledge/"
    )


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "X-Device-API-Key": DEVICE_API_KEY,
    "Content-Type": "application/json",
}


# ============================================================
# CHECK BACKEND
# ============================================================

def check_backend():

    print()
    print("Testing backend connection...")
    print(LED_COMMANDS_URL)

    try:

        response = requests.get(
            LED_COMMANDS_URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        print(
            f"Backend HTTP status: "
            f"{response.status_code}"
        )

        print(
            f"Backend response: "
            f"{response.text}"
        )

        return response.status_code == 200

    except requests.RequestException as error:

        print(
            f"Backend connection FAILED: {error}"
        )

        return False


# ============================================================
# GET LED COMMANDS
# ============================================================

def get_led_commands():

    try:

        response = requests.get(
            LED_COMMANDS_URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:

            print(
                f"LED command request failed: "
                f"HTTP {response.status_code}"
            )

            print(response.text)

            return []

        data = response.json()

        return data.get(
            "commands",
            []
        )

    except requests.RequestException as error:

        print(
            f"Backend connection error: {error}"
        )

        return []

    except ValueError:

        print(
            "Backend returned invalid JSON."
        )

        return []


# ============================================================
# CLAIM LED COMMAND
# ============================================================

def claim_led_command(command_id):

    url = claim_url(command_id)

    try:

        response = requests.post(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        print(
            f"Claim command {command_id}: "
            f"HTTP {response.status_code}"
        )

        if response.status_code not in [200, 201]:

            print(response.text)

            return False

        return True

    except requests.RequestException as error:

        print(
            f"Claim error: {error}"
        )

        return False


# ============================================================
# ACKNOWLEDGE LED COMMAND
# ============================================================

def acknowledge_led_command(
    command_id,
    status,
    error_message=""
):

    url = acknowledge_url(command_id)

    payload = {
        "status": status
    }

    if error_message:

        payload["error"] = error_message

    try:

        response = requests.post(
            url,
            headers=HEADERS,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        print(
            f"Acknowledge command {command_id}: "
            f"HTTP {response.status_code}"
        )

        if response.status_code not in [200, 201]:

            print(response.text)

            return False

        return True

    except requests.RequestException as error:

        print(
            f"Acknowledgement error: {error}"
        )

        return False


# ============================================================
# PROCESS ONE LED COMMAND
# ============================================================

def process_led_command(command):

    command_id = command.get("id")

    slot_number = command.get("slot_number")

    led_name = command.get("led_name")

    action = command.get("action")

    print()
    print("----------------------------------------")

    print(
        f"Command ID : {command_id}"
    )

    print(
        f"Slot       : {slot_number}"
    )

    print(
        f"LED        : {led_name}"
    )

    print(
        f"Action     : {action}"
    )

    print("----------------------------------------")


    # ========================================================
    # VALIDATE COMMAND ID
    # ========================================================

    if command_id is None:

        print(
            "Invalid LED command: missing ID."
        )

        return


    # ========================================================
    # VALIDATE LED NAME
    # ========================================================

    if not led_name:

        error = (
            "Backend did not provide led_name."
        )

        print(error)

        acknowledge_led_command(
            command_id,
            "failed",
            error
        )

        return


    # ========================================================
    # VALIDATE ACTION
    # ========================================================

    if action not in ["on", "off"]:

        error = (
            f"Invalid LED action: {action}"
        )

        print(error)

        acknowledge_led_command(
            command_id,
            "failed",
            error
        )

        return


    # ========================================================
    # CLAIM COMMAND
    # ========================================================

    if not claim_led_command(command_id):

        print(
            f"Could not claim LED command "
            f"{command_id}."
        )

        return


    print(
        f"LED command {command_id} claimed."
    )


    # ========================================================
    # EXECUTE GPIO OPERATION
    # ========================================================

    success = False

    try:

        if action == "on":

            print(
                f"Turning ON LED: {led_name}"
            )

            success = led_on(
                led_name
            )

        elif action == "off":

            print(
                f"Turning OFF LED: {led_name}"
            )

            success = led_off(
                led_name
            )


    except Exception as error:

        print(
            f"GPIO error: {error}"
        )

        success = False

        acknowledge_led_command(
            command_id,
            "failed",
            str(error)
        )

        return


    # ========================================================
    # ACKNOWLEDGE RESULT
    # ========================================================

    if success:

        print(
            f"LED {led_name} "
            f"{action} SUCCESS."
        )

        acknowledged = acknowledge_led_command(
            command_id,
            "succeeded"
        )

        if not acknowledged:

            print(
                f"WARNING: LED operated successfully "
                f"but acknowledgement failed for "
                f"command {command_id}."
            )

    else:

        print(
            f"LED {led_name} "
            f"{action} FAILED."
        )

        acknowledge_led_command(
            command_id,
            "failed",
            "LED GPIO operation failed."
        )


# ============================================================
# MAIN CONTROLLER
# ============================================================

def run():

    print()
    print(
        "=============================================="
    )

    print(
        "       SMART CAR PARK LED CONTROLLER"
    )

    print(
        "=============================================="
    )

    print(
        f"Backend: {BACKEND_URL}"
    )

    print(
        "GPIO pins: loaded from gpio_config.py"
    )

    print(
        "Backend LED commands: ENABLED"
    )

    print(
        "=============================================="
    )


    # ========================================================
    # GPIO SETUP
    # ========================================================

    GPIO.setmode(
        GPIO.BCM
    )

    setup_leds()

    all_leds_off()


    # ========================================================
    # BACKEND CONNECTION
    # ========================================================

    if check_backend():

        print()
        print(
            "Backend connection: OK"
        )

    else:

        print()
        print(
            "Backend connection: FAILED"
        )

        print(
            "Check BACKEND_URL, Wi-Fi and backend server."
        )


    print()
    print(
        "Waiting for LED commands..."
    )

    print(
        "Press CTRL+C to stop."
    )

    print(
        "=============================================="
    )


    # ========================================================
    # CONTINUOUS LOOP
    # ========================================================

    try:

        while True:

            commands = get_led_commands()

            if commands:

                print()
                print(
                    f"Received "
                    f"{len(commands)} LED command(s)."
                )

                for command in commands:

                    process_led_command(
                        command
                    )

            time.sleep(
                POLL_INTERVAL
            )


    except KeyboardInterrupt:

        print()
        print(
            "LED controller stopped."
        )


    finally:

        print(
            "Turning all LEDs OFF..."
        )

        all_leds_off()

        GPIO.cleanup()

        print(
            "GPIO cleanup completed."
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    run()