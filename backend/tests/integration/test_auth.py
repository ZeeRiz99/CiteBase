from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import text

from tests.conftest import Api, Mailbox

PASSWORD = "correct-horse-battery"


async def test_register_creates_workspace_and_signs_in(api: Api, mailbox: Mailbox) -> None:
    response = await api.register()
    assert response.status_code == 201
    for name in ("cb_access", "cb_refresh", "cb_session", "cb_csrf"):
        assert name in {c.name for c in api.cookies.jar}

    me = (await api.get("/api/v1/auth/me")).json()
    assert me["user"]["email"] == "ada@example.com"
    assert me["user"]["email_verified"] is False
    assert me["workspace"]["name"] == "Ada Lovelace Co"
    assert me["role"] == "owner"

    sent = await mailbox.deliver()
    assert len(sent) == 1
    assert sent[0].to == "ada@example.com"
    assert "/verify-email?token=" in sent[0].text


async def test_email_verification_is_single_use(api: Api, mailbox: Mailbox) -> None:
    await api.register()
    token = mailbox.token_from((await mailbox.deliver())[0])

    assert (await api.post("/api/v1/auth/verify-email", {"token": token})).status_code == 200
    assert (await api.get("/api/v1/auth/me")).json()["user"]["email_verified"] is True

    again = await api.post("/api/v1/auth/verify-email", {"token": token})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_token"


async def test_resend_verification_invalidates_previous_link(api: Api, mailbox: Mailbox) -> None:
    await api.register()
    first = mailbox.token_from((await mailbox.deliver())[0])
    assert (await api.post("/api/v1/auth/resend-verification")).status_code == 202
    second = mailbox.token_from((await mailbox.deliver())[1])
    assert (await api.post("/api/v1/auth/verify-email", {"token": first})).status_code == 400
    assert (await api.post("/api/v1/auth/verify-email", {"token": second})).status_code == 200


