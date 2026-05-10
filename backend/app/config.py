from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Right Recruit AI Interviewer"
    DEBUG: bool = True

    # AI API Keys
    GEMINI_API_KEY: str = "AIzaSyDBZDBXvaeEga6zn-rIAAMGjLN3KRi89ow"
    ASSEMBLYAI_API_KEY: str = "75769324b35d41978372e0fa6986b5a7"
    ELEVENLABS_API_KEY: str = "sk_f375231c88f33fb525cd65111bc5f406f03a43eaa0fddc6b"

    # Model Configuration (Restored names to match application code)
    GEMINI_LIVE_MODEL: str = "gemini-flash-latest"
    ASSEMBLYAI_MODEL: str = "universal-3-pro"
    ELEVENLABS_MODEL: str = "eleven_flash_v2_5"
    
    # Fallback names for other services
    GEMINI_SCORING_MODEL: str = "gemini-flash-latest"
    GEMINI_PARSING_MODEL: str = "gemini-flash-latest"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./right_recruit.db"

    # File storage
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    RECORDINGS_DIR: Path = BASE_DIR / "recordings"

    # Interview defaults
    DEFAULT_MAX_DURATION_MINUTES: int = 15
    MAX_ASSESSMENT_POINTS: int = 10
    MIN_ASSESSMENT_POINTS: int = 3

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

# Ensure directories exist
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
