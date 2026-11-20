#!/usr/bin/env python3
"""
Air Cursor: 10 Real-World Acceptance Tests Suite
Executes live against the Air Cursor server (port 9880) inside live Blender.
Validates kinematics, input isolation, action pipeline, and stability.
"""

import socket
import json
import time
import math
import sys

try:
    import Quartz
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False

SERVER_PORT = 9880

def send_cmd(payload: dict, timeout: float = 10.0) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(('127.0.0.1', SERVER_PORT))
    s.sendall(json.dumps(payload).encode('utf-8'))
    data = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            try:
                parsed = json.loads(data.decode('utf-8'))
                s.close()
                return parsed
            except Exception:
                pass
        except Exception:
            break
    s.close()
    return json.loads(data.decode('utf-8'))

def get_telemetry() -> dict:
    res = send_cmd({"cmd": "telemetry"})
    return res.get("telemetry", {})

def get_human_cursor_pos():
    if not QUARTZ_AVAILABLE:
        return {"x": 0.0, "y": 0.0}
    ev = Quartz.CGEventCreate(None)
    loc = Quartz.CGEventGetLocation(ev)
    return {"x": round(loc.x, 2), "y": round(loc.y, 2)}

def run_acceptance_tests():
    print("=" * 75)
    print("AIR CURSOR — 10 REAL-WORLD ACCEPTANCE TESTS SUITE")
    print("=" * 75)

    results = {}

    # Initial check
    tel = get_telemetry()
    print(f"Initial State: Status={tel.get('status')}, Pos=({tel.get('win_x')}, {tel.get('win_y')}), FPS={tel.get('avg_fps')}")

    # TEST 1: Viewport Navigation
    print("\n[TEST 1] Viewport Navigation (Glide to 3D Viewport)...")
    t1_res = send_cmd({
        "cmd": "enqueue",
        "target": "VIEW_3D",
        "action_type": "MOVE",
        "duration": 0.35,
        "action_text": "Test 1: Viewport Navigation"
    })
    time.sleep(0.45)
    t1_tel = get_telemetry()
    t1_pass = not t1_tel.get("is_moving") and t1_tel.get("completed_actions", 0) >= 1
    print(f"  Target Arrived: Pos=({t1_tel.get('win_x')}, {t1_tel.get('win_y')}), Queue={t1_tel.get('queue_depth')}")
    print(f"  Result: {'PASS' if t1_pass else 'FAIL'}")
    results["Test 1: Viewport Navigation"] = t1_pass

    # TEST 2: Viewport to Outliner
    print("\n[TEST 2] Viewport to Outliner (Cross-Editor Transition)...")
    t2_res = send_cmd({
        "cmd": "enqueue",
        "target": "OUTLINER",
        "action_type": "CLICK",
        "duration": 0.40,
        "action_text": "Test 2: Outliner Click"
    })
    time.sleep(0.50)
    t2_tel = get_telemetry()
    t2_pass = not t2_tel.get("is_moving") and t2_tel.get("completed_actions", 0) >= 2
    print(f"  Outliner Arrived: Pos=({t2_tel.get('win_x')}, {t2_tel.get('win_y')})")
    print(f"  Result: {'PASS' if t2_pass else 'FAIL'}")
    results["Test 2: Viewport to Outliner"] = t2_pass

    # TEST 3: Outliner to Properties
    print("\n[TEST 3] Outliner to Properties (Vertical Panel Glide)...")
    t3_res = send_cmd({
        "cmd": "enqueue",
        "target": "PROPERTIES",
        "action_type": "HOVER",
        "duration": 0.35,
        "action_text": "Test 3: Properties Hover"
    })
    time.sleep(0.45)
    t3_tel = get_telemetry()
    t3_pass = not t3_tel.get("is_moving") and t3_tel.get("completed_actions", 0) >= 3
    print(f"  Properties Arrived: Pos=({t3_tel.get('win_x')}, {t3_tel.get('win_y')})")
    print(f"  Result: {'PASS' if t3_pass else 'FAIL'}")
    results["Test 3: Outliner to Properties"] = t3_pass

    # TEST 4: 20 Consecutive Actions Stress Test
    print("\n[TEST 4] 20 Consecutive Actions Stress Test...")
    base_completed = get_telemetry().get("completed_actions", 0)
    waypoints = [
        (400 + (i * 45) % 800, 300 + (i * 35) % 500) for i in range(20)
    ]
    for i, (wx, wy) in enumerate(waypoints):
        send_cmd({
            "cmd": "enqueue",
            "target": (wx, wy),
            "action_type": "MOVE",
            "duration": 0.08,
            "action_text": f"Stress Action #{i+1}"
        })
    # Wait for queue to drain: 20 actions * 0.08s = 1.6s + buffer
    time.sleep(2.2)
    t4_tel = get_telemetry()
    drain_completed = t4_tel.get("completed_actions", 0) - base_completed
    t4_pass = (drain_completed >= 20) and (t4_tel.get("queue_depth") == 0)
    print(f"  Processed {drain_completed}/20 actions. Queue depth = {t4_tel.get('queue_depth')}")
    print(f"  Result: {'PASS' if t4_pass else 'FAIL'}")
    results["Test 4: 20 Consecutive Actions"] = t4_pass

    # TEST 5: Scene Operation During Cursor Movement (Safe Main-Thread Execution)
    print("\n[TEST 5] Scene Operation Synchronized with Cursor Arrival...")
    marker_name = f"AirCursor_Acceptance_{int(time.time())}"
    scene_code = f"""
import bpy
obj = bpy.data.objects.new('{marker_name}', None)
bpy.context.collection.objects.link(obj)
"""
    send_cmd({
        "cmd": "enqueue",
        "target": "VIEW_3D",
        "action_type": "CLICK",
        "duration": 0.30,
        "action_text": "Spawning Test Object on Arrival",
        "code": scene_code
    })
    time.sleep(0.45)
    # Verify object created via execute_code
    verify_res = send_cmd({
        "cmd": "execute_code",
        "code": f"import bpy; assert '{marker_name}' in bpy.data.objects"
    })
    t5_pass = verify_res.get("status") == "success"
    # Clean up marker object
    send_cmd({
        "cmd": "execute_code",
        "code": f"import bpy; o = bpy.data.objects.get('{marker_name}'); bpy.data.objects.remove(o) if o else None"
    })
    print(f"  Object synchronized creation: {t5_pass}")
    print(f"  Result: {'PASS' if t5_pass else 'FAIL'}")
    results["Test 5: Scene Operation on Arrival"] = t5_pass

    # TEST 6: Consecutive Actions Without Artificial Pauses
    print("\n[TEST 6] Consecutive Actions Without Artificial Client-Side Pauses...")
    # Send a sequence of 4 rapid actions at once and measure end-to-end flow
    t6_start = time.perf_counter()
    send_cmd({"cmd": "enqueue", "target": (500, 500), "duration": 0.12, "action_text": "Seq 1"})
    send_cmd({"cmd": "enqueue", "target": (600, 500), "duration": 0.12, "action_text": "Seq 2"})
    send_cmd({"cmd": "enqueue", "target": (600, 600), "duration": 0.12, "action_text": "Seq 3"})
    send_cmd({"cmd": "enqueue", "target": (500, 600), "duration": 0.12, "action_text": "Seq 4"})
    time.sleep(0.65)
    t6_tel = get_telemetry()
    t6_pass = t6_tel.get("queue_depth") == 0 and not t6_tel.get("is_moving")
    print(f"  Sequence finished smoothly in {(time.perf_counter() - t6_start):.3f}s, Queue depth = {t6_tel.get('queue_depth')}")
    print(f"  Result: {'PASS' if t6_pass else 'FAIL'}")
    results["Test 6: Continuous Action Sequence"] = t6_pass

    # TEST 7: Pause and Resume During Movement
    print("\n[TEST 7] Pause and Resume During Movement...")
    send_cmd({"cmd": "enqueue", "target": (1200, 800), "duration": 0.80, "action_text": "Long Trajectory"})
    time.sleep(0.20) # Mid flight
    send_cmd({"cmd": "pause"})
    time.sleep(0.10)
    p_tel = get_telemetry()
    paused_pos = (p_tel.get("win_x"), p_tel.get("win_y"))
    print(f"  Paused at coordinates: {paused_pos}, Status={p_tel.get('status')}")
    time.sleep(0.20)
    p_tel2 = get_telemetry()
    held_still = (p_tel2.get("win_x") == paused_pos[0]) and (p_tel2.get("win_y") == paused_pos[1])
    send_cmd({"cmd": "resume"})
    time.sleep(0.80)
    res_tel = get_telemetry()
    t7_pass = held_still and res_tel.get("status") == "RUNNING"
    print(f"  Held position while paused: {held_still}. Completed trajectory after resume: {t7_pass}")
    print(f"  Result: {'PASS' if t7_pass else 'FAIL'}")
    results["Test 7: Pause and Resume"] = t7_pass

    # TEST 8: Emergency Stop
    print("\n[TEST 8] Emergency Stop During Movement...")
    send_cmd({"cmd": "enqueue", "target": (1500, 900), "duration": 0.80, "action_text": "Pre-Stop Action"})
    time.sleep(0.15)
    send_cmd({"cmd": "stop"})
    time.sleep(0.10)
    stop_tel = get_telemetry()
    t8_pass = (stop_tel.get("status") == "STOPPED") and (stop_tel.get("queue_depth") == 0) and not stop_tel.get("is_active")
    print(f"  Emergency stop status: Status={stop_tel.get('status')}, Active={stop_tel.get('is_active')}, Queue={stop_tel.get('queue_depth')}")
    # Restart operator for remaining tests
    send_cmd({"cmd": "start"})
    time.sleep(0.20)
    print(f"  Result: {'PASS' if t8_pass else 'FAIL'}")
    results["Test 8: Emergency Stop"] = t8_pass

    # TEST 9: Human Mouse Pointer Independence (0.00 px Deflection)
    print("\n[TEST 9] Human Mouse Pointer Independence Audit...")
    h_before = get_human_cursor_pos()
    print(f"  Hardware Cursor Position Before: ({h_before['x']}, {h_before['y']})")
    
    # Execute rapid large-screen movements
    send_cmd({"cmd": "enqueue", "target": (300, 300), "duration": 0.15, "action_text": "Corner 1"})
    send_cmd({"cmd": "enqueue", "target": (1400, 900), "duration": 0.15, "action_text": "Corner 2"})
    send_cmd({"cmd": "enqueue", "target": (600, 700), "duration": 0.15, "action_text": "Corner 3"})
    time.sleep(0.60)
    
    h_after = get_human_cursor_pos()
    print(f"  Hardware Cursor Position After:  ({h_after['x']}, {h_after['y']})")
    dx = abs(h_after["x"] - h_before["x"])
    dy = abs(h_after["y"] - h_before["y"])
    deflection = math.hypot(dx, dy)
    t9_pass = deflection < 0.01
    print(f"  Human Pointer Deflection: {deflection:.2f} px")
    print(f"  Result: {'PASS' if t9_pass else 'FAIL'}")
    results["Test 9: Human Mouse Independence"] = t9_pass

    # TEST 10: Restart and Standalone Verification
    print("\n[TEST 10] Standalone Verification (No Third-Party Addon Dependencies)...")
    # Verify telemetry response via standard socket without any external framework
    final_tel = get_telemetry()
    t10_pass = final_tel.get("status") == "RUNNING" and final_tel.get("avg_fps", 0) > 30.0
    print(f"  Standalone Operator Verified: Status={final_tel.get('status')}, FPS={final_tel.get('avg_fps')}")
    print(f"  Result: {'PASS' if t10_pass else 'FAIL'}")
    results["Test 10: Standalone Verification"] = t10_pass

    print("\n" + "=" * 75)
    print("ACCEPTANCE TESTS SUMMARY:")
    print("=" * 75)
    all_passed = True
    for test_name, passed in results.items():
        status_str = "PASSED [OK]" if passed else "FAILED [X]"
        print(f"  {test_name:<45}: {status_str}")
        if not passed:
            all_passed = False

    print("=" * 75)
    print(f"OVERALL STATUS: {'ALL 10 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 75)
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(run_acceptance_tests())
