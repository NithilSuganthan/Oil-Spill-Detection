"""False positive review API routes.

Simple human-review workflow for detections flagged as potential false positives.
In-memory storage — not persisted across restarts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.services.false_positive_review import FalsePositiveReviewManager

router = APIRouter(prefix="/reviews", tags=["reviews"])

# Shared in-memory manager
_manager = FalsePositiveReviewManager()


def to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


class ReviewResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    incident_id: str
    review_status: str
    reviewer: str
    notes: str
    reviewed_at: str | None = None
    automated_classification: str
    automated_confidence: float


class ReviewUpdateRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    review_status: str | None = None
    reviewer: str | None = None
    notes: str | None = None


class ReviewCreateRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    automated_classification: str = ""
    automated_confidence: float = 0.0


@router.post("/{incident_id}", response_model=ReviewResponse)
def create_review(incident_id: str, request: ReviewCreateRequest):
    """Create a review entry for an incident."""
    existing = _manager.get_review(incident_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Review already exists for {incident_id}")

    review = _manager.create_review(
        incident_id=incident_id,
        automated_classification=request.automated_classification,
        automated_confidence=request.automated_confidence,
    )
    return ReviewResponse(
        incident_id=review.incident_id,
        review_status=review.review_status,
        reviewer=review.reviewer,
        notes=review.notes,
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
        automated_classification=review.automated_classification,
        automated_confidence=review.automated_confidence,
    )


@router.get("/{incident_id}", response_model=ReviewResponse)
def get_review(incident_id: str):
    """Get review status for an incident."""
    review = _manager.get_review(incident_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"No review for {incident_id}")
    return ReviewResponse(
        incident_id=review.incident_id,
        review_status=review.review_status,
        reviewer=review.reviewer,
        notes=review.notes,
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
        automated_classification=review.automated_classification,
        automated_confidence=review.automated_confidence,
    )


@router.patch("/{incident_id}", response_model=ReviewResponse)
def update_review(incident_id: str, request: ReviewUpdateRequest):
    """Update review status for an incident."""
    review = _manager.update_review(
        incident_id,
        review_status=request.review_status,
        reviewer=request.reviewer,
        notes=request.notes,
    )
    if review is None:
        raise HTTPException(status_code=404, detail=f"No review for {incident_id}")
    return ReviewResponse(
        incident_id=review.incident_id,
        review_status=review.review_status,
        reviewer=review.reviewer,
        notes=review.notes,
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
        automated_classification=review.automated_classification,
        automated_confidence=review.automated_confidence,
    )


@router.get("/", response_model=list[ReviewResponse])
def list_reviews(status: str | None = None):
    """List all reviews, optionally filtered by status."""
    if status:
        reviews = _manager.list_by_status(status)
    else:
        reviews = _manager.list_pending()
    return [
        ReviewResponse(
            incident_id=r.incident_id,
            review_status=r.review_status,
            reviewer=r.reviewer,
            notes=r.notes,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            automated_classification=r.automated_classification,
            automated_confidence=r.automated_confidence,
        )
        for r in reviews
    ]
