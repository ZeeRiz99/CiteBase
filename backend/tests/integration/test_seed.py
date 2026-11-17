"""The labeled demo seed: one verified account, samples indexed through the real pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import Settings
from app.services.demo import DEMO_WORKSPACE, sample_files, seed_demo
from tests.conftest import Api, Mailbox


def write_samples(folder: Path) -> list[Path]:
    (folder / "README.txt").write_text("DEMO DATA: not uploaded")
    (folder / "Returns Policy.md").write_text(
        "# Returns policy\n\nDEMO DATA.\n\n## Time limits\n\n"
        "Items can be returned within 30 days of delivery.\n"
    )
    (folder / "Support Guide.txt").write_text(
        "DEMO DATA. Support is open Monday to Friday, 9:00 to 17:00.\n"
    )
    (folder / "notes.csv").write_text("not,an,allowed,type\n")
    return sample_files(folder)


async def test_seed_creates_a_verified_demo_workspace_once(
    app: FastAPI, settings: Settings, api: Api, mailbox: Mailbox, tmp_path: Path, owner_engine: Any
) -> None:
    files = write_samples(tmp_path)
    assert [f.name for f in files] == ["Returns Policy.md", "Support Guide.txt"]

    async with app.state.sessionmaker() as db:
        result = await seed_demo(db, settings, app.state.storage, files)
    assert result.created and result.password and len(result.password) >= 16
    assert result.uploaded == ["Returns Policy.md", "Support Guide.txt"] and not result.rejected
    await mailbox.drain()  # the real ingestion jobs
    assert mailbox.sender.outbox == []  # no verification email for the demo account

    login = await api.login(result.email, result.password)
    assert login.status_code == 200, login.text
    me = (await api.get("/api/v1/auth/me")).json()
    assert me["user"]["email_verified"] is True and me["workspace"]["name"] == DEMO_WORKSPACE
    docs = (await api.get("/api/v1/documents")).json()
    assert sorted(d["latest"]["status"] for d in docs["items"]) == ["indexed", "indexed"]

    async with app.state.sessionmaker() as db:
        again = await seed_demo(db, settings, app.state.storage, files)
    assert not again.created and again.password is None
    with owner_engine.begin() as conn:
        users = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
    assert users == 1
