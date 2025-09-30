import chess

def parse_move(board: chess.Board, move_str: str) -> chess.Move:
    # Try SAN first, then UCI
    try:
        move = board.parse_san(move_str)
        return move
    except ValueError:
        pass
    try:
        move = board.parse_uci(move_str)
        return move
    except ValueError as e:
        raise ValueError(f"Invalid move: '{move_str}'. Provide SAN (e.g., Nf3) or UCI (e.g., g1f3).") from e

def material_score(board: chess.Board) -> int:
    pass

def king_exposed_heuristic(board: chess.Board, side: bool) -> bool:
    pass

def extract_features_before_after(fen: str, move: chess.Move) -> dict:
    board = chess.Board(fen)
    features = {
        "turn": "White" if board.turn == chess.WHITE else "Black",
        "in_check": board.is_check(),
        "legal": move in board.legal_moves,
    }
    # Material before
    features["material_before"] = material_score(board)

    # Tactics: is capture? is check? is promotion?
    features["is_capture"] = board.is_capture(move)
    features["is_check_move"] = board.gives_check(move)
    features["is_promotion"] = (move.promotion is not None)

    # Execute the move
    board.push(move)

    # After-move info
    features["in_check_after"] = board.is_check()
    features["gives_check_after"] = board.is_check()
    features["material_after"] = material_score(board)
    features["material_delta"] = features["material_after"] - features["material_before"]
    
    # King safety proxy: did king move into danger (very rough)
    features["king_exposed"] = king_exposed_heuristic(board, side=(board.turn ^ 1))

    # Game termination flags
    features["is_checkmate_after"] = board.is_checkmate()
    features["is_stalemate_after"] = board.is_stalemate()
    features["is_insufficient_material_after"] = board.is_insufficient_material()
    features["is_seventyfive_moves_after"] = board.is_seventyfive_moves()
    features["is_fivefold_repetition_after"] = board.is_fivefold_repetition()

    return features
