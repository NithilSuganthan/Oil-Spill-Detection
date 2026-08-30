"""Verification script for Phase 7 real environmental data.

Tests the RealEnvironmentalProvider with a small bbox around the demo
incident area (72.6°E–73.1°E, 15.0°N–15.6°N) using a historical date
range known to be available.

Usage:
    cd backend
    python scripts/verify_real_env.py

Requires CMEMS and CDS credentials in .env file:
    CMEMS_USERNAME=...
    CMEMS_PASSWORD=...
    CDS_API_KEY=...
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    print("=" * 70)
    print("Phase 7: Real Environmental Data Verification")
    print("=" * 70)

    # Load .env if available
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[OK] Loaded .env from {env_path}")
    except ImportError:
        pass

    cmems_user = os.environ.get("CMEMS_USERNAME", "")
    cmems_pass = os.environ.get("CMEMS_PASSWORD", "")
    cds_key = os.environ.get("CDS_API_KEY", "")

    print(f"\nCMEMS_USERNAME: {'SET' if cmems_user else 'NOT SET'}")
    print(f"CMEMS_PASSWORD: {'SET' if cmems_pass else 'NOT SET'}")
    print(f"CDS_API_KEY:    {'SET' if cds_key else 'NOT SET'}")

    if not cmems_user or not cmems_pass:
        print("\n[SKIP] CMEMS credentials not set. Cannot test real data.")
        print("Set CMEMS_USERNAME and CMEMS_PASSWORD in .env to enable.")
        return 0

    if not cds_key:
        print("\n[SKIP] CDS API key not set. Cannot test ERA5 winds.")
        print("Set CDS_API_KEY in .env to enable.")
        return 0

    # Import and create provider
    from app.services.environmental_real_provider import RealEnvironmentalProvider

    print("\n--- Creating RealEnvironmentalProvider ---")
    try:
        provider = RealEnvironmentalProvider(
            cmems_username=cmems_user,
            cmems_password=cmems_pass,
            cds_api_key=cds_key,
        )
        print("[OK] Provider created successfully")
    except ValueError as e:
        print(f"[FAIL] Provider creation failed: {e}")
        return 1

    # Test parameters
    bbox = (72.6, 15.0, 73.1, 15.6)
    # Use a historical date range (Aug 19, 2026 - known to be in CMEMS/ERA5)
    base_time = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    timesteps = [base_time - timedelta(hours=h) for h in range(4)]

    print(f"\n--- Preparing Cache ---")
    print(f"BBox: {bbox}")
    print(f"Time range: {timesteps[-1].isoformat()} to {timesteps[0].isoformat()}")
    print(f"Timesteps: {len(timesteps)}")

    try:
        provider.prepare_cache(bbox, timesteps)
        print("[OK] Cache prepared successfully")
        print(f"  Lats: {len(provider._cache_lats)} points "
              f"({provider._cache_lats.min():.3f} to {provider._cache_lats.max():.3f})")
        print(f"  Lons: {len(provider._cache_lons)} points "
              f"({provider._cache_lons.min():.3f} to {provider._cache_lons.max():.3f})")
        print(f"  Timesteps: {len(provider._cache_timesteps)}")
    except RuntimeError as e:
        print(f"[FAIL] Cache preparation failed: {e}")
        return 1

    # Test interpolation
    print(f"\n--- Testing Interpolation ---")
    test_points = [
        (15.3, 72.85, timesteps[1]),
        (15.0, 72.6, timesteps[0]),
        (15.6, 73.1, timesteps[-1]),
    ]

    for lat, lon, ts in test_points:
        try:
            conditions = provider.get_conditions(lat, lon, ts)
            print(f"  ({lat:.2f}, {lon:.2f}) @ {ts.strftime('%H:%M')} UTC:")
            print(f"    Current: u={conditions.current_u:.4f} m/s, "
                  f"v={conditions.current_v:.4f} m/s")
            print(f"    Wind:    u={conditions.wind_u:.4f} m/s, "
                  f"v={conditions.wind_v:.4f} m/s")
        except Exception as e:
            print(f"  [FAIL] ({lat:.2f}, {lon:.2f}): {e}")
            return 1

    # Test drift engine with real provider
    print(f"\n--- Testing Drift Engine ---")
    from app.config import Settings
    from app.services.drift_engine import FirstOrderDriftProvider

    settings = Settings(
        drift_provider="first_order",
        environmental_provider="real",
        drift_hours=6.0,
        drift_timestep_minutes=60.0,
        drift_ensemble_size=10,
    )

    engine = FirstOrderDriftProvider(
        environmental_provider=provider,
        settings=settings,
    )

    try:
        result = engine.estimate_source(
            incident_id="verify-001",
            slick_lat=15.3,
            slick_lon=72.85,
            observation_time=base_time,
        )
        print("[OK] Drift analysis completed")
        print(f"  Source: ({result.source_latitude:.4f}, {result.source_longitude:.4f})")
        print(f"  Uncertainty: ±{result.uncertainty_km:.2f} km")
        print(f"  Confidence: {result.confidence:.3f}")
        print(f"  Quality flags: {result.quality_flags}")
        print(f"  Provenance: {result.provenance}")
    except Exception as e:
        print(f"[FAIL] Drift analysis failed: {e}")
        return 1

    # Cleanup
    provider.close()
    print(f"\n{'=' * 70}")
    print("Phase 7 verification PASSED")
    print(f"{'=' * 70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
