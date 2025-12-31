import chess

from chess import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING


def validate_fen(fen: str) -> tuple[bool, str | None]:
    """Validate a FEN string for correctness.

    Checks that the FEN is parseable by python-chess and that both kings
    are present on the board.

    Args:
        fen: The FEN string to validate.

    Returns:
        A tuple of (is_valid, error_message). If valid, error_message is None.
    """
    try:
        board = chess.Board(fen)
    except ValueError as e:
        return False, f"Invalid FEN format: {e}"

    if board.king(chess.WHITE) is None:
        return False, "Invalid position: White king is missing"
    if board.king(chess.BLACK) is None:
        return False, "Invalid position: Black king is missing"

    return True, None

ROOK_HOME_SQUARES = {
    chess.WHITE: {"k": chess.H1, "q": chess.A1},
    chess.BLACK: {"k": chess.H8, "q": chess.A8},
}

def king_zone_files(square: int | None) -> set[int]:
    """Return the mover king's file plus any adjacent files, clamped to the 0-7 board range."""
    if square is None:
        return set()
    file_idx = chess.square_file(square)
    return set(range(max(0, file_idx - 1), min(7, file_idx + 1) + 1))

def piece_undefended(board: chess.Board, square: int, color: bool) -> tuple[bool, chess.Piece | None]:
    """Return (True, piece) if the piece of `color` on `square` has zero defenders."""
    piece = board.piece_at(square)
    if not piece or piece.color != color:
        return False, None
    defenders = board.attackers(color, square)
    return len(defenders) == 0, piece

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

def king_exposed_heuristic(board: chess.Board, side: bool) -> dict[int, int]:
    """Analyze king safety by evaluating escape square danger.

    For each unattacked neighboring square around the king, calculates how much
    more dangerous that square would be if the king moved there. A higher value
    indicates the king's escape routes are becoming more restricted.

    Args:
        board: The chess board position to analyze.
        side: The color of the king to evaluate (chess.WHITE or chess.BLACK).

    Returns:
        A dict mapping square indices to their increased danger level.
        Empty dict means the king has safe escape squares.
        Example: {chess.E2: 2, chess.F2: 1} means moving to e2 would expose
        the king to 2 more attacks than the current position.
    """
    king_sq = board.king(side)
    if king_sq is None:
        return {}

    neighbors = [sq for sq in chess.SQUARES if chess.square_distance(sq, king_sq) == 1]
    attacks = sum(1 for sq in neighbors if board.is_attacked_by(not side, sq))
    unattacked = (sq for sq in neighbors if not board.is_attacked_by(not side, sq))

    # For every unattacked neighboring square, calculate attack score.
    # If the attack score is greater, moving to that square is more dangerous.
    attack_dict: dict[int, int] = {}

    for neighbor_sq in unattacked:
        sq_to_check = neighbor_sq
        board_copy = board.copy(stack=False)
        board_copy.remove_piece_at(king_sq)
        board_copy.set_piece_at(sq_to_check, chess.Piece(chess.KING, side))

        new_neighbors = [sq for sq in chess.SQUARES if chess.square_distance(sq, sq_to_check) == 1]
        neighbor_attacks = sum(1 for sq in new_neighbors if board_copy.is_attacked_by(not side, sq))
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
    features["pawn_structure_before"] = analyze_pawn_structure(board)

    # Raw material score for reference
    features["material_raw_before"] = features["material_before"] 
    
    features["is_hanging_to_lesser"] = is_hanging_to_lesser_piece(board, move)

    features["opening_notes"] = check_opening_principles(board, move, board.fullmove_number * 2)
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
    features["pawn_structure_after"] = analyze_pawn_structure(board)

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
    def count_moves(color: bool) -> int:
        copy = board.copy(stack=False)
        copy.turn = color
        return sum(1 for _ in copy.legal_moves)

    return count_moves(chess.WHITE), count_moves(chess.BLACK)

def get_center_control_scores(board: chess.Board) -> tuple[int, int]:
    """Evaluates each side's center control based on the number of moves that are attacking the center squares: d4, e4, d5, e5."""
    center_squares = {'d4', 'e4', 'd5', 'e5'}

    def count_center_moves(color: bool) -> int:
        copy = board.copy(stack=False)
        copy.turn = color
        total = 0
        for move in copy.legal_moves:
            if chess.square_name(move.to_square) in center_squares:
                total += 1
        return total

    return count_center_moves(chess.WHITE), count_center_moves(chess.BLACK)

