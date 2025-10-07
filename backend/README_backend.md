# Backend quickstart

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Run API
uvicorn app:app --reload --port 8000

# Try CLI (example: initial chess position and 1. e4)
python cli.py --fen "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" --move "e4"

# Running tests (make sure any additional tests are named test_*.py so pytest auto-discovers them)
pytest -q
```

```
├── README_backend.md
├── app.py
├── cli.py
├── engine.py
├── explain.py
├── features.py
├── requirements.txt
├── schemas.py
├── settings.py
└── tests
    └── test_explain.py
```

- app.py           - FastAPI app and /api/analyze endpoint
- cli.py           - CLI wrapper to analyze a single FEN+move locally
- explain.py       - Rule-based “reaction” engine + endgame messaging + (optional) engine deltas
- features.py      - Feature extraction: material, tactical flags, endgame flags
- engine.py        - Stockfish UCI runner (before/after evals) + configuration checks
- schemas.py       - Pydantic request/response models for API
- settings.py      - Config via env vars (CORS, STOCKFISH_PATH, depth, host/port)
- tests/
  test_explain.py  - Basic tests for parsing and explanations

## features.py

### get_mobility_scores(...)
- evaluates each side's mobility based on the number of available moves per side.

### get_center_control_scores(...)
- evaluates each side's center control based on the number of moves that are attacking the 
center squares: d4, e4, d5, e5.