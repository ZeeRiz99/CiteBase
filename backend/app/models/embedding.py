"""Embedding profiles (catalog) and per-profile chunk vectors."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmbeddingProfileRow(Base):
    """Mirror of app/rag/profiles.py PROFILES (seeded by migration 0003)."""

    __tablename__ = "embedding_profiles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    max_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChunkEmbedding(Base):
    """One vector per (chunk, profile). Partial HNSW indexes per profile live in migrations."""

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        Index("ix_chunk_embeddings_cache", "workspace_id", "profile_id", "content_hash"),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    profile_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("embedding_profiles.id"), primary_key=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