def is_hanging_to_lesser_piece(board: chess.Board, move: chess.Move) -> bool:
    """Check if you're hanging a high value piece to a lower value piece."""
    piece = board.piece_at(move.from_square)
    if not piece: return False
    

    values = {PAWN: 1, KNIGHT: 3, BISHOP: 3, ROOK: 5, QUEEN: 9, KING: 100}
    our_val = values.get(piece.piece_type, 0)
    

    tmp = board.copy(stack=False)
    tmp.push(move)
    
    attackers = tmp.attackers(tmp.turn, move.to_square)
    for sq in attackers:
        attacker_piece = tmp.piece_at(sq)
        if attacker_piece and values.get(attacker_piece.piece_type, 0) < our_val:
            return True
    return False
def check_opening_principles(board: chess.Board, move: chess.Move, ply_count: int) -> list[str]:
    """Return simple heuristic flags for opening mistakes."""
    notes = []
    
    # Only applying to approximate "opening"
    if ply_count > 16: return notes
    

    if len(board.piece_map()) < 10: return notes

    piece = board.piece_at(move.from_square)
    if not piece: return notes


    if piece.piece_type == QUEEN:
        notes.append("early_queen")


    if piece.piece_type not in [PAWN, KING]:
        is_white = board.turn == chess.WHITE
        home_rank = 0 if is_white else 7
        current_rank = chess.square_rank(move.from_square)
        
        if current_rank != home_rank:
             notes.append("moved_twice")
             
    return notes

def detect_doubled_pawns(board: chess.Board, color: bool) -> list[str]:
    """Detect files with multiple pawns of the same color."""
    doubled_files = []
    pawns = board.pieces(chess.PAWN, color)
    
    for file_idx in range(8):
        file_pawns = 0
        for square in pawns:
            if chess.square_file(square) == file_idx:
                file_pawns += 1
        
        if file_pawns >= 2:
            doubled_files.append(chess.FILE_NAMES[file_idx])
    
    return doubled_files

def detect_isolated_pawns(board: chess.Board, color: bool) -> list[str]:
    """Detect pawns with no friendly pawns on adjacent files."""
    isolated_files = []
    pawns = board.pieces(chess.PAWN, color)
    
    for square in pawns:
        file_idx = chess.square_file(square)
        has_adjacent_pawn = False
        
        # Check adjacent files for friendly pawns
        for adj_file in [file_idx - 1, file_idx + 1]:
            if 0 <= adj_file <= 7:
                for other_square in pawns:
                    if chess.square_file(other_square) == adj_file:
                        has_adjacent_pawn = True
                        break
                if has_adjacent_pawn:
                    break
        
        if not has_adjacent_pawn:
            file_name = chess.FILE_NAMES[file_idx]
            if file_name not in isolated_files:
                isolated_files.append(file_name)
    
    return isolated_files

def detect_passed_pawns(board: chess.Board, color: bool) -> list[str]:
    """Detect pawns with no enemy pawns blocking their path to promotion."""
    passed_squares = []
    pawns = board.pieces(chess.PAWN, color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    
    for square in pawns:
        file_idx = chess.square_file(square)
        rank_idx = chess.square_rank(square)
        is_passed = True
        
        # Check if any enemy pawns can block this pawn's path
        for enemy_square in enemy_pawns:
            enemy_file = chess.square_file(enemy_square)
            enemy_rank = chess.square_rank(enemy_square)
            
            # Enemy pawn on same file or adjacent files
            if abs(enemy_file - file_idx) <= 1:
                if color == chess.WHITE:
                    # White pawn: check if enemy pawn is ahead
                    if enemy_rank > rank_idx:
                        is_passed = False
                        break
                else:
                    # Black pawn: check if enemy pawn is ahead  
                    if enemy_rank < rank_idx:
                        is_passed = False
                        break
        
        if is_passed:
            passed_squares.append(chess.square_name(square))
    
    return passed_squares

def analyze_pawn_structure(board: chess.Board) -> dict:
    """Analyze pawn structure for both sides."""
    return {
        "white": {
            "doubled": detect_doubled_pawns(board, chess.WHITE),
            "isolated": detect_isolated_pawns(board, chess.WHITE), 
            "passed": detect_passed_pawns(board, chess.WHITE)
        },
        "black": {
            "doubled": detect_doubled_pawns(board, chess.BLACK),
            "isolated": detect_isolated_pawns(board, chess.BLACK),
            "passed": detect_passed_pawns(board, chess.BLACK)
        }
    }