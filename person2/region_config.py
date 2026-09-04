"""
Person 2 — Region configuration.

Defines the study region bounding box, country code, and spatial boundary
filtering for India. Shared across all Person 2 modules.
"""

from pathlib import Path
import geopandas as gpd
import pandas as pd

# -----------------------------------------------------------------
# Country & Study Region Configuration
# -----------------------------------------------------------------
COUNTRY_CODE = "IND"
REGION_NAME = "india"

# Nationwide bounding box encompassing all of mainland India and islands
BBOX = {
    "south": 6.50,
    "west": 68.00,
    "north": 35.50,
    "east": 97.50,
}

# Path to India official boundary GeoJSON
PERSON2_DIR = Path(__file__).resolve().parent
INDIA_BOUNDARY_PATH = PERSON2_DIR / "india_boundary.geojson"

_CACHED_INDIA_GEOMETRY = None


def get_india_boundary():
    """Load and cache the India boundary polygon/multipolygon."""
    global _CACHED_INDIA_GEOMETRY
    if _CACHED_INDIA_GEOMETRY is None:
        if not INDIA_BOUNDARY_PATH.exists():
            raise FileNotFoundError(
                f"India boundary file not found at {INDIA_BOUNDARY_PATH}. "
                "Ensure person2/india_boundary.geojson is present."
            )
        gdf = gpd.read_file(INDIA_BOUNDARY_PATH)
        _CACHED_INDIA_GEOMETRY = gdf.unary_union
    return _CACHED_INDIA_GEOMETRY


def filter_points_within_india(
    df: pd.DataFrame,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
) -> pd.DataFrame:
    """
    Filter points in a DataFrame to strictly those within India's borders.
    Points outside India (e.g. in bordering countries or international waters)
    are discarded.
    """
    if len(df) == 0:
        return df

    india_geom = get_india_boundary()

    # Fast bounding box pre-filter
    valid_coords = (
        (df[lat_col] >= BBOX["south"])
        & (df[lat_col] <= BBOX["north"])
        & (df[lon_col] >= BBOX["west"])
        & (df[lon_col] <= BBOX["east"])
    )
    pre_filtered = df[valid_coords].copy()

    if len(pre_filtered) == 0:
        return pre_filtered

    # Exact spatial polygon containment check
    points = gpd.points_from_xy(pre_filtered[lon_col], pre_filtered[lat_col], crs="EPSG:4326")
    points_series = gpd.GeoSeries(points, crs="EPSG:4326")
    within_mask = points_series.within(india_geom)

    filtered = pre_filtered[within_mask.values].copy()
    dropped_count = len(df) - len(filtered)
    if dropped_count > 0:
        print(f"  [Boundary Filter] Filtered out {dropped_count} points outside India's borders "
              f"({len(filtered)} remaining).")
    return filtered

