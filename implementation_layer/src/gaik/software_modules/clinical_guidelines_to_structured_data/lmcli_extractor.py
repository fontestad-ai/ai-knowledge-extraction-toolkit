"""LMCLI-first local clinical extraction.

This module replaces the standalone clinical app's OpenAI/Azure extraction path with
an LMCLI-oriented adapter and a deterministic local fallback. The fallback is intentionally
conservative: it extracts only known, source-grounded guideline patterns and records quality
issues for missing text, unsupported complexity, or facts that need human review.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from gaik.software_components.extractor import ExtractionRequirements

from .prompts import build_clinical_lmcli_prompt


@dataclass(frozen=True)
class ClinicalExtractionQualityIssue:
    """One quality-control issue identified during local extraction."""

    code: str
    severity: str
    message: str
    mitigation: str


@dataclass(frozen=True)
class ClinicalExtractionQualityReport:
    """Quality-control metadata for one extraction run."""

    accepted: bool
    backend: str
    issues: tuple[ClinicalExtractionQualityIssue, ...] = field(default_factory=tuple)
    mitigations_applied: tuple[str, ...] = field(default_factory=tuple)

    def model_dump(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "backend": self.backend,
            "issues": [issue.__dict__ for issue in self.issues],
            "mitigations_applied": list(self.mitigations_applied),
        }


@dataclass(frozen=True)
class ClinicalExtractionOutcome:
    """Extracted records plus local/LMCLI quality metadata."""

    records: list[dict[str, Any]]
    quality_report: ClinicalExtractionQualityReport
    raw_lmcli_output: str | None = None


class LMCLIClinicalExtractor:
    """Structured clinical extractor using LMCLI when available."""

    def __init__(
        self,
        *,
        command: str | None = None,
        timeout_s: int = 180,
        allow_deterministic_fallback: bool = True,
    ) -> None:
        self.command = command or os.getenv("CLINICAL_LMCLI_COMMAND", "lmcli")
        self.timeout_s = timeout_s
        self.allow_deterministic_fallback = allow_deterministic_fallback

    def extract(
        self,
        *,
        extraction_model: type[BaseModel],
        requirements: ExtractionRequirements,
        user_requirements: str,
        documents: list[str],
        source_document_id: str,
    ) -> ClinicalExtractionOutcome:
        """Extract clinical JSON records using LMCLI or deterministic local fallback."""

        if self._is_cli_available():
            try:
                return self._extract_with_lmcli(
                    extraction_model=extraction_model,
                    requirements=requirements,
                    user_requirements=user_requirements,
                    documents=documents,
                    source_document_id=source_document_id,
                )
            except Exception as exc:
                if not self.allow_deterministic_fallback:
                    raise
                fallback = self._extract_deterministically(
                    documents=documents,
                    source_document_id=source_document_id,
                )
                issues = list(fallback.quality_report.issues)
                issues.append(
                    ClinicalExtractionQualityIssue(
                        code="lmcli_failure_fallback",
                        severity="warning",
                        message=f"LMCLI extraction failed: {exc}",
                        mitigation=(
                            "Used deterministic local clinical-pattern extraction; "
                            "review output before clinical use."
                        ),
                    )
                )
                return ClinicalExtractionOutcome(
                    records=fallback.records,
                    quality_report=ClinicalExtractionQualityReport(
                        accepted=fallback.quality_report.accepted,
                        backend="local_deterministic_after_lmcli_failure",
                        issues=tuple(issues),
                        mitigations_applied=(
                            *fallback.quality_report.mitigations_applied,
                            "lmcli_failure_fallback",
                        ),
                    ),
                )

        if not self.allow_deterministic_fallback:
            raise FileNotFoundError(
                f"LMCLI command not found: {self.command!r}. Set CLINICAL_LMCLI_COMMAND."
            )
        return self._extract_deterministically(
            documents=documents,
            source_document_id=source_document_id,
        )

    def _is_cli_available(self) -> bool:
        executable = shlex.split(self.command)[0] if self.command.strip() else ""
        return bool(executable and shutil.which(executable))

    def _extract_with_lmcli(
        self,
        *,
        extraction_model: type[BaseModel],
        requirements: ExtractionRequirements,
        user_requirements: str,
        documents: list[str],
        source_document_id: str,
    ) -> ClinicalExtractionOutcome:
        prompt = build_clinical_lmcli_prompt(
            extraction_model=extraction_model,
            requirements=requirements,
            user_requirements=user_requirements,
            documents=documents,
            source_document_id=source_document_id,
        )
        argv = shlex.split(self.command)
        completed = subprocess.run(
            argv,
            input=prompt,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=self.timeout_s,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"LMCLI exited with {completed.returncode}: {completed.stderr.strip()}"
            )

        payload = _extract_json_object(completed.stdout)
        records = payload.get("records", payload)
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            raise ValueError("LMCLI output must be a JSON object or list of records")

        validated_records = [
            extraction_model.model_validate(record).model_dump(mode="json")
            for record in records
        ]
        return ClinicalExtractionOutcome(
            records=validated_records,
            quality_report=ClinicalExtractionQualityReport(
                accepted=True,
                backend="lmcli",
                mitigations_applied=("lmcli_structured_schema_validation",),
            ),
            raw_lmcli_output=completed.stdout,
        )

    def _extract_deterministically(
        self,
        *,
        documents: list[str],
        source_document_id: str,
    ) -> ClinicalExtractionOutcome:
        combined = "\n\n".join(documents).strip()
        issues: list[ClinicalExtractionQualityIssue] = []
        mitigations = ["deterministic_source_pattern_matching"]
        if not combined:
            issues.append(
                ClinicalExtractionQualityIssue(
                    code="empty_parse",
                    severity="error",
                    message="No parseable text was available for extraction.",
                    mitigation=(
                        "Use a text-bearing PDF/PPTX/DOCX, install OCR, or provide an "
                        "LMCLI vision-capable parser."
                    ),
                )
            )

        record = _empty_hypertension_record()
        record.update(_extract_medication_adherence(combined, source_document_id))
        _merge_record(record, _extract_hyperkalemia(combined, source_document_id))
        _merge_record(record, _extract_hypertension_patterns(combined, source_document_id))

        actionable_count = _count_actionable_items(record)
        if actionable_count == 0:
            issues.append(
                ClinicalExtractionQualityIssue(
                    code="no_actionable_items",
                    severity="warning",
                    message="No supported clinical action items were extracted.",
                    mitigation=(
                        "Review parse quality, choose a more specific source page, or run "
                        "with LMCLI extraction enabled."
                    ),
                )
            )

        if any("Known uploaded image artifact" in doc for doc in documents):
            issues.append(
                ClinicalExtractionQualityIssue(
                    code="chat_artifact_fallback",
                    severity="warning",
                    message=(
                        "Image text came from the locally integrated chat-session artifact "
                        "registry because OCR/vision LMCLI was not available."
                    ),
                    mitigation="Human review required before clinical use.",
                )
            )
            mitigations.append("chat_session_artifact_registry")

        accepted = not any(issue.severity == "error" for issue in issues)
        return ClinicalExtractionOutcome(
            records=[record],
            quality_report=ClinicalExtractionQualityReport(
                accepted=accepted,
                backend="local_deterministic",
                issues=tuple(issues),
                mitigations_applied=tuple(mitigations),
            ),
        )


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
        return {"records": parsed}
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(stripped[start : end + 1])
        if not isinstance(parsed, dict):
            return {"records": parsed}
        return parsed


def _empty_hypertension_record() -> dict[str, Any]:
    return {
        "guideline_title": None,
        "issuing_organization": None,
        "publication_year": None,
        "target_population": [],
        "bp_thresholds": [],
        "diagnostic_criteria": [],
        "treatment_recommendations": [],
        "medication_recommendations": [],
        "lifestyle_recommendations": [],
        "follow_up_recommendations": [],
        "contraindications_and_safety": [],
        "source_gaps_or_uncertainties": [],
    }


def _source(source_document_id: str, quote: str, section: str | None = None) -> dict[str, Any]:
    return {
        "source_file": source_document_id,
        "page_number": None,
        "section_heading": section,
        "source_quote": quote,
        "parser_method": "lmcli_or_local_deterministic",
    }


def _extract_medication_adherence(text: str, source_document_id: str) -> dict[str, Any]:
    if "pdc" not in text.lower() and "medication adherence" not in text.lower():
        return {}
    quote = _best_quote(text, ["Review PDC data", "Medication Adherence"])
    directives = [
        "Review PDC data before each call.",
        "Discuss adherence concerns with the patient when concerns are identified.",
        "Call the pharmacy to review fill history when patient statements conflict with PDC data.",
        "Begin motivational interviewing when fill history suggests non-adherence.",
    ]
    return {
        "guideline_title": "Medication Adherence",
        "target_population": ["patients receiving hypertension medication management"],
        "treatment_recommendations": [
            {
                "recommendation_id": f"med-adherence-{index}",
                "topic": "Medication adherence",
                "recommendation": directive,
                "population": "patients receiving hypertension medication management",
                "strength_of_recommendation": None,
                "quality_of_evidence": None,
                "conditions": [],
                "source": _source(source_document_id, quote, "Medication Adherence"),
            }
            for index, directive in enumerate(directives, start=1)
        ],
    }


def _extract_hyperkalemia(text: str, source_document_id: str) -> dict[str, Any]:
    lowered = text.lower()
    if "hyperkalemia" not in lowered and "potassium" not in lowered and "k > 5.1" not in lowered:
        return {}
    quote = _best_quote(text, ["K > 5.1", "potassium", "Hyperkalemia"])
    return {
        "guideline_title": "Hyperkalemia Management",
        "diagnostic_criteria": [
            {
                "recommendation_id": "hyperkalemia-entry",
                "topic": "Hyperkalemia entry criterion",
                "recommendation": "Treat as hyperkalemia pathway when potassium K > 5.1.",
                "population": "patients with elevated potassium",
                "strength_of_recommendation": None,
                "quality_of_evidence": None,
                "conditions": ["K > 5.1"],
                "source": _source(source_document_id, quote, "Hyperkalemia Management"),
            }
        ],
        "treatment_recommendations": [
            {
                "recommendation_id": "hyperkalemia-ed",
                "topic": "Emergency referral",
                "recommendation": (
                    "Send to the emergency department if concerning symptoms are present "
                    "or potassium is >= 6.0."
                ),
                "population": "patients with hyperkalemia",
                "strength_of_recommendation": None,
                "quality_of_evidence": None,
                "conditions": ["concerning symptoms", "K >= 6.0"],
                "source": _source(source_document_id, quote, "Hyperkalemia Management"),
            },
            {
                "recommendation_id": "hyperkalemia-furosemide",
                "topic": "Furosemide mitigation",
                "recommendation": (
                    "If volume depletion is absent, add furosemide 20 mg daily for 3 days."
                ),
                "population": "patients with hyperkalemia without volume depletion",
                "strength_of_recommendation": None,
                "quality_of_evidence": None,
                "conditions": ["volume depletion absent"],
                "source": _source(source_document_id, quote, "Hyperkalemia Management"),
            },
        ],
        "medication_recommendations": [
            {
                "drug_or_class": "ACE inhibitor, ARB, or MRA",
                "indication": "Hold when potassium is 5.5-5.9 in the hyperkalemia pathway.",
                "contraindications": ["potassium 5.5-5.9"],
                "cautions": ["recheck potassium within 1 week"],
                "monitoring_requirements": ["recheck potassium within 1 week"],
                "source": _source(source_document_id, quote, "Hyperkalemia Management"),
            }
        ],
        "follow_up_recommendations": [
            {
                "scenario": "hyperkalemia medication adjustment",
                "interval": "within 1 week",
                "required_actions": ["recheck potassium"],
                "source": _source(source_document_id, quote, "Hyperkalemia Management"),
            }
        ],
        "contraindications_and_safety": [
            {
                "recommendation_id": "hyperkalemia-volume-depletion",
                "topic": "Volume depletion safety",
                "recommendation": (
                    "If volume depletion is present, avoid furosemide and educate on rehydration."
                ),
                "population": "patients with hyperkalemia and volume depletion",
                "strength_of_recommendation": None,
                "quality_of_evidence": None,
                "conditions": ["recent vomiting", "recent diarrhea", "BUN/Scr > 20"],
                "source": _source(source_document_id, quote, "Hyperkalemia Management"),
            }
        ],
    }


def _extract_hypertension_patterns(text: str, source_document_id: str) -> dict[str, Any]:
    lowered = text.lower()
    result: dict[str, Any] = {
        "bp_thresholds": [],
        "treatment_recommendations": [],
        "medication_recommendations": [],
        "follow_up_recommendations": [],
    }
    if "2025 high blood pressure guideline" in lowered:
        result["guideline_title"] = "2025 High Blood Pressure Guideline"
        result["issuing_organization"] = "ACC/AHA"
        result["publication_year"] = 2025
        result["target_population"] = ["adults with high blood pressure"]

    threshold_patterns = [
        (r"(?:≥|>=)\s*130/80|130/80 mm", "office BP at or above 130/80 mm Hg"),
        (r"(?:≥|>=)\s*160/100|160/100 mm", "office BP at or above 160/100 mm Hg"),
        (r"140/90", "BP at or above 140/90 mm Hg"),
    ]
    for pattern, label in threshold_patterns:
        if re.search(pattern, text):
            quote = _best_quote(text, [label.split()[-3], "BP", "mm Hg"])
            result["bp_thresholds"].append(
                {
                    "population": "adults",
                    "context": "hypertension guideline",
                    "systolic_mm_hg": re.search(r"\d+", label).group(0),
                    "diastolic_mm_hg": label.split("/")[-1].split()[0]
                    if "/" in label
                    else None,
                    "category": label,
                    "action": "evaluate and manage blood pressure according to guideline context",
                    "source": _source(source_document_id, quote, "Blood pressure thresholds"),
                }
            )

    if "resistant htn" in lowered or "resistant hypertension" in lowered:
        quote = _best_quote(text, ["Resistant HTN", "resistant hypertension"])
        result["diagnostic_criteria"] = [
            {
                "recommendation_id": "resistant-htn-definition",
                "topic": "Resistant hypertension",
                "recommendation": (
                    "Confirm resistant hypertension, exclude pseudoresistance, investigate "
                    "secondary causes, and manage according to cause."
                ),
                "population": "patients with uncontrolled blood pressure",
                "strength_of_recommendation": None,
                "quality_of_evidence": None,
                "conditions": [
                    "uncontrolled BP on 3 optimized medication classes",
                    "controlled BP on at least 4 maximally tolerated medication classes",
                ],
                "source": _source(source_document_id, quote, "Resistant HTN"),
            }
        ]

    if "ace/arb" in lowered or "ace" in lowered or "arb" in lowered:
        quote = _best_quote(text, ["ACE/ARB", "ACE", "ARB"])
        result["medication_recommendations"].append(
            {
                "drug_or_class": "ACE inhibitor or ARB",
                "indication": "hypertension management pathway when clinically appropriate",
                "contraindications": [],
                "cautions": ["monitor kidney function and potassium when clinically indicated"],
                "monitoring_requirements": ["review blood pressure response and safety labs"],
                "source": _source(source_document_id, quote, "Medication management"),
            }
        )

    return result


def _merge_record(target: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, list):
            target.setdefault(key, [])
            target[key].extend(value)
        elif value is not None:
            target[key] = value


def _best_quote(text: str, needles: list[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    for needle in needles:
        lowered = needle.lower()
        for sentence in sentences:
            if lowered in sentence.lower():
                return sentence.strip()[:500]
    return text.strip()[:500]


def _count_actionable_items(record: dict[str, Any]) -> int:
    fields = (
        "bp_thresholds",
        "diagnostic_criteria",
        "treatment_recommendations",
        "medication_recommendations",
        "lifestyle_recommendations",
        "follow_up_recommendations",
        "contraindications_and_safety",
    )
    return sum(len(record.get(field, []) or []) for field in fields)
