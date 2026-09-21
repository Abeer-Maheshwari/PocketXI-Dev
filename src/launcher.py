# src/launcher.py
import base64
import hashlib
import json
import os
import random
import pygame
from src.encryption import EncryptionEngine


def get_secure_salt():
    # Generate random salt with WASM fallback
    try:
        import secrets
        return secrets.token_hex(16)
    except (ImportError, NotImplementedError):
        return ''.join(random.choice("0123456789abcdef") for _ in range(32))


class GameLauncher:
    # Handles local offline auth, saved career stats, and settings
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(base_path, "data")
        self.auth_path = os.path.join(data_path, "auth.json")
        self.userdata_path = os.path.join(data_path, "userdata.json")
        self.settings_path = os.path.join(data_path, "settings.json")
        self._initialise_local_storage_files()

        # Default settings
        self.master_volume = 0.8
        self.base_difficulty_tier = 3
        self.high_contrast_active = False
        self.p1_is_ai = False
        self.p2_is_ai = True
        self.load_settings()

        # Session state
        self.menu_state = "LOGIN_SCREEN"
        self.username_input = ""
        self.password_input = ""
        self.status_message = ""
        self.status_color = "white"
        self.active_user_session = None
        self.temp_saved_profile = None

    def _initialise_local_storage_files(self):
        # Create data directory and JSON storage files if missing
        os.makedirs(os.path.dirname(self.auth_path), exist_ok=True)
        for path in (self.auth_path, self.userdata_path, self.settings_path):
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as file:
                    json.dump({}, file)

    @staticmethod
    def _load_json_dict(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def load_settings(self):
        data = self._load_json_dict(self.settings_path)
        self.master_volume = float(data.get("master_volume", 0.8))
        self.base_difficulty_tier = int(data.get("base_difficulty_tier", 3))
        self.p1_is_ai = bool(data.get("p1_is_ai", False))
        self.p2_is_ai = bool(data.get("p2_is_ai", True))
        self.high_contrast_active = bool(data.get("high_contrast_active", False))

    def save_settings(self):
        payload = {
            "master_volume": round(self.master_volume, 2),
            "base_difficulty_tier": int(self.base_difficulty_tier),
            "p1_is_ai": self.p1_is_ai,
            "p2_is_ai": self.p2_is_ai,
            "high_contrast_active": self.high_contrast_active,
        }
        try:
            with open(self.settings_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=4)
        except OSError:
            pass

    def validateCredentials(self, username, password):
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")

        if not (3 <= len(u_clean) <= 15):
            self.status_message = "Username must be between 3 and 15 characters long."
            self.status_color = (255, 100, 100)
            return False
        if len(p_clean) < 8:
            self.status_message = "Password must be at least 8 characters long."
            self.status_color = (255, 100, 100)
            return False

        for char in u_clean:
            if not (char.isalnum() or char in ["_", ".", "@"]):
                self.status_message = "Only letters, numbers, '_', '.', and '@' allowed."
                self.status_color = (255, 100, 100)
                return False
        return True

    def register(self, username, password):
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")

        if not self.validateCredentials(u_clean, p_clean):
            return False

        auth_db = self._load_json_dict(self.auth_path)
        if u_clean in auth_db:
            self.status_message = "Username already exists."
            self.status_color = (255, 100, 100)
            return False

        salt = get_secure_salt()
        salted_password = p_clean + salt
        password_hash = hashlib.sha256(salted_password.encode("utf-8")).hexdigest()

        # Derive encryption key from password for stats
        derived_key = hashlib.sha256(p_clean.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)

        initial_stats = {
            "goals": 0,
            "shots": 0,
            "possession_time": 0.0,
        }

        try:
            encrypted_token = EncryptionEngine.encryptData(initial_stats, fernet_key)
            if not encrypted_token:
                self.status_message = "Failed to encrypt initial stats."
                self.status_color = (255, 100, 100)
                return False

            auth_db[u_clean] = {"salt": salt, "hash": password_hash}
            with open(self.auth_path, "w", encoding="utf-8") as f:
                json.dump(auth_db, f, indent=4)

            user_db = self._load_json_dict(self.userdata_path)
            user_db[u_clean] = encrypted_token
            with open(self.userdata_path, "w", encoding="utf-8") as f:
                json.dump(user_db, f, indent=4)

            self.status_message = "Registration successful. Please log in."
            self.status_color = (100, 255, 100)
            self.menu_state = "LOGIN_SCREEN"
            self.password_input = ""
            return True
        except Exception as e:
            self.status_message = f"Storage error: {e}"
            self.status_color = (255, 100, 100)
            return False

    def login(self, username, password):
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")

        if not self.validateCredentials(u_clean, p_clean):
            return False

        auth_db = self._load_json_dict(self.auth_path)
        if u_clean not in auth_db:
            self.status_message = "Username not found."
            self.status_color = (255, 100, 100)
            return False

        record = auth_db[u_clean]
        if not isinstance(record, dict) or "salt" not in record or "hash" not in record:
            self.status_message = "Corrupted account record."
            self.status_color = (255, 100, 100)
            return False

        stored_salt = record["salt"]
        stored_hash = record["hash"]
        computed_hash = hashlib.sha256((p_clean + stored_salt).encode("utf-8")).hexdigest()

        if computed_hash != stored_hash:
            self.status_message = "Incorrect password."
            self.status_color = (255, 100, 100)
            return False

        derived_key = hashlib.sha256(p_clean.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)

        user_db = self._load_json_dict(self.userdata_path)
        encrypted_token = user_db.get(u_clean)
        if not isinstance(encrypted_token, str):
            self.status_message = "No saved data found."
            self.status_color = (255, 100, 100)
            return False

        try:
            decrypted_profile = EncryptionEngine.decryptData(encrypted_token, fernet_key)
            if decrypted_profile is not None:
                self.active_user_session = u_clean
                self.temp_saved_profile = decrypted_profile
                self.status_message = f"Welcome back, {u_clean}."
                self.status_color = (100, 255, 100)
                self.menu_state = "MAIN_HUB"
                return True
            else:
                self.status_message = "Failed to decrypt profile data."
                self.status_color = (255, 100, 100)
                return False
        except Exception as e:
            self.status_message = "Decryption error occurred."
            self.status_color = (255, 100, 100)
            return False