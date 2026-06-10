import base64
import hashlib
import os
from datetime import datetime

from cryptography.fernet import Fernet


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_text(plain_text: str, secret: str) -> str:
    fernet = Fernet(_derive_fernet_key(secret))
    token = fernet.encrypt(plain_text.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(cipher_text: str, secret: str) -> str:
    fernet = Fernet(_derive_fernet_key(secret))
    return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")


def utcnow() -> datetime:
    return datetime.utcnow()
