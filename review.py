"""File de relecture : consulter, corriger, valider ou rejeter les textes nettoyés."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams, error, require_role
from app.db.session import get_session
from app.models import CleanedText, Corpus, RawText, Review, Source, User
from app.schemas.common import Page
from app.schemas.review import (ContentUpdate, Decision, DecisionOut, QueueItem, ReviewDetail, ReviewOut,
                                SourceBrief)
from app.services.audit import audit
from app.services.text_utils import content_hash, words

router = APIRouter(prefix="/review", tags=["relecture"])


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def _load(session: AsyncSession, id_cleaned: int, org_id: int, lock: bool = False):
    """Texte nettoyé de l'organisation (sinon 404, même si l'identifiant existe chez une autre organisation)."""
    if lock:
        await session.execute(select(CleanedText.id_cleaned).where(CleanedText.id_cleaned == id_cleaned).with_for_update())
    row = (await session.execute(
        select(CleanedText, RawText, Source)
        .join(RawText, RawText.id_raw == CleanedText.id_raw).join(Source, Source.id_source == RawText.id_source)
        .where(CleanedText.id_cleaned == id_cleaned, Source.id_org == org_id))).first()
    if row is None:
        raise error(404, "NOT_FOUND", "Texte introuvable")
    return row


@router.get("/queue", response_model=Page[QueueItem], summary="Textes en attente de relecture")
async def queue(p: PageParams = Depends(), q: str | None = Query(None, description="Mot recherché dans le titre ou le texte"),
                min_score: float | None = Query(None, ge=0, le=1), max_score: float | None = Query(None, ge=0, le=1),
                order: Literal["oldest", "score_asc", "score_desc"] = "oldest",
                user: User = Depends(require_role("reviewer")), session: AsyncSession = Depends(get_session)):
    conds = [Source.id_org == user.id_org, CleanedText.status == "ready_for_review"]
    if q:
        conds.append(or_(RawText.title.ilike(_like(q), escape="\\"), CleanedText.content.ilike(_like(q), escape="\\")))
    if min_score is not None:
        conds.append(CleanedText.quality_score >= min_score)
    if max_score is not None:
        conds.append(CleanedText.quality_score <= max_score)
    joins = lambda s: (s.join(RawText, RawText.id_raw == CleanedText.id_raw)  # noqa: E731
                       .join(Source, Source.id_source == RawText.id_source))
    total = (await session.execute(joins(select(func.count()).select_from(CleanedText)).where(*conds))).scalar_one()
    order_by = {"oldest": [CleanedText.created_at, CleanedText.id_cleaned],
                "score_asc": [CleanedText.quality_score.asc(), CleanedText.id_cleaned],
                "score_desc": [CleanedText.quality_score.desc(), CleanedText.id_cleaned]}[order]
    rows = (await session.execute(joins(select(CleanedText, RawText, Source)).where(*conds)
                                  .order_by(*order_by).offset(p.offset).limit(p.size))).all()
    items = [QueueItem(id_cleaned=c.id_cleaned, title=r.title, word_count=c.word_count,
                       quality_score=float(c.quality_score) if c.quality_score is not None else None,
                       source=s.name, created_at=c.created_at) for c, r, s in rows]
    return Page(items=items, total=total, page=p.page, size=p.size)


@router.get("/{id_cleaned}", response_model=ReviewDetail, summary="Détail d'un texte à relire")
async def detail(id_cleaned: int, user: User = Depends(require_role("reviewer")), session: AsyncSession = Depends(get_session)):
    c, r, s = await _load(session, id_cleaned, user.id_org)
    reviews = (await session.execute(
        select(Review, User.email).join(User, User.id_user == Review.id_user)
        .where(Review.id_cleaned == id_cleaned).order_by(Review.created_at, Review.id_review))).all()
    return ReviewDetail(
        id_cleaned=c.id_cleaned, id_raw=r.id_raw, status=c.status, title=r.title, content=c.content,
        word_count=c.word_count, quality_score=float(c.quality_score) if c.quality_score is not None else None,
        language=r.language, creator=r.creator, region=r.region, date_origin=r.date_origin, origin_url=r.origin_url,
        source=SourceBrief(id_source=s.id_source, name=s.name, url=s.url, license=s.license),
        reviews=[ReviewOut(id_review=rv.id_review, action=rv.action, comment=rv.comment, created_at=rv.created_at,
                           reviewer=email) for rv, email in reviews])


@router.patch("/{id_cleaned}/content", response_model=ReviewDetail, summary="Corriger le texte avant décision")
async def edit_content(id_cleaned: int, body: ContentUpdate, user: User = Depends(require_role("reviewer")),
                       session: AsyncSession = Depends(get_session)):
    c, r, s = await _load(session, id_cleaned, user.id_org, lock=True)
    if c.status != "ready_for_review":
        raise error(409, "NOT_PENDING", "Seuls les textes en attente de relecture peuvent être corrigés")
    new_hash = content_hash(body.content)
    clash = (await session.execute(
        select(CleanedText.id_cleaned).join(RawText, RawText.id_raw == CleanedText.id_raw)
        .join(Source, Source.id_source == RawText.id_source)
        .where(Source.id_org == user.id_org, CleanedText.dedupe_hash == new_hash,
               CleanedText.id_cleaned != id_cleaned, CleanedText.status != "rejected"))).first()
    if clash:
        raise error(409, "DUPLICATE_CONTENT", f"Ce contenu est identique au texte #{clash[0]} (règle RG16)")
    old_count = c.word_count
    c.content, c.dedupe_hash, c.word_count = body.content, new_hash, len(words(body.content))
    audit(session, user.id_user, "review.edit", "texte_nettoye", c.id_cleaned, {"words": [old_count, c.word_count]})
    await session.commit()
    return await detail(id_cleaned, user, session)


@router.post("/{id_cleaned}/decision", response_model=DecisionOut, status_code=201,
             summary="Valider, rejeter ou commenter un texte")
async def decide(id_cleaned: int, body: Decision, user: User = Depends(require_role("reviewer")),
                 session: AsyncSession = Depends(get_session)):
    c, r, s = await _load(session, id_cleaned, user.id_org, lock=True)
    if body.action in ("validate", "reject") and c.status != "ready_for_review":
        raise error(409, "NOT_PENDING", "Ce texte a déjà été validé ou rejeté")
    review = Review(action=body.action, comment=(body.comment or "").strip() or None, id_user=user.id_user,
                    id_cleaned=id_cleaned)
    session.add(review)
    await session.flush()
    id_corpus = None
    try:
        if body.action == "validate":
            corpus = Corpus(genre=body.genre, access_level=body.access_level, id_cleaned=id_cleaned)
            session.add(corpus)
            c.status = "validated"
            await session.flush()
            id_corpus = corpus.id_corpus
        elif body.action == "reject":
            c.status = "rejected"
        audit(session, user.id_user, f"review.{body.action}", "texte_nettoye", id_cleaned,
              {"id_review": review.id_review, "genre": body.genre, "access_level": body.access_level}
              if body.action == "validate" else {"id_review": review.id_review})
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise error(409, "ALREADY_VALIDATED", "Ce texte est déjà dans le corpus") from exc
    return DecisionOut(id_review=review.id_review, status=c.status, id_corpus=id_corpus)
