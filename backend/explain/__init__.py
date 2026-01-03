"""Chess move explanation module.

This module provides natural language explanations for chess moves,
analyzing tactical, positional, and strategic aspects of each move.
"""

from .core import explain_move
from .engine_summary import EngineSummary, summarize_engine
from .reason_builder import ReasonBuilder
from .templates import ENGINE_TONE_BANK, TEMPLATES, pick_engine_line, pick_line
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
