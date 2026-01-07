# Chess Move Reaction AI

An AI chess analysis system that provides natural language reactions and explanations for chess moves. Unlike traditional chess engines that only output numerical evaluations, this AI acts like a coach - explaining *why* moves are good, bad, or interesting.

The concept can be expanded into customized coach/spectator/companion bots, i.e. famous players or commentators.

### How It Works
1. **Feature Extraction** - Extracts 20+ positional metrics (material, mobility, king safety, pawn structure, pins, etc).
2. **Engine Evaluation** (optional) - Stockfish centipawn deltas map to quality tones.
3. **Move Classification** - Heuristics and ML classify moves and generate contextual reasons.
4. **Reaction Assembly** - A tone-based headline combines with reasons to form the natural language reaction.

![Demo Screenshot](screenshots/sample-screenshot.png)

## Using Docker (Recommended)

**Option A - Build from source:**
```bash
git clone https://github.com/GeoffreyFClark/Chess-Move-Reaction-AI
cd Chess-Move-Reaction-AI
docker compose up --build
# Open http://localhost:3000
```

**Option B - Prebuilt images:**
```bash
git clone https://github.com/GeoffreyFClark/Chess-Move-Reaction-AI
cd Chess-Move-Reaction-AI
docker compose -f docker-compose.ghcr.yml up -d
# Open http://localhost:3000
```

### Docker Images
Images are published to GitHub Container Registry:
```bash
docker pull ghcr.io/geoffreyfclark/chess-move-reaction-ai-backend:latest
docker pull ghcr.io/geoffreyfclark/chess-move-reaction-ai-frontend:latest
```

## Manual Installation

**Prerequisites:** Python 3.10+, Node.js 18+

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install && npm run dev
# Open http://localhost:5173
```

### Stockfish Setup (Optional)
When Stockfish is available, the system uses engine evaluations to provide more accurate move assessments.

To download Stockfish for your platform, the official website is: https://stockfishchess.org/download/

| Platform | Binary Name | Alternate download method |
|----------|-------------|---------------------------|
| Windows | `stockfish.exe` | ---------------------- |
| macOS | `stockfish` | Homebrew: `brew install stockfish` |
| Linux | `stockfish` | Use your package manager |

Then do ONE of the following:
- Place the binary in the `backend/` folder (Ensure binary name matches above platform-specific binary name)
- Add it to your system PATH
- Set the `STOCKFISH_PATH` environment variable to the full path

**Docker users:** Stockfish 16.1 is automatically downloaded and configured for Docker users during the image build.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `STOCKFISH_PATH` | Auto-detect | Path to Stockfish binary |
| `STOCKFISH_DEPTH` | `18` | Engine max analysis depth |
| `STOCKFISH_MOVETIME_MS` | `500` | Max move analysis time |

## Development

```bash
cd backend
pytest -v                    # Run tests
ruff check . && black .      # Lint and format
```

## Alternative CLI Usage

```bash
cd backend
python cli.py --fen "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" --move "e4"
# Output: Move: e4 | Reaction: Good move. You increase control of the central squares.
```

## Project Structure

```
Chess-Move-Reaction-AI/
├── backend/
│   ├── app.py              # FastAPI REST API
│   ├── explain/            # Move explanation module
│   ├── features.py         # Chess feature extraction
│   ├── engine.py           # Stockfish UCI integration
│   ├── ml/                 # Machine learning module
│   └── tests/              # Test suite
├── frontend/
│   └── src/App.tsx         # React chess board UI
├── docker-compose.yml      # Build from source
└── docker-compose.ghcr.yml # Prebuilt images
```

## API

**POST /api/analyze**

```json
// Request
{"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "move": "e4"}

// Response
{
  "ok": true,
  "normalized_move": "e4",
  "reaction": "Good move. You increase control of the central squares.",
  "details": {
    "turn": "White",
    "is_capture": false,
    "is_check_move": false,
    "is_promotion": false,
    "material_before": 0,
    "material_after": 0,
    "material_delta": 0,
    "mobility_before": {"white": 20, "black": 20},
    "mobility_after": {"white": 29, "black": 20},
    "center_control_before": {"white": 2, "black": 2},
    "center_control_after": {"white": 4, "black": 2},
    "castling_rights_lost": {"white_can_castle_k_lost": false, "...": "..."},
    "pawn_structure_before": {"white": {"doubled": [], "isolated": [], "passed": []}, "...": "..."},
    "engine": {"enabled": true, "before": {"cp": 20}, "after": {"cp": 35}},
    "engine_summary": {"before_cp": 20, "after_cp": 35, "tone": "good"},
    "ml_prediction": {"prediction": "good", "confidence": 0.6, "method": "heuristic"}
  }
}
```