import chess

def parse_move(board: chess.Board, move_str: str) -> chess.Move:
    """ Handle both Standard Algebraic Notation(SAN) first, then Universal Chess Interface(UCI).
    SAN for human convenience (CLI and tests), UCI for compatibility with engines and APIs.
    """
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
    """Compute material score from White's perspective. Positive = White ahead, Negative = Black ahead."""
    values = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9}
    score = 0
    for piece_type, val in values.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * val
        score -= len(board.pieces(piece_type, chess.BLACK)) * val
    return score

def king_exposed_heuristic(board: chess.Board, side: bool) -> bool:
    """Very rough: count squares attacked around the king. If 4 or more attacks, consider king exposed."""
    king_sq = board.king(side)
    if king_sq is None:
        return False
    
    neighbors = [sq for sq in chess.SQUARES if chess.square_distance(sq, king_sq) == 1]
    attacks = sum(1 for sq in neighbors if board.is_attacked_by(not side, sq)) # Attack count for current neighboring squares
    unattacked = (sq for sq in neighbors if not board.is_attacked_by(not side, sq))

    # Extend the king safety heuristic by including whether the king's escape squares shrink.
    # Idea: For every unattacked neighboring square, calculate attack score, if the attack score is greater it means moving to that square is more dangerous. Store this info in a dictionary.

    attack_dict = {}

    for neighbor_sq in unattacked:
        sq_to_check = neighbor_sq
        board_copy = board.copy(stack=False)
        board_copy.remove_piece_at(king_sq)
        board_copy.set_piece_at(sq_to_check, chess.Piece(chess.KING, side))

        neighbors = [sq for sq in chess.SQUARES if chess.square_distance(sq, sq_to_check) == 1]
        neighbor_attacks = sum(1 for sq in neighbors if board_copy.is_attacked_by(not side, sq)) # Attack count for unattacked neighbor's neighboring squares
        if neighbor_attacks > attacks:
            attack_dict[sq_to_check] = neighbor_attacks - attacks

    return attack_dict

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

def ud_material(board):
    """Return the underdefended pieces for each side using python-chess board.attackers().
    Returns a dict like {"white": [(sq, piece), ...], "black": [(sq, piece), ...]}.
    """
    # BUG: Assumes order of exchange is from least to most valuable pieces, which ignores cases where
    # certain pieces MUST be exchanged before others (eg. rook behind a queen).
    # BUG: board.attackers can't detect attackers that are behind other attackers
    # (eg. bishop behind pawn taking diagonally)
    # BUG: Ignores pinned pieces which cannot be moved, as well as partial pins.
    # BUG: Ignoring overwhelming complexity from considering board after each exchange possibility.
    underdefended_pieces = {"white": [], "black": []}
    values = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9, chess.KING:999}
    for sq, piece in board.piece_map().items():
        # Do not consider kings as underdefended (since it doesn't make sense to exchange the king).
        if not piece.piece_type == chess.KING:
            attackers = board.attackers(not piece.color, sq)
            defenders = board.attackers(piece.color, sq)

            if attackers: # TODO: Consider differentiating loose, hanging, and loosely defended pieces.
                if piece.color == chess.WHITE:
                    color = "white"
                else:
                    color = "black"
                a_material = []
                d_material = []

                # Prepare information to simulate exchange possibilities.
                for a_sq in attackers:
                    a_piece = board.piece_at(a_sq).piece_type
                    a_material.append(values[a_piece])

                for d_sq in defenders:
                    d_piece = board.piece_at(d_sq).piece_type
                    d_material.append(values[d_piece])

                # Assuming players will exchange from least to most valuable pieces.
                a_material.sort()
                d_material.sort()
                d_material = [values[piece.piece_type]] + d_material # Prepend current piece since it will be taken first.

                # Simulate an exchange to determine if an unfavorable exchange could be forced.
                score = 0
                attackers_turn = True
                full_exchange = True
                while not ((attackers_turn and not a_material) or (not attackers_turn and not d_material)):
                    # Keep exchanging until a side runs out of pieces
                    if attackers_turn:
                        score -= d_material.pop(0)
                        attackers_turn = False
                        if score >= 0: # Defender can stop exchanging while not down in material, which is fine.
                            full_exchange = False
                            break
                    else:
                        score += a_material.pop(0)
                        attackers_turn = True
                        if score < 0: # Attacker can stop exchanging while up in material, which is bad.
                            underdefended_pieces[color].append((chess.square_name(sq), piece))
                            full_exchange = False
                            break

                if full_exchange:
                    if score < 0: # Defender is down material after a full exchange, which is bad.
                        underdefended_pieces[color].append((chess.square_name(sq), piece))

    return underdefended_pieces


