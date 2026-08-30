"""False positive review management.

Tracks review status for detections flagged as potential false positives.
Supports human review workflow and automated classification feedback.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.domain.entities import FalsePositiveReview

logger = logging.getLogger(__name__)


class FalsePositiveReviewManager:
    """Manage false positive review lifecycle."""

    def __init__(self) -> None:
        self._reviews: dict[str, FalsePositiveReview] = {}

    def create_review(
        self,
        incident_id: str,
        automated_classification: str = "",
        automated_confidence: float = 0.0,
    ) -> FalsePositiveReview:
        """Create a new review entry for an incident."""
        review = FalsePositiveReview(
            incident_id=incident_id,
            automated_classification=automated_classification,
            automated_confidence=automated_confidence,
        )
        self._reviews[incident_id] = review
        logger.info("Created FP review for incident %s", incident_id)
        return review

    def get_review(self, incident_id: str) -> FalsePositiveReview | None:
        return self._reviews.get(incident_id)

    def update_review(
        self,
        incident_id: str,
        *,
        review_status: str | None = None,
        reviewer: str | None = None,
        notes: str | None = None,
    ) -> FalsePositiveReview | None:
        """Update an existing review."""
        review = self._reviews.get(incident_id)
        if review is None:
            return None

        if review_status is not None:
            review.review_status = review_status
        if reviewer is not None:
            review.reviewer = reviewer
        if notes is not None:
            review.notes = notes
        review.reviewed_at = datetime.now(timezone.utc)

        logger.info(
            "Updated FP review for incident %s: status=%s",
            incident_id,
            review.review_status,
        )
        return review

    def list_pending(self) -> list[FalsePositiveReview]:
        return [r for r in self._reviews.values() if r.review_status == "pending"]

    def list_by_status(self, status: str) -> list[FalsePositiveReview]:
        return [r for r in self._reviews.values() if r.review_status == status]

    @property
    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._reviews.values():
            counts[r.review_status] = counts.get(r.review_status, 0) + 1
        return counts
