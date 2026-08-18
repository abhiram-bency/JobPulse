from app.ingestion.parser import RawJob
from app.ingestion.validator import JobValidator


def _raw(**kwargs) -> RawJob:
    defaults = {"title": "Engineer", "url": "https://example.test/jobs/1"}
    defaults.update(kwargs)
    return RawJob(**defaults)


def test_all_valid():
    result = JobValidator().validate_all([_raw(), _raw(title="Other")])
    assert len(result.valid) == 2
    assert result.invalid_count == 0


def test_missing_title_skipped():
    result = JobValidator().validate_all([_raw(title="  "), _raw()])
    assert len(result.valid) == 1
    assert result.invalid_count == 1
    assert result.invalid[0][1] == "missing_title"


def test_missing_url_skipped():
    result = JobValidator().validate_all([_raw(url=""), _raw()])
    assert len(result.valid) == 1
    assert result.invalid_count == 1
    assert result.invalid[0][1] == "missing_url"


def test_one_bad_record_does_not_kill_rest():
    result = JobValidator().validate_all([_raw(title=None), _raw(url=None), _raw()])
    assert len(result.valid) == 1
    assert result.invalid_count == 2