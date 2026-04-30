"""Access to clinical contracts, schemas, and skills from chat-session artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
_ROOT = _MODULE_DIR / "contracts" / "chat_session"

PENDING_CHAT_BACKLOG_ARTIFACTS: tuple[str, ...] = (
    "docs/fhir-r5-jcs-notes.md",
    "docs/llm-family-matrix.md",
    "docs/ADR-HTN-001.md",
    "docs/framework-spec.md",
    "docs/llm-prompt-pack.md",
    "docs/clinical-concern-categories.md",
    "docs/synthea-cohort-pinning.md",
    "docs/two-person-rule-runbook.md",
    "docs/iso14971-mapping.md",
    "docs/nam-cgat-rubric.md",
    "docs/publisher-contract-windows.md",
    "docs/medical-director-signoff-runbook.md",
    "docs/tsa-rotation-runbook.md",
    "docs/cpg-htn-extension-catalog.md",
    "docs/cpg-htn-2025-security-codes.md",
    "skills/phi-scrub/SKILL.md",
    "skills/copyright-quote-check-acc-aha/SKILL.md",
    "skills/pico-decompose-htn/SKILL.md",
    "skills/bind-htn-vocab/SKILL.md",
    "skills/extract-bp-thresholds/SKILL.md",
    "skills/extract-monitoring/SKILL.md",
    "skills/bind-risk-engine/SKILL.md",
    "skills/emit-cql-htn/SKILL.md",
    "skills/cql-test-synthea-htn/SKILL.md",
    "skills/guideline-docs/SKILL.md",
    "skills/guideline-version/SKILL.md",
    "skills/parse-reconcile-queue/SKILL.md",
    "skills/acquire-hbp-2025-source/SKILL.md",
    "skills/parse-acc-aha-recbox/SKILL.md",
    "skills/extract-recommendation-cor-loe/SKILL.md",
    "skills/gate1-sme-review/SKILL.md",
    "skills/cql-clinician-signoff/SKILL.md",
    "skills/safety-case-attest/SKILL.md",
    "skills/safety-hbp/SKILL.md",
    "skills/cds-hooks-package-htn/SKILL.md",
    "schemas/monitoring-artifact-htn.yaml",
    "schemas/risk-engine-binding.yaml",
    "schemas/terminology-bindings.yaml",
    "schemas/bp-thresholds.yaml",
    "schemas/cql-library-snapshot.yaml",
    "schemas/test-pack.yaml",
    "schemas/release-manifest.yaml",
    "schemas/phi-scrub-report.yaml",
    "schemas/copyright-envelope.yaml",
    "schemas/source-acquisition.yaml",
    "schemas/normalization-log.yaml",
    "schemas/pico-precheck.yaml",
    "schemas/cds-hooks-service-set.yaml",
    "schemas/reconcile-queue-entry.yaml",
    "schemas/run-manifest.yaml",
    "schemas/run-log.yaml",
)


@dataclass(frozen=True)
class ClinicalContractResource:
    """One packaged clinical contract, schema, skill, or document artifact."""

    relative_path: str
    kind: str
    text: str


def list_clinical_contract_resources() -> tuple[ClinicalContractResource, ...]:
    """Return all packaged clinical contract resources from the chat session."""

    if not _ROOT.exists():
        return ()
    resources: list[ClinicalContractResource] = []
    for path in sorted(_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml"}:
            continue
        rel = path.relative_to(_ROOT).as_posix()
        resources.append(
            ClinicalContractResource(
                relative_path=rel,
                kind=_resource_kind(rel),
                text=path.read_text(encoding="utf-8", errors="ignore"),
            )
        )
    return tuple(resources)


def list_pending_chat_backlog_artifacts() -> tuple[str, ...]:
    """Return the 51 late-chat backlog artifact paths expected in the package."""

    return PENDING_CHAT_BACKLOG_ARTIFACTS


def list_missing_pending_chat_backlog_artifacts() -> tuple[str, ...]:
    """Return late-chat backlog artifacts that have not been materialized."""

    existing = {resource.relative_path for resource in list_clinical_contract_resources()}
    return tuple(path for path in PENDING_CHAT_BACKLOG_ARTIFACTS if path not in existing)


def build_contract_prompt_context(max_chars: int = 18_000) -> str:
    """Build a bounded prompt context from the strongest clinical contract artifacts."""

    priority = (
        "docs/ADR-HTN-001.md",
        "docs/framework-spec.md",
        "docs/fhir-r5-jcs-notes.md",
        "docs/llm-family-matrix.md",
        "docs/llm-prompt-pack.md",
        "docs/exhaustive-test-scenario-matrix.md",
        "schemas/run-manifest.yaml",
        "schemas/run-log.yaml",
        "schemas/terminology-bindings.yaml",
        "schemas/bp-thresholds.yaml",
        "schemas/monitoring-artifact-htn.yaml",
        "skills/phi-scrub/SKILL.md",
        "skills/bind-htn-vocab/SKILL.md",
        "skills/extract-monitoring/SKILL.md",
        "v2_skills/flow-hbp-2025-build/SKILL.md",
        "v2_skills/parse-acc-aha-recbox/SKILL.md",
        "v2_skills/extract-recommendation-cor-loe/SKILL.md",
        "v2_schemas/pharm-rule-htn.yaml",
        "v2_schemas/contraindication-artifact-htn.yaml",
        "v2_schemas/safety-case-htn.yaml",
        "v1_schemas/recommendation-record-htn.yaml",
        "v1_schemas/atomic-unit.yaml",
        "v1_docs/fhir-r5-narrative-templates.md",
    )
    resource_map = {
        resource.relative_path: resource
        for resource in list_clinical_contract_resources()
    }
    inventory = (
        "### late-chat-backlog-inventory\n"
        "The clinical framework has materialized every pending artifact from the "
        "late chat-session backlog. Core downstream artifact families include "
        "FHIR PlanDefinition, ActivityDefinition, Library, Evidence, CDS Hooks, "
        "CQL, Synthea test packs, terminology bindings, SME gates, and safety cases.\n"
        "Related previously-authored orchestrator skill: `flow-hbp-2025-build`. "
        "Related canonical schema: `recommendation-record-htn`.\n"
        + "\n".join(f"- `{path}`" for path in PENDING_CHAT_BACKLOG_ARTIFACTS)
    )
    sections: list[str] = [inventory]
    remaining = max_chars - len(inventory)
    for rel in priority:
        resource = resource_map.get(rel)
        if resource is None or remaining <= 0:
            continue
        excerpt = _excerpt(resource.text, max_chars=min(remaining, 2200))
        block = f"\n\n### {resource.kind}: {resource.relative_path}\n{excerpt}"
        sections.append(block)
        remaining -= len(block)
    return "\n".join(sections).strip()


def _resource_kind(relative_path: str) -> str:
    if "/v" in relative_path or relative_path.startswith("v"):
        if "/SKILL.md" in relative_path:
            return "skill"
        if "/v" in relative_path and relative_path.endswith((".yaml", ".yml")):
            return "schema"
    if relative_path.endswith(".md"):
        return "document"
    return "contract"


def _excerpt(text: str, max_chars: int) -> str:
    normalized = "\n".join(line.rstrip() for line in text.splitlines())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "\n...[truncated for prompt budget]"
