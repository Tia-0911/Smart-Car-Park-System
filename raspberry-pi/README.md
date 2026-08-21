# Raspberry Pi Integration Manual

This guide explains how the Raspberry Pi hardware connects to the existing
Smart Car Park Django backend. You do not need to inspect or modify the Django
source code to follow this contract.

## Your responsibilities

The Raspberry Pi teammate is responsible for:

- reading the temperature, humidity, and fire sensors;
- reading parking sensors `PARK_A01` through `PARK_A06`;
- reading the entrance and exit vehicle sensors;
- controlling the entrance and exit gate servo/motor;
- sending sensor readings to Django;
- fetching authorized gate commands from Django;
- claiming each command before operating a servo;
- acknowledging physical success or failure after the operation.

You do **not** need to:

- create another Django project or an app such as `back1`;
- connect directly to the database;
- validate bookings or customer ownership;
- calculate payments, refunds, or overstay charges;
- decide whether a customer may open a gate.

Django is the source of truth for authorization and business rules. The Pi must
only execute commands created by Django.

## Architecture

Sensor reporting:

```text
Sensors
   ↓
Raspberry Pi
   ↓
Sensor API
   ↓
Django Backend
   ↓
Database / Dashboard
```

Gate control:

```text
Customer / Admin
   ↓
Django authorization
   ↓
GateCommand
   ↓
Raspberry Pi
   ↓
Servo / Motor
   ↓
Acknowledgement
   ↓
Django physical gate state
```

## Required configuration

Store configuration outside source control, preferably in environment
variables:

```text
SMART_PARK_BACKEND_URL=http://192.168.x.x:8000
SENSOR_DEVICE_API_KEY=YOUR_DEVICE_API_KEY
```

The backend owner must provide the real API key securely. Do not put it in Git,
screenshots, or shared logs.

Build request URLs by joining `SMART_PARK_BACKEND_URL` with the paths below.

## Device authentication

Every sensor and gate-device request requires:

```http
X-Device-API-Key: YOUR_DEVICE_API_KEY
```

Gate device endpoints do not require an admin login or CSRF token. A missing or
incorrect key returns HTTP 401.

## Sensor reporting API

```http
POST /api/device/sensors/update/
Content-Type: application/json
X-Device-API-Key: YOUR_DEVICE_API_KEY
```

Successful response:

```json
{
  "message": "Sensor updated",
  "sensor_id": "TEMPERATURE_01",
  "changed": true
}
```

The Pi sends `sensor_id` and `value`. Django determines the sensor type,
location, connection state, and receipt timestamp.

### Exact sensor IDs

| Hardware | `sensor_id` |
|---|---|
| Temperature | `TEMPERATURE_01` |
| Humidity | `HUMIDITY_01` |
| Fire | `FIRE_01` |
| Parking A01 | `PARK_A01` |
| Parking A02 | `PARK_A02` |
| Parking A03 | `PARK_A03` |
| Parking A04 | `PARK_A04` |
| Parking A05 | `PARK_A05` |
| Parking A06 | `PARK_A06` |
| Entrance | `ENTRANCE_01` |
| Exit | `EXIT_01` |

Use the canonical values below even though the backend accepts some aliases.

### Temperature

Send a numeric Celsius value without the unit:

```json
{
  "sensor_id": "TEMPERATURE_01",
  "value": 24.5
}
```

### Humidity

Send a numeric percentage without the `%` symbol:

```json
{
  "sensor_id": "HUMIDITY_01",
  "value": 58
}
```

### Fire

Normal:

```json
{
  "sensor_id": "FIRE_01",
  "value": "clear"
}
```

Fire detected:

```json
{
  "sensor_id": "FIRE_01",
  "value": "detected"
}
```

### Parking A01-A06

Available:

```json
{
  "sensor_id": "PARK_A01",
  "value": "clear"
}
```

Occupied:

```json
{
  "sensor_id": "PARK_A01",
  "value": "occupied"
}
```

Replace `PARK_A01` with the matching ID for each physical space.

### Entrance and exit

Entrance detected:

```json
{
  "sensor_id": "ENTRANCE_01",
  "value": "detected"
}
```

Entrance clear:

```json
{
  "sensor_id": "ENTRANCE_01",
  "value": "clear"
}
```

Exit detected:

```json
{
  "sensor_id": "EXIT_01",
  "value": "detected"
}
```

Exit clear:

