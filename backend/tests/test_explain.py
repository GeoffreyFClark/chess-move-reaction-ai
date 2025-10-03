import os
import sys
import pytest
import chess

# This line allows imports from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from explain import explain_move
from features import parse_move, material_score


def test_basic_e4():
	fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
	out = explain_move(fen, "e4")
	assert out["normalized_move"] == "e4"
	assert "reaction" in out


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