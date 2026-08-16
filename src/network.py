import pygame
import sys
import json
import asyncio
from collections import deque

IS_WASM = sys.platform == "emscripten"

if not IS_WASM:
    try:
        import websockets
    except ImportError:
        websockets = None
else:
    websockets = None
    try:
        import js
        from pyodide.ffi import create_proxy
    except ImportError:
        pass

class NetworkClient:
    """Manages communication with server."""

    def __init__(self, server_uri="ws://152.67.155.250:8765"):
        self.server_uri = server_uri
        self.is_wasm = IS_WASM

        # Connection & Lobby State
        self.connected = False
        self.room_code = None
        self.player_role = None  # "p1" (Host) or "p2" (Guest)
        self.match_started = False
        self.error_message = None

        # Thread-safe message queue for the Pygame loop
        self.inbox = deque()

        # Internal references
        self._ws = None
        self._receive_task = None

    async def connect(self):
        # Connect to relay server.
        if self.connected:
            return True

        self.error_message = None

        if not self.is_wasm:
            # Desktop Connection
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
            # Browser Connection
            try:
                self._ws = js.WebSocket.new(self.server_uri)

                # Bind JS event proxies
                self._ws.onopen = create_proxy(self._wasm_on_open)
                self._ws.onmessage = create_proxy(self._wasm_on_message)
                self._ws.onerror = create_proxy(self._wasm_on_error)
                self._ws.onclose = create_proxy(self._wasm_on_close)

                # Wait briefly for handshake
                for _ in range(50):
                    if self.connected:
                        return True
                    if self.error_message:
                        return False
                    await asyncio.sleep(0.05)
                return self.connected
            except Exception as e:
                self.error_message = f"WASM Socket failed: {e}"
                return False

    async def create_room(self):
        # Request the server to create a new room as Host (p1).
        await self._send({"action": "create"})

    async def join_room(self, room_code):
        # Request to join an existing room code as Guest (p2).
        self.room_code = room_code.upper().strip()
        await self._send({"action": "join", "room": self.room_code})

    async def send_relay(self, payload):
        # Relay game state / input packet to the other player.
        if self.connected and self.room_code:
            await self._send({"action": "relay", "payload": payload})

    def _handle_incoming_packet(self, data):
        # Parse JSON payload and update lobby state.
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

        # Push to queue for MatchController / UI
        self.inbox.append(data)

    def pop_messages(self):
        # Retrieve and drain all queued packets during a Pygame frame.
        messages = []
        while self.inbox:
            messages.append(self.inbox.popleft())
        return messages

    async def _send(self, message_dict):
        # Serialise and send payload over the active socket.
        raw_msg = json.dumps(message_dict)
        if not self.connected or not self._ws:
            return

        try:
            if not self.is_wasm:
                await self._ws.send(raw_msg)
            else:
                self._ws.send(raw_msg)
        except Exception as e:
            self.error_message = f"Send error: {e}"

    async def _desktop_receiver(self):
        # Background receiver loop for desktop.
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

    def _wasm_on_open(self, event):
        self.connected = True

    def _wasm_on_message(self, event):
        try:
            data = json.loads(event.data)
            self._handle_incoming_packet(data)
        except Exception:
            pass

    def _wasm_on_error(self, event):
        self.error_message = "WebSocket encountered a network error."

    def _wasm_on_close(self, event):
        self.connected = False

    async def disconnect(self):
        # Close connection cleanly.
        self.connected = False
        if not self.is_wasm and self._ws:
            await self._ws.close()
            if self._receive_task:
                self._receive_task.cancel()
        elif self.is_wasm and self._ws:
            self._ws.close()
        self._ws = None