"""Document queries. Every query filters by workspace_id explicitly; RLS is the second line."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Literal

from sqlalchemy import Select, and_, delete, func, insert, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.ids import uuid7
from app.ingestion.chunking import ChunkDraft, PageText
from app.ingestion.extractors.base import HEADING_SEPARATOR
from app.models import IN_PROGRESS, Chunk, Document, DocumentPage, DocumentStatus, DocumentVersion

StatusGroup = Literal["processing", "indexed", "attention"]
_GROUPS: dict[str, set[DocumentStatus]] = {
    "processing": set(IN_PROGRESS),
    "indexed": {DocumentStatus.indexed},
    "attention": {DocumentStatus.failed, DocumentStatus.needs_ocr},
}

Latest = aliased(DocumentVersion, name="latest")


# SQLAlchemy 2.1 types Select over the row's element types (TypeVarTuple), not a tuple.
def _live_documents(workspace_id: uuid.UUID) -> Select[Document, DocumentVersion]:
    return (
        select(Document, Latest)
        .join(Latest, Latest.id == Document.latest_version_id)
        .where(Document.workspace_id == workspace_id, Document.deleted_at.is_(None))
    )


async def list_documents(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    query: str | None,
    group: StatusGroup | None,
    offset: int,
    limit: int,
) -> tuple[list[tuple[Document, DocumentVersion]], int]:
    stmt = _live_documents(workspace_id)
    if query:
        pattern = f"%{query.replace('%', r'\%').replace('_', r'\_')}%"
        stmt = stmt.where(
            or_(Document.title.ilike(pattern), Latest.original_filename.ilike(pattern))
        )
    if group:
        stmt = stmt.where(Latest.status.in_(_GROUPS[group]))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.execute(stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit))
    return [(d, v) for d, v in rows], total


async def get_document(
    db: AsyncSession, workspace_id: uuid.UUID, document_id: uuid.UUID
) -> tuple[Document, DocumentVersion] | None:
    row = (
        await db.execute(_live_documents(workspace_id).where(Document.id == document_id))
    ).first()
    return (row[0], row[1]) if row else None


async def list_versions(
    db: AsyncSession, workspace_id: uuid.UUID, document_id: uuid.UUID
) -> list[DocumentVersion]:
    result = await db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document_id,
        )
        .order_by(DocumentVersion.version_number.desc())
    )
    return list(result.scalars())


async def get_version(
    db: AsyncSession, workspace_id: uuid.UUID, version_id: uuid.UUID
) -> DocumentVersion | None:
    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.workspace_id == workspace_id, DocumentVersion.id == version_id
        )
    )
    return result.scalar_one_or_none()


async def find_duplicate(
    db: AsyncSession, workspace_id: uuid.UUID, content_hash: str
) -> Document | None:
    """A live document whose current or latest version has exactly this content."""
    result = await db.execute(
        select(Document)
        .join(
            DocumentVersion,
            and_(
                DocumentVersion.document_id == Document.id,
                or_(
                    DocumentVersion.id == Document.current_version_id,
                    DocumentVersion.id == Document.latest_version_id,
                ),
            ),
        )
        .where(
            Document.workspace_id == workspace_id,
            Document.deleted_at.is_(None),
            DocumentVersion.content_hash == content_hash,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_live(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.workspace_id == workspace_id, Document.deleted_at.is_(None))
        )
        or 0
    )


async def next_version_number(db: AsyncSession, document_id: uuid.UUID) -> int:
    current = await db.scalar(
        select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
    )
    return int(current or 0) + 1


async def status_counts(db: AsyncSession, workspace_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(Latest.status, func.count())
        .select_from(Document)
        .join(Latest, Latest.id == Document.latest_version_id)
        .where(Document.workspace_id == workspace_id, Document.deleted_at.is_(None))
        .group_by(Latest.status)
    )
    by_status = {status: n for status, n in rows}
    return {
        "total": sum(by_status.values()),
        **{
            group: sum(by_status.get(s, 0) for s in statuses) for group, statuses in _GROUPS.items()
        },
    }


async def page_count(db: AsyncSession, version_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(DocumentPage)
            .where(DocumentPage.document_version_id == version_id)
        )
        or 0
    )


async def load_pages(db: AsyncSession, version_id: uuid.UUID) -> list[PageText]:
    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_version_id == version_id)
        .order_by(DocumentPage.page_number)
    )
    return [
        PageText(
            number=p.page_number,
            text=p.text,
            heading_path=tuple(p.heading_path.split(HEADING_SEPARATOR)) if p.heading_path else (),
        )
        for p in result.scalars()
    ]


async def replace_chunks(
    db: AsyncSession,
    *,
    document: Document,
    version: DocumentVersion,
    drafts: Sequence[ChunkDraft],
    fts_config: str,
) -> None:
    await db.execute(delete(Chunk).where(Chunk.document_version_id == version.id))
    if drafts:
        await db.execute(
            insert(Chunk),
            [
                {
                    "id": uuid7(),
                    "workspace_id": document.workspace_id,
                    "document_id": document.id,
                    "document_version_id": version.id,
                    "collection_id": document.collection_id,
                    "chunk_index": d.index,
                    "page_start": d.page_start,
                    "page_end": d.page_end,
                    "section_title": d.section_title,
                    "char_start": d.char_start,
                    "char_end": d.char_end,
                    "text": d.text,
                    "token_count": d.token_count,
                    "content_hash": d.content_hash,
                }
                for d in drafts
            ],
        )
    # Keyword index: section titles weigh more than body text.
    await db.execute(
        text(
            "UPDATE chunks SET tsv = "
            "setweight(to_tsvector(CAST(:cfg AS regconfig), coalesce(section_title, '')), 'A') || "
            "setweight(to_tsvector(CAST(:cfg AS regconfig), text), 'B') "
            "WHERE document_version_id = :vid"
        ),
        {"cfg": fts_config, "vid": version.id},
    )


async def list_chunks(
    db: AsyncSession, workspace_id: uuid.UUID, version_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[Chunk], int]:
    base = select(Chunk).where(
        Chunk.workspace_id == workspace_id, Chunk.document_version_id == version_id
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.execute(base.order_by(Chunk.chunk_index).offset(offset).limit(limit))
    return list(rows.scalars()), total


async def storage_keys(db: AsyncSession, document_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(DocumentVersion.storage_key).where(DocumentVersion.document_id == document_id)
    )
    return list(result.scalars())


async def delete_document(db: AsyncSession, document_id: uuid.UUID) -> None:
    await db.execute(delete(Document).where(Document.id == document_id))
