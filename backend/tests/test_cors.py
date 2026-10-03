"""CORS regression tests — verify all configured origins receive
Access-Control-Allow-Origin headers on AIS endpoints.

These tests use the real FastAPI app + CORSMiddleware (not mocked)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

DISALLOWED_ORIGINS = [
    "http://evil.com",
    "https://attacker.example.com",
]


def _make_client(extra_origins: str = "") -> tuple[TestClient, Settings]:
    """Create a TestClient with the full production CORS config."""
    cors = ",".join(ALLOWED_ORIGINS)
    if extra_origins:
        cors += "," + extra_origins
    settings = Settings(
        database_url="",
        seed_demo_data=True,
        scene_storage_dir=".tmp-cors-tests/scenes",
        model_adapter="mock",
        cors_origins=cors,
    )
    app = create_app(settings)
    return TestClient(app, raise_server_exceptions=False), settings


@pytest.fixture()
def cors_client():
    client, _ = _make_client()
    return client


# ── Allowed origins ──────────────────────────────────────────────────────


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_ais_status_allowed_origin(cors_client: TestClient, origin: str):
    """Every configured origin must receive Access-Control-Allow-Origin."""
    resp = cors_client.get(
        "/api/v1/ais/status",
        headers={"Origin": origin},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_health_allowed_origin(cors_client: TestClient, origin: str):
    """CORS must work on health endpoint too."""
    resp = cors_client.get(
        "/api/v1/health",
        headers={"Origin": origin},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_incidents_allowed_origin(cors_client: TestClient, origin: str):
    """CORS must work on the incidents endpoint."""
    resp = cors_client.get(
        "/api/v1/spills",
        headers={"Origin": origin},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


# ── Disallowed origins ───────────────────────────────────────────────────


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
def test_cors_ais_status_disallowed_origin(cors_client: TestClient, origin: str):
    """Unlisted origins must NOT receive Access-Control-Allow-Origin."""
    resp = cors_client.get(
        "/api/v1/ais/status",
        headers={"Origin": origin},
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


# ── Preflight (OPTIONS) ─────────────────────────────────────────────────


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_preflight_ais_status(cors_client: TestClient, origin: str):
    """OPTIONS preflight must return allowed methods and the origin."""
    resp = cors_client.options(
        "/api/v1/ais/status",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette CORSMiddleware responds to preflight even if the route
    # doesn't explicitly handle OPTIONS (returns 405 or 200).
    assert resp.status_code in (200, 405)
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"
    assert "access-control-allow-methods" in resp.headers


# ── No Origin header ────────────────────────────────────────────────────


def test_cors_no_origin_header(cors_client: TestClient):
    """Requests without an Origin header must not get CORS headers."""
    resp = cors_client.get("/api/v1/ais/status")
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


# ── Stream endpoint CORS ────────────────────────────────────────────────


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_ais_vessels_allowed_origin(cors_client: TestClient, origin: str):
    """The /ais/vessels endpoint must return CORS headers.

    CORSMiddleware is global — it applies to ALL routes including the
    /ais/stream SSE endpoint.  We verify CORS on /ais/vessels (a normal
    GET that doesn't block) as a proxy for all AIS routes.
    """
    resp = cors_client.get(
        "/api/v1/ais/vessels",
        headers={"Origin": origin},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"



