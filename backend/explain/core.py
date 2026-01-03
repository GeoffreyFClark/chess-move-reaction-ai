"""Core move explanation logic."""

import chess

from engine import analyze_with_stockfish_before_after, is_configured
from features import (
    ROOK_HOME_SQUARES,
    extract_features_before_after,
    king_zone_files,
    piece_undefended,
    validate_fen,
)

from .engine_summary import summarize_engine
from .reason_builder import ReasonBuilder
from .templates import pick_engine_line, pick_line
from .utils import describe_piece


def explain_move(fen: str, move_str: str) -> dict:
    """Given a FEN and a move (in SAN or UCI), return an explanation dict.

    Args:
        fen: The position in FEN notation.
        move_str: The move in SAN (e.g., "Nf3") or UCI (e.g., "g1f3") notation.

    Returns:
        Dict containing:
        - normalized_move: move in standard SAN notation
        - reaction: text reaction to the move
        - details: dict of extracted features and (if configured) engine evals

    Raises:
        ValueError: If the FEN is invalid or the move is illegal.
    """
    # Validate FEN before processing
    is_valid, error = validate_fen(fen)
    if not is_valid:
        raise ValueError(error)

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

    # Setup mover context
    mover = feats["turn"]
    mover_key = "white" if mover == "White" else "black"
    opponent_key = "black" if mover_key == "white" else "white"
    mover_color = chess.WHITE if mover == "White" else chess.BLACK

    # Calculate material perspectives
    material_delta_from_mover = (
        feats["material_delta"] if mover == "White" else -feats["material_delta"]
    )
    material_balance_before = (
        feats["material_before"] if mover == "White" else -feats["material_before"]
    )
    material_balance_after = (
        feats["material_after"] if mover == "White" else -feats["material_after"]
    )

    # Underdefended material analysis
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

    # Get board state after move
    board_after = chess.Board(fen)
    board_after.push(move)
    fen_after = board_after.fen()

    # Engine evaluation
    if is_configured():
        engine_result = analyze_with_stockfish_before_after(fen, fen_after, depth=None)
    else:
        engine_result = {"enabled": False, "note": "Set STOCKFISH_PATH to enable engine evals."}
    engine_summary = summarize_engine(engine_result, mover)

    # Determine evaluation basis
    engine_eval_ready = (
        engine_summary.get("before_cp") is not None and engine_summary.get("after_cp") is not None
    )
    if engine_eval_ready:
        eval_before = engine_summary["before_cp"] / 100.0
        eval_after = engine_summary["after_cp"] / 100.0
    else:
        eval_before = material_balance_before
        eval_after = material_balance_after
    eval_delta = eval_after - eval_before
    eval_drop = abs(eval_delta) >= 0.25

    # Capture analysis
    capture_destination = chess.square_name(move.to_square)
    opponent_moves_after = list(board_after.legal_moves)
    immediate_recapture_possible = feats["is_capture"] and any(
        m.to_square == move.to_square and board_after.is_capture(m) for m in opponent_moves_after
    )
    capturing_piece_loose = feats["is_capture"] and any(
        sq == capture_destination for sq, _ in ud_material_from_mover
    )

    # Classify move and build reasons
    key, reasons = _classify_move(
        feats=feats,
        material_balance_before=material_balance_before,
        material_balance_after=material_balance_after,
        material_delta_from_mover=material_delta_from_mover,
        eval_drop=eval_drop,
        engine_eval_ready=engine_eval_ready,
        immediate_recapture_possible=immediate_recapture_possible,
        capturing_piece_loose=capturing_piece_loose,
        board=board,
        board_after=board_after,
        move=move,
        moving_piece=moving_piece,
        mover=mover,
        mover_key=mover_key,
        opponent_key=opponent_key,
        mover_color=mover_color,
        ud_material_from_mover=ud_material_from_mover,
        ud_material_from_nonmover=ud_material_from_nonmover,
        ud_material_from_mover_no_longer=ud_material_from_mover_no_longer,
        capture_destination=capture_destination,
    )

    # Build reaction
    base_headline = pick_line(key)
    reason_text = " ".join(reasons).strip()
    reaction = base_headline if not reason_text else f"{base_headline} {reason_text}"

    # Add engine data to details
    details = feats
    details["engine"] = engine_result
    details["engine_summary"] = engine_summary

    # Add ML prediction if available
    try:
        from ml import predict_move_quality

        ml_prediction = predict_move_quality(board, move)
        details["ml_prediction"] = ml_prediction
    except ImportError:
        details["ml_prediction"] = None
    except Exception:
        details["ml_prediction"] = None

    # Engine override for non-terminal positions
    allow_engine_override = key not in {
        "mate_for",
        "mate_against",
        "stalemate",
        "insufficient_material",
    }
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


