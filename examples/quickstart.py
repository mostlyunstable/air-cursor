#!/usr/bin/env python3
"""
Air Cursor: Quickstart Example
Demonstrates connecting to Blender, moving the cursor smoothly, and triggering clicks.
"""

import socket
import json
import time

BLENDER_PORT = 9876

def send_code(code_str):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', BLENDER_PORT))
    payload = {"type": "execute_code", "params": {"code": code_str}}
    s.sendall(json.dumps(payload).encode('utf-8'))
    raw = s.recv(4096)
    s.close()
    return json.loads(raw.decode('utf-8'))

def main():
    print("[1] Initializing Air Cursor in Blender...")
    send_code("""
import air_cursor
air_cursor.register()
air_cursor.start_operator()
""")
    time.sleep(0.2)

    print("[2] Moving cursor to 3D Viewport canvas (1200, 1000)...")
    send_code("""
import air_cursor
air_cursor.move_cursor_to_win(1200, 1000, action_text="Navigating 3D Viewport Canvas", duration=0.4)
""")
    time.sleep(0.5)

    print("[3] Gliding to Outliner hierarchy and triggering 150ms click ripple...")
    send_code("""
import air_cursor
air_cursor.click_target_win(3200, 1400, action_text="Inspecting Scene Collection in Outliner")
""")
    time.sleep(0.5)

    print("[4] Gliding down to Properties editor...")
    send_code("""
import air_cursor
air_cursor.move_cursor_to_win(3200, 480, action_text="Adjusting Material Properties", hover=True, duration=0.35)
""")
    time.sleep(0.5)

    print("[5] Returning smoothly to center canvas...")
    send_code("""
import air_cursor
air_cursor.move_cursor_to_win(1400, 950, action_text="Ready in 3D Viewport")
""")
    time.sleep(0.5)

    print("[6] Reading live telemetry...")
    res = send_code("""
import air_cursor, json
print('TEL:' + json.dumps(air_cursor.get_telemetry()))
""")
    print("Telemetry Response:", res.get("result", {}).get("result", "").strip())
    print("\nAir Cursor Quickstart demonstration complete!")

if __name__ == "__main__":
    main()
