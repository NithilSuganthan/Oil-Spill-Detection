"""Integration tests proving Phase 8 intelligence is live in the API.

These tests verify that the LIVE attribution/investigation endpoints
actually invoke Phase 8 components and return intelligence data.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Settings


@pytest.fixture
def client():
    settings = Settings(
        seed_demo_data=True,
        ais_provider="mock",
        environmental_provider="mock",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def incident_id(client):
    """Get the first demo incident ID."""
    resp = client.get("/api/v1/spills")
    assert resp.status_code == 200
    incidents = resp.json()
    assert len(incidents) > 0
    return incidents[0]["id"]


class TestIntelligenceLive:
    """Prove Phase 8 intelligence is actually executed in the live API."""

    def test_attribution_endpoint_returns_intelligence(self, client, incident_id):
        """GET /attribution/{id} must return intelligence field."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "intelligence" in data
        assert data["intelligence"] is not None

    def test_intelligence_has_confidence_breakdown(self, client, incident_id):
        """Intelligence must contain confidenceBreakdown with both raw and adjusted."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        data = resp.json()
        intel = data["intelligence"]
        cb = intel["confidenceBreakdown"]
        assert cb["rawModelConfidence"] > 0
        assert cb["adjustedConfidence"] > 0
        assert cb["confidenceBand"] in ("HIGH", "MEDIUM", "LOW")

    def test_look_alike_screening_is_heuristic(self, client, incident_id):
        """Look-alike screening must be labeled HEURISTIC."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        la = intel["lookAlikeScreening"]
        assert la["status"] == "HEURISTIC"
        assert 0.0 <= la["pLookAlike"] <= 1.0
        assert la["penalty"] >= 0.0

    def test_texture_status_is_unavailable(self, client, incident_id):
        """Texture features must be UNAVAILABLE (not extracted from SAR patch)."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        la = intel["lookAlikeScreening"]
        assert la["textureStatus"] == "UNAVAILABLE"

    def test_environmental_reliability_is_heuristic(self, client, incident_id):
        """Environmental reliability must be labeled HEURISTIC."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        env = intel["environmentalReliability"]
        assert env["status"] == "HEURISTIC"
        assert env["band"] in ("IDEAL", "GOOD", "MARGINAL", "POOR", "UNKNOWN")

    def test_calibration_is_not_calibrated(self, client, incident_id):
        """Calibration must be NOT_CALIBRATED."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        cal = intel["calibration"]
        assert cal["status"] == "NOT_CALIBRATED"
        assert cal["calibratedConfidence"] is None
        assert cal["calibrationShift"] == 0.0

    def test_ais_gap_is_raw_ais_required(self, client, incident_id):
        """AIS gap must be RAW_AIS_REQUIRED (GFW is aggregated)."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        gap = intel["aisGap"]
        assert gap["status"] == "RAW_AIS_REQUIRED"

    def test_static_spacing_is_raw_ais_required(self, client, incident_id):
        """Static spacing must be RAW_AIS_REQUIRED."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        ss = intel["staticSpacing"]
        assert ss["status"] == "RAW_AIS_REQUIRED"

    def test_seasonal_prior_is_heuristic(self, client, incident_id):
        """Seasonal prior must be labeled HEURISTIC."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        sp = intel["seasonalPrior"]
        assert sp["status"] == "HEURISTIC"
        assert 1 <= sp["month"] <= 12
        assert sp["factor"] > 0

    def test_small_detection_is_heuristic(self, client, incident_id):
        """Small detection must be labeled HEURISTIC."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        sd = intel["smallDetection"]
        assert sd["status"] == "HEURISTIC"
        assert sd["areaKm2"] >= 0
        assert sd["risk"] in ("LOW", "MEDIUM", "HIGH", "UNKNOWN")

    def test_vessel_evidence_has_availability(self, client, incident_id):
        """Each vessel evidence must show availability status."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        for ve in intel["vesselEvidence"]:
            assert "mmsi" in ve
            assert ve["aisGapStatus"] == "RAW_AIS_REQUIRED"
            assert ve["staticSpacingStatus"] == "RAW_AIS_REQUIRED"
            assert ve["evidenceAvailability"] == "PARTIAL"

    def test_provenance_has_all_fields(self, client, incident_id):
        """Provenance must contain all required status fields."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        prov = intel["provenance"]
        # Provenance uses snake_case keys (raw dict, not CamelModel)
        assert prov["calibration_status"] == "NOT_CALIBRATED"
        assert prov["seasonal_prior_status"] == "HEURISTIC"
        assert prov["ais_gap_status"] == "RAW_AIS_REQUIRED"
        assert prov["static_spacing_status"] == "RAW_AIS_REQUIRED"
        assert prov["texture_status"] == "UNAVAILABLE"

    def test_phase4_attribution_score_unchanged(self, client, incident_id):
        """Phase 4 attribution score must still be present and separate."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        data = resp.json()
        # Phase 4 score is in candidates
        assert data["candidateCount"] >= 0
        for c in data["candidates"]:
            assert "attributionScore" in c
            assert "scoreComponents" in c
        # Intelligence is separate
        assert "intelligence" in data

    def test_investigation_returns_intelligence(self, client, incident_id):
        """POST /investigation/{id}/run must return intelligence."""
        resp = client.post(f"/api/v1/investigation/{incident_id}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "intelligence" in data
        assert data["intelligence"] is not None
        intel = data["intelligence"]
        assert "confidenceBreakdown" in intel
        assert "lookAlikeScreening" in intel

    def test_confidence_equation_correct(self, client, incident_id):
        """Verify the confidence equation: adjusted = raw - penalties."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        cb = resp.json()["intelligence"]["confidenceBreakdown"]
        raw = cb["rawModelConfidence"]
        adj = cb["adjustedConfidence"]
        ll = cb["lookAlikePenalty"]
        env = cb["environmentalPenalty"]
        small = cb["smallDetectionPenalty"]
        cal = cb["calibrationShift"]
        seasonal = cb["seasonalPriorAdjustment"]

        expected = raw - ll - env - small + cal + seasonal
        expected = max(0.0, min(1.0, expected))
        assert adj == pytest.approx(expected, abs=0.001)

    def test_no_fabricated_zero_evidence(self, client, incident_id):
        """Unavailable evidence must not be replaced with zero."""
        resp = client.get(f"/api/v1/attribution/{incident_id}")
        intel = resp.json()["intelligence"]
        # AIS gap score must be None, not 0.0
        for ve in intel["vesselEvidence"]:
            assert ve["aisGapScore"] is None
            assert ve["staticSpacingScore"] is None
            assert ve["vesselTypePrior"] is None


class TestReviewsAPI:
    """Test the FalsePositiveReview API endpoints."""

    def test_create_review(self, client, incident_id):
        resp = client.post(f"/api/v1/reviews/{incident_id}", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewStatus"] == "pending"

    def test_get_review(self, client, incident_id):
        client.post(f"/api/v1/reviews/{incident_id}", json={})
        resp = client.get(f"/api/v1/reviews/{incident_id}")
        assert resp.status_code == 200

    def test_update_review(self, client, incident_id):
        client.post(f"/api/v1/reviews/{incident_id}", json={})
        resp = client.patch(
            f"/api/v1/reviews/{incident_id}",
            json={"reviewStatus": "likely_oil", "reviewer": "analyst1"},
        )
        assert resp.status_code == 200
        assert resp.json()["reviewStatus"] == "likely_oil"
        assert resp.json()["reviewer"] == "analyst1"

    def test_get_nonexistent_review(self, client):
        resp = client.get("/api/v1/reviews/NONEXISTENT")
        assert resp.status_code == 404

    def test_duplicate_review_rejected(self, client, incident_id):
        client.post(f"/api/v1/reviews/{incident_id}", json={})
        resp = client.post(f"/api/v1/reviews/{incident_id}", json={})
        assert resp.status_code == 409
