"""Utility functions for move explanation."""

import chess


def describe_piece(piece: chess.Piece) -> str:
    """Get a human-readable name for a chess piece.

    Args:
        piece: The chess piece to describe.

    Returns:
        Capitalized piece name (e.g., "Knight", "Queen").
    """
    names = {
        chess.PAWN: "Pawn",
        chess.KNIGHT: "Knight",
        chess.BISHOP: "Bishop",
        chess.ROOK: "Rook",
        chess.QUEEN: "Queen",
        chess.KING: "King",
    }
    return names.get(piece.piece_type, "Piece")
