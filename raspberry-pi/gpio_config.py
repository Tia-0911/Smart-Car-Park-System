# gpio_config.py

# ==========================================
# RASPBERRY PI GPIO CONFIGURATION
# BCM NUMBERING
# ==========================================


# ==========================================
# ULTRASONIC SENSORS
# ==========================================
#
# sensor1 -> Parking Slot 1
# sensor2 -> Parking Slot 2
# sensor3 -> Parking Slot 3
# sensor4 -> Parking Slot 4
# sensor5 -> Entrance
# sensor6 -> Exit
#
# HC-SR04 ECHO MUST be reduced from 5V
# to 3.3V using a voltage divider/level shifter.
# ==========================================

ULTRASONIC = {

    # Parking Slot 1
    "sensor1": {
        "trig": 2,
        "echo": 3
    },

    # Parking Slot 2
    "sensor2": {
        "trig": 4,
        "echo": 5
    },

    # Parking Slot 3
    "sensor3": {
        "trig": 6,
        "echo": 7
    },

    # Parking Slot 4
    "sensor4": {
        "trig": 8,
        "echo": 9
    },

    # Entrance
    "sensor5": {
        "trig": 10,
        "echo": 11
    },

    # Exit
    "sensor6": {
        "trig": 12,
        "echo": 13
    },
}


# ==========================================
# PARKING LEDs
# ==========================================
#
# A01 -> Parking Slot A01
# A02 -> Parking Slot A02
# A03 -> Parking Slot A03
# A04 -> Parking Slot A04
# ==========================================

PARKING_LEDS = {

    "A01_LED": 14,

    "A02_LED": 15,

    "A03_LED": 16,

    "A04_LED": 17,
}


# ==========================================
# GATE LEDs
# ==========================================
#
# GATE1 -> ENTRANCE
# GATE2 -> EXIT
#
# GREEN = GATE OPEN
# RED   = GATE CLOSED
# ==========================================

GATE_LEDS = {

    # Entrance Gate
    "GATE1_GREEN": 18,
    "GATE1_RED": 19,

    # Exit Gate
    "GATE2_GREEN": 20,
    "GATE2_RED": 21,
}


# ==========================================
# ALL LEDs
# ==========================================

LEDS = {
    **PARKING_LEDS,
    **GATE_LEDS,
}


# ==========================================
# SERVOS
# ==========================================
#
# servo1 -> Entrance Gate
# servo2 -> Exit Gate
# ==========================================

SERVOS = {

    "servo1": 22,

    "servo2": 23,
}


# ==========================================
# TEMPERATURE / HUMIDITY SENSOR
# DHT22
# ==========================================

TEMP_HUMIDITY = {

    "pin": 24,
}


# ==========================================
# BUZZER
# ==========================================

BUZZER = {

    "pin": 25,
}


# ==========================================
# FIRE / FLAME SENSOR
# ==========================================
#
# Physical sensor:
# Digital flame sensor
#
# Database/API sensor ID:
# FIRE_01
#
# This name is only the GPIO configuration
# name. It does NOT need to be FIRE_01.
# ==========================================

FLAME_SENSOR = {

    "pin": 26,
}