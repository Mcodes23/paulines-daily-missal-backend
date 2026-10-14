"""Subscription HTTP regressions using registered, disposable synthetic accounts.

The characterization tests preserve existing model rules. Synthetic Premium is
an approved test fixture, rather than an assertion about real product pricing.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
import os
from threading import Event
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

if settings.SETTINGS_MODULE != "paulines.test_settings":
    raise ImproperlyConfigured("Subscription tests require the disposable test settings.")

from django.contrib.auth.models import User
from django.db.backends.utils import CursorWrapper
from django.test import TransactionTestCase
from fastapi import FastAPI
from fastapi.testclient import TestClient

from accounts.models import Subscription, SubscriptionPlan
from fastapi_api.api.v1.auth import auth, profile
from fastapi_api.api.v1.subscriptions import subscriptions
from fastapi_api.core.exceptions import register_exception_handlers


FROZEN_TIME = datetime(2026, 10, 14, 12, 0, tzinfo=datetime_timezone.utc)
TEST_PASSWORD = "Synthetic-subscription-password-2026!"


def subscription_test_app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth.router, prefix="/v1/auth")
    app.include_router(profile.router, prefix="/v1/auth")
    app.include_router(subscriptions.router, prefix="/v1/subscriptions")
    return app


class SubscriptionFlowTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.assertNotIn("DJANGO_ALLOW_ASYNC_UNSAFE", os.environ)
        self.enterContext(patch("accounts.models.timezone.now", return_value=FROZEN_TIME))
        self.client = self.enterContext(
            TestClient(subscription_test_app(), raise_server_exceptions=False)
        )
        self.free_user, self.free_tokens = self.register_account("synthetic-free@example.org")
        self.premium_user, self.premium_tokens = self.register_account("synthetic-premium@example.org")
        self.free_subscription = Subscription.objects.get(user=self.free_user)
        self.premium_plan = SubscriptionPlan.objects.create(
            name="Synthetic Premium", price=Decimal("10.00"), currency="KES",
            duration_days=30, description="Disposable subscription fixture", is_active=True,
        )
        self.premium_subscription = Subscription.objects.get(user=self.premium_user)
        self.premium_subscription.plan = self.premium_plan
        self.premium_subscription.status = Subscription.Status.ACTIVE
        self.premium_subscription.current_period_start = FROZEN_TIME
        self.premium_subscription.current_period_end = FROZEN_TIME + timedelta(days=30)
        self.premium_subscription.save(
            update_fields=["plan", "status", "current_period_start", "current_period_end"]
        )

    def register_account(self, email):
        response = self.client.post(
            "/v1/auth/register", json={"email": email, "password": TEST_PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        return User.objects.get(email=email), response.json()["data"]

    def bearer(self, tokens):
        return {"Authorization": "Bearer " + tokens["access_token"]}

    def status_response(self, tokens, **params):
        return self.client.get(
            "/v1/subscriptions/status", headers=self.bearer(tokens), params=params
        )

    def assert_status(self, tokens, expected, **params):
        response = self.status_response(tokens, **params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "success": True, "message": "Success", "data": expected, "meta": None,
        })
        return response.json()["data"]

    def free_status(self, **changes):
        expected = {
            "status": "trial", "plan_name": None, "is_active": False,
            "days_remaining": 0, "trial_end": None, "current_period_end": None,
        }
        expected.update(changes)
        return expected

    def premium_status(self, **changes):
        expected = {
            "status": "active", "plan_name": "Synthetic Premium", "is_active": True,
            "days_remaining": 30, "trial_end": None,
            "current_period_end": (FROZEN_TIME + timedelta(days=30)).isoformat(),
        }
        expected.update(changes)
        return expected

    def snapshot(self, subscription):
        subscription.refresh_from_db()
        return {
            "status": subscription.status, "plan_id": subscription.plan_id,
            "trial_start": subscription.trial_start, "trial_end": subscription.trial_end,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
        }

    def test_registered_free_account_has_no_plan_or_activated_trial(self):
        self.assert_status(self.free_tokens, self.free_status())
        self.assertEqual(self.snapshot(self.free_subscription), {
            "status": Subscription.Status.TRIAL, "plan_id": None,
            "trial_start": None, "trial_end": None,
            "current_period_start": None, "current_period_end": None,
        })

    def test_synthetic_premium_fixture_has_exact_paid_period_and_status(self):
        self.assert_status(self.premium_tokens, self.premium_status())
        self.assertEqual(self.snapshot(self.premium_subscription), {
            "status": Subscription.Status.ACTIVE, "plan_id": self.premium_plan.pk,
            "trial_start": None, "trial_end": None,
            "current_period_start": FROZEN_TIME,
            "current_period_end": FROZEN_TIME + timedelta(days=30),
        })
        self.assertEqual(self.premium_plan.price, Decimal("10.00"))
        self.assertEqual(self.premium_plan.currency, "KES")
        self.assertEqual(self.premium_plan.duration_days, 30)

    def test_public_plan_listing_excludes_inactive_plans(self):
        SubscriptionPlan.objects.create(
            name="Synthetic Inactive", price=Decimal("1.00"), currency="KES",
            duration_days=30, is_active=False,
        )
        response = self.client.get("/v1/subscriptions/plans")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "success": True, "message": "Success", "meta": None,
            "data": [{
                "id": str(self.premium_plan.pk), "name": "Synthetic Premium", "price": 10.0,
                "currency": "KES", "duration_days": 30,
                "description": "Disposable subscription fixture",
            }],
        })

    def test_query_parameters_cannot_select_or_change_another_users_subscription(self):
        premium_before = self.snapshot(self.premium_subscription)
        targets = {
            "user_id": str(self.premium_user.pk), "user": str(self.premium_user.pk),
            "subscription_id": str(self.premium_subscription.pk),
            "email": self.premium_user.email,
        }
        self.assert_status(self.free_tokens, self.free_status(), **targets)
        response = self.client.post(
            "/v1/subscriptions/activate-trial", headers=self.bearer(self.free_tokens), params=targets,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.snapshot(self.premium_subscription), premium_before)
        self.assert_status(self.premium_tokens, self.premium_status())
        self.assertEqual(self.snapshot(self.free_subscription)["trial_start"], FROZEN_TIME)

    def test_refresh_and_logout_keep_free_and_premium_accounts_separate(self):
        free_before = self.snapshot(self.free_subscription)
        premium_before = self.snapshot(self.premium_subscription)
        refreshed_free = self.client.post(
            "/v1/auth/refresh", json={"refresh_token": self.free_tokens["refresh_token"]}
        )
        self.assertEqual(refreshed_free.status_code, 200)
        free_access = refreshed_free.json()["data"]["access_token"]
        self.assert_status({"access_token": free_access}, self.free_status())
        self.assert_status(self.premium_tokens, self.premium_status())
        logout = self.client.post("/v1/auth/logout", headers=self.bearer({"access_token": free_access}))
        self.assertEqual(logout.status_code, 200)
        denied_free = self.client.post(
            "/v1/auth/refresh", json={"refresh_token": self.free_tokens["refresh_token"]}
        )
        self.assertEqual(denied_free.status_code, 401)
        refreshed_premium = self.client.post(
            "/v1/auth/refresh", json={"refresh_token": self.premium_tokens["refresh_token"]}
        )
        self.assertEqual(refreshed_premium.status_code, 200)
        premium_access = refreshed_premium.json()["data"]["access_token"]
        self.assert_status({"access_token": premium_access}, self.premium_status())
        self.assertEqual(self.snapshot(self.free_subscription), free_before)
        self.assertEqual(self.snapshot(self.premium_subscription), premium_before)

    def test_protected_subscription_routes_reject_missing_or_invalid_credentials(self):
        before = self.snapshot(self.free_subscription)
        for method, path in (("get", "/status"), ("post", "/activate-trial")):
            with self.subTest(endpoint=path):
                request = getattr(self.client, method)
                self.assertEqual(request("/v1/subscriptions" + path).status_code, 403)
                invalid = request(
                    "/v1/subscriptions" + path,
                    headers={"Authorization": "Bearer synthetic-invalid-jwt"},
                )
                self.assertEqual(invalid.status_code, 401)
        self.assertEqual(self.snapshot(self.free_subscription), before)
        self.assertNotIn("DJANGO_ALLOW_ASYNC_UNSAFE", os.environ)

    def test_inactive_account_is_denied_login_and_subscription_status(self):
        before = self.snapshot(self.premium_subscription)
        self.premium_user.is_active = False
        self.premium_user.save(update_fields=["is_active"])
        denied_login = self.client.post(
            "/v1/auth/login", json={"email": self.premium_user.email, "password": TEST_PASSWORD}
        )
        self.assertEqual(denied_login.status_code, 403)
        self.assertEqual(self.status_response(self.premium_tokens).status_code, 401)
        denied_trial = self.client.post(
            "/v1/subscriptions/activate-trial", headers=self.bearer(self.premium_tokens)
        )
        self.assertEqual(denied_trial.status_code, 401)
        self.assertEqual(self.snapshot(self.premium_subscription), before)
        self.assert_status(self.free_tokens, self.free_status())

    def test_paid_expiry_uses_strict_future_end_and_floors_days_remaining(self):
        cases = (
            (timedelta(seconds=-1), False, 0),
            (timedelta(), False, 0),
            (timedelta(days=1, seconds=-1), True, 0),
            (timedelta(days=1), True, 1),
            (timedelta(days=2, seconds=-1), True, 1),
        )
        for offset, is_active, days_remaining in cases:
            with self.subTest(offset_seconds=offset.total_seconds()):
                end = FROZEN_TIME + offset
                self.premium_subscription.current_period_end = end
                self.premium_subscription.save(update_fields=["current_period_end"])
                before = self.snapshot(self.premium_subscription)
                self.assert_status(self.premium_tokens, self.premium_status(
                    current_period_end=end.isoformat(), is_active=is_active,
                    days_remaining=days_remaining,
                ))
                self.assertEqual(self.snapshot(self.premium_subscription), before)

    def test_trial_expiry_uses_strict_future_end_and_floors_days_remaining(self):
        cases = (
            (timedelta(seconds=-1), False, 0),
            (timedelta(), False, 0),
            (timedelta(days=1, seconds=-1), True, 0),
            (timedelta(days=1), True, 1),
        )
        for offset, is_active, days_remaining in cases:
            with self.subTest(offset_seconds=offset.total_seconds()):
                end = FROZEN_TIME + offset
                self.free_subscription.trial_start = FROZEN_TIME - timedelta(days=7)
                self.free_subscription.trial_end = end
                self.free_subscription.save(update_fields=["trial_start", "trial_end"])
                before = self.snapshot(self.free_subscription)
                self.assert_status(self.free_tokens, self.free_status(
                    trial_end=end.isoformat(), is_active=is_active, days_remaining=days_remaining,
                ))
                self.assertEqual(self.snapshot(self.free_subscription), before)

    def test_lifetime_label_without_period_end_is_currently_inactive(self):
        # Characterization: duration_days=0 does not itself grant active access.
        self.premium_plan.duration_days = 0
        self.premium_plan.save(update_fields=["duration_days"])
        self.premium_subscription.current_period_end = None
        self.premium_subscription.save(update_fields=["current_period_end"])
        self.assert_status(self.premium_tokens, self.premium_status(
            current_period_end=None, is_active=False, days_remaining=0,
        ))

    def test_future_period_start_does_not_currently_delay_active_status(self):
        # Characterization: existing eligibility uses the end, not the start.
        self.premium_subscription.current_period_start = FROZEN_TIME + timedelta(days=5)
        self.premium_subscription.save(update_fields=["current_period_start"])
        self.assert_status(self.premium_tokens, self.premium_status())

    def test_inactive_plan_does_not_currently_revoke_a_paid_period(self):
        # Characterization: plan availability and an existing period are distinct.
        self.premium_plan.is_active = False
        self.premium_plan.save(update_fields=["is_active"])
        self.assert_status(self.premium_tokens, self.premium_status())
        public = self.client.get("/v1/subscriptions/plans")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()["data"], [])

    def test_first_trial_activation_returns_and_stores_seven_days_and_repeat_is_rejected(self):
        response = self.client.post(
            "/v1/subscriptions/activate-trial", headers=self.bearer(self.free_tokens)
        )
        self.assertEqual(response.status_code, 200)
        expected = self.free_status(
            is_active=True, days_remaining=7,
            trial_end=(FROZEN_TIME + timedelta(days=7)).isoformat(),
        )
        self.assertEqual(response.json(), {
            "success": True, "message": "7-day trial activated", "data": expected, "meta": None,
        })
        before = self.snapshot(self.free_subscription)
        self.assertEqual(before["trial_start"], FROZEN_TIME)
        self.assertEqual(before["trial_end"], FROZEN_TIME + timedelta(days=7))
        self.assertIsNone(before["plan_id"])
        self.assertIsNone(before["current_period_start"])
        self.assertIsNone(before["current_period_end"])
        repeated = self.client.post(
            "/v1/subscriptions/activate-trial", headers=self.bearer(self.free_tokens)
        )
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(self.snapshot(self.free_subscription), before)
        self.assert_status(self.free_tokens, expected)

    def test_expired_trial_cannot_be_started_again(self):
        self.free_subscription.trial_start = FROZEN_TIME - timedelta(days=8)
        self.free_subscription.trial_end = FROZEN_TIME - timedelta(days=1)
        self.free_subscription.save(update_fields=["trial_start", "trial_end"])
        before = self.snapshot(self.free_subscription)
        repeated = self.client.post(
            "/v1/subscriptions/activate-trial", headers=self.bearer(self.free_tokens)
        )
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(self.snapshot(self.free_subscription), before)
        self.assert_status(self.free_tokens, self.free_status(
            trial_end=(FROZEN_TIME - timedelta(days=1)).isoformat(),
        ))

    def test_active_premium_trial_request_cannot_overwrite_paid_periods(self):
        before = self.snapshot(self.premium_subscription)
        reported_before = self.assert_status(self.premium_tokens, self.premium_status())
        rejected = self.client.post(
            "/v1/subscriptions/activate-trial", headers=self.bearer(self.premium_tokens)
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(self.snapshot(self.premium_subscription), before)
        reported_after = self.assert_status(self.premium_tokens, self.premium_status())
        self.assertEqual(reported_after, reported_before)

    def test_simultaneous_trial_requests_activate_only_once(self):
        first_save = Event()
        release_first_trial = Event()
        second_lock_attempt = Event()
        original_save = Subscription.save
        original_execute = CursorWrapper.execute

        def pause_trial_save(instance, *args, **kwargs):
            if instance.user_id == self.free_user.pk and "trial_start" in (kwargs.get("update_fields") or ()):
                first_save.set()
                if not release_first_trial.wait(timeout=10):
                    raise RuntimeError("synthetic concurrent trial timeout")
            return original_save(instance, *args, **kwargs)

        def observe_second_user_lock(cursor, sql, params=None):
            if first_save.is_set() and "FOR UPDATE" in sql.upper() and User._meta.db_table in sql:
                second_lock_attempt.set()
            return original_execute(cursor, sql, params)

        def activate_through_http():
            with TestClient(subscription_test_app(), raise_server_exceptions=False) as client:
                return client.post(
                    "/v1/subscriptions/activate-trial", headers=self.bearer(self.free_tokens)
                )

        with (
            patch.object(Subscription, "save", pause_trial_save),
            patch.object(CursorWrapper, "execute", observe_second_user_lock),
            ThreadPoolExecutor(max_workers=2) as workers,
        ):
            first = workers.submit(activate_through_http)
            second = None
            try:
                self.assertTrue(first_save.wait(timeout=10))
                second = workers.submit(activate_through_http)
                self.assertTrue(second_lock_attempt.wait(timeout=10))
                with self.assertRaises(FutureTimeout):
                    second.result(timeout=0.2)
            finally:
                release_first_trial.set()
            replies = [first.result(timeout=10), second.result(timeout=10)]
        self.assertEqual(sorted(reply.status_code for reply in replies), [200, 400])
        stored = self.snapshot(self.free_subscription)
        self.assertEqual(stored["trial_start"], FROZEN_TIME)
        self.assertEqual(stored["trial_end"], FROZEN_TIME + timedelta(days=7))
        self.assert_status(self.free_tokens, self.free_status(
            is_active=True, days_remaining=7,
            trial_end=(FROZEN_TIME + timedelta(days=7)).isoformat(),
        ))
