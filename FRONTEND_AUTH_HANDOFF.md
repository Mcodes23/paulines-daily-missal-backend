# Authentication and subscription handoff for George

The regression suite exercises the actual authentication, profile, and subscription
routers through in-process HTTP requests on disposable PostgreSQL. This establishes
local behavior; deployed connectivity and persistent integration accounts remain
pending an approved environment and Premium test plan.

## Required provisioning details

- Reachable backend URL/environment for George.
- Approved Premium plan, or the name, price, currency, and duration of a new synthetic plan.
- Finite Premium test period and account expiry expectations.

Do not use production accounts for integration testing. Both test accounts must be
active ordinary users, without staff or superuser privileges. Provision new unique
synthetic identities only; refuse any collision rather than updating an existing user.

Generate unique random passwords only when provisioning is approved for the target.
Keep credentials in a protected credential store or a private mode-0600 file outside
the repository. Share them separately through the team's approved secure channel.
Never include passwords, JWTs, recovery proofs, or signing keys in this document,
screenshots, logs, Git, or URLs.

## Base URL and requests

The routes below are registered under `/v1`. The deployment may expose an additional
`/api` prefix; confirm the reachable URL rather than deriving it from `root_path`.
Requests with JSON bodies use `Content-Type: application/json`.

| Request | Input | Expected result |
|---|---|---|
| `POST /v1/auth/login` | Privately supplied test email and password | `data.access_token`, `data.refresh_token`, `data.token_type`, and `data.user` |
| `GET /v1/auth/profile` | `Authorization: Bearer <access token>` | The authenticated account's profile |
| `GET /v1/subscriptions/plans` | No authentication required | Active plans: id, name, price, currency, duration_days, description |
| `GET /v1/subscriptions/status` | Access bearer token | The authenticated account's subscription data |
| `POST /v1/auth/refresh` | JSON field `refresh_token` | New `data.access_token` and `data.token_type`; retain the original refresh token |
| `POST /v1/auth/logout` | Access bearer token | Refresh session revoked |
| `POST /v1/subscriptions/activate-trial` | Access bearer token | First eligible activation succeeds; repeat or active-subscription activation returns 400 |

Read the response `data` field. Subscription status is not embedded in login/profile
responses; fetch it separately. Never put bearer tokens in query parameters.

## Expected integration states

Free is represented for these fixtures by the initial registration subscription:

```json
{
  "status": "trial",
  "plan_name": null,
  "is_active": false,
  "days_remaining": 0,
  "trial_end": null,
  "current_period_end": null
}
```

The raw `trial` status does not mean a trial was activated. Do not activate a trial
on the Free fixture while checking the initial Free state.

The Premium fixture requires an approved plan association, `status="active"`, and
a future `current_period_end`. Its response must show the approved plan name,
`is_active=true`, null `trial_end`, and the selected period end. Remaining days are
floored whole days; an unexpired period can report zero during its last 24 hours.

These are fixture mappings, not new backend tier definitions. `is_active=true` can
also describe a trial and does not by itself identify Premium. Premium feature
enforcement and payment integration are outside this change.

## Session and recovery behavior

- Wrong credentials return 401. Inactive accounts are rejected; a correct-password
  inactive login returns 403, while protected access and refresh return 401.
- Missing bearer credentials currently return 403; invalid/expired/wrong-type
  tokens return 401.
- A second login for the same account replaces its refresh session. Distinct test
  accounts retain independent sessions.
- Logout/password change/reset revoke refresh. Existing access JWTs remain valid
  until expiry while the user remains active; discard them on frontend logout.
- Registration returns no verification proof and leaves `is_email_verified=false`.
  Verification is not currently an access gate.
- Forgot-password and resend-verification uniformly return 503 because there is no
  approved private delivery channel. They perform no lookup or proof issuance.
- Verification/reset consumers are tested using proofs assigned only to owned
  disposable records. Real inbox delivery is not established. Existing unexpired
  proofs are not globally invalidated by this patch.

## Regression command

```bash
.venv/bin/python -B scripts/run_auth_tests.py accounts.test_isolation accounts.test_auth_flows accounts.test_subscription_flows
```

The script starts a fresh private PostgreSQL cluster, disables TCP, rejects inherited
connection overrides, and applies existing migrations only to its uniquely named
test database. Django removes that test database after the run; the script stops
only its own server. It never loads the project's `.env` or production settings.

Successful temporary fixtures are destroyed afterward. They are not persistent
accounts that George can log into. Provisioning is complete only after the approved
target passes login, profile, subscription-status, refresh, and logout checks for
both new accounts, followed by frontend verification.
