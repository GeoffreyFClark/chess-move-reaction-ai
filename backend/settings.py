import os
import platform
import shutil
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings with environment variable support."""

    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    stockfish_path: str | None = None
    stockfish_depth: int = int(os.getenv("STOCKFISH_DEPTH", "18"))
    stockfish_movetime_ms: int = int(os.getenv("STOCKFISH_MOVETIME_MS", "500"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


_backend_dir = Path(__file__).resolve().parent


def _find_stockfish() -> str | None:
    """Find Stockfish binary for the current platform.

    Search order:
    1. STOCKFISH_PATH environment variable (if set)
    2. Platform-specific binary names in the backend directory
    3. System PATH

    Returns:
        Path to Stockfish executable, or None if not found.
    """
    # Check environment variable first
    env_path = os.getenv("STOCKFISH_PATH")
    if env_path:
        return env_path

    # Determine platform-specific binary names
    system = platform.system().lower()
    if system == "windows":
        candidates = ["stockfish.exe", "stockfish-windows.exe", "stockfish-windows-x86-64.exe"]
    elif system == "darwin":
        candidates = ["stockfish", "stockfish-macos", "stockfish-darwin", "stockfish-macos-x86-64"]
    else:  # Linux and others
        candidates = ["stockfish", "stockfish-linux", "stockfish-ubuntu", "stockfish-linux-x86-64"]

    # Check in backend directory
    for name in candidates:
        path = _backend_dir / name
        if path.exists() and path.is_file():
            return str(path)

    # Check in system PATH
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    return None


settings = Settings(stockfish_path=_find_stockfish())
