import subprocess, re, shutil
from typing import Optional
from settings import settings

UCI_SCORE_RE = re.compile(r"score (cp|mate) (-?\d+)")

def is_configured() -> bool:
    return bool(settings.stockfish_path) and (shutil.which(settings.stockfish_path) is not None)

def _uci_eval(fen: str, depth: int) -> dict:
    if not is_configured():
        return {"ok": False, "note": "Stockfish not configured."}
    pass

def analyze_with_stockfish_before_after(fen: str, fen_after: str, depth: Optional[int] = None) -> dict:
    pass