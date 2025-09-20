import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "default_key")
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    N8N_WEBHOOK_URL: str = os.getenv("N8N_WEBHOOK_URL", "https://sidhya.app.n8n.cloud/webhook-test/13777be7-74c6-47b8-b15f-bb084cb08105")

settings = Settings()