```json
{
  "sensor_id": "EXIT_01",
  "value": "clear"
}
```

Detection reports that a vehicle is present. It does not authorize the gate to
open; Django handles authorization separately.

## Sensor reporting frequency

The backend considers a sensor offline after:

```text
SENSOR_OFFLINE_SECONDS = 600
```

Report comfortably before ten minutes:

| Sensor | Recommended reporting strategy |
|---|---|
| Temperature | Every 5 minutes |
| Humidity | Every 5 minutes |
| Fire | Every 5 minutes and immediately on change |
| PARK_A01-A06 | Immediately on change and a 5-minute heartbeat |
| Entrance | Immediately on change and a 5-minute heartbeat |
| Exit | Immediately on change and a 5-minute heartbeat |

Send the current value as the heartbeat even when it has not changed. Sensor
heartbeat scheduling should be independent from gate-command polling.

After a valid report, Django updates the current `SensorData`, appends a
`SensorReadingHistory` row, updates the related parking space when applicable,
creates a `SystemEvent` for state transitions, and refreshes dashboard data.
The Pi does not implement those operations.

## Physical gate command protocol

Canonical gates:

- `entrance` — Entrance gate servo/motor
- `exit` — Exit gate servo/motor

Canonical actions:

- `open` — physically open the gate
- `close` — physically close the gate

### Step 1: fetch pending commands

```http
GET /api/device/gates/commands/
X-Device-API-Key: YOUR_DEVICE_API_KEY
```

Actual response structure:

```json
{
  "commands": [
    {
      "id": 42,
      "gate_id": 1,
      "gate": "entrance",
      "action": "open",
      "status": "pending",
      "created_at": "2026-08-12T12:00:00Z",
      "expires_at": "2026-08-12T12:01:00Z"
    }
  ]
}
```

When nothing is pending:

```json
{
  "commands": []
}
```

### Step 2: claim before operating the servo

```http
POST /api/device/gates/commands/42/claim/
X-Device-API-Key: YOUR_DEVICE_API_KEY
```

Successful response:

```json
{
  "id": 42,
  "gate": "entrance",
  "action": "open",
  "status": "executing",
  "expires_at": "2026-08-12T12:01:00Z"
}
```

The Pi **must claim first**. Only operate the servo after a successful HTTP 200
claim. The lifecycle is:

```text
pending → claim → executing
```

A duplicate claim returns HTTP 409. Do not operate the servo after a 409.

### Step 3: operate the correct servo

After a successful claim:

| Command | Hardware operation |
|---|---|
| `gate=entrance`, `action=open` | Open Entrance servo |
| `gate=entrance`, `action=close` | Close Entrance servo |
| `gate=exit`, `action=open` | Open Exit servo |
| `gate=exit`, `action=close` | Close Exit servo |

GPIO pins, servo angles, motor timing, obstruction detection, and hardware
safety remain the Pi teammate's responsibility. They are intentionally not
prescribed by this backend contract.

### Step 4: acknowledge the physical result

```http
POST /api/device/gates/commands/42/acknowledge/
Content-Type: application/json
X-Device-API-Key: YOUR_DEVICE_API_KEY
```

Send success only after the physical movement succeeds:

```json
{
  "status": "succeeded"
}
```

Report a hardware failure:

```json
{
  "status": "failed",
  "error": "Servo timeout"
}
```

Successful acknowledgement response:

```json
{
  "id": 42,
  "gate": "entrance",
  "action": "open",
  "status": "succeeded",
  "physical_state": "open",
  "changed": true
}
```

Retrying the same final acknowledgement is safe and returns `changed: false`.
A conflicting final result returns HTTP 409.

Do not acknowledge `succeeded` immediately after receiving or claiming a
command. Wait until the servo/motor operation has actually succeeded.

## Logical state versus physical state

The backend maintains two separate concepts:

- `Gate.is_open`: what Django wants the gate to be;
- `Gate.is_physically_open`: what the Pi has confirmed actually happened.

For example:

```text
Customer presses Open Gate
→ Django authorizes the request
→ Django sets logical is_open = True
→ physical state remains False or unknown
→ Pi fetches, claims, and physically opens the servo
→ Pi acknowledges succeeded
→ Django sets is_physically_open = True
```

Failed acknowledgement does not falsely update physical state. The Pi never
needs direct database access.

## Command lifecycle and expiry

Possible command statuses:

