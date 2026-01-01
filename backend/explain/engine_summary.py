"""Engine evaluation summary utilities."""
from typing import TypedDict

from .templates import ENGINE_TONE_THRESHOLDS


class EngineSummary(TypedDict, total=False):
    """Summary of engine evaluation for a move."""

    available: bool
    tone: str | None
    delta_cp: int | None
    before_cp: int | None
    after_cp: int | None


def tone_from_delta(delta_pawns: float) -> str:
    """Determine engine tone based on centipawn delta.

    Args:
        delta_pawns: The evaluation change in pawns (can be negative).

    Returns:
        Tone string: "excellent", "good", "okay", "mistake", or "blunder".
    """
    delta_abs = abs(delta_pawns)
    for limit, tone in ENGINE_TONE_THRESHOLDS:
        if delta_abs <= limit:
            return tone
    return "blunder"


def summarize_engine(engine: dict | None, mover: str) -> EngineSummary:
    """Create a summary of engine evaluation results.

    Args:
        engine: Raw engine result dict with before/after evaluations.
        mover: The side that made the move ("White" or "Black").

    Returns:
        EngineSummary with tone, delta, and oriented scores.
    """
    summary: EngineSummary = {
        "available": False,
        "tone": None,
        "delta_cp": None,
        "before_cp": None,
        "after_cp": None,
    }

    if not engine or not engine.get("enabled"):
        return summary

    before = engine.get("before", {})
    after = engine.get("after", {})

    if not before.get("ok") or not after.get("ok"):
        return summary

    cp_before = before.get("score_centipawn")
    cp_after = after.get("score_centipawn")
    mate_before = before.get("mate_in")
    mate_after = after.get("mate_in")

    summary["available"] = True
    is_white_mover = mover.lower().startswith("white")

    def orient(value: int | None) -> int | None:
        """Orient score from the mover's perspective."""
        if value is None:
            return None
        return value if is_white_mover else -value

    # Handle centipawn scores
    if cp_before is not None and cp_after is not None:
        oriented_before = orient(cp_before)
        oriented_after = orient(cp_after)
        delta_cp = oriented_after - oriented_before

        summary["before_cp"] = oriented_before
        summary["after_cp"] = oriented_after
        summary["delta_cp"] = delta_cp
        summary["tone"] = tone_from_delta(delta_cp / 100.0)
        return summary

    # Handle mate scores
    if mate_before is not None or mate_after is not None:
        oriented_before = orient(mate_before) if mate_before is not None else 0
        oriented_after = orient(mate_after) if mate_after is not None else 0
        delta = oriented_after - oriented_before
        abs_delta = abs(delta)

        # Simplified mate tone logic
        if abs_delta <= 0.15:
            summary["tone"] = "excellent"
        elif abs_delta <= 0.99:
            summary["tone"] = "mistake"
        else:
            summary["tone"] = "blunder"

        summary["delta_cp"] = None

    return summary
