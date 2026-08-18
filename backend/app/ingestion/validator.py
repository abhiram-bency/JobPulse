"""Record-level validation.

Required fields (per the challenge): title and URL.
Anything else missing is tolerated and normalized later.
One malformed record must never abort the whole sync.
"""

from dataclasses import dataclass, field

from app.ingestion.parser import RawJob


@dataclass
class ValidationResult:
    valid: list[RawJob] = field(default_factory=list)
    invalid: list[tuple[RawJob, str]] = field(default_factory=list)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid)


class JobValidator:
    def validate_all(self, items: list[RawJob]) -> ValidationResult:
        result = ValidationResult()
        for item in items:
            reason = self._problem(item)
            if reason is None:
                result.valid.append(item)
            else:
                result.invalid.append((item, reason))
        return result

    @staticmethod
    def _problem(item: RawJob) -> str | None:
        if not item.title or not item.title.strip():
            return "missing_title"
        if not item.url or not item.url.strip():
            return "missing_url"
        return None