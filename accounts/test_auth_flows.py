"""Authentication regressions against the explicitly disposable PostgreSQL database.

Run through scripts/run_auth_tests.py. The test app deliberately avoids importing
the production application, settings, admin, or external readings service.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import timedelta
import os
from threading import Event, Lock
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

if settings.SETTINGS_MODULE != "paulines.test_settings":
    raise ImproperlyConfigured("Authentication tests require the disposable test settings.")

from django.contrib.auth.hashers import check_password, identify_hasher
from django.contrib.auth.models import User
from django.db import transaction
from django.db.backends.utils import CursorWrapper
from django.test import TransactionTestCase
from django.utils import timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt
from passlib.hash import bcrypt_sha256

from accounts.models import Subscription, UserProfile
from fastapi_api.api.v1.auth import auth, profile
from fastapi_api.core.exceptions import register_exception_handlers
from fastapi_api.api.v1.auth.schemas import RegisterRequest


# These credentials and proofs belong exclusively to disposable test records.
TEST_PASSWORD = "Synthetic-test-password-2026!"
NEW_PASSWORD = "Replacement-test-password-2026!"
RESET_PROOF = "synthetic-reset-proof-for-owned-test-record"


def authentication_test_app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth.router, prefix="/v1/auth")
    app.include_router(profile.router, prefix="/v1/auth")
    return app


class AuthenticationFlowTests(TransactionTestCase):
    """Use real ORM transactions and HTTP dependency/validation execution."""

    def setUp(self):
        super().setUp()
        self.assertNotIn("DJANGO_ALLOW_ASYNC_UNSAFE", os.environ)
        self.client = self.enterContext(
            TestClient(authentication_test_app(), raise_server_exceptions=False)
        )

    def create_account(self, email="synthetic-user@example.org", password=TEST_PASSWORD):
        user = User.objects.create_user(username=email, email=email, password=password)
        account_profile = UserProfile.objects.create(user=user)
        return user, account_profile

    def registration_body(self, email="synthetic-registration@example.org"):
        return {"email": email, "password": TEST_PASSWORD, "first_name": "Synthetic"}

    def login(self, user, password=TEST_PASSWORD):
        response = self.client.post(
            "/v1/auth/login", json={"email": user.email, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def bearer(self, access_token):
        return {"Authorization": "Bearer " + access_token}

    def assign_reset_proof(self, account_profile, *, expired=False):
        account_profile.password_reset_token = RESET_PROOF
        account_profile.password_reset_expiry = timezone.now() + timedelta(
            hours=-1 if expired else 1
        )
        account_profile.refresh_token_jti = "synthetic-active-session"
        account_profile.save(
            update_fields=["password_reset_token", "password_reset_expiry", "refresh_token_jti"]
        )

    def signed_token(self, **overrides):
        now = timezone.now()
        payload = {
            "sub": "999999",
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        payload.update(overrides)
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def test_registration_creates_django_compatible_bundle_without_verification_proof(self):
        with patch.object(
            UserProfile, "generate_email_verification_token", side_effect=AssertionError("unexpected proof generation")
        ) as generation:
            response = self.client.post("/v1/auth/register", json=self.registration_body())
        self.assertEqual(response.status_code, 200)
        generation.assert_not_called()
        data = response.json()["data"]
        self.assertTrue({"access_token", "refresh_token", "user"}.issubset(data))
        self.assertNotIn("verification_token", data)
        self.assertNotIn("reset_token", data)
        user = User.objects.get(email=self.registration_body()["email"])
        identify_hasher(user.password)
        self.assertTrue(check_password(TEST_PASSWORD, user.password))
        self.assertTrue(user.check_password(TEST_PASSWORD))
        account_profile = UserProfile.objects.get(user=user)
        self.assertFalse(account_profile.is_email_verified)
        self.assertEqual(account_profile.email_verification_token, "")
        self.assertIsNone(account_profile.email_verification_expiry)
        self.assertTrue(bool(account_profile.refresh_token_jti))
        self.assertEqual(Subscription.objects.filter(user=user).count(), 1)

    def test_registration_failure_rolls_back_user_profile_and_subscription(self):
        before = (User.objects.count(), UserProfile.objects.count(), Subscription.objects.count())
        with patch.object(
            Subscription.objects, "create", side_effect=RuntimeError("synthetic-database-failure")
        ):
            response = self.client.post("/v1/auth/register", json=self.registration_body())
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("synthetic-database-failure", response.text)
        self.assertEqual(
            (User.objects.count(), UserProfile.objects.count(), Subscription.objects.count()), before
        )

    def test_duplicate_registration_is_conflict_and_does_not_create_partial_records(self):
        first = self.client.post("/v1/auth/register", json=self.registration_body())
        self.assertEqual(first.status_code, 200)
        before = (User.objects.count(), UserProfile.objects.count(), Subscription.objects.count())
        duplicate = self.client.post("/v1/auth/register", json=self.registration_body())
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(
            (User.objects.count(), UserProfile.objects.count(), Subscription.objects.count()), before
        )

    def test_django_created_user_can_log_in(self):
        user, account_profile = self.create_account()
        data = self.login(user)
        self.assertEqual(data["user"]["id"], str(user.pk))
        account_profile.refresh_from_db()
        self.assertTrue(bool(account_profile.refresh_token_jti))

    def test_legacy_passlib_password_can_log_in_without_rewriting_the_hash(self):
        user, _ = self.create_account()
        legacy_hash = bcrypt_sha256.using(rounds=4).hash(TEST_PASSWORD)
        user.password = legacy_hash
        user.save(update_fields=["password"])
        self.login(user)
        user.refresh_from_db()
        self.assertTrue(user.password == legacy_hash)

    def test_wrong_password_unknown_account_and_corrupt_hashes_return_401(self):
        user, _ = self.create_account()
        for email, password in (
            (user.email, "Synthetic-wrong-password!"),
            ("synthetic-missing@example.org", TEST_PASSWORD),
        ):
            with self.subTest(case="wrong password" if email == user.email else "missing account"):
                response = self.client.post("/v1/auth/login", json={"email": email, "password": password})
                self.assertEqual(response.status_code, 401)
        for index, corrupt_hash in enumerate((
            "not-a-hash", "pbkdf2_sha256$invalid$salt$bad", "$bcrypt-sha256$invalid", "!",
            "pbkdf2_sha256$18446744073709551616$salt$bad",
        )):
            with self.subTest(corrupt_hash_case=index):
                user.password = corrupt_hash
                user.save(update_fields=["password"])
                response = self.client.post("/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
                self.assertEqual(response.status_code, 401)
                user.refresh_from_db()
                self.assertTrue(user.password == corrupt_hash)

    def test_protected_profile_reads_and_updates_without_async_unsafe_override(self):
        user, _ = self.create_account()
        data = self.login(user)
        headers = self.bearer(data["access_token"])
        response = self.client.get("/v1/auth/profile", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], str(user.pk))
        updated = self.client.put(
            "/v1/auth/profile", headers=headers,
            json={"first_name": "Updated Synthetic", "phone_number": "synthetic-phone"},
        )
        self.assertEqual(updated.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated Synthetic")
        self.assertEqual(UserProfile.objects.get(user=user).phone_number, "synthetic-phone")
        self.assertNotIn("DJANGO_ALLOW_ASYNC_UNSAFE", os.environ)

    def test_invalid_expired_and_missing_expiry_access_tokens_return_401(self):
        user, _ = self.create_account()
        now = timezone.now()
        missing_expiry = jwt.encode(
            {"sub": str(user.pk), "type": "access", "iat": now},
            settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
        )
        tokens = (
            "synthetic-not-a-jwt",
            missing_expiry,
            self.signed_token(sub=str(user.pk), exp=now - timedelta(seconds=1)),
            self.signed_token(sub="not-an-integer"),
            self.signed_token(sub=""),
            self.signed_token(sub=str(user.pk), exp=[]),
            self.signed_token(sub=str(user.pk), iat=None),
            self.signed_token(sub=str(user.pk), exp=float("inf")),
        )
        for index, token in enumerate(tokens):
            with self.subTest(token_case=index):
                response = self.client.get("/v1/auth/profile", headers=self.bearer(token))
                self.assertEqual(response.status_code, 401)

    def test_refresh_rejects_malformed_missing_expiry_and_missing_jti_tokens(self):
        user, _ = self.create_account()
        data = self.login(user)
        now = timezone.now()
        missing_expiry = jwt.encode(
            {"sub": str(user.pk), "type": "refresh", "iat": now, "jti": "synthetic-jti"},
            settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
        )
        tokens = (
            "synthetic-not-a-jwt", missing_expiry,
            self.signed_token(sub=str(user.pk), type="refresh"),
            self.signed_token(sub=str(user.pk), type="refresh", jti=""),
            data["access_token"],
        )
        for index, token in enumerate(tokens):
            with self.subTest(token_case=index):
                response = self.client.post("/v1/auth/refresh", json={"refresh_token": token})
                self.assertEqual(response.status_code, 401)
        rejected_access = self.client.get("/v1/auth/profile", headers=self.bearer(data["refresh_token"]))
        self.assertEqual(rejected_access.status_code, 401)

    def test_refresh_succeeds_then_logout_revokes_the_refresh_session(self):
        user, account_profile = self.create_account()
        data = self.login(user)
        refresh = self.client.post("/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
        self.assertEqual(refresh.status_code, 200)
        access = refresh.json()["data"]["access_token"]
        self.assertEqual(self.client.get("/v1/auth/profile", headers=self.bearer(access)).status_code, 200)
        logged_out = self.client.post("/v1/auth/logout", headers=self.bearer(access))
        self.assertEqual(logged_out.status_code, 200)
        account_profile.refresh_from_db()
        self.assertEqual(account_profile.refresh_token_jti, "")
        denied = self.client.post("/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
        self.assertEqual(denied.status_code, 401)

    def test_deactivated_account_cannot_use_existing_tokens_or_log_in(self):
        user, account_profile = self.create_account()
        data = self.login(user)
        deleted = self.client.delete("/v1/auth/profile", headers=self.bearer(data["access_token"]))
        self.assertEqual(deleted.status_code, 200)
        user.refresh_from_db()
        account_profile.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(account_profile.refresh_token_jti, "")
        self.assertEqual(self.client.get("/v1/auth/profile", headers=self.bearer(data["access_token"])).status_code, 401)
        self.assertEqual(self.client.post("/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}).status_code, 401)
        denied_login = self.client.post("/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        self.assertEqual(denied_login.status_code, 403)

    def test_profile_and_password_changes_do_not_affect_another_account(self):
        user_a, profile_a = self.create_account("synthetic-a@example.org")
        user_b, profile_b = self.create_account("synthetic-b@example.org")
        tokens_a, tokens_b = self.login(user_a), self.login(user_b)
        original_b_hash = user_b.password
        profile_b.refresh_from_db()
        original_b_jti = profile_b.refresh_token_jti
        updated = self.client.put(
            "/v1/auth/profile", headers=self.bearer(tokens_a["access_token"]),
            json={"first_name": "Account A Only", "phone_number": "synthetic-a-phone"},
        )
        self.assertEqual(updated.status_code, 200)
        changed = self.client.put(
            "/v1/auth/change-password", headers=self.bearer(tokens_a["access_token"]),
            json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
        )
        self.assertEqual(changed.status_code, 200)
        user_a.refresh_from_db()
        user_b.refresh_from_db()
        profile_a.refresh_from_db()
        profile_b.refresh_from_db()
        self.assertTrue(user_a.check_password(NEW_PASSWORD))
        self.assertEqual(profile_a.refresh_token_jti, "")
        self.assertEqual(user_b.first_name, "")
        self.assertEqual(profile_b.phone_number, "")
        self.assertTrue(user_b.password == original_b_hash)
        self.assertTrue(profile_b.refresh_token_jti == original_b_jti)
        self.assertEqual(self.client.post("/v1/auth/refresh", json={"refresh_token": tokens_b["refresh_token"]}).status_code, 200)

    def test_recovery_requests_are_uniformly_unavailable_before_lookup_or_proof_generation(self):
        unverified, unverified_profile = self.create_account("synthetic-unverified@example.org")
        verified, verified_profile = self.create_account("synthetic-verified@example.org")
        verified_profile.is_email_verified = True
        verified_profile.save(update_fields=["is_email_verified"])
        emails = (unverified.email, verified.email, "synthetic-missing@example.org")
        with (
            patch.object(User.objects, "get", side_effect=AssertionError("unexpected account lookup")) as get_user,
            patch.object(User.objects, "filter", side_effect=AssertionError("unexpected account lookup")) as filter_user,
            patch.object(UserProfile, "generate_email_verification_token", side_effect=AssertionError("unexpected proof generation")) as verification,
            patch.object(UserProfile, "generate_password_reset_token", side_effect=AssertionError("unexpected proof generation")) as reset,
        ):
            for endpoint in ("/forgot-password", "/resend-verification"):
                endpoint_replies = []
                for index, email in enumerate(emails):
                    with self.subTest(endpoint=endpoint, account_case=index):
                        response = self.client.post("/v1/auth" + endpoint, json={"email": email})
                        self.assertEqual(response.status_code, 503)
                        body = response.json()
                        self.assertFalse(body["success"])
                        self.assertNotIn("verification_token", body)
                        self.assertNotIn("reset_token", body)
                        endpoint_replies.append(body)
                self.assertTrue(all(body == endpoint_replies[0] for body in endpoint_replies))
            get_user.assert_not_called()
            filter_user.assert_not_called()
            verification.assert_not_called()
            reset.assert_not_called()
        for account_profile in (unverified_profile, verified_profile):
            account_profile.refresh_from_db()
            self.assertEqual(account_profile.email_verification_token, "")
            self.assertEqual(account_profile.password_reset_token, "")

    def test_blank_or_whitespace_proofs_and_refresh_tokens_are_validation_errors(self):
        for value in ("", " ", "\n\t"):
            for path, payload in (
                ("/verify-email", {"token": value}),
                ("/reset-password", {"token": value, "new_password": NEW_PASSWORD}),
                ("/refresh", {"refresh_token": value}),
            ):
                with self.subTest(endpoint=path, blank_case=repr(value)):
                    response = self.client.post("/v1/auth" + path, json=payload)
                    self.assertEqual(response.status_code, 422)

    def test_password_reset_changes_password_revokes_refresh_and_consumes_proof_once(self):
        user, account_profile = self.create_account()
        self.assign_reset_proof(account_profile)
        response = self.client.post("/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        account_profile.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertFalse(user.check_password(TEST_PASSWORD))
        self.assertEqual(account_profile.password_reset_token, "")
        self.assertIsNone(account_profile.password_reset_expiry)
        self.assertEqual(account_profile.refresh_token_jti, "")
        reused = self.client.post("/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": TEST_PASSWORD})
        self.assertEqual(reused.status_code, 400)
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))

    def test_expired_reset_proof_does_not_change_password_or_session(self):
        user, account_profile = self.create_account()
        self.assign_reset_proof(account_profile, expired=True)
        original_hash = user.password
        response = self.client.post("/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        account_profile.refresh_from_db()
        self.assertTrue(user.password == original_hash)
        self.assertEqual(account_profile.password_reset_token, RESET_PROOF)
        self.assertEqual(account_profile.refresh_token_jti, "synthetic-active-session")

    def test_profile_save_failure_rolls_back_password_reset_and_keeps_proof_usable(self):
        user, account_profile = self.create_account()
        self.assign_reset_proof(account_profile)
        original_hash = user.password
        original_expiry = account_profile.password_reset_expiry
        with patch.object(UserProfile, "save", side_effect=RuntimeError("synthetic-database-failure")):
            response = self.client.post("/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("synthetic-database-failure", response.text)
        user.refresh_from_db()
        account_profile.refresh_from_db()
        self.assertTrue(user.password == original_hash)
        self.assertEqual(account_profile.password_reset_token, RESET_PROOF)
        self.assertEqual(account_profile.password_reset_expiry, original_expiry)
        self.assertEqual(account_profile.refresh_token_jti, "synthetic-active-session")
        retry = self.client.post("/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": NEW_PASSWORD})
        self.assertEqual(retry.status_code, 200)

    def test_database_operation_preserves_the_callers_transaction(self):
        body = self.registration_body("synthetic-outer-transaction@example.org")
        with transaction.atomic():
            auth.register(RegisterRequest(**body))
            self.assertTrue(User.objects.filter(email=body["email"]).exists())
            transaction.set_rollback(True)
        self.assertFalse(User.objects.filter(email=body["email"]).exists())
        self.assertEqual(UserProfile.objects.count(), 0)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_email_verification_consumes_an_owned_proof_once(self):
        user, account_profile = self.create_account()
        proof = account_profile.generate_email_verification_token()
        verified = self.client.post("/v1/auth/verify-email", json={"token": proof})
        self.assertEqual(verified.status_code, 200)
        self.assertFalse(proof in verified.text)
        account_profile.refresh_from_db()
        self.assertTrue(account_profile.is_email_verified)
        self.assertEqual(account_profile.email_verification_token, "")
        self.assertIsNone(account_profile.email_verification_expiry)
        self.assertEqual(self.client.post("/v1/auth/verify-email", json={"token": proof}).status_code, 400)

    def test_unknown_and_exact_expiry_proofs_do_not_change_account_state(self):
        user, account_profile = self.create_account()
        self.assign_reset_proof(account_profile)
        now = timezone.now()
        account_profile.email_verification_token = "synthetic-verification-proof"
        for expiry in (None, now, now - timedelta(seconds=1)):
            account_profile.email_verification_expiry = expiry
            account_profile.password_reset_expiry = expiry
            account_profile.save(update_fields=[
                "email_verification_token", "email_verification_expiry", "password_reset_expiry"
            ])
            with patch("accounts.models.timezone.now", return_value=now):
                self.assertEqual(self.client.post(
                    "/v1/auth/verify-email", json={"token": account_profile.email_verification_token}
                ).status_code, 400)
                self.assertEqual(self.client.post(
                    "/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": NEW_PASSWORD}
                ).status_code, 400)
        self.assertEqual(self.client.post("/v1/auth/verify-email", json={"token": RESET_PROOF}).status_code, 400)
        self.assertEqual(self.client.post(
            "/v1/auth/reset-password", json={"token": "synthetic-unknown", "new_password": NEW_PASSWORD}
        ).status_code, 400)
        account_profile.refresh_from_db()
        user.refresh_from_db()
        self.assertFalse(account_profile.is_email_verified)
        self.assertTrue(user.check_password(TEST_PASSWORD))

    def test_ambiguous_email_identity_is_rejected_without_creating_a_profile(self):
        email = "synthetic-ambiguous@example.org"
        for username in ("synthetic-one", "synthetic-two"):
            User.objects.create_user(username=username, email=email, password=TEST_PASSWORD)
        response = self.client.post("/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(UserProfile.objects.count(), 0)

    def test_password_change_invalidates_existing_reset_proofs(self):
        user, account_profile = self.create_account()
        self.assign_reset_proof(account_profile)
        data = self.login(user)
        response = self.client.put(
            "/v1/auth/change-password", headers=self.bearer(data["access_token"]),
            json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        account_profile.refresh_from_db()
        self.assertEqual(account_profile.password_reset_token, "")
        self.assertIsNone(account_profile.password_reset_expiry)
        self.assertEqual(self.client.post(
            "/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": TEST_PASSWORD}
        ).status_code, 400)

    def test_registration_token_creation_failure_rolls_back_the_entire_bundle(self):
        with patch.object(auth, "create_refresh_token", side_effect=RuntimeError("synthetic-token-failure")):
            response = self.client.post("/v1/auth/register", json=self.registration_body())
        self.assertEqual(response.status_code, 500)
        self.assertFalse("synthetic-token-failure" in response.text)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(UserProfile.objects.count(), 0)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_simultaneous_resets_cannot_consume_the_same_proof_twice(self):
        user, account_profile = self.create_account()
        self.assign_reset_proof(account_profile)
        first_password_save = Event()
        release_first_reset = Event()
        second_lock_attempt = Event()
        lock_count_guard = Lock()
        user_lock_count = 0
        original_save = User.save
        original_execute = CursorWrapper.execute

        def pause_first_password_save(instance, *args, **kwargs):
            if instance.pk == user.pk and "password" in (kwargs.get("update_fields") or ()):
                first_password_save.set()
                if not release_first_reset.wait(timeout=10):
                    raise RuntimeError("synthetic concurrent reset timeout")
            return original_save(instance, *args, **kwargs)

        def observe_user_lock(cursor, sql, params=None):
            nonlocal user_lock_count
            if "FOR UPDATE" in sql.upper() and User._meta.db_table in sql:
                with lock_count_guard:
                    user_lock_count += 1
                    if user_lock_count == 2:
                        second_lock_attempt.set()
            return original_execute(cursor, sql, params)

        def reset_through_http():
            with TestClient(authentication_test_app(), raise_server_exceptions=False) as client:
                return client.post("/v1/auth/reset-password", json={"token": RESET_PROOF, "new_password": NEW_PASSWORD})

        with (
            patch.object(User, "save", pause_first_password_save),
            patch.object(CursorWrapper, "execute", observe_user_lock),
            ThreadPoolExecutor(max_workers=2) as workers,
        ):
            first = workers.submit(reset_through_http)
            second = None
            try:
                self.assertTrue(first_password_save.wait(timeout=10))
                second = workers.submit(reset_through_http)
                self.assertTrue(second_lock_attempt.wait(timeout=10))
                with self.assertRaises(FutureTimeout):
                    second.result(timeout=0.2)
            finally:
                release_first_reset.set()
            responses = [first.result(timeout=10), second.result(timeout=10)]
        self.assertEqual(sorted(response.status_code for response in responses), [200, 400])
        user.refresh_from_db()
        account_profile.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertEqual(account_profile.password_reset_token, "")
        self.assertIsNone(account_profile.password_reset_expiry)
        self.assertEqual(account_profile.refresh_token_jti, "")
