from pathlib import Path
import sys

from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from server import app


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
