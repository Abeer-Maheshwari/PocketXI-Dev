import asyncio
import json
import sqlite3
import hashlib
import secrets
import string
import os
import websockets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "pocketxi.db")
ROOMS = {}

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                goals INTEGER DEFAULT 0,
                shots INTEGER DEFAULT 0,
                possession_time REAL DEFAULT 0.0,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        conn.commit()

init_db()

async def handle_auth_register(ws, data):
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not (3 <= len(username) <= 15) or len(password) < 8:
        return await ws.send(json.dumps({"status": "auth_error", "message": "Invalid username or password length."}))

    salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, salt, password_hash) VALUES (?, ?, ?)", (username, salt, pw_hash))
            user_id = cur.lastrowid
            cur.execute("INSERT INTO user_profiles (user_id, goals, shots, possession_time) VALUES (?, 0, 0, 0.0)", (user_id,))
            conn.commit()
        await ws.send(json.dumps({"status": "register_success", "username": username}))
    except sqlite3.IntegrityError:
        await ws.send(json.dumps({"status": "auth_error", "message": "Username already exists."}))

async def handle_auth_login(ws, data):
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        user = cur.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            return await ws.send(json.dumps({"status": "auth_error", "message": "Username not found."}))

        pw_hash = hashlib.sha256((password + user["salt"]).encode("utf-8")).hexdigest()
        if pw_hash != user["password_hash"]:
            return await ws.send(json.dumps({"status": "auth_error", "message": "Incorrect password."}))

        profile = cur.execute("SELECT goals, shots, possession_time FROM user_profiles WHERE user_id = ?", (user["id"],)).fetchone()
        profile_dict = dict(profile) if profile else {"goals": 0, "shots": 0, "possession_time": 0.0}

        await ws.send(json.dumps({
            "status": "login_success",
            "username": user["username"],
            "profile": profile_dict
        }))

async def handle_save_stats(ws, data):
    username = data.get("username")
    stats = data.get("stats", {})
    goals = int(stats.get("goals", 0))
    shots = int(stats.get("shots", 0))
    poss = float(stats.get("possession_time", 0.0))

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            UPDATE user_profiles
            SET goals = goals + ?, shots = shots + ?, possession_time = possession_time + ?
            WHERE user_id = (SELECT id FROM users WHERE username = ?)
        """, (goals, shots, poss, username))
        conn.commit()
    await ws.send(json.dumps({"status": "stats_saved"}))

async def handle_create_room(ws):
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    ROOMS[code] = {"p1": ws, "p2": None}
    await ws.send(json.dumps({"status": "room_created", "room": code, "role": "p1"}))

async def handle_join_room(ws, room_code):
    room = ROOMS.get(room_code)
    if not room:
        return await ws.send(json.dumps({"status": "error", "message": "Room not found"}))
    if room["p2"] is not None:
        return await ws.send(json.dumps({"status": "error", "message": "Room is full"}))

    room["p2"] = ws
    await ws.send(json.dumps({"status": "join_success", "room": room_code, "role": "p2"}))
    start_pkt = json.dumps({"status": "match_start", "room": room_code})
    await room["p1"].send(start_pkt)
    await room["p2"].send(start_pkt)

# Compatible with both handler(ws) and handler(ws, path) across all websockets versions
async def handler(ws, *args):
    current_room = None
    try:
        async for message in ws:
            data = json.loads(message)
            action = data.get("action")

            if action == "register":
                await handle_auth_register(ws, data)
            elif action == "login":
                await handle_auth_login(ws, data)
            elif action == "save_stats":
                await handle_save_stats(ws, data)
            elif action == "create":
                await handle_create_room(ws)
            elif action == "join":
                current_room = data.get("room")
                await handle_join_room(ws, current_room)
            elif action == "relay":
                room_code = data.get("room") or current_room
                if room_code in ROOMS:
                    room = ROOMS[room_code]
                    target = room["p2"] if ws == room["p1"] else room["p1"]
                    if target:
                        await target.send(json.dumps({"status": "relay", "payload": data.get("payload")}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        for r_code, room in list(ROOMS.items()):
            if ws in (room["p1"], room["p2"]):
                other = room["p2"] if ws == room["p1"] else room["p1"]
                if other:
                    try:
                        await other.send(json.dumps({"status": "relay", "payload": {"type": "PLAYER_LEFT"}}))
                    except Exception:
                        pass
                ROOMS.pop(r_code, None)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("PocketXI Server & SQLite DB running on port 8765...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())