"""Documents, versions, extracted pages and chunks. All tenant-scoped (RLS)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class DocumentStatus(enum.StrEnum):
    queued = "queued"
    extracting = "extracting"
    chunking = "chunking"
    embedding = "embedding"  # used from Phase 3
    indexed = "indexed"
    failed = "failed"
    needs_ocr = "needs_ocr"


IN_PROGRESS = {
    DocumentStatus.queued,
    DocumentStatus.extracting,
    DocumentStatus.chunking,
    DocumentStatus.embedding,
}


class Document(UUIDPk, Timestamps, Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_workspace_live", "workspace_id", "deleted_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # The version retrieval serves. Switches only when a newer version finishes indexing.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", use_alter=True, ondelete="SET NULL")
    )
    # The most recent upload, which may still be processing or may have failed.
    latest_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", use_alter=True, ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentVersion(UUIDPk, Timestamps, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_number"),
        Index("ix_document_versions_workspace_hash", "workspace_id", "content_hash"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_ext: Mapped[str] = mapped_column(String(10), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        nullable=False,
        server_default=DocumentStatus.queued.value,
    )
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    extractor: Mapped[str | None] = mapped_column(String(40))
    extractor_version: Mapped[str | None] = mapped_column(String(40))
    chunking_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentPage(UUIDPk, Base):
    """Extracted text per PDF page, or per section for DOCX/MD/TXT. Re-chunking reads this."""

    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_version_id", "page_number", name="uq_document_pages_number"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)


class Chunk(UUIDPk, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_chunks_version_index"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_chunks_workspace_id", "workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Page numbers for PDFs; section ordinals for DOCX/MD/TXT (see document_pages).
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str | None] = mapped_column(Text)
    # Offsets into document_pages.text: char_start in page_start, char_end in page_end.
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tsv: Mapped[Any | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
