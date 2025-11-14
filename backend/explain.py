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

    cp_before = before.get("score_centipawn")
    cp_after = after.get("score_centipawn")
    mate_before = before.get("mate_in")
    mate_after = after.get("mate_in")
    summary["available"] = True
    is_white_mover = mover.lower().startswith("white")

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

    if cp_before is not None and cp_after is not None:
        oriented_before = orient(cp_before)
        oriented_after = orient(cp_after)
        delta_cp = oriented_after - oriented_before
        summary["before_cp"] = oriented_before
        summary["after_cp"] = oriented_after
        summary["delta_cp"] = delta_cp
        summary["tone"] = tone_from_delta(delta_cp / 100.0)
        return summary

    if mate_before is not None or mate_after is not None:
        oriented_before = orient(mate_before) if mate_before is not None else 0
        oriented_after = orient(mate_after) if mate_after is not None else 0
        delta = oriented_after - oriented_before
        abs_delta = abs(delta)
        summary["tone"] = "excellent" if abs_delta <= 0.15 else ("mistake" if abs_delta <= 0.99 else "blunder")
        summary["delta_cp"] = None
    return summary

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

    mover = feats["turn"]
    mover_key = "white" if mover == "White" else "black"
    opponent_key = "black" if mover_key == "white" else "white"
    material_delta_from_mover = feats["material_delta"] if mover == "White" else -feats["material_delta"]

    ud_material_from_mover_before = feats["ud_material_before"][mover_key]
    ud_material_from_mover = feats["ud_material_after"][mover_key]
    ud_material_from_nonmover = feats["ud_material_after"][opponent_key]
    ud_material_from_mover_no_longer: list[tuple[str, chess.Piece]] = []
    for sq, piece in ud_material_from_mover_before:
        target_sq = sq
        if sq == chess.square_name(move.from_square):
            target_sq = chess.square_name(move.to_square)
        if (target_sq, piece) not in ud_material_from_mover:
            ud_material_from_mover_no_longer.append((target_sq, piece))

    board_after = chess.Board(fen)
    board_after.push(move)
    fen_after = board_after.fen()

    capture_destination = chess.square_name(move.to_square)
    opponent_moves_after = list(board_after.legal_moves)
    immediate_recapture_possible = feats["is_capture"] and any(
        m.to_square == move.to_square and board_after.is_capture(m)
        for m in opponent_moves_after
    )
    capturing_piece_loose = feats["is_capture"] and any(
        sq == capture_destination for sq, _ in ud_material_from_mover
    )

    if feats.get("is_checkmate_after"):
        key = "mate_for"
        reasons = ["The move delivers checkmate."]
    elif feats.get("is_stalemate_after"):
        key = "stalemate"
        reasons = ["The side to move has no legal moves and is not in check."]
    elif feats.get("is_insufficient_material_after"):
        key = "stalemate"
        reasons = ["Both sides lack mating material, so the game is drawn."]
    else:
        key = "neutral"
        reasons: list[str] = []
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
            if material_delta_from_mover > 0:
                reasons.append("It trades material in your favor.")
            elif material_delta_from_mover < 0:
                reasons.append("The capture may not be justified tactically.")
            else:
                reasons.append("It simplifies material without changing the balance.")
            if immediate_recapture_possible:
                reasons.append("The captured square can be contested immediately, so stay alert.")
            if capturing_piece_loose:
                reasons.append("The capturing piece is loose and could be chased away.")
        if feats["is_check_move"]:
            reasons.append("Forcing check increases pressure on the opponent's king.")
        if feats["is_promotion"]:
            reasons.append("Promotion escalates your attack with fresh material.")
        if material_delta_from_mover >= 2:
            reasons.append("You win a large chunk of material with this sequence.")
        elif material_delta_from_mover <= -2:
            reasons.append("Material losses here are severe; compensation must be immediate.")
        elif material_delta_from_mover == 1:
            if immediate_recapture_possible or capturing_piece_loose:
                reasons.append("The extra pawn is tenuous and may be lost again soon.")
            else:
                reasons.append("You come out a pawn ahead.")
        elif material_delta_from_mover == -1:
            reasons.append("You give up a pawn for activity.")
        if feats["king_exposed"]:
            reasons.append("It may loosen king safety.")

        for piece in ud_material_from_mover_no_longer:
            reasons.append(f"Your {piece[1]} at {piece[0]} is no longer underdefended!")
        for piece in ud_material_from_mover:
            reasons.append(f"You have an underdefended {piece[1]} at {piece[0]}!")
        for piece in ud_material_from_nonmover:
            reasons.append(f"Your opponent has an underdefended {piece[1]} at {piece[0]}!")

        castling_lost = feats["castling_rights_lost"]
        if castling_lost.get(f"{mover_key}_can_castle_k_lost"):
            reasons.append("You can no longer castle kingside.")
        if castling_lost.get(f"{mover_key}_can_castle_q_lost"):
            reasons.append("Queenside castling is now off the table for you.")
        if castling_lost.get(f"{opponent_key}_can_castle_k_lost"):
            reasons.append("You stripped your opponent's kingside castling rights.")
        if castling_lost.get(f"{opponent_key}_can_castle_q_lost"):
            reasons.append("The opponent can no longer castle queenside.")

        mobility_before = feats["mobility_before"]
        mobility_after = feats["mobility_after"]
        mob_delta_mover = mobility_after[mover_key] - mobility_before[mover_key]
        mob_delta_opp = mobility_after[opponent_key] - mobility_before[opponent_key]
        if mob_delta_mover >= 3:
            reasons.append("Your pieces gain significant mobility.")
        elif mob_delta_mover <= -3:
            reasons.append("This choice limits your own piece activity.")
        if mob_delta_opp <= -3:
            reasons.append("The opponent's options shrink after this move.")

        center_before = feats["center_control_before"]
        center_after = feats["center_control_after"]
        center_delta_mover = center_after[mover_key] - center_before[mover_key]
        center_delta_opp = center_after[opponent_key] - center_before[opponent_key]
        both_center_drop = center_delta_mover <= -1 and center_delta_opp <= -1
        if center_delta_mover >= 1:
            reasons.append("You tighten control of the central squares.")
        elif both_center_drop:
            reasons.append("Central control is balanced.")
        elif center_delta_mover <= -1:
            reasons.append("Central influence slips a bit here.")
        if not both_center_drop and center_delta_opp <= -1:
            reasons.append("Your opponent's center control declines.")

        pins_before = feats["pins_before"]
        pins_after = feats["pins_after"]
        if pins_after[opponent_key] > pins_before[opponent_key]:
            reasons.append("You add pressure by pinning another enemy piece.")
        if pins_after[mover_key] > pins_before[mover_key]:
            reasons.append("More of your pieces become pinned, increasing tactical risk.")

        if feats["in_check_after"]:
            reasons.append("You leave your opponent in check.")

    base_headline = pick_line(key)
    reason_text = " ".join(reasons).strip()
    reaction = base_headline if not reason_text else f"{base_headline} {reason_text}"

    details = feats
    if is_configured():
        engine = analyze_with_stockfish_before_after(fen, fen_after, depth=None)
        details["engine"] = engine
        engine_summary = summarize_engine(engine, mover)
    else:
        engine_summary = {"available": False, "tone": None}
        details["engine"] = {"enabled": False, "note": "Set STOCKFISH_PATH to enable engine evals."}
    details["engine_summary"] = engine_summary

    allow_engine_override = key not in {"mate_for", "mate_against", "stalemate"}
    if allow_engine_override and engine_summary.get("tone"):
        engine_headline = pick_engine_line(engine_summary["tone"])
        if not engine_headline:
            engine_headline = base_headline
        reaction = engine_headline if not reason_text else f"{engine_headline} {reason_text}"

    return {
        "normalized_move": normalized_move,
        "reaction": reaction.strip(),
        "details": details,
    }
