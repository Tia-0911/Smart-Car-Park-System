# System Architecture

## Overview

The Smart Car Park System consists of four main layers:

1. IoT Layer
2. Cloud Backend Layer
3. Database Layer
4. User Interface Layer


## Architecture Flow


                 Vehicle
                    |
                    ↓
          Parking Detection Sensor
                    |
                    ↓
              Raspberry Pi
                    |
                    ↓
             REST API Request
                    |
                    ↓
        Django Backend (Cloud)
                    |
                    ↓
          Cloud Database
                    |
                    ↓
          React Web Dashboard



## Components Description


### IoT Layer

Components:
- Raspberry Pi
- Ultrasonic Sensor / IR Sensor

Function:
- Detect whether a parking slot is occupied
- Send parking status data to backend


### Backend Layer

Technology:
- Django REST Framework

Function:
- Receive sensor data
- Process parking information
- Provide API services


### Database Layer

Function:
- Store:
  - Parking slot information
  - Sensor status
  - Booking information


### Frontend Layer

Technology:
- React

Function:
- Display:
  - Available parking spaces
  - Occupied spaces
  - Parking status