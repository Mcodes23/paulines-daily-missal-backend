import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from accounts.models import UserProfile, Subscription

from fastapi_api.core.database import database_operation
from fastapi_api.core.deps import get_current_user
from fastapi_api.core.security import (
    create_access_token, create_refresh_token, decode_token, hash_password, verify_password,
)
from fastapi_api.core.standard_response import StandardResponse
from .schemas import (
    ForgotPasswordRequest, LoginRequest, RefreshRequest, RegisterRequest,
    ResetPasswordRequest, ResendVerificationRequest, TokenResponse, UserResponse, VerifyEmailRequest,
)

router = APIRouter()


def user_exists(email: str) -> bool:
    return User.objects.filter(email=email).exists()


def get_user_by_email(email: str) -> User | None:
    try:
        return User.objects.get(email=email)
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        return None


def _validate_password(password: str, user: User):
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages) from None


def _user_to_response(user: User, profile: UserProfile) -> UserResponse:
    return UserResponse(
        id=str(user.id), email=user.email, first_name=user.first_name, last_name=user.last_name,
        phone_number=profile.phone_number, country_code=profile.country_code,
        avatar_url=profile.avatar_url, is_email_verified=profile.is_email_verified,
    )


def _create_token_response(user: User, profile: UserProfile) -> dict:
    access_token = create_access_token(str(user.id))
    refresh_token, jti = create_refresh_token(str(user.id))
    profile.refresh_token_jti = jti
    profile.save(update_fields=["refresh_token_jti"])
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=_user_to_response(user, profile)
    ).model_dump()


def _lock_user(user_id: int, active_only: bool = False) -> User:
    filters = {"pk": user_id}
    if active_only:
        filters["is_active"] = True
    try:
        return User.objects.select_for_update().get(**filters)
    except User.DoesNotExist:
        raise HTTPException(status_code=401, detail="User not found") from None


def _lock_profile(user: User) -> UserProfile:
    profile, _ = UserProfile.objects.select_for_update().get_or_create(user=user)
    return profile


def _locked_token_profile(token: str, field: str) -> tuple[User, UserProfile] | None:
    try:
        profile_id, user_id = UserProfile.objects.values_list("pk", "user_id").get(**{field: token})
        user = User.objects.select_for_update().get(pk=user_id)
        profile = UserProfile.objects.select_for_update().get(pk=profile_id, user=user)
    except (UserProfile.DoesNotExist, UserProfile.MultipleObjectsReturned, User.DoesNotExist):
        return None
    return user, profile


@router.post("/register")
@database_operation
def register(body: RegisterRequest):
    if user_exists(body.email):
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    user = User(username=body.email, email=body.email, first_name=body.first_name, last_name=body.last_name)
    _validate_password(body.password, user)
    user.password = hash_password(body.password)
    try:
        with transaction.atomic():
            user.save()
            profile = UserProfile.objects.create(
                user=user, phone_number=body.phone_number, country_code=body.country_code
            )
            Subscription.objects.create(user=user)
            token_data = _create_token_response(user, profile)
            return StandardResponse.ok(message="Account created successfully.", data=token_data)
    except IntegrityError:
        if User.objects.filter(username=body.email).exists() or user_exists(body.email):
            raise HTTPException(status_code=409, detail="A user with this email already exists") from None
        raise


@router.post("/login")
@database_operation
def login(body: LoginRequest):
    candidate = get_user_by_email(body.email)
    if candidate is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    with transaction.atomic():
        user = _lock_user(candidate.pk)
        if not verify_password(body.password, user.password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")
        token_data = _create_token_response(user, _lock_profile(user))
        return StandardResponse.ok(message="Login successful", data=token_data)


@router.post("/refresh")
@database_operation
def refresh_token(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired") from None
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id = payload.get("sub")
    if (
        not isinstance(user_id, str) or not user_id.isascii() or not user_id.isdecimal()
        or len(user_id) > 10 or not 0 < int(user_id) <= 2_147_483_647
    ):
        raise HTTPException(status_code=401, detail="Invalid token payload")
    with transaction.atomic():
        user = _lock_user(int(user_id), active_only=True)
        profile = _lock_profile(user)
        jti = payload.get("jti")
        if not isinstance(jti, str) or not jti or not profile.refresh_token_jti or profile.refresh_token_jti != jti:
            raise HTTPException(status_code=401, detail="Refresh token revoked")
        return StandardResponse.ok(
            message="Token refreshed",
            data={"access_token": create_access_token(str(user.id)), "token_type": "bearer"},
        )


@router.post("/logout")
@database_operation
def logout(user: User = Depends(get_current_user)):
    with transaction.atomic():
        user = _lock_user(user.pk, active_only=True)
        profile = _lock_profile(user)
        profile.refresh_token_jti = ""
        profile.save(update_fields=["refresh_token_jti"])
    return StandardResponse.ok(message="Logged out successfully")


@router.post("/verify-email")
@database_operation
def verify_email(body: VerifyEmailRequest):
    with transaction.atomic():
        account = _locked_token_profile(body.token, "email_verification_token")
        if account is None or not account[1].verify_email(body.token):
            raise HTTPException(status_code=400, detail="Invalid or expired token")
    return StandardResponse.ok(message="Email verified successfully")


def _delivery_unavailable():
    # No private delivery channel exists. Never issue unreachable proof tokens.
    return JSONResponse(
        status_code=503,
        content=StandardResponse.error(message="Email delivery is unavailable").model_dump(),
    )


@router.post("/resend-verification")
def resend_verification(body: ResendVerificationRequest):
    return _delivery_unavailable()


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest):
    return _delivery_unavailable()


@router.post("/reset-password")
@database_operation
def reset_password(body: ResetPasswordRequest):
    with transaction.atomic():
        account = _locked_token_profile(body.token, "password_reset_token")
        if account is None:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        user, profile = account
        if not profile.verify_password_reset_token(body.token):
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        _validate_password(body.new_password, user)
        user.password = hash_password(body.new_password)
        user.save(update_fields=["password"])
        profile.password_reset_token = ""
        profile.password_reset_expiry = None
        profile.refresh_token_jti = ""
        profile.save(update_fields=["password_reset_token", "password_reset_expiry", "refresh_token_jti"])
    return StandardResponse.ok(message="Password reset successfully")