def _classify_move(
    *,
    feats: dict,
    material_balance_before: float,
    material_balance_after: float,
    material_delta_from_mover: float,
    eval_drop: bool,
    engine_eval_ready: bool,
    immediate_recapture_possible: bool,
    capturing_piece_loose: bool,
    board: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece | None,
    mover: str,
    mover_key: str,
    opponent_key: str,
    mover_color: chess.Color,
    ud_material_from_mover: list,
    ud_material_from_nonmover: list,
    ud_material_from_mover_no_longer: list,
    capture_destination: str,
) -> tuple[str, list[str]]:
    """Classify a move and generate explanation reasons.

    Returns:
        Tuple of (category_key, list of reason strings).
    """
    # Handle game-ending positions
    if feats.get("is_checkmate_after"):
        return "mate_for", ["The move delivers checkmate."]

    if feats.get("is_stalemate_after"):
        return "stalemate", ["The side to move has no legal moves and is not in check."]

    if feats.get("is_insufficient_material_after"):
        return "insufficient_material", ["Both sides lack mating material, so the game is drawn."]

    # Game continues - analyze move
    reasons = ReasonBuilder()
    key = "game_continues"

    # Classify by move type
    if feats["is_capture"]:
        key = _classify_capture(
            reasons=reasons,
            material_balance_before=material_balance_before,
            material_balance_after=material_balance_after,
            material_delta_from_mover=material_delta_from_mover,
            eval_drop=eval_drop,
            engine_eval_ready=engine_eval_ready,
            immediate_recapture_possible=immediate_recapture_possible,
            capturing_piece_loose=capturing_piece_loose,
        )
    elif feats["is_check_move"]:
        key = "warning_hanging" if eval_drop else "great_tactic"
    else:
        king_safety_concern = bool(feats["king_exposed"]) and len(feats["king_exposed"]) > 0
        if king_safety_concern or eval_drop:
            key = "warning_hanging"
        elif material_delta_from_mover > 0:
            key = "solid_improvement"
        else:
            key = "neutral"

    # Add specific reasons
    _add_move_reasons(
        reasons=reasons,
        feats=feats,
        material_delta_from_mover=material_delta_from_mover,
        board=board,
        board_after=board_after,
        move=move,
        moving_piece=moving_piece,
        mover=mover,
        mover_key=mover_key,
        opponent_key=opponent_key,
        mover_color=mover_color,
        ud_material_from_mover=ud_material_from_mover,
        ud_material_from_nonmover=ud_material_from_nonmover,
        ud_material_from_mover_no_longer=ud_material_from_mover_no_longer,
        capture_destination=capture_destination,
    )

    # Check for key overrides based on specific patterns
    key = _apply_key_overrides(
        key=key,
        reasons=reasons,
        feats=feats,
        mover=mover,
    )

    return key, reasons.build()


def _classify_capture(
    *,
    reasons: ReasonBuilder,
    material_balance_before: float,
    material_balance_after: float,
    material_delta_from_mover: float,
    eval_drop: bool,
    engine_eval_ready: bool,
    immediate_recapture_possible: bool,
    capturing_piece_loose: bool,
) -> str:
    """Classify a capture move and add initial reasons."""
    winning_cleanly = (
        material_balance_after > material_balance_before
        and material_balance_after > 0
        and not immediate_recapture_possible
    )

    if winning_cleanly:
        reasons.add("You win material outright.")
    elif engine_eval_ready and material_delta_from_mover <= 0 and not eval_drop:
        reasons.add("Engine expects the initiative to justify the capture.")

    if immediate_recapture_possible:
        reasons.add("An immediate recapture is possible.")

    if not immediate_recapture_possible and capturing_piece_loose:
        reasons.add("The capturing piece may be chased away.")

    if eval_drop:
        reasons.add("The capture may not be justified.")
        return "blunderish"
    elif winning_cleanly:
        return "great_tactic"
    elif material_balance_after > material_balance_before:
        return "solid_improvement"
    else:
        reasons.add("It simplifies material without changing the balance.")
        return "neutral"


