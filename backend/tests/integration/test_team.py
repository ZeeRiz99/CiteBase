from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_token
from app.db.session import set_tenant
from app.models import Invitation
from tests.conftest import TEST_DATABASE_URL, Api, Mailbox, _client

PASSWORD = "correct-horse-battery"


async def invite(api: Api, email: str, role: str = "member") -> dict[str, Any]:
    response = await api.post("/api/v1/workspace/invitations", {"email": email, "role": role})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def token_of(link: str) -> str:
    return link.split("token=", 1)[1]


async def accept(api: Api, token: str, name: str = "Grace Hopper") -> httpx.Response:
    return await api.post(
        "/api/v1/invitations/accept", {"token": token, "full_name": name, "password": PASSWORD}
    )


@pytest.fixture
async def api_c(app: FastAPI) -> Any:
    async with _client(app) as client:
        yield Api(client)


async def test_invite_email_accept_and_join_with_role(
    api: Api, api_b: Api, mailbox: Mailbox
) -> None:
    await api.register()
    await mailbox.deliver()
    created = await invite(api, "Grace@Example.com", "viewer")
    assert created["email"] == "grace@example.com"
    assert created["link"].startswith("http://testserver/invite?token=")

    sent = (await mailbox.deliver())[-1]
    assert sent.to == "grace@example.com"
    assert "Ada Lovelace invited you to Ada Lovelace Co" in sent.subject
    token = mailbox.token_from(sent)
    assert token == token_of(created["link"])

    preview = await api_b.post("/api/v1/invitations/preview", {"token": token})
    assert preview.status_code == 200
    assert preview.json()["workspace_name"] == "Ada Lovelace Co"
    assert preview.json()["inviter_name"] == "Ada Lovelace"
    assert preview.json()["role"] == "viewer"

    joined = await accept(api_b, token)
    assert joined.status_code == 200, joined.text
    me = (await api_b.get("/api/v1/auth/me")).json()
    assert me["workspace"]["name"] == "Ada Lovelace Co"
    assert me["role"] == "viewer"
    assert me["user"]["email_verified"] is True

    # The link is single use, and the new member can sign in again later.
    assert (await accept(api_b, token)).status_code == 400
    assert (await api_b.login("grace@example.com", PASSWORD)).status_code == 200

    members = (await api.get("/api/v1/workspace/members")).json()
    assert [(m["email"], m["role"], m["is_you"]) for m in members] == [
        ("ada@example.com", "owner", True),
        ("grace@example.com", "viewer", False),
    ]
    assert (await api.get("/api/v1/workspace/invitations")).json() == []


async def test_viewer_cannot_upload_but_can_read(api: Api, api_b: Api) -> None:
    await api.register()
    await api.upload("Policy.txt", b"Returns are accepted within thirty days of delivery.")
    await accept(api_b, token_of((await invite(api, "v@example.com", "viewer"))["link"]))

    assert (await api_b.get("/api/v1/documents")).status_code == 200
    assert len((await api_b.get("/api/v1/documents")).json()["items"]) == 1
    upload = await api_b.upload("Mine.txt", b"Viewers may not add documents to the workspace.")
    assert upload.status_code == 403
    assert (await api_b.get("/api/v1/workspace/members")).status_code == 403


async def test_role_hierarchy(api: Api, api_b: Api, api_c: Api) -> None:
    await api.register()
    await accept(api_b, token_of((await invite(api, "admin@example.com", "admin"))["link"]))
    admin_me = (await api_b.get("/api/v1/auth/me")).json()
    assert admin_me["role"] == "admin"
    owner_id = (await api.get("/api/v1/auth/me")).json()["user"]["id"]

    # Admins cannot create or manage admins, or touch the owner.
    denied = await api_b.post(
        "/api/v1/workspace/invitations", {"email": "x@example.com", "role": "admin"}
    )
    assert denied.status_code == 403
    assert (
        await api_b.patch(f"/api/v1/workspace/members/{owner_id}", {"role": "member"})
    ).status_code == 403
    assert (await api_b.delete(f"/api/v1/workspace/members/{owner_id}")).status_code == 403
    me_id = admin_me["user"]["id"]
    assert (
        await api_b.patch(f"/api/v1/workspace/members/{me_id}", {"role": "viewer"})
    ).status_code == 403

    # Admins manage members; "owner" is never grantable.
    await accept(api_c, token_of((await invite(api_b, "m@example.com"))["link"]), "Member M")
    member_id = (await api_c.get("/api/v1/auth/me")).json()["user"]["id"]
    ok = await api_b.patch(f"/api/v1/workspace/members/{member_id}", {"role": "viewer"})
    assert ok.status_code == 200
    assert (await api_c.get("/api/v1/auth/me")).json()["role"] == "viewer"
    owner_grant = await api.patch(f"/api/v1/workspace/members/{member_id}", {"role": "owner"})
    assert owner_grant.status_code == 422


