# Chess Move Reaction AI
Chess engines give raw scores and best lines, but not explanations, reasons, or reactions. Many chess players would appreciate AI that feels like a coach or informed spectator: it evaluates a move and reacts with both logic and tone (“Great tactic! That move creates immediate pressure and improves your material situation.” or “Prudent choice — this improves your position and reduces risk.” or “Careful — that square is dangerous; your piece may be in danger.”). Beyond the scope of this project, the concept could be expanded into customized spectator/companion bots, i.e. famous players or commentators.

## Prereqs
- Node.js
- Python 3
- (Later) Stockfish binary

## Run Python venv and install requirements
```bash
cd backend

python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Run backend
```bash
uvicorn app:app --reload --port 8000
```