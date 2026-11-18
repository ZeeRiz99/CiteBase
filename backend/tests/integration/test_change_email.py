"""Changing the sign-in email: link to the new address, notice to the old one, sessions end."""

from __future__ import annotations

from tests.conftest import Api, Mailbox

PASSWORD = "correct-horse-battery"


async def request(api: Api, new_email: str, password: str = PASSWORD) -> int:
    response = await api.post(
        "/api/v1/me/email", {"new_email": new_email, "current_password": password}
    )
    return response.status_code


async def test_email_change_needs_the_link_from_the_new_inbox(
    api: Api, api_b: Api, mailbox: Mailbox
) -> None:
    await api.register()
    await mailbox.deliver()  # the sign-up confirmation

    assert await request(api, "Ada.New@Example.com") == 202
    sent = (await mailbox.deliver())[-1]
    assert sent.to == "ada.new@example.com"
    assert "/confirm-email-change?token=" in sent.text
    # Nothing changes until the link is opened.
    assert (await api.get("/api/v1/auth/me")).json()["user"]["email"] == "ada@example.com"

    token = mailbox.token_from(sent)
    confirmed = await api_b.post("/api/v1/auth/confirm-email-change", {"token": token})
    assert confirmed.status_code == 200, confirmed.text
    assert "ada.new@example.com" in confirmed.json()["message"]

    notice = (await mailbox.deliver())[-1]
    assert notice.to == "ada@example.com"
    assert "ada.new@example.com" in notice.text and "/forgot-password" in notice.text

    # Every session ended; the new address signs in and is confirmed, the old one does not.
    assert (await api.get("/api/v1/auth/me")).status_code == 401
    assert (await api.login("ada@example.com", PASSWORD)).status_code == 401
    assert (await api.login("ada.new@example.com", PASSWORD)).status_code == 200
    me = (await api.get("/api/v1/auth/me")).json()
    assert me["user"]["email"] == "ada.new@example.com" and me["user"]["email_verified"] is True

    # Single use.
    again = await api_b.post("/api/v1/auth/confirm-email-change", {"token": token})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_token"


async def test_email_change_checks(api: Api, api_b: Api, mailbox: Mailbox) -> None:
    await api.register()
    await api_b.register(email="eve@example.com", name="Eve Adams")

    wrong = await api.post(
        "/api/v1/me/email", {"new_email": "x@example.com", "current_password": "nope-nope-no"}
    )
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "wrong_password"
    same = await api.post(
        "/api/v1/me/email", {"new_email": "ADA@example.com", "current_password": PASSWORD}
    )
    assert same.status_code == 409 and same.json()["error"]["code"] == "same_email"
    taken = await api.post(
        "/api/v1/me/email", {"new_email": "eve@example.com", "current_password": PASSWORD}
    )
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "email_taken"


async def test_a_newer_request_cancels_the_older_link(api: Api, mailbox: Mailbox) -> None:
    await api.register()
    await mailbox.deliver()
    assert await request(api, "first@example.com") == 202
    first = mailbox.token_from((await mailbox.deliver())[-1])
    assert await request(api, "second@example.com") == 202
    second = mailbox.token_from((await mailbox.deliver())[-1])

    old = await api.post("/api/v1/auth/confirm-email-change", {"token": first})
    assert old.status_code == 400
    assert (
        await api.post("/api/v1/auth/confirm-email-change", {"token": second})
    ).status_code == 200


async def test_address_taken_before_confirming(api: Api, api_b: Api, mailbox: Mailbox) -> None:
    await api.register()
    await mailbox.deliver()
    assert await request(api, "race@example.com") == 202
    token = mailbox.token_from((await mailbox.deliver())[-1])
    await api_b.register(email="race@example.com", name="Racer")
    late = await api.post("/api/v1/auth/confirm-email-change", {"token": token})
    assert late.status_code == 409 and late.json()["error"]["code"] == "email_taken"
