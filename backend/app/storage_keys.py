"""Canonical storage keys for satellite artifacts."""

from __future__ import annotations


def product_key_for(scene_id: str, *, mock: bool) -> str:
    ext = "tif" if mock else "zip"
    return f"products/{scene_id}.{ext}"


def preprocessed_key_for(scene_id: str) -> str:
    return f"preprocessed/{scene_id}.tif"


def preview_key_for(scene_id: str) -> str:
    return f"previews/{scene_id}.png"
