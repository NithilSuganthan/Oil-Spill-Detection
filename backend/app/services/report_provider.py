"""Groq report provider abstraction.

Provides natural-language investigation reports from structured evidence.
All scientific computation happens BEFORE this provider is called.
Groq is ONLY a natural-language explanation/reporting layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
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


class InvestigationReport(CamelModel):
    """Structured investigation report from Groq."""
    title: str = ""
    executive_summary: str = ""
    detection_assessment: str = ""
    environment_assessment: str = ""
    drift_assessment: str = ""
    ais_assessment: str = ""
    candidate_assessments: list[dict[str, Any]] = []
    uncertainty: str = ""
    recommended_actions: list[str] = []
    limitations: list[str] = []
    human_review_required: bool = True


class GroqReportProvider(ABC):
    """Abstract base class for report providers."""

    name: str = "base"

    @abstractmethod
    def generate_report(self, evidence_json: dict[str, Any]) -> InvestigationReport:
        """Generate investigation report from structured evidence.

        Args:
            evidence_json: Serialized InvestigationEvidence.

        Returns:
            InvestigationReport with structured sections.

        Raises:
            RuntimeError: if report generation fails.
        """

    def close(self) -> None:
        """Release any resources."""
