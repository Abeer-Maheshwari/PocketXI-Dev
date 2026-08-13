import json
import base64
import sys

# Detect WebAssembly / Pygbag environment
IS_WASM = sys.platform == "emscripten"

if not IS_WASM:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        IS_WASM = True

class EncryptionEngine:
    # Module that utilizes cryptography on Desktop and a WebAssembly fallback in Browser
    @staticmethod
    def generate_secure_key():
        if not IS_WASM:
            return Fernet.generate_key()
        return b"pocket_xi_wasm_secure_key_12345"

    @staticmethod
    def encryptData(payload_dict, secret_key):
        # Converts a dictionary to JSON and encrypts it
        if not IS_WASM:
            try:
                serialised_data = json.dumps(payload_dict).encode('utf-8')
                cipher = Fernet(secret_key)
                encrypted_token = cipher.encrypt(serialised_data)
                return encrypted_token.decode('utf-8')
            except Exception as e:
                print(f"ERROR: Encryption failure: {e}")
                return None
        else:
            # Pure Python XOR cipher for WASM
            try:
                raw_bytes = json.dumps(payload_dict).encode('utf-8')
                key_bytes = secret_key if isinstance(secret_key, bytes) else str(secret_key).encode('utf-8')
                encrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw_bytes)])
                return base64.b64encode(encrypted).decode('utf-8')
            except Exception as e:
                print(f"ERROR: WASM Encryption failure: {e}")
                return None

    @staticmethod
    def decryptData(encrypted_token, secret_key):
        # Decrypts a secure token string back into dictionary format
        if not IS_WASM:
            try:
                cipher = Fernet(secret_key)
                decrypted_bytes = cipher.decrypt(encrypted_token.encode('utf-8'))
                return json.loads(decrypted_bytes.decode('utf-8'))
            except Exception as e:
                print(f"ERROR: Decryption failure: {e}")
                return None
        else:
            # Pure Python XOR cipher for WASM
            try:
                encrypted_bytes = base64.b64decode(encrypted_token.encode('utf-8'))
                key_bytes = secret_key if isinstance(secret_key, bytes) else str(secret_key).encode('utf-8')
                decrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(encrypted_bytes)])
                return json.loads(decrypted.decode('utf-8'))
            except Exception as e:
                print(f"ERROR: WASM Decryption failure: {e}")
                return None