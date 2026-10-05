from fastapi import APIRouter, Depends, HTTPException, status

from django.contrib.auth.models import User
from accounts.models import Subscription, SubscriptionPlan
from fastapi_api.core.deps import get_current_user
from fastapi_api.core.standard_response import StandardResponse
from fastapi_api.api.v1.auth.schemas import SubscriptionPlanResponse, SubscriptionStatusResponse

router = APIRouter()


def _get_or_create_subscription(user: User) -> Subscription:
    try:
        return user.subscription
    except Subscription.DoesNotExist:
        return Subscription.objects.create(user=user)


@router.get("/plans")
async def list_plans():
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
async def get_subscription_status(user: User = Depends(get_current_user)):
    """Get the current user's subscription status."""
    sub = _get_or_create_subscription(user)

    data = SubscriptionStatusResponse(
        status=sub.status,
        plan_name=sub.plan.name if sub.plan else None,
        is_active=sub.is_active_or_trial,
        days_remaining=sub.days_remaining,
        trial_end=sub.trial_end.isoformat() if sub.trial_end else None,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
    ).model_dump()

    return StandardResponse.ok(data=data)


@router.post("/activate-trial")
async def activate_trial(user: User = Depends(get_current_user)):
    """Activate a 7-day trial for the current user."""
    sub = _get_or_create_subscription(user)

    if sub.trial_start is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trial has already been used",
        )

    sub.activate_trial(days=7)

    data = SubscriptionStatusResponse(
        status=sub.status,
        plan_name=sub.plan.name if sub.plan else None,
        is_active=sub.is_active_or_trial,
        days_remaining=sub.days_remaining,
        trial_end=sub.trial_end.isoformat() if sub.trial_end else None,
        current_period_end=None,
    ).model_dump()

    return StandardResponse.ok(message="7-day trial activated", data=data)
