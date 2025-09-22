from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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