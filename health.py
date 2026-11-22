"""Santé de l'application et aperçu de développement."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.models import CleanedText, Corpus, Organisation, RawText, Source, User

router = APIRouter()


@router.get("/health", tags=["système"], summary="Vérifie que l'API et la base répondent")
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"status": "error", "database": "down"}) from exc
    return {"status": "ok", "database": "up"}


@router.get("/dev/overview", tags=["développement"],
            summary="Nombre de lignes par table (désactivé hors développement)")
async def overview(session: AsyncSession = Depends(get_session)):
    if not get_settings().is_dev:
        raise HTTPException(status_code=404, detail="Not found")
    out = {}
    for label, model in [("organisations", Organisation), ("utilisateurs", User), ("sources", Source),
                         ("textes_bruts", RawText), ("textes_nettoyes", CleanedText), ("corpus", Corpus)]:
        out[label] = (await session.execute(select(func.count()).select_from(model))).scalar_one()
    return out
