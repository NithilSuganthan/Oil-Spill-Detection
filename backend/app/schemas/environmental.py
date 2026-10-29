"""Environmental grid API schemas.

Provides the response contract for the /environmental/grid endpoint.
The frontend consumes this to drive particle visualization and metadata display.
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.drift import CamelModel


class WindVectorResponse(CamelModel):
    """Wind vector at a single grid point."""

    u: float = Field(..., description="Eastward wind component (m/s)")
    v: float = Field(..., description="Northward wind component (m/s)")
    speed_ms: float = Field(..., description="Wind speed (m/s)")
    speed_kts: float = Field(..., description="Wind speed (knots)")
    direction_deg: float = Field(..., description="Wind direction (degrees, meteorological convention)")


class CurrentVectorResponse(CamelModel):
    """Ocean current vector at a single grid point."""

    u: float = Field(..., description="Eastward current component (m/s)")
    v: float = Field(..., description="Northward current component (m/s)")
    speed_ms: float = Field(..., description="Current speed (m/s)")
    direction_deg: float = Field(..., description="Current direction (degrees, meteorological convention)")


class EnvironmentalMetadataResponse(CamelModel):
    """Metadata about the environmental data source."""

    provider: str = Field(..., description="Data provider name (e.g., 'CMEMS+ERA5', 'mock', 'unavailable')")
    status: str = Field(..., description="REAL | DEMO | DATA_UNAVAILABLE | CREDENTIALS_REQUIRED")
    data_time: str | None = Field(None, description="ISO-8601 timestamp of the environmental data")
    data_age_minutes: float | None = Field(None, description="Minutes since data was generated")
    spatial_resolution_deg: float | None = Field(None, description="Grid resolution in degrees")
    temporal_resolution_hours: float | None = Field(None, description="Temporal resolution in hours")
    bbox: list[float] = Field(default_factory=list, description="[min_lon, min_lat, max_lon, max_lat]")
    grid_size: list[int] = Field(default_factory=list, description="[n_lat, n_lon]")


class EnvironmentalGridResponse(CamelModel):
    """Full environmental grid response for frontend visualization."""

    wind: list[list[float | None]] = Field(
        ..., description="Wind speed (knots) grid [lat][lon]. None = no data."
    )
    current: list[list[float | None]] = Field(
        ..., description="Current speed (m/s) grid [lat][lon]. None = no data."
    )
    wind_u: list[list[float | None]] = Field(
        ..., description="Wind u-component (m/s) grid [lat][lon]"
    )
    wind_v: list[list[float | None]] = Field(
        ..., description="Wind v-component (m/s) grid [lat][lon]"
    )
    current_u: list[list[float | None]] = Field(
        ..., description="Current u-component (m/s) grid [lat][lon]"
    )
    current_v: list[list[float | None]] = Field(
        ..., description="Current v-component (m/s) grid [lat][lon]"
    )
    lats: list[float] = Field(..., description="Latitude axis (ascending)")
    lons: list[float] = Field(..., description="Longitude axis (ascending)")
    metadata: EnvironmentalMetadataResponse
    wind_point: WindVectorResponse | None = Field(
        None, description="Point wind vector at incident centroid (for panel display)"
    )
    current_point: CurrentVectorResponse | None = Field(
        None, description="Point current vector at incident centroid (for panel display)"
    )
