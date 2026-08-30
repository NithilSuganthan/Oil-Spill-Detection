-- 001_init_postgis.sql — SAGAR WATCH initial schema (PostgreSQL + PostGIS)
-- Run as a superuser or the schema owner:
--   psql "postgresql://sagar:sagar@localhost:5432/sagarwatch" -f 001_init_postgis.sql

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS satellite_scenes (
    id               VARCHAR(64) PRIMARY KEY,
    product_id       VARCHAR(128) NOT NULL,
    satellite        VARCHAR(32)  NOT NULL,
    sensor           VARCHAR(32)  NOT NULL DEFAULT 'SAR C-band',
    acquisition_mode VARCHAR(8)   NOT NULL DEFAULT 'IW',
    polarisation     VARCHAR(16)  NOT NULL DEFAULT 'VV + VH',
    acquisition_time TIMESTAMPTZ,
    processing_time  TIMESTAMPTZ,
    status           VARCHAR(16)  NOT NULL DEFAULT 'queued',
    image_path       TEXT,
    is_demo          BOOLEAN      NOT NULL DEFAULT FALSE,
    footprint        geometry(POLYGON, 4326)
);

CREATE INDEX IF NOT EXISTS idx_satellite_scenes_footprint
    ON satellite_scenes USING GIST (footprint);
CREATE INDEX IF NOT EXISTS idx_satellite_scenes_acq
    ON satellite_scenes (acquisition_time DESC);

CREATE TABLE IF NOT EXISTS spill_incidents (
    id                   VARCHAR(32) PRIMARY KEY,   -- e.g. IN-250825-001
    scene_id             VARCHAR(64) NOT NULL REFERENCES satellite_scenes(id),
    confidence           DOUBLE PRECISION NOT NULL, -- MODEL CONFIDENCE 0..1
    area_km2             DOUBLE PRECISION NOT NULL, -- geodesic (WGS84) area
    perimeter_km         DOUBLE PRECISION NOT NULL, -- geodesic perimeter
    detected_at          TIMESTAMPTZ NOT NULL,
    region               VARCHAR(48) NOT NULL,
    location_description TEXT        NOT NULL,
    satellite            VARCHAR(32) NOT NULL,
    model_name           VARCHAR(64) NOT NULL,
    model_version        VARCHAR(32) NOT NULL,
    status               VARCHAR(16) NOT NULL DEFAULT 'completed',
    wind_speed_kts       DOUBLE PRECISION,
    estimated_volume_tons DOUBLE PRECISION,
    level                VARCHAR(8)  NOT NULL,      -- derived: HIGH/MEDIUM/LOW
    is_demo              BOOLEAN     NOT NULL DEFAULT FALSE,
    centroid             geometry(POINT, 4326) NOT NULL,
    geometry             geometry(POLYGON, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spill_incidents_geometry
    ON spill_incidents USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_spill_incidents_centroid
    ON spill_incidents USING GIST (centroid);
CREATE INDEX IF NOT EXISTS idx_spill_incidents_detected
    ON spill_incidents (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_spill_incidents_region
    ON spill_incidents (region);
CREATE INDEX IF NOT EXISTS idx_spill_incidents_confidence
    ON spill_incidents (confidence);

CREATE TABLE IF NOT EXISTS model_runs (
    id                VARCHAR(64) PRIMARY KEY,
    scene_id          VARCHAR(64) NOT NULL REFERENCES satellite_scenes(id),
    model_name        VARCHAR(64) NOT NULL,
    model_version     VARCHAR(32) NOT NULL,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    inference_time_ms INTEGER,
    status            VARCHAR(16) NOT NULL DEFAULT 'running',
    error_message     TEXT
);

CREATE INDEX IF NOT EXISTS idx_model_runs_scene ON model_runs (scene_id);
