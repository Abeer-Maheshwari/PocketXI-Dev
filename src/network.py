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
    # Handles WebSocket connection for online multiplayer and cloud authentication

    def __init__(self, server_uri="wss://pocketxi.duckdns.org"):
        self.server_uri = server_uri
        self.is_wasm = IS_WASM

        self.connected = False
        self.room_code = None
        self.player_role = None  # "p1" or "p2"
        self.match_started = False
        self.error_message = None
        self.last_auth_response = None

        self.inbox = deque()
        self._ws = None
        self._receive_task = None

    async def connect(self):
        if self.connected:
            return True

        self.error_message = None

        if not self.is_wasm:
            # Desktop connection using websockets library
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
            # Browser WebSocket connection via Pygbag JS bridge
            try:
                js_code = (
                    "window.__pxi_inbox = window.__pxi_inbox || [];"
                    "window.__pxi_status = 'connecting';"
                    "window.__pxi_error = '';"
                    f"var serverUri = '{self.server_uri}';"
                    "if (window.location && window.location.protocol === 'https:' && serverUri.startsWith('ws://')) {"
                    "  serverUri = 'wss://' + serverUri.slice(5);"
                    "}"
                    "try {"
                    "  window.__pxi_socket = new WebSocket(serverUri);"
                    "  window.__pxi_socket.onopen = function() { window.__pxi_status = 'connected'; };"
                    "  window.__pxi_socket.onmessage = function(e) { window.__pxi_inbox.push(e.data); };"
                    "  window.__pxi_socket.onerror = function(e) {"
                    "    window.__pxi_status = 'error';"
                    "    window.__pxi_error = 'Connection blocked. Please disable Adblock / Brave Shields for online play.';"
                    "  };"
                    "  window.__pxi_socket.onclose = function(e) {"
                    "    window.__pxi_status = 'closed';"
                    "    if (e.code === 1006) {"
                    "      window.__pxi_error = 'Connection blocked (Code 1006). Please disable Adblock / Brave Shields.';"
                    "    } else if (e.code === 1000) {"
                    "      window.__pxi_error = 'Connection closed normally.';"
                    "    } else {"
                    "      window.__pxi_error = 'Closed (code ' + e.code + (e.reason ? ': ' + e.reason : '') + '). Check Adblock settings.';"
                    "    }"
                    "  };"
                    "} catch(e) {"
                    "  window.__pxi_status = 'error';"
                    "  window.__pxi_error = 'Connection blocked. Please disable Adblock / Brave Shields for online play.';"
                    "}"
                )
                platform.window.eval(js_code)

                for _ in range(80):
                    ready_state = int(platform.window.eval("window.__pxi_socket ? window.__pxi_socket.readyState : -1"))
                    status = str(platform.window.eval("window.__pxi_status || ''"))

                    if ready_state == 1 or status == "connected":
                        self.connected = True
                        return True
                    elif status in ("error", "closed") or ready_state in (2, 3):
                        raw_err = str(platform.window.eval("window.__pxi_error || ''"))
                        self.error_message = raw_err or "Connection blocked (Code 1006). Please disable Adblock."
                        return False

                    await asyncio.sleep(0.1)

                self.error_message = "Connection timed out. Check internet / Adblock settings."
                return False

            except Exception as e:
                self.error_message = f"Socket error: {e}"
                return False

    async def auth_register(self, username, password):
        if not self.connected:
            connected = await self.connect()
            if not connected:
                return {"status": "auth_error", "message": self.error_message or "Could not connect to cloud server."}

        self.last_auth_response = None
        await self._send({"action": "register", "username": username, "password": password})

        for _ in range(50):
            self.pop_messages()
            if self.last_auth_response:
                resp = self.last_auth_response
                self.last_auth_response = None
                return resp
            await asyncio.sleep(0.1)

        return {"status": "auth_error", "message": "Server timeout."}

    async def auth_login(self, username, password):
        if not self.connected:
            connected = await self.connect()
            if not connected:
                return {"status": "auth_error", "message": self.error_message or "Could not connect to cloud server."}

        self.last_auth_response = None
        await self._send({"action": "login", "username": username, "password": password})

        for _ in range(50):
            self.pop_messages()
            if self.last_auth_response:
                resp = self.last_auth_response
                self.last_auth_response = None
                return resp
            await asyncio.sleep(0.1)

        return {"status": "auth_error", "message": "Server timeout."}

    async def auth_save_stats(self, username, stats):
        if not self.connected:
            await self.connect()
        if self.connected:
            await self._send({"action": "save_stats", "username": username, "stats": stats})

    async def create_room(self):
        await self._send({"action": "create"})

    async def join_room(self, room_code):
        self.room_code = room_code.upper().strip()
        await self._send({"action": "join", "room": self.room_code})

    async def send_relay(self, payload):
        if self.connected and self.room_code:
            await self._send({"action": "relay", "room": self.room_code, "payload": payload})

    def _handle_incoming_packet(self, data):
        status = data.get("status")

        if status in ("register_success", "login_success", "auth_error", "stats_saved"):
            self.last_auth_response = data
        elif status == "room_created":
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
        # Fetch any newly arrived messages from queue
        if self.is_wasm and self.connected:
            try:
                count = int(platform.window.eval("(window.__pxi_inbox && window.__pxi_inbox.length) || 0;"))
                if count > 0:
                    for _ in range(count):
                        raw_msg = str(platform.window.eval("window.__pxi_inbox.shift();"))
                        if raw_msg and raw_msg not in ("undefined", "null"):
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
                safe_json = json.dumps(raw_msg)
                platform.window.eval(f"if (window.__pxi_socket && window.__pxi_socket.readyState === 1) {{ window.__pxi_socket.send({safe_json}); }}")
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
        self.room_code = None
        self.player_role = None
        self.match_started = False
        self.inbox.clear()
        if not self.is_wasm and self._ws:
            await self._ws.close()
            if self._receive_task:
                self._receive_task.cancel()
        elif self.is_wasm:
            try:
                platform.window.eval("if (window.__pxi_socket) { window.__pxi_socket.close(); } window.__pxi_inbox = [];")
            except Exception:
                pass
        self._ws = None