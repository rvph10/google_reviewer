from cryptography.fernet import Fernet
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import get_settings

LINK_MAX_AGE = 30 * 24 * 3600


def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=salt)


def sign(value: int | str, salt: str) -> str:
    return _serializer(salt).dumps(value)


def unsign(token: str, salt: str, max_age: int = LINK_MAX_AGE) -> int | str | None:
    try:
        return _serializer(salt).loads(token, max_age=max_age)
    except BadSignature:
        return None
