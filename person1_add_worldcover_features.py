import os
import math
import requests
import numpy as np
import pandas as pd
import rasterio

INPUT = "person1_fire_type_classification_v0.csv"
OUTPUT = "person1_fire_type_classification_worldcover.csv"
CACHE = "worldcover_tiles"

os.makedirs(CACHE, exist_ok=True)

BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"

FOREST = {10, 20}
OPEN_VEGETATION = {30, 40}
BUILT = {50}
BARE = {60}
WATER_WETLAND = {80, 90, 95, 70}
OTHER_VEGETATION = {100}


def tile_name(lat, lon):
    lat0 = math.floor(lat / 3.0) * 3
    lon0 = math.floor(lon / 3.0) * 3
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}"


def download_tile(tile):
    fn = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    local = os.path.join(CACHE, fn)

    if os.path.exists(local):
        return local

    url = f"{BASE}/{fn}"
    print("Downloading", tile)

    r = requests.get(url, timeout=120)
    r.raise_for_status()

    with open(local, "wb") as f:
        f.write(r.content)

    return local


def sample_landcover(path, lon, lat):
    with rasterio.open(path) as ds:
        row, col = ds.index(lon, lat)
        arr = ds.read(1, window=((row, row + 1), (col, col + 1)))

        if arr.size == 0:
            return np.nan

        return int(arr[0, 0])


def main():
    df = pd.read_csv(INPUT)

    df["worldcover_tile"] = [
        tile_name(float(lat), float(lon))
        for lat, lon in zip(df.latitude, df.longitude)
    ]

    tile_paths = {}

    for tile in sorted(df.worldcover_tile.dropna().unique()):
        tile_paths[tile] = download_tile(tile)

    df["worldcover_class"] = [
        sample_landcover(tile_paths[tile], float(lon), float(lat))
        for tile, lon, lat in zip(df.worldcover_tile, df.longitude, df.latitude)
    ]

    df["forest_like_landcover"] = df.worldcover_class.isin(FOREST).astype(int)
    df["open_vegetation_landcover"] = df.worldcover_class.isin(OPEN_VEGETATION).astype(int)
    df["builtup_landcover"] = df.worldcover_class.isin(BUILT).astype(int)
    df["bare_sparse_landcover"] = df.worldcover_class.isin(BARE).astype(int)
    df["water_wetland_landcover"] = df.worldcover_class.isin(WATER_WETLAND).astype(int)
    df["other_vegetation_landcover"] = df.worldcover_class.isin(OTHER_VEGETATION).astype(int)

    industrial = (
        (df["type"] == 2)
        & (df["distance_to_nearest_industry_km"] <= 1.0)
        & (df["status"].isin(["operating", "construction", "mothballed", "permitted"]))
    )

    forest = (
        (df["type"] == 0)
        & (df["forest_like_landcover"] == 1)
        & (df["distance_to_nearest_industry_km"] >= 5.0)
    )

    other_natural = (
        (df["type"] == 0)
        & ((df["open_vegetation_landcover"] == 1) | (df["bare_sparse_landcover"] == 1))
        & (df["distance_to_nearest_industry_km"] >= 5.0)
    )

    df["proposed_weak_class"] = np.select(
        [industrial, forest, other_natural],
        ["industrial_proxy", "forest_proxy", "other_natural_proxy"],
        default=""
    )

    df.to_csv(OUTPUT, index=False)

    print("\nClass counts:")
    print(df.loc[df.proposed_weak_class != "", "proposed_weak_class"].value_counts())
    print("\nSaved:", OUTPUT)


if __name__ == "__main__":
    main()