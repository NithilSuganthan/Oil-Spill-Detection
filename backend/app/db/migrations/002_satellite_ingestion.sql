-- Migration 002: satellite catalogue ingestion metadata (Phase 2).
-- Adds real-catalogue fields to satellite_scenes (idempotent; PostgreSQL 9.6+).

ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS product_name        VARCHAR(256);
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS source_provider     VARCHAR(32) DEFAULT 'mock';
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS orbit_state         VARCHAR(16);
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS absolute_orbit      INTEGER;
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS relative_orbit      INTEGER;
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS download_url        TEXT;
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS file_size_bytes     INTEGER;
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS product_type        VARCHAR(32);
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS thumbnail_url       TEXT;
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS preview_path        TEXT;
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS pipeline_state      VARCHAR(24);
ALTER TABLE satellite_scenes ADD COLUMN IF NOT EXISTS metadata_extra_json TEXT;

CREATE INDEX IF NOT EXISTS idx_satellite_scenes_source_provider
    ON satellite_scenes (source_provider);
CREATE INDEX IF NOT EXISTS idx_satellite_scenes_pipeline_state
    ON satellite_scenes (pipeline_state);
