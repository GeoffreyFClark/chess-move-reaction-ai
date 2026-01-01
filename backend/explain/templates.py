"""Reaction templates and tone selection for chess move explanations."""
import random

# Move category templates - used for generating base reaction headlines
TEMPLATES: dict[str, list[str]] = {
    "great_tactic": [
        "Tactical shot.",
        "Nice tactics!",
        "Sharp move!"
    ],
    "solid_improvement": [
        "Improving move.",
        "Good positional play.",
        "This strengthens your position."
    ],
    "warning_hanging": [
        "Loose piece warning.",
        "Careful! Piece in danger.",
        "Watch out - loose pieces drop off."
    ],
    "blunderish": [
        "Likely mistake.",
        "This looks questionable.",
        "Risky decision here."
    ],
    "neutral": [
        "Balanced move.",
        "Reasonable choice.",
        "Steady play."
    ],
    "mate_for": [
        "Checkmate.",
        "Game over - checkmate!",
        "Victory achieved!"
    ],
    "mate_against": [
        "Mate threat against you.",
        "Danger - mate on the horizon.",
        "Critical defensive situation."
    ],
    "stalemate": [
        "Stalemate.",
        "No legal moves - game drawn.",
        "Draw by stalemate."
    ],
    "insufficient_material": [
        "Draw by insufficient material.",
        "Neither side can force checkmate.",
        "The game is drawn - not enough pieces remain."
    ],
    "game_continues": [
        "Game continues.",
        "Play on.",
        "The position remains dynamic."
    ]
}

# Engine-based tone templates - used when Stockfish evaluation is available
ENGINE_TONE_BANK: dict[str, list[str]] = {
    "excellent": [  # <0.2 delta
        "Excellent move.",
        "This is a very precise move.",
        "This is one of the top moves."
    ],
    "good": [  # 0.2 to 0.44 delta
        "Good move.",
        "A solid choice.",
        "Not the absolute best option, but still good."
    ],
    "okay": [  # 0.45 to 0.74 delta
        "Okay move. There were stronger alternatives.",
        "This move is not great, but it's playable.",
        "This is serviceable play, though stronger moves existed."
    ],
    "mistake": [  # 0.75 to 1.24 delta
        "Mistake detected.",
        "The engine disapproves.",
        "A noticeable evaluation drop from the engine."
    ],
    "blunder": [  # 1.25+ delta
        "Blunder! This move can be punished severely.",
        "This move is a blunder and leads to a disadvantage.",
        "A significant blunder according to the engine."
    ]
}

# Thresholds for engine tone classification (in pawns)
ENGINE_TONE_THRESHOLDS: list[tuple[float, str]] = [
    (0.19, "excellent"),
    (0.44, "good"),
    (0.74, "okay"),
    (1.24, "mistake"),
]


def pick_line(key: str) -> str:
    """Select a random template line for the given category.

    Args:
        key: The template category key (e.g., "great_tactic", "neutral").

    Returns:
        A randomly selected template string, or a neutral one if key not found.
    """
    arr = TEMPLATES.get(key, TEMPLATES["neutral"])
    return random.choice(arr)


def pick_engine_line(tone: str) -> str:
    """Select a random engine tone line.

    Args:
        tone: The engine tone (e.g., "excellent", "blunder").

    Returns:
        A randomly selected tone string, or empty string if tone not found.
    """
    if tone and tone in ENGINE_TONE_BANK:
        return random.choice(ENGINE_TONE_BANK[tone])
    return ""
