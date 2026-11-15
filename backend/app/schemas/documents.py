from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import Document, DocumentStatus, DocumentVersion


class VersionOut(BaseModel):
    id: uuid.UUID
    version_number: int
    original_filename: str
    file_ext: str
    size_bytes: int
    page_count: int | None
    status: DocumentStatus
    error_code: str | None
    error_message: str | None
    chunk_count: int
    is_current: bool
    created_at: datetime
    indexed_at: datetime | None

    @classmethod
    def build(cls, version: DocumentVersion, current_id: uuid.UUID | None) -> VersionOut:
        return cls(
            id=version.id,
            version_number=version.version_number,
            original_filename=version.original_filename,
            file_ext=version.file_ext,
            size_bytes=version.size_bytes,
            page_count=version.page_count,
            status=version.status,
            error_code=version.error_code,
            error_message=version.error_message,
            chunk_count=version.chunk_count,
            is_current=version.id == current_id,
            created_at=version.created_at,
            indexed_at=version.indexed_at,
        )


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    collection_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    has_current_version: bool
    latest: VersionOut

    @classmethod
    def build(cls, document: Document, latest: DocumentVersion) -> DocumentOut:
        return cls(
            id=document.id,
            title=document.title,
            collection_id=document.collection_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
            has_current_version=document.current_version_id is not None,
            latest=VersionOut.build(latest, document.current_version_id),
        )


class DocumentDetail(DocumentOut):
    versions: list[VersionOut]


class Limits(BaseModel):
    max_file_mb: int
    max_documents: int
    document_count: int
    allowed_extensions: list[str]


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int
    limits: Limits


class ChunkOut(BaseModel):
    id: uuid.UUID
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    char_start: int
    char_end: int
    token_count: int
    text: str


class ChunkList(BaseModel):
    items: list[ChunkOut]
    total: int
    page: int
    page_size: int
    version_id: uuid.UUID | None


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_default: bool


class DocumentCounts(BaseModel):
    total: int
    processing: int
    indexed: int
    attention: int


class DashboardSummary(BaseModel):
    documents: DocumentCounts