def extract_features_before_after(fen: str, move: chess.Move) -> dict:
    """Extract features from a FEN position before and after a given move.

    Returns a dict of features including:
    - turn: "White" or "Black"
    - in_check: bool before move
    - legal: bool if move is legal

        Before-move info:
    - material_before: int material score before move
    - is_capture: bool if move captures
    - is_check_move: bool if move gives check
    - is_promotion: bool if move promotes
    - pins_before: dict {"white": n, "black": n} Number of 'squares pinned to king' before move
    - castling_rights_before: dict of castling rights before move
    - ud_material_before: dict {"white": [(sq, piece), ...], "black": [(sq, piece), ...]} Underdefended pieces before move
    - mobility_before: dict move counts per side before move
    - center_control_before: dict counts of moves hitting {d4,e4,d5,e5}
    
        After-move info:
    - in_check_after: bool after move
    - gives_check_after: bool if move gives check
    - material_after: int material score after move
    - material_delta: int material_after - material_before
    - pins_after: dict {"white": n, "black": n} Number of 'squares pinned to king' after move
    - castling_rights_after: dict of castling rights after move
    - castling_rights_lost: dict of which castling rights were lost due to the move
    - king_exposed: bool if king is exposed after move - could use refinement, ie before+after
    - ud_material_after: dict {"white": [(sq, piece), ...], "black": [(sq, piece), ...]} Underdefended pieces after move
    - mobility_after: dict move counts per side after move
    - center_control_after: dict counts of moves hitting {d4,e4,d5,e5}
    
        Game termination flags:
    - is_checkmate_after: bool if move results in checkmate
    - is_stalemate_after: bool if move results in stalemate
    - is_insufficient_material_after: bool if move results in insufficient material draw
    """

    board = chess.Board(fen)
    features = {
        "turn": "White" if board.turn == chess.WHITE else "Black",
        "in_check": board.is_check(),
        "legal": move in board.legal_moves,
    }

    # Before-move info
    features["material_before"] = material_score(board)
    features["is_capture"] = board.is_capture(move)
    features["is_check_move"] = board.gives_check(move)
    features["is_promotion"] = (move.promotion is not None)
    features["pins_before"] = count_pins(board)
    features["castling_rights_before"] = get_castling_rights(board)
    features["ud_material_before"] = ud_material(board)
    features["mobility_before"] = dict(zip(["white", "black"], get_mobility_scores(board)))
    features["center_control_before"] = dict(zip(["white", "black"], get_center_control_scores(board)))

    # Execute the move
    board.push(move)

    # After-move info
    features["in_check_after"] = board.is_check()
    features["gives_check_after"] = board.is_check()
    features["material_after"] = material_score(board)
    features["material_delta"] = features["material_after"] - features["material_before"]
    features["pins_after"] = count_pins(board)
    features["castling_rights_after"] = get_castling_rights(board)
    features["castling_rights_lost"] = castling_rights_lost(features["castling_rights_before"], features["castling_rights_after"])
    features["king_exposed"] = king_exposed_heuristic(board, side=(board.turn ^ 1))
    features["ud_material_after"] = ud_material(board)
    features["mobility_after"] = dict(zip(["white", "black"], get_mobility_scores(board)))
    features["center_control_after"] = dict(zip(["white", "black"], get_center_control_scores(board)))

    # Game termination flags
    features["is_checkmate_after"] = board.is_checkmate()
    features["is_stalemate_after"] = board.is_stalemate()
    features["is_insufficient_material_after"] = board.is_insufficient_material()

    return features

# Roughly check for doubled, isolated, and passed pawns.

# ------------ Comments from review ------------ #

# Thanks, your plans regarding feature extraction sound good to add! Other quick ideas: 
# - King-ring pressure (attackers on the 8 surrounding squares i.e. defending pawns) - board.attackers()
# - Check flags (is the side to move in check or giving check after a move)
# - Identifying when pieces are placed on undefended squares
# - Piece development i.e. 4v2 developed out of the opening)
# - legal_moves / generate_legal_moves() could be useful in many ways... including iteration through future board states for deeper feature extraction.

# InvalidMoveError, IllegalMoveError, AmbiguousMoveError in python-chess all subclass ValueError, so one except ValueError already catches them. I kept it simple, but if we ever want to distinguish the types, we can just add type(e).__name__ to the message. Honestly, more useful might be richer debug/error messages and additional tests to support both extraction logic and the reaction/explanation logic.

# Aside from expanding feature extraction, our main focus should be on utilizing those features in patterns/heuristics/algorithms from our course so the “AI reactions” feel more meaningful. Let's talk more on Discord with the rest of the team to delegate tasks more clearly.

def get_mobility_scores(board: chess.Board) -> tuple[int, int]:
    """Evaluates each side's mobility based on the number of available moves per side."""
    white_score, black_score = 0, 0
    for move in board.legal_moves:
        color = board.color_at(move.from_square)
        if color is chess.WHITE:
            white_score += 1
        elif color is chess.BLACK:
            black_score += 1
    return white_score, black_score

def get_center_control_scores(board: chess.Board) -> tuple[int, int]:
    """Evaluates each side's center control based on the number of moves that are attacking the center squares: d4, e4, d5, e5."""
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
