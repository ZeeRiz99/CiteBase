"""Developer command line.

    python -m app.cli ask "How many days of leave do new hires get?" --email you@example.com --trace
    python -m app.cli reindex --email you@example.com

The workspace is resolved from the user's membership (row-level security stays in force: the CLI
acts as that user, exactly like the API).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import textwrap

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_sessionmaker, set_tenant
from app.models import Document, DocumentStatus, DocumentVersion, User, Workspace
from app.rag.factory import build_engine
from app.repositories import system as system_repo
from app.repositories import workspaces as ws_repo


async def _workspace_for(db, email: str) -> Workspace:  # type: ignore[no-untyped-def]
    user = (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
    if user is None:
        sys.exit(f"No user with email {email}")
    await set_tenant(db, workspace_id=None, user_id=user.id)
    membership = await ws_repo.first_membership(db, user.id)
    if membership is None:
        sys.exit(f"{email} has no workspace")
    await set_tenant(db, workspace_id=membership.workspace_id, user_id=user.id)
    workspace = await ws_repo.get_workspace(db, membership.workspace_id)
    assert workspace is not None
    return workspace


async def ask(question: str, email: str, show_trace: bool) -> None:
    settings = get_settings()
    engine = create_engine(settings, null_pool=True)
    maker = create_sessionmaker(engine)
    async with maker() as db, httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http:
        workspace = await _workspace_for(db, email)
        rag = build_engine(db, settings, workspace, http)
        result = await rag.answer(question)
    await engine.dispose()

    print(f"\nQ: {question}")
    print(
        f"Evidence: {result.evidence}"
        + (f"   (refused: {result.refusal_reason})" if result.refused else "")
    )
    print("\n" + textwrap.fill(result.text, 100) + "\n")
    for source in result.cited_sources:
        print(f"  [{source.number}] {source.document_title} - {source.location}")
    if show_trace:
        print("\nTrace:")
        print(json.dumps(result.trace(), indent=2, default=str))


async def reindex(email: str) -> None:
    """Re-run ingestion for every live document's latest version (e.g. after a model change)."""
    settings = get_settings()
    engine = create_engine(settings, null_pool=True)
    maker = create_sessionmaker(engine)
    async with maker() as db:
        workspace = await _workspace_for(db, email)
        rows = await db.execute(
            select(DocumentVersion)
            .join(Document, Document.latest_version_id == DocumentVersion.id)
            .where(Document.workspace_id == workspace.id, Document.deleted_at.is_(None))
        )
        versions = list(rows.scalars())
        for version in versions:
            version.status = DocumentStatus.queued
            system_repo.enqueue_job(
                db,
                job_type="ingest",
                workspace_id=workspace.id,
                payload={"version_id": str(version.id)},
                max_attempts=3,
            )
        await db.commit()
    await engine.dispose()
    print(f"Queued {len(versions)} document(s) for re-indexing in {workspace.name}.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="citebase")
    sub = parser.add_subparsers(dest="command", required=True)
    p_ask = sub.add_parser("ask", help="answer a question from a workspace's documents")
    p_ask.add_argument("question")
    p_ask.add_argument("--email", required=True, help="a member of the workspace")
    p_ask.add_argument("--trace", action="store_true", help="print retrieval and gate details")
    p_re = sub.add_parser("reindex", help="re-chunk and re-embed all documents of a workspace")
    p_re.add_argument("--email", required=True)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging("WARNING", json_output=settings.environment != "development")
    if args.command == "ask":
        asyncio.run(ask(args.question, args.email, args.trace))
    else:
        asyncio.run(reindex(args.email))


if __name__ == "__main__":
    main()
