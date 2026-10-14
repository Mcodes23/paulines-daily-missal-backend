from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, EmailStr, field_validator


def _validate_recovery_token(value: str) -> str:
    if not value.strip():
        raise ValueError("Token must not be empty or whitespace")
    return value


RecoveryToken = Annotated[str, AfterValidator(_validate_recovery_token)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str = ""
    last_name: str = ""
    phone_number: str = ""
    country_code: str = "KE"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: RecoveryToken


class VerifyEmailRequest(BaseModel):
    token: RecoveryToken


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: RecoveryToken
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    phone_number: str
    country_code: str
    avatar_url: str
    is_email_verified: bool

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    country_code: Optional[str] = None
    avatar_url: Optional[str] = None


class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    duration_days: int
    description: str

    class Config:
        from_attributes = True


class SubscriptionStatusResponse(BaseModel):
    status: str
    plan_name: Optional[str] = None
    is_active: bool
    days_remaining: int
    trial_end: Optional[str] = None
    current_period_end: Optional[str] = None


# Resolve forward reference
TokenResponse.model_rebuild()
