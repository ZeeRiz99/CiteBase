"""Ingestion and purge job handlers.

ingest: queued → extracting → chunking → indexed  (embedding is inserted before indexed in Phase 3)
        or failed / needs_ocr with a user-safe message. Extraction results are stored as
        document_pages, so a retry after a chunking failure resumes without re-parsing.
        A new version becomes the document's current version only once it is indexed.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import set_tenant
from app.ingestion.chunking import ChunkingConfig, chunk_pages
from app.ingestion.extractors import ExtractionError
from app.ingestion.runner import run_extraction
from app.models import Document, DocumentPage, DocumentStatus, DocumentVersion, Job, Workspace
from app.repositories import documents as docs_repo
from app.repositories import system as system_repo
from app.repositories import workspaces as ws_repo
from app.repositories.users import utcnow
from app.worker.context import PermanentJobError, WorkerContext, heartbeat

log = structlog.get_logger("ingestion")

NEEDS_OCR_MESSAGE = (
    "This PDF appears to be scanned: it has little or no selectable text. It needs text "
    "recognition (OCR) before it can be searched, so it was not indexed."
)
RETRYING_MESSAGE = "A temporary problem interrupted processing. Retrying automatically."
INTERNAL_MESSAGE = "Processing failed. Use Retry, and contact support if it keeps failing."


def chunking_config_for(workspace: Workspace) -> ChunkingConfig:
    overrides: dict[str, Any] = (workspace.settings or {}).get("chunking", {})
    allowed = {"target_tokens", "max_tokens", "overlap_tokens", "min_tokens"}
    try:
        return ChunkingConfig(**{k: int(v) for k, v in overrides.items() if k in allowed})
    except (TypeError, ValueError):
        log.warning("invalid_chunking_settings", workspace_id=str(workspace.id))
        return ChunkingConfig()


def _ids(job: Job, key: str) -> tuple[uuid.UUID, uuid.UUID]:
    if job.workspace_id is None or key not in job.payload:
        raise PermanentJobError(f"{job.job_type} job needs workspace_id and {key}")
    return job.workspace_id, uuid.UUID(str(job.payload[key]))


async def _mark(
    db: AsyncSession,
    version_id: uuid.UUID,
    status: DocumentStatus,
    *,
    code: str | None = None,
    message: str | None = None,
    event: str | None = None,
) -> None:
    version = await db.get(DocumentVersion, version_id, populate_existing=True)
    if version is None:
        return
    version.status = status
    version.error_code = code
    version.error_message = message
    if event:
        system_repo.add_event(
            db,
            workspace_id=version.workspace_id,
            event_type=event,
            payload={
                "document_id": str(version.document_id),
                "version_id": str(version.id),
                "status": status.value,
                "error_code": code,
            },
        )
    await db.commit()


async def _process(
    db: AsyncSession,
    ctx: WorkerContext,
    job: Job,
    workspace: Workspace,
    document: Document,
    version: DocumentVersion,
) -> None:
    if await docs_repo.page_count(db, version.id) == 0:
        version.status = DocumentStatus.extracting
        version.error_code = version.error_message = None
        await db.commit()

        path = ctx.storage.local_path(version.storage_key)
        if not path.is_file():
            raise ExtractionError("file_missing", "The uploaded file is missing. Upload it again.")
        async with heartbeat(ctx, job.id):
            extraction = await run_extraction(
                path, version.file_ext, ctx.settings.extraction_timeout_seconds
            )

        version.extractor = extraction.extractor
        version.extractor_version = extraction.extractor_version
        if extraction.page_count is not None:
            version.page_count = extraction.page_count
        if extraction.needs_ocr:
            await db.commit()
            await _mark(
                db,
                version.id,
                DocumentStatus.needs_ocr,
                code="needs_ocr",
                message=NEEDS_OCR_MESSAGE,
                event="document.failed",
            )
            return
        if not extraction.pages:
            raise ExtractionError("no_text", "No text could be found in this file.")
        db.add_all(
            DocumentPage(
                workspace_id=version.workspace_id,
                document_version_id=version.id,
                page_number=page.number,
                heading_path=page.heading_label,
                text=page.text,
                char_count=len(page.text),
            )
            for page in extraction.pages
        )

    version.status = DocumentStatus.chunking
    await db.commit()

    pages = await docs_repo.load_pages(db, version.id)
    config = chunking_config_for(workspace)
    drafts = await asyncio.to_thread(chunk_pages, pages, config)
    if not drafts:
        raise ExtractionError("no_text", "No text could be found in this file.")
    async with heartbeat(ctx, job.id):
        await docs_repo.replace_chunks(
            db, document=document, version=version, drafts=drafts, fts_config=workspace.fts_config
        )

    version.chunk_count = len(drafts)
    version.chunking_config = config.as_dict()
    version.status = DocumentStatus.indexed
    version.error_code = version.error_message = None
    version.indexed_at = utcnow()
    current = (
        await db.get(DocumentVersion, document.current_version_id)
        if document.current_version_id
        else None
    )
    if current is None or version.version_number >= current.version_number:
        document.current_version_id = version.id
    system_repo.add_event(
        db,
        workspace_id=document.workspace_id,
        event_type="document.indexed",
        payload={
            "document_id": str(document.id),
            "version_id": str(version.id),
            "chunk_count": len(drafts),
        },
    )
    await db.commit()
    log.info("document_indexed", document_id=str(document.id), chunks=len(drafts))


async def ingest_document(job: Job, ctx: WorkerContext) -> None:
    workspace_id, version_id = _ids(job, "version_id")
    async with ctx.sessionmaker() as db:
        await set_tenant(db, workspace_id=workspace_id, user_id=None)
        version = await db.get(DocumentVersion, version_id)
        document = await db.get(Document, version.document_id) if version else None
        workspace = await ws_repo.get_workspace(db, workspace_id)
        if version is None or document is None or workspace is None or document.deleted_at:
            log.info("ingest_skipped", version_id=str(version_id))
            return
        try:
            await _process(db, ctx, job, workspace, document, version)
        except ExtractionError as exc:
            await db.rollback()
            await _mark(
                db,
                version_id,
                DocumentStatus.failed,
                code=exc.code,
                message=exc.message,
                event="document.failed",
            )
        except Exception:
            await db.rollback()
            if job.attempts >= job.max_attempts:
                await _mark(
                    db,
                    version_id,
                    DocumentStatus.failed,
                    code="internal_error",
                    message=INTERNAL_MESSAGE,
                    event="document.failed",
                )
            else:
                await _mark(db, version_id, DocumentStatus.queued, message=RETRYING_MESSAGE)
            raise


async def purge_document(job: Job, ctx: WorkerContext) -> None:
    """Permanently remove a soft-deleted document: rows (versions, pages, chunks) and files."""
    workspace_id, document_id = _ids(job, "document_id")
    async with ctx.sessionmaker() as db:
        await set_tenant(db, workspace_id=workspace_id, user_id=None)
        document = await db.get(Document, document_id)
        if document is None or document.deleted_at is None:
            return  # already purged, or restored
        keys = await docs_repo.storage_keys(db, document_id)
        await docs_repo.delete_document(db, document_id)
        system_repo.add_audit(
            db,
            action="document.purged",
            workspace_id=workspace_id,
            target_type="document",
            target_id=str(document_id),
            details={"files": len(keys)},
        )
        await db.commit()
    for key in keys:
        ctx.storage.delete(key)
