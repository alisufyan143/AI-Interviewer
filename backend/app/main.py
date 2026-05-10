from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.api.interviews import router as interviews_router
from app.ws.interview_handler import router as ws_router


from app.services.model_manager import model_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create database tables
    await init_db()
    model_manager.initialize_models()
    print(f"[OK] {settings.APP_NAME} started")
    print(f"[UPLOADS] {settings.UPLOADS_DIR}")
    print(f"[RECORDINGS] {settings.RECORDINGS_DIR}")
    yield
    # Shutdown
    print(f"[SHUTDOWN] {settings.APP_NAME} shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered initial interview screening platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files and recordings as static files
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")
app.mount("/recordings", StaticFiles(directory=str(settings.RECORDINGS_DIR)), name="recordings")

# API Routes
app.include_router(interviews_router)
app.include_router(ws_router) 


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
    }
