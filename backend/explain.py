import chess
from features import extract_features_before_after
from settings import settings

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
    arr = TEMPLATES.get(key, TEMPLATES["neutral"])
    return arr[0]

def explain_move(fen: str, move_str: str) -> dict:
    board = chess.Board(fen)
    # Normalize move
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
    elif feats.get("is_seventyfive_moves_after") or feats.get("is_fivefold_repetition_after"):
        key = "stalemate"
        reasons = ["Draw by rule (75-move or fivefold repetition)."]
    else:
        # Rule-based classification
        key = "neutral"
        reasons = []
        if feats["is_capture"] or feats["is_check_move"]:
            if feats["material_delta"] > 0:
                key = "great_tactic"
            elif feats["material_delta"] < 0 or feats["moved_piece_hanging"]:
                key = "blunderish"
            else:
                key = "solid_improvement"
        else:
            if feats["moved_piece_hanging"] or feats["king_exposed"]:
                key = "warning_hanging"
            elif feats["material_delta"] > 0:
                key = "solid_improvement"
            else:
                key = "neutral"

        if feats["is_capture"]:
            reasons.append("It trades material in your favor." if feats["material_delta"] > 0 else "The capture may not be justified tactically.")
        if feats["is_check_move"]:
            reasons.append("Forcing check increases pressure on the opponent’s king.")
        if feats["moved_piece_hanging"]:
            reasons.append("The destination square fails static exchange evaluation (likely loses material).")
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

    return {
        "normalized_move": normalized_move,
        "reaction": reaction,
        "details": details,
    }