"""API-level integration and adversarial tests for the clinical router."""

from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZipFile

import fitz
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(
    0,
    "/home/runner/work/ai-knowledge-extraction-toolkit/ai-knowledge-extraction-toolkit/"
    "implementation_layer/toolkit_demo_app",
)
for module_name in list(sys.modules):
    if module_name == "api" or module_name.startswith("api."):
        del sys.modules[module_name]

from api.routers import clinical  # noqa: E402


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(clinical.router, prefix="/clinical")
    return TestClient(app)


def test_clinical_api_rejects_wrong_format(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLINICAL_SQLITE_PATH", str(tmp_path / "clinical.sqlite3"))
    client = _client()

    response = client.post(
        "/clinical/extract",
        files={"file": ("bad.txt", b"not a guideline", "text/plain")},
        data={"parser_choice": "auto"},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_clinical_api_rejects_path_traversal():
    client = _client()

    response = client.get("/clinical/examples/../../etc/passwd")

    assert response.status_code == 404


def test_clinical_api_extracts_from_uploaded_zip_and_persists_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLINICAL_SQLITE_PATH", str(tmp_path / "clinical.sqlite3"))
    zip_path = tmp_path / "guideline.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "guideline.pptx",
            _minimal_pptx_bytes(
                "Medication Adherence",
                "Review PDC data before each call",
                "Call the pharmacy to review fill history",
            ),
        )
    client = _client()

    with zip_path.open("rb") as handle:
        response = client.post(
            "/clinical/extract",
            files={"file": ("guideline.zip", handle, "application/zip")},
            data={"parser_choice": "auto", "operationalize": "true"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_file"] == "guideline.pptx"
    assert payload["uploaded_file"] == "guideline.zip"
    assert payload["run_id"]
    assert payload["persistence"]["sqlite"] is True

    loaded = client.get(f"/clinical/runs/{payload['run_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["source_file"] == "guideline.pptx"


def test_clinical_api_empty_upload_returns_quality_report(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLINICAL_SQLITE_PATH", str(tmp_path / "clinical.sqlite3"))
    client = _client()
    document = fitz.open()
    document.new_page()
    blank_pdf = document.tobytes()
    document.close()

    response = client.post(
        "/clinical/extract",
        files={"file": ("blank.pdf", blank_pdf, "application/pdf")},
        data={"parser_choice": "pdf_text", "operationalize": "true"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["quality_report"]["accepted"] is False
    codes = {issue["code"] for issue in payload["quality_report"]["issues"]}
    assert "empty_parse" in codes or "no_actionable_items" in codes


def _minimal_pptx_bytes(*texts: str) -> bytes:
    import io

    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        text_xml = "".join(f"<a:t>{text}</a:t>" for text in texts)
        archive.writestr("ppt/slides/slide1.xml", f"<p:sld>{text_xml}</p:sld>")
    return output.getvalue()
