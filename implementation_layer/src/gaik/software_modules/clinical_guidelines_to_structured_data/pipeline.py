"""Traceable hypertension clinical guideline extraction pipeline.

This module composes existing GAIK building blocks into a domain-oriented workflow:

1. Parse official guideline/protocol source files into markdown/text.
2. Extract typed hypertension clinical knowledge with source-trace fields.
3. Optionally validate the extraction against rendered source page images with LLMJudge.

The module intentionally does not add new runtime dependencies. It relies on the parser,
extractor, and validator extras already exposed by the toolkit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

ExtractionComplexity = Literal["low", "medium", "high"]
KnowledgeSemanticType = Literal[
    "recommendation",
    "threshold",
    "decision_condition",
    "intervention",
    "medication",
    "contraindication",
    "monitoring_action",
    "evidence_statement",
]
KnowledgeRelationType = Literal[
    "applies_to",
    "recommends",
    "contraindicated_for",
    "requires_monitoring",
    "supported_by",
    "supersedes",
    "depends_on",
    "triggers",
    "excludes",
]
ExtractionStatus = Literal["grounded", "needs_review", "uncertain"]


@dataclass
class AdaptiveExtractionRoute:
    """Local-first parser routing plan with fallbacks for escalation."""

    complexity: ExtractionComplexity
    selected_parser: str
    candidate_parsers: list[str]
    fallback_parsers: list[str] = field(default_factory=list)
    escalation_reason: str | None = None
    attempted_parsers: list[str] = field(default_factory=list)
    parser_errors: dict[str, str] = field(default_factory=dict)


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


class KnowledgeRelationship(BaseModel):
    """Traceable relation from one atomic unit to another label or unit."""

    relation_type: KnowledgeRelationType
    target_label: str = Field(description="Human-readable target of the relation")
    target_unit_id: str | None = Field(
        default=None, description="Canonical target unit id when known"
    )


class DownstreamEligibility(BaseModel):
    """Whether a unit is safe to project into downstream representations."""

    structured_data: bool = True
    embeddings: bool = True
    knowledge_graph: bool = True
    rag: bool = True
    blocked_reason: str | None = None


class AtomicClinicalKnowledgeUnit(BaseModel):
    """Canonical, source-grounded knowledge unit for downstream operationalization."""

    unit_id: str
    semantic_type: KnowledgeSemanticType
    title: str
    normalized_statement: str
    source_quote: str
    source: ClinicalGuidelineSource
    source_document_id: str
    source_document_version: str | None = None
    certainty: str | None = None
    extraction_status: ExtractionStatus = "grounded"
    relationships: list[KnowledgeRelationship] = Field(default_factory=list)
    downstream_eligibility: DownstreamEligibility = Field(
        default_factory=DownstreamEligibility
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuredKnowledgeRecord(BaseModel):
    """Database-ready record derived from one atomic knowledge unit."""

    record_id: str
    record_type: str
    unit_id: str
    normalized_statement: str
    source_quote: str
    provenance: ClinicalGuidelineSource
    payload: dict[str, Any] = Field(default_factory=dict)


class EmbeddingKnowledgeProjection(BaseModel):
    """Embedding-ready text unit that preserves traceability metadata."""

    embedding_id: str
    unit_id: str
    text: str
    normalized_text: str
    source_quote: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalKnowledgeDocument(BaseModel):
    """RAG/retrieval-ready document derived from a canonical knowledge unit."""

    document_id: str
    unit_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphEntity(BaseModel):
    """Graph node projected from source-grounded knowledge."""

    entity_id: str
    entity_type: str
    label: str
    source_unit_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphEdge(BaseModel):
    """Graph edge with supporting unit/source provenance."""

    edge_id: str
    relation_type: KnowledgeRelationType
    source_entity_id: str
    target_entity_id: str
    supporting_unit_ids: list[str] = Field(default_factory=list)
    source_quote: str | None = None


class KnowledgeGraphProjection(BaseModel):
    """Graph projection derived from canonical knowledge units."""

    entities: list[KnowledgeGraphEntity] = Field(default_factory=list)
    edges: list[KnowledgeGraphEdge] = Field(default_factory=list)


class ClinicalOperationalizationBundle(BaseModel):
    """Downstream operationalizations built from canonical knowledge units."""

    atomic_units: list[AtomicClinicalKnowledgeUnit] = Field(default_factory=list)
    structured_records: list[StructuredKnowledgeRecord] = Field(default_factory=list)
    embedding_units: list[EmbeddingKnowledgeProjection] = Field(default_factory=list)
    rag_documents: list[RetrievalKnowledgeDocument] = Field(default_factory=list)
    knowledge_graph: KnowledgeGraphProjection = Field(
        default_factory=KnowledgeGraphProjection
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
    route: AdaptiveExtractionRoute | None = None
    operationalized_knowledge: ClinicalOperationalizationBundle | None = None
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
        adaptive_routing: bool = True,
        operationalize: bool = True,
        source_document_id: str | None = None,
        source_document_version: str | None = None,
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
        route = self._plan_adaptive_route(file_path, parser_choice)
        if parser_choice != "auto" or not adaptive_routing:
            chosen_parser = self._select_parser_choice(file_path, parser_choice)
            route = AdaptiveExtractionRoute(
                complexity=route.complexity,
                selected_parser=chosen_parser,
                candidate_parsers=[chosen_parser],
                fallback_parsers=[],
                escalation_reason=route.escalation_reason,
            )
            parser = self._build_parser(chosen_parser, parser_ctor)
            parsed_documents = self._parse_document(
                chosen_parser, parser, file_path, parse_options
            )
        else:
            chosen_parser, parsed_documents = self._parse_with_fallbacks(
                route, file_path, parser_ctor, parse_options
            )

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

        operationalized_knowledge = None
        if operationalize:
            operationalized_knowledge = self.operationalize_extracted_knowledge(
                extracted_knowledge,
                source_document_id=source_document_id or Path(file_path).name,
                source_document_version=source_document_version,
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
            route=route,
            operationalized_knowledge=operationalized_knowledge,
            validation=validation,
        )

    def operationalize_extracted_knowledge(
        self,
        extracted_knowledge: list[dict[str, Any]] | dict[str, Any],
        *,
        source_document_id: str,
        source_document_version: str | None = None,
    ) -> ClinicalOperationalizationBundle:
        """Project extracted JSON into canonical units and downstream forms."""
        atomic_units = self.build_atomic_knowledge_units(
            extracted_knowledge,
            source_document_id=source_document_id,
            source_document_version=source_document_version,
        )
        return ClinicalOperationalizationBundle(
            atomic_units=atomic_units,
            structured_records=self._build_structured_records(atomic_units),
            embedding_units=self._build_embedding_units(atomic_units),
            rag_documents=self._build_rag_documents(atomic_units),
            knowledge_graph=self._build_knowledge_graph(atomic_units),
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

    def _plan_adaptive_route(
        self, file_path: str | Path, parser_choice: SupportedParser
    ) -> AdaptiveExtractionRoute:
        if parser_choice != "auto":
            return AdaptiveExtractionRoute(
                complexity="medium",
                selected_parser=parser_choice,
                candidate_parsers=[parser_choice],
            )

        suffix = Path(file_path).suffix.lower()
        if suffix == ".pdf":
            return AdaptiveExtractionRoute(
                complexity="high",
                selected_parser="pymupdf",
                candidate_parsers=["pymupdf", "docling", "multimodal"],
                fallback_parsers=["docling", "multimodal"],
                escalation_reason=(
                    "PDFs start with deterministic/local parsing and escalate to multimodal "
                    "only when local parsers fail or lose structure."
                ),
            )
        if suffix in {".ppt", ".pptx"}:
            return AdaptiveExtractionRoute(
                complexity="high",
                selected_parser="docling",
                candidate_parsers=["docling", "multimodal"],
                fallback_parsers=["multimodal"],
                escalation_reason=(
                    "Slide decks start with layout-aware parsing and escalate to multimodal "
                    "for visually dense content."
                ),
            )
        if suffix in {".doc", ".docx"}:
            return AdaptiveExtractionRoute(
                complexity="low",
                selected_parser="docx",
                candidate_parsers=["docx", "docling"],
                fallback_parsers=["docling"],
                escalation_reason=(
                    "DOCX files are usually structured enough for deterministic parsing."
                ),
            )
        if suffix in {".png", ".jpg", ".jpeg"}:
            return AdaptiveExtractionRoute(
                complexity="high",
                selected_parser="vision_parser",
                candidate_parsers=["vision_parser", "multimodal"],
                fallback_parsers=["multimodal"],
                escalation_reason=(
                    "Images require OCR/vision parsing and may escalate to multimodal parsing "
                    "for charts or dense visual layouts."
                ),
            )
        chosen = self._select_parser_choice(file_path, parser_choice)
        return AdaptiveExtractionRoute(
            complexity="medium",
            selected_parser=chosen,
            candidate_parsers=[chosen],
        )

    def _parse_with_fallbacks(
        self,
        route: AdaptiveExtractionRoute,
        file_path: str | Path,
        parser_ctor: dict,
        parse_options: dict,
    ) -> tuple[str, list[str]]:
        errors: dict[str, str] = {}
        for parser_name in route.candidate_parsers:
            route.attempted_parsers.append(parser_name)
            try:
                parser = self._build_parser(parser_name, parser_ctor)
                parsed = self._parse_document(parser_name, parser, file_path, parse_options)
                route.selected_parser = parser_name
                route.fallback_parsers = [
                    choice for choice in route.candidate_parsers if choice != parser_name
                ]
                route.parser_errors = errors
                return parser_name, parsed
            except Exception as exc:
                errors[parser_name] = str(exc)
        route.parser_errors = errors
        raise RuntimeError(
            "Adaptive parser routing failed for "
            f"{file_path}. Attempted: {route.attempted_parsers}. Errors: {errors}"
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
                    "Medication indications, contraindications, and monitoring "
                    "must not be inferred.",
                    "Recommendation strength and evidence grade must be null when absent.",
                ],
                item_level_checks=[
                    "Flag any item that cannot be traced back to the provided source pages.",
                    "Flag any clinical action that is broader than the source statement.",
                ],
                scoring_mode="likert_1_5",
            )
        return judge.validate(source_pages=source_pages, extracted=extracted, rubric=rubric)

    def build_atomic_knowledge_units(
        self,
        extracted_knowledge: list[dict[str, Any]] | dict[str, Any],
        *,
        source_document_id: str,
        source_document_version: str | None = None,
    ) -> list[AtomicClinicalKnowledgeUnit]:
        """Normalize extracted guideline JSON into atomic canonical units."""
        payloads = self._coerce_extracted_payloads(extracted_knowledge)
        units: list[AtomicClinicalKnowledgeUnit] = []
        mapping = {
            "bp_thresholds": "threshold",
            "diagnostic_criteria": "decision_condition",
            "treatment_recommendations": "recommendation",
            "medication_recommendations": "medication",
            "lifestyle_recommendations": "intervention",
            "follow_up_recommendations": "monitoring_action",
            "contraindications_and_safety": "contraindication",
        }
        for payload_index, payload in enumerate(payloads):
            for field_name, semantic_type in mapping.items():
                for item_index, item in enumerate(payload.get(field_name, []) or []):
                    if not isinstance(item, dict):
                        continue
                    units.append(
                        self._build_atomic_unit(
                            item,
                            semantic_type=semantic_type,
                            unit_id=(
                                f"{source_document_id}:{payload_index}:{field_name}:{item_index}"
                            ),
                            source_document_id=source_document_id,
                            source_document_version=source_document_version,
                        )
                    )
        return units

    @staticmethod
    def _coerce_extracted_payloads(
        extracted_knowledge: list[dict[str, Any]] | dict[str, Any],
    ) -> list[dict[str, Any]]:
        if isinstance(extracted_knowledge, list):
            return [item for item in extracted_knowledge if isinstance(item, dict)]
        if isinstance(extracted_knowledge, dict):
            return [extracted_knowledge]
        return []

    def _build_atomic_unit(
        self,
        item: dict[str, Any],
        *,
        semantic_type: KnowledgeSemanticType,
        unit_id: str,
        source_document_id: str,
        source_document_version: str | None,
    ) -> AtomicClinicalKnowledgeUnit:
        source_payload = item.get("source", {})
        if not isinstance(source_payload, dict):
            source_payload = {}
        source = ClinicalGuidelineSource.model_validate(
            {
                "source_file": source_payload.get("source_file", source_document_id),
                "page_number": source_payload.get("page_number"),
                "section_heading": source_payload.get("section_heading"),
                "source_quote": source_payload.get("source_quote", ""),
                "parser_method": source_payload.get("parser_method"),
            }
        )
        normalized_statement = self._build_normalized_statement(item, semantic_type)
        blocked_reason = None
        extraction_status: ExtractionStatus = "grounded"
        if not source.source_quote:
            blocked_reason = "Missing verbatim source quote"
            extraction_status = "needs_review"
        relationships = self._build_relationships(item, semantic_type)
        title = self._build_unit_title(item, semantic_type)
        return AtomicClinicalKnowledgeUnit(
            unit_id=unit_id,
            semantic_type=semantic_type,
            title=title,
            normalized_statement=normalized_statement,
            source_quote=source.source_quote,
            source=source,
            source_document_id=source_document_id,
            source_document_version=source_document_version,
            certainty=self._infer_certainty(item),
            extraction_status=extraction_status,
            relationships=relationships,
            downstream_eligibility=DownstreamEligibility(
                structured_data=blocked_reason is None,
                embeddings=blocked_reason is None,
                knowledge_graph=blocked_reason is None,
                rag=blocked_reason is None,
                blocked_reason=blocked_reason,
            ),
            metadata={
                key: value
                for key, value in item.items()
                if key not in {"source", "source_quote"}
            },
        )

    @staticmethod
    def _build_normalized_statement(
        item: dict[str, Any], semantic_type: KnowledgeSemanticType
    ) -> str:
        if semantic_type == "threshold":
            population = item.get("population") or "patient"
            context = item.get("context") or "clinical context"
            systolic = item.get("systolic_mm_hg") or "unspecified systolic"
            diastolic = item.get("diastolic_mm_hg") or "unspecified diastolic"
            category = item.get("category") or "threshold"
            action = item.get("action") or "review"
            return (
                f"For {population} in {context}, category '{category}' is triggered at "
                f"{systolic}/{diastolic} mmHg and recommends: {action}."
            )
        if semantic_type == "medication":
            drug = item.get("drug_or_class") or "medication"
            indication = item.get("indication") or "unspecified indication"
            return f"{drug} is recommended when {indication}."
        if semantic_type == "monitoring_action":
            scenario = item.get("scenario") or "clinical scenario"
            interval = item.get("interval") or "unspecified interval"
            return f"For {scenario}, follow-up should occur at {interval}."

        recommendation = item.get("recommendation") or item.get("action") or item.get("topic")
        population = item.get("population")
        if population:
            return f"For {population}, {recommendation}."
        return str(recommendation or item)

    @staticmethod
    def _build_unit_title(item: dict[str, Any], semantic_type: KnowledgeSemanticType) -> str:
        if semantic_type == "threshold":
            return str(item.get("category") or item.get("context") or "Blood pressure threshold")
        if semantic_type == "medication":
            return str(item.get("drug_or_class") or "Medication recommendation")
        if semantic_type == "monitoring_action":
            return str(item.get("scenario") or "Follow-up recommendation")
        return str(item.get("topic") or item.get("recommendation") or semantic_type)

    @staticmethod
    def _infer_certainty(item: dict[str, Any]) -> str | None:
        return item.get("quality_of_evidence") or item.get("strength_of_recommendation")

    @staticmethod
    def _build_relationships(
        item: dict[str, Any], semantic_type: KnowledgeSemanticType
    ) -> list[KnowledgeRelationship]:
        relationships: list[KnowledgeRelationship] = []
        population = item.get("population")
        if population:
            relationships.append(
                KnowledgeRelationship(relation_type="applies_to", target_label=str(population))
            )
        for condition in item.get("conditions", []) or []:
            relationships.append(
                KnowledgeRelationship(relation_type="depends_on", target_label=str(condition))
            )
        for contraindication in item.get("contraindications", []) or []:
            relationships.append(
                KnowledgeRelationship(
                    relation_type="contraindicated_for",
                    target_label=str(contraindication),
                )
            )
        for caution in item.get("cautions", []) or []:
            relationships.append(
                KnowledgeRelationship(relation_type="excludes", target_label=str(caution))
            )
        for requirement in item.get("monitoring_requirements", []) or []:
            relationships.append(
                KnowledgeRelationship(
                    relation_type="requires_monitoring",
                    target_label=str(requirement),
                )
            )
        if semantic_type == "threshold" and item.get("action"):
            relationships.append(
                KnowledgeRelationship(
                    relation_type="triggers",
                    target_label=str(item["action"]),
                )
            )
        return relationships

    @staticmethod
    def _build_structured_records(
        atomic_units: list[AtomicClinicalKnowledgeUnit],
    ) -> list[StructuredKnowledgeRecord]:
        return [
            StructuredKnowledgeRecord(
                record_id=f"record:{unit.unit_id}",
                record_type=unit.semantic_type,
                unit_id=unit.unit_id,
                normalized_statement=unit.normalized_statement,
                source_quote=unit.source_quote,
                provenance=unit.source,
                payload=unit.metadata,
            )
            for unit in atomic_units
        ]

    @staticmethod
    def _build_embedding_units(
        atomic_units: list[AtomicClinicalKnowledgeUnit],
    ) -> list[EmbeddingKnowledgeProjection]:
        projections: list[EmbeddingKnowledgeProjection] = []
        for unit in atomic_units:
            projections.append(
                EmbeddingKnowledgeProjection(
                    embedding_id=f"embedding:{unit.unit_id}",
                    unit_id=unit.unit_id,
                    text="\n".join(
                        [
                            f"Normalized statement: {unit.normalized_statement}",
                            f"Source quote: {unit.source_quote}",
                        ]
                    ),
                    normalized_text=unit.normalized_statement,
                    source_quote=unit.source_quote,
                    metadata={
                        "semantic_type": unit.semantic_type,
                        "section_heading": unit.source.section_heading,
                        "page_number": unit.source.page_number,
                        "source_file": unit.source.source_file,
                        "source_document_id": unit.source_document_id,
                        "source_document_version": unit.source_document_version,
                        "certainty": unit.certainty,
                    },
                )
            )
        return projections

    @staticmethod
    def _build_rag_documents(
        atomic_units: list[AtomicClinicalKnowledgeUnit],
    ) -> list[RetrievalKnowledgeDocument]:
        return [
            RetrievalKnowledgeDocument(
                document_id=f"rag:{unit.unit_id}",
                unit_id=unit.unit_id,
                content="\n".join(
                    [
                        unit.title,
                        unit.normalized_statement,
                        f"Evidence: {unit.source_quote}",
                    ]
                ),
                metadata={
                    "semantic_type": unit.semantic_type,
                    "section_heading": unit.source.section_heading,
                    "page_number": unit.source.page_number,
                    "source_file": unit.source.source_file,
                    "source_document_id": unit.source_document_id,
                },
            )
            for unit in atomic_units
        ]

    @staticmethod
    def _build_knowledge_graph(
        atomic_units: list[AtomicClinicalKnowledgeUnit],
    ) -> KnowledgeGraphProjection:
        entities: dict[str, KnowledgeGraphEntity] = {}
        edges: list[KnowledgeGraphEdge] = []
        for unit in atomic_units:
            primary_id = f"unit:{unit.unit_id}"
            entities.setdefault(
                primary_id,
                KnowledgeGraphEntity(
                    entity_id=primary_id,
                    entity_type=unit.semantic_type,
                    label=unit.title,
                    source_unit_ids=[unit.unit_id],
                    properties={
                        "normalized_statement": unit.normalized_statement,
                        "certainty": unit.certainty,
                    },
                ),
            )
            source_anchor_id = f"source:{unit.unit_id}"
            entities.setdefault(
                source_anchor_id,
                KnowledgeGraphEntity(
                    entity_id=source_anchor_id,
                    entity_type="source_anchor",
                    label=unit.source.source_quote,
                    source_unit_ids=[unit.unit_id],
                    properties={
                        "source_file": unit.source.source_file,
                        "page_number": unit.source.page_number,
                        "section_heading": unit.source.section_heading,
                    },
                ),
            )
            edges.append(
                KnowledgeGraphEdge(
                    edge_id=f"edge:{unit.unit_id}:supported_by",
                    relation_type="supported_by",
                    source_entity_id=primary_id,
                    target_entity_id=source_anchor_id,
                    supporting_unit_ids=[unit.unit_id],
                    source_quote=unit.source_quote,
                )
            )
            for rel_index, relationship in enumerate(unit.relationships):
                target_id = (
                    relationship.target_unit_id
                    if relationship.target_unit_id
                    else f"label:{relationship.relation_type}:{relationship.target_label}"
                )
                entities.setdefault(
                    target_id,
                    KnowledgeGraphEntity(
                        entity_id=target_id,
                        entity_type="label",
                        label=relationship.target_label,
                        source_unit_ids=[unit.unit_id],
                    ),
                )
                edges.append(
                    KnowledgeGraphEdge(
                        edge_id=f"edge:{unit.unit_id}:{rel_index}",
                        relation_type=relationship.relation_type,
                        source_entity_id=primary_id,
                        target_entity_id=target_id,
                        supporting_unit_ids=[unit.unit_id],
                        source_quote=unit.source_quote,
                    )
                )
        return KnowledgeGraphProjection(entities=list(entities.values()), edges=edges)
