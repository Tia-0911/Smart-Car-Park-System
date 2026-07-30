# Smart Car Park System

## Project Overview

Smart Car Park System is an IoT and Cloud-based project that aims to improve parking management by monitoring parking space availability in real time.

The system uses sensors connected with Raspberry Pi to detect whether parking spaces are occupied. The collected data is sent to a cloud-based backend system and displayed through a web dashboard.

## Objectives

- Monitor real-time parking slot availability
- Detect vehicle occupancy using sensors
- Store parking data in a cloud database
- Provide a dashboard for users to view parking status
- Support smart parking management

## System Components

## 1. IoT Layer (Raspberry Pi + Sensors)

Responsibilities:
- Detect vehicle presence in parking spaces
- Collect sensor data
- Send data to backend API

Technologies:
- Raspberry Pi
- Ultrasonic / IR Sensors

---

## 2. Backend System

Responsibilities:
- Receive sensor data
- Manage parking slot information
- Handle booking information
- Provide REST API services

Technologies:
- Python
- Django REST Framework
- Database

---

## 3. Frontend Dashboard

Responsibilities:
- Display available parking spaces
- Show real-time parking status
- Provide user interface

Technology:
- React

---

## 4. Cloud Infrastructure

Cloud services are used for:

- Hosting backend services
- Database storage
- Remote access
- System scalability

---

## System Architecture
