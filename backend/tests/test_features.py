"""Tests for the features module."""

import os
import sys

import chess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from features import (
    analyze_pawn_structure,
    castling_rights_lost,
    count_pins,
    detect_doubled_pawns,
    detect_isolated_pawns,
    detect_passed_pawns,
    get_castling_rights,
    get_center_control_scores,
    get_mobility_scores,
    is_hanging_to_lesser_piece,
    king_exposed_heuristic,
    material_score,
    parse_move,
    piece_undefended,
    validate_fen,
)


class TestValidateFen:
    """Tests for FEN validation."""

    def test_valid_starting_position(self):
        valid, error = validate_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert valid is True
        assert error is None

    def test_valid_mid_game_position(self):
        valid, error = validate_fen(
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        )
        assert valid is True
        assert error is None

    def test_invalid_no_white_king(self):
        valid, error = validate_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ1BNR w KQkq - 0 1")
        assert valid is False
        assert "White king" in error

    def test_invalid_no_black_king(self):
        valid, error = validate_fen("rnbq1bnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert valid is False
        assert "Black king" in error

    def test_invalid_malformed_fen(self):
        valid, error = validate_fen("not a valid fen")
        assert valid is False
        assert error is not None


class TestMaterialScore:
    """Tests for material scoring."""

    def test_starting_position_balanced(self):
        board = chess.Board()
        assert material_score(board) == 0

    def test_white_up_queen(self):
        board = chess.Board()
        board.remove_piece_at(chess.D8)  # Remove black queen
        assert material_score(board) == 9

    def test_black_up_rook(self):
        board = chess.Board()
        board.remove_piece_at(chess.A1)  # Remove white rook
        assert material_score(board) == -5

    def test_white_up_pawn(self):
        board = chess.Board()
        board.remove_piece_at(chess.A7)  # Remove black pawn
        assert material_score(board) == 1

    def test_complex_material_imbalance(self):
        # White: K, R(5), B(3) = 8
        # Black: K, Q(9) = 9
        # Balance: 8 - 9 = -1
        board = chess.Board("8/8/8/8/8/8/8/KRB2q1k w - - 0 1")
        assert material_score(board) == 5 + 3 - 9  # -1


class TestKingExposedHeuristic:
    """Tests for king safety heuristic."""

    def test_starting_position_safe(self):
        board = chess.Board()
        result = king_exposed_heuristic(board, chess.WHITE)
        assert isinstance(result, dict)
        # King is well protected in starting position

    def test_king_in_center_exposed(self):
        # King on e4 with attackers nearby
        board = chess.Board("8/8/3r4/8/4K3/8/8/4k3 w - - 0 1")
        result = king_exposed_heuristic(board, chess.WHITE)
        assert isinstance(result, dict)

    def test_returns_empty_dict_when_no_king(self):
        board = chess.Board()
        board.remove_piece_at(chess.E1)  # Remove white king (invalid but for testing)
        result = king_exposed_heuristic(board, chess.WHITE)
        assert result == {}


class TestCountPins:
    """Tests for pin detection."""

    def test_no_pins_starting_position(self):
        board = chess.Board()
        pins = count_pins(board)
        assert pins["white"] == 0
        assert pins["black"] == 0

    def test_detect_pin(self):
        # Black bishop pins white knight to white king
        board = chess.Board("4k3/8/8/8/8/2b5/3N4/4K3 w - - 0 1")
        pins = count_pins(board)
        assert pins["white"] == 1
        assert pins["black"] == 0


class TestCastlingRights:
    """Tests for castling rights detection."""

    def test_starting_position_all_rights(self):
        board = chess.Board()
        rights = get_castling_rights(board)
        assert rights["white_can_castle_k"] is True
        assert rights["white_can_castle_q"] is True
        assert rights["black_can_castle_k"] is True
        assert rights["black_can_castle_q"] is True

    def test_no_castling_rights(self):
        board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        rights = get_castling_rights(board)
        assert rights["white_can_castle_k"] is False
        assert rights["white_can_castle_q"] is False

    def test_castling_rights_lost(self):
        before = {
            "white_can_castle_k": True,
            "white_can_castle_q": True,
            "black_can_castle_k": True,
            "black_can_castle_q": True,
        }
        after = {
            "white_can_castle_k": False,
            "white_can_castle_q": True,
            "black_can_castle_k": True,
            "black_can_castle_q": False,
        }
        lost = castling_rights_lost(before, after)
        assert lost["white_can_castle_k_lost"] is True
        assert lost["white_can_castle_q_lost"] is False
        assert lost["black_can_castle_k_lost"] is False
        assert lost["black_can_castle_q_lost"] is True


class TestMobility:
    """Tests for mobility scoring."""

    def test_starting_position_mobility(self):
        board = chess.Board()
        white_mob, black_mob = get_mobility_scores(board)
        assert white_mob == 20  # Standard starting mobility
        assert black_mob == 20

    def test_mobility_changes_after_move(self):
        board = chess.Board()
        board.push_san("e4")
        white_mob, black_mob = get_mobility_scores(board)
        # After e4, mobility changes
        assert white_mob > 0
        assert black_mob > 0


class TestCenterControl:
    """Tests for center control scoring."""

    def test_starting_position_center_control(self):
        board = chess.Board()
        white_cc, black_cc = get_center_control_scores(board)
        assert white_cc >= 0
        assert black_cc >= 0

    def test_center_control_after_e4(self):
        board = chess.Board()
        board.push_san("e4")
        white_cc, black_cc = get_center_control_scores(board)
        # e4 controls d5 and f5, plus existing moves
        assert white_cc > 0


class TestPawnStructure:
    """Tests for pawn structure analysis."""

    def test_no_weaknesses_starting_position(self):
        board = chess.Board()
        doubled = detect_doubled_pawns(board, chess.WHITE)
        isolated = detect_isolated_pawns(board, chess.WHITE)
        passed = detect_passed_pawns(board, chess.WHITE)
        assert doubled == []
        assert isolated == []
        assert passed == []

    def test_detect_doubled_pawns(self):
        # Two white pawns on e-file
        board = chess.Board("8/8/8/4P3/4P3/8/8/4K2k w - - 0 1")
        doubled = detect_doubled_pawns(board, chess.WHITE)
        assert "e" in doubled

    def test_detect_isolated_pawn(self):
        # Single white pawn on e4 with no adjacent pawns
        board = chess.Board("8/8/8/8/4P3/8/8/4K2k w - - 0 1")
        isolated = detect_isolated_pawns(board, chess.WHITE)
        assert "e" in isolated

    def test_detect_passed_pawn(self):
        # White pawn on e5 with no black pawns blocking
        board = chess.Board("8/8/8/4P3/8/8/8/4K2k w - - 0 1")
        passed = detect_passed_pawns(board, chess.WHITE)
        assert "e5" in passed

    def test_analyze_pawn_structure(self):
        board = chess.Board()
        structure = analyze_pawn_structure(board)
        assert "white" in structure
        assert "black" in structure
        assert "doubled" in structure["white"]
        assert "isolated" in structure["white"]
        assert "passed" in structure["white"]


class TestHangingPiece:
    """Tests for hanging piece detection."""

    def test_no_hanging_piece(self):
        board = chess.Board()
        move = board.parse_san("e4")
        assert is_hanging_to_lesser_piece(board, move) is False

    def test_queen_hanging_to_pawn(self):
        # Moving queen to a square attacked by a pawn
        # Queen on d1 can move to c2, which is attacked by pawn on b3
        board = chess.Board("4k3/8/8/8/8/1p6/8/3QK3 w - - 0 1")
        move = board.parse_san("Qc2")  # Queen moves to c2, attacked by b3 pawn
        result = is_hanging_to_lesser_piece(board, move)
        # This should detect the queen is attacked by the pawn
        assert result is True


class TestParseMove:
    """Tests for move parsing."""

    def test_parse_san_valid(self):
        board = chess.Board()
        move = parse_move(board, "e4")
        assert move == chess.Move.from_uci("e2e4")

    def test_parse_uci_valid(self):
        board = chess.Board()
        move = parse_move(board, "e2e4")
        assert move == chess.Move.from_uci("e2e4")

    def test_parse_invalid_raises(self):
        board = chess.Board()
        with pytest.raises(ValueError):
            parse_move(board, "invalid")

    def test_parse_knight_move(self):
        board = chess.Board()
        move = parse_move(board, "Nf3")
        assert move == chess.Move.from_uci("g1f3")


class TestPieceUndefended:
    """Tests for undefended piece detection."""

    def test_defended_piece(self):
        board = chess.Board()
        # Knight on g1 is defended by king
        undefended, piece = piece_undefended(board, chess.G1, chess.WHITE)
        assert undefended is False

    def test_undefended_piece(self):
        # Lone knight with no defenders
        board = chess.Board("8/8/8/4N3/8/8/8/4K2k w - - 0 1")
        undefended, piece = piece_undefended(board, chess.E5, chess.WHITE)
        assert undefended is True
        assert piece.piece_type == chess.KNIGHT
