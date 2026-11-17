"""Documents end to end: upload → worker ingestion → chunks and keyword index → API views."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from app.ingestion import pipeline
from app.ingestion.extractors import ExtractionError
from tests.conftest import Api, Mailbox
from tests.fixtures import factory

DOCS = "/api/v1/documents"


async def upload_and_index(api: Api, worker: Mailbox, name: str, data: bytes) -> dict[str, Any]:
    response = await api.upload(name, data)
    assert response.status_code == 201, response.text
    await worker.drain()
    detail = (await api.get(f"{DOCS}/{response.json()['id']}")).json()
    return dict(detail)


def tenant_sql(owner_engine: Any, workspace_id: str, sql: str, **params: Any) -> Any:
    with owner_engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.workspace_id', :w, true)"), {"w": workspace_id})
        return conn.execute(text(sql), params).all()


@pytest.fixture
async def signed_in(api: Api) -> dict[str, Any]:
    await api.register()
    return dict((await api.get("/api/v1/auth/me")).json())


@pytest.mark.parametrize(
    ("name", "data", "expected_text"),
    [
        (
            "Leave Policy.pdf",
            factory.pdf_with_text([factory.LEAVE_POLICY, "Remote work rules."]),
            "annual leave",
        ),
        ("Handbook.docx", factory.docx_document(), "annual leave"),
        ("Returns.md", factory.MARKDOWN.encode(), "returned within 30 days"),
        ("Support.txt", factory.TEXT.encode(), "Warranty claims"),
    ],
)
async def test_each_format_is_indexed(
    api: Api,
    mailbox: Mailbox,
    signed_in: dict[str, Any],
    owner_engine: Any,
    name: str,
    data: bytes,
    expected_text: str,
) -> None:
    detail = await upload_and_index(api, mailbox, name, data)
    latest = detail["latest"]
    assert latest["status"] == "indexed", latest
    assert latest["chunk_count"] > 0
    assert latest["is_current"] is True
    assert detail["title"] == name.rsplit(".", 1)[0]

    chunks = (await api.get(f"{DOCS}/{detail['id']}/chunks")).json()
    assert chunks["total"] == latest["chunk_count"]
    assert any(expected_text in c["text"] for c in chunks["items"])

    # Keyword index is populated and scoped to the workspace.
    word = expected_text.rsplit(maxsplit=1)[-1]
    hits = tenant_sql(
        owner_engine,
        signed_in["workspace"]["id"],
        "SELECT count(*) FROM chunks WHERE tsv @@ plainto_tsquery('english', :q)",
        q=word,
    )
    assert hits[0][0] >= 1


async def test_pdf_metadata_and_section_titles(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any]
) -> None:
    pdf = await upload_and_index(
        api, mailbox, "Policy.pdf", factory.pdf_with_text(["One.", "Two.", "Three."])
    )
    assert pdf["latest"]["page_count"] == 3
    docx_doc = await upload_and_index(api, mailbox, "Handbook.docx", factory.docx_document())
    chunks = (await api.get(f"{DOCS}/{docx_doc['id']}/chunks")).json()["items"]
    assert any((c["section_title"] or "").startswith("Employee Handbook") for c in chunks)


async def test_scanned_pdf_is_flagged_not_indexed(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any]
) -> None:
    # Gray bars only: text recognition runs and finds nothing readable.
    detail = await upload_and_index(api, mailbox, "Scan.pdf", factory.scanned_pdf())
    latest = detail["latest"]
    assert latest["status"] == "needs_ocr"
    assert latest["error_code"] == "ocr_no_text"
    assert latest["chunk_count"] == 0
    assert "Text recognition found no readable text" in latest["error_message"]
    assert detail["has_current_version"] is False
    retry = await api.post(f"{DOCS}/{detail['id']}/retry")
    assert retry.status_code == 409


async def test_failure_is_visible_and_retry_recovers(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    real = pipeline.run_extraction

    async def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise ExtractionError("pdf_unreadable", "This PDF could not be read.")

    monkeypatch.setattr(pipeline, "run_extraction", broken)
    detail = await upload_and_index(
        api, mailbox, "Policy.pdf", factory.pdf_with_text([factory.LEAVE_POLICY])
    )
    assert detail["latest"]["status"] == "failed"
    assert detail["latest"]["error_code"] == "pdf_unreadable"
    assert detail["latest"]["error_message"] == "This PDF could not be read."

    monkeypatch.setattr(pipeline, "run_extraction", real)
    assert (await api.post(f"{DOCS}/{detail['id']}/retry")).json()["latest"]["status"] == "queued"
    await mailbox.drain()
    assert (await api.get(f"{DOCS}/{detail['id']}")).json()["latest"]["status"] == "indexed"


async def test_unexpected_error_retries_automatically(
    api: Api,
    mailbox: Mailbox,
    signed_in: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    owner_engine: Any,
) -> None:
    calls = {"n": 0}
    real = pipeline.chunk_pages

    def flaky(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return real(*args, **kwargs)

    monkeypatch.setattr(pipeline, "chunk_pages", flaky)
    response = await api.upload("Support.txt", factory.TEXT.encode())
    await mailbox.drain()
    detail = (await api.get(f"{DOCS}/{response.json()['id']}")).json()
    assert detail["latest"]["status"] == "queued"
    assert "Retrying automatically" in detail["latest"]["error_message"]

    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE jobs SET run_after = now() WHERE status = 'queued'"))
    await mailbox.drain()
    assert (await api.get(f"{DOCS}/{response.json()['id']}")).json()["latest"][
        "status"
    ] == "indexed"


async def test_duplicates_are_rejected_with_a_link(api: Api, signed_in: dict[str, Any]) -> None:
    first = await api.upload("Support.txt", factory.TEXT.encode())
    again = await api.upload("Copy of support.txt", factory.TEXT.encode())
    assert again.status_code == 409
    error = again.json()["error"]
    assert error["code"] == "duplicate_document"
    assert error["details"]["document_id"] == first.json()["id"]


async def test_upload_validation_errors(api: Api, app: FastAPI, signed_in: dict[str, Any]) -> None:
    exe = await api.upload("tool.exe", b"MZ\x90\x00")
    assert exe.status_code == 422 and exe.json()["error"]["code"] == "unsupported_type"
    fake = await api.upload("fake.pdf", b"not a pdf at all")
    assert fake.status_code == 422 and fake.json()["error"]["code"] == "type_mismatch"
    app.state.settings.max_upload_mb = 1
    big = await api.upload("big.txt", b"a" * (1024 * 1024 + 10))
    assert big.status_code == 413 and big.json()["error"]["code"] == "file_too_large"


async def test_document_limit(api: Api, signed_in: dict[str, Any], owner_engine: Any) -> None:
    tenant_sql(
        owner_engine,
        signed_in["workspace"]["id"],
        "UPDATE workspaces SET max_documents = 1 RETURNING id",
    )
    assert (await api.upload("a.txt", b"first file")).status_code == 201
    second = await api.upload("b.txt", b"second file")
    assert second.status_code == 409 and second.json()["error"]["code"] == "document_limit"


async def test_list_filters_and_limits(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any]
) -> None:
    await upload_and_index(api, mailbox, "Support.txt", factory.TEXT.encode())
    await upload_and_index(api, mailbox, "Scan.pdf", factory.scanned_pdf())
    listing = (await api.get(DOCS)).json()
    assert listing["total"] == 2
    assert listing["limits"]["allowed_extensions"] == [
        ".docx",
        ".jpeg",
        ".jpg",
        ".md",
        ".pdf",
        ".png",
        ".txt",
    ]
    assert listing["limits"]["document_count"] == 2
    assert [d["title"] for d in (await api.get(f"{DOCS}?status=attention")).json()["items"]] == [
        "Scan"
    ]
    assert [d["title"] for d in (await api.get(f"{DOCS}?status=indexed")).json()["items"]] == [
        "Support"
    ]
    assert (await api.get(f"{DOCS}?q=supp")).json()["total"] == 1
    summary = (await api.get("/api/v1/dashboard/summary")).json()["documents"]
    assert summary == {"total": 2, "processing": 0, "indexed": 1, "attention": 1}


async def test_new_version_replaces_current_only_after_indexing(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any]
) -> None:
    v1 = await upload_and_index(api, mailbox, "Support.txt", factory.TEXT.encode())
    doc_id = v1["id"]
    new_text = factory.TEXT.replace("weekdays", "every day of the week")
    response = await api.upload(
        "Support v2.txt", new_text.encode(), url=f"{DOCS}/{doc_id}/versions"
    )
    assert response.status_code == 201
    pending = (await api.get(f"{DOCS}/{doc_id}")).json()
    assert pending["latest"]["version_number"] == 2 and pending["latest"]["status"] == "queued"
    # Retrieval still serves version 1 while version 2 processes.
    served = (await api.get(f"{DOCS}/{doc_id}/chunks")).json()
    assert any("weekdays" in c["text"] for c in served["items"])
    busy = await api.upload("again.txt", b"third", url=f"{DOCS}/{doc_id}/versions")
    assert busy.status_code == 409

    await mailbox.drain()
    done = (await api.get(f"{DOCS}/{doc_id}")).json()
    assert [v["version_number"] for v in done["versions"]] == [2, 1]
    assert [v["is_current"] for v in done["versions"]] == [True, False]
    served = (await api.get(f"{DOCS}/{doc_id}/chunks")).json()
    assert any("every day of the week" in c["text"] for c in served["items"])
    assert not any("weekdays" in c["text"] for c in served["items"])


async def test_download_is_served_safely(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any]
) -> None:
    pdf = factory.pdf_with_text(["Hello"])
    doc = await upload_and_index(api, mailbox, "Report.pdf", pdf)
    response = await api.get(f"{DOCS}/{doc['id']}/file")
    assert response.status_code == 200
    assert response.content == pdf
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert "sandbox" in response.headers["content-security-policy"]
    txt = await upload_and_index(api, mailbox, "Notes.txt", b"plain notes")
    response = await api.get(f"{DOCS}/{txt['id']}/file")
    assert response.headers["content-disposition"].startswith("attachment")


async def test_delete_then_purge(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any], app: FastAPI, owner_engine: Any
) -> None:
    doc = await upload_and_index(api, mailbox, "Support.txt", factory.TEXT.encode())
    ws = signed_in["workspace"]["id"]
    key = tenant_sql(owner_engine, ws, "SELECT storage_key FROM document_versions")[0][0]
    storage = app.state.storage
    assert storage.exists(key)

    assert (await api.delete(f"{DOCS}/{doc['id']}")).status_code == 200
    assert (await api.get(f"{DOCS}/{doc['id']}")).status_code == 404
    assert (await api.get(DOCS)).json()["total"] == 0
    assert await mailbox.drain() == 0  # purge is scheduled for after the retention period
    assert storage.exists(key)
    # The same file can be uploaded again once the old copy is deleted.
    assert (await api.upload("Support.txt", factory.TEXT.encode())).status_code == 201

    assert (await api.post(f"{DOCS}/{doc['id']}/purge")).status_code == 404  # already hidden
    tenant_sql(
        owner_engine,
        ws,
        "UPDATE jobs SET run_after = now() WHERE job_type = 'purge_document' RETURNING id",
    )
    await mailbox.drain()
    assert not storage.exists(key)
    remaining = tenant_sql(
        owner_engine, ws, "SELECT count(*) FROM documents WHERE id = :d", d=uuid.UUID(doc["id"])
    )
    assert remaining[0][0] == 0


async def test_purge_now_removes_everything(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any], owner_engine: Any
) -> None:
    doc = await upload_and_index(api, mailbox, "Handbook.docx", factory.docx_document())
    assert (await api.post(f"{DOCS}/{doc['id']}/purge")).status_code == 202
    await mailbox.drain()
    ws = signed_in["workspace"]["id"]
    counts = tenant_sql(
        owner_engine,
        ws,
        "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM document_versions), "
        "(SELECT count(*) FROM document_pages), (SELECT count(*) FROM chunks)",
    )
    assert tuple(counts[0]) == (0, 0, 0, 0)
    actions = {r[0] for r in tenant_sql(owner_engine, ws, "SELECT action FROM audit_log")}
    assert {"document.uploaded", "document.purge_requested", "document.purged"} <= actions


async def test_viewers_cannot_upload_or_delete(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any], owner_engine: Any
) -> None:
    doc = await upload_and_index(api, mailbox, "Support.txt", factory.TEXT.encode())
    tenant_sql(
        owner_engine,
        signed_in["workspace"]["id"],
        "UPDATE memberships SET role = 'viewer' RETURNING id",
    )
    assert (await api.get(DOCS)).status_code == 200
    assert (await api.upload("x.txt", b"new content")).status_code == 403
    assert (await api.delete(f"{DOCS}/{doc['id']}")).status_code == 403
    assert (await api.post(f"{DOCS}/{doc['id']}/purge")).status_code == 403


async def test_domain_events_are_recorded(
    api: Api, mailbox: Mailbox, signed_in: dict[str, Any], owner_engine: Any
) -> None:
    await upload_and_index(api, mailbox, "Support.txt", factory.TEXT.encode())
    await upload_and_index(api, mailbox, "Scan.pdf", factory.scanned_pdf())
    events = tenant_sql(
        owner_engine, signed_in["workspace"]["id"], "SELECT event_type FROM domain_events"
    )
    assert sorted(e[0] for e in events) == ["document.failed", "document.indexed"]
