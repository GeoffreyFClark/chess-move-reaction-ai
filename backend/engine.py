import subprocess, re, shutil
from typing import Optional
from settings import settings

UCI_SCORE_RE = re.compile(r"score (cp|mate) (-?\d+)")

def is_configured() -> bool:
    return bool(settings.stockfish_path) and (shutil.which(settings.stockfish_path) is not None)

def _uci_eval(fen: str, depth: int) -> dict:
    if not is_configured():
        return {"ok": False, "note": "Stockfish not configured."}

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

    def send(cmd: str):
        assert p.stdin is not None
        p.stdin.write(cmd + "\n")
        p.stdin.flush()

    out_lines = []
    try:
        send("uci")
        send("isready")
        send(f"position fen {fen}")
        send(f"go depth {depth}")
        assert p.stdout is not None
        for line in p.stdout:
            out_lines.append(line.rstrip())
            if line.startswith("bestmove"):
                break
        send("quit")
    except Exception as e:
        try:
            p.kill()
        except Exception:
            pass
        return {"ok": False, "note": f"Error during UCI: {e}"}

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

    return {"ok": True, "score_centipawn": score_centipawn, "mate_in": mate_in, "bestmove": bestmove, "raw_tail": out_lines[-10:]}

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
