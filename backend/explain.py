import chess
from features import extract_features_before_after
from settings import settings
from engine import analyze_with_stockfish_before_after, is_configured

TEMPLATES = {
    "great_tactic": [
        "Great tactic! That move creates immediate pressure and improves your material situation."
    ],
    "solid_improvement": [
        "Prudent choice — this improves your position and reduces risk."
    ],
    "warning_hanging": [
        "Careful — that square is dangerous; your piece may be in danger."
    ],
    "blunderish": [
        "This looks like a serious mistake — the tactic against you is strong."
    ],
    "neutral": [
        "Reasonable — keeps the balance without forcing matters."
    ],
    "mate_for": [
        "Checkmate! Beautiful finish — the game is over."
    ],
    "mate_against": [
        "Careful — this line allows a forced mate against you."
    ],
    "stalemate": [
        "Stalemate — the game ends in a draw."
    ]
}

def pick_line(key: str) -> str:
    """Pick a template line for the given key."""
    arr = TEMPLATES.get(key, TEMPLATES["neutral"])
    return arr[0]

def explain_move(fen: str, move_str: str) -> dict:
    """Given a FEN and a move (in SAN or UCI), return an explanation dict with:
    - normalized_move: move in standard SAN notation
    - reaction: text reaction to the move
    - details: dict of extracted features and (if configured) engine evals before/after
    """

    board = chess.Board(fen)

    # Normalize move to SAN
    try:
        try:
            move = board.parse_san(move_str)
            normalized_move = board.san(move)
        except ValueError:
            move = board.parse_uci(move_str)
            normalized_move = board.san(move)
    except ValueError as e:
        raise ValueError(f"Invalid move: {move_str}") from e

    feats = extract_features_before_after(fen, move)

    # Track who is moving and material delta from their perspective
    mover = feats["turn"] 
    material_delta_from_mover = feats["material_delta"] if mover == "White" else -feats["material_delta"]

    # End-of-game messaging has priority
    if feats.get("is_checkmate_after"):
        key = "mate_for"
        reasons = ["The move delivers checkmate."]
    elif feats.get("is_stalemate_after"):
        key = "stalemate"
        reasons = ["The side to move has no legal moves and is not in check."]
    elif feats.get("is_insufficient_material_after"):
        key = "stalemate"
        reasons = ["Insufficient mating material leads to a draw."]
    else:
        # Rule-based classification
        key = "neutral"
        reasons = []
        if feats["is_capture"] or feats["is_check_move"]:
            if material_delta_from_mover > 0:
                key = "great_tactic"
            elif material_delta_from_mover < 0:
                key = "blunderish"
            else:
                key = "solid_improvement"
        else:
            if feats["king_exposed"]:
                key = "warning_hanging"
            elif material_delta_from_mover > 0:
                key = "solid_improvement"
            else:
                key = "neutral"

        if feats["is_capture"]:
            reasons.append("It trades material in your favor." if material_delta_from_mover > 0 else "The capture may not be justified tactically.")
        if feats["is_check_move"]:
            reasons.append("Forcing check increases pressure on the opponent’s king.")
        if feats["king_exposed"]:
            reasons.append("It may loosen king safety.")

    reaction = f"{pick_line(key)}"
    if reasons:
        reaction += " " + " ".join(reasons)

    # Create after-FEN and attach engine evals (diff) if configured
    board_after = chess.Board(fen)
    board_after.push(move)
    fen_after = board_after.fen()

    details = feats
    if is_configured():
        engine = analyze_with_stockfish_before_after(fen, fen_after, depth=None)
        details["engine"] = engine
        # Optional: fold eval swing into the text if both cp scores are present
        try:
            b = engine["before"]
            a = engine["after"]
            if b.get("ok") and a.get("ok") and b.get("score_centipawn") is not None and a.get("score_centipawn") is not None:
                swing = a["score_centipawn"] - b["score_centipawn"]
                sign = "+" if swing >= 0 else ""
                reaction += f" (Eval: {b['score_centipawn']/100:.2f} → {a['score_centipawn']/100:.2f}, Δ {sign}{swing/100:.2f})."
        except Exception:
            pass
    else:
        details["engine"] = {"enabled": False, "note": "Set STOCKFISH_PATH to enable engine evals."}

    return {
        "normalized_move": normalized_move,
        "reaction": reaction,
        "details": details,
    }
