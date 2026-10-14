import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from django.contrib.auth.models import User
from django.db import transaction
from accounts.models import UserProfile
from fastapi_api.core.database import database_operation
from fastapi_api.core.security import decode_token

bearer_scheme = HTTPBearer()


def ensure_profile(user: User) -> UserProfile:
    """Get or create a UserProfile for the given user."""
    with transaction.atomic():
        try:
            current_user = User.objects.select_for_update().get(pk=user.pk, is_active=True)
        except User.DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            ) from None
        profile, _ = UserProfile.objects.get_or_create(user=current_user)
        return profile


@database_operation
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    """Extract and validate the current user from the Bearer token."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    # The built-in Django User uses a signed 32-bit AutoField primary key.
    if (
        not isinstance(user_id, str)
        or not user_id.isascii()
        or not user_id.isdecimal()
        or len(user_id) > 10
        or not 0 < int(user_id) <= 2_147_483_647
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user = User.objects.get(id=int(user_id), is_active=True)
    except User.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Ensure profile exists
    ensure_profile(user)

    return user
