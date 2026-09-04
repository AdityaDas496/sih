import math, numpy as np, pandas as pd, rasterio

INPUT="person1_fire_type_classification_v0.csv"
OUTPUT="person1_fire_type_classification_worldcover.csv"
BASE="https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"

FOREST={10,20}; OPEN={30,40}; BUILT={50}; BARE={60}; WATER={70,80,90,95}; MOSS={100}


def tile_name(lat,lon):
    a=math.floor(float(lat)/3)*3; o=math.floor(float(lon)/3)*3
    return f"{'N' if a>=0 else 'S'}{abs(a):02d}{'E' if o>=0 else 'W'}{abs(o):03d}"


def url_for(tile):
    return f"{BASE}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"


def sample_group(g,url):
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",VSI_CACHE="TRUE",VSI_CACHE_SIZE=50000000,GDAL_CACHEMAX=256,GDAL_HTTP_MULTIRANGE="YES"):
        with rasterio.open("/vsicurl/"+url) as src:
            coords=list(zip(g.longitude.astype(float),g.latitude.astype(float)))
            return {i:(np.nan if src.nodata is not None and x[0]==src.nodata else int(x[0])) for i,x in zip(g.index,src.sample(coords))}


def main():
    df=pd.read_csv(INPUT)
    df["worldcover_tile"]=[tile_name(a,b) for a,b in zip(df.latitude,df.longitude)]
    df["worldcover_class"]=np.nan

    for tile,g in df.groupby("worldcover_tile",sort=True):
        print(f"Reading {tile} remotely ({len(g):,} points)...",flush=True)
        try:
            vals=sample_group(g,url_for(tile))
            for i,v in vals.items(): df.at[i,"worldcover_class"]=v
            print(f"  done: {len(vals):,}",flush=True)
        except Exception as e:
            print(f"  FAILED: {e}",flush=True)

    df["worldcover_class"]=pd.to_numeric(df.worldcover_class,errors="coerce").astype("Int64")
    df["forest_like_landcover"]=df.worldcover_class.isin(FOREST).astype(int)
    df["open_vegetation_landcover"]=df.worldcover_class.isin(OPEN).astype(int)
    df["builtup_landcover"]=df.worldcover_class.isin(BUILT).astype(int)
    df["bare_sparse_landcover"]=df.worldcover_class.isin(BARE).astype(int)
    df["water_wetland_landcover"]=df.worldcover_class.isin(WATER).astype(int)
    df["moss_lichen_landcover"]=df.worldcover_class.isin(MOSS).astype(int)

    industrial=((df.type==2)&(df.distance_to_nearest_industry_km<=1)&(df.status.isin(["operating","construction","mothballed","permitted"])))
    forest=((df.type==0)&(df.forest_like_landcover==1)&(df.distance_to_nearest_industry_km>=5))
    other=((df.type==0)&((df.open_vegetation_landcover==1)|(df.bare_sparse_landcover==1))&(df.distance_to_nearest_industry_km>=5))

    df["proposed_weak_class"]=np.select([industrial,forest,other],["industrial_proxy","forest_proxy","other_natural_proxy"],default="")
    df.to_csv(OUTPUT,index=False)

    print("\nSaved:",OUTPUT)
    print("\nWeak-label counts:")
    print(df.loc[df.proposed_weak_class!="","proposed_weak_class"].value_counts())


if __name__=="__main__":
    main()