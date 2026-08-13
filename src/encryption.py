import json
from cryptography.fernet import Fernet

class EncryptionEngine:
    # Module that utilises a cryptography library to encrypt user profile data
    @staticmethod
    def generate_secure_key():
        return Fernet.generate_key()
    
    @staticmethod
    def encryptData(payload_dict, secret_key):
        # Converts a dictionary to JSON and encrypts it into a secure token string.
        try:
            serialised_data = json.dumps(payload_dict).encode('utf-8')
            cipher = Fernet(secret_key)
            encrypted_token = cipher.encrypt(serialised_data)
            return encrypted_token.decode('utf-8')
        except Exception as e:
            print(f"ERROR: Encryption failure: {e}")
            return None
    
    @staticmethod
    def decryptData(encrypted_token, secret_key):
        # Decrypts a secure token string back into the dictionary format.
        try:
            cipher = Fernet(secret_key)
            decrypted_bytes = cipher.decrypt(encrypted_token.encode('utf-8'))
            return json.loads(decrypted_bytes.decode('utf-8'))
        except Exception as e:
            print(f"ERROR: Decryption failure: {e}")
            return None
