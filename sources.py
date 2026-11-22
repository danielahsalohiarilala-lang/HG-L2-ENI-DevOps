"""Sources de collecte (avec leur licence)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import error, require_role
from app.db.session import get_session
from app.models import Source, User
from app.schemas.sources import SourceCreate, SourceOut, SourceUpdate
from app.services.audit import audit

router = APIRouter(prefix="/sources", tags=["sources"])


def _out(s: Source) -> SourceOut:
    return SourceOut(id_source=s.id_source, name=s.name, url=s.url, type=s.type, license=s.license)


@router.get("", response_model=list[SourceOut], summary="Lister les sources de l'organisation")
async def list_sources(user: User = Depends(require_role("reviewer")), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Source).where(Source.id_org == user.id_org).order_by(Source.id_source))).scalars()
    return [_out(s) for s in rows]


@router.post("", response_model=SourceOut, status_code=201, summary="Enregistrer une source (licence obligatoire)")
async def create_source(body: SourceCreate, admin: User = Depends(require_role("admin")),
                        session: AsyncSession = Depends(get_session)):
    dup = (await session.execute(select(Source.id_source).where(Source.id_org == admin.id_org, Source.url == body.url))).scalar_one_or_none()
    if dup:
        raise error(409, "SOURCE_EXISTS", "Cette adresse est déjà enregistrée comme source")
    src = Source(name=body.name, url=body.url, type=body.type, license=body.license, id_org=admin.id_org)
    session.add(src)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise error(409, "SOURCE_EXISTS", "Cette adresse est déjà enregistrée comme source") from exc
    audit(session, admin.id_user, "source.create", "source", src.id_source, {"url": body.url, "license": body.license})
    await session.commit()
    return _out(src)


@router.patch("/{id_source}", response_model=SourceOut, summary="Modifier le nom ou la licence d'une source")
async def update_source(id_source: int, body: SourceUpdate, admin: User = Depends(require_role("admin")),
                        session: AsyncSession = Depends(get_session)):
    src = (await session.execute(select(Source).where(Source.id_source == id_source, Source.id_org == admin.id_org))).scalar_one_or_none()
    if src is None:
        raise error(404, "NOT_FOUND", "Source introuvable")
    changes = {}
    for field in ("name", "license"):
        value = getattr(body, field)
        if value is not None and value != getattr(src, field):
            changes[field] = {"from": getattr(src, field), "to": value}
            setattr(src, field, value)
    if changes:
        audit(session, admin.id_user, "source.update", "source", src.id_source, changes)
    await session.commit()
    return _out(src)
