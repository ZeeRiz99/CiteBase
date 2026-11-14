from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbDep, SettingsDep

router = APIRouter(tags=["system"])


class Branding(BaseModel):
    product_name: str
    tagline: str


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
async def readyz(db: DbDep) -> dict[str, str] | JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return {"status": "ok", "database": "up"}


@router.get("/public/branding")
async def branding(settings: SettingsDep) -> Branding:
    return Branding(product_name=settings.product_name, tagline=settings.product_tagline)
