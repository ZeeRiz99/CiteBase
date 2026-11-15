"""A user in workspace B must never see, download, change or retrieve workspace A's documents."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from tests.conftest import Api, Mailbox

DOCS = "/api/v1/documents"


async def test_document_endpoints_are_workspace_isolated(
    api: Api, api_b: Api, mailbox: Mailbox, owner_engine: Any
) -> None:
    await api.register(email="a@example.com", name="Alice A")
    await api_b.register(email="b@example.com", name="Bob B")
    doc_id = (
        await api.upload("Secret plan.txt", b"Workspace A confidential pricing plan.")
    ).json()["id"]
    await mailbox.drain()

    # Listing, search and counts show nothing from A.
    assert (await api_b.get(DOCS)).json()["total"] == 0
    assert (await api_b.get(f"{DOCS}?q=Secret")).json()["total"] == 0
    assert (await api_b.get("/api/v1/dashboard/summary")).json()["documents"]["total"] == 0

    # Every per-document endpoint answers 404, never 403 (no confirmation that it exists).
    for method, url in [
        ("GET", f"{DOCS}/{doc_id}"),
        ("GET", f"{DOCS}/{doc_id}/file"),
        ("GET", f"{DOCS}/{doc_id}/chunks"),
        ("POST", f"{DOCS}/{doc_id}/retry"),
        ("POST", f"{DOCS}/{doc_id}/purge"),
        ("DELETE", f"{DOCS}/{doc_id}"),
    ]:
        response = await (api_b.get(url) if method == "GET" else api_b.send(method, url))
        assert response.status_code == 404, (method, url, response.status_code)
    version = await api_b.upload("x.txt", b"overwrite attempt", url=f"{DOCS}/{doc_id}/versions")
    assert version.status_code == 404

    # A's identical file is not a "duplicate" for B: hashes are per workspace.
    b_upload = await api_b.upload("Mine.txt", b"Workspace A confidential pricing plan.")
    assert b_upload.status_code == 201
    await mailbox.drain()

    # A still has its document, untouched.
    assert (await api.get(f"{DOCS}/{doc_id}")).json()["latest"]["status"] == "indexed"

    # Row-level security: in B's context only B's chunks exist, even with an unfiltered query.
    b_ws = (await api_b.get("/api/v1/auth/me")).json()["workspace"]["id"]
    with owner_engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.workspace_id', :w, true)"), {"w": b_ws})
        doc_ids = {str(r[0]) for r in conn.execute(text("SELECT DISTINCT document_id FROM chunks"))}
    assert doc_ids == {b_upload.json()["id"]}


async def test_collection_from_another_workspace_is_rejected(api: Api, api_b: Api) -> None:
    await api.register(email="a@example.com", name="Alice A")
    await api_b.register(email="b@example.com", name="Bob B")
    a_collection = (await api.get("/api/v1/collections")).json()[0]["id"]
    response = await api_b.upload("x.txt", b"content", data={"collection_id": a_collection})
    assert response.status_code == 404
