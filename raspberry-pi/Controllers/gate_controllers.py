import time
import requests
import RPi.GPIO as GPIO

from actuators.servo import gate_up, gate_down
from gpio_config import GATE_LEDS


# ============================================================
# BACKEND CONFIGURATION
# ============================================================

BACKEND_URL = "http://10.27.34.79:8080"

DEVICE_API_KEY = "smart-parking-pi-test-2026"

POLL_INTERVAL = 3


# ============================================================
# SERVO / GATE CONFIGURATION
# ============================================================

ENTRY_GATE_SERVO = "servo1"
EXIT_GATE_SERVO = "servo2"


# ============================================================
# GATE LED CONFIGURATION
# ============================================================
#
# GPIO numbers are NOT written here.
# They come from gpio_config.py
#
# GATE1 = Entrance
# GATE2 = Exit
#
# GREEN = Gate open
# RED   = Gate closed
# ============================================================


# ============================================================
# DEVICE AUTHENTICATION
# ============================================================

HEADERS = {
    "X-Device-API-Key": DEVICE_API_KEY
}


# ============================================================
# GPIO SETUP
# ============================================================

def setup_gate_leds():

    GPIO.setmode(GPIO.BCM)

    for pin in GATE_LEDS.values():

        GPIO.setup(
            pin,
            GPIO.OUT,
            initial=GPIO.LOW
        )


# ============================================================
# GATE LED CONTROL
# ============================================================

def set_gate_led(gate_name, is_open):
    """
    Set the correct gate indicator.

    Entrance:
        GATE1_GREEN / GATE1_RED

    Exit:
        GATE2_GREEN / GATE2_RED

    Open:
        GREEN ON
        RED OFF

    Closed:
        GREEN OFF
        RED ON
    """

    # --------------------------------------------------------
    # ENTRANCE
    # --------------------------------------------------------

    if gate_name in ("entry", "entrance"):

        green_pin = GATE_LEDS["GATE1_GREEN"]
        red_pin = GATE_LEDS["GATE1_RED"]

    # --------------------------------------------------------
    # EXIT
    # --------------------------------------------------------

    elif gate_name == "exit":

        green_pin = GATE_LEDS["GATE2_GREEN"]
        red_pin = GATE_LEDS["GATE2_RED"]

    else:

        print(
            f"Unknown gate for LED control: "
            f"{gate_name}"
        )

        return False

    # --------------------------------------------------------
    # GATE OPEN
    # --------------------------------------------------------

    if is_open:

        GPIO.output(
            green_pin,
            GPIO.HIGH
        )

        GPIO.output(
            red_pin,
            GPIO.LOW
        )

        print(
            f"{gate_name}: GREEN LED ON, "
            f"RED LED OFF"
        )

    # --------------------------------------------------------
    # GATE CLOSED
    # --------------------------------------------------------

    else:

        GPIO.output(
            green_pin,
            GPIO.LOW
        )

        GPIO.output(
            red_pin,
            GPIO.HIGH
        )

        print(
            f"{gate_name}: GREEN LED OFF, "
            f"RED LED ON"
        )

    return True


# ============================================================
# INITIAL GATE LED STATE
# ============================================================

def set_all_gates_closed():

    print(
        "Setting all gate indicators to CLOSED..."
    )

    set_gate_led(
        "entrance",
        False
    )

    set_gate_led(
        "exit",
        False
    )


# ============================================================
# GET SERVO FOR GATE
# ============================================================

def get_servo_name(gate_name):
    """Return the servo associated with a gate."""

    if gate_name in ("entry", "entrance"):

        return ENTRY_GATE_SERVO

    if gate_name == "exit":

        return EXIT_GATE_SERVO

    return None


# ============================================================
# GET PENDING GATE COMMANDS
# ============================================================

def get_gate_commands():
    """Ask the backend for pending gate commands."""

    url = (
        f"{BACKEND_URL}"
        f"/api/device/gates/commands/"
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=5
        )

        if response.status_code != 200:

            print(
                f"Failed to get gate commands. "
                f"HTTP {response.status_code}"
            )

            return None

        data = response.json()

        return data.get(
            "commands",
            []
        )

    except requests.RequestException as error:

        print(
            f"Backend connection error: "
            f"{error}"
        )

        return None


# ============================================================
# CLAIM GATE COMMAND
# ============================================================

