import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "default_key")
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    N8N_WEBHOOK_URL: str = os.getenv("N8N_WEBHOOK_URL", "")

settings = Settings()