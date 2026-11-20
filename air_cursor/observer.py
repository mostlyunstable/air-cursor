import http.server
import socketserver
import threading
import json
import time
import socket
import os
import io
from urllib.parse import urlparse
from PIL import Image

try:
    import Quartz
    from Cocoa import NSURL
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False

DEFAULT_PORT = 8088
DEFAULT_AIR_CURSOR_PORT = 9880
DEFAULT_FALLBACK_PORT = 9876

def send_blender_cmd(payload, port=DEFAULT_AIR_CURSOR_PORT):
    for p in (port, DEFAULT_FALLBACK_PORT):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect(('127.0.0.1', p))
            s.sendall(json.dumps(payload).encode('utf-8'))
            raw = s.recv(8192)
            s.close()
            return json.loads(raw.decode('utf-8'))
        except Exception:
            continue
    return {"status": "error", "message": "Failed to connect to Blender"}

def send_blender_code(code_str, port=DEFAULT_AIR_CURSOR_PORT):
    return send_blender_cmd({
        "cmd": "execute_code",
        "code": code_str,
        "type": "execute_code",
        "params": {"code": code_str}
    }, port=port)

def get_human_cursor_pos():
    if not QUARTZ_AVAILABLE:
        return {"x": 0.0, "y": 0.0, "note": "Quartz unavailable"}
    try:
        ev = Quartz.CGEventCreate(None)
        loc = Quartz.CGEventGetLocation(ev)
        return {"x": round(loc.x, 1), "y": round(loc.y, 1)}
    except Exception as e:
        return {"x": 0.0, "y": 0.0, "error": str(e)}

def get_blender_telemetry(port=DEFAULT_AIR_CURSOR_PORT):
    res = send_blender_cmd({"cmd": "telemetry"}, port=port)
    if res.get("status") == "ok" and "telemetry" in res:
        return res["telemetry"]
    code = """
import air_cursor
import json
print('TELEMETRY_JSON:' + json.dumps(air_cursor.get_telemetry()))
"""
    res = send_blender_code(code, port=port)
    try:
        out = res.get("result", {}).get("result", "")
        for line in out.splitlines():
            if line.startswith("TELEMETRY_JSON:"):
                return json.loads(line[len("TELEMETRY_JSON:"):])
    except Exception:
        pass
    return {
        "status": "UNKNOWN",
        "ai_x": 0.0,
        "ai_y": 0.0,
        "target_x": 0.0,
        "target_y": 0.0,
        "action": "Connecting to Blender...",
        "is_active": False
    }

