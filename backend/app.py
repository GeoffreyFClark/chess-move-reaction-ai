from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from explain import explain_move
from schemas import AnalyzeRequest, AnalyzeResponse
from settings import settings

app = FastAPI(title="Chess Move Reaction AI", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def api_analyze(req: AnalyzeRequest):
    try:
        out = explain_move(req.fen, req.move)
        return AnalyzeResponse(
            ok=True,
            normalized_move=out["normalized_move"],
            reaction=out["reaction"],
            details=out["details"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