async def test_removing_a_member_ends_their_sessions(api: Api, api_b: Api) -> None:
    await api.register()
    await accept(api_b, token_of((await invite(api, "m@example.com"))["link"]))
    member_id = (await api_b.get("/api/v1/auth/me")).json()["user"]["id"]

    assert (await api.delete(f"/api/v1/workspace/members/{member_id}")).status_code == 204
    assert (await api_b.get("/api/v1/auth/me")).status_code == 401
    assert (await api_b.post("/api/v1/auth/refresh")).status_code == 401
    assert (await api_b.login("m@example.com", PASSWORD)).status_code == 401


async def test_revoked_expired_and_existing_accounts(
    api: Api, api_b: Api, owner_engine: Any
) -> None:
    await api.register()
    revoked = await invite(api, "r@example.com")
    assert (await api.delete(f"/api/v1/workspace/invitations/{revoked['id']}")).status_code == 204
    assert (await accept(api_b, token_of(revoked["link"]))).status_code == 400

    expired = await invite(api, "e@example.com")
    with owner_engine.begin() as conn:
        conn.execute(
            text("UPDATE invitations SET expires_at = now() - interval '1 minute' WHERE id = :i"),
            {"i": expired["id"]},
        )
    assert (
        await api_b.post("/api/v1/invitations/preview", {"token": token_of(expired["link"])})
    ).status_code == 400

    # Re-inviting replaces the earlier link.
    first = await invite(api, "twice@example.com")
    second = await invite(api, "twice@example.com")
    assert (await accept(api_b, token_of(first["link"]))).status_code == 400
    assert len((await api.get("/api/v1/workspace/invitations")).json()) == 1
    assert (await accept(api_b, token_of(second["link"]))).status_code == 200

    # People who already have an account cannot be invited (one workspace per account for now).
    taken = await api.post(
        "/api/v1/workspace/invitations", {"email": "ada@example.com", "role": "member"}
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "email_taken"

    bogus = await api_b.post("/api/v1/invitations/preview", {"token": "x" * 43})
    assert bogus.status_code == 400


async def test_team_endpoints_are_isolated_per_workspace(api: Api, api_b: Api) -> None:
    await api.register()
    created = await invite(api, "m@example.com")
    await api_b.register(email="eve@example.com", name="Eve Adams")

    assert (await api_b.get("/api/v1/workspace/invitations")).json() == []
    assert [m["email"] for m in (await api_b.get("/api/v1/workspace/members")).json()] == [
        "eve@example.com"
    ]
    revoke = await api_b.delete(f"/api/v1/workspace/invitations/{created['id']}")
    assert revoke.status_code == 404
    ada_id = (await api.get("/api/v1/auth/me")).json()["user"]["id"]
    assert (await api_b.delete(f"/api/v1/workspace/members/{ada_id}")).status_code == 404


async def test_workspace_settings(api: Api, api_b: Api) -> None:
    await api.register()
    settings = (await api.get("/api/v1/workspace")).json()
    assert settings["name"] == "Ada Lovelace Co"
    assert settings["monthly_token_limit"] == 2_000_000
    assert settings["token_limit_source"] == "default"

    renamed = await api.patch("/api/v1/workspace", {"name": "  Analytical Engines  "})
    assert renamed.json()["name"] == "Analytical Engines"
    assert (await api.get("/api/v1/auth/me")).json()["workspace"]["name"] == "Analytical Engines"

    await accept(api_b, token_of((await invite(api, "m@example.com"))["link"]))
    assert (await api_b.get("/api/v1/workspace")).status_code == 200
    assert (await api_b.patch("/api/v1/workspace", {"name": "Mine"})).status_code == 403


async def test_invitation_rows_need_tenant_context(api: Api, api_b: Api) -> None:
    """The app role sees invitations only for its tenant; the lookup function returns just an id."""
    await api.register()
    created = await invite(api, "m@example.com")
    await api_b.register(email="eve@example.com", name="Eve Adams")
    ws_a = uuid.UUID((await api.get("/api/v1/auth/me")).json()["workspace"]["id"])
    ws_b = uuid.UUID((await api_b.get("/api/v1/auth/me")).json()["workspace"]["id"])

    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with async_sessionmaker(engine)() as db:
            assert (await db.execute(select(Invitation))).scalars().all() == []
            await set_tenant(db, workspace_id=ws_b, user_id=None)
            assert (await db.execute(select(Invitation))).scalars().all() == []
            token_hash = hash_token(token_of(created["link"]))
            resolved = (
                await db.execute(text("SELECT app_invitation_workspace(:h)"), {"h": token_hash})
            ).scalar_one()
            assert resolved == ws_a
            await set_tenant(db, workspace_id=ws_a, user_id=None)
            assert len((await db.execute(select(Invitation))).scalars().all()) == 1
    finally:
        await engine.dispose()