def _add_move_reasons(
    *,
    reasons: ReasonBuilder,
    feats: dict,
    material_delta_from_mover: float,
    board: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece | None,
    mover: str,
    mover_key: str,
    opponent_key: str,
    mover_color: chess.Color,
    ud_material_from_mover: list,
    ud_material_from_nonmover: list,
    ud_material_from_mover_no_longer: list,
    capture_destination: str,
) -> None:
    """Add detailed reasons based on move features."""
    # Check and promotion
    if feats["is_check_move"]:
        reasons.add("You check the opponent's king, forcing a response.")
    if feats["is_promotion"]:
        reasons.add("Promotion increases your material!")

    # Material changes
    if material_delta_from_mover >= 2:
        reasons.add("You win material with this move.")
    elif material_delta_from_mover <= -2:
        reasons.add("Material losses with this move.")
    elif material_delta_from_mover == -1:
        reasons.add("Slight material loss with this move.")

    # King safety
    king_files_nearby = king_zone_files(board.king(mover_color)) | king_zone_files(
        board_after.king(mover_color)
    )
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
            reasons.add("Safe squares for the King to move to have decreased.")
        elif num_dangerous_squares >= 1:
            reasons.add("King escape squares have been reduced.")
        else:
            reasons.add("It may loosen king safety.")

    # Underdefended pieces
    for sq, piece in ud_material_from_mover_no_longer:
        reasons.add(f"Your {describe_piece(piece)} at {sq} is no longer underdefended.")
    for sq, piece in ud_material_from_mover:
        reasons.add(f"You have an underdefended {describe_piece(piece)} at {sq}.")
    for sq, piece in ud_material_from_nonmover:
        reasons.add(f"Your opponent has an underdefended {describe_piece(piece)} at {sq}.")

    # Castling rights
    _add_castling_reasons(
        reasons=reasons,
        feats=feats,
        board=board,
        move=move,
        moving_piece=moving_piece,
        mover_key=mover_key,
        opponent_key=opponent_key,
        mover_color=mover_color,
    )

    # Mobility
    _add_mobility_reasons(reasons, feats, mover_key, opponent_key)

    # Center control
    _add_center_control_reasons(reasons, feats, mover_key, opponent_key)

    # Pins
    _add_pin_reasons(reasons, feats, mover_key, opponent_key)

    # Pawn structure
    _add_pawn_structure_reasons(reasons, feats, mover_key)

    # Undefended moved piece
    moved_piece_undefended, moved_piece_after = piece_undefended(
        board_after, move.to_square, mover_color
    )
    if moved_piece_undefended and moved_piece_after:
        reasons.add(
            f"Your {describe_piece(moved_piece_after)} at {capture_destination} is undefended."
        )


