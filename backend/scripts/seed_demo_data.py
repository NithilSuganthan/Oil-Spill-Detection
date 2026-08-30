"""Seed demo data into the configured repository.

Usage:
    python scripts/seed_demo_data.py [--force]

DEVELOPMENT/DEMO ONLY — inserts clearly-flagged demo incidents
(is_demo=true) so the frontend can be exercised without real satellite data.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.seed import seed_demo_data
from app.db.session import create_repository

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed SAGAR WATCH demo data")
    parser.add_argument(
        "--force", action="store_true", help="seed even if data already exists"
    )
    args = parser.parse_args()

    settings = get_settings()
    repo = create_repository(settings)
    count = seed_demo_data(repo, force=args.force)
    print(f"Seeded {count} demo incidents "
          f"({'in-memory dev' if not settings.use_postgis else 'PostGIS'} repository).")


if __name__ == "__main__":
    main()
