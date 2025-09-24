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

def extract_features_before_after(fen: str, move: chess.Move) -> dict:
    pass