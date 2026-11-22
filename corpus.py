"""Consultation et correction du corpus validé."""
import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ROLE_RANK, PageParams, error, require_role, role_of
from app.db.session import get_session
from app.models import CleanedText, Corpus, CorpusRevision, RawText, Source, User
from app.schemas.common import Page
from app.schemas.corpus import CorpusDetail, CorpusItem, CorpusUpdate, RevisionOut
from app.schemas.review import SourceBrief
from app.services.audit import audit
from app.services.text_utils import words

router = APIRouter(prefix="/corpus", tags=["corpus"])


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def visible(user: User):
    """Règle d'accès : public = tous les utilisateurs connectés ; restricted = membres de l'organisation ;
    private = relecteurs et administrateurs de l'organisation."""
    own_levels = true() if ROLE_RANK[role_of(user)] >= ROLE_RANK["reviewer"] else Corpus.access_level.in_(("public", "restricted"))
    return or_(Corpus.access_level == "public", and_(Source.id_org == user.id_org, own_levels))


def _joined(stmt):
    return (stmt.join(CleanedText, CleanedText.id_cleaned == Corpus.id_cleaned)
            .join(RawText, RawText.id_raw == CleanedText.id_raw).join(Source, Source.id_source == RawText.id_source))


async def _latest_contents(session: AsyncSession, corpus_ids: list[int]) -> dict[int, str]:
    if not corpus_ids:
        return {}
    last = (select(func.max(CorpusRevision.id_revision)).where(CorpusRevision.id_corpus.in_(corpus_ids))
            .group_by(CorpusRevision.id_corpus))
    rows = (await session.execute(select(CorpusRevision.id_corpus, CorpusRevision.content)
                                  .where(CorpusRevision.id_revision.in_(last)))).all()
    return {i: c for i, c in rows}


def _excerpt(text: str, n: int = 200) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= n else flat[:n].rstrip() + "…"


@router.get("", response_model=Page[CorpusItem], summary="Catalogue du corpus (filtres et recherche)")
async def list_corpus(p: PageParams = Depends(), genre: str | None = Query(None, pattern="^(tantara|hira_gasy)$"),
                      region: str | None = None, language: str | None = Query(None, pattern="^(mg|fr)$"),
                      access_level: str | None = Query(None, pattern="^(public|restricted|private)$"),
                      q: str | None = Query(None, description="Mot recherché dans le titre, le texte ou ses révisions"),
                      user: User = Depends(require_role("reader")), session: AsyncSession = Depends(get_session)):
    conds = [visible(user)]
    if genre:
        conds.append(Corpus.genre == genre)
    if region:
        conds.append(func.lower(RawText.region) == region.lower())
    if language:
        conds.append(RawText.language == language)
    if access_level:
        conds.append(Corpus.access_level == access_level)
    if q:
        pat = _like(q)
        rev = exists().where(CorpusRevision.id_corpus == Corpus.id_corpus, CorpusRevision.content.ilike(pat, escape="\\"))
        conds.append(or_(RawText.title.ilike(pat, escape="\\"), CleanedText.content.ilike(pat, escape="\\"), rev))
    total = (await session.execute(_joined(select(func.count()).select_from(Corpus)).where(*conds))).scalar_one()
    rows = (await session.execute(_joined(select(Corpus, CleanedText, RawText, Source)).where(*conds)
                                  .order_by(Corpus.validated_at.desc(), Corpus.id_corpus.desc())
                                  .offset(p.offset).limit(p.size))).all()
    latest = await _latest_contents(session, [co.id_corpus for co, *_ in rows])
    items = []
    for co, cl, raw, src in rows:
        content = latest.get(co.id_corpus, cl.content)
        items.append(CorpusItem(
            id_corpus=co.id_corpus, title=raw.title, genre=co.genre, access_level=co.access_level, language=raw.language,
            region=raw.region, creator=raw.creator, source=src.name, license=src.license,
            word_count=len(words(content)), quality_score=float(cl.quality_score) if cl.quality_score is not None else None,
            version=co.version, validated_at=co.validated_at, excerpt=_excerpt(content)))
    return Page(items=items, total=total, page=p.page, size=p.size)


