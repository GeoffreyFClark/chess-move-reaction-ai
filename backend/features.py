import chess

def parse_move(board: chess.Board, move_str: str) -> chess.Move:
    # Try Standard Algebraic Notation(SAN) first, then Universal Chess Interface(UCI)
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
    # Simple material: P=1, N=3, B=3, R=5, Q=9
    values = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9}
    score = 0
    for piece_type, val in values.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * val
        score -= len(board.pieces(piece_type, chess.BLACK)) * val
    return score

def king_exposed_heuristic(board: chess.Board, side: bool) -> bool:
    # Very rough: count attacks on king’s neighborhood
    king_sq = board.king(side)
    if king_sq is None:
        return False
    neighbors = [sq for sq in chess.SQUARES if chess.square_distance(sq, king_sq) == 1]
    attacks = sum(1 for sq in neighbors if board.is_attacked_by(not side, sq))
    return attacks >= 2

def count_pins(board: chess.Board) -> dict:
    """Count 'squares pinned to king' for each side using python-chess board.is_pinned().
    Returns a dict like {"white": n, "black": n}. 
    """
    counts = {"white": 0, "black": 0}
    for sq, piece in board.piece_map().items():
        if board.is_pinned(piece.color, sq):
            if piece.color == chess.WHITE:
                counts["white"] += 1
            else:
                counts["black"] += 1
    return counts

def get_castling_rights(board: chess.Board) -> dict:
    """Return current castling rights flags for each side (kingside/queenside) as a dict."""
    return {
        "white_can_castle_k": board.has_kingside_castling_rights(chess.WHITE),
        "white_can_castle_q": board.has_queenside_castling_rights(chess.WHITE),
        "black_can_castle_k": board.has_kingside_castling_rights(chess.BLACK),
        "black_can_castle_q": board.has_queenside_castling_rights(chess.BLACK),
    }

def castling_rights_lost(before: dict, after: dict) -> dict:
    """Compute which castling rights were lost. Returns a dict with *_lost boolean flags.
    Given two castling rights dicts BEFORE + AFTER (each generated from get_castling_rights()).
    Returns a dict with {key}_lost boolean flags."""
    lost = {}
    for k, v in before.items():
        lost[f"{k}_lost"] = bool(v and not after.get(k))
    return lost

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

    return features


# For parse_moves, are we leaving the exceptions as the general type "ValueError" ? Or would it be better to specify specific errors like InvalidMoveError, IllegalMoveError, and AmbiguousMoveError ?
# I plan on implementing mobility feature which evaluates how many legal moves each side has.
# Center control.
# Extend the king safety heuristic by including whether the king's escape squares shrink.
# Roughly check for doubled, isolated, and passed pawns.

# ------------ Comments from review ------------ #

# Thanks, your plans regarding feature extraction sound good to add! Other quick ideas: 
# - measure pinned piece count - board.is_pinned() 
# - Castling-rights lost flags - board.has_castling_rights() 
# - King-ring pressure (attackers on the 8 surrounding squares i.e. defending pawns) - board.attackers()
# - Check flags (is the side to move in check or giving check after a move)
# - Identifying when pieces are placed on undefended squares
# - Piece development i.e. 4v2 developed out of the opening)
# - legal_moves / generate_legal_moves() could be useful in many ways... including iteration through future board states for deeper feature extraction.

# InvalidMoveError, IllegalMoveError, AmbiguousMoveError in python-chess all subclass ValueError, so one except ValueError already catches them. I kept it simple, but if we ever want to distinguish the types, we can just add type(e).__name__ to the message. Honestly, more useful might be richer debug/error messages and additional tests to support both extraction logic and the reaction/explanation logic.

# Aside from expanding feature extraction, our main focus should be on utilizing those features in patterns/heuristics/algorithms from our course so the “AI reactions” feel more meaningful. Let's talk more on Discord with the rest of the team to delegate tasks more clearly.

def get_mobility_scores(board: chess.Board) -> tuple[int, int]:
    white_score, black_score = 0, 0
    for move in board.legal_moves:
        color = board.color_at(move.from_square)
        if color is chess.WHITE:
            white_score += 1
        elif color is chess.BLACK:
            black_score += 1
    return white_score, black_score

def get_center_control_scores(board: chess.Board) -> tuple[int, int]:
    center_squares = {'d4', 'e4', 'd5', 'e5'}
    white_score, black_score = 0, 0
    for move in board.legal_moves:
        color = board.color_at(move.from_square)
        if chess.square_name(move.to_square) in center_squares:
            if color == chess.WHITE:
                white_score += 1
            elif color is chess.BLACK:
                black_score += 1
    return white_score, black_score
