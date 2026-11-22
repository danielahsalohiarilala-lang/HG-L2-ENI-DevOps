"""Statistiques et journal d'audit de l'organisation (administrateur)."""
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams, require_role
from app.db.session import get_session
from app.models import (AuditLog, CleanedText, Corpus, RawText, Role, ScrapingJob, Source, User)
from app.schemas.common import Page

router = APIRouter(prefix="/admin", tags=["administration"])


class AuditItem(BaseModel):
    id_log: int
    action: str
    entity: str
    entity_id: int
    meta: dict[str, Any] | None
    created_at: Any
    user: str


@router.get("/stats", summary="Indicateurs de l'organisation")
async def stats(admin: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    org = admin.id_org

    async def grouped(stmt):
        return {k: n for k, n in (await session.execute(stmt)).all()}

    raw_join = lambda s: s.join(Source, Source.id_source == RawText.id_source)  # noqa: E731
    return {
        "users_by_role": await grouped(select(Role.code, func.count()).join(User, User.id_role == Role.id_role)
                                       .where(User.id_org == org).group_by(Role.code)),
        "sources": (await session.execute(select(func.count()).select_from(Source).where(Source.id_org == org))).scalar_one(),
        "raw_texts_by_status": await grouped(raw_join(select(RawText.status, func.count()).select_from(RawText))
                                             .where(Source.id_org == org).group_by(RawText.status)),
        "cleaned_texts_by_status": await grouped(
            raw_join(select(CleanedText.status, func.count()).select_from(CleanedText)
                     .join(RawText, RawText.id_raw == CleanedText.id_raw)).where(Source.id_org == org).group_by(CleanedText.status)),
        "corpus_by_genre": await grouped(
            raw_join(select(Corpus.genre, func.count()).select_from(Corpus)
                     .join(CleanedText, CleanedText.id_cleaned == Corpus.id_cleaned)
                     .join(RawText, RawText.id_raw == CleanedText.id_raw)).where(Source.id_org == org).group_by(Corpus.genre)),
        "jobs_by_status": await grouped(select(ScrapingJob.status, func.count()).select_from(ScrapingJob)
                                        .join(Source, Source.id_source == ScrapingJob.id_source)
                                        .where(Source.id_org == org).group_by(ScrapingJob.status)),
    }


@router.get("/audit", response_model=Page[AuditItem], summary="Journal d'audit de l'organisation")
async def audit_log(p: PageParams = Depends(), entity: str | None = Query(None), action: str | None = Query(None),
                    admin: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    org_users = select(User.id_user).where(User.id_org == admin.id_org)
    org_raw = select(RawText.id_raw).join(Source, Source.id_source == RawText.id_source).where(Source.id_org == admin.id_org)
    conds = [or_(AuditLog.id_user.in_(org_users),
                 and_(AuditLog.id_user.is_(None), AuditLog.entity == "texte_brut", AuditLog.entity_id.in_(org_raw)))]
    if entity:
        conds.append(AuditLog.entity == entity)
    if action:
        conds.append(AuditLog.action == action)
    total = (await session.execute(select(func.count()).select_from(AuditLog).where(*conds))).scalar_one()
    rows = (await session.execute(
        select(AuditLog, User.email).outerjoin(User, User.id_user == AuditLog.id_user).where(*conds)
        .order_by(AuditLog.id_log.desc()).offset(p.offset).limit(p.size))).all()
    items = [AuditItem(id_log=a.id_log, action=a.action, entity=a.entity, entity_id=a.entity_id, meta=a.meta,
                       created_at=a.created_at, user=email or "système") for a, email in rows]
    return Page(items=items, total=total, page=p.page, size=p.size)
