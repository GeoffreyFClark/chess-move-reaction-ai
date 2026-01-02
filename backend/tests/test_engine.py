"""Tests for the engine module."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import is_configured, _uci_eval


class TestEngineConfiguration:
    """Tests for engine configuration checks."""

    def test_is_configured_without_path(self):
        with patch('engine.settings') as mock_settings:
            mock_settings.stockfish_path = None
            assert is_configured() is False

    def test_is_configured_with_nonexistent_path(self):
        with patch('engine.settings') as mock_settings:
            mock_settings.stockfish_path = "/nonexistent/path/stockfish"
            with patch('os.path.isfile', return_value=False):
                with patch('shutil.which', return_value=None):
                    assert is_configured() is False

    def test_is_configured_with_valid_file(self):
        with patch('engine.settings') as mock_settings:
            mock_settings.stockfish_path = "/usr/bin/stockfish"
            with patch('os.path.isfile', return_value=True):
                assert is_configured() is True


class TestUciEval:
    """Tests for UCI evaluation function."""

    def test_returns_error_when_not_configured(self):
        with patch('engine.is_configured', return_value=False):
            result = _uci_eval("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 10)
            assert result["ok"] is False
            assert "not configured" in result["note"].lower()

    def test_returns_error_on_popen_failure(self):
        with patch('engine.is_configured', return_value=True):
            with patch('subprocess.Popen', side_effect=Exception("Popen failed")):
                result = _uci_eval("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 10)
                assert result["ok"] is False
                assert "Unable to start" in result["note"]
