"""Uploads and invitations need a confirmed email address (REQUIRE_VERIFIED_EMAIL, default on)."""

from __future__ import annotations

from app.core.config import Settings
from tests.conftest import Api, Mailbox
from tests.fixtures import factory

DOCS = "/api/v1/documents"


async def test_unconfirmed_accounts_cannot_upload_or_invite(
    api: Api, mailbox: Mailbox, settings: Settings
) -> None:
    settings.require_verified_email = True
    await api.register()

    upload = await api.upload("Support.txt", factory.TEXT.encode())
    assert upload.status_code == 403
    assert upload.json()["error"]["code"] == "email_not_verified"
    invite = await api.post(
        "/api/v1/workspace/invitations", {"email": "new@example.com", "role": "member"}
    )
    assert invite.status_code == 403 and invite.json()["error"]["code"] == "email_not_verified"

    # Reading, asking and settings still work before confirming.
    assert (await api.get(DOCS)).status_code == 200
    assert (await api.get("/api/v1/workspace")).status_code == 200

    token = mailbox.token_from((await mailbox.deliver())[0])
    assert (await api.post("/api/v1/auth/verify-email", {"token": token})).status_code == 200
    assert (await api.upload("Support.txt", factory.TEXT.encode())).status_code == 201
    invite = await api.post(
        "/api/v1/workspace/invitations", {"email": "new@example.com", "role": "member"}
    )
    assert invite.status_code == 201


async def test_invited_people_are_confirmed_by_their_link(
    api: Api, api_b: Api, mailbox: Mailbox, settings: Settings
) -> None:
    await api.register()
    token = mailbox.token_from((await mailbox.deliver())[0])
    await api.post("/api/v1/auth/verify-email", {"token": token})
    settings.require_verified_email = True
    link = (
        await api.post(
            "/api/v1/workspace/invitations", {"email": "m@example.com", "role": "member"}
        )
    ).json()["link"]
    accepted = await api_b.post(
        "/api/v1/invitations/accept",
        {"token": link.split("token=")[1], "full_name": "Mia", "password": "correct-horse-battery"},
    )
    assert accepted.status_code == 200
    assert (await api_b.upload("Notes.txt", factory.TEXT.encode())).status_code == 201


async def test_requirement_can_be_turned_off(api: Api, settings: Settings) -> None:
    settings.require_verified_email = False
    await api.register()
    assert (await api.upload("Support.txt", factory.TEXT.encode())).status_code == 201