def claim_gate_command(command_id):
    """Claim a gate command from the backend."""

    url = (
        f"{BACKEND_URL}"
        f"/api/device/gates/commands/"
        f"{command_id}/claim/"
    )

    try:

        response = requests.post(
            url,
            headers=HEADERS,
            timeout=5
        )

        if response.status_code != 200:

            print(
                f"Could not claim command "
                f"{command_id}. "
                f"HTTP {response.status_code}"
            )

            print(
                response.text
            )

            return None

        return response.json()

    except requests.RequestException as error:

        print(
            f"Backend connection error: "
            f"{error}"
        )

        return None


# ============================================================
# ACKNOWLEDGE GATE COMMAND
# ============================================================

def acknowledge_gate_command(
    command_id,
    success,
    error_message=""
):
    """
    Tell the backend whether the gate operation
    succeeded or failed.
    """

    url = (
        f"{BACKEND_URL}"
        f"/api/device/gates/commands/"
        f"{command_id}/acknowledge/"
    )

    status_value = (
        "succeeded"
        if success
        else
        "failed"
    )

    payload = {
        "status": status_value
    }

    if error_message:

        payload["error"] = error_message

    try:

        response = requests.post(
            url,
            headers=HEADERS,
            json=payload,
            timeout=5
        )

        if response.status_code != 200:

            print(
                f"Could not acknowledge command "
                f"{command_id}. "
                f"HTTP {response.status_code}"
            )

            print(
                response.text
            )

            return False

        print(
            f"Command {command_id} "
            f"acknowledged successfully."
        )

        return True

    except requests.RequestException as error:

        print(
            f"Backend connection error: "
            f"{error}"
        )

        return False


# ============================================================
# EXECUTE GATE COMMAND
# ============================================================

def execute_gate_command(command):

    command_id = command.get(
        "id"
    )

    action = command.get(
        "action"
    )

    gate_name = command.get(
        "gate"
    )

    slot_number = command.get(
        "slot_number"
    )

    # --------------------------------------------------------
    # DISPLAY COMMAND
    # --------------------------------------------------------

    print()
    print(
        "----------------------------------------"
    )

    print(
        f"Command ID : {command_id}"
    )

    print(
        f"Gate       : {gate_name}"
    )

    print(
        f"Action     : {action}"
    )

    print(
        f"Slot       : {slot_number}"
    )

    # --------------------------------------------------------
    # FIND SERVO
    # --------------------------------------------------------

    servo_name = get_servo_name(
        gate_name
    )

    if servo_name is None:

        error = (
            f"Unknown gate: {gate_name}"
        )

        print(error)

        acknowledge_gate_command(
            command_id,
            False,
            error
        )

        return False

    print(
        f"Using servo: {servo_name}"
    )

    # ========================================================
    # OPEN GATE
    # ========================================================

    if action == "open":

        print(
            f"Opening {gate_name} gate..."
        )

        try:

            result = gate_up(
                servo_name
            )

        except Exception as error:

            print(
                f"Servo error: {error}"
            )

            # Keep gate indicator RED
            set_gate_led(
                gate_name,
                False
            )

            acknowledge_gate_command(
                command_id,
                False,
                str(error)
            )

            return False

        # ----------------------------------------------------
        # SERVO SUCCESS
        # ----------------------------------------------------

        if result:

            print(
                f"{gate_name} gate "
                f"open successful."
            )

            # ------------------------------------------------
            # GREEN ON / RED OFF
            # ------------------------------------------------

            set_gate_led(
                gate_name,
                True
            )

        else:

            print(
                f"{gate_name} gate "
                f"failed to open."
            )

            # Keep RED ON
            set_gate_led(
                gate_name,
                False
            )

            acknowledge_gate_command(
                command_id,
                False,
                "Servo failed to open gate."
            )

            return False

    # ========================================================
    # CLOSE GATE
    # ========================================================

    elif action == "close":

        print(
            f"Closing {gate_name} gate..."
        )

        try:

            result = gate_down(
                servo_name
            )

        except Exception as error:

            print(
                f"Servo error: {error}"
            )

            # Keep RED ON
            set_gate_led(
                gate_name,
                False
            )

            acknowledge_gate_command(
                command_id,
                False,
                str(error)
            )

            return False

        # ----------------------------------------------------
        # SERVO SUCCESS
        # ----------------------------------------------------

        if result:

            print(
                f"{gate_name} gate "
                f"close successful."
            )

            # ------------------------------------------------
            # RED ON / GREEN OFF
            # ------------------------------------------------

            set_gate_led(
                gate_name,
                False
            )

        else:

            print(
                f"{gate_name} gate "
                f"failed to close."
            )

            # Gate state is uncertain.
            # Keep indicator RED for safety.
            set_gate_led(
                gate_name,
                False
            )

            acknowledge_gate_command(
                command_id,
                False,
                "Servo failed to close gate."
            )

            return False

    # ========================================================
    # UNKNOWN ACTION
    # ========================================================

    else:

        error = (
            f"Unknown gate action: "
            f"{action}"
        )

        print(error)

        acknowledge_gate_command(
            command_id,
            False,
            error
        )

        return False

    # ========================================================
    # DISPLAY SLOT INFORMATION
    # ========================================================

    if slot_number:

        print(
            f"Assigned parking slot: "
            f"{slot_number}"
        )

    else:

        print(
            "No parking slot assigned "
            "to this command."
        )

    # ========================================================
    # ACKNOWLEDGE SUCCESS
    # ========================================================

    acknowledge_gate_command(
        command_id,
        True
    )

    return True


