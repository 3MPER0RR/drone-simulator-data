The system consists of three components working together:

```
ArduPilot SITL (simulator)
        ↓  UDP :14550
  mavlink_bridge.py
        ↓  WebSocket :8765
  drone-telemetry-v2.html  ←  open in browser
```

---

## Installing the Python Bridge

### Requirements

- Python 3.8 or higher
- pip

### Install dependencies

Open a terminal (PowerShell on Windows, Terminal on Mac/Linux) and run:

```bash
pip install pymavlink websockets
```

### Verify the installation

```bash
python -c "import pymavlink, websockets; print('OK')"
```

If you see `OK`, the installation was successful.

---

## Installing ArduPilot SITL

### Windows

**Install WSL2** (Windows Subsystem for Linux), then open Ubuntu from WSL and type:

```bash
sudo apt update && sudo apt install git python3-pip -y
git clone https://github.com/ArduPilot/ardupilot.git
cd ardupilot
git submodule update --init --recursive
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

To launch the ArduCopter simulator:

```bash
cd ardupilot
sim_vehicle.py -v ArduCopter --console --map
```

SITL will start sending MAVLink data on UDP port 14550 of your machine.

### Mac

```bash
brew install python3
pip3 install --user pymavlink MAVProxy
git clone https://github.com/ArduPilot/ardupilot.git
cd ardupilot && git submodule update --init --recursive
sim_vehicle.py -v ArduCopter --console --map
```

### Linux (Ubuntu/Debian)

Same procedure as WSL above, no need for WSL.

### QGroundControl (easiest, no terminal required)

1. Download QGroundControl from https://qgroundcontrol.com
2. Open it → go to **Vehicle Setup → Firmware**
3. Select **"ArduPilot Flight Stack"** → check **"Standard Version (stable)"**
4. QGroundControl has a built-in SITL: **Simulate → Start Simulation**
5. MAVLink data is automatically broadcast on port 14550

---

## Starting the Bridge

Once SITL is running, open a **second terminal** and start the bridge:

```bash
python mavlink_bridge.py
```

You should see:

```
[BRIDGE] MAVLink connection: udpin:0.0.0.0:14550
[BRIDGE] Waiting for heartbeat...
[BRIDGE] ✓ Heartbeat received — system 1, component 1
[BRIDGE] WebSocket server on ws://localhost:8765
```

The bridge is now active and listening.

### Advanced bridge options

```bash
# Local SITL (default)
python mavlink_bridge.py --connect udpin:0.0.0.0:14550

# Real drone via Wi-Fi (e.g. Tello or Pixhawk-based drone)
python mavlink_bridge.py --connect udpout:192.168.1.100:14550

# Mission Planner via TCP
python mavlink_bridge.py --connect tcp:127.0.0.1:5760

# Real drone via serial port (USB)
python mavlink_bridge.py --connect /dev/ttyUSB0
```

---

## Opening the Dashboard in the Browser

1. Open `drone-telemetry-v2.html` in Chrome, Edge, or Firefox
2. In the top-right corner, click the **REAL** button
3. A dialog will appear — leave the address as `ws://localhost:8765` and click **CONNECT**
4. The indicator dot will turn green and you will see live data from the simulator

If you only want to use the built-in simulator without the bridge, leave **SIM** selected: data is generated directly in the browser with no additional setup required.

---

## Connecting a Real Drone

### DJI Tello

The Tello uses its own UDP protocol, not MAVLink. A dedicated bridge is needed:

```bash
pip install djitellopy websockets
python tello_bridge.py   # (to be created separately)
```

The Tello bridge connects to the drone via Wi-Fi (IP: 192.168.10.1, port 8889) and re-transmits telemetry data via WebSocket on port 8765 — exactly like the MAVLink bridge.

In the dashboard, click **REAL** and use the **Tello** preset (`ws://192.168.10.1:8765`), or point it to the IP of the PC running the bridge.

### Pixhawk / Real ArduPilot Drone

Connect the Pixhawk via USB or radio telemetry, then start the bridge specifying the port:

```bash
# USB
python mavlink_bridge.py --connect /dev/ttyUSB0

# Radio telemetry (e.g. SiK radio)
python mavlink_bridge.py --connect /dev/ttyUSB0

# Wi-Fi (e.g. with ESP8266/ESP32 module)
python mavlink_bridge.py --connect udpin:0.0.0.0:14550
```

---

## Troubleshooting

**The bridge does not receive the heartbeat**
Make sure SITL is running and that no firewall is blocking UDP port 14550. On Windows you may need to add an exception in Windows Defender Firewall.

**The browser cannot connect to the WebSocket**
Make sure the bridge is running (check the terminal). If the browser shows a `mixed content` error, open the HTML file as a local `file://` path rather than from an HTTPS server.

**Data arrives but all values are zero**
SITL takes a few seconds to arm and simulate GPS. Wait 10–15 seconds after launch before expecting meaningful data.

**Error "No module named pymavlink"**
Run `pip install pymavlink websockets` and try again. On some systems you may need to use `pip3` instead of `pip`.
