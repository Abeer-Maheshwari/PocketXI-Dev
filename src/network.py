import sys
import json
import asyncio
from collections import deque

IS_WASM = sys.platform in ("emscripten", "wasi")

if not IS_WASM:
    try:
        import websockets
    except ImportError:
        websockets = None
else:
    websockets = None
    try:
        import platform
    except ImportError:
        platform = None


class NetworkClient:
    """Manages asynchronous WebSocket communication across Desktop and Pygbag builds."""

    def __init__(self, server_uri="wss://152.67.155.250:8765"):
        self.server_uri = server_uri
        self.is_wasm = IS_WASM

        # Connection & Lobby State
        self.connected = False
        self.room_code = None
        self.player_role = None  # "p1" or "p2"
        self.match_started = False
        self.error_message = None

        # Message queue
        self.inbox = deque()
        self._ws = None
        self._receive_task = None

    async def connect(self):
        """Establish connection with the relay server."""
        if self.connected:
            return True

        self.error_message = None

        if not self.is_wasm:
            # Desktop Async Engine
            if websockets is None:
                self.error_message = "Python 'websockets' library not installed."
                return False

            try:
                self._ws = await websockets.connect(self.server_uri)
                self.connected = True
                self._receive_task = asyncio.create_task(self._desktop_receiver())
                return True
            except Exception as e:
                self.error_message = f"Connection failed: {e}"
                self.connected = False
                return False
        else:
            # Pygbag / Browser JS Engine
            try:
                js_code = (
                    "window.__pxi_inbox = window.__pxi_inbox || [];"
                    "window.__pxi_status = 'connecting';"
                    "window.__pxi_error = '';"
                    f"try {{ window.__pxi_socket = new WebSocket('{self.server_uri}'); }} "
                    "catch(e) { window.__pxi_status = 'error'; window.__pxi_error = e.message; }"
                    "window.__pxi_socket.onopen = function() { window.__pxi_status = 'connected'; };"
                    "window.__pxi_socket.onmessage = function(e) { window.__pxi_inbox.push(e.data); };"
                    "window.__pxi_socket.onerror = function(e) { window.__pxi_status = 'error'; window.__pxi_error = 'Handshake failed'; };"
                    "window.__pxi_socket.onclose = function(e) { "
                    "  window.__pxi_status = 'closed'; "
                    "  window.__pxi_error = 'Closed (code ' + e.code + (e.reason ? ': ' + e.reason : '') + ')'; "
                    "};"
                )
                platform.window.eval(js_code)

                # Poll for up to 8 seconds
                for _ in range(80):
                    # Direct check: readyState 1 means OPEN
                    ready_state = int(platform.window.eval("window.__pxi_socket ? window.__pxi_socket.readyState : -1"))
                    status = str(platform.window.eval("window.__pxi_status || ''"))

                    if ready_state == 1 or status == "connected":
                        self.connected = True
                        return True
                    elif status in ("error", "closed") or ready_state in (2, 3):
                        self.error_message = str(platform.window.eval("window.__pxi_error || 'Connection closed'"))
                        return False

                    await asyncio.sleep(0.1)

                self.error_message = "Connection timed out."
                return False

            except Exception as e:
                self.error_message = f"WASM Socket failed: {e}"
                return False

    async def create_room(self):
        await self._send({"action": "create"})

    async def join_room(self, room_code):
        self.room_code = room_code.upper().strip()
        await self._send({"action": "join", "room": self.room_code})

    async def send_relay(self, payload):
        if self.connected and self.room_code:
            await self._send({"action": "relay", "payload": payload})

    def _handle_incoming_packet(self, data):
        status = data.get("status")

        if status == "room_created":
            self.room_code = data.get("room")
            self.player_role = "p1"
        elif status == "join_success":
            self.room_code = data.get("room")
            self.player_role = "p2"
        elif status == "match_start":
            self.match_started = True
        elif status == "error":
            self.error_message = data.get("message", "Server error")

        self.inbox.append(data)

    def pop_messages(self):
        """Drain and return queued packets during a Pygame frame."""
        # Poll WASM JS Inbox if running on web
        if self.is_wasm and self.connected:
            try:
                # Retrieve pending messages from the window array
                count = int(platform.window.eval("window.__pxi_inbox.length;"))
                if count > 0:
                    for _ in range(count):
                        raw_msg = str(platform.window.eval("window.__pxi_inbox.shift();"))
                        try:
                            data = json.loads(raw_msg)
                            self._handle_incoming_packet(data)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass

        messages = []
        while self.inbox:
            messages.append(self.inbox.popleft())
        return messages

    async def _send(self, message_dict):
        raw_msg = json.dumps(message_dict)
        if not self.connected:
            return

        try:
            if not self.is_wasm and self._ws:
                await self._ws.send(raw_msg)
            elif self.is_wasm:
                # Escape quotes for JS eval
                safe_json = json.dumps(raw_msg)
                platform.window.eval(f"window.__pxi_socket.send({safe_json});")
        except Exception as e:
            self.error_message = f"Send error: {e}"

    async def _desktop_receiver(self):
        try:
            async for raw_message in self._ws:
                try:
                    data = json.loads(raw_message)
                    self._handle_incoming_packet(data)
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        finally:
            self.connected = False

    async def disconnect(self):
        self.connected = False
        if not self.is_wasm and self._ws:
            await self._ws.close()
            if self._receive_task:
                self._receive_task.cancel()
        elif self.is_wasm:
            try:
                platform.window.eval("if (window.__pxi_socket) { window.__pxi_socket.close(); }")
            except Exception:
                pass
        self._ws = None