| Status | Meaning |
|---|---|
| `pending` | Waiting for the Pi to claim |
| `executing` | Claimed; Pi may be operating hardware |
| `succeeded` | Pi confirmed physical success |
| `failed` | Pi reported physical failure |
| `expired` | No longer valid and must not execute |

Current expiry configuration:

```text
GATE_COMMAND_EXPIRY_SECONDS = 60
```

Never claim or execute a command after `expires_at`. Poll frequently enough to
receive valid commands; a one-second gate polling interval is reasonable on a
stable local network.

## Recommended Pi control loop

This is pseudocode, not production GPIO code:

```python
while running:
    read_sensors()
    send_due_heartbeats_and_state_changes()

    commands = fetch_gate_commands()
    for command in commands:
        if not claim(command["id"]):
            continue

        try:
            operate_correct_servo(command["gate"], command["action"])
        except HardwareError as error:
            acknowledge(command["id"], "failed", str(error))
        else:
            acknowledge(command["id"], "succeeded")

    sleep_briefly()
```

Use separate timers for five-minute sensor heartbeats and frequent gate polling.

## Network setup

Do not use:

```text
http://127.0.0.1:8000
```

unless Django is running on the Pi. On Raspberry Pi, `127.0.0.1` means the Pi
itself.

When Django runs on another laptop/computer, use that machine's LAN IP:

```text
SMART_PARK_BACKEND_URL=http://192.168.x.x:8000
```

The Pi and backend computer must be connected to networks that can reach each
other. Django must listen on an accessible interface, and its host/firewall
configuration must allow the connection.

For deployment, use the confirmed HTTPS Django backend URL. Do not use a
frontend Azure URL unless the backend owner confirms that it is the Django API
host.

## Error handling

| HTTP status | Meaning | Pi action |
|---:|---|---|
| 200 | Request succeeded | Continue normally |
| 400 | Invalid payload/value | Fix the request; do not retry forever |
| 401 | Missing/wrong device key | Stop and fix configuration |
| 404 | Command/resource not found | Discard that command ID |
| 409 | Already claimed, final, expired, or conflicting | Do not execute/retry blindly |
| 405 | Wrong HTTP method | Fix the request method |
| 5xx | Backend/server failure | Use bounded retry with backoff |

Network timeouts and 5xx responses may be retried with bounded exponential
backoff. Do not blindly retry 400, 401, or 409 responses.

## Security rules

- Never commit `SENSOR_DEVICE_API_KEY`.
- Never print the full key in logs or exception messages.
- Prefer environment variables or a protected device configuration file.
- Use HTTPS with the deployed backend.
- Do not connect the Pi directly to the Django database.
- Do not bypass Django booking or gate authorization.
- Do not execute unclaimed, expired, unknown, or already-final commands.

## Hardware integration checklist

Connectivity:

- [ ] Pi can reach the Django backend.
- [ ] Device API key is accepted.

Sensors:

- [ ] Temperature appears correctly.
- [ ] Humidity appears correctly.
- [ ] Fire `clear` appears correctly.
- [ ] Fire `detected` appears correctly.
- [ ] `PARK_A01` clear/occupied works.
- [ ] `PARK_A02` clear/occupied works.
- [ ] `PARK_A03` clear/occupied works.
- [ ] `PARK_A04` clear/occupied works.
- [ ] `PARK_A05` clear/occupied works.
- [ ] `PARK_A06` clear/occupied works.
- [ ] Entrance detected/clear works.
- [ ] Exit detected/clear works.

Gate hardware:

- [ ] Pi receives Entrance OPEN.
- [ ] Pi claims Entrance OPEN.
- [ ] Entrance servo opens.
- [ ] Pi acknowledges Entrance OPEN success.
- [ ] Pi receives and claims Entrance CLOSE.
- [ ] Entrance servo closes and acknowledgement succeeds.
- [ ] Pi receives and claims Exit OPEN.
- [ ] Exit servo opens and acknowledgement succeeds.
- [ ] Pi receives and claims Exit CLOSE.
- [ ] Exit servo closes and acknowledgement succeeds.
- [ ] Servo failure acknowledgement records the error.
- [ ] Duplicate claim does not operate the servo twice.
- [ ] Expired command is never executed.

Backend verification:

- [ ] Dashboard sensor values update.
- [ ] Sensor History receives new readings.
- [ ] Parking status changes with parking sensors.
- [ ] System Event Log shows sensor and gate hardware results.
- [ ] Physical gate state changes only after successful acknowledgement.
