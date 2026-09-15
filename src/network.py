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
        import js
    except (ImportError, ModuleNotFoundError):
        js = None


class NetworkClient:
    """Manages asynchronous WebSocket communication across Desktop and Pygbag Web builds."""

    def __init__(self, server_uri="wss://photographs-river-various-observed.trycloudflare.com"):
        self.server_uri = server_uri
        self.is_wasm = IS_WASM

        # Connection & Lobby State
        self.connected = False
        self.room_code = None
        self.player_role = None  # "p1" (Host) or "p2" (Guest)
        self.match_started = False
        self.error_message = None

        # Message queue for the Pygame loop
        self.inbox = deque()

        # Internal references
        self._ws = None
        self._receive_task = None

    async def connect(self):
        """Establish connection with the relay server."""
        if self.connected:
            return True

        self.error_message = None

        if not self.is_wasm:
            # Native Desktop Async Connection
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
            # Pygbag / Emscripten Browser WebSocket Interface
            try:
                if js is None or not hasattr(js, "WebSocket"):
                    self.error_message = "Browser WebSocket API unavailable."
                    return False

                # Instantiate native browser WebSocket
                self._ws = js.WebSocket.new(self.server_uri)

                # Bind direct event callbacks (Pygbag automatically handles JS event bridging)
                self._ws.onopen = self._wasm_on_open
                self._ws.onmessage = self._wasm_on_message
                self._ws.onerror = self._wasm_on_error
                self._ws.onclose = self._wasm_on_close

                # Await handshake completion
                for _ in range(60):
                    if self.connected:
                        return True
                    if self.error_message:
                        return False
                    await asyncio.sleep(0.05)

                if not self.connected:
                    self.error_message = "Connection timed out."
                return self.connected

            except Exception as e:
                self.error_message = f"WASM Socket failed: {e}"
                return False

    # -------------------------------------------------------------
    # Room Actions
    # -------------------------------------------------------------

    async def create_room(self):
        """Request the server to create a new room as Host (p1)."""
        await self._send({"action": "create"})

    async def join_room(self, room_code):
        """Request to join an existing room code as Guest (p2)."""
        self.room_code = room_code.upper().strip()
        await self._send({"action": "join", "room": self.room_code})

    async def send_relay(self, payload):
        """Relay game state / input packet to the opponent."""
        if self.connected and self.room_code:
            await self._send({"action": "relay", "payload": payload})

    # -------------------------------------------------------------
    # Message Dispatch & Queuing
    # -------------------------------------------------------------

    def _handle_incoming_packet(self, data):
        """Parse raw incoming JSON payload and update lobby state."""
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
            self.error_message = data.get("message", "Unknown server error")

        # Push to inbox for Pygame loop
        self.inbox.append(data)

    def pop_messages(self):
        """Drain and return queued packets during a Pygame frame."""
        messages = []
        while self.inbox:
            messages.append(self.inbox.popleft())
        return messages

    # -------------------------------------------------------------
    # Transports
    # -------------------------------------------------------------

    async def _send(self, message_dict):
        """Serialize and send payload over active socket."""
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
        """Background receiver task for desktop builds."""
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

    # -------------------------------------------------------------
    # Browser Callbacks
    # -------------------------------------------------------------

    def _wasm_on_open(self, event=None):
        self.connected = True
        self.error_message = None

    def _wasm_on_message(self, event):
        try:
            raw_text = str(event.data)
            data = json.loads(raw_text)
            self._handle_incoming_packet(data)
        except Exception:
            pass

    def _wasm_on_error(self, event=None):
        self.error_message = "WebSocket handshake failed or mixed-content blocked."

    def _wasm_on_close(self, event=None):
        self.connected = False

    async def disconnect(self):
        """Close active connection."""
        self.connected = False
        if not self.is_wasm and self._ws:
            await self._ws.close()
            if self._receive_task:
                self._receive_task.cancel()
        elif self.is_wasm and self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._ws = None