import jwt
from asgiref.sync import sync_to_async
from fastapi import APIRouter, Depends, HTTPException, status

from django.contrib.auth.models import User
from accounts.models import UserProfile, Subscription

from fastapi_api.core.deps import ensure_profile, get_current_user
from fastapi_api.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from fastapi_api.core.standard_response import StandardResponse

from .schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResendVerificationRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)

router = APIRouter()

# -------------------------------------------------------------------
# ORM-safe wrappers
# -------------------------------------------------------------------

@sync_to_async
def user_exists(email: str) -> bool:
    return User.objects.filter(email=email).exists()


@sync_to_async
def get_user_by_email(email: str) -> User | None:
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        return None


@sync_to_async
def get_user_by_id(user_id: str) -> User | None:
    try:
        return User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return None


@sync_to_async
def create_user(body: RegisterRequest) -> User:
    user = User.objects.create(
        username=body.email,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    user.password = hash_password(body.password)
    user.save(update_fields=["password"])
    return user


@sync_to_async
def create_profile_and_subscription(user: User, body: RegisterRequest) -> UserProfile:
    profile = UserProfile.objects.create(
        user=user,
        phone_number=body.phone_number,
        country_code=body.country_code,
    )
    Subscription.objects.create(user=user)
    return profile


@sync_to_async
def get_profile_by_verification_token(token: str) -> UserProfile | None:
    try:
        return UserProfile.objects.get(email_verification_token=token)
    except UserProfile.DoesNotExist:
        return None


@sync_to_async
def get_profile_by_reset_token(token: str) -> UserProfile | None:
    try:
        return UserProfile.objects.select_related("user").get(
            password_reset_token=token
        )
    except UserProfile.DoesNotExist:
        return None


# -------------------------------------------------------------------
# Model-method wrappers (THIS IS WHAT WAS MISSING)
# -------------------------------------------------------------------

@sync_to_async
def generate_email_verification_token(profile: UserProfile) -> str:
    return profile.generate_email_verification_token()


@sync_to_async
def verify_email_token(profile: UserProfile, token: str) -> bool:
    return profile.verify_email(token)


@sync_to_async
def generate_password_reset_token(profile: UserProfile) -> str:
    return profile.generate_password_reset_token()


@sync_to_async
def verify_password_reset_token(profile: UserProfile, token: str) -> bool:
    return profile.verify_password_reset_token(token)


@sync_to_async
def ensure_profile_async(user: User) -> UserProfile:
    return ensure_profile(user)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _user_to_response(user: User, profile: UserProfile) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=profile.phone_number,
        country_code=profile.country_code,
        avatar_url=profile.avatar_url,
        is_email_verified=profile.is_email_verified,
    )


@sync_to_async
def _create_token_response(user: User, profile: UserProfile) -> dict:
    access_token = create_access_token(str(user.id))
    refresh_token, jti = create_refresh_token(str(user.id))

    profile.refresh_token_jti = jti
    profile.save(update_fields=["refresh_token_jti"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_to_response(user, profile),
    ).model_dump()


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@router.post("/register")
async def register(body: RegisterRequest):
    if await user_exists(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = await create_user(body)
    profile = await create_profile_and_subscription(user, body)

    verification_token = await generate_email_verification_token(profile)
    token_data = await _create_token_response(user, profile)

    return StandardResponse.ok(
        message="Account created successfully. Please verify your email.",
        data={
            **token_data,
            "verification_token": verification_token,  # REMOVE IN PROD
        },
    )


@router.post("/login")
async def login(body: LoginRequest):
    user = await get_user_by_email(body.email)

    if not user or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    profile = await ensure_profile_async(user)
    token_data = await _create_token_response(user, profile)

    return StandardResponse.ok(message="Login successful", data=token_data)


@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user = await get_user_by_id(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    profile = await ensure_profile_async(user)

    if profile.refresh_token_jti != payload.get("jti"):
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    access_token = create_access_token(str(user.id))

    return StandardResponse.ok(
        message="Token refreshed",
        data={"access_token": access_token, "token_type": "bearer"},
    )


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    profile = await ensure_profile_async(user)
    profile.refresh_token_jti = ""
    await sync_to_async(profile.save)(update_fields=["refresh_token_jti"])

    return StandardResponse.ok(message="Logged out successfully")


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest):
    profile = await get_profile_by_verification_token(body.token)

    if not profile or not await verify_email_token(profile, body.token):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    return StandardResponse.ok(message="Email verified successfully")


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequest):
    user = await get_user_by_email(body.email)

    if not user:
        return StandardResponse.ok(
            message="If the email exists, a verification link has been sent"
        )

    profile = await ensure_profile_async(user)

    if profile.is_email_verified:
        return StandardResponse.ok(message="Email already verified")

    verification_token = await generate_email_verification_token(profile)

    return StandardResponse.ok(
        message="Verification email sent",
        data={"verification_token": verification_token},  # REMOVE IN PROD
    )


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    user = await get_user_by_email(body.email)

    if user:
        profile = await ensure_profile_async(user)
        reset_token = await generate_password_reset_token(profile)

        return StandardResponse.ok(
            message="If the email exists, a reset link has been sent",
            data={"reset_token": reset_token},  # REMOVE IN PROD
        )

    return StandardResponse.ok(
        message="If the email exists, a reset link has been sent"
    )


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    profile = await get_profile_by_reset_token(body.token)

    if not profile or not await verify_password_reset_token(profile, body.token):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = profile.user
    user.password = hash_password(body.new_password)
    await sync_to_async(user.save)(update_fields=["password"])

    profile.password_reset_token = ""
    profile.password_reset_expiry = None
    profile.refresh_token_jti = ""
    await sync_to_async(profile.save)(
        update_fields=[
            "password_reset_token",
            "password_reset_expiry",
            "refresh_token_jti",
        ]
    )

    return StandardResponse.ok(message="Password reset successfully")
