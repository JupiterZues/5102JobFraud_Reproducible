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
from bs4.element import Tag
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
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

JOB_PAGE_MARKERS = [
    "job description",
    "responsibilities",
    "requirements",
    "qualifications",
    "experience",
    "salary",
    "apply",
    "hiring",
    "岗位职责",
    "职位描述",
    "工作职责",
    "任职要求",
    "岗位要求",
    "工作经验",
    "学历",
    "薪资",
    "福利",
    "招聘",
]

KNOWN_JOB_SITES = [
    "boss直聘",
    "zhipin",
    "linkedin",
    "indeed",
    "glassdoor",
    "51job",
    "前程无忧",
    "智联招聘",
    "monster",
]


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


def text_content(value) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or ""
    if isinstance(value, list):
        return "; ".join(filter(None, (text_content(item) for item in value)))
    if not isinstance(value, str):
        return ""
    return " ".join(BeautifulSoup(value, "lxml").get_text(" ", strip=True).split())


def iter_json_nodes(value):
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if graph:
            yield from iter_json_nodes(graph)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_nodes(item)


def find_job_json_ld(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in iter_json_nodes(data):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if any(str(item).lower() == "jobposting" for item in types):
                return node
    return {}


def clean_page_title(title: str, site_name: str) -> str:
    title = " ".join(title.split()).strip()
    site_lower = site_name.casefold().strip()
    for separator in [" | ", " - ", " — ", " – ", " _ "]:
        if separator not in title:
            continue
        parts = title.rsplit(separator, 1)
        suffix = parts[-1].casefold().strip()
        if suffix == site_lower or any(site in suffix for site in KNOWN_JOB_SITES):
            title = parts[0].strip()
            break
    if site_lower and title.casefold().strip() == site_lower:
        return ""
    return title


def extract_job_posting(page: str) -> dict:
    soup = BeautifulSoup(page, "lxml")
    json_ld = find_job_json_ld(soup)
    for tag in soup(
        ["script", "style", "noscript", "nav", "footer", "form", "svg", "aside"]
    ):
        tag.decompose()

    site_meta = soup.find("meta", attrs={"property": "og:site_name"})
    site_name = site_meta.get("content", "") if isinstance(site_meta, Tag) else ""

    title = text_content(json_ld.get("title") or json_ld.get("name"))
    company_profile = text_content(json_ld.get("hiringOrganization"))
    job_description = text_content(json_ld.get("description"))
    requirements = "; ".join(
        filter(
            None,
            [
                text_content(json_ld.get("qualifications")),
                text_content(json_ld.get("experienceRequirements")),
                text_content(json_ld.get("educationRequirements")),
                text_content(json_ld.get("skills")),
            ],
        )
    )
    benefits = text_content(json_ld.get("jobBenefits"))
    source = "jsonld" if json_ld else "html"

    if not title:
        for heading in soup.find_all(["h1", "h2"]):
            candidate = " ".join(heading.get_text(" ", strip=True).split())
            candidate = clean_page_title(candidate, site_name)
            if 3 <= len(candidate) <= 220:
                title = candidate
                break

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if not title and isinstance(og_title, Tag):
        title = clean_page_title(og_title.get("content", ""), site_name)
    if not title and soup.title:
        title = clean_page_title(soup.title.get_text(" ", strip=True), site_name)
    title = clean_page_title(title, site_name)

    root = soup.find("main") or soup.find("article") or soup.body or soup
    page_text = " ".join(root.get_text(" ", strip=True).split())
    description = job_description or page_text

    minimum_description = 20 if source == "jsonld" else 250
    if not title or len(description) < minimum_description:
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not identify a reliable job-detail page. "
                "Paste the job text directly instead."
            ),
        )

    combined = f"{title} {description}".casefold()
    marker_count = sum(marker.casefold() in combined for marker in JOB_PAGE_MARKERS)
    if source == "html" and marker_count < 2:
        raise HTTPException(
            status_code=422,
            detail=(
                "The page does not look like a job-detail post. "
                "Paste the job text directly instead."
            ),
        )

    return {
        "title": title[:300],
        "company_profile": company_profile[:500],
        "description": description[:20_000],
        "requirements": requirements[:8_000],
        "benefits": benefits[:4_000],
        "quality": "high" if source == "jsonld" else "medium",
        "source": source,
        "warning": (
            ""
            if source == "jsonld"
            else "The page was extracted from general HTML. Verify the title and text before assessment."
        ),
    }


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css_text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    js_text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html_text = html_text.replace(
        '<link rel="stylesheet" href="/assets/styles.css">',
        f"<style>\n{css_text}\n</style>",
    )
    html_text = html_text.replace(
        '<script src="/assets/app.js"></script>',
        f"<script>\n{js_text}\n</script>",
    )
    return HTMLResponse(
        html_text,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


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
    result = extract_job_posting(page)
    result["final_url"] = final_url
    return result


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
