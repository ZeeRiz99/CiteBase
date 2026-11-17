from fastapi import APIRouter

from app.api.v1 import auth, chat, documents, me, system, team

router = APIRouter(prefix="/api/v1")
router.include_router(system.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(documents.router)
router.include_router(chat.router)
router.include_router(team.router)
