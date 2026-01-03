from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    fen: str = Field(..., description="FEN string of the current position")
    move: str = Field(..., description="Move in SAN or UCI (e.g., 'Nf3' or 'g1f3')")


class AnalyzeResponse(BaseModel):
    ok: bool
    normalized_move: str
    reaction: str
    details: dict
