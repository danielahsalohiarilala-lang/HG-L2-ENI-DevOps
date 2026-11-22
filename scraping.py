"""Jobs de collecte : l'API les met en file (statut queued) ; le worker data.run_jobs les exécute."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams, error, require_role
from app.db.session import get_session
from app.models import RawText, ScrapingJob, Source, User
from app.schemas.archive import JobCreate, JobOut
from app.schemas.common import Page
from app.services.audit import audit

router = APIRouter(prefix="/scraping", tags=["collecte"])


def _out(job: ScrapingJob, count: int = 0) -> JobOut:
    return JobOut(id_job=job.id_job, id_source=job.id_source, status=job.status, params=job.params,
                  error_message=job.error_message, created_at=job.created_at, started_at=job.started_at,
                  finished_at=job.finished_at, texts_count=count)


@router.post("/jobs", response_model=JobOut, status_code=202, summary="Mettre une collecte en file d'attente")
async def create_job(body: JobCreate, admin: User = Depends(require_role("admin")),
                     session: AsyncSession = Depends(get_session)):
    src = (await session.execute(select(Source).where(Source.id_source == body.id_source, Source.id_org == admin.id_org))).scalar_one_or_none()
    if src is None:
        raise error(404, "NOT_FOUND", "Source introuvable")
    job = ScrapingJob(status="queued", params=body.params, id_user=admin.id_user, id_source=src.id_source)
    session.add(job)
    await session.flush()
    audit(session, admin.id_user, "scraping.create", "scraping_job", job.id_job, {"id_source": src.id_source})
    await session.commit()
    await session.refresh(job)
    return _out(job)


@router.get("/jobs", response_model=Page[JobOut], summary="Lister les jobs de l'organisation")
async def list_jobs(p: PageParams = Depends(), admin: User = Depends(require_role("admin")),
                    session: AsyncSession = Depends(get_session)):
    base = select(ScrapingJob).join(Source, Source.id_source == ScrapingJob.id_source).where(Source.id_org == admin.id_org)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    jobs = (await session.execute(base.order_by(ScrapingJob.id_job.desc()).offset(p.offset).limit(p.size))).scalars().all()
    counts = dict((await session.execute(
        select(RawText.id_job, func.count()).where(RawText.id_job.in_([j.id_job for j in jobs])).group_by(RawText.id_job))).all()) if jobs else {}
    return Page(items=[_out(j, counts.get(j.id_job, 0)) for j in jobs], total=total, page=p.page, size=p.size)


@router.get("/jobs/{id_job}", response_model=JobOut, summary="Statut d'un job")
async def get_job(id_job: int, admin: User = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    job = (await session.execute(
        select(ScrapingJob).join(Source, Source.id_source == ScrapingJob.id_source)
        .where(ScrapingJob.id_job == id_job, Source.id_org == admin.id_org))).scalar_one_or_none()
    if job is None:
        raise error(404, "NOT_FOUND", "Job introuvable")
    n = (await session.execute(select(func.count()).select_from(RawText).where(RawText.id_job == id_job))).scalar_one()
    return _out(job, n)
