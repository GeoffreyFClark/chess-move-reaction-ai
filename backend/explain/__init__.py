"""Chess move explanation module.

This module provides natural language explanations for chess moves,
analyzing tactical, positional, and strategic aspects of each move.
"""
from .core import explain_move
from .templates import TEMPLATES, ENGINE_TONE_BANK, pick_line, pick_engine_line
from .engine_summary import summarize_engine, EngineSummary
from .reason_builder import ReasonBuilder
from .utils import describe_piece

__all__ = [
    "explain_move",
    "TEMPLATES",
    "ENGINE_TONE_BANK",
    "pick_line",
    "pick_engine_line",
    "summarize_engine",
    "EngineSummary",
    "ReasonBuilder",
    "describe_piece",
]
