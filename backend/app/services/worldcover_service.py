import math
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from functools import lru_cache

from app.config import settings

FOREST_CLASSES = {10, 20}
OPEN_CLASSES = {30, 40}
BUILT_CLASSES = {50}
BARE_CLASSES = {60}
WATER_CLASSES = {70, 80, 90, 95}
MOSS_CLASSES = {100}

# Try importing rasterio
RASTERIO_AVAILABLE = False
try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


def get_worldcover_tile_name(lat: float, lon: float) -> str:
    """Derive 3x3 degree ESA WorldCover tile name for given lat/lon."""
    a = math.floor(float(lat) / 3.0) * 3
    o = math.floor(float(lon) / 3.0) * 3
    lat_str = f"{'N' if a >= 0 else 'S'}{abs(a):02d}"
    lon_str = f"{'E' if o >= 0 else 'W'}{abs(o):03d}"
    return f"{lat_str}{lon_str}"


class WorldCoverService:
    def __init__(self, tiles_dir: Optional[Path] = None):
        self.tiles_dir = tiles_dir or settings.WORLDCOVER_TILES_DIR
        self._tile_datasets: Dict[str, Any] = {}
        self._memory_cache: Dict[Tuple[float, float], Dict[str, Any]] = {}

    def _get_local_tile_path(self, tile_name: str) -> Optional[Path]:
        """Find local TIF tile file if available."""
        if not self.tiles_dir.exists():
            return None
        
        tif_filename = f"ESA_WorldCover_10m_2021_v200_{tile_name}_Map.tif"
        full_path = self.tiles_dir / tif_filename
        if full_path.exists():
            return full_path
        return None

    @lru_cache(maxsize=10000)
    def sample_landcover(self, lat: float, lon: float) -> Dict[str, Any]:
        """Sample landcover class for a given latitude and longitude.
        
        Returns dictionary of landcover class and binary indicator features.
        """
        # Round coordinate to ~10m precision for cache key lookup
        cache_key = (round(lat, 4), round(lon, 4))
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        worldcover_class: Optional[int] = None
        tile_name = get_worldcover_tile_name(lat, lon)

        if RASTERIO_AVAILABLE:
            tile_path = self._get_local_tile_path(tile_name)
            if tile_path:
                try:
                    if tile_name not in self._tile_datasets:
                        self._tile_datasets[tile_name] = rasterio.open(tile_path)
                    
                    src = self._tile_datasets[tile_name]
                    vals = list(src.sample([(lon, lat)]))
                    if vals and len(vals[0]) > 0:
                        val = int(vals[0][0])
                        if src.nodata is None or val != src.nodata:
                            worldcover_class = val
                except Exception as e:
                    print(f"[WorldCoverService] Error sampling raster {tile_name}: {e}")

        # Default fallback class if raster tile unavailable
        if worldcover_class is None:
            worldcover_class = 40  # Default open vegetation/cropland

        features = self.derive_landcover_features(worldcover_class)
        self._memory_cache[cache_key] = features
        return features

    @staticmethod
    def derive_landcover_features(worldcover_class: Optional[int]) -> Dict[str, Any]:
        """Derive binary landcover indicator features from worldcover_class code."""
        wc = worldcover_class if worldcover_class is not None else 40
        return {
            "worldcover_class": wc,
            "forest_like_landcover": 1 if wc in FOREST_CLASSES else 0,
            "open_vegetation_landcover": 1 if wc in OPEN_CLASSES else 0,
            "builtup_landcover": 1 if wc in BUILT_CLASSES else 0,
            "bare_sparse_landcover": 1 if wc in BARE_CLASSES else 0,
            "water_wetland_landcover": 1 if wc in WATER_CLASSES else 0,
            "moss_lichen_landcover": 1 if wc in MOSS_CLASSES else 0,
        }

    def close(self):
        """Close opened raster datasets."""
        for ds in self._tile_datasets.values():
            try:
                ds.close()
            except Exception:
                pass
        self._tile_datasets.clear()


# Global singleton instance
worldcover_service = WorldCoverService()
