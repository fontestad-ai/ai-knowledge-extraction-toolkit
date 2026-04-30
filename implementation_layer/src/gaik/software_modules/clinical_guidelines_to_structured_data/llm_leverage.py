"""LLM leverage map for clinical knowledge extraction workflows.

The toolkit already centralizes API-backed LLM access through
``gaik.software_components.llm`` and parser-specific provider factories. This module documents
where models are used in the clinical-guideline workflow and defines explicit target providers
for future CLI-backed adapters without executing any external CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LLMProcessStage = Literal[
    "parsing",
    "classification",
    "schema_generation",
    "structured_extraction",
    "validation",
    "evaluation",
    "retrieval_synthesis",
]


@dataclass(frozen=True)
class LLMUsageDescriptor:
    """One place where LLMs are used in knowledge extraction."""

    stage: LLMProcessStage
    code_path: str
    current_entry_points: tuple[str, ...]
    model_role: str
    grounding_or_safety_control: str


@dataclass(frozen=True)
class CliModelAccessTarget:
    """Target CLI-backed provider for a future centralized LLM adapter."""

    provider_key: str
    expected_cli: str
    intended_models: tuple[str, ...]
    target_factory_surface: str
    implementation_note: str


def get_knowledge_extraction_llm_usage_map() -> tuple[LLMUsageDescriptor, ...]:
    """Return the LLM-use inventory for extraction, evaluation, distillation, and synthesis."""

    return (
        LLMUsageDescriptor(
            stage="parsing",
            code_path="gaik.software_components.parsers",
            current_entry_points=(
                "VisionParser",
                "VisionPlusParser",
                "MultimodalParser",
            ),
            model_role=(
                "Convert complex clinical PDFs, scanned pages, charts, and tables into "
                "source-preserving markdown/text."
            ),
            grounding_or_safety_control=(
                "Parser prompts require visible-only output and avoid hallucinated rows; "
                "MultimodalParser keeps raw_markdown and clean_markdown for audit."
            ),
        ),
        LLMUsageDescriptor(
            stage="classification",
            code_path="gaik.software_components.doc_classifier",
            current_entry_points=("DocumentClassifier",),
            model_role=(
                "Route source files by guideline/protocol/document class before choosing "
                "parsers or extraction schemas."
            ),
            grounding_or_safety_control=(
                "Structured classification schema limits output to caller-provided classes "
                "plus unknown."
            ),
        ),
        LLMUsageDescriptor(
            stage="schema_generation",
            code_path="gaik.software_components.extractor.schema",
            current_entry_points=("SchemaGenerator", "detect_structure_type"),
            model_role=(
                "Distill natural-language extraction requirements into flat or nested "
                "Pydantic schemas."
            ),
            grounding_or_safety_control=(
                "FieldSpec validators enforce snake_case names, allowed field types, and "
                "unique fields."
            ),
        ),
        LLMUsageDescriptor(
            stage="structured_extraction",
            code_path="gaik.software_components.extractor.extractor",
            current_entry_points=("DataExtractor",),
            model_role=(
                "Extract source-grounded clinical facts into typed Pydantic JSON objects."
            ),
            grounding_or_safety_control=(
                "SYSTEM_PARSER requires null for uncertain or missing values and forbids "
                "extra fields."
            ),
        ),
        LLMUsageDescriptor(
            stage="validation",
            code_path="gaik.software_components.validators.llm_judge",
            current_entry_points=("LLMJudge", "LLMJudgePanel", "compare_pairwise"),
            model_role=(
                "Evaluate extracted clinical JSON against source page images and identify "
                "unsupported, suspect, or wrong facts."
            ),
            grounding_or_safety_control=(
                "ValidationRubric supports field checks, item checks, few-shot calibration, "
                "Likert scoring, and suggested corrections."
            ),
        ),
        LLMUsageDescriptor(
            stage="evaluation",
            code_path="gaik.software_components.evaluators",
            current_entry_points=("ExtractionEvaluator", "RAGEvaluator", "BatchEvaluationRunner"),
            model_role=(
                "Score extraction and RAG quality, including semantic equivalence, "
                "faithfulness, answer relevance, context precision, and context recall."
            ),
            grounding_or_safety_control=(
                "Exact metrics are deterministic; semantic metrics reuse LLMJudge rubrics."
            ),
        ),
        LLMUsageDescriptor(
            stage="retrieval_synthesis",
            code_path="gaik.software_components.RAG.answer_generator",
            current_entry_points=("AnswerGenerator", "RAGWorkflow"),
            model_role=(
                "Synthesize grounded answers from retrieved source chunks for clinical "
                "decision-support interactions."
            ),
            grounding_or_safety_control=(
                "Retriever-supplied documents preserve metadata for source citations and "
                "faithfulness evaluation."
            ),
        ),
    )


def get_cli_model_access_targets() -> tuple[CliModelAccessTarget, ...]:
    """Return target providers for a future CLI-backed centralized wrapper/factory."""

    return (
        CliModelAccessTarget(
            provider_key="claude_code_cli",
            expected_cli="claude",
            intended_models=("Claude Code subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Add a subprocess-backed ProviderClient adapter that sends prompts to the "
                "Claude Code CLI only when the CLI is installed and authenticated locally."
            ),
        ),
        CliModelAccessTarget(
            provider_key="codex_cli",
            expected_cli="codex",
            intended_models=("Codex / ChatGPT subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Add a CLI adapter for non-interactive Codex invocations with explicit "
                "timeout, no shell interpolation, and structured-output post-parsing."
            ),
        ),
        CliModelAccessTarget(
            provider_key="gemini_cli",
            expected_cli="gemini",
            intended_models=("Gemini subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Add a Gemini CLI adapter alongside the existing Google API adapter for "
                "workflows that must use an authenticated local subscription CLI."
            ),
        ),
        CliModelAccessTarget(
            provider_key="github_copilot_cli",
            expected_cli="gh copilot",
            intended_models=("GitHub Copilot subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Add an adapter only for supported non-interactive Copilot CLI surfaces; "
                "fallback to API-backed providers when structured output is unavailable."
            ),
        ),
        CliModelAccessTarget(
            provider_key="snowflake_cortex_cli",
            expected_cli="snow sql",
            intended_models=("Snowflake Cortex models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Add a Snowflake CLI/Cortex adapter that routes prompts through a configured "
                "warehouse and returns normalized ProviderClient responses."
            ),
        ),
    )
