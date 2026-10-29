"""Criticality score schemas — Operational Priority Index for SAGAR WATCH."""

from __future__ import annotations

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


class CriticalityFactorResponse(CamelModel):
    """A single factor in the criticality breakdown."""
    name: str
    label: str
    score: float  # 0-100 normalized contribution
    max_score: float  # maximum possible score for this factor
    weight: float  # original weight (0-1)
    normalized_weight: float  # weight after redistribution (0-1)
    available: bool  # whether this factor was computable
    source: str  # data source description
    explanation: str  # human-readable explanation


class CriticalityResponse(CamelModel):
    """Operational Criticality Index — priority triage score for incidents.

    This is NOT:
    - probability of oil being present
    - detection confidence
    - attribution probability
    - environmental damage prediction

    This IS:
    - operational priority index helping operators decide
      which incident requires attention first
    """
    score: int  # 0-100 integer
    level: str  # LOW, MODERATE, HIGH, CRITICAL
    action: str  # operational recommendation
    methodology: str  # version/methodology description
    factors: list[CriticalityFactorResponse]  # factor breakdown
    available_factor_count: int  # how many factors were available
    total_factor_count: int  # total factors considered
    normalization_note: str  # explanation of weight redistribution
