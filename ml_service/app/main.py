"""GPT-OSS-compatible model microservice."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from app.config import settings
from app.predictor import ModelRunnerError, predictor
from app.schemas import PredictionRequest, PredictionResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load model resources on startup and clean them up on shutdown."""
    logger.info(
        "ML Service starting with predictor mode=%s model=%s",
        predictor.mode,
        predictor.model_name,
    )
    yield
    logger.info("ML Service shutting down")


app = FastAPI(
    title="Zarabotok GPT-OSS Model Service",
    description="GPT-OSS-compatible salary analysis microservice",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Legacy prediction endpoint kept for old local scripts."""
    return predictor.predict(request)


@app.post("/analyze")
async def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    """GPT-OSS-compatible endpoint used by backend as the single model call."""
    try:
        return await predictor.analyze(payload)
    except ModelRunnerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "zarabotok-ml",
        "mode": predictor.mode,
        "model": predictor.model_name,
        "api_style": settings.openai_api_style,
        "base_url": settings.openai_base_url,
        "timeout_seconds": settings.openai_timeout,
    }
