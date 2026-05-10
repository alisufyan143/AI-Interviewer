import logging
from google import genai
from app.config import settings

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.models = {
            "interview": settings.GEMINI_LIVE_MODEL,
            "scoring": settings.GEMINI_SCORING_MODEL,
            "parsing": settings.GEMINI_PARSING_MODEL,
        }
        self.status = {k: "UNKNOWN" for k in self.models}

    def initialize_models(self):
        """Verify that the configured models are accessible."""
        print("\n" + "="*50)
        print("AI MODEL STATUS")
        print("="*50)
        
        for key, model_id in self.models.items():
            try:
                # Use a simple get_model call to verify availability
                self.client.models.get(model=model_id)
                self.status[key] = "READY"
                print(f"{key.upper():<10}: {model_id:<25} [READY]")
            except Exception as e:
                self.status[key] = "ERROR"
                logger.error(f"Failed to verify model {model_id}: {e}")
                print(f"{key.upper():<10}: {model_id:<25} [ERROR]")
        
        print("="*50 + "\n")

    def get_model(self, key: str) -> str:
        """Return the model ID for a specific service, with fallback."""
        return self.models.get(key, settings.GEMINI_LIVE_MODEL)

    def get_status(self):
        return self.status

model_manager = ModelManager()
