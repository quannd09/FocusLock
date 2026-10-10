import os
import sys
import time
import asyncio
import json
import threading
import psutil
import websockets

def free_stale_port_holders(port=8765):
    """Kills any orphaned python process holding the WebSocket port from a previous run."""
    try:
        current_pid = os.getpid()
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                if conn.pid and conn.pid != current_pid:
                    try:
                        p = psutil.Process(conn.pid)
                        if "python" in p.name().lower():
                            print(f"[WebSocketBridge] Terminating stale Python PID {conn.pid} holding port {port}...")
                            p.kill()
                            time.sleep(0.5)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[WebSocketBridge] Note on port check: {e}")

def detect_browser_from_port(port):
    """Detects browser process name (Edge, Chrome, Cốc Cốc, Brave, etc.) from the client connection port."""
    if not port:
        return None
    try:
        for c in psutil.net_connections(kind='inet'):
            if c.laddr and c.laddr.port == port:
                if c.pid:
                    try:
                        p = psutil.Process(c.pid)
                        name = p.name().lower()
                        if "msedge" in name or "edge" in name:
                            return "Edge"
                        elif "chrome" in name:
                            return "Chrome"
                        elif "browser" in name or "coccoc" in name:
                            return "Cốc Cốc"
                        elif "brave" in name:
                            return "Brave"
                        elif "opera" in name:
                            return "Opera"
                        elif "firefox" in name:
                            return "Firefox"
                        return p.name().replace(".exe", "").capitalize()
                    except Exception:
                        pass
    except Exception:
        pass
    return None

class WebSocketBridge:
    def __init__(self, host="127.0.0.1", port=8765, on_tabs_received=None, on_client_changed=None):
        self.host = host
        self.port = port
        self.clients = set()
        self.client_info = {}
        self.on_tabs_received = on_tabs_received
        self.on_client_changed = on_client_changed
        self.loop = None
        self.thread = None
        self.is_running = False

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def _run_server(self):
        # Automatically clean up any stale instance holding the port
        free_stale_port_holders(self.port)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def main():
            # Try binding with up to 3 retries in case Windows socket is clearing
            server_started = False
            for attempt in range(3):
                try:
                    async with websockets.serve(self._handler, self.host, self.port):
                        print(f"[WebSocketBridge] Server running on ws://{self.host}:{self.port}")
                        server_started = True
                        await asyncio.Future()  # Run indefinitely
                except OSError as e:
                    if e.errno == 10048 and attempt < 2:
                        print(f"[WebSocketBridge] Port {self.port} busy, retrying in 1s (Attempt {attempt + 1}/3)...")
                        free_stale_port_holders(self.port)
                        await asyncio.sleep(1)
                    else:
                        print(f"[WebSocketBridge] Server error: {e}")
                        break
                except Exception as e:
                    print(f"[WebSocketBridge] Server error: {e}")
                    break

        try:
            self.loop.run_until_complete(main())
        except Exception as e:
            print(f"[WebSocketBridge] Loop ended: {e}")

    def _notify_clients_changed(self):
        if self.on_client_changed:
            browsers = [info.get("browser", "Browser") for info in self.client_info.values()]
            try:
                self.on_client_changed(len(self.clients), browsers)
            except Exception as e:
                print(f"[WebSocketBridge] Error calling on_client_changed: {e}")

    async def _handler(self, websocket):
        self.clients.add(websocket)

        # OS-level process detection via remote socket port
        browser_name = "Browser"
        try:
            if hasattr(websocket, "remote_address") and websocket.remote_address:
                remote_port = websocket.remote_address[1]
                detected = detect_browser_from_port(remote_port)
                if detected:
                    browser_name = detected
        except Exception as e:
            print(f"[WebSocketBridge] Port detection note: {e}")

        self.client_info[websocket] = {"browser": browser_name}
        print(f"[WebSocketBridge] Client connected ({browser_name}). Total: {len(self.clients)}")
        self._notify_clients_changed()

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    self._handle_message(websocket, data)
                except Exception as e:
                    print(f"[WebSocketBridge] Error handling msg: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            self.client_info.pop(websocket, None)
            print(f"[WebSocketBridge] Client disconnected. Total: {len(self.clients)}")
            self._notify_clients_changed()

    def _handle_message(self, websocket, data):
        msg_type = data.get("type")
        browser = data.get("browser")
        if browser and browser != "Browser" and websocket in self.client_info:
            if self.client_info[websocket].get("browser") in ("Browser", None):
                self.client_info[websocket]["browser"] = browser
                self._notify_clients_changed()

        if msg_type == "TABS_LIST":
            tabs = data.get("tabs", [])
            client_browser = self.client_info.get(websocket, {}).get("browser")
            if not client_browser or client_browser == "Browser":
                try:
                    if hasattr(websocket, "remote_address") and websocket.remote_address:
                        client_browser = detect_browser_from_port(websocket.remote_address[1]) or "Browser"
                except Exception:
                    client_browser = "Browser"

            # Tag each tab with detected browser name
            for t in tabs:
                if not t.get("browser") or t.get("browser") == "Browser":
                    t["browser"] = client_browser

            if self.on_tabs_received:
                try:
                    self.on_tabs_received(tabs, client_browser)
                except TypeError:
                    self.on_tabs_received(tabs)
        elif msg_type == "HELLO":
            client_browser = self.client_info.get(websocket, {}).get("browser", "Browser")
            print(f"[WebSocketBridge] Extension greeting received from {client_browser}.")

    def request_tabs(self):
        self._broadcast({"type": "GET_TABS"})

    def start_lock(self, allowed_urls):
        self._broadcast({"type": "LOCK_START", "allowedUrls": allowed_urls})

    def stop_lock(self):
        self._broadcast({"type": "LOCK_STOP"})

    def _broadcast(self, msg):
        if not self.loop or not self.clients:
            return
        payload = json.dumps(msg)
        asyncio.run_coroutine_threadsafe(self._async_broadcast(payload), self.loop)

    async def _async_broadcast(self, payload):
        if self.clients:
            await asyncio.gather(
                *[client.send(payload) for client in self.clients],
                return_exceptions=True
            )

    def is_connected(self):
        return len(self.clients) > 0
