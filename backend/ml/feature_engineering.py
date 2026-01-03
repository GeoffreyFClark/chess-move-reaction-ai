"""Feature engineering for ML move quality prediction.

Extracts numerical features from chess positions and moves
for use in machine learning models.
"""
import chess
from typing import TypedDict


class PositionFeatures(TypedDict):
    """Feature dictionary for a chess position and move."""

    # Piece counts (10 features)
    white_pawns: int
    white_knights: int
    white_bishops: int
    white_rooks: int
    white_queens: int
    black_pawns: int
    black_knights: int
    black_bishops: int
    black_rooks: int
    black_queens: int

    # Positional (6 features)
    material_balance: float
    center_control_white: int
    center_control_black: int
    mobility_white: int
    mobility_black: int
    game_phase: float

    # Move-specific (6 features)
    is_capture: int
    is_check: int
    is_promotion: int
    piece_value_moved: int
    piece_value_captured: int
    to_square_attacked: int


PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # King value not counted for material
}


def extract_ml_features(board: chess.Board, move: chess.Move) -> list[float]:
    """Extract a feature vector for ML model input.

    Args:
        board: The chess board position before the move.
        move: The move to analyze.

    Returns:
        A list of 22 numerical features.
    """
    features: list[float] = []

    # Piece counts (10 features)
    for color in [chess.WHITE, chess.BLACK]:
        for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            features.append(float(len(board.pieces(piece_type, color))))

    # Material balance (1 feature)
    white_material = sum(
        len(board.pieces(pt, chess.WHITE)) * val
        for pt, val in PIECE_VALUES.items()
    )
    black_material = sum(
        len(board.pieces(pt, chess.BLACK)) * val
        for pt, val in PIECE_VALUES.items()
    )
    features.append(float(white_material - black_material))

    # Center control (2 features)
    center_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
    white_center = sum(1 for sq in center_squares if board.is_attacked_by(chess.WHITE, sq))
    black_center = sum(1 for sq in center_squares if board.is_attacked_by(chess.BLACK, sq))
    features.append(float(white_center))
    features.append(float(black_center))

    # Mobility (2 features)
    board_copy = board.copy(stack=False)
    board_copy.turn = chess.WHITE
    white_mobility = len(list(board_copy.legal_moves))
    board_copy.turn = chess.BLACK
    black_mobility = len(list(board_copy.legal_moves))
    features.append(float(white_mobility))
    features.append(float(black_mobility))

    # Game phase (1 feature) - 0=opening, 0.5=middlegame, 1=endgame
    total_material = white_material + black_material
    max_material = 78  # Starting material minus kings
    game_phase = 1 - (total_material / max_material) if max_material > 0 else 1.0
    features.append(game_phase)

    # Move-specific features (6 features)
    features.append(1.0 if board.is_capture(move) else 0.0)
    features.append(1.0 if board.gives_check(move) else 0.0)
    features.append(1.0 if move.promotion else 0.0)

    moving_piece = board.piece_at(move.from_square)
    features.append(float(PIECE_VALUES.get(moving_piece.piece_type, 0)) if moving_piece else 0.0)

    captured_piece = board.piece_at(move.to_square)
    features.append(float(PIECE_VALUES.get(captured_piece.piece_type, 0)) if captured_piece else 0.0)

    # Is the destination square attacked by opponent?
    features.append(1.0 if board.is_attacked_by(not board.turn, move.to_square) else 0.0)

    return features


def get_feature_names() -> list[str]:
    """Return the names of all features in order.

    Returns:
        List of feature name strings.
    """
    return [
        "white_pawns", "white_knights", "white_bishops", "white_rooks", "white_queens",
        "black_pawns", "black_knights", "black_bishops", "black_rooks", "black_queens",
        "material_balance",
        "center_control_white", "center_control_black",
        "mobility_white", "mobility_black",
        "game_phase",
        "is_capture", "is_check", "is_promotion",
        "piece_value_moved", "piece_value_captured",
        "to_square_attacked",
    ]
