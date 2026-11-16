"""Document use cases for the API. Workspace and role come from the authenticated context."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentContext
from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.db.ids import uuid7
from app.ingestion.validation import (
    ALLOWED_TYPES,
    FileTooLarge,
    UploadRejected,
    extension_of,
    inspect_file,
    sanitize_filename,
)
from app.models import Chunk, Document, DocumentPage, DocumentStatus, DocumentVersion
from app.providers.storage import Storage
from app.repositories import documents as docs_repo
from app.repositories import system as system_repo
from app.repositories import workspaces as ws_repo
from app.repositories.documents import StatusGroup
from app.repositories.users import utcnow

READ_CHUNK = 1024 * 1024
INGEST_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class StoredUpload:
    key: str
    filename: str
    ext: str
    mime_type: str
    size_bytes: int
    content_hash: str
    page_count: int | None


@dataclass(frozen=True)
class DownloadTarget:
    path: Path
    filename: str
    mime_type: str


class DocumentService:
    def __init__(
        self, db: AsyncSession, settings: Settings, storage: Storage, ctx: CurrentContext
    ) -> None:
        self.db = db
        self.settings = settings
        self.storage = storage
        self.ctx = ctx
        self.workspace_id = ctx.workspace.id

    # ---- helpers -------------------------------------------------------------------------

    @property
    def max_file_mb(self) -> int:
        return min(self.settings.max_upload_mb, self.ctx.workspace.max_file_mb)

    async def _receive(self, upload: UploadFile) -> StoredUpload:
        """Stream the upload to a temp file (hashing as we go), validate it, then commit it."""
        filename = sanitize_filename(upload.filename or "")
        ext = extension_of(filename)
        limit = self.max_file_mb * 1024 * 1024
        temp = self.storage.temp_path()
        digest = hashlib.sha256()
        size = 0
        try:
            with temp.open("wb") as out:
                while chunk := await upload.read(READ_CHUNK):
                    size += len(chunk)
                    if size > limit:
                        raise FileTooLarge(
                            f"This file is larger than the {self.max_file_mb} MB limit."
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise UploadRejected("This file is empty.", code="empty_file")
            facts = await asyncio.to_thread(
                inspect_file, temp, ext, max_pdf_pages=self.settings.max_pdf_pages
            )
            key = self.storage.new_key(self.workspace_id)
            self.storage.commit_temp(temp, key)
        finally:
            temp.unlink(missing_ok=True)
        return StoredUpload(
            key=key,
            filename=filename,
            ext=facts.ext,
            mime_type=facts.mime_type,
            size_bytes=size,
            content_hash=digest.hexdigest(),
            page_count=facts.page_count,
        )

    async def _reject_duplicate(self, stored: StoredUpload) -> None:
        duplicate = await docs_repo.find_duplicate(self.db, self.workspace_id, stored.content_hash)
        if duplicate is not None:
            self.storage.delete(stored.key)
            raise Conflict(
                f'This file is already in your knowledge base as "{duplicate.title}".',
                code="duplicate_document",
                details={"document_id": str(duplicate.id)},
            )

    def _new_version(
        self, document: Document, stored: StoredUpload, number: int
    ) -> DocumentVersion:
        version = DocumentVersion(
            id=uuid7(),
            workspace_id=self.workspace_id,
            document_id=document.id,
            version_number=number,
            original_filename=stored.filename,
            storage_key=stored.key,
            mime_type=stored.mime_type,
            file_ext=stored.ext,
            size_bytes=stored.size_bytes,
            content_hash=stored.content_hash,
            page_count=stored.page_count,
            status=DocumentStatus.queued,
            created_by=self.ctx.user.id,
        )
        self.db.add(version)
        return version

    def _enqueue_ingest(self, version: DocumentVersion) -> None:
        system_repo.enqueue_job(
            self.db,
            job_type="ingest",
            workspace_id=self.workspace_id,
            payload={"version_id": str(version.id)},
            max_attempts=INGEST_MAX_ATTEMPTS,
        )

    async def _require(self, document_id: uuid.UUID) -> tuple[Document, DocumentVersion]:
        found = await docs_repo.get_document(self.db, self.workspace_id, document_id)
        if found is None:
            raise NotFound("Document not found.")
        return found

    # ---- use cases -----------------------------------------------------------------------

    async def upload(
        self, upload: UploadFile, collection_id: uuid.UUID | None
    ) -> tuple[Document, DocumentVersion]:
        workspace = self.ctx.workspace
        if await docs_repo.count_live(self.db, self.workspace_id) >= workspace.max_documents:
            raise Conflict(
                f"Your workspace has reached its limit of {workspace.max_documents} documents.",
                code="document_limit",
            )
        collections = await ws_repo.list_collections(self.db, self.workspace_id)
        if collection_id is None:
            collection = next((c for c in collections if c.is_default), None)
        else:
            collection = next((c for c in collections if c.id == collection_id), None)
        if collection is None:
            raise NotFound("Collection not found.")

        stored = await self._receive(upload)
        await self._reject_duplicate(stored)

        document = Document(
            id=uuid7(),
            workspace_id=self.workspace_id,
            collection_id=collection.id,
            title=Path(stored.filename).stem[:255] or stored.filename,
            created_by=self.ctx.user.id,
        )
        self.db.add(document)
        await self.db.flush()
        version = self._new_version(document, stored, 1)
        await self.db.flush()
        document.latest_version_id = version.id
        self._enqueue_ingest(version)
        system_repo.add_audit(
            self.db,
            action="document.uploaded",
            workspace_id=self.workspace_id,
            actor_user_id=self.ctx.user.id,
            target_type="document",
            target_id=str(document.id),
            details={"filename": stored.filename, "size_bytes": stored.size_bytes},
        )
        await self.db.commit()
        return document, version

    async def upload_version(
        self, document_id: uuid.UUID, upload: UploadFile
    ) -> tuple[Document, DocumentVersion]:
        document, latest = await self._require(document_id)
        if latest.status in (
            DocumentStatus.queued,
            DocumentStatus.extracting,
            DocumentStatus.chunking,
        ):
            raise Conflict(
                "The previous upload is still processing. Wait for it to finish.",
                code="version_in_progress",
            )
        stored = await self._receive(upload)
        await self._reject_duplicate(stored)
        number = await docs_repo.next_version_number(self.db, document.id)
        version = self._new_version(document, stored, number)
        await self.db.flush()
        document.latest_version_id = version.id
        self._enqueue_ingest(version)
        system_repo.add_audit(
            self.db,
            action="document.version_uploaded",
            workspace_id=self.workspace_id,
            actor_user_id=self.ctx.user.id,
            target_type="document",
            target_id=str(document.id),
            details={"version": number, "filename": stored.filename},
        )
        await self.db.commit()
        return document, version

    async def list_documents(
        self, *, query: str | None, group: StatusGroup | None, page: int, page_size: int
    ) -> tuple[list[tuple[Document, DocumentVersion]], int, int]:
        rows, total = await docs_repo.list_documents(
            self.db,
            self.workspace_id,
            query=query,
            group=group,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        live = await docs_repo.count_live(self.db, self.workspace_id)
        return rows, total, live

    async def detail(
        self, document_id: uuid.UUID
    ) -> tuple[Document, DocumentVersion, list[DocumentVersion]]:
        document, latest = await self._require(document_id)
        versions = await docs_repo.list_versions(self.db, self.workspace_id, document.id)
        return document, latest, versions

    async def retry(self, document_id: uuid.UUID) -> tuple[Document, DocumentVersion]:
        document, latest = await self._require(document_id)
        if latest.status != DocumentStatus.failed:
            raise Conflict(
                "Only documents that failed processing can be retried.", code="not_failed"
            )
        latest.status = DocumentStatus.queued
        latest.error_code = latest.error_message = None
        self._enqueue_ingest(latest)
        system_repo.add_audit(
            self.db,
            action="document.retried",
            workspace_id=self.workspace_id,
            actor_user_id=self.ctx.user.id,
            target_type="document",
            target_id=str(document.id),
        )
        await self.db.commit()
        return document, latest

    async def delete(self, document_id: uuid.UUID) -> None:
        """Soft delete: hidden from the UI and retrieval now, purged after the retention period."""
        document, _ = await self._require(document_id)
        now = utcnow()
        document.deleted_at = now
        document.purge_after = now + timedelta(days=self.settings.retention_days)
        job = system_repo.enqueue_job(
            self.db,
            job_type="purge_document",
            workspace_id=self.workspace_id,
            payload={"document_id": str(document.id)},
        )
        job.run_after = document.purge_after
        system_repo.add_audit(
            self.db,
            action="document.deleted",
            workspace_id=self.workspace_id,
            actor_user_id=self.ctx.user.id,
            target_type="document",
            target_id=str(document.id),
            details={"purge_after": document.purge_after.isoformat()},
        )
        await self.db.commit()

    async def purge_now(self, document_id: uuid.UUID) -> None:
        """Owner-only: delete and purge immediately (files, pages, chunks)."""
        document, _ = await self._require(document_id)
        document.deleted_at = document.purge_after = utcnow()
        system_repo.enqueue_job(
            self.db,
            job_type="purge_document",
            workspace_id=self.workspace_id,
            payload={"document_id": str(document.id)},
        )
        system_repo.add_audit(
            self.db,
            action="document.purge_requested",
            workspace_id=self.workspace_id,
            actor_user_id=self.ctx.user.id,
            target_type="document",
            target_id=str(document.id),
        )
        await self.db.commit()

    async def download(
        self, document_id: uuid.UUID, version_id: uuid.UUID | None
    ) -> DownloadTarget:
        document, latest = await self._require(document_id)
        if version_id is None:
            version_id = document.current_version_id or latest.id
        version = await docs_repo.get_version(self.db, self.workspace_id, version_id)
        if version is None or version.document_id != document.id:
            raise NotFound("Document version not found.")
        path = self.storage.local_path(version.storage_key)
        if not path.is_file():
            raise NotFound("The file for this version is no longer available.")
        return DownloadTarget(
            path=path, filename=version.original_filename, mime_type=version.mime_type
        )

    async def chunks(
        self, document_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[Chunk], int, uuid.UUID | None]:
        document, latest = await self._require(document_id)
        version_id = document.current_version_id or (
            latest.id if latest.status == DocumentStatus.indexed else None
        )
        if version_id is None:
            return [], 0, None
        items, total = await docs_repo.list_chunks(
            self.db, self.workspace_id, version_id, offset=(page - 1) * page_size, limit=page_size
        )
        return items, total, version_id

    async def counts(self) -> dict[str, int]:
        return await docs_repo.status_counts(self.db, self.workspace_id)

    async def chunk_context(self, chunk_id: uuid.UUID) -> ChunkContext:
        """A cited passage with its neighbours and page text, for the source viewer.

        Works for passages of older versions too (old answers cite them); deleted documents
        are gone.
        """
        chunk = await docs_repo.get_chunk(self.db, self.workspace_id, chunk_id)
        if chunk is None:
            raise NotFound("This passage is no longer available.")
        document, _latest = await self._require(chunk.document_id)
        version = await docs_repo.get_version(self.db, self.workspace_id, chunk.document_version_id)
        if version is None:
            raise NotFound("This passage is no longer available.")
        previous, following = await docs_repo.neighbor_chunks(self.db, chunk)
        pages = await docs_repo.pages_between(
            self.db, version.id, max(1, chunk.page_start - 1), chunk.page_end + 1
        )
        return ChunkContext(chunk, document, version, previous, following, pages)


@dataclass(frozen=True)
class ChunkContext:
    chunk: Chunk
    document: Document
    version: DocumentVersion
    previous: Chunk | None
    following: Chunk | None
    pages: list[DocumentPage]


__all__ = ["ALLOWED_TYPES", "ChunkContext", "DocumentService", "DownloadTarget"]
