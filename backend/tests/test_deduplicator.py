from app.core.time import utc_now
from app.ingestion.deduplicator import Deduplicator
from app.ingestion.normalizer import NormalizedJob
from app.models.source import Source
from app.models.job import Job
from sqlalchemy import select


def _job(external_id="ext-1", title="Engineer", company="Acme", url="https://example.test/jobs/1"):
    return NormalizedJob(
        external_id=external_id,
        title=title,
        company=company,
        location="Remote",
        description="desc",
        url=url,
        published_at=None,
    )


def _create_source(db):
    source = Source(name="Test Source", type="rss", base_url="https://example.test/feed", enabled=True)
    db.add(source)
    db.flush()
    return source.id


def test_creates_new_job(db_session_factory):
    with db_session_factory() as db:
        source_id = _create_source(db)
        stats = Deduplicator(db).apply(source_id, [_job()], utc_now())
        assert stats.created == 1
        assert stats.updated == 0
        assert stats.skipped == 0
        job = db.scalar(select(Job).where(Job.external_id == "ext-1"))
        assert job.title == "Engineer"
        assert job.first_seen_at == job.last_seen_at


def test_unchanged_job_is_skipped(db_session_factory):
    with db_session_factory() as db:
        source_id = _create_source(db)
        Deduplicator(db).apply(source_id, [_job()], utc_now())
        db.commit()

    with db_session_factory() as db:
        stats = Deduplicator(db).apply(source_id, [_job()], utc_now())
        assert stats.created == 0
        assert stats.updated == 0
        assert stats.skipped == 1


def test_updated_job_is_updated(db_session_factory):
    with db_session_factory() as db:
        source_id = _create_source(db)
        Deduplicator(db).apply(source_id, [_job()], utc_now())
        db.commit()

    with db_session_factory() as db:
        changed = _job(title="Engineer II", company="Acme Corp", url="https://example.test/jobs/1")
        stats = Deduplicator(db).apply(source_id, [changed], utc_now())
        assert stats.updated == 1
        job = db.scalar(select(Job).where(Job.external_id == "ext-1"))
        assert job.title == "Engineer II"
        assert job.company == "Acme Corp"


def test_in_batch_duplicates_are_skipped(db_session_factory):
    with db_session_factory() as db:
        source_id = _create_source(db)
        stats = Deduplicator(db).apply(source_id, [_job(), _job()], utc_now())
        assert stats.created == 1
        assert stats.skipped == 1


def test_database_unique_constraint(db_session_factory):
    from sqlalchemy.exc import IntegrityError

    with db_session_factory() as db:
        source_id = _create_source(db)
        db.add(
            Job(
                source_id=source_id,
                external_id="ext-1",
                title="A",
                url="https://example.test/jobs/1",
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
            )
        )
        db.flush()
        db.add(
            Job(
                source_id=source_id,
                external_id="ext-1",
                title="B",
                url="https://example.test/jobs/2",
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
            )
        )
        try:
            db.flush()
        except IntegrityError:
            return
        raise AssertionError("expected IntegrityError on duplicate (source_id, external_id)")