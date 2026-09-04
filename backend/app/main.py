import sys
from pathlib import Path

# Ensure backend directory is in sys.path for robust module resolution
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import health, detections, facilities, statistics
from app.schemas.detection import Person2InputDetection, CanonicalDetection
from app.schemas.response import ProcessBatchRequest, ProcessBatchResponse
from app.services.detection_store import detection_store
from app.services.worldcover_service import worldcover_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan handler."""
    print("=" * 60)
    print(f"STARTING {settings.PROJECT_NAME} v{settings.VERSION}")
    print("=" * 60)
    
    # Load initial sample detection dataset
    detection_store.load_initial_dataset()
    
    yield
    
    # Shutdown logic
    print("Closing background resources...")
    worldcover_service.close()
    print("Backend server shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API and integration layer connecting satellite fire existence detection, ML classification, and GIS visualization.",
    lifespan=lifespan
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routes
app.include_router(health.router)
app.include_router(detections.router)
app.include_router(facilities.router)
app.include_router(statistics.router)

# Top-level API alias routes matching prompt specs exactly
@app.post("/api/classify", response_model=CanonicalDetection, tags=["Detections"])
def api_classify_alias(payload: Person2InputDetection = Body(...)):
    """Real-time single detection payload classification endpoint alias."""
    return detections.classify_detection(payload)


@app.post("/api/process", response_model=ProcessBatchResponse, tags=["Detections"])
def api_process_alias(payload: ProcessBatchRequest = Body(...)):
    """Batch Person 2 detection processing endpoint alias."""
    return detections.process_batch_detections(payload)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
