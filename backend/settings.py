from pydantic import BaseModel
import os

class Settings(BaseModel):
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    stockfish_path: str | None = os.getenv("STOCKFISH_PATH")
    stockfish_depth: int = int(os.getenv("STOCKFISH_DEPTH", "12"))

settings = Settings()
