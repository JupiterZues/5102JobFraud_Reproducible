"""FastAPI server for the bilingual job-fraud review interface."""

from __future__ import annotations

import io
import ipaddress
import json
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd
from bs4 import BeautifulSoup
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


class URLRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2_000)


def validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="Only public http:// or https:// URLs are supported.",
        )
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as error:
        raise HTTPException(status_code=400, detail="Could not resolve URL host.") from error

    for address in addresses:
        host = address[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            continue
        if not ip.is_global:
            raise HTTPException(
                status_code=400,
                detail="Private, local, and reserved network addresses are blocked.",
            )
    return parsed.geturl()


async def fetch_public_page(url: str) -> tuple[str, str]:
    current_url = validate_public_url(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; JobGuardDemo/1.0; "
            "+https://github.com/JupiterZues/5102JobFraud_Reproducible)"
        )
    }
    timeout = httpx.Timeout(12.0, connect=6.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(4):
            async with client.stream("GET", current_url, headers=headers) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise HTTPException(
                            status_code=400,
                            detail="The page redirected without a destination.",
                        )
                    current_url = validate_public_url(urljoin(current_url, location))
                    continue
                if response.status_code >= 400:
                    raise HTTPException(
                        status_code=400,
                        detail=f"The job page returned HTTP {response.status_code}.",
                    )

                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower():
                    raise HTTPException(
                        status_code=400,
                        detail="The URL did not return an HTML page.",
                    )

                chunks = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > 2_000_000:
                        raise HTTPException(
                            status_code=413,
                            detail="The fetched page exceeds 2 MB.",
                        )
                    chunks.append(chunk)
                return current_url, b"".join(chunks).decode(
                    response.encoding or "utf-8",
                    errors="replace",
                )

    raise HTTPException(status_code=400, detail="Too many redirects.")


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
        "review_flag": (
            "priority_review"
            if score >= float(detector.thresholds["top_5pct"])
            else "no_priority_flag"
        ),
        "thresholds": detector.thresholds,
    }


@app.post("/api/fetch-url")
async def fetch_url(payload: URLRequest) -> dict:
    final_url, page = await fetch_public_page(payload.url)
    soup = BeautifulSoup(page, "lxml")

    for tag in soup(
        ["script", "style", "noscript", "nav", "footer", "form", "svg"]
    ):
        tag.decompose()

    title = ""
    if soup.title:
        title = " ".join(soup.title.get_text(" ", strip=True).split())
    meta_description = soup.find(
        "meta",
        attrs={"name": lambda value: value and value.lower() == "description"},
    )
    company_meta = soup.find(
        "meta",
        attrs={"property": "og:site_name"},
    )

    root = soup.find("main") or soup.find("article") or soup.body or soup
    page_text = " ".join(root.get_text(" ", strip=True).split())
    if len(page_text) < 40:
        raise HTTPException(
            status_code=400,
            detail="The page did not expose enough readable text.",
        )

    return {
        "final_url": final_url,
        "title": title[:300],
        "company_profile": (
            company_meta.get("content", "")[:500]
            if company_meta
            else ""
        ),
        "description": page_text[:20_000],
        "meta_description": (
            meta_description.get("content", "")[:2_000]
            if meta_description
            else ""
        ),
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
