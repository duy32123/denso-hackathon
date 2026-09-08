"""Ket qua kiem tra: Issue, Severity va Report."""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


# Ma kiem tra theo bang muc 8 cua Schema chung.
CHECK_CODES: dict[str, str] = {
    "V01": "Schema / enum / khoa la / kieu null",
    "V02": "Checksum, so dong, source_type va split",
    "V03": "ID, revision, tham chieu source/claim/evidence",
    "V04": "Timestamp goc va locator van ban",
    "V05": "FieldRef.state va claim role",
    "V06": "Claim observed/stated va EvidenceLink",
    "V07": "Review va conflict",
    "V08": "Relation / branch / repeated step",
    "V09": "Import lai / sua noi dung cung revision",
    "V10": "Nguon/claim bi rut hoac index loi",
}


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "path": self.path,
            "message": self.message,
        }

    def __str__(self) -> str:
        return f"[{self.severity.value.upper():7}] {self.code} {self.path}: {self.message}"


@dataclass
class Report:
    bundle_path: str
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def add(self, code: str, severity: Severity, path: str, message: str) -> None:
        self.issues.append(Issue(code, severity, path, message))

    def error(self, code: str, path: str, message: str) -> None:
        self.add(code, Severity.ERROR, path, message)

    def warn(self, code: str, path: str, message: str) -> None:
        self.add(code, Severity.WARNING, path, message)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def ok(self) -> bool:
        """Bundle sai bi tu choi nguyen goi (muc 1). Warning khong chan import."""
        return not self.errors

    @property
    def error_codes(self) -> list[str]:
        seen: list[str] = []
        for issue in self.errors:
            if issue.code not in seen:
                seen.append(issue.code)
        return sorted(seen)

    def as_dict(self) -> dict[str, object]:
        return {
            "bundle_path": self.bundle_path,
            "ok": self.ok,
            "stats": self.stats,
            "error_codes": self.error_codes,
            "issues": [i.as_dict() for i in self.issues],
        }
