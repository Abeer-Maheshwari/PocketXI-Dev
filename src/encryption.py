import json
import base64
import sys

# Check if running in browser via Pygbag/WASM
IS_WASM = sys.platform == "emscripten"

if not IS_WASM:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        IS_WASM = True


class EncryptionEngine:
    # Encrypts saved profile data locally (Fernet on desktop, XOR fallback in browser)
    @staticmethod
    def generate_secure_key():
        if not IS_WASM:
            return Fernet.generate_key()
        return b"pocket_xi_wasm_secure_key_12345"

    @staticmethod
    def encryptData(payload_dict, secret_key):
        if not IS_WASM:
            try:
                serialised_data = json.dumps(payload_dict).encode('utf-8')
                cipher = Fernet(secret_key)
                encrypted_token = cipher.encrypt(serialised_data)
                return encrypted_token.decode('utf-8')
            except Exception as e:
                print(f"Encryption error: {e}")
                return None
        else:
            # Simple XOR cipher for WASM
            try:
                raw_bytes = json.dumps(payload_dict).encode('utf-8')
                key_bytes = secret_key if isinstance(secret_key, bytes) else str(secret_key).encode('utf-8')
                encrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw_bytes)])
                return base64.b64encode(encrypted).decode('utf-8')
            except Exception as e:
                print(f"WASM encryption error: {e}")
                return None

    @staticmethod
    def decryptData(encrypted_token, secret_key):
        if not IS_WASM:
            try:
                cipher = Fernet(secret_key)
                decrypted_bytes = cipher.decrypt(encrypted_token.encode('utf-8'))
                return json.loads(decrypted_bytes.decode('utf-8'))
            except Exception as e:
                print(f"Decryption error: {e}")
                return None
        else:
            # Simple XOR cipher for WASM
            try:
                encrypted_bytes = base64.b64decode(encrypted_token.encode('utf-8'))
                key_bytes = secret_key if isinstance(secret_key, bytes) else str(secret_key).encode('utf-8')
                decrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(encrypted_bytes)])
                return json.loads(decrypted.decode('utf-8'))
            except Exception as e:
                print(f"WASM decryption error: {e}")
                return None