from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration.

    Every deployment-specific value comes from the environment (.env supported).
    Nothing about the ML model is hardcoded.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    api_version: str = "1.0.0-phase1b"

    # Database — empty string => in-memory development repository
    database_url: str = ""
    seed_demo_data: bool = True

    # Model adapter configuration (consumed via the OilSpillModel interface)
    model_adapter: str = "mock"          # mock | torch (torch arrives with the real model)
    model_path: str = "/models/oil_spill/model.pth"
    model_name: str = "OilSpillNet"
    model_version: str = "1.0-dev"
    model_device: str = "auto"
    model_threshold: float = 0.5
    model_tile_size: int = 512
    model_tile_stride: int = 384
    model_batch_size: int = 8
    model_max_tiles: int = 0  # 0 = unlimited; >0 = smoke-test cap

    # ---- Satellite ingestion (Phase 2) -----------------------------------
    # 'mock'  -> clearly-labeled synthetic scenes (no network, no credentials)
    # 'copernicus' -> REAL Copernicus Data Space Ecosystem catalogue
    satellite_provider: str = "mock"
    cdse_username: str = ""              # env-only; never hardcode
    cdse_password: str = ""              # env-only; never hardcode
    cdse_token_url: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    cdse_stac_search_url: str = "https://stac.dataspace.copernicus.eu/v1/search"
    cdse_stac_item_url: str = "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-1-grd/items/{item_id}"
    catalogue_query_limit: int = 20      # hard cap on discovery result size

    # India maritime AOI. Default is a documented development bounding box;
    # point india_aoi_geojson_path at an official EEZ boundary for production.
    india_aoi_bbox: str = "68.0,6.0,94.5,24.5"   # west,south,east,north (WGS84)
    india_aoi_geojson_path: str = ""

    # Download behaviour (streaming + retries)
    download_chunk_mb: int = 1
    download_max_retries: int = 3
    download_retry_backoff_seconds: float = 5.0

    # Storage: 'local' filesystem or S3-compatible object store ('s3')
    storage_backend: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # SAR preprocessing pipeline — JSON list of stage configs, e.g.
    #   '[{"name":"subset_bbox"},{"name":"to_db"},{"name":"normalize_percentile"}]'
    # Empty string => sensible GRD defaults. Final MODEL-specific stages stay
    # configurable until the trained-model contract is delivered.
    preprocessing_stages: str = ""

    # Real Sentinel-1 GRD preprocessing (Phase 2C). Scientifically neutral
    # defaults: native 10 m preserved; noise removal off until the ML
    # contract decides the final input representation.
    grd_target_crs: str = "EPSG:4326"
    grd_target_resolution_m: float = 10.0
    grd_resampling: str = "bilinear"
    grd_apply_noise_removal: bool = False
    grd_gcp_poly_order: int = 3

    # Post-processing
    min_poly_area_km2: float = 0.05
    polygon_simplify_tolerance_m: float = 25.0

    # AIS vessel correlation (Phase 4)
    ais_provider: str = "mock"          # mock | gfw
    gfw_api_token: str = ""             # env-only; Global Fishing Watch API token
    ais_search_radius_km: float = 50.0
    ais_time_window_hours: float = 6.0
    ais_distance_weight: float = 0.50
    ais_time_weight: float = 0.30
    ais_track_weight: float = 0.20

    # Drift / hindcast (Phase 5)
    drift_provider: str = "mock"        # mock | first_order
    environmental_provider: str = "mock"  # mock | real
    drift_hours: float = 24.0           # backward integration window
    drift_timestep_minutes: float = 15.0
    drift_ensemble_size: int = 50
    windage_coefficient: float = 0.03   # typical 1–4% of wind speed
    windage_coefficient_std: float = 0.01  # ensemble perturbation
    current_fraction: float = 1.0       # fraction of current to apply
    position_noise_km: float = 0.5      # per-timestep position noise
    drift_uncertainty_km_per_hour: float = 0.5  # accumulated uncertainty rate

    # Phase 7: Real environmental data (CMEMS + ERA5)
    cmems_username: str = ""            # Copernicus Marine account username
    cmems_password: str = ""            # Copernicus Marine account password
    cds_api_key: str = ""               # CDS API personal access token
    cds_api_url: str = "https://cds.climate.copernicus.eu/api"
    env_cache_bbox_pad_deg: float = 0.5  # padding around slick for bbox
    env_cache_temporal_pad_hours: float = 1.0  # padding around time window

    # Phase 9: Groq investigation reports
    groq_api_key: str = ""              # Groq API key (never commit)
    groq_model: str = "llama-3.3-70b-versatile"  # Groq model for reports

    # Storage
    scene_storage_dir: str = "./data/scenes"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_postgis(self) -> bool:
        return self.database_url.strip().lower().startswith(("postgresql", "postgis"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
