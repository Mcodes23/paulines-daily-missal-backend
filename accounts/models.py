import uuid
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """Extended profile for Django's built-in User model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=20, blank=True, default="")
    country_code = models.CharField(max_length=5, default="KE")
    avatar_url = models.URLField(blank=True, default="")

    # Email verification
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=128, blank=True, default="")
    email_verification_expiry = models.DateTimeField(null=True, blank=True)

    # Password reset
    password_reset_token = models.CharField(max_length=128, blank=True, default="")
    password_reset_expiry = models.DateTimeField(null=True, blank=True)

    # Refresh token tracking (for logout/revocation)
    refresh_token_jti = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_user_profile"
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return self.user.email

    def generate_email_verification_token(self):
        self.email_verification_token = secrets.token_urlsafe(48)
        self.email_verification_expiry = timezone.now() + timedelta(hours=24)
        self.save(update_fields=["email_verification_token", "email_verification_expiry"])
        return self.email_verification_token

    def generate_password_reset_token(self):
        self.password_reset_token = secrets.token_urlsafe(48)
        self.password_reset_expiry = timezone.now() + timedelta(hours=1)
        self.save(update_fields=["password_reset_token", "password_reset_expiry"])
        return self.password_reset_token

    def verify_email(self, token: str) -> bool:
        if (
            self.email_verification_token == token
            and self.email_verification_expiry
            and self.email_verification_expiry > timezone.now()
        ):
            self.is_email_verified = True
            self.email_verification_token = ""
            self.email_verification_expiry = None
            self.save(
                update_fields=[
                    "is_email_verified",
                    "email_verification_token",
                    "email_verification_expiry",
                ]
            )
            return True
        return False

    def verify_password_reset_token(self, token: str) -> bool:
        return (
            self.password_reset_token == token
            and self.password_reset_expiry is not None
            and self.password_reset_expiry > timezone.now()
        )


class SubscriptionPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default="KES")
    duration_days = models.IntegerField(help_text="Duration in days. 0 = lifetime.")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_subscription_plan"
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} - {self.currency} {self.price}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TRIAL
    )
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_subscription"

    def __str__(self):
        return f"{self.user.email} - {self.status}"

    @property
    def is_active_or_trial(self) -> bool:
        now = timezone.now()
        if self.status == self.Status.TRIAL and self.trial_end and self.trial_end > now:
            return True
        if (
            self.status == self.Status.ACTIVE
            and self.current_period_end
            and self.current_period_end > now
        ):
            return True
        return False

    @property
    def days_remaining(self) -> int:
        now = timezone.now()
        if self.status == self.Status.TRIAL and self.trial_end:
            return max(0, (self.trial_end - now).days)
        if self.status == self.Status.ACTIVE and self.current_period_end:
            return max(0, (self.current_period_end - now).days)
        return 0

    def activate_trial(self, days: int = 7):
        now = timezone.now()
        self.status = self.Status.TRIAL
        self.trial_start = now
        self.trial_end = now + timedelta(days=days)
        self.save(update_fields=["status", "trial_start", "trial_end", "updated_at"])
