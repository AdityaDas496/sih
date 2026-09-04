import os
import sys
from pathlib import Path

# Workspace Root Directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

class Settings:
    PROJECT_NAME: str = "Satellite Industrial Fire Detection API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # Paths relative to repository root
    PERSON1_MODEL_PATH: Path = Path(os.getenv("PERSON1_MODEL_PATH", BASE_DIR / "person1" / "model" / "person1_fire_type_classifier_v0.joblib"))
    GIS_FACILITIES_PATH: Path = Path(os.getenv("GIS_FACILITIES_PATH", BASE_DIR / "gis" / "india_industrial_facilities.geojson"))
    SAMPLE_PREDICTIONS_PATH: Path = Path(os.getenv("SAMPLE_PREDICTIONS_PATH", BASE_DIR / "outputs" / "sample" / "person1_fire_type_classification_predictions_v0.csv"))
    WORLDCOVER_TILES_DIR: Path = Path(os.getenv("WORLDCOVER_TILES_DIR", BASE_DIR / "worldcover_tiles"))

    # Server & CORS
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,*").split(",")

settings = Settings()
