"""Robustness tests for LMCLI/local clinical extraction and SQLite persistence."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from gaik.software_modules.clinical_guidelines_to_structured_data import (
    ClinicalGuidelineKnowledgeExtractor,
    ClinicalSQLiteStore,
    LMCLIClinicalExtractor,
)
from gaik.software_modules.clinical_guidelines_to_structured_data.contracts import (
    build_contract_prompt_context,
    list_clinical_contract_resources,
    list_missing_pending_chat_backlog_artifacts,
    list_pending_chat_backlog_artifacts,
)
from gaik.software_modules.clinical_guidelines_to_structured_data.pipeline import (
    HYPERTENSION_REQUIREMENTS_MODEL,
    HypertensionClinicalKnowledge,
)
from gaik.software_modules.clinical_guidelines_to_structured_data.prompts import (
    build_clinical_lmcli_prompt,
)


def test_lmcli_extractor_uses_cli_when_available(tmp_path: Path):
    script = tmp_path / "lmcli_stub.py"
    payload = {
        "records": [
            {
                "guideline_title": "Medication Adherence",
                "target_population": ["patients"],
                "treatment_recommendations": [
                    {
                        "recommendation_id": "med-1",
                        "topic": "Medication adherence",
                        "recommendation": "Review PDC data before each call.",
                        "population": "patients",
                        "strength_of_recommendation": None,
                        "quality_of_evidence": None,
                        "conditions": [],
                        "source": {
                            "source_file": "upload.jpeg",
                            "page_number": None,
                            "section_heading": "Medication Adherence",
                            "source_quote": "Review PDC data before each call.",
                        },
                    }
                ],
            }
        ]
    }
    script.write_text(
        "import json, sys\n"
        "_ = sys.stdin.read()\n"
        f"print({json.dumps(json.dumps(payload))})\n",
        encoding="utf-8",
    )

    extractor = LMCLIClinicalExtractor(
        command=f"{sys.executable} {script}",
        allow_deterministic_fallback=False,
    )
    outcome = extractor.extract(
        extraction_model=HypertensionClinicalKnowledge,
        requirements=HYPERTENSION_REQUIREMENTS_MODEL,
        user_requirements="Extract medication adherence.",
        documents=["Medication Adherence. Review PDC data before each call."],
        source_document_id="upload.jpeg",
    )

    assert outcome.quality_report.backend == "lmcli"
    assert outcome.records[0]["guideline_title"] == "Medication Adherence"


def test_lmcli_prompt_reuses_existing_parser_and_judge_prompt_resources():
    prompt = build_clinical_lmcli_prompt(
        extraction_model=HypertensionClinicalKnowledge,
        requirements=HYPERTENSION_REQUIREMENTS_MODEL,
        user_requirements="Extract clinical guidance.",
        documents=["Medication Adherence. Review PDC data before each call."],
        source_document_id="upload.jpeg",
    )

    assert "Preserve the document structure" in prompt
    assert "data-bbox" in prompt
    assert "Likert score" in prompt
    assert "Clinical extraction policy" in prompt
    assert "Return ONLY valid JSON" in prompt
    assert "flow-hbp-2025-build" in prompt
    assert "recommendation-record-htn" in prompt


def test_chat_session_contract_resources_are_packaged_and_loadable():
    resources = list_clinical_contract_resources()
    paths = {resource.relative_path for resource in resources}
    context = build_contract_prompt_context()

    assert "v2_skills/flow-hbp-2025-build/SKILL.md" in paths
    assert "v2_schemas/pharm-rule-htn.yaml" in paths
    assert "v1_schemas/recommendation-record-htn.yaml" in paths
    assert "SME" in context or "sme" in context.lower()
    assert "PlanDefinition" in context or "recommendation" in context.lower()


def test_late_chat_backlog_artifacts_are_fully_materialized():
    pending_paths = set(list_pending_chat_backlog_artifacts())
    resource_map = {
        resource.relative_path: resource for resource in list_clinical_contract_resources()
    }

    assert len(pending_paths) == 51
    assert list_missing_pending_chat_backlog_artifacts() == ()
    for path in pending_paths:
        assert path in resource_map
        assert len(resource_map[path].text.strip()) > 500


def test_expanded_contract_prompt_context_includes_governance_and_test_artifacts():
    context = build_contract_prompt_context(max_chars=40_000)

    assert "ADR-HTN-001" in context
    assert "FHIR R5 JSON Canonicalization" in context
    assert "LLM Family Matrix" in context
    assert "terminology" in context.lower()
    assert "Synthea" in context


def test_lmcli_missing_without_fallback_raises():
    extractor = LMCLIClinicalExtractor(
        command="definitely-not-installed-lmcli",
        allow_deterministic_fallback=False,
    )

    with pytest.raises(FileNotFoundError):
        extractor.extract(
            extraction_model=HypertensionClinicalKnowledge,
            requirements=HYPERTENSION_REQUIREMENTS_MODEL,
            user_requirements="Extract.",
            documents=["Medication Adherence"],
            source_document_id="upload.jpeg",
        )


def test_deterministic_medication_adherence_fallback_extracts_chat_artifact():
    extractor = LMCLIClinicalExtractor(command="definitely-not-installed-lmcli")

    outcome = extractor.extract(
        extraction_model=HypertensionClinicalKnowledge,
        requirements=HYPERTENSION_REQUIREMENTS_MODEL,
        user_requirements="Extract.",
        documents=[
            "Medication Adherence. Review PDC data before each call. "
            "If concerns are identified, discuss concerns with the patient."
        ],
        source_document_id="medication.jpeg",
    )

    recommendations = outcome.records[0]["treatment_recommendations"]
    assert outcome.quality_report.backend == "local_deterministic"
    assert any("PDC" in item["recommendation"] for item in recommendations)


def test_deterministic_hyperkalemia_extracts_safety_and_follow_up():
    extractor = LMCLIClinicalExtractor(command="definitely-not-installed-lmcli")

    outcome = extractor.extract(
        extraction_model=HypertensionClinicalKnowledge,
        requirements=HYPERTENSION_REQUIREMENTS_MODEL,
        user_requirements="Extract.",
        documents=[
            "Hyperkalemia management. K > 5.1. If K >= 6.0 send to ED. "
            "If volume depletion is absent, add furosemide 20 mg daily for 3 days. "
            "Recheck potassium within 1 week."
        ],
        source_document_id="hyperkalemia.jpeg",
    )

    record = outcome.records[0]
    assert record["follow_up_recommendations"][0]["interval"] == "within 1 week"
    assert record["contraindications_and_safety"]


def test_empty_parse_quality_control_blocks_acceptance():
    extractor = LMCLIClinicalExtractor(command="definitely-not-installed-lmcli")

    outcome = extractor.extract(
        extraction_model=HypertensionClinicalKnowledge,
        requirements=HYPERTENSION_REQUIREMENTS_MODEL,
        user_requirements="Extract.",
        documents=[""],
        source_document_id="blank.pdf",
    )

    assert outcome.quality_report.accepted is False
    codes = {issue.code for issue in outcome.quality_report.issues}
    assert "empty_parse" in codes
    assert "no_actionable_items" in codes


def test_pipeline_uses_local_image_artifact_registry():
    extractor = ClinicalGuidelineKnowledgeExtractor(
        lmcli_extractor=LMCLIClinicalExtractor(command="definitely-not-installed-lmcli")
    )

    parsed = extractor._parse_document(
        "local_image",
        None,
        "Digital Medicine HTN Best Practice Guidelines 2025_V2_old - Copy(1)_page_5.jpeg",
        {},
    )

    assert "Medication Adherence" in parsed[0]
    assert "Review PDC data" in parsed[0]


def test_pipeline_extracts_text_from_pptx_locally(tmp_path: Path):
    pptx = tmp_path / "guideline.pptx"
    with ZipFile(pptx, "w") as archive:
        archive.writestr(
            "ppt/slides/slide1.xml",
            (
                "<p:sld><a:t>Medication Adherence</a:t>"
                "<a:t>Review PDC data before each call</a:t></p:sld>"
            ),
        )

    text = ClinicalGuidelineKnowledgeExtractor._parse_pptx_text(pptx)

    assert "Slide 1" in text
    assert "Medication Adherence" in text
    assert "Review PDC data" in text


def test_pipeline_runs_end_to_end_without_openai_or_azure(tmp_path: Path):
    pptx = tmp_path / "guideline.pptx"
    with ZipFile(pptx, "w") as archive:
        archive.writestr(
            "ppt/slides/slide1.xml",
            (
                "<p:sld><a:t>Medication Adherence</a:t>"
                "<a:t>Review PDC data before each call</a:t>"
                "<a:t>Call the pharmacy to review fill history</a:t></p:sld>"
            ),
        )
    extractor = ClinicalGuidelineKnowledgeExtractor(
        lmcli_extractor=LMCLIClinicalExtractor(command="definitely-not-installed-lmcli")
    )

    result = extractor.run(file_path=pptx, parser_choice="auto")

    assert result.parser_choice == "pptx_text"
    assert result.extraction_backend == "local_deterministic"
    assert result.extracted_knowledge[0]["treatment_recommendations"]
    assert result.operationalized_knowledge is not None
    assert result.quality_report is not None


def test_sqlite_store_persists_run_and_operationalized_units(tmp_path: Path):
    db_path = tmp_path / "clinical.sqlite3"
    store = ClinicalSQLiteStore(db_path)
    extractor = ClinicalGuidelineKnowledgeExtractor(
        lmcli_extractor=LMCLIClinicalExtractor(command="definitely-not-installed-lmcli")
    )
    image_name = "Digital Medicine HTN Best Practice Guidelines 2025_V2_old - Copy(1)_page_5.jpeg"
    result = extractor.run(file_path=Path(image_name), parser_choice="local_image")

    run_id = store.save_run(
        source_file="upload.jpeg",
        parser_choice=result.parser_choice,
        extraction_backend=result.extraction_backend,
        parsed_documents=result.parsed_documents,
        extracted_knowledge=result.extracted_knowledge,
        operationalized_knowledge=result.operationalized_knowledge,
        validation=result.validation,
        quality_report=result.quality_report,
    )

    runs = store.list_runs()
    loaded = store.get_run(run_id)
    assert runs[0]["id"] == run_id
    assert loaded is not None
    assert loaded["extracted_knowledge"][0]["treatment_recommendations"]
