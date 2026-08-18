from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job
from app.schemas.common import Paginated
from app.schemas.job import JobOut

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.get("/jobs", response_model=Paginated[JobOut])
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    location: str | None = None,
    company: str | None = None,
    source_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = select(Job)

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )
    if location and location.strip():
        query = query.where(Job.location.ilike(f"%{location.strip()}%"))
    if company and company.strip():
        query = query.where(Job.company.ilike(f"%{company.strip()}%"))
    if source_id is not None:
        query = query.where(Job.source_id == source_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Job.published_at.desc().nulls_last(), Job.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return Paginated[JobOut](items=rows, page=page, page_size=page_size, total=total)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job