import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "default_key")
    CHROMA_HOST: str = "chromadb" # Docker service name
    CHROMA_PORT: int = 8000

settings = Settings()