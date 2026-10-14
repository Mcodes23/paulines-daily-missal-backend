from fastapi import APIRouter, Depends, HTTPException, status

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from accounts.models import UserProfile
from fastapi_api.core.database import database_operation
from fastapi_api.core.deps import ensure_profile, get_current_user
from fastapi_api.core.security import hash_password, verify_password
from fastapi_api.core.standard_response import StandardResponse

from .schemas import ChangePasswordRequest, ProfileUpdateRequest, UserResponse

router = APIRouter()


def _build_response(user: User, profile: UserProfile | None = None) -> dict:
    if profile is None:
        profile = ensure_profile(user)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=profile.phone_number,
        country_code=profile.country_code,
        avatar_url=profile.avatar_url,
        is_email_verified=profile.is_email_verified,
    ).model_dump()


def _lock_account(user: User) -> tuple[User, UserProfile]:
    """Lock the user before its profile inside the caller's transaction."""
    try:
        current_user = User.objects.select_for_update().get(pk=user.pk, is_active=True)
    except User.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        ) from None
    profile, _ = UserProfile.objects.select_for_update().get_or_create(user=current_user)
    return current_user, profile


@router.get("/profile")
@database_operation
def get_profile(user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return StandardResponse.ok(data=_build_response(user))


@router.put("/profile")
@database_operation
def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update the current user's profile."""
    with transaction.atomic():
        user, profile = _lock_account(user)
        user_fields = []
        profile_fields = []

        if body.first_name is not None:
            user.first_name = body.first_name
            user_fields.append("first_name")
        if body.last_name is not None:
            user.last_name = body.last_name
            user_fields.append("last_name")
        if body.phone_number is not None:
            profile.phone_number = body.phone_number
            profile_fields.append("phone_number")
        if body.country_code is not None:
            profile.country_code = body.country_code
            profile_fields.append("country_code")
        if body.avatar_url is not None:
            profile.avatar_url = body.avatar_url
            profile_fields.append("avatar_url")

        if user_fields:
            user.save(update_fields=user_fields)
        if profile_fields:
            profile.save(update_fields=profile_fields)

        return StandardResponse.ok(message="Profile updated", data=_build_response(user, profile))


@router.put("/change-password")
@database_operation
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
):
    """Change the current user's password."""
    with transaction.atomic():
        user, profile = _lock_account(user)
        if not verify_password(body.current_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        try:
            validate_password(body.new_password, user=user)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.messages,
            ) from None

        user.password = hash_password(body.new_password)
        user.save(update_fields=["password"])

        profile.refresh_token_jti = ""
        profile.password_reset_token = ""
        profile.password_reset_expiry = None
        profile.save(
            update_fields=["refresh_token_jti", "password_reset_token", "password_reset_expiry"]
        )

    return StandardResponse.ok(message="Password changed successfully")


@router.delete("/profile")
@database_operation
def delete_account(user: User = Depends(get_current_user)):
    """Deactivate the current user's account."""
    with transaction.atomic():
        user, profile = _lock_account(user)
        user.is_active = False
        user.save(update_fields=["is_active"])

        profile.refresh_token_jti = ""
        profile.save(update_fields=["refresh_token_jti"])

    return StandardResponse.ok(message="Account deactivated successfully")
