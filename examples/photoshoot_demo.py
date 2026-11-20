#!/usr/bin/env python3
"""
Air Cursor: Automotive Photoshoot Demonstration Script
Executes multi-region select & inspect, studio lighting setup, and camera re-framing.
"""

import socket
import json
import time

BLENDER_PORT = 9876

def send_code(code_str, timeout=30.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(('127.0.0.1', BLENDER_PORT))
    payload = {"type": "execute_code", "params": {"code": code_str}}
    s.sendall(json.dumps(payload).encode('utf-8'))
    chunks = []
    while True:
        try:
            c = s.recv(4096)
            if not c: break
            chunks.append(c)
            try:
                parsed = json.loads(b''.join(chunks).decode('utf-8'))
                break
            except Exception:
                pass
        except Exception:
            break
    s.close()
    return json.loads(b''.join(chunks).decode('utf-8'))

def main():
    print("=" * 70)
    print("AIR CURSOR — AUTOMOTIVE PHOTOSHOOT DEMO")
    print("=" * 70)

    # 1. Start Operator
    print("\n[Phase 1] Initializing Air Cursor in Blender...")
    send_code("""
import air_cursor
air_cursor.register()
air_cursor.start_operator()
""")
    time.sleep(0.3)

    # 2. Select & Inspect Urus
    print("\n[Phase 2] Outliner -> Inspecting Urus Paint Material...")
    send_code("""
import air_cursor, bpy
# Travel to Outliner
air_cursor.move_cursor_to_win(3200, 1420, action_text="Outliner: Locating Lamborghini Urus", duration=0.45)
air_cursor.click_target_win(3200, 1420, action_text="Outliner: Selected Urus Shell")
obj = bpy.data.objects.get('BODY_MainShell_Continuous')
if obj:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

# Travel down to Properties Material Tab
air_cursor.move_cursor_to_win(2980, 480, action_text="Properties: Material Tab", duration=0.40)
air_cursor.click_target_win(2980, 480, action_text="Properties: Inspecting Giallo Auge")
air_cursor.move_cursor_to_win(3250, 420, action_text="Inspecting Giallo Auge Car Paint", hover=True, duration=0.25)
""")
    time.sleep(1.2)

    # 3. Select & Inspect M5
    print("\n[Phase 3] Outliner -> Inspecting BMW M5 Zed Black...")
    send_code("""
import air_cursor, bpy
air_cursor.move_cursor_to_win(3200, 1280, action_text="Outliner: Locating BMW M5 Competition", duration=0.45)
air_cursor.click_target_win(3200, 1280, action_text="Outliner: Selected BMW M5 Shell")
obj = bpy.data.objects.get('BODY_MainShell_Continuous.001')
if obj:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

air_cursor.move_cursor_to_win(3250, 460, action_text="Properties: Inspecting Zed Black Metallic", hover=True, duration=0.40)
""")
    time.sleep(1.2)

    # 4. Return to Viewport
    print("\n[Phase 4] Smooth return to 3D Viewport canvas...")
    send_code("""
import air_cursor, bpy
air_cursor.move_cursor_to_win(1450, 950, action_text="3D Viewport: Ready for Photoshoot", duration=0.48)
air_cursor.click_target_win(1450, 950, action_text="Deselected objects")
bpy.ops.object.select_all(action='DESELECT')
""")
    time.sleep(0.8)

    print("\nPhotoshoot demo sequence finished successfully!")

if __name__ == "__main__":
    main()
