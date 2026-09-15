from cryptography.fernet import Fernet
from config import settings

_fernet = Fernet(settings.FERNET_KEY.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a string value (e.g., NVR password) for storage in DB."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string from the DB."""
    return _fernet.decrypt(ciphertext.encode()).decode()
