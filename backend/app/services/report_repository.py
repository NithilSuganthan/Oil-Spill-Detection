"""Report storage repository — stores investigation reports.

In-memory development storage. Persistent storage can be added later.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict


def to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class StoredReport(CamelModel):
    """Stored investigation report."""
    report_id: str
    incident_id: str
    generated_at: str
    provider: str
    model: str
    evidence_version: str = "1.0"
    prompt_version: str = "1.0"
    report_json: dict[str, Any]


class ReportRepository:
    """In-memory report storage for development."""

    def __init__(self) -> None:
        self._reports: dict[str, StoredReport] = {}
        self._lock = threading.Lock()

    def store_report(self, report: StoredReport) -> None:
        """Store a report."""
        with self._lock:
            self._reports[report.report_id] = report

    def get_report(self, report_id: str) -> StoredReport | None:
        """Get a report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def get_report_by_incident(self, incident_id: str) -> StoredReport | None:
        """Get the latest report for an incident."""
        with self._lock:
            for report in self._reports.values():
                if report.incident_id == incident_id:
                    return report
            return None

    def list_reports(self) -> list[StoredReport]:
        """List all reports."""
        with self._lock:
            return list(self._reports.values())


# Global singleton for development
_report_repo: ReportRepository | None = None
_report_repo_lock = threading.Lock()


def get_report_repository() -> ReportRepository:
    """Get the global report repository."""
    global _report_repo
    if _report_repo is None:
        with _report_repo_lock:
            if _report_repo is None:
                _report_repo = ReportRepository()
    return _report_repo
