from pydantic import BaseModel
import os
from pathlib import Path

class Settings(BaseModel):
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    stockfish_path: str | None = None
    stockfish_depth: int = int(os.getenv("STOCKFISH_DEPTH", "18"))
    stockfish_movetime_ms: int = int(os.getenv("STOCKFISH_MOVETIME_MS", "500"))

_backend_dir = Path(__file__).resolve().parent
_env_stockfish_path = os.getenv("STOCKFISH_PATH")
if _env_stockfish_path:
    _default_stockfish_path = _env_stockfish_path
else:
    candidate = _backend_dir / "stockfish.exe"
    _default_stockfish_path = str(candidate) if candidate.exists() else None

settings = Settings(stockfish_path=_default_stockfish_path)
