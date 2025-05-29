from base64 import b64decode
from hashlib import sha256
import hmac
import logging
import jwt
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timedelta
from Crypto.Util.Padding import pad, unpad


class AuthenticationSystem:
    def __init__(self, config):
        self.config = config
        self.public_key = self._load_public_key()

    def _load_public_key(self):
        try:
            with open(self.config["ota"]["public_key"], "rb") as key_file:
                return serialization.load_pem_public_key(key_file.read())
        except Exception as e:
            logging.error(f"Public key load failed: {e}")
            return None

    def validate_user(self, username, password):
        stored_hash = self.config["auth"]["users"].get(username)
        if not stored_hash:
            return False

        computed_hash = sha256(f"{username}:{password}".encode()).hexdigest()
        return hmac.compare_digest(computed_hash, stored_hash)

    def generate_token(self, user):
        return jwt.encode(
            {"user": user, "exp": datetime.now() + timedelta(hours=1)},
            self.config["database"]["encryption_key"],
            algorithm="HS256",
        )

    def verify_token(self, token):
        try:
            payload = jwt.decode(
                token, self.config["database"]["encryption_key"], algorithms=["HS256"]
            )
            return payload["user"]
        except jwt.PyJWTError as e:
            logging.error(f"Token verification failed: {e}")
            return None

    def verify_firmware(self, firmware, signature):
        try:
            self.public_key.verify(
                signature,
                firmware,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logging.error(f"Firmware verification failed: {e}")
            return False
