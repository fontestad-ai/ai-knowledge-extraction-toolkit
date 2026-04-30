"""Regression tests against user-provided clinical assets in uploads/."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from gaik.software_modules.clinical_guidelines_to_structured_data import (
    ClinicalGuidelineKnowledgeExtractor,
    LMCLIClinicalExtractor,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOADS = REPO_ROOT / "uploads"


def _extractor() -> ClinicalGuidelineKnowledgeExtractor:
    return ClinicalGuidelineKnowledgeExtractor(
        lmcli_extractor=LMCLIClinicalExtractor(command="definitely-not-installed-lmcli")
    )


def test_uploaded_hypertension_image_extracts_medication_adherence():
    image = (
        UPLOADS
        / "Digital Medicine HTN Best Practice Guidelines 2025_V2_old - Copy(1)_page_5.jpeg"
    )

    result = _extractor().run(file_path=image, parser_choice="auto")

    assert result.parser_choice == "local_image"
    assert result.extraction_backend == "local_deterministic"
    assert "Medication Adherence" in result.parsed_documents[0]
    recommendations = result.extracted_knowledge[0]["treatment_recommendations"]
    assert any("PDC" in item["recommendation"] for item in recommendations)


def test_uploaded_powerpoint_extracts_local_slide_text_and_recommendations():
    pptx = UPLOADS / "Digital Medicine HTN Best Practice Guidelines 2025_V2_old - Copy.pptx"

    result = _extractor().run(file_path=pptx, parser_choice="auto")

    assert result.parser_choice == "pptx_text"
    assert "Treatment Naïve" in result.parsed_documents[0]
    assert result.extracted_knowledge[0]["medication_recommendations"]


def test_uploaded_zip_guideline_pdf_is_parseable_without_external_calls(tmp_path: Path):
    archive_path = (
        UPLOADS
        / (
            "2025 Guideline for the Prevention, Detection,?Evaluation and Management "
            "of High Blood?Pressure in Adults Compressed.zip"
        )
    )
    with ZipFile(archive_path) as archive:
        pdf_members = [
            member for member in archive.namelist() if member.lower().endswith(".pdf")
        ]
        assert pdf_members
        archive.extract(pdf_members[0], tmp_path)
    pdf_path = tmp_path / pdf_members[0]

    result = _extractor().run(file_path=pdf_path, parser_choice="auto")

    assert result.parser_choice == "pymupdf"
    assert "2025 High Blood Pressure Guideline" in result.parsed_documents[0]
    assert result.extracted_knowledge[0]["guideline_title"] == "2025 High Blood Pressure Guideline"
