"""Seasonal prior service for oil spill likelihood.

Provides time-of-year adjustment factors based on known seasonal
patterns in oil spill occurrence in the Indian maritime region.

Seasonal patterns:
- Monsoon (Jun-Sep): higher shipping activity, rough seas → more spills
- Post-monsoon (Oct-Nov): moderate activity
- Winter (Dec-Feb): lower activity, calm seas
- Pre-monsoon (Mar-May): moderate activity, high temperatures

These are broad priors based on historical records and should be
used as a minor adjustment factor, not a primary classification signal.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# Monthly seasonal factors for Indian maritime region
# Values represent relative likelihood of true oil spills (1.0 = average)
MONTHLY_FACTORS = {
    1: 0.8,   # January — winter, low activity
    2: 0.8,   # February — winter, low activity
    3: 0.9,   # March — pre-monsoon, moderate
    4: 1.0,   # April — pre-monsoon, moderate
    5: 1.1,   # May — pre-monsoon, increasing
    6: 1.3,   # June — monsoon onset, high activity
    7: 1.4,   # July — peak monsoon, highest activity
    8: 1.4,   # August — peak monsoon, highest activity
    9: 1.2,   # September — monsoon retreating
    10: 1.0,  # October — post-monsoon
    11: 0.9,  # November — post-monsoon
    12: 0.8,  # December — winter
}


class SeasonalPriorService:
    """Provide seasonal prior adjustments for spill likelihood."""

    def __init__(self, monthly_factors: dict[int, float] | None = None) -> None:
        self._factors = monthly_factors or MONTHLY_FACTORS

    def get_prior(self, month: int) -> float:
        """Get seasonal prior factor for a given month (1-12).

        Returns a factor in [0.5, 1.5] where:
        - 1.0 = average likelihood
        - > 1.0 = above average (monsoon season)
        - < 1.0 = below average (winter)
        """
        return self._factors.get(month, 1.0)

    def get_adjustment(self, month: int) -> float:
        """Get seasonal adjustment for confidence breakdown.

        Returns a small adjustment in [-0.05, +0.05] based on seasonal patterns.
        """
        factor = self.get_prior(month)
        # Convert factor to a small adjustment centered on 0
        # factor 1.4 → +0.05, factor 0.8 → -0.05
        adjustment = (factor - 1.0) * 0.125  # scale to ±0.05
        return max(-0.05, min(0.05, adjustment))

    def explain(self, month: int) -> str:
        """Human-readable explanation of the seasonal adjustment."""
        factor = self.get_prior(month)
        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        if factor > 1.2:
            return (
                f"{month_names[month]}: Monsoon season — higher shipping activity "
                f"and rough seas increase spill likelihood (factor: {factor:.1f})."
            )
        elif factor < 0.9:
            return (
                f"{month_names[month]}: Winter season — lower shipping activity "
                f"and calm seas reduce spill likelihood (factor: {factor:.1f})."
            )
        else:
            return (
                f"{month_names[month]}: Average seasonal conditions "
                f"(factor: {factor:.1f})."
            )
