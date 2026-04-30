"""Clinical LMCLI prompt assembly using existing toolkit prompt resources."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from gaik.software_components.extractor import ExtractionRequirements
from gaik.software_components.validators.llm_judge.prompts import build_system_prompt

from .contracts import build_contract_prompt_context


def _load_multimodal_prompt_constants() -> dict[str, str]:
    prompt_file = (
        Path(__file__).resolve().parents[1]
        / "software_components"
        / "parsers"
        / "multimodal_parser"
        / "prompts.py"
    )
    if not prompt_file.exists():
        prompt_file = (
            Path(__file__).resolve().parents[2]
            / "software_components"
            / "parsers"
            / "multimodal_parser"
            / "prompts.py"
        )
    text = prompt_file.read_text(encoding="utf-8", errors="ignore") if prompt_file.exists() else ""
    constants: dict[str, str] = {}
    for name in ("OPENAI_SYSTEM_PROMPT", "CLAUDE_SYSTEM_PROMPT", "GOOGLE_SYSTEM_PROMPT"):
        match = re.search(rf'{name}\s*=\s*"""(.*?)"""', text, flags=re.DOTALL)
        constants[name] = match.group(1).strip() if match else ""
    return constants

_CLINICAL_EXTRACTION_POLICY = """
Clinical extraction policy:
- Preserve source structure, headings, tables, thresholds, caveats, exception logic, and
  medication/action pathways.
- Use ONLY text that is present in the source document block. Do not infer missing clinical
  values, grades, contraindications, populations, dates, or follow-up intervals.
- Every actionable item must include source.source_file and a verbatim source.source_quote.
- Set absent values to null or [] according to schema type.
- Keep recommendation strength and evidence grade null unless explicitly present.
- If the source text is a chat-session artifact registry fallback, mark uncertainty in
  source_gaps_or_uncertainties and preserve the registry quote verbatim.
- Return ONLY valid JSON. No markdown fences, no explanation, no trailing commentary.
"""

_MULTIMODAL_PROMPTS = _load_multimodal_prompt_constants()

_EXISTING_PROMPT_RESOURCE_BLOCK = "\n\n".join(
    (
        "Existing multimodal parser prompt resource (OpenAI-style):\n"
        + _MULTIMODAL_PROMPTS["OPENAI_SYSTEM_PROMPT"],
        "Existing multimodal parser prompt resource (Claude-style):\n"
        + _MULTIMODAL_PROMPTS["CLAUDE_SYSTEM_PROMPT"],
        "Existing multimodal parser prompt resource (Google-style):\n"
        + _MULTIMODAL_PROMPTS["GOOGLE_SYSTEM_PROMPT"],
        "Existing LLM judge calibration prompt resource:\n"
        + build_system_prompt("likert_1_5"),
    )
)


def build_clinical_lmcli_prompt(
    *,
    extraction_model: type[BaseModel],
    requirements: ExtractionRequirements,
    user_requirements: str,
    documents: list[str],
    source_document_id: str,
) -> str:
    """Build a high-fidelity clinical extraction prompt from existing prompt assets."""

    schema = extraction_model.model_json_schema()
    fields = [field.model_dump(mode="json") for field in requirements.fields]
    documents_block = "\n\n--- DOCUMENT ---\n\n".join(documents)
    contract: dict[str, Any] = {
        "output_contract": {
            "top_level": "object",
            "required_key": "records",
            "records_type": "array",
            "record_schema_name": extraction_model.__name__,
        },
        "source_document_id": source_document_id,
        "field_requirements": fields,
        "pydantic_json_schema": schema,
    }
    return (
        "You are the local LMCLI clinical knowledge extraction backend.\n"
        "Use the robust parser and judge prompt resources below as operating constraints.\n\n"
        f"{_EXISTING_PROMPT_RESOURCE_BLOCK}\n\n"
        "Packaged chat-session clinical contracts, schemas, and skills:\n"
        f"{build_contract_prompt_context()}\n\n"
        f"{_CLINICAL_EXTRACTION_POLICY}\n\n"
        "User extraction requirements:\n"
        f"{user_requirements}\n\n"
        "Strict JSON output contract:\n"
        f"{json.dumps(contract, indent=2)}\n\n"
        "Documents to extract from:\n"
        f"{documents_block}\n"
    )
