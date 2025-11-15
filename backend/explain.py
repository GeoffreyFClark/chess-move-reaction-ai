import chess
import random
from features import extract_features_before_after, king_zone_files, ROOK_HOME_SQUARES, piece_undefended
from engine import analyze_with_stockfish_before_after, is_configured

TEMPLATES = {
    "great_tactic": [
        "Tactical shot."
    ],
    "solid_improvement": [
        "Improving move."
    ],
    "warning_hanging": [
        "Loose piece warning."
    ],
    "blunderish": [
        "Likely mistake."
    ],
    "neutral": [
        "Balanced move."
    ],
    "mate_for": [
        "Checkmate."
    ],
    "mate_against": [
        "Mate threat against you."
    ],
    "stalemate": [
        "Stalemate."
    ],
    "game_continues": [
        "Game continues."
    ]
}

ENGINE_TONE_BANK = {
    "excellent": [ # <0.2 delta
        "Excellent move.",
        "This is a very precise move.",
        "This is one of the top moves."
    ],
    "good": [ # 0.2 to 0.44 delta
        "Good move.",
        "A solid choice.",
        "Not the absolute best option, but still good."
    ],
    "okay": [ # 0.45 to 0.74 delta
        "Okay move. There were stronger alternatives.",
        "This move is not great, but it's playable.",
        "This is serviceable play, though stronger moves existed."
    ],
    "mistake": [ # 0.75 to 1.24 delta
        "Mistake detected.",
        "The engine disapproves.",
        "A noticeable evaluation drop from the engine."
    ],
    "blunder": [ # 1.25+ delta
        "Blunder! This move can be punished severely.",
        "This move is a blunder and leads to a disadvantage.",
        "A significant blunder according to the engine."
    ]
}

ENGINE_TONE_THRESHOLDS = [
    (0.19, "excellent"),
    (0.44, "good"),
    (0.74, "okay"),
    (1.24, "mistake"),
]

def pick_line(key: str) -> str:
    arr = TEMPLATES.get(key, TEMPLATES["neutral"])
    return random.choice(arr)

def pick_engine_line(tone: str) -> str:
    if tone and tone in ENGINE_TONE_BANK:
        return random.choice(ENGINE_TONE_BANK[tone])
    return ""

def describe_piece(piece: chess.Piece) -> str:
    names = {
        chess.PAWN: "Pawn",
        chess.KNIGHT: "Knight",
        chess.BISHOP: "Bishop",
        chess.ROOK: "Rook",
        chess.QUEEN: "Queen",
        chess.KING: "King",
    }
    return names.get(piece.piece_type, "Piece")

def add_reason(reasons: list[str], text: str):
    if text and text not in reasons:
        reasons.append(text)

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

    moving_piece = board.piece_at(move.from_square)
    feats = extract_features_before_after(fen, move)

    mover = feats["turn"]
    mover_key = "white" if mover == "White" else "black"
    opponent_key = "black" if mover_key == "white" else "white"
    material_delta_from_mover = feats["material_delta"] if mover == "White" else -feats["material_delta"]
    material_balance_before = feats["material_before"] if mover == "White" else -feats["material_before"]
    material_balance_after = feats["material_after"] if mover == "White" else -feats["material_after"]

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

    if is_configured():
        engine_result = analyze_with_stockfish_before_after(fen, fen_after, depth=None)
    else:
        engine_result = {"enabled": False, "note": "Set STOCKFISH_PATH to enable engine evals."}
    engine_summary = summarize_engine(engine_result, mover)

    engine_eval_ready = engine_summary.get("before_cp") is not None and engine_summary.get("after_cp") is not None
    if engine_eval_ready:
        eval_before = engine_summary["before_cp"] / 100.0
        eval_after = engine_summary["after_cp"] / 100.0
    else:
        eval_before = material_balance_before
        eval_after = material_balance_after
    eval_delta = eval_after - eval_before
    eval_drop = abs(eval_delta) >= 0.25

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
        key = "game_continues"
        reasons: list[str] = []
        if feats["is_capture"]:
                key = "great_tactic"
            elif material_balance_after > material_balance_before:
                key = "solid_improvement"
            else:
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
            add_reason(reasons, "Your pieces gain mobility options.")
        elif mob_delta_mover <= -5:
            add_reason(reasons, "This choice limits your own piece activity.")
        if mob_delta_opp <= -3:
            add_reason(reasons, "The opponent's options are more limited after this move.")

        center_before = feats["center_control_before"]
        center_after = feats["center_control_after"]
        center_delta_mover = center_after[mover_key] - center_before[mover_key]
        center_delta_opp = center_after[opponent_key] - center_before[opponent_key]
        both_center_drop = center_delta_mover <= -1 and center_delta_opp <= -1
        if center_delta_mover >= 2:
            add_reason(reasons, "You increase control of the central squares.")
        elif both_center_drop:
            add_reason(reasons, "Central control is balanced.")
        elif center_delta_mover <= -2:
            add_reason(reasons, "Central influence decreases a bit here.")
        if not both_center_drop and center_delta_opp <= -1:
            add_reason(reasons, "Your opponent's center control declines.")

        pins_before = feats["pins_before"]
        pins_after = feats["pins_after"]
        if pins_after[opponent_key] > pins_before[opponent_key]:
            add_reason(reasons, "Note that you have increased pins against your opponent.")
        if pins_after[mover_key] > pins_before[mover_key]:
            add_reason(reasons, "Note that pins against you have increased.")

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
