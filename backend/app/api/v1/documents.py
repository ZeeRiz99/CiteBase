from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentContext, DbDep, SettingsDep, require_role
from app.models import Role
from app.providers.storage import Storage
from app.repositories import workspaces as ws_repo
from app.repositories.documents import StatusGroup
from app.schemas.auth import MessageResponse
from app.schemas.documents import (
    ChunkList,
    ChunkOut,
    CollectionOut,
    DashboardSummary,
    DocumentCounts,
    DocumentDetail,
    DocumentList,
    DocumentOut,
    Limits,
    VersionOut,
)
from app.services.documents import ALLOWED_TYPES, DocumentService

router = APIRouter(tags=["documents"])

Viewer = Annotated[CurrentContext, Depends(require_role(Role.viewer))]
Member = Annotated[CurrentContext, Depends(require_role(Role.member))]
Admin = Annotated[CurrentContext, Depends(require_role(Role.admin))]
Owner = Annotated[CurrentContext, Depends(require_role(Role.owner))]


def _service(
    request: Request, db: DbDep, settings: SettingsDep, ctx: CurrentContext
) -> DocumentService:
    storage: Storage = request.app.state.storage
    return DocumentService(db, settings, storage, ctx)


@router.get("/collections")
async def list_collections(ctx: Viewer, db: DbDep) -> list[CollectionOut]:
    rows = await ws_repo.list_collections(db, ctx.workspace.id)
    return [
        CollectionOut(id=c.id, name=c.name, description=c.description, is_default=c.is_default)
        for c in rows
    ]


@router.get("/documents")
async def list_documents(
    request: Request,
    ctx: Viewer,
    db: DbDep,
    settings: SettingsDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status_group: Annotated[StatusGroup | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DocumentList:
    service = _service(request, db, settings, ctx)
    rows, total, live = await service.list_documents(
        query=q.strip() if q else None, group=status_group, page=page, page_size=page_size
    )
    return DocumentList(
        items=[DocumentOut.build(d, v) for d, v in rows],
        total=total,
        page=page,
        page_size=page_size,
        limits=Limits(
            max_file_mb=service.max_file_mb,
            max_documents=ctx.workspace.max_documents,
            document_count=live,
            allowed_extensions=sorted(ALLOWED_TYPES),
        ),
    )


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    ctx: Member,
    db: DbDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    collection_id: Annotated[uuid.UUID | None, Form()] = None,
) -> DocumentOut:
    document, version = await _service(request, db, settings, ctx).upload(file, collection_id)
    return DocumentOut.build(document, version)


@router.get("/documents/{document_id}")
async def get_document(
    request: Request, document_id: uuid.UUID, ctx: Viewer, db: DbDep, settings: SettingsDep
) -> DocumentDetail:
    document, latest, versions = await _service(request, db, settings, ctx).detail(document_id)
    base = DocumentOut.build(document, latest)
    return DocumentDetail(
        **base.model_dump(),
        versions=[VersionOut.build(v, document.current_version_id) for v in versions],
    )


@router.post("/documents/{document_id}/versions", status_code=status.HTTP_201_CREATED)
async def upload_version(
    request: Request,
    document_id: uuid.UUID,
    ctx: Member,
    db: DbDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
) -> DocumentOut:
    document, version = await _service(request, db, settings, ctx).upload_version(document_id, file)
    return DocumentOut.build(document, version)


@router.post("/documents/{document_id}/retry")
async def retry_document(
    request: Request, document_id: uuid.UUID, ctx: Member, db: DbDep, settings: SettingsDep
) -> DocumentOut:
    document, version = await _service(request, db, settings, ctx).retry(document_id)
    return DocumentOut.build(document, version)


@router.delete("/documents/{document_id}")
async def delete_document(
    request: Request, document_id: uuid.UUID, ctx: Admin, db: DbDep, settings: SettingsDep
) -> MessageResponse:
    await _service(request, db, settings, ctx).delete(document_id)
    days = settings.retention_days
    return MessageResponse(
        message=f"Document deleted. It will be permanently removed after {days} days."
    )


@router.post("/documents/{document_id}/purge", status_code=status.HTTP_202_ACCEPTED)
async def purge_document(
    request: Request, document_id: uuid.UUID, ctx: Owner, db: DbDep, settings: SettingsDep
) -> MessageResponse:
    await _service(request, db, settings, ctx).purge_now(document_id)
    return MessageResponse(message="Document is being permanently removed.")


@router.get("/documents/{document_id}/file", response_model=None)
async def download_file(
    request: Request,
    document_id: uuid.UUID,
    ctx: Viewer,
    db: DbDep,
    settings: SettingsDep,
    version_id: uuid.UUID | None = None,
) -> FileResponse:
    target = await _service(request, db, settings, ctx).download(document_id, version_id)
    return FileResponse(
        target.path,
        media_type=target.mime_type,
        filename=target.filename,
        content_disposition_type="inline"
        if target.mime_type == "application/pdf"
        else "attachment",
        headers={
            # Never let a served file run script in our origin.
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/documents/{document_id}/chunks")
async def list_chunks(
    request: Request,
    document_id: uuid.UUID,
    ctx: Viewer,
    db: DbDep,
    settings: SettingsDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ChunkList:
    items, total, version_id = await _service(request, db, settings, ctx).chunks(
        document_id, page=page, page_size=page_size
    )
    return ChunkList(
        items=[
            ChunkOut(
                id=c.id,
                chunk_index=c.chunk_index,
                page_start=c.page_start,
                page_end=c.page_end,
                section_title=c.section_title,
                char_start=c.char_start,
                char_end=c.char_end,
                token_count=c.token_count,
                text=c.text,
            )
            for c in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        version_id=version_id,
    )


@router.get("/dashboard/summary")
async def dashboard_summary(
    request: Request, ctx: Viewer, db: DbDep, settings: SettingsDep
) -> DashboardSummary:
    counts = await _service(request, db, settings, ctx).counts()
    return DashboardSummary(documents=DocumentCounts(**counts))
