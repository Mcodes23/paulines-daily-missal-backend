import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured

# ------------------------------------------------------------------
# Django password hashes, with read-only verification of legacy hashes
# ------------------------------------------------------------------

pwd_context = CryptContext(
    schemes=["bcrypt_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return make_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not isinstance(hashed_password, str) or not hashed_password:
        return False

    try:
        if hashed_password.startswith("$bcrypt-sha256$"):
            return pwd_context.verify(plain_password, hashed_password)
        return check_password(plain_password, hashed_password)
    except (ValueError, OverflowError):
        # Reject malformed encodings, including out-of-range work factors.
        return False


# ------------------------------------------------------------------
# JWT helpers
# ------------------------------------------------------------------

def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    }
    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, jti


def decode_token(token: str) -> dict:
    signing_key = settings.JWT_SECRET_KEY
    algorithm = settings.JWT_ALGORITHM
    if not isinstance(signing_key, (str, bytes)) or not signing_key:
        raise ImproperlyConfigured("JWT signing key must be a non-empty string or bytes")
    if not isinstance(algorithm, str) or not algorithm:
        raise ImproperlyConfigured("JWT algorithm must be a non-empty string")

    try:
        return jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
    except (TypeError, OverflowError):
        # PyJWT does not normalize every malformed NumericDate conversion.
        raise jwt.InvalidTokenError("Invalid token timestamp") from None
