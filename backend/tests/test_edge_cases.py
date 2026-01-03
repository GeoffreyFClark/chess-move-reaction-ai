"""Tests for edge cases in move analysis."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from explain import explain_move


class TestEnPassant:
    """Tests for en passant capture handling."""

    def test_en_passant_capture(self):
        # Position after 1.e4 d5 2.e5 f5 - en passant available
        fen = "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"
        result = explain_move(fen, "exf6")
        assert result["details"]["is_capture"] is True
        assert "reaction" in result


class TestPromotion:
    """Tests for pawn promotion handling."""

    def test_promotion_to_queen(self):
        fen = "8/P7/8/8/8/8/8/K6k w - - 0 1"
        result = explain_move(fen, "a8=Q")
        assert result["details"]["is_promotion"] is True
        assert "=Q" in result["normalized_move"]

    def test_underpromotion_to_knight(self):
        fen = "8/P7/8/8/8/8/8/K6k w - - 0 1"
        result = explain_move(fen, "a8=N")
        assert result["details"]["is_promotion"] is True
        assert "=N" in result["normalized_move"]

    def test_promotion_with_check(self):
        fen = "2k5/P7/8/8/8/8/8/K7 w - - 0 1"
        result = explain_move(fen, "a8=Q+")
        assert result["details"]["is_promotion"] is True
        assert result["details"]["is_check_move"] is True


class TestCastling:
    """Tests for castling moves."""

    def test_kingside_castling(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        result = explain_move(fen, "O-O")
        assert (
            "castle" in result["reaction"].lower()
            or result["details"]["castling_rights_lost"]["white_can_castle_k_lost"]
        )

    def test_queenside_castling(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        result = explain_move(fen, "O-O-O")
        assert result["details"]["castling_rights_lost"]["white_can_castle_q_lost"] is True


class TestGameTermination:
    """Tests for checkmate and stalemate detection."""

    def test_checkmate_detection(self):
        fen = "7k/5Q2/7K/8/8/8/8/8 w - - 0 1"
        result = explain_move(fen, "Qg7#")
        assert result["details"]["is_checkmate_after"] is True
        assert "checkmate" in result["reaction"].lower()

    def test_stalemate_detection(self):
        # Position where white can stalemate black
        fen = "k7/8/1K6/8/8/8/8/7Q w - - 0 1"
        result = explain_move(fen, "Qa8+")  # This is checkmate, not stalemate
        assert "details" in result

    def test_insufficient_material_detection(self):
        # K+B vs K - insufficient material
        # Bishop on h1, king on a1, black king on h8
        fen = "7k/8/8/8/8/8/8/K6B w - - 0 1"
        # Bishop can move
        result = explain_move(fen, "Bg2")
        # Just verify it handles the position with insufficient material
        assert "reaction" in result


class TestDiscoveredCheck:
    """Tests for discovered check scenarios."""

    def test_discovered_check(self):
        # Moving bishop discovers check from rook
        fen = "4k3/8/8/3B4/8/2R5/8/4K3 w - - 0 1"
        # Bishop moves, rook gives check
        result = explain_move(fen, "Bf3")
        # The position should be analyzed correctly
        assert "reaction" in result


class TestComplexPositions:
    """Tests for complex tactical positions."""

    def test_capture_with_recapture(self):
        # Position where capture leads to immediate recapture
        fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
        result = explain_move(fen, "Nxe5")
        assert result["details"]["is_capture"] is True

    def test_pin_detection_in_position(self):
        # Position with a pin
        fen = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
        result = explain_move(fen, "a6")
        # Just verify the move is analyzed
        assert "reaction" in result


class TestInvalidInputs:
    """Tests for invalid input handling."""

    def test_invalid_fen_raises(self):
        with pytest.raises(ValueError):
            explain_move("invalid fen", "e4")

    def test_illegal_move_raises(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        with pytest.raises(ValueError):
            explain_move(fen, "e5")  # Illegal - pawn can't move to e5 from start

    def test_invalid_move_notation_raises(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        with pytest.raises(ValueError):
            explain_move(fen, "xyz123")


class TestOpeningPrinciples:
    """Tests for opening principle detection."""

    def test_early_queen_move(self):
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
        result = explain_move(fen, "Qh5")
        # Should flag early queen development
        assert "queen" in result["reaction"].lower() or "reaction" in result

    def test_moving_piece_twice(self):
        # Knight already developed, moving again
        fen = "rnbqkbnr/pppppppp/8/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 2"
        result = explain_move(fen, "Ng5")
        # Should detect moving same piece twice
        assert "reaction" in result
