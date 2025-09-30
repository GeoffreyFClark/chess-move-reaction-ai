import chess
from settings import settings

TEMPLATES = {
    "great_tactic": [
        "Great tactic! That move creates immediate pressure and improves your material situation."
    ],
    "solid_improvement": [
        "Prudent choice — this improves your position and reduces risk."
    ],
    "warning_hanging": [
        "Careful — that square is dangerous; your piece may be in danger."
    ],
    "blunderish": [
        "This looks like a serious mistake — the tactic against you is strong."
    ],
    "neutral": [
        "Reasonable — keeps the balance without forcing matters."
    ],
    "mate_for": [
        "Checkmate! Beautiful finish — the game is over."
    ],
    "mate_against": [
        "Careful — this line allows a forced mate against you."
    ],
    "stalemate": [
        "Stalemate — the game ends in a draw."
    ]
}

def pick_line(key: str) -> str:
    arr = TEMPLATES.get(key, TEMPLATES["neutral"])
    return arr[0]

def explain_move(fen: str, move_str: str) -> dict:
    board = chess.Board(fen)
    # Normalize move
    try:
        try:
            move = board.parse_san(move_str)
            normalized_move = board.san(move)
        except ValueError:
            move = board.parse_uci(move_str)
            normalized_move = board.san(move)
    except ValueError as e:
        raise ValueError(f"Invalid move: {move_str}") from e

    feats = extract_features_before_after(fen, move)

    reaction = f"{pick_line(key)}"

    # Create after-FEN and attach engine evals (diff) if configured
    board_after = chess.Board(fen)
    board_after.push(move)
    fen_after = board_after.fen()

    details = feats

    return {
        "normalized_move": normalized_move,
        "reaction": reaction,
        "details": details,
    }