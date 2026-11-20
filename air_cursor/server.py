"""
Air Cursor: Built-in Non-Blocking Socket Command Server.
Enables any external AI agent, script, or controller to dispatch actions and query telemetry.
Runs inside Blender using non-blocking sockets integrated into the main event loop.
"""

import socket
import json
import threading
import traceback
from typing import Optional

class CommandServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 9880):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.dispatch_callback = None

    def start(self, dispatch_callback):
        if self.running:
            return
        self.dispatch_callback = dispatch_callback
        self.running = True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)
            self.sock.settimeout(0.5)
            
            self._thread = threading.Thread(target=self._server_loop, daemon=True)
            self._thread.start()
            print(f"[Air Cursor] Command Server listening on {self.host}:{self.port}")
        except Exception as e:
            print(f"[Air Cursor] Could not bind command server on {self.host}:{self.port}: {e}")
            self.running = False

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _server_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            
            # Handle client in worker
            t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
            t.start()

    def _handle_client(self, conn: socket.socket):
        try:
            conn.settimeout(5.0)
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                try:
                    payload = json.loads(data.decode('utf-8'))
                    break
                except ValueError:
                    continue
            
            if not data:
                conn.close()
                return

            response = {"status": "ok"}
            if self.dispatch_callback:
                try:
                    response = self.dispatch_callback(payload)
                except Exception as e:
                    response = {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

            conn.sendall(json.dumps(response).encode('utf-8'))
        except Exception as e:
            try:
                err_resp = {"status": "error", "message": str(e)}
                conn.sendall(json.dumps(err_resp).encode('utf-8'))
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
