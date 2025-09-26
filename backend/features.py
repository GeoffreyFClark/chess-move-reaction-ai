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
    return features