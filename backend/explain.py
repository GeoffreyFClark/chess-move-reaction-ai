import chess
import random
from features import extract_features_before_after, king_zone_files, ROOK_HOME_SQUARES, piece_undefended
from engine import analyze_with_stockfish_before_after, is_configured

TEMPLATES = {
    "great_tactic": [
        "Tactical shot.",
        "Nice tactics!",
        "Sharp move!"
    ],
    "solid_improvement": [
        "Improving move.",
        "Good positional play.",
        "This strengthens your position."
    ],
    "warning_hanging": [
        "Loose piece warning.",
        "Careful! Piece in danger.",
        "Watch out - loose pieces drop off."
    ],
    "blunderish": [
        "Likely mistake.",
        "This looks questionable.",
        "Risky decision here."
    ],
    "neutral": [
        "Balanced move.",
        "Reasonable choice.",
        "Steady play."
    ],
    "mate_for": [
        "Checkmate.",
        "Game over - checkmate!",
        "Victory achieved!"
    ],
    "mate_against": [
        "Mate threat against you.",
        "Danger - mate on the horizon.",
        "Critical defensive situation."
    ],
    "stalemate": [
        "Stalemate.",
        "No legal moves - game drawn.",
        "Draw by stalemate."
    ],
    "game_continues": [
        "Game continues.",
        "Play on.",
        "The position remains dynamic."
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

def format_ud_pieces(ud_material, type, moved_piece_undefended = False, void_sq = None):
    """Format underdefended material output to condense the feedback."""
    sqs = []
    pieces = []
    for sq, piece in ud_material:
        if (moved_piece_undefended and not sq == void_sq) or not moved_piece_undefended:
            # Ignore if moved piece is undefended (handled by undefended heuristic).
            sqs.append(sq)
            pieces.append(piece)

    if type == 1: # ud_material_from_mover_no_longer
        if len(pieces) == 1:
            # Your | [piece] at [sq] [IS] | no longer underdefended.
            return f"{describe_piece(pieces[0])} at {sqs[0]} is"
        if len(pieces) == 2:
            # Your | [piece] at [sq] and [piece] at [sq] [ARE] | no longer underdefended.
            return f"{describe_piece(pieces[0])} at {sqs[0]} and {describe_piece(pieces[1])} at {sqs[1]} are"
        if len(pieces) >= 3:
            # Your | [piece] at [sq], [piece] at [sq], and [piece] at [sq] [ARE] | no longer underdefended.
            pieces_text = ""
            for i in range(len(pieces)):
                if i < len(pieces) - 1:
                    pieces_text += f"{describe_piece(pieces[i])} at {sqs[i]}, "
                else:
                    pieces_text += f"and {describe_piece(pieces[i])} at {sqs[i]} are"
            return pieces_text

    if type == 2: # ud_material_from_mover, ud_material_from_nonmover
        if len(pieces) == 1:
            # You have an underdefended | [piece] at [sq] | .
            return f"{describe_piece(pieces[0])} at {sqs[0]}"
        if len(pieces) == 2:
            # You have an underdefended | [piece] at [sq] and [piece] at [sq] | .
            return f"{describe_piece(pieces[0])} at {sqs[0]} and {describe_piece(pieces[1])} at {sqs[1]}"
        if len(pieces) >= 3:
            # You have an underdefended | [piece] at [sq], [piece] at [sq], and [piece] at [sq] | .
            pieces_text = ""
            for i in range(len(pieces)):
                if i < len(pieces) - 1:
                    pieces_text += f"{describe_piece(pieces[i])} at {sqs[i]}, "
                else:
                    pieces_text += f"and {describe_piece(pieces[i])} at {sqs[i]}"
            return pieces_text

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
    # eval_drop = abs(eval_delta) >= 0.25
    eval_drop = eval_delta <= -0.25
    values = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9, chess.KING:999}
    capture_destination = chess.square_name(move.to_square)
    opponent_moves_after = list(board_after.legal_moves)
    immediate_recapture_possible = feats["is_capture"] and any(
        m.to_square == move.to_square and board_after.is_capture(m)
        for m in opponent_moves_after
    )
    cur_piece_val = values[(moving_piece).piece_type]
    good_exchange = (material_balance_after - material_balance_before) > cur_piece_val
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
        win_material_dupe = False

        if feats["is_capture"]:
            winning_cleanly = (
                material_balance_after > material_balance_before
                and material_balance_after > 0
                and not immediate_recapture_possible
            )
            if winning_cleanly:
                add_reason(reasons, "You win material outright.")
                win_material_dupe = True
            elif engine_eval_ready and material_delta_from_mover <= 0 and not eval_drop:
                add_reason(reasons, "Engine expects the initiative to justify the capture.")
            if immediate_recapture_possible:
                if good_exchange and not win_material_dupe:
                    add_reason(reasons, "Expect an immediate recapture, but positive exchange overall.")
                elif good_exchange:
                    add_reason(reasons, "Expect an immediate recapture.")
                else:
                    add_reason(reasons, "Expect an immediate recapture that cancels the gain.")
            if not immediate_recapture_possible and capturing_piece_loose:
                add_reason(reasons, "The capturing piece may be chased away.")

            if eval_drop:
                add_reason(reasons, "The capture may not be justified.")
                key = "blunderish"
            elif winning_cleanly:
                key = "great_tactic"
            elif material_balance_after > material_balance_before:
                key = "solid_improvement"
            else:
                add_reason(reasons, "It simplifies material without changing the balance.")
                key = "neutral"
        elif feats["is_check_move"]:
            if eval_drop:
                key = "warning_hanging"
            else:
                key = "great_tactic"
        else:
            king_safety_concern = bool(feats["king_exposed"]) and len(feats["king_exposed"]) > 0
            if king_safety_concern or eval_drop:
                key = "warning_hanging"
            elif material_delta_from_mover > 0:
                key = "solid_improvement"
            else:
                key = "neutral"

        if feats["is_check_move"]:
            add_reason(reasons, "You check the opponent's king, forcing a response.")
        if feats["is_promotion"]:
            add_reason(reasons, "Promotion increases your material!")
        if material_delta_from_mover >= 2:
            if not win_material_dupe and not immediate_recapture_possible:
                add_reason(reasons, "You took material.") # "win" material changed to "took" material to generalize scenarios that don't win an exchange
        elif material_delta_from_mover <= -2:
            add_reason(reasons, "Material losses.")
        elif material_delta_from_mover == -1:
            add_reason(reasons, "Slight material loss.")

        mover_color = chess.WHITE if mover == "White" else chess.BLACK
        king_files_nearby = king_zone_files(board.king(mover_color)) | king_zone_files(board_after.king(mover_color))

        pawn_near_king = (
            moving_piece
            and moving_piece.piece_type == chess.PAWN
            and king_files_nearby
            and chess.square_file(move.from_square) in king_files_nearby
        )
        king_move = moving_piece and moving_piece.piece_type == chess.KING
        king_safety_concern = bool(feats["king_exposed"]) and len(feats["king_exposed"]) > 0
        if king_safety_concern and (king_move or pawn_near_king):
            num_dangerous_squares = len(feats["king_exposed"])
            if num_dangerous_squares >= 3:
                add_reason(reasons, "This significantly worsens king safety - multiple escape squares become more dangerous.")
            elif num_dangerous_squares >= 1:
                add_reason(reasons, "It may loosen king safety - some escape squares become more perilous.")
            else:
                add_reason(reasons, "It may loosen king safety.")

        if ud_material_from_mover_no_longer:
            moved_piece_undefended, moved_piece_after = piece_undefended(board_after, move.to_square, mover_color)
            piece_text = format_ud_pieces(ud_material_from_mover_no_longer, 1, moved_piece_undefended, capture_destination)
            full_text = f"Your {piece_text} no longer underdefended."
            if piece_text:
                add_reason(reasons, full_text)
        if ud_material_from_mover:
            moved_piece_undefended, moved_piece_after = piece_undefended(board_after, move.to_square, mover_color)
            piece_text = format_ud_pieces(ud_material_from_mover, 2, moved_piece_undefended, capture_destination)
            full_text = f"You have an underdefended {piece_text}."
            if piece_text:
                add_reason(reasons, full_text)
        if ud_material_from_nonmover:
            full_text = f"Your opponent has an underdefended {format_ud_pieces(ud_material_from_nonmover, 2)}."
            add_reason(reasons, full_text)

        castling_lost = feats["castling_rights_lost"]
        mover_lost_k = castling_lost.get(f"{mover_key}_can_castle_k_lost")
        mover_lost_q = castling_lost.get(f"{mover_key}_can_castle_q_lost")
        opponent_lost_k = castling_lost.get(f"{opponent_key}_can_castle_k_lost")
        opponent_lost_q = castling_lost.get(f"{opponent_key}_can_castle_q_lost")

        is_castling_move = board.is_castling(move)
        king_moved_no_castle = (
            moving_piece
            and moving_piece.piece_type == chess.KING
            and not is_castling_move
        )
        rook_from_k = (
            moving_piece
            and moving_piece.piece_type == chess.ROOK
            and move.from_square == ROOK_HOME_SQUARES[mover_color]["k"]
        )
        rook_from_q = (
            moving_piece
            and moving_piece.piece_type == chess.ROOK
            and move.from_square == ROOK_HOME_SQUARES[mover_color]["q"]
        )

        if king_moved_no_castle and (mover_lost_k or mover_lost_q):
            add_reason(reasons, "You can no longer castle.")
        else:
            if mover_lost_k and not is_castling_move and rook_from_k:
                add_reason(reasons, "You can no longer castle kingside.")
            if mover_lost_q and not is_castling_move and rook_from_q:
                add_reason(reasons, "Queenside castling is now off the table for you.")

        if opponent_lost_k:
            add_reason(reasons, "The opponent can no longer castle kinside.")
        if opponent_lost_q:
            add_reason(reasons, "The opponent can no longer castle queenside.")

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
            add_reason(reasons, "Central activity decreases for both sides.")
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

        # Pawn structure analysis
        pawn_before = feats["pawn_structure_before"]
        pawn_after = feats["pawn_structure_after"]
        
        # Check for new pawn weaknesses created
        new_doubled = set(pawn_after[mover_key]["doubled"]) - set(pawn_before[mover_key]["doubled"])
        new_isolated = set(pawn_after[mover_key]["isolated"]) - set(pawn_before[mover_key]["isolated"])
        new_passed = set(pawn_after[mover_key]["passed"]) - set(pawn_before[mover_key]["passed"])
        
        if new_doubled:
            add_reason(reasons, f"This creates doubled pawns on the {', '.join(new_doubled)}-file(s).")
        if new_isolated:
            add_reason(reasons, f"Your pawn on the {', '.join(new_isolated)}-file(s) becomes isolated.")
        if new_passed:
            add_reason(reasons, f"You create a passed pawn! ({', '.join(new_passed)})")

        moved_piece_undefended, moved_piece_after = piece_undefended(board_after, move.to_square, mover_color)
        if moved_piece_undefended and moved_piece_after:
            if not immediate_recapture_possible: # Redundant if intended to be exchanged.
                add_reason(reasons, f"Your {describe_piece(moved_piece_after)} at {capture_destination} is undefended.")

        # Trading check
        if feats["is_capture"] or (feats["material_delta"] == 0 and feats["is_capture"]):
            raw_score = feats.get("material_raw_before", 0)
            
 
            mover_is_white = (mover == "White")
            is_winning = (mover_is_white and raw_score >= 3) or (not mover_is_white and raw_score <= -3)
            is_losing = (mover_is_white and raw_score <= -3) or (not mover_is_white and raw_score >= 3)
            
            # Even trade case
            if feats["material_delta"] == 0:
                if is_winning:
                    key = "solid_improvement"
                    add_reason(reasons, "Trading simplifies the game when you are ahead.")
                elif is_losing:
                    key = "blunderish"
                    add_reason(reasons, "Trading pieces usually helps the opponent when you are behind.")

        # Opening principles
        opening_notes = feats.get("opening_notes", [])
        if "early_queen" in opening_notes:
            key = "blunderish"
            add_reason(reasons, "Bringing the Queen out this early makes her a target.")
        if "moved_twice" in opening_notes:
            key = "blunderish"
            add_reason(reasons, "Moving the same piece twice in the opening costs time (tempo).")

        # Blunders
        if feats.get("is_hanging_to_lesser"):
            key = "blunderish"
          
            add_reason(reasons, "You moved a valuable piece to a square attacked by a pawn or minor piece!")

    base_headline = pick_line(key)
    reason_text = " ".join(reasons).strip()
    reaction = base_headline if not reason_text else f"{base_headline} {reason_text}"

    details = feats
    details["engine"] = engine_result
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
