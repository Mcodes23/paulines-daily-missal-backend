from fastapi import APIRouter, Depends, HTTPException, status

from django.contrib.auth.models import User
from django.db import transaction
from accounts.models import Subscription, SubscriptionPlan
from fastapi_api.core.database import database_operation
from fastapi_api.core.deps import get_current_user
from fastapi_api.core.standard_response import StandardResponse
from fastapi_api.api.v1.auth.schemas import SubscriptionPlanResponse, SubscriptionStatusResponse

router = APIRouter()


def _lock_user(user: User) -> User:
    try:
        return User.objects.select_for_update().get(pk=user.pk, is_active=True)
    except User.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        ) from None


def _get_or_create_subscription(user: User) -> Subscription:
    with transaction.atomic():
        user = _lock_user(user)
        subscription, _ = Subscription.objects.select_related("plan").get_or_create(user=user)
        return subscription


def _subscription_to_response(subscription: Subscription) -> dict:
    return SubscriptionStatusResponse(
        status=subscription.status,
        plan_name=subscription.plan.name if subscription.plan else None,
        is_active=subscription.is_active_or_trial,
        days_remaining=subscription.days_remaining,
        trial_end=subscription.trial_end.isoformat() if subscription.trial_end else None,
        current_period_end=(
            subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None
        ),
    ).model_dump()


@router.get("/plans")
@database_operation
def list_plans():
    """List all active subscription plans."""
    plans = SubscriptionPlan.objects.filter(is_active=True)
    data = [
        SubscriptionPlanResponse(
            id=str(p.id),
            name=p.name,
            price=float(p.price),
            currency=p.currency,
            duration_days=p.duration_days,
            description=p.description,
        ).model_dump()
        for p in plans
    ]
    return StandardResponse.ok(data=data)


@router.get("/status")
@database_operation
def get_subscription_status(user: User = Depends(get_current_user)):
    """Get the current user's subscription status."""
    sub = _get_or_create_subscription(user)

    return StandardResponse.ok(data=_subscription_to_response(sub))


@router.post("/activate-trial")
@database_operation
def activate_trial(user: User = Depends(get_current_user)):
    """Activate a 7-day trial for the current user."""
    with transaction.atomic():
        user = _lock_user(user)
        sub, _ = Subscription.objects.select_for_update().get_or_create(user=user)

        if sub.trial_start is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trial has already been used",
            )
        if sub.is_active_or_trial:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription is already active",
            )

        sub.activate_trial(days=7)
        return StandardResponse.ok(
            message="7-day trial activated",
            data=_subscription_to_response(sub),
        )
