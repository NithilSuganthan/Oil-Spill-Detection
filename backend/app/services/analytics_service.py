"""Analytics aggregation over incidents + scenes.

Computed from repository data (no fabricated numbers). All dates are grouped
in IST (Asia/Kolkata) to match the operational focus region.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.repository import SpillRepository
from app.domain.entities import confidence_level
from app.domain.regions import classify_region  # noqa: F401  (re-exported use)

IST = timezone(timedelta(hours=5, minutes=30))

BUCKETS = ["50–60%", "60–70%", "70–80%", "80–90%", "90–100%"]


def _bucket_of(confidence: float) -> str:
    if confidence >= 0.9:
        return "90–100%"
    if confidence >= 0.8:
        return "80–90%"
    if confidence >= 0.7:
        return "70–80%"
    if confidence >= 0.6:
        return "60–70%"
    return "50–60%"


class AnalyticsService:
    def __init__(self, repo: SpillRepository) -> None:
        self._repo = repo

    def summary(self, window_days: int = 7) -> dict:
        incidents = self._repo.list_incidents()
        scenes = self._repo.list_scenes()

        # Determine the reporting window from the data itself (last N distinct
        # IST detection days), so demo seeds and live data both behave.
        ist_dates = sorted(
            {inc.detected_at.astimezone(IST).date() for inc in incidents},
            reverse=True,
        )[:window_days]
        day_set = set(ist_dates)

        by_day: dict = {}
        for d in ist_dates:
            by_day[d] = {"detections": 0, "high": 0, "area": 0.0}

        totals_detections = 0
        totals_high = 0
        totals_area = 0.0
        hourly = {f"{h:02d}": 0 for h in range(0, 24, 2)}
        buckets = {b: 0 for b in BUCKETS}
        regions: dict[str, dict] = {}

        for inc in incidents:
            local_dt = inc.detected_at.astimezone(IST)
            level = confidence_level(inc.confidence)
            in_window = local_dt.date() in day_set

            if in_window:
                totals_detections += 1
                totals_area += inc.area_km2
                if level == "HIGH":
                    totals_high += 1
                stat = by_day[local_dt.date()]
                stat["detections"] += 1
                stat["area"] += inc.area_km2
                if level == "HIGH":
                    stat["high"] += 1

            hr = f"{(local_dt.hour // 2) * 2:02d}"
            hourly[hr] += 1
            buckets[_bucket_of(inc.confidence)] += 1
            r = regions.setdefault(inc.region, {"detections": 0, "area": 0.0})
            r["detections"] += 1
            r["area"] += inc.area_km2

        # scenes processed per day (by acquisition date, within the window)
        scenes_by_day = {d: 0 for d in ist_dates}
        for sc in scenes:
            if sc.acquired_at:
                d = sc.acquired_at.astimezone(IST).date()
                if d in scenes_by_day:
                    scenes_by_day[d] += 1

        def label(d: datetime) -> str:
            return d.strftime("%d %b")

        daily = [
            {
                "date": label(d),
                "detections": by_day[d]["detections"],
                "high_confidence": by_day[d]["high"],
                "area_km2": round(by_day[d]["area"], 1),
                "scenes_processed": scenes_by_day[d],
            }
            for d in sorted(ist_dates)
        ]

        return {
            "totals": {
                "detections": totals_detections,
                "high_confidence": totals_high,
                "total_area_km2": round(totals_area, 1),
                "scenes_processed": sum(scenes_by_day.values()),
            },
            "daily": daily,
            "hourly": [{"hour": h, "detections": n} for h, n in hourly.items()],
            "by_region": [
                {"region": name, "detections": v["detections"], "area_km2": round(v["area"], 1)}
                for name, v in sorted(regions.items(), key=lambda kv: -kv[1]["detections"])
            ],
            "confidence_buckets": [
                {"bucket": b, "count": buckets[b]} for b in BUCKETS
            ],
        }

    def detections(self):
        return [
            {
                "incident_id": inc.id,
                "detected_at": inc.detected_at.isoformat(),
                "confidence": inc.confidence,
                "area_km2": inc.area_km2,
                "level": inc.level,
                "region": inc.region,
            }
            for inc in self._repo.list_incidents()
        ]