async def _load(session: AsyncSession, id_corpus: int, user: User):
    row = (await session.execute(_joined(select(Corpus, CleanedText, RawText, Source))
                                 .where(Corpus.id_corpus == id_corpus, visible(user)))).first()
    if row is None:
        raise error(404, "NOT_FOUND", "Archive introuvable")
    return row


@router.get("/{id_corpus}", response_model=CorpusDetail, summary="Détail d'une archive")
async def detail(id_corpus: int, user: User = Depends(require_role("reader")), session: AsyncSession = Depends(get_session)):
    co, cl, raw, src = await _load(session, id_corpus, user)
    latest = await _latest_contents(session, [id_corpus])
    n_rev = (await session.execute(select(func.count()).select_from(CorpusRevision)
                                   .where(CorpusRevision.id_corpus == id_corpus))).scalar_one()
    return CorpusDetail(
        id_corpus=co.id_corpus, title=raw.title, genre=co.genre, access_level=co.access_level, language=raw.language,
        region=raw.region, creator=raw.creator, date_origin=raw.date_origin, origin_url=raw.origin_url,
        content=latest.get(id_corpus, cl.content), version=co.version, validated_at=co.validated_at,
        quality_score=float(cl.quality_score) if cl.quality_score is not None else None,
        source=SourceBrief(id_source=src.id_source, name=src.name, url=src.url, license=src.license),
        revisions_count=n_rev, editable=src.id_org == user.id_org and ROLE_RANK[role_of(user)] >= ROLE_RANK["reviewer"])


@router.patch("/{id_corpus}", response_model=CorpusDetail, summary="Corriger une archive (crée une révision)")
async def update(id_corpus: int, body: CorpusUpdate, user: User = Depends(require_role("reviewer")),
                 session: AsyncSession = Depends(get_session)):
    if body.content is None and body.genre is None and body.access_level is None:
        raise error(400, "NOTHING_TO_UPDATE", "Aucune modification demandée")
    co, cl, raw, src = await _load(session, id_corpus, user)
    if src.id_org != user.id_org:
        raise error(403, "FORBIDDEN_ORG", "Cette archive appartient à une autre organisation")
    changes: dict = {}
    if body.genre is not None and body.genre != co.genre:
        changes["genre"] = {"from": co.genre, "to": body.genre}
        co.genre = body.genre
    if body.access_level is not None and body.access_level != co.access_level:
        changes["access_level"] = {"from": co.access_level, "to": body.access_level}
        co.access_level = body.access_level
    if body.content is not None:
        current = (await _latest_contents(session, [id_corpus])).get(id_corpus, cl.content)
        if body.content != current:
            session.add(CorpusRevision(content=body.content, id_corpus=id_corpus, id_user=user.id_user))
            co.version += 1
            changes["content"] = {"version": co.version}
    if changes:
        audit(session, user.id_user, "corpus.update", "corpus", id_corpus, changes)
    await session.commit()
    return await detail(id_corpus, user, session)


@router.get("/{id_corpus}/revisions", response_model=list[RevisionOut], summary="Historique des révisions")
async def revisions(id_corpus: int, user: User = Depends(require_role("reviewer")), session: AsyncSession = Depends(get_session)):
    _, _, _, src = await _load(session, id_corpus, user)
    if src.id_org != user.id_org:
        raise error(403, "FORBIDDEN_ORG", "Cette archive appartient à une autre organisation")
    rows = (await session.execute(
        select(CorpusRevision, User.email).join(User, User.id_user == CorpusRevision.id_user)
        .where(CorpusRevision.id_corpus == id_corpus).order_by(CorpusRevision.id_revision.desc()))).all()
    return [RevisionOut(id_revision=r.id_revision, created_at=r.created_at, author=email, content=r.content) for r, email in rows]