def capture_blender_jpeg(port=DEFAULT_AIR_CURSOR_PORT):
    dest_path = "/tmp/air_cursor_observer_snap.png"
    code = f"""
import bpy
window = bpy.context.window_manager.windows[0]
with bpy.context.temp_override(window=window):
    bpy.ops.screen.screenshot(filepath='{dest_path}')
"""
    send_blender_code(code, port=port)
    try:
        if os.path.exists(dest_path):
            pil_img = Image.open(dest_path)
            pil_img.thumbnail((1440, 900), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            pil_img.save(buf, format='JPEG', quality=80)
            return buf.getvalue()
    except Exception as e:
        print(f"Capture error: {e}")
    return None
"""
    send_blender_code(code, port=port)
    try:
        if os.path.exists(dest_path):
            pil_img = Image.open(dest_path)
            pil_img.thumbnail((1440, 900), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            pil_img.save(buf, format='JPEG', quality=80)
            return buf.getvalue()
    except Exception as e:
        print(f"Capture error: {e}")
    return None

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Air Cursor — Live Observer Dashboard</title>
<style>
  :root {
    --bg-dark: #0a0d14;
    --card-bg: #111726;
    --border: #1e293b;
    --cyan: #00e5ff;
    --green: #10b981;
    --text-primary: #f8fafc;
    --text-muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
  body { background: var(--bg-dark); color: var(--text-primary); padding: 20px; }
  header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 20px; }
  h1 { font-size: 20px; font-weight: 700; color: var(--cyan); display: flex; align-items: center; gap: 10px; }
  .badge { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; background: rgba(16, 185, 129, 0.15); color: var(--green); border: 1px solid var(--green); }
  .grid-telemetry { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 20px; }
  .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 15px; }
  .card-header { font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px; font-weight: 600; }
  .card-val { font-size: 20px; font-weight: 700; font-family: monospace; }
  .card-sub { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
  .main-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
  .stream-container { background: #000; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; position: relative; }
  .stream-container img { width: 100%; height: auto; display: block; }
  .controls-panel { display: flex; flex-direction: column; gap: 15px; }
  .btn-group { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  button { padding: 10px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; border: none; }
  .btn-start { background: var(--cyan); color: #000; grid-column: span 2; }
  .btn-stop { background: #ef4444; color: #fff; grid-column: span 2; }
  .log-box { background: #07090e; border: 1px solid var(--border); border-radius: 6px; padding: 10px; height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; }
</style>
</head>
<body>
<header>
  <h1>AIR CURSOR <span style="font-size: 13px; color: var(--text-muted); font-weight: 400;">Independent AI Pointer</span></h1>
  <div><span class="badge">100% INPUT ISOLATION ACTIVE</span></div>
</header>
<div class="grid-telemetry">
  <div class="card">
    <div class="card-header">Human Hardware Cursor (OS)</div>
    <div class="card-val" id="human-pos">X: --- | Y: ---</div>
    <div class="card-sub">Untouched and Isolated</div>
  </div>
  <div class="card">
    <div class="card-header">Autonomous AI Cursor (Blender)</div>
    <div class="card-val" style="color: var(--cyan);" id="ai-pos">X: --- | Y: ---</div>
    <div class="card-sub" id="ai-action">Target: Ready</div>
  </div>
  <div class="card">
    <div class="card-header">Operator Status</div>
    <div class="card-val" style="color: var(--green);" id="ai-status">IDLE</div>
    <div class="card-sub" id="ai-perf">FPS: -- | Jitter: --ms</div>
  </div>
</div>
<div class="main-layout">
  <div class="stream-container">
    <img id="viewport-feed" src="/api/snapshot" alt="Live Blender Feed" />
  </div>
  <div class="controls-panel">
    <div class="card">
      <div class="card-header">Controls</div>
      <div class="btn-group">
        <button class="btn-start" onclick="execCmd('start')">START</button>
        <button style="background:#334155;color:#fff;" onclick="execCmd('pause')">PAUSE</button>
        <button style="background:#0f766e;color:#fff;" onclick="execCmd('resume')">RESUME</button>
        <button class="btn-stop" onclick="execCmd('stop')">EMERGENCY STOP</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">Activity Log</div>
      <div class="log-box" id="log-box"></div>
    </div>
  </div>
</div>
<script>
function addLog(msg) {
  const box = document.getElementById("log-box");
  const time = new Date().toLocaleTimeString();
  const line = document.createElement("div");
  line.innerHTML = `[${time}] ${msg}`;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}
function updateTelemetry() {
  fetch('/api/telemetry')
    .then(r => r.json())
    .then(data => {
      document.getElementById("human-pos").innerText = `X: ${data.human.x} | Y: ${data.human.y}`;
      document.getElementById("ai-pos").innerText = `X: ${data.ai.ai_x || data.ai.win_x} | Y: ${data.ai.ai_y || data.ai.win_y}`;
      document.getElementById("ai-status").innerText = data.ai.status;
      document.getElementById("ai-action").innerText = data.ai.action || "Ready";
      document.getElementById("ai-perf").innerText = `FPS: ${data.ai.avg_fps || 60} | Jitter: ${data.ai.frame_jitter_ms || 0}ms`;
    }).catch(() => {});
}
function refreshSnapshot() {
  document.getElementById("viewport-feed").src = '/api/snapshot?t=' + Date.now();
}
function execCmd(action) {
  fetch('/api/' + action, { method: 'POST' }).then(() => addLog('CMD: ' + action.toUpperCase()));
}
setInterval(updateTelemetry, 100);
setInterval(refreshSnapshot, 400);
</script>
</body>
</html>
"""

class ObserverHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode('utf-8'))
        elif parsed.path == "/api/telemetry":
            human = get_human_cursor_pos()
            ai = get_blender_telemetry()
            data = {"human": human, "ai": ai}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        elif parsed.path == "/api/snapshot":
            jpeg = capture_blender_jpeg()
            if jpeg:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                self.wfile.write(jpeg)
            else:
                self.send_response(503)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        cmd_action = parsed.path.lstrip("/api/")
        if cmd_action in ("start", "pause", "resume", "stop"):
            res = send_blender_cmd({"cmd": cmd_action})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=DEFAULT_PORT):
    server = socketserver.TCPServer(("", port), ObserverHandler)
    print(f"Air Cursor Observer Server running at http://localhost:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
