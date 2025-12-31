import os
import re
import shutil
import subprocess
import time
from typing import Optional

import chess

from settings import settings

UCI_SCORE_RE = re.compile(r"score (cp|mate) (-?\d+)")

# Timeout for Stockfish operations (seconds)
DEFAULT_TIMEOUT = 30.0


def is_configured() -> bool:
    """Check if Stockfish is properly configured and accessible."""
    if not settings.stockfish_path:
        return False
    # Check if path exists directly or is in system PATH
    return os.path.isfile(settings.stockfish_path) or shutil.which(settings.stockfish_path) is not None


def _uci_eval(fen: str, depth: int, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Evaluate a position using Stockfish via UCI protocol.

    Args:
        fen: The FEN string of the position to evaluate.
        depth: The search depth for the engine.
        timeout: Maximum time to wait for engine response (seconds).

    Returns:
        A dict with evaluation results or error information.
    """
    if not is_configured():
        return {"ok": False, "note": "Stockfish not configured."}

    p: subprocess.Popen | None = None
    try:
        p = subprocess.Popen(
            [settings.stockfish_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except Exception as e:
        return {"ok": False, "note": f"Unable to start Stockfish: {e}"}

    def send(cmd: str) -> None:
        assert p is not None and p.stdin is not None
        p.stdin.write(cmd + "\n")
        p.stdin.flush()

    def cleanup() -> None:
        """Ensure the subprocess is properly terminated."""
        if p is None:
            return
        try:
            if p.stdin:
                p.stdin.write("quit\n")
                p.stdin.flush()
        except Exception:
            pass
        try:
            p.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()

    out_lines: list[str] = []
    board = chess.Board(fen)
    go_parts = ["go"]
    if settings.stockfish_movetime_ms > 0:
        go_parts += ["movetime", str(settings.stockfish_movetime_ms)]
    if depth > 0:
        go_parts += ["depth", str(depth)]

    try:
        send("uci")
        send("isready")
        send(f"position fen {fen}")
        send(" ".join(go_parts))

        assert p.stdout is not None

        # Read with timeout - check elapsed time on each line read
        start_time = time.time()

        for line in p.stdout:
            if time.time() - start_time > timeout:
                cleanup()
                return {"ok": False, "note": f"Stockfish evaluation timed out after {timeout}s"}

            out_lines.append(line.rstrip())
            if line.startswith("bestmove"):
                break

    except Exception as e:
        cleanup()
        return {"ok": False, "note": f"Error during UCI communication: {e}"}
    finally:
        cleanup()

    score_centipawn = None
    mate_in = None
    bestmove = None

    for line in out_lines:
        m = UCI_SCORE_RE.search(line)
        if m:
            kind, val = m.groups()
            if kind == "cp":
                # UCI reports 'cp' for centipawns; store using full name internally
                score_centipawn = int(val)
                mate_in = None
            else:
                mate_in = int(val)
                score_centipawn = None
        if line.startswith("bestmove"):
            parts = line.split()
            if len(parts) >= 2:
                bestmove = parts[1]

    sign = 1 if board.turn == chess.WHITE else -1
    if score_centipawn is not None:
        score_centipawn *= sign
    if mate_in is not None:
        mate_in *= sign

    return {"ok": True, "score_centipawn": score_centipawn, "mate_in": mate_in, "bestmove": bestmove}

def analyze_with_stockfish_before_after(fen: str, fen_after: str, depth: Optional[int] = None) -> dict:
    d = depth or settings.stockfish_depth
    before = _uci_eval(fen, d)
    after  = _uci_eval(fen_after, d)
    return {
        "enabled": True,
        "depth": d,
        "before": before,
        "after": after
    }
