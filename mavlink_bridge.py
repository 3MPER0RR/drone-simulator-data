#!/usr/bin/env python3
"""
MAVLink → WebSocket Bridge
Legge i dati MAVLink da ArduPilot SITL (UDP:14550)
e li trasmette via WebSocket al pannello drone-telemetry.html
"""

import asyncio
import json
import math
import time
import threading
import argparse
from pymavlink import mavutil
import websockets

# ─── CONFIGURAZIONE ───────────────────────────────────────────────
MAVLINK_HOST = "0.0.0.0"
MAVLINK_PORT = 14550          # Porta UDP default di ArduPilot SITL
WEBSOCKET_PORT = 8765         # Porta WebSocket per il pannello HTML
UPDATE_HZ = 20                # Frequenza di aggiornamento (Hz)
# ──────────────────────────────────────────────────────────────────

# Stato telemetria condiviso tra i thread
telemetry = {
    "lat": 0.0,
    "lon": 0.0,
    "alt": 0.0,
    "relative_alt": 0.0,
    "vx": 0.0,
    "vy": 0.0,
    "vz": 0.0,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "battery_pct": 0,
    "voltage": 0.0,
    "current": 0.0,
    "satellites": 0,
    "hdop": 0.0,
    "flight_mode": "UNKNOWN",
    "armed": False,
    "signal": 100,
    "timestamp": 0,
    "connected": False,
}

connected_clients = set()
telemetry_lock = threading.Lock()


# ─── MAVLINK READER (thread separato) ────────────────────────────
def mavlink_reader(connection_string):
    """
    Si connette al SITL e legge i messaggi MAVLink in modo continuo.
    connection_string esempi:
      - "udpin:0.0.0.0:14550"   → ricezione UDP (SITL default)
      - "tcp:127.0.0.1:5760"    → Mission Planner TCP
      - "/dev/ttyUSB0"          → drone reale via seriale
      - "udpout:192.168.1.x:14550" → drone reale via Wi-Fi
    """
    print(f"[BRIDGE] Connessione MAVLink: {connection_string}")
    mav = mavutil.mavlink_connection(connection_string, baud=57600)

    print("[BRIDGE] In attesa del heartbeat...")
    mav.wait_heartbeat()
    print(f"[BRIDGE] ✓ Heartbeat ricevuto — sistema {mav.target_system}, componente {mav.target_component}")

    # Richiede stream dati al veicolo
    mav.mav.request_data_stream_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, UPDATE_HZ, 1
    )

    with telemetry_lock:
        telemetry["connected"] = True

    while True:
        msg = mav.recv_match(blocking=True, timeout=2.0)
        if msg is None:
            with telemetry_lock:
                telemetry["connected"] = False
            print("[BRIDGE] ⚠ Timeout MAVLink — in attesa...")
            continue

        msg_type = msg.get_type()

        with telemetry_lock:
            telemetry["connected"] = True
            telemetry["timestamp"] = time.time()

            if msg_type == "GLOBAL_POSITION_INT":
                telemetry["lat"] = msg.lat / 1e7
                telemetry["lon"] = msg.lon / 1e7
                telemetry["alt"] = msg.alt / 1000.0          # mm → m
                telemetry["relative_alt"] = msg.relative_alt / 1000.0
                telemetry["vx"] = msg.vx / 100.0             # cm/s → m/s
                telemetry["vy"] = msg.vy / 100.0
                telemetry["vz"] = msg.vz / 100.0

            elif msg_type == "ATTITUDE":
                telemetry["roll"] = math.degrees(msg.roll)
                telemetry["pitch"] = math.degrees(msg.pitch)
                telemetry["yaw"] = math.degrees(msg.yaw) % 360

            elif msg_type == "SYS_STATUS":
                pct = msg.battery_remaining
                telemetry["battery_pct"] = pct if pct >= 0 else 0
                telemetry["voltage"] = msg.voltage_battery / 1000.0  # mV → V
                telemetry["current"] = msg.current_battery / 100.0   # cA → A

            elif msg_type == "GPS_RAW_INT":
                telemetry["satellites"] = msg.satellites_visible
                telemetry["hdop"] = msg.eph / 100.0 if msg.eph != 65535 else 99.9

            elif msg_type == "HEARTBEAT":
                mode_map = {
                    0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD",
                    3: "AUTO", 4: "GUIDED", 5: "LOITER",
                    6: "RTL", 7: "CIRCLE", 9: "LAND",
                    16: "POSHOLD", 17: "BRAKE",
                }
                telemetry["flight_mode"] = mode_map.get(msg.custom_mode, f"MODE_{msg.custom_mode}")
                telemetry["armed"] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

            elif msg_type == "RC_CHANNELS":
                # RSSI: 0-254 → 0-100%
                rssi = msg.rssi
                telemetry["signal"] = int((rssi / 254) * 100) if rssi != 255 else 100


# ─── WEBSOCKET SERVER ─────────────────────────────────────────────
async def ws_handler(websocket):
    """Gestisce ogni client WebSocket connesso al pannello HTML."""
    connected_clients.add(websocket)
    print(f"[WS] Client connesso — totale: {len(connected_clients)}")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Client disconnesso — totale: {len(connected_clients)}")


async def broadcast_loop():
    """Invia i dati telemetrici a tutti i client connessi ogni 1/UPDATE_HZ secondi."""
    interval = 1.0 / UPDATE_HZ
    while True:
        if connected_clients:
            with telemetry_lock:
                payload = json.dumps(telemetry)
            websockets.broadcast(connected_clients, payload)
        await asyncio.sleep(interval)


async def main_async(connection_string):
    print(f"[BRIDGE] WebSocket server su ws://localhost:{WEBSOCKET_PORT}")
    async with websockets.serve(ws_handler, "0.0.0.0", WEBSOCKET_PORT):
        await broadcast_loop()


# ─── ENTRY POINT ──────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MAVLink → WebSocket Bridge per drone-telemetry.html")
    parser.add_argument(
        "--connect", "-c",
        default="udpin:0.0.0.0:14550",
        help="Stringa di connessione MAVLink (default: udpin:0.0.0.0:14550)"
    )
    args = parser.parse_args()

    # Avvia il reader MAVLink in un thread separato
    t = threading.Thread(target=mavlink_reader, args=(args.connect,), daemon=True)
    t.start()

    # Avvia il server WebSocket nell'event loop principale
    try:
        asyncio.run(main_async(args.connect))
    except KeyboardInterrupt:
        print("\n[BRIDGE] Chiusura.")
