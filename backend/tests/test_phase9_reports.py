"""Tests for Phase 9 — Real environmental forcing + Groq investigation reports.

Tests cover:
- RealEnvironmentalProvider (when credentials missing)
- MockEnvironmentalProvider provenance
- InvestigationEvidence schema
- Evidence builder
- MockReportProvider
- Report API endpoints
- Report storage repository
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.domain.ais import CandidateVessel
from app.domain.entities import SpillIncident
from app.schemas.evidence import InvestigationEvidence
from app.services.drift_engine import FirstOrderDriftProvider
from app.services.environmental_mock_provider import MockEnvironmentalProvider
from app.services.evidence_builder import build_investigation_evidence
from app.services.mock_report_provider import MockReportProvider
from app.services.report_repository import ReportRepository, StoredReport
from app.services.report_provider import InvestigationReport


# ── Environmental provider tests ────────────────────────────────────────


class TestMockEnvironmentalProvenance:
    """MockEnvironmentalProvider must include provenance in conditions."""

    def test_provider_name(self):
        provider = MockEnvironmentalProvider()
        assert provider.name == "mock"

    def test_conditions_have_provenance(self):
        provider = MockEnvironmentalProvider()
        conditions = provider.get_conditions(
            lat=15.0, lon=73.0, timestamp=datetime.now(timezone.utc),
        )
        assert conditions.provider == "mock"
        assert conditions.dataset == "deterministic_synthetic"
        assert conditions.environment_status == "DEMO"

    def test_conditions_have_location(self):
        provider = MockEnvironmentalProvider()
        conditions = provider.get_conditions(
            lat=15.0, lon=73.0, timestamp=datetime.now(timezone.utc),
        )
        assert conditions.latitude == 15.0
        assert conditions.longitude == 73.0


class TestRealEnvironmentalCredentialsRequired:
    """RealEnvironmentalProvider must fail loudly on missing credentials."""

    def test_missing_cmems_username(self):
        from app.services.environmental_real_provider import RealEnvironmentalProvider
        with pytest.raises(ValueError, match="CMEMS_USERNAME"):
            RealEnvironmentalProvider(
                cmems_username="",
                cmems_password="pass",
                cds_api_key="key",
            )

    def test_missing_cmems_password(self):
        from app.services.environmental_real_provider import RealEnvironmentalProvider
        with pytest.raises(ValueError, match="CMEMS_USERNAME"):
            RealEnvironmentalProvider(
                cmems_username="user",
                cmems_password="",
                cds_api_key="key",
            )

    def test_missing_cds_key(self):
        from app.services.environmental_real_provider import RealEnvironmentalProvider
        with pytest.raises(ValueError, match="CDS_API_KEY"):
            RealEnvironmentalProvider(
                cmems_username="user",
                cmems_password="pass",
                cds_api_key="",
            )


# ── InvestigationEvidence schema tests ──────────────────────────────────


class TestInvestigationEvidenceSchema:
    """InvestigationEvidence must serialize to camelCase JSON."""

    def test_minimal_evidence(self):
        evidence = InvestigationEvidence(
            incident_id="TEST-001",
            detection={"incidentId": "TEST-001"},
            look_alike={},
            environment={},
            drift={},
            ais={},
            small_detection={},
            seasonal_prior={},
            calibration={},
            human_review={},
            provenance={},
        )
        data = evidence.model_dump(by_alias=True)
        assert data["incidentId"] == "TEST-001"
        assert "detection" in data
        assert "candidates" in data

    def test_full_evidence(self):
        evidence = InvestigationEvidence(
            incident_id="TEST-002",
            detection={"incidentId": "TEST-002", "rawModelConfidence": 0.85},
            look_alike={"status": "HEURISTIC", "pLookAlike": 0.3},
            environment={"provider": "mock", "environmentStatus": "DEMO"},
            drift={"method": "first_order", "sourceLatitude": 15.5},
            ais={"provider": "gfw", "vesselCount": 3},
            candidates=[
                {"mmsi": "123456789", "attributionScore": 0.8},
            ],
            small_detection={"areaKm2": 10.0, "risk": "LOW"},
            seasonal_prior={"status": "HEURISTIC", "month": 8},
            calibration={"status": "NOT_CALIBRATED"},
            human_review={"reviewStatus": "NOT_REVIEWED"},
            provenance={"modelVersion": "1.0"},
            raw_model_confidence=0.85,
            adjusted_confidence=0.78,
            confidence_band="HIGH",
        )
        data = evidence.model_dump(by_alias=True)
        assert data["rawModelConfidence"] == 0.85
        assert data["adjustedConfidence"] == 0.78
        assert data["confidenceBand"] == "HIGH"
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["mmsi"] == "123456789"


# ── Evidence builder tests ──────────────────────────────────────────────


class TestEvidenceBuilder:
    """Evidence builder must assemble structured evidence from pipeline results."""

    def _make_incident(self):
        return SpillIncident(
            id="INC-TEST-001",
            scene_id="SCENE-001",
            centroid_lat=15.0,
            centroid_lon=73.0,
            confidence=0.85,
            area_km2=10.0,
            perimeter_km=5.0,
            detected_at=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
            geometry={"type": "Polygon", "coordinates": [[[73.0, 15.0]]]},
            bbox=(72.9, 14.9, 73.1, 15.1),
            region="West Coast",
            location_description="Test location",
            satellite="Sentinel-1",
            model_name="TinyUNet",
            model_version="1.0-dev",
        )

    def _make_drift_result(self):
        from app.services.drift_provider import DriftResult
        return DriftResult(
            incident_id="INC-TEST-001",
            method="first_order_backward_hindcast",
            slick_latitude=15.0,
            slick_longitude=73.0,
            observation_time=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
            integration_hours=24.0,
            timestep_minutes=15.0,
            ensemble_size=50,
            source_latitude=14.8,
            source_longitude=72.8,
            source_earliest=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
            source_latest=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
            uncertainty_km=15.0,
            uncertainty_hours=6.0,
            confidence=0.7,
            quality_flags=["DEMO_ENVIRONMENTAL_FORCING"],
            source_points=[(14.8, 72.8)],
            provenance={"provider": "first_order", "environmental_provider": "mock"},
            analyzed_at=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
        )

    def _make_candidates(self):
        return [
            CandidateVessel(
                mmsi="987654321",
                vessel_name="TEST VESSEL",
                vessel_type="Cargo",
                closest_distance_km=2.5,
                closest_time_difference_minutes=30.0,
                attribution_score=0.75,
                score_components={"distance": 0.8, "time": 0.7, "trackConsistency": 0.6},
                number_of_observations=5,
            ),
        ]

    def _make_intelligence(self):
        from app.schemas.intelligence import (
            AISGapResponse,
            CalibrationResponse,
            ConfidenceBreakdownResponse,
            DetectionIntelligenceResponse,
            EnvironmentalReliabilityResponse,
            LookAlikeScreeningResponse,
            SeasonalPriorResponse,
            SmallDetectionResponse,
            StaticSpacingResponse,
            VesselEvidenceResponse,
        )
        return DetectionIntelligenceResponse(
            confidence_breakdown=ConfidenceBreakdownResponse(
                raw_model_confidence=0.85,
                adjusted_confidence=0.78,
                confidence_band="HIGH",
                look_alike_penalty=0.05,
                environmental_penalty=0.02,
                small_detection_penalty=0.0,
                calibration_shift=0.0,
                seasonal_prior_adjustment=0.0,
            ),
            look_alike_screening=LookAlikeScreeningResponse(
                status="HEURISTIC",
                p_look_alike=0.3,
                penalty=0.05,
                explanation="Test",
            ),
            environmental_reliability=EnvironmentalReliabilityResponse(
                status="HEURISTIC",
                band="GOOD",
                wind_speed_knots=10.0,
                penalty=0.02,
                explanation="Test",
            ),
            small_detection=SmallDetectionResponse(
                area_km2=10.0,
                risk="LOW",
                explanation="Test",
            ),
            seasonal_prior=SeasonalPriorResponse(
                status="HEURISTIC",
                month=8,
                factor=1.4,
                adjustment=0.0,
                explanation="Test",
            ),
            calibration=CalibrationResponse(
                status="NOT_CALIBRATED",
                calibration_shift=0.0,
                explanation="Test",
            ),
            ais_gap=AISGapResponse(),
            static_spacing=StaticSpacingResponse(),
            vessel_evidence=[],
            provenance={},
        )

    def test_build_evidence(self):
        incident = self._make_incident()
        drift_result = self._make_drift_result()
        candidates = self._make_candidates()
        intelligence = self._make_intelligence()
        settings = Settings()

        evidence = build_investigation_evidence(
            incident=incident,
            drift_result=drift_result,
            candidates=candidates,
            intelligence=intelligence,
            settings=settings,
            environmental_provider_name="mock",
            ais_provider_name="gfw",
        )

        assert isinstance(evidence, InvestigationEvidence)
        assert evidence.incident_id == "INC-TEST-001"
        assert evidence.detection.raw_model_confidence == 0.85
        assert evidence.drift.method == "first_order_backward_hindcast"
        assert len(evidence.candidates) == 1
        assert evidence.candidates[0].mmsi == "987654321"

    def test_evidence_serializes(self):
        incident = self._make_incident()
        drift_result = self._make_drift_result()
        candidates = self._make_candidates()
        intelligence = self._make_intelligence()
        settings = Settings()

        evidence = build_investigation_evidence(
            incident=incident,
            drift_result=drift_result,
            candidates=candidates,
            intelligence=intelligence,
            settings=settings,
        )

        data = evidence.model_dump(by_alias=True)
        json_str = json.dumps(data, default=str)
        assert "INC-TEST-001" in json_str
        assert "987654321" in json_str


# ── MockReportProvider tests ────────────────────────────────────────────


class TestMockReportProvider:
    """MockReportProvider must generate deterministic reports."""

    def test_generates_report(self):
        provider = MockReportProvider()
        evidence = {
            "incidentId": "INC-TEST-001",
            "detection": {
                "rawModelConfidence": 0.85,
                "adjustedConfidence": 0.78,
                "calibrationStatus": "NOT_CALIBRATED",
                "detectionAreaKm2": 10.0,
                "sarModel": "TinyUNet",
                "modelVersion": "1.0",
            },
            "environment": {"environmentStatus": "DEMO", "provider": "mock"},
            "drift": {"method": "first_order", "sourceLatitude": 14.8, "sourceLongitude": 72.8},
            "candidates": [
                {"mmsi": "987654321", "vesselName": "TEST VESSEL", "attributionScore": 0.75},
            ],
            "ais": {"provider": "gfw", "vesselCount": 1},
        }
        report = provider.generate_report(evidence)
        assert isinstance(report, InvestigationReport)
        assert "INC-TEST-001" in report.title
        assert report.human_review_required is True
        assert len(report.candidate_assessments) == 1

    def test_report_has_all_sections(self):
        provider = MockReportProvider()
        evidence = {
            "incidentId": "INC-TEST-002",
            "detection": {"rawModelConfidence": 0.9, "adjustedConfidence": 0.85},
            "environment": {"environmentStatus": "REAL"},
            "drift": {},
            "candidates": [],
            "ais": {},
        }
        report = provider.generate_report(evidence)
        assert report.executive_summary
        assert report.detection_assessment
        assert report.environment_assessment
        assert report.drift_assessment
        assert report.ais_assessment
        assert report.uncertainty
        assert len(report.recommended_actions) > 0
        assert len(report.limitations) > 0

    def test_deterministic_output(self):
        provider = MockReportProvider()
        evidence = {"incidentId": "INC-TEST-003", "detection": {}, "environment": {}, "drift": {}, "candidates": [], "ais": {}}
        report1 = provider.generate_report(evidence)
        report2 = provider.generate_report(evidence)
        assert report1.title == report2.title
        assert report1.executive_summary == report2.executive_summary


# ── Report repository tests ─────────────────────────────────────────────


class TestReportRepository:
    """Report repository must store and retrieve reports."""

    def test_store_and_retrieve(self):
        repo = ReportRepository()
        report = StoredReport(
            report_id="RPT-001",
            incident_id="INC-001",
            generated_at="2026-08-25T12:00:00Z",
            provider="mock",
            model="mock",
            report_json={"title": "Test Report"},
        )
        repo.store_report(report)
        retrieved = repo.get_report("RPT-001")
        assert retrieved is not None
        assert retrieved.incident_id == "INC-001"

    def test_get_by_incident(self):
        repo = ReportRepository()
        report = StoredReport(
            report_id="RPT-002",
            incident_id="INC-002",
            generated_at="2026-08-25T12:00:00Z",
            provider="mock",
            model="mock",
            report_json={},
        )
        repo.store_report(report)
        retrieved = repo.get_report_by_incident("INC-002")
        assert retrieved is not None
        assert retrieved.report_id == "RPT-002"

    def test_list_reports(self):
        repo = ReportRepository()
        for i in range(3):
            repo.store_report(StoredReport(
                report_id=f"RPT-{i}",
                incident_id=f"INC-{i}",
                generated_at="2026-08-25T12:00:00Z",
                provider="mock",
                model="mock",
                report_json={},
            ))
        reports = repo.list_reports()
        assert len(reports) == 3


# ── API endpoint tests ──────────────────────────────────────────────────


class TestReportAPI:
    """Report API endpoints must work correctly."""

    def test_generate_report(self, client):
        resp = client.post("/api/v1/reports/investigation/IN-250825-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "reportId" in data
        assert "report" in data
        assert data["provider"] in ("mock", "groq")
        assert data["report"]["humanReviewRequired"] is True

    def test_generate_report_404(self, client):
        resp = client.post("/api/v1/reports/investigation/NONEXISTENT")
        assert resp.status_code == 404

    def test_get_report(self, client):
        # Generate first
        gen_resp = client.post("/api/v1/reports/investigation/IN-250825-001")
        assert gen_resp.status_code == 200

        # Get
        get_resp = client.get("/api/v1/reports/investigation/IN-250825-001")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert "report" in data

    def test_get_report_404(self, client):
        resp = client.get("/api/v1/reports/investigation/NONEXISTENT")
        assert resp.status_code == 404

    def test_list_reports(self, client):
        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
