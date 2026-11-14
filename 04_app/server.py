"""FastAPI server for the bilingual job-fraud review interface."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fraud_detector import FraudDetector


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
MAX_UPLOAD_BYTES = 10_000_000
MAX_BATCH_ROWS = 5_000

app = FastAPI(
    title="Job Fraud Review Assistant",
    description="Human-in-the-loop triage demo for fraudulent job postings.",
    version="1.0.0",
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

detector = FraudDetector()

PRIORITY_CODES = {
    "High - top 5%": "high",
    "Medium - top 10%": "medium",
    "Low - top 20%": "low",
    "Routine review": "routine",
}


class PredictionRequest(BaseModel):
    title: str = ""
    company_profile: str = ""
    description: str = Field(default="", max_length=50_000)
    requirements: str = Field(default="", max_length=50_000)
    benefits: str = Field(default="", max_length=50_000)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> PlainTextResponse:
    return PlainTextResponse("", status_code=204)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta")
async def metadata() -> dict:
    return {
        "model": "Linear SVM",
        "parameter": "C=1.0",
        "validation_pr_auc": 0.895951,
        "test_pr_auc": 0.946594,
        "test_recall_at_5pct": 0.886792,
        "thresholds": detector.thresholds,
        "score_range": {"min": -2.3, "max": 1.5},
    }


@app.post("/api/predict")
async def predict(payload: PredictionRequest) -> dict:
    try:
        score, priority = detector.score_record(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "score": score,
        "priority": PRIORITY_CODES[priority],
        "thresholds": detector.thresholds,
    }


@app.post("/api/batch")
async def batch(request: Request) -> JSONResponse:
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Empty CSV file.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV exceeds 10 MB.")

    try:
        text = content.decode("utf-8-sig")
        frame = pd.read_csv(io.StringIO(text))
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse CSV: {error}",
        ) from error

    if frame.empty:
        raise HTTPException(status_code=400, detail="The CSV contains no rows.")
    if len(frame) > MAX_BATCH_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"The CSV exceeds {MAX_BATCH_ROWS:,} rows.",
        )

    try:
        result = detector.score_frame(frame)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    result["priority_code"] = result["priority"].map(PRIORITY_CODES)
    rows = json.loads(result.to_json(orient="records", force_ascii=False))
    return JSONResponse(
        {
            "columns": result.columns.tolist(),
            "rows": rows,
            "count": len(rows),
        }
    )


@app.get("/api/sample.csv", include_in_schema=False)
async def sample_csv() -> FileResponse:
    return FileResponse(
        APP_DIR / "sample_jobs.csv",
        media_type="text/csv",
        filename="sample_jobs.csv",
    )
