"""Dépôt manuel d'une archive (texte)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import error, require_role
from app.db.session import get_session
from app.models import RawText, Source, User
from app.schemas.archive import ArchiveCreate, ArchiveOut
from app.services.audit import audit

router = APIRouter(prefix="/archives", tags=["archives"])


@router.post("", response_model=ArchiveOut, status_code=201, summary="Déposer un texte (il suivra le pipeline de nettoyage)")
async def deposit(body: ArchiveCreate, user: User = Depends(require_role("reviewer")),
                  session: AsyncSession = Depends(get_session)):
    src = (await session.execute(select(Source).where(Source.id_source == body.id_source, Source.id_org == user.id_org))).scalar_one_or_none()
    if src is None:
        raise error(404, "NOT_FOUND", "Source introuvable")
    raw = RawText(title=body.title, content=body.content, language=body.language, creator=body.creator,
                  region=body.region, date_origin=body.date_origin, media_type="text", status="pending",
                  id_source=src.id_source)
    session.add(raw)
    await session.flush()
    audit(session, user.id_user, "archive.deposit", "texte_brut", raw.id_raw, {"id_source": src.id_source})
    await session.commit()
    return ArchiveOut(id_raw=raw.id_raw, status="pending",
                      message="Texte déposé. Il sera nettoyé par le pipeline (preprocessing.process) avant la relecture.")
