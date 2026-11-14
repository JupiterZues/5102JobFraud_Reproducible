from pathlib import Path
import sys

from fastapi.testclient import TestClient
from fastapi import HTTPException
import pytest


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from server import app, extract_job_posting


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_single_prediction() -> None:
    response = client.post(
        "/api/predict",
        json={
            "title": "Data Entry Clerk",
            "description": "Apply using below link. No experience necessary.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["score"], float)
    assert data["priority"] in {"high", "medium", "low", "routine"}


def test_batch_prediction() -> None:
    csv_text = (
        "job_id,title,description\n"
        "1,Data Entry Clerk,Apply using below link\n"
        "2,Data Analyst,Maintain reporting pipelines with Python and SQL\n"
    )
    response = client.post(
        "/api/batch",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["rows"][0]["review_rank"] == 1


def test_private_url_is_blocked() -> None:
    response = client.post(
        "/api/fetch-url",
        json={"url": "http://127.0.0.1:8501/"},
    )
    assert response.status_code == 400


def test_jobposting_json_ld_title_is_not_site_name() -> None:
    page = """
    <html>
      <head>
        <meta property="og:site_name" content="BOSS直聘">
        <title>Data Entry Clerk | BOSS直聘</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Data Entry Clerk",
          "description": "<p>Enter records and maintain spreadsheets.</p>",
          "hiringOrganization": {"@type": "Organization", "name": "Acme Ltd"},
          "qualifications": "Attention to detail"
        }
        </script>
      </head>
      <body><h1>BOSS直聘</h1></body>
    </html>
    """
    result = extract_job_posting(page)
    assert result["title"] == "Data Entry Clerk"
    assert result["company_profile"] == "Acme Ltd"
    assert result["source"] == "jsonld"
    assert result["quality"] == "high"


def test_non_job_page_is_rejected() -> None:
    page = """
    <html>
      <head><title>Example Domain</title></head>
      <body><h1>Example Domain</h1><p>This is a documentation example.</p></body>
    </html>
    """
    with pytest.raises(HTTPException) as error:
        extract_job_posting(page)
    assert error.value.status_code == 422
