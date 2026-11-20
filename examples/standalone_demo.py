#!/usr/bin/env python3
"""
Air Cursor: Standalone Demonstration Script
Operates on standard Blender scene elements (Default Cube, Camera, Light)
using the dynamic target resolution and arrival-synchronized action pipeline.
"""

import socket
import json
import time

AIR_CURSOR_PORT = 9880
FALLBACK_PORT = 9876

def send_code(code_str, timeout=10.0):
    for port in (AIR_CURSOR_PORT, FALLBACK_PORT):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(('127.0.0.1', port))
            payload = {
                "cmd": "execute_code",
                "code": code_str,
                "type": "execute_code",
                "params": {"code": code_str}
            }
            s.sendall(json.dumps(payload).encode('utf-8'))
            chunks = []
            while True:
                c = s.recv(4096)
                if not c:
                    break
                chunks.append(c)
                try:
                    parsed = json.loads(b''.join(chunks).decode('utf-8'))
                    s.close()
                    return parsed
                except Exception:
                    pass
            s.close()
            if chunks:
                return json.loads(b''.join(chunks).decode('utf-8'))
        except Exception:
            continue
    raise ConnectionError("Could not connect to Blender on port 9880 or 9876")

def main():
    print("=" * 70)
    print("AIR CURSOR — STANDALONE BLENDER INTERACTION DEMO")
    print("=" * 70)

    print("\n[Phase 1] Starting Air Cursor...")
    send_code("""
import air_cursor
air_cursor.register()
air_cursor.start_operator()
""")
    time.sleep(0.2)

    print("\n[Phase 2] Gliding to 3D Viewport...")
    send_code("""
import air_cursor
x, y = air_cursor.resolve_target('VIEW_3D')
air_cursor.move_cursor_to_win(x, y, action_text="Inspecting 3D Viewport", duration=0.35)
""")
    time.sleep(0.4)

    print("\n[Phase 3] Navigating to Outliner to select active object...")
    send_code("""
import air_cursor, bpy
ox, oy = air_cursor.resolve_target('OUTLINER')
def select_cube():
    obj = bpy.data.objects.get('Cube') or (bpy.data.objects[0] if bpy.data.objects else None)
    if obj:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
air_cursor.click_target_win(ox, oy, action_text="Selecting Object in Outliner", callback=select_cube)
""")
    time.sleep(0.5)

    print("\n[Phase 4] Gliding to Properties Editor to inspect Material Properties...")
    send_code("""
import air_cursor
px, py = air_cursor.resolve_target('PROPERTIES')
air_cursor.move_cursor_to_win(px, py, action_text="Inspecting Properties Panel", hover=True, duration=0.35)
""")
    time.sleep(0.5)

    print("\n[Phase 5] Returning to 3D Viewport canvas...")
    send_code("""
import air_cursor
vx, vy = air_cursor.resolve_target('VIEW_3D')
air_cursor.move_cursor_to_win(vx, vy, action_text="Ready in 3D Viewport", duration=0.35)
""")
    time.sleep(0.5)

    print("\n[Phase 6] Telemetry Audit:")
    res = send_code("""
import air_cursor, json
print('TEL:' + json.dumps(air_cursor.get_telemetry()))
""")
    out = res.get("result", {}).get("result", "")
    for line in out.splitlines():
        if line.startswith("TEL:"):
            data = json.loads(line[4:])
            print(f"  Status:             {data.get('status')}")
            print(f"  Coordinates:        ({data.get('win_x')}, {data.get('win_y')})")
            print(f"  Completed Actions:  {data.get('completed_actions')}")
            print(f"  Avg Frame FPS:      {data.get('avg_fps')}")
            print(f"  Dispatch Latency:   {data.get('dispatch_latency_ms')} ms")

    print("\nStandalone demonstration finished successfully.")

if __name__ == "__main__":
    main()
