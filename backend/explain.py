import chess
import random
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

ENGINE_TONE_BANK = {
    "excellent": [ # <0.15 delta
        "Excellent move.",
        "This is a very precise move.",
        "This is one of the top moves."
    ],
    "good": [ # 0.15 to 0.35 delta
        "Good move.",
        "A solid choice.",
        "Not the best move, but still good according to the engine."
    ],
    "okay": [ # 0.36 to 0.55 delta
        "Okay move.",
        "This move is not great, but it's playable.",
        "This is serviceable play, though stronger moves existed."
    ],
    "mistake": [ # 0.56 to 0.99 delta
        "Mistake detected.",
        "The engine disapproves.",
        "A noticeable evaluation drop from the engine."
    ],
    "blunder": [ # 1.0+ delta
        "Blunder!",
        "This move is a blunder.",
        "A significant blunder according to the engine."
    ]
}

ENGINE_TONE_THRESHOLDS = [
    (0.15, "excellent"),
    (0.35, "good"),
    (0.55, "okay"),
    (0.99, "mistake"),
]

def pick_line(key: str) -> str:
    arr = TEMPLATES.get(key, TEMPLATES["neutral"])
    return random.choice(arr)

def pick_engine_line(tone: str) -> str:
    if tone and tone in ENGINE_TONE_BANK:
        return random.choice(ENGINE_TONE_BANK[tone])
    return ""

def summarize_engine(engine: dict | None, mover: str) -> dict:
    summary = {
        "available": False,
        "tone": None,
        "delta_cp": None,
        "before_cp": None,
        "after_cp": None,
    }
    if not engine or not engine.get("enabled"):
        return summary
    before = engine.get("before", {})
    after = engine.get("after", {})
    if not before.get("ok") or not after.get("ok"):
        return summary

    def orient(value: int | None) -> int | None:
        if value is None:
            return None
        return value if is_white_mover else -value

    def tone_from_delta(delta_pawns: float) -> str:
        delta_abs = abs(delta_pawns)
        for limit, tone in ENGINE_TONE_THRESHOLDS:
            if delta_abs <= limit:
                return tone
        return "blunder"

    return arr[0]

def add_reason(reasons: list[str], text: str):
    if text and text not in reasons:
        reasons.append(text)

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
    
    # Track underdefended material from both sides.
    # TODO: More linguistic variation (you defended this/your opponent's piece is hanging/etc.)
    if mover == "White":
        ud_material_from_mover_before = feats["ud_material_before"]["white"]
        ud_material_from_mover = feats["ud_material_after"]["white"]
        ud_material_from_nonmover = feats["ud_material_after"]["black"]
    else:
        ud_material_from_mover_before = feats["ud_material_before"]["black"]
        ud_material_from_mover = feats["ud_material_after"]["black"]
        ud_material_from_nonmover = feats["ud_material_after"]["white"]

    # Identifies changes in underdefended material (mover only, for now).
    ud_material_from_mover_no_longer = []
    for piece in ud_material_from_mover_before:
            if piece[0] == chess.square_name(move.from_square): # Special case: Convert moved piece to same form as "after" board.
                piece = (chess.square_name(move.to_square), piece[1])
            if piece not in ud_material_from_mover:
                ud_material_from_mover_no_longer.append(piece)

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

        for piece in ud_material_from_mover_no_longer:
            reasons.append(f"Your {piece[1]} at {piece[0]} is no longer underdefended!")
        for piece in ud_material_from_mover:
            reasons.append(f"You have an underdefended {piece[1]} at {piece[0]}!")
        for piece in ud_material_from_nonmover:
            reasons.append(f"Your opponent has an underdefended {piece[1]} at {piece[0]}!")

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
        engine_summary = summarize_engine(engine, mover)
        details["engine_summary"] = engine_summary
    else:
        engine_summary = {"available": False, "tone": None}
        details["engine"] = {"enabled": False, "note": "Set STOCKFISH_PATH to enable engine evals."}
        details["engine_summary"] = engine_summary

    return {
        "normalized_move": normalized_move,
        "reaction": reaction,
        "details": details,
    }
