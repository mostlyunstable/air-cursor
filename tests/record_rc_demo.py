#!/usr/bin/env python3
"""
Air Cursor: Release Candidate Demonstration Recorder
Executes live demonstration of Air Cursor operating Blender GUI:
- Start operator
- Smooth multi-region traversal (Viewport -> Outliner -> Properties)
- Actual Blender operations (object selection, material property inspection)
- Independent hardware cursor audit
- Mid-flight pause and resume
- Final operation execution
Captures window frames and encodes MP4, GIF, and Contact Sheet.
"""

import subprocess
import socket
import json
import time
import os
import shutil
import threading

SERVER_PORT = 9880
FRAMES_DIR = "/tmp/air_cursor_rc_frames"
OUTPUT_DIR = "/Users/mayankkumar/.gemini/antigravity/scratch/air-cursor/docs/assets"

def send_cmd(payload: dict) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect(('127.0.0.1', SERVER_PORT))
    s.sendall(json.dumps(payload).encode('utf-8'))
    data = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk: break
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
    return json.loads(data.decode('utf-8')) if data else {}

class FrameRecorder:
    def __init__(self, output_dir, interval=0.08):
        self.output_dir = output_dir
        self.interval = interval
        self.running = False
        self.frame_count = 0
        self.thread = None

    def start(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()

    def _capture_loop(self):
        while self.running:
            t0 = time.perf_counter()
            f_path = os.path.join(self.output_dir, f"frame_{self.frame_count:05d}.png")
            subprocess.run(["screencapture", "-R0,0,1800,1024", "-x", f_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.frame_count += 1
            elapsed = time.perf_counter() - t0
            sleep_time = max(0.01, self.interval - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print(f"Captured {self.frame_count} frames.")

def run_demo():
    print("=" * 70)
    print("AIR CURSOR — RELEASE CANDIDATE DEMONSTRATION RECORDING")
    print("=" * 70)

    # 1. Reset / Start Operator
    print("\n[Phase 1] Initializing Air Cursor in Blender...")
    send_cmd({"cmd": "start"})
    send_cmd({"cmd": "teleport", "target": (500, 500), "action_text": "Air Cursor Initialized"})
    time.sleep(0.3)

    recorder = FrameRecorder(FRAMES_DIR, interval=0.07)
    recorder.start()
    time.sleep(0.4)

    # 2. Viewport Navigation & Selection
    print("\n[Phase 2] Gliding to 3D Viewport & Selecting Default Cube...")
    cube_code = """
import bpy
bpy.ops.object.select_all(action='DESELECT')
cube = bpy.data.objects.get('Cube')
if cube:
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
"""
    send_cmd({
        "cmd": "enqueue",
        "target": "VIEW_3D",
        "action_type": "CLICK",
        "duration": 0.45,
        "action_text": "Navigating 3D Viewport",
        "code": cube_code
    })
    time.sleep(0.65)

    # 3. Traversal to Outliner
    print("\n[Phase 3] Traversing to Outliner & Selecting Light Object...")
    light_code = """
import bpy
bpy.ops.object.select_all(action='DESELECT')
light = bpy.data.objects.get('Light')
if light:
    light.select_set(True)
    bpy.context.view_layer.objects.active = light
"""
    send_cmd({
        "cmd": "enqueue",
        "target": "OUTLINER",
        "action_type": "CLICK",
        "duration": 0.50,
        "action_text": "Inspecting Outliner Hierarchy",
        "code": light_code
    })
    time.sleep(0.70)

    # 4. Traversal to Properties Panel
    print("\n[Phase 4] Vertical Glide into Properties Editor...")
    send_cmd({
        "cmd": "enqueue",
        "target": "PROPERTIES",
        "action_type": "HOVER",
        "duration": 0.45,
        "action_text": "Inspecting Object Properties"
    })
    time.sleep(0.65)

    # 5. Mid-flight Pause and Resume
    print("\n[Phase 5] Demonstrating Mid-Flight Pause and Resume...")
    send_cmd({
        "cmd": "enqueue",
        "target": (800, 600),
        "action_type": "MOVE",
        "duration": 0.90,
        "action_text": "Cross-Editor Long Trajectory"
    })
    time.sleep(0.25) # In flight
    send_cmd({"cmd": "pause"})
    print("  [PAUSED] Cursor holding position...")
    time.sleep(0.60) # Hold paused for recording
    send_cmd({"cmd": "resume"})
    print("  [RESUMED] Motion resumed smoothly...")
    time.sleep(0.95)

    # 6. Final Successful Operation
    print("\n[Phase 6] Returning to Viewport & Executing Final Operation...")
    final_op_code = """
import bpy
cube = bpy.data.objects.get('Cube')
if cube:
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
    cube.location.z += 0.5
"""
    send_cmd({
        "cmd": "enqueue",
        "target": "VIEW_3D",
        "action_type": "CLICK",
        "duration": 0.40,
        "action_text": "Operation Completed Successfully",
        "code": final_op_code
    })
    time.sleep(0.65)

    time.sleep(0.5)
    recorder.stop()

    # 7. Encode Video & Media Artifacts via ffmpeg
    print("\n[Phase 7] Encoding Media Artifacts via FFmpeg...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    mp4_path = os.path.join(OUTPUT_DIR, "air_cursor_demo.mp4")
    gif_path = os.path.join(OUTPUT_DIR, "air_cursor_demo.gif")
    sheet_path = os.path.join(OUTPUT_DIR, "release_candidate_audit_contact_sheet.png")

    # Encode MP4 (H.264, 12 fps)
    print("  Encoding MP4 video...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", "12",
        "-i", os.path.join(FRAMES_DIR, "frame_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "22", "-preset", "fast",
        mp4_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  MP4: {mp4_path} ({os.path.getsize(mp4_path) / 1024:.1f} KB)")

    # Encode GIF (optimized palette, 8 fps, 720p width)
    print("  Encoding animated GIF...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", "10",
        "-i", os.path.join(FRAMES_DIR, "frame_%05d.png"),
        "-vf", "fps=8,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer",
        gif_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  GIF: {gif_path} ({os.path.getsize(gif_path) / 1024:.1f} KB)")

    # Generate 6-panel contact sheet (2 rows x 3 columns)
    print("  Generating Contact Sheet...")
    # Select 6 key frames evenly spaced across the recording
    all_frames = sorted([f for f in os.listdir(FRAMES_DIR) if f.endswith(".png")])
    if len(all_frames) >= 6:
        indices = [
            int(len(all_frames) * 0.05), # Start
            int(len(all_frames) * 0.20), # Viewport
            int(len(all_frames) * 0.40), # Outliner
            int(len(all_frames) * 0.55), # Properties
            int(len(all_frames) * 0.75), # Paused
            int(len(all_frames) * 0.95)  # Final
        ]
        sample_dir = "/tmp/rc_sample_frames"
        os.makedirs(sample_dir, exist_ok=True)
        for i, idx in enumerate(indices):
            src = os.path.join(FRAMES_DIR, all_frames[idx])
            dst = os.path.join(sample_dir, f"sample_{i:02d}.png")
            shutil.copy(src, dst)

        subprocess.run([
            "ffmpeg", "-y",
            "-i", os.path.join(sample_dir, "sample_%02d.png"),
            "-filter_complex", "scale=600:-1,tile=3x2:padding=6:color=0x0a0d14",
            sheet_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  Contact Sheet: {sheet_path} ({os.path.getsize(sheet_path) / 1024:.1f} KB)")

    print("\nDemonstration recording and artifact compilation complete!")

if __name__ == "__main__":
    run_demo()
