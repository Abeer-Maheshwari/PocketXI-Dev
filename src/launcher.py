import os
import json
import base64
import hashlib
import pygame
from src.encryption import EncryptionEngine
try:
    import secrets
    def get_secure_salt():
        return secrets.token_hex(16)
except ImportError:
    def get_secure_salt():
        return os.urandom(16).hex()

class GameLauncher:
    # Gatekeeper that manages authentication, saving, and dashboards before passing execution to main game loop.
    
    def __init__(self):
        # Initialises the launcher window, assets, and default security states.
        pygame.init()
        self.width = 1280
        self.height = 720
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Pocket XI - Login")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 40)
        
        # Runtime data is stored separately from application code and assets.
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(base_path, "data")
        self.auth_path = os.path.join(data_path, "auth.json")
        self.userdata_path = os.path.join(data_path, "userdata.json")
        self._initialise_local_storage_files()
        self.base_difficulty_tier = 3
        self.high_contrast_active = False
        
        # Login Configuration
        self.menu_state = "LOGIN_SCREEN"
        self.username_input = ""
        self.password_input = ""
        self.active_input_box = "username"
        self.status_message = ""
        self.status_color = "white"
        
        # Session Management
        self.active_user_session = None
        self.temp_saved_profile = None

    def _initialise_local_storage_files(self):
        # Create the data directory and empty stores on a first run.
        os.makedirs(os.path.dirname(self.auth_path), exist_ok=True)
        for path in (self.auth_path, self.userdata_path):
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as file:
                    json.dump({}, file)

    @staticmethod
    def _load_json_dict(path):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
    
    def validateCredentials(self, username, password):
        # Enforces length and alphanumeric conditions
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")
        
        # Constraint boundaries
        if not (3 <= len(u_clean) <= 15):
            self.status_message = "Username must be between 3 and 15 characters long."
            self.status_color = (255, 100, 100)
            return False
        if len(p_clean) < 8:
            self.status_message = "Password must be at least 8 characters long."
            self.status_color = (255, 100, 100)
            return False
            
        # Character parsing filter to block injection symbols
        for char in u_clean:
            if not (char.isalnum() or char in ['_', '.', '@',]):
                self.status_message = "'_', '.', or '@' characters not allowed in username."
                self.status_color = (255, 100, 100)
                return False
        return True

    def register(self, username, password):
        # Computes salted SHA-256 hashes and saves initialised profile data to disk.
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")
        
        if not self.validateCredentials(u_clean, p_clean):
            return False
            
        auth_db = self._load_json_dict(self.auth_path)
            
        if u_clean in auth_db:
            self.status_message = "Username already exists."
            self.status_color = (255, 100, 100)
            return False
            
        # Salting
        salt = get_secure_salt()
        salted_password = p_clean + salt
        password_hash = hashlib.sha256(salted_password.encode('utf-8')).hexdigest()
        
        # Generate key directly from the password
        derived_key = hashlib.sha256(p_clean.encode('utf-8')).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        
        # Base progress template
        initial_stats_payload = {
            "goals": 0,
            "shots": 0,
            "possession_time": 0.0
        }
        
        # Reversible data encryption
        encrypted_data_token = EncryptionEngine.encryptData(initial_stats_payload, fernet_key)
        if not encrypted_data_token:
            self.status_message = "Cryptographic processing failed."
            self.status_color = (255, 100, 100)
            return False
            
        # Commit records across both storage files
        try:
            auth_db[u_clean] = {"salt": salt, "hash": password_hash}
            with open(self.auth_path, 'w', encoding='utf-8') as f:
                json.dump(auth_db, f, indent=4)
                
            user_db = self._load_json_dict(self.userdata_path)
            user_db[u_clean] = encrypted_data_token
            with open(self.userdata_path, 'w', encoding='utf-8') as f:
                json.dump(user_db, f, indent=4)
                
            self.status_message = "Successful Registration, Proceed to Login"
            self.status_color = (100, 255, 100)
            self.menu_state = "LOGIN_SCREEN"
            self.password_input = ""
            return True
        except Exception as e:
            self.status_message = f"FILE SYNC ERROR: Rollback triggered. Error: {e}"
            self.status_color = (255, 100, 100)
            return False
    
    def login(self, username, password):
        # Reconstructs salted hashes from the database and extracts decoded session history
        u_clean = username.strip().replace(" ", "")
        p_clean = password.strip().replace(" ", "")
        
        if not self.validateCredentials(u_clean, p_clean):
            return False
            
        auth_db = self._load_json_dict(self.auth_path)
            
        if u_clean not in auth_db:
            self.status_message = "AUTHENTICATION REFUSED: Username does not match records."
            self.status_color = (255, 100, 100)
            return False
            
        # Reconstruct and verify calculated hash values against target database contents
        record = auth_db[u_clean]
        if not isinstance(record, dict) or "salt" not in record or "hash" not in record:
            self.status_message = "AUTHENTICATION REFUSED: Account record is invalid."
            self.status_color = (255, 100, 100)
            return False
        stored_salt = record["salt"]
        stored_hash = record["hash"]
        computed_hash = hashlib.sha256((p_clean + stored_salt).encode('utf-8')).hexdigest()
        
        if computed_hash != stored_hash:
            self.status_message = "AUTHENTICATION REFUSED: Incorrect password."
            self.status_color = (255, 100, 100)
            return False
            
        # Password matches -> derive secret key
        derived_key = hashlib.sha256(p_clean.encode('utf-8')).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        
        user_db = self._load_json_dict(self.userdata_path)
        encrypted_token_string = user_db.get(u_clean)
        if not isinstance(encrypted_token_string, str):
            self.status_message = "DECRYPTION ERROR: No valid saved profile was found."
            self.status_color = (255, 100, 100)
            return False
        
        # Extract plaintext dictionaries
        decrypted_profile = EncryptionEngine.decryptData(encrypted_token_string, fernet_key)
        
        if decrypted_profile is not None:
            self.active_user_session = u_clean
            self.temp_saved_profile = decrypted_profile
            self.status_message = f"WELCOME BACK: {u_clean}. Session active."
            self.status_color = (100, 255, 100)
            self.menu_state = "MAIN_HUB"
            return True
        else:
            self.status_message = "DECRYPTION ERROR: JSON stream extraction rejected."
            self.status_color = (255, 100, 100)
            return False