# ============================================================
# PROCESS ONE COMMAND
# ============================================================

def process_gate_command(command):

    command_id = command.get(
        "id"
    )

    if command_id is None:

        print(
            "Invalid command: missing ID"
        )

        return

    print()
    print(
        f"Found pending command: "
        f"{command_id}"
    )

    # --------------------------------------------------------
    # CLAIM
    # --------------------------------------------------------

    claimed_command = claim_gate_command(
        command_id
    )

    if claimed_command is None:

        print(
            f"Could not claim command "
            f"{command_id}"
        )

        return

    print(
        f"Command {command_id} claimed."
    )

    # --------------------------------------------------------
    # EXECUTE
    # --------------------------------------------------------

    execute_gate_command(
        claimed_command
    )


# ============================================================
# MAIN GATE CONTROLLER
# ============================================================

def run_gate_controller():

    print()
    print(
        "========================================"
    )

    print(
        "       SMART PARKING GATE CONTROLLER"
    )

    print(
        "========================================"
    )

    print(
        f"Entry Gate : {ENTRY_GATE_SERVO}"
    )

    print(
        f"Exit Gate  : {EXIT_GATE_SERVO}"
    )

    print(
        f"Backend    : {BACKEND_URL}"
    )

    print(
        "Gate LED control: ENABLED"
    )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # GPIO SETUP
    # --------------------------------------------------------

    setup_gate_leds()

    # --------------------------------------------------------
    # INITIAL STATE
    # --------------------------------------------------------
    #
    # Both gates start as CLOSED.
    #
    # Entrance:
    #   RED ON
    #
    # Exit:
    #   RED ON
    # --------------------------------------------------------

    set_all_gates_closed()

    print(
        "Gate indicators initialized."
    )

    print(
        "Waiting for backend commands..."
    )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    while True:

        commands = get_gate_commands()

        # ----------------------------------------------------
        # BACKEND UNAVAILABLE
        # ----------------------------------------------------

        if commands is None:

            time.sleep(
                POLL_INTERVAL
            )

            continue

        # ----------------------------------------------------
        # NO COMMANDS
        # ----------------------------------------------------

        if not commands:

            time.sleep(
                POLL_INTERVAL
            )

            continue

        # ----------------------------------------------------
        # PROCESS COMMANDS
        # ----------------------------------------------------

        for command in commands:

            process_gate_command(
                command
            )

        time.sleep(
            POLL_INTERVAL
        )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    try:

        run_gate_controller()

    except KeyboardInterrupt:

        print()
        print(
            "Gate controller stopped by user."
        )

    except Exception as error:

        print()
        print(
            f"Controller error: {error}"
        )

    finally:

        # ----------------------------------------------------
        # TURN ALL GATE LEDs OFF
        # ----------------------------------------------------

        try:

            for pin in GATE_LEDS.values():

                GPIO.output(
                    pin,
                    GPIO.LOW
                )

        except Exception:

            pass

        GPIO.cleanup()

        print(
            "GPIO cleanup completed."
        )