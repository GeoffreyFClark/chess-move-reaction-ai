import os
import sys
import pytest
import chess

# This line allows imports from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from explain import explain_move
from features import parse_move, material_score, extract_features_before_after


def test_basic_e4():
	fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
	out = explain_move(fen, "e4")
	assert out["normalized_move"] == "e4"
	assert "reaction" in out


def test_basic_e4_uci_input():
	fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
	out = explain_move(fen, "e2e4")
	assert out["normalized_move"] == "e4"
	assert out["details"]["legal"] is True


def test_illegal_move_raises():
	fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
	with pytest.raises(ValueError):
		explain_move(fen, "e5")  # illegal for White on first move


def test_parse_move_valid_and_invalid():
	board = chess.Board()
	# valid SAN
	mv = parse_move(board, "Nf3")
	assert isinstance(mv, chess.Move)
	# valid UCI
	mv2 = parse_move(board, "g1f3")
	assert isinstance(mv2, chess.Move)
	# invalid
	with pytest.raises(ValueError):
		parse_move(board, "invalid")


def test_material_score_simple():
	board = chess.Board()
	# Starting position material should be 0 (balanced)
	assert material_score(board) == 0
	# Remove black queen to change material
	board.remove_piece_at(chess.square(3, 7))  # d8
	assert material_score(board) == 9


def test_explain_move_capture_and_check():
	# Position where white can capture and give check: simple constructed FEN
	fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
	# A common move Nxe5 (knight captures pawn on e5)
	res = explain_move(fen, "Nxe5")
	assert "normalized_move" in res
	assert "reaction" in res
	assert "details" in res
	# capture should be detected in details
	assert res["details"]["is_capture"] is True


def test_extract_features_include_new_metrics():
	fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
	board = chess.Board(fen)
	move = parse_move(board, "e4")
	feats = extract_features_before_after(fen, move)
	assert "mobility_before" in feats and "mobility_after" in feats
	assert feats["mobility_before"]["white"] > 0
	assert "center_control_before" in feats and "center_control_after" in feats
	assert set(feats["center_control_before"].keys()) == {"white", "black"}


def test_castling_rights_lost_detected():
	fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
	result = explain_move(fen, "O-O")
	lost = result["details"]["castling_rights_lost"]
	assert lost["white_can_castle_k_lost"] is True
	assert lost["white_can_castle_q_lost"] is True


	fen = "2k5/P7/8/8/8/8/8/K6R w K - 0 1"
	result = explain_move(fen, "a8=Q+")
	assert result["details"]["is_promotion"] is True
	assert "=Q" in result["normalized_move"]


def test_explain_move_sets_checkmate_flag():
	fen = "7k/5Q2/7K/8/8/8/8/8 w - - 0 1"
	result = explain_move(fen, "Qg7#")
	assert result["details"]["is_checkmate_after"] is True
	assert "checkmate" in result["reaction"].lower()