def _add_castling_reasons(
    *,
    reasons: ReasonBuilder,
    feats: dict,
    board: chess.Board,
    move: chess.Move,
    moving_piece: chess.Piece | None,
    mover_key: str,
    opponent_key: str,
    mover_color: chess.Color,
) -> None:
    """Add reasons related to castling rights changes."""
    castling_lost = feats["castling_rights_lost"]
    mover_lost_k = castling_lost.get(f"{mover_key}_can_castle_k_lost")
    mover_lost_q = castling_lost.get(f"{mover_key}_can_castle_q_lost")
    opponent_lost_k = castling_lost.get(f"{opponent_key}_can_castle_k_lost")
    opponent_lost_q = castling_lost.get(f"{opponent_key}_can_castle_q_lost")

    is_castling_move = board.is_castling(move)
    king_moved_no_castle = (
        moving_piece and moving_piece.piece_type == chess.KING and not is_castling_move
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
        reasons.add("You can no longer castle.")
    else:
        if mover_lost_k and not is_castling_move and rook_from_k:
            reasons.add("You can no longer castle kingside.")
        if mover_lost_q and not is_castling_move and rook_from_q:
            reasons.add("Queenside castling is now off the table for you.")

    if opponent_lost_k:
        reasons.add("The opponent can no longer castle kingside.")
    if opponent_lost_q:
        reasons.add("The opponent can no longer castle queenside.")


def _add_mobility_reasons(
    reasons: ReasonBuilder, feats: dict, mover_key: str, opponent_key: str
) -> None:
    """Add reasons related to mobility changes."""
    mobility_before = feats["mobility_before"]
    mobility_after = feats["mobility_after"]
    mob_delta_mover = mobility_after[mover_key] - mobility_before[mover_key]
    mob_delta_opp = mobility_after[opponent_key] - mobility_before[opponent_key]

    if mob_delta_mover >= 3:
        reasons.add("Your pieces gain mobility options.")
    elif mob_delta_mover <= -5:
        reasons.add("This choice limits your own piece activity.")

    if mob_delta_opp <= -3:
        reasons.add("The opponent's options are more limited after this move.")


def _add_center_control_reasons(
    reasons: ReasonBuilder, feats: dict, mover_key: str, opponent_key: str
) -> None:
    """Add reasons related to center control changes."""
    center_before = feats["center_control_before"]
    center_after = feats["center_control_after"]
    center_delta_mover = center_after[mover_key] - center_before[mover_key]
    center_delta_opp = center_after[opponent_key] - center_before[opponent_key]
    both_center_drop = center_delta_mover <= -1 and center_delta_opp <= -1

    if center_delta_mover >= 2:
        reasons.add("You increase control of the central squares.")
    elif both_center_drop:
        reasons.add("Central activity decreases for both sides.")
    elif center_delta_mover <= -2:
        reasons.add("Central influence decreases a bit here.")

    if not both_center_drop and center_delta_opp <= -1:
        reasons.add("Your opponent's center control declines.")


def _add_pin_reasons(
    reasons: ReasonBuilder, feats: dict, mover_key: str, opponent_key: str
) -> None:
    """Add reasons related to pin changes."""
    pins_before = feats["pins_before"]
    pins_after = feats["pins_after"]

    if pins_after[opponent_key] > pins_before[opponent_key]:
        reasons.add("Note that you have increased pins against your opponent.")
    if pins_after[mover_key] > pins_before[mover_key]:
        reasons.add("Note that pins against you have increased.")


def _add_pawn_structure_reasons(reasons: ReasonBuilder, feats: dict, mover_key: str) -> None:
    """Add reasons related to pawn structure changes."""
    pawn_before = feats["pawn_structure_before"]
    pawn_after = feats["pawn_structure_after"]

    new_doubled = set(pawn_after[mover_key]["doubled"]) - set(pawn_before[mover_key]["doubled"])
    new_isolated = set(pawn_after[mover_key]["isolated"]) - set(pawn_before[mover_key]["isolated"])
    new_passed = set(pawn_after[mover_key]["passed"]) - set(pawn_before[mover_key]["passed"])

    if new_doubled:
        reasons.add(f"This creates doubled pawns on the {', '.join(new_doubled)}-file(s).")
    if new_isolated:
        reasons.add(f"Your pawn on the {', '.join(new_isolated)}-file(s) becomes isolated.")
    if new_passed:
        reasons.add(f"You create a passed pawn! ({', '.join(new_passed)})")


def _apply_key_overrides(
    *,
    key: str,
    reasons: ReasonBuilder,
    feats: dict,
    mover: str,
) -> str:
    """Apply key overrides based on specific patterns."""
    # Trading check
    if feats["is_capture"] or (feats["material_delta"] == 0 and feats["is_capture"]):
        raw_score = feats.get("material_raw_before", 0)
        mover_is_white = mover == "White"
        is_winning = (mover_is_white and raw_score >= 3) or (not mover_is_white and raw_score <= -3)
        is_losing = (mover_is_white and raw_score <= -3) or (not mover_is_white and raw_score >= 3)

        if feats["material_delta"] == 0:
            if is_winning:
                key = "solid_improvement"
                reasons.add("Trading simplifies the game when you are ahead.")
            elif is_losing:
                key = "blunderish"
                reasons.add("Trading pieces usually helps the opponent when you are behind.")

    # Opening principles
    opening_notes = feats.get("opening_notes", [])
    if "early_queen" in opening_notes:
        key = "blunderish"
        reasons.add("Bringing the Queen out this early makes her a target.")
    if "moved_twice" in opening_notes:
        key = "blunderish"
        reasons.add("Moving the same piece twice in the opening costs time (tempo).")

    # Hanging to lesser piece
    if feats.get("is_hanging_to_lesser"):
        key = "blunderish"
        reasons.add("You moved a valuable piece to a square attacked by a pawn or minor piece!")

    return key