async def test_duplicate_email_is_rejected_case_insensitively(api: Api) -> None:
    await api.register(email="ada@example.com")
    response = await api.register(email="ADA@Example.com")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_validation_errors_use_the_error_envelope(api: Api) -> None:
    response = await api.post(
        "/api/v1/auth/register", {"full_name": "A", "email": "not-an-email", "password": "short"}
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert {f["field"] for f in body["fields"]} == {"email", "password"}
    assert body["request_id"]


async def test_login_success_and_uniform_failure(api: Api, api_b: Api) -> None:
    await api.register()

    wrong = await api_b.login("ada@example.com", "not-the-password")
    unknown = await api_b.login("nobody@example.com", "not-the-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]

    ok = await api_b.login("ADA@example.com", PASSWORD)
    assert ok.status_code == 200
    assert (await api_b.get("/api/v1/auth/me")).json()["user"]["email"] == "ada@example.com"


async def test_unauthenticated_requests_are_rejected(api: Api) -> None:
    response = await api.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_unsafe_requests_require_csrf_token(api: Api) -> None:
    response = await api.client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "x"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


async def test_login_is_rate_limited_per_email(api: Api) -> None:
    await api.register()
    statuses = [
        (await api.login("ada@example.com", "wrong-password")).status_code for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


async def test_refresh_rotates_and_detects_reuse(api: Api, owner_engine: Any) -> None:
    await api.register()
    old_refresh = api.cookies.get("cb_refresh", path="/api/v1/auth")

    assert (await api.post("/api/v1/auth/refresh")).status_code == 200
    new_refresh = api.cookies.get("cb_refresh", path="/api/v1/auth")
    assert new_refresh != old_refresh
    assert (await api.get("/api/v1/auth/me")).status_code == 200

    # Within the grace window, an old token is treated as a tab race: rejected, nothing revoked.
    api.cookies.set("cb_refresh", old_refresh, path="/api/v1/auth")
    race = await api.post("/api/v1/auth/refresh")
    assert race.status_code == 401
    assert race.json()["error"]["code"] == "refresh_race"
    assert "cb_session" in {c.name for c in api.cookies.jar}  # a race keeps the session cookies

    # After the grace window, reuse means theft: the whole session family is revoked.
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE auth_sessions SET rotated_at = rotated_at - :d WHERE rotated_at IS NOT NULL"
            ),
            {"d": timedelta(minutes=5)},
        )
    assert (await api.post("/api/v1/auth/refresh")).status_code == 401
    # A dead session clears its cookies, so the UI cannot bounce between /login and /dashboard.
    assert "cb_session" not in {c.name for c in api.cookies.jar}
    assert (await api.get("/api/v1/auth/me")).status_code == 401
    api.cookies.set("cb_refresh", new_refresh, path="/api/v1/auth")
    assert (await api.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_revokes_session(api: Api) -> None:
    await api.register()
    access = api.cookies.get("cb_access", path="/api")
    assert (await api.post("/api/v1/auth/logout")).status_code == 200
    api.cookies.set("cb_access", access, path="/api")  # replaying the old access token
    assert (await api.get("/api/v1/auth/me")).status_code == 401


async def test_forgot_password_does_not_reveal_accounts(api: Api, mailbox: Mailbox) -> None:
    response = await api.post("/api/v1/auth/forgot-password", {"email": "nobody@example.com"})
    assert response.status_code == 202
    assert await mailbox.deliver() == []


async def test_password_reset_flow(api: Api, api_b: Api, mailbox: Mailbox) -> None:
    await api.register()
    await mailbox.deliver()  # verification email

    assert (
        await api_b.post("/api/v1/auth/forgot-password", {"email": "ada@example.com"})
    ).status_code == 202
    reset_email = (await mailbox.deliver())[-1]
    assert "/reset-password?token=" in reset_email.text
    token = mailbox.token_from(reset_email)

    new_password = "a-brand-new-passphrase"
    response = await api_b.post(
        "/api/v1/auth/reset-password", {"token": token, "password": new_password}
    )
    assert response.status_code == 200

    # Existing sessions were revoked everywhere.
    assert (await api.get("/api/v1/auth/me")).status_code == 401
    # Single use.
    reuse = await api_b.post(
        "/api/v1/auth/reset-password", {"token": token, "password": "another-passphrase"}
    )
    assert reuse.status_code == 400
    # Old password no longer works; new one does, and the email counts as verified.
    assert (await api_b.login("ada@example.com", PASSWORD)).status_code == 401
    assert (await api_b.login("ada@example.com", new_password)).status_code == 200
    assert (await api_b.get("/api/v1/auth/me")).json()["user"]["email_verified"] is True


async def test_change_password_signs_out_other_devices(api: Api, api_b: Api) -> None:
    await api.register()
    await api_b.login("ada@example.com", PASSWORD)

    wrong = await api.post(
        "/api/v1/me/password",
        {"current_password": "nope-nope-nope", "new_password": "another-passphrase"},
    )
    assert wrong.status_code == 400

    ok = await api.post(
        "/api/v1/me/password", {"current_password": PASSWORD, "new_password": "another-passphrase"}
    )
    assert ok.status_code == 200
    assert (await api.get("/api/v1/auth/me")).status_code == 200
    assert (await api_b.get("/api/v1/auth/me")).status_code == 401


async def test_update_profile(api: Api) -> None:
    await api.register()
    response = await api.patch("/api/v1/me", {"full_name": "  Ada King  "})
    assert response.status_code == 200
    assert response.json()["user"]["full_name"] == "Ada King"


async def test_audit_log_records_auth_events(api: Api, api_b: Api, owner_engine: Any) -> None:
    await api.register()
    await api_b.login("ada@example.com", "wrong-password")
    me = (await api.get("/api/v1/auth/me")).json()
    with owner_engine.begin() as conn:
        # Without tenant context nothing is visible (FORCE RLS applies to the owner too).
        assert conn.execute(text("SELECT count(*) FROM audit_log")).scalar_one() == 0
        conn.execute(
            text("SELECT set_config('app.workspace_id', :w, true)"), {"w": me["workspace"]["id"]}
        )
        actions = {row[0] for row in conn.execute(text("SELECT action FROM audit_log"))}
    # The failed login has no workspace, so it is stored but not readable by any tenant.
    assert actions == {"auth.register"}


async def test_health_and_branding(api: Api) -> None:
    assert (await api.get("/api/v1/healthz")).json() == {"status": "ok"}
    assert (await api.get("/api/v1/readyz")).json()["database"] == "up"
    branding = (await api.get("/api/v1/public/branding")).json()
    assert branding["product_name"] == "CiteBase"
    assert (await api.get("/api/v1/healthz")).headers["x-request-id"]
