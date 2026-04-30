"""Tests for the clinical guideline extraction pipeline."""

from pathlib import Path

from gaik.software_modules.clinical_guidelines_to_structured_data import (
    AtomicClinicalKnowledgeUnit,
    ClinicalGuidelineKnowledgeExtractor,
    ClinicalOperationalizationBundle,
    HypertensionClinicalKnowledge,
    get_cli_model_access_targets,
    get_knowledge_extraction_llm_usage_map,
)


def test_module_import_and_schema_shape():
    assert HypertensionClinicalKnowledge.model_fields["bp_thresholds"] is not None
    assert HypertensionClinicalKnowledge.model_fields["treatment_recommendations"] is not None


def test_auto_parser_selection_by_extension():
    extractor = ClinicalGuidelineKnowledgeExtractor(api_config={"model": "test", "api_key": "x"})

    assert extractor._select_parser_choice("guideline.pdf", "auto") == "multimodal"
    assert extractor._select_parser_choice("protocol.pptx", "auto") == "docling"
    assert extractor._select_parser_choice("protocol.docx", "auto") == "docx"
    assert extractor._select_parser_choice("scan.jpeg", "auto") == "vision_parser"


def test_coerce_parsed_output_prefers_known_text_fields():
    extractor = ClinicalGuidelineKnowledgeExtractor(api_config={"model": "test", "api_key": "x"})

    assert (
        extractor._coerce_parsed_output_to_text({"parsed_markdown": "# Guideline"})
        == "# Guideline"
    )
    assert extractor._coerce_parsed_output_to_text({"text_content": "body"}) == "body"
    assert extractor._coerce_parsed_output_to_text("plain") == "plain"


def test_unsupported_extension_raises_clear_error():
    extractor = ClinicalGuidelineKnowledgeExtractor(api_config={"model": "test", "api_key": "x"})

    try:
        extractor._select_parser_choice(Path("guideline.csv"), "auto")
    except ValueError as exc:
        assert ".pdf" in str(exc)
        assert ".jpeg" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported extension")


def test_llm_leverage_map_identifies_core_stages_and_cli_targets():
    stages = {item.stage for item in get_knowledge_extraction_llm_usage_map()}
    cli_targets = {item.provider_key for item in get_cli_model_access_targets()}

    assert "parsing" in stages
    assert "structured_extraction" in stages
    assert "validation" in stages
    assert "claude_code_cli" in cli_targets
    assert "snowflake_cortex_cli" in cli_targets


def test_adaptive_route_prefers_local_first_with_multimodal_fallback():
    extractor = ClinicalGuidelineKnowledgeExtractor(api_config={"model": "test", "api_key": "x"})

    route = extractor._plan_adaptive_route("guideline.pdf", "auto")

    assert route.selected_parser == "pymupdf"
    assert route.candidate_parsers == ["pymupdf", "docling", "multimodal"]
    assert "multimodal" in route.fallback_parsers


def test_operationalization_builds_atomic_units_and_downstream_projections():
    extractor = ClinicalGuidelineKnowledgeExtractor(api_config={"model": "test", "api_key": "x"})
    extracted = [
        {
            "bp_thresholds": [
                {
                    "population": "adults with office readings",
                    "context": "office",
                    "systolic_mm_hg": "140",
                    "diastolic_mm_hg": "90",
                    "category": "stage 2 hypertension",
                    "action": "start antihypertensive treatment",
                    "source": {
                        "source_file": "guideline.pdf",
                        "page_number": 12,
                        "section_heading": "Diagnosis",
                        "source_quote": "Start treatment when BP is 140/90 mmHg or above.",
                    },
                }
            ],
            "medication_recommendations": [
                {
                    "drug_or_class": "ACE inhibitor",
                    "indication": "first-line treatment in adults with diabetes",
                    "contraindications": ["pregnancy"],
                    "monitoring_requirements": ["check creatinine within 2 weeks"],
                    "source": {
                        "source_file": "guideline.pdf",
                        "page_number": 18,
                        "section_heading": "Drug therapy",
                        "source_quote": "ACE inhibitors are first-line in diabetes.",
                    },
                }
            ],
        }
    ]

    bundle = extractor.operationalize_extracted_knowledge(
        extracted,
        source_document_id="hypertension-guideline",
        source_document_version="2026-04",
    )

    assert isinstance(bundle, ClinicalOperationalizationBundle)
    assert len(bundle.atomic_units) == 2
    assert all(isinstance(unit, AtomicClinicalKnowledgeUnit) for unit in bundle.atomic_units)
    assert len(bundle.structured_records) == 2
    assert len(bundle.embedding_units) == 2
    assert len(bundle.rag_documents) == 2
    assert any(edge.relation_type == "supported_by" for edge in bundle.knowledge_graph.edges)
