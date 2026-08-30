"""AIS provider abstraction layer.

All AIS data sources (mock, GFW, etc.) implement the AISProvider interface.
The correlation engine depends only on this interface — never on a concrete provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.ais import AisObservation, AisSearchWindow


class AISProvider(ABC):
    """Abstract base class for AIS data providers."""

    name: str = "base"
    dataset: str = ""

    @abstractmethod
    def query_positions(
        self,
        search_window: AisSearchWindow,
    ) -> list[AisObservation]:
        """Query AIS positions within the given search window.

        Args:
            search_window: Geographic bbox, time range, and center point.

        Returns:
            List of normalized AIS observations. Empty list if none found.
        """

    def get_vessel(self, vessel_id: str) -> dict | None:
        """Optional: retrieve vessel identity details by MMSI or GFW vessel ID.

        Not all providers support this. Returns None if unsupported.
        """
        return None

    def close(self) -> None:
        """Release any resources held by the provider."""
