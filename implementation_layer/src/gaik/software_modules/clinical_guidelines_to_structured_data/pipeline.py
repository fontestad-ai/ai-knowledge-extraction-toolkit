"""Traceable hypertension clinical guideline extraction pipeline.

This module composes existing GAIK building blocks into a domain-oriented workflow:

1. Parse official guideline/protocol source files into markdown/text.
2. Extract typed hypertension clinical knowledge with source-trace fields.
3. Optionally validate the extraction against rendered source page images with LLMJudge.

The module intentionally does not add new runtime dependencies. It relies on the parser,
extractor, and validator extras already exposed by the toolkit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from gaik.software_components.config import get_openai_config
from gaik.software_components.extractor import DataExtractor, ExtractionRequirements, FieldSpec

try:  # Optional dependency surface; each parser still raises its own actionable ImportError.
    from gaik.software_components.parsers import (
        DoclingParser,
        DocxParser,
        MultimodalParser,
        PyMuPDFParser,
        VisionParser,
        VisionPlusParser,
    )
except Exception:  # pragma: no cover - optional parser extras may be absent.
    DoclingParser = DocxParser = MultimodalParser = PyMuPDFParser = None  # type: ignore
    VisionParser = VisionPlusParser = None  # type: ignore

try:
    from gaik.software_components.validators.llm_judge import LLMJudge, ValidationRubric
    from gaik.software_components.validators.llm_judge.schema import ValidationResult
except Exception:  # pragma: no cover - optional validator extras may be absent.
    LLMJudge = ValidationRubric = ValidationResult = None  # type: ignore


SupportedParser = Literal[
    "auto",
    "multimodal",
    "vision_plus",
    "vision_parser",
    "docling",
    "pymupdf",
    "docx",
]


class ClinicalGuidelineSource(BaseModel):
    """Traceability fields required for every clinical knowledge item."""

    source_file: str = Field(description="Original source file name")
    page_number: int | None = Field(
        default=None, description="Page number in the original source, if known"
    )
    section_heading: str | None = Field(
        default=None, description="Heading or section from which the item was extracted"
    )
    source_quote: str = Field(
        description="Verbatim quote from the source supporting the extracted item"
    )
    parser_method: str | None = Field(
        default=None, description="Parser used to produce the text/markdown evidence"
    )


class BloodPressureThreshold(BaseModel):
    """Actionable blood-pressure threshold or category."""

    population: str = Field(description="Applicable patient population")
    context: str = Field(description="Clinical context, e.g. office, home, ambulatory")
    systolic_mm_hg: str | None = Field(default=None, description="Systolic threshold/range")
    diastolic_mm_hg: str | None = Field(default=None, description="Diastolic threshold/range")
    category: str = Field(description="Named category or decision label")
    action: str = Field(description="Recommended action triggered by this threshold")
    source: ClinicalGuidelineSource


class ClinicalRecommendation(BaseModel):
    """Clinical recommendation with evidence strength and traceability."""

    recommendation_id: str | None = Field(
        default=None, description="Stable identifier from the source, if present"
    )
    topic: str = Field(description="Clinical topic or decision area")
    recommendation: str = Field(description="Actionable recommendation text")
    population: str | None = Field(default=None, description="Applicable population")
    strength_of_recommendation: str | None = Field(
        default=None, description="Recommendation class/strength as stated"
    )
    quality_of_evidence: str | None = Field(
        default=None, description="Evidence level/grade as stated"
    )
    conditions: list[str] = Field(
        default_factory=list, description="Prerequisites, exceptions, or modifiers"
    )
    source: ClinicalGuidelineSource


class MedicationRecommendation(BaseModel):
    """Medication-related hypertension guidance."""

    drug_or_class: str = Field(description="Drug or medication class")
    indication: str = Field(description="When this medication/class is recommended")
    contraindications: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    monitoring_requirements: list[str] = Field(default_factory=list)
    source: ClinicalGuidelineSource


class FollowUpRecommendation(BaseModel):
    """Monitoring or follow-up interval guidance."""

    scenario: str = Field(description="Clinical scenario")
    interval: str = Field(description="Recommended follow-up interval")
    required_actions: list[str] = Field(default_factory=list)
    source: ClinicalGuidelineSource


class HypertensionClinicalKnowledge(BaseModel):
    """Structured, source-traceable hypertension guideline knowledge base."""

    guideline_title: str | None = Field(default=None)
    issuing_organization: str | None = Field(default=None)
    publication_year: int | None = Field(default=None)
    target_population: list[str] = Field(default_factory=list)
    bp_thresholds: list[BloodPressureThreshold] = Field(default_factory=list)
    diagnostic_criteria: list[ClinicalRecommendation] = Field(default_factory=list)
    treatment_recommendations: list[ClinicalRecommendation] = Field(default_factory=list)
    medication_recommendations: list[MedicationRecommendation] = Field(default_factory=list)
    lifestyle_recommendations: list[ClinicalRecommendation] = Field(default_factory=list)
    follow_up_recommendations: list[FollowUpRecommendation] = Field(default_factory=list)
    contraindications_and_safety: list[ClinicalRecommendation] = Field(default_factory=list)
    source_gaps_or_uncertainties: list[str] = Field(
        default_factory=list,
        description="Items the extractor could not resolve from the source without guessing",
    )


DEFAULT_HYPERTENSION_EXTRACTION_REQUIREMENTS = (
    "Extract only source-grounded, clinically actionable hypertension guideline knowledge. "
    "Capture diagnostic blood-pressure thresholds, staging/categories, treatment thresholds, "
    "lifestyle recommendations, medication recommendations, contraindications, follow-up "
    "intervals, target populations, recommendation strength, evidence grade, and exceptions. "
    "Every actionable item must include source_file, page_number when available, section_heading "
    "when available, and a verbatim source_quote. Never infer missing values; use null or an "
    "empty list and record uncertainty in source_gaps_or_uncertainties."
)


HYPERTENSION_REQUIREMENTS_MODEL = ExtractionRequirements(
    use_case_name="hypertension_clinical_guideline_knowledge_extraction",
    fields=[
        FieldSpec(
            field_name="guideline_title",
            field_type="str",
            description="Official title of the clinical guideline or protocol",
            required=False,
        ),
        FieldSpec(
            field_name="issuing_organization",
            field_type="str",
            description="Organization issuing the guideline",
            required=False,
        ),
        FieldSpec(
            field_name="publication_year",
            field_type="int",
            description="Publication or update year",
            required=False,
        ),
        FieldSpec(
            field_name="target_population",
            field_type="list[str]",
            description="Patient populations covered by the guideline",
            required=False,
        ),
        FieldSpec(
            field_name="bp_thresholds",
            field_type="list[dict]",
            description="Blood-pressure thresholds/categories with actions and source traces",
        ),
        FieldSpec(
            field_name="diagnostic_criteria",
            field_type="list[dict]",
            description="Diagnostic criteria with source traces",
            required=False,
        ),
        FieldSpec(
            field_name="treatment_recommendations",
            field_type="list[dict]",
            description="Treatment recommendations with source traces",
            required=False,
        ),
        FieldSpec(
            field_name="medication_recommendations",
            field_type="list[dict]",
            description="Medication guidance with source traces",
            required=False,
        ),
        FieldSpec(
            field_name="lifestyle_recommendations",
            field_type="list[dict]",
            description="Lifestyle recommendations with source traces",
            required=False,
        ),
        FieldSpec(
            field_name="follow_up_recommendations",
            field_type="list[dict]",
            description="Follow-up and monitoring intervals with source traces",
            required=False,
        ),
        FieldSpec(
            field_name="contraindications_and_safety",
            field_type="list[dict]",
            description="Contraindications, cautions, safety monitoring, and exceptions",
            required=False,
        ),
        FieldSpec(
            field_name="source_gaps_or_uncertainties",
            field_type="list[str]",
            description="Unresolved items or missing source evidence",
            required=False,
        ),
    ],
)


@dataclass
class ClinicalGuidelinePipelineResult:
    """Result of one clinical guideline extraction run."""

    parsed_documents: list[str]
    extracted_knowledge: list[dict[str, Any]]
    parser_choice: str
    validation: ValidationResult | None = None


class ClinicalGuidelineKnowledgeExtractor:
    """End-to-end extraction for traceable hypertension clinical guideline knowledge."""

    def __init__(
        self,
        *,
        api_config: dict | None = None,
        use_azure: bool = True,
        extraction_model: type[BaseModel] = HypertensionClinicalKnowledge,
        extraction_requirements: ExtractionRequirements = HYPERTENSION_REQUIREMENTS_MODEL,
        user_requirements: str = DEFAULT_HYPERTENSION_EXTRACTION_REQUIREMENTS,
    ) -> None:
        self.api_config = api_config or get_openai_config(use_azure=use_azure)
        self.extraction_model = extraction_model
        self.extraction_requirements = extraction_requirements
        self.user_requirements = user_requirements

    def run(
        self,
        *,
        file_path: str | Path,
        parser_choice: SupportedParser = "auto",
        parser_ctor: dict | None = None,
        parse_options: dict | None = None,
        extractor_ctor: dict | None = None,
        extract_options: dict | None = None,
        validate: bool = False,
        source_pages: list[bytes] | None = None,
        validation_rubric: Any | None = None,
        judge: Any | None = None,
    ) -> ClinicalGuidelinePipelineResult:
        """Parse, extract, and optionally validate guideline knowledge.

        Validation requires caller-provided ``source_pages`` as PNG bytes so the judge can
        ground extracted JSON against the original page images.
        """

        parser_ctor = parser_ctor or {}
        parse_options = parse_options or {}
        chosen_parser = self._select_parser_choice(file_path, parser_choice)
        parser = self._build_parser(chosen_parser, parser_ctor)
        parsed_documents = self._parse_document(chosen_parser, parser, file_path, parse_options)

        extractor_cfg = self.api_config.copy()
        extractor_ctor = extractor_ctor or {}
        model_override = extractor_ctor.get("model")
        if model_override:
            extractor_cfg["model"] = model_override

        data_extractor = DataExtractor(config=extractor_cfg, **extractor_ctor)
        extract_opts = {"save_json": False, "json_path": "clinical_guideline_knowledge.json"}
        if extract_options:
            extract_opts.update(extract_options)

        extracted_knowledge = data_extractor.extract(
            extraction_model=self.extraction_model,
            requirements=self.extraction_requirements,
            user_requirements=self.user_requirements,
            documents=parsed_documents,
            **extract_opts,
        )

        validation = None
        if validate:
            validation = self._validate_extraction(
                source_pages=source_pages,
                extracted=extracted_knowledge,
                rubric=validation_rubric,
                judge=judge,
            )

        return ClinicalGuidelinePipelineResult(
            parsed_documents=parsed_documents,
            extracted_knowledge=extracted_knowledge,
            parser_choice=chosen_parser,
            validation=validation,
        )

    def _select_parser_choice(self, file_path: str | Path, parser_choice: SupportedParser) -> str:
        if parser_choice != "auto":
            return parser_choice

        suffix = Path(file_path).suffix.lower()
        if suffix == ".pdf":
            return "multimodal"
        if suffix in {".ppt", ".pptx"}:
            return "docling"
        if suffix in {".doc", ".docx"}:
            return "docx"
        if suffix in {".png", ".jpg", ".jpeg"}:
            return "vision_parser"
        raise ValueError(
            f"Unsupported file type: {suffix}. Supported: .pdf, .ppt, .pptx, "
            ".doc, .docx, .png, .jpg, .jpeg"
        )

    def _build_parser(self, parser_choice: str, ctor: dict):
        if parser_choice == "multimodal":
            if MultimodalParser is None:
                raise ImportError("MultimodalParser is not available. Install parser extras.")
            return MultimodalParser(**ctor)
        if parser_choice == "vision_plus":
            if VisionPlusParser is None:
                raise ImportError("VisionPlusParser is not available. Install parser extras.")
            return VisionPlusParser(vision_config=self.api_config, **ctor)
        if parser_choice == "vision_parser":
            if VisionParser is None:
                raise ImportError("VisionParser is not available. Install parser extras.")
            return VisionParser(openai_config=self.api_config, **ctor)
        if parser_choice == "docling":
            if DoclingParser is None:
                raise ImportError("DoclingParser is not available. Install parser extras.")
            return DoclingParser(**ctor)
        if parser_choice == "pymupdf":
            if PyMuPDFParser is None:
                raise ImportError("PyMuPDFParser is not available. Install parser extras.")
            return PyMuPDFParser(**ctor)
        if parser_choice == "docx":
            if DocxParser is None:
                raise ImportError("DocxParser is not available. Install parser extras.")
            return DocxParser(**ctor)
        raise ValueError(f"Unsupported parser_choice: {parser_choice}")

    def _parse_document(
        self, parser_choice: str, parser: Any, file_path: str | Path, parse_options: dict
    ) -> list[str]:
        path = Path(file_path)
        if parser_choice == "multimodal":
            result = parser.parse(path, **parse_options)
            return [result.clean_markdown]
        if parser_choice == "vision_plus":
            result = parser.parse_document(str(path), **parse_options)
            return [self._coerce_parsed_output_to_text(result)]
        if parser_choice == "vision_parser":
            if path.suffix.lower() == ".pdf":
                pages = parser.convert_pdf(str(path), **parse_options)
                return pages if isinstance(pages, list) else [str(pages)]
            with open(path, "rb") as handle:
                image_bytes = handle.read()
            text = parser._parse_image(image_bytes, page=1, previous_context=None)
            return [text]
        if parser_choice == "docling":
            result = parser.parse_document(str(path), **parse_options)
            return [self._coerce_parsed_output_to_text(result)]
        if parser_choice == "pymupdf":
            return [parser.parse_pdf(str(path), **parse_options)]
        if parser_choice == "docx":
            result = parser.parse_document(str(path), **parse_options)
            return [self._coerce_parsed_output_to_text(result)]
        raise ValueError(f"Unsupported parser_choice: {parser_choice}")

    @staticmethod
    def _coerce_parsed_output_to_text(parsed: Any) -> str:
        if isinstance(parsed, str):
            return parsed
        if isinstance(parsed, dict):
            for key in ("parsed_markdown", "text_content", "clean_markdown", "raw_markdown"):
                value = parsed.get(key)
                if isinstance(value, str):
                    return value
            return str(parsed)
        return str(parsed)

    @staticmethod
    def _validate_extraction(
        *,
        source_pages: list[bytes] | None,
        extracted: list[dict[str, Any]],
        rubric: Any | None,
        judge: Any | None,
    ):
        if not source_pages:
            raise ValueError("source_pages must be provided when validate=True")
        if judge is None:
            if LLMJudge is None:
                raise ImportError("LLMJudge is not available. Install llm-judge extras.")
            judge = LLMJudge()
        if rubric is None:
            if ValidationRubric is None:
                raise ImportError("ValidationRubric is not available. Install llm-judge extras.")
            rubric = ValidationRubric(
                field_checks=[
                    "Every actionable clinical item must be supported by a verbatim source_quote.",
                    "Blood pressure thresholds must match the source exactly.",
                    "Medication indications, contraindications, and monitoring must not be inferred.",
                    "Recommendation strength and evidence grade must be null when absent.",
                ],
                item_level_checks=[
                    "Flag any item that cannot be traced back to the provided source pages.",
                    "Flag any clinical action that is broader than the source statement.",
                ],
                scoring_mode="likert_1_5",
            )
        return judge.validate(source_pages=source_pages, extracted=extracted, rubric=rubric)
