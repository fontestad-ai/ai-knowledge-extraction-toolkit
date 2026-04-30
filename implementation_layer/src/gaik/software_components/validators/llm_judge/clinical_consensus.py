"""Clinical consensus orchestration on top of ``LLMJudgePanel``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .panel import LLMJudgePanel
from .schema import JudgePanelResult, ValidationFlag, ValidationRubric

ClinicalJudgeRole = Literal[
    "source_faithfulness",
    "completeness",
    "clinical_logic_consistency",
    "provenance_traceability",
    "normalization_correctness",
    "downstream_representation",
]
ClinicalArtifactType = Literal[
    "extraction",
    "structured_record",
    "embedding_projection",
    "knowledge_graph",
    "rag_document",
]
ArtifactRisk = Literal["low", "medium", "high"]

_ROLE_ORDER: tuple[ClinicalJudgeRole, ...] = (
    "source_faithfulness",
    "completeness",
    "clinical_logic_consistency",
    "provenance_traceability",
    "normalization_correctness",
    "downstream_representation",
)

_ROLE_GUIDANCE: dict[ClinicalJudgeRole, tuple[list[str], list[str], list[str]]] = {
    "source_faithfulness": (
        [
            "Reject any clinical content that is unsupported by the source pages.",
            "Flag wording that overstates or broadens the source statement.",
        ],
        ["Escalate any unsupported recommendation, threshold, or contraindication."],
        ["source-grounding", "unsupported-claims"],
    ),
    "completeness": (
        [
            "Check whether clinically material thresholds, actions, caveats, and exceptions "
            "visible in the source are missing from the artifact."
        ],
        ["Use document-level flags when major sections or recommendation units are absent."],
        ["coverage", "missing-content"],
    ),
    "clinical_logic_consistency": (
        [
            "Check for contradictions between recommendations, thresholds, follow-up intervals, "
            "and contraindications.",
        ],
        ["Flag any internally inconsistent or clinically incoherent logic."],
        ["consistency", "contraindications"],
    ),
    "provenance_traceability": (
        [
            "Every actionable item must have a verbatim source quote and source location metadata."
        ],
        ["Reject artifacts that cannot be traced back at a granular level."],
        ["traceability", "provenance"],
    ),
    "normalization_correctness": (
        [
            "Normalized statements must preserve the meaning of the source quote without adding "
            "new claims."
        ],
        ["Flag normalization that changes scope, actors, or clinical intent."],
        ["normalization", "meaning-preservation"],
    ),
    "downstream_representation": (
        [
            "Downstream structured records, embedding units, RAG documents, and graph edges must "
            "remain semantically equivalent to the canonical source-grounded units."
        ],
        ["Flag downstream projections that lose provenance or distort relations."],
        ["projection-fidelity", "representation-consistency"],
    ),
}


@dataclass(frozen=True)
class ClinicalConsensusPolicy:
    """Gate thresholds for clinical consensus decisions."""

    min_role_score: float = 0.7
    completeness_min_score: float = 0.8
    min_agreement: float = 0.67
    min_high_risk_agreement: float = 0.8
    reject_on_any_wrong: bool = True
    reject_on_traceability_gap: bool = True


@dataclass(frozen=True)
class ClinicalConsensusRoleResult:
    """One role-specific panel outcome plus derived gate signals."""

    role: ClinicalJudgeRole
    result: JudgePanelResult
    normalized_score: float
    has_wrong_flag: bool
    has_traceability_gap: bool
    below_threshold: bool
    requires_escalation: bool


@dataclass(frozen=True)
class ClinicalConsensusResult:
    """Aggregate consensus decision over multiple clinical judge roles."""

    artifact_type: ClinicalArtifactType
    risk_level: ArtifactRisk
    role_results: list[ClinicalConsensusRoleResult]
    accepted: bool
    requires_human_review: bool
    rejection_reasons: list[str] = field(default_factory=list)


class ClinicalConsensusEngine:
    """Run specialized judge panels and apply a fail-closed policy."""

    def __init__(
        self,
        role_panels: dict[ClinicalJudgeRole, LLMJudgePanel],
        *,
        policy: ClinicalConsensusPolicy | None = None,
    ) -> None:
        self.role_panels = dict(role_panels)
        self.policy = policy or ClinicalConsensusPolicy()

    def validate_artifact(
        self,
        *,
        source_pages: list[bytes],
        artifact: list[dict] | dict[str, Any],
        artifact_type: ClinicalArtifactType = "extraction",
        risk_level: ArtifactRisk = "high",
        base_rubric: ValidationRubric | None = None,
        active_roles: list[ClinicalJudgeRole] | None = None,
    ) -> ClinicalConsensusResult:
        roles = active_roles or self._default_roles_for_artifact(artifact_type)
        role_results: list[ClinicalConsensusRoleResult] = []
        rejection_reasons: list[str] = []
        requires_human_review = False
        agreement_floor = (
            self.policy.min_high_risk_agreement
            if risk_level == "high"
            else self.policy.min_agreement
        )

        for role in roles:
            panel = self.role_panels.get(role)
            if panel is None:
                raise ValueError(f"No panel configured for clinical judge role: {role}")
            rubric = self._build_role_rubric(role, artifact_type, base_rubric)
            panel_result = panel.validate(
                source_pages=source_pages,
                extracted=artifact,
                rubric=rubric,
            )
            normalized_score = _normalized_score(panel_result.aggregated_flags)
            has_wrong_flag = any(flag.severity == "wrong" for flag in panel_result.aggregated_flags)
            has_traceability_gap = role == "provenance_traceability" and any(
                flag.severity != "ok" for flag in panel_result.aggregated_flags
            )
            threshold = (
                self.policy.completeness_min_score
                if role == "completeness"
                else self.policy.min_role_score
            )
            below_threshold = normalized_score < threshold
            requires_escalation = panel_result.agreement_score < agreement_floor
            role_results.append(
                ClinicalConsensusRoleResult(
                    role=role,
                    result=panel_result,
                    normalized_score=normalized_score,
                    has_wrong_flag=has_wrong_flag,
                    has_traceability_gap=has_traceability_gap,
                    below_threshold=below_threshold,
                    requires_escalation=requires_escalation,
                )
            )

            if self.policy.reject_on_any_wrong and has_wrong_flag:
                rejection_reasons.append(
                    f"{role} identified unsupported or incorrect clinical content"
                )
            if self.policy.reject_on_traceability_gap and has_traceability_gap:
                rejection_reasons.append("provenance_traceability found incomplete traceability")
            if below_threshold:
                rejection_reasons.append(f"{role} score below threshold")
            if requires_escalation:
                requires_human_review = True

        accepted = not rejection_reasons and not requires_human_review
        return ClinicalConsensusResult(
            artifact_type=artifact_type,
            risk_level=risk_level,
            role_results=role_results,
            accepted=accepted,
            requires_human_review=requires_human_review,
            rejection_reasons=_dedupe(rejection_reasons),
        )

    @staticmethod
    def _default_roles_for_artifact(
        artifact_type: ClinicalArtifactType,
    ) -> list[ClinicalJudgeRole]:
        if artifact_type == "extraction":
            return list(_ROLE_ORDER[:-1])
        return list(_ROLE_ORDER)

    @staticmethod
    def _build_role_rubric(
        role: ClinicalJudgeRole,
        artifact_type: ClinicalArtifactType,
        base_rubric: ValidationRubric | None,
    ) -> ValidationRubric:
        base = base_rubric or ValidationRubric(scoring_mode="likert_1_5")
        field_checks, item_checks, aspects = _ROLE_GUIDANCE[role]
        return ValidationRubric(
            vendor_id=base.vendor_id,
            field_checks=[*base.field_checks, *field_checks],
            item_level_checks=[
                *base.item_level_checks,
                *item_checks,
                f"Artifact type under review: {artifact_type}.",
            ],
            custom_system_suffix=base.custom_system_suffix,
            few_shot_examples=list(base.few_shot_examples),
            scoring_mode=base.scoring_mode,
            evaluation_aspects=[*base.evaluation_aspects, *aspects],
        )


def _normalized_score(flags: list[ValidationFlag]) -> float:
    if not flags:
        return 1.0
    total = 0.0
    for flag in flags:
        if flag.score:
            total += max(min(flag.score, 5), 1) / 5
        elif flag.severity == "ok":
            total += 1.0
        elif flag.severity == "suspect":
            total += 0.6
        else:
            total += 0.2
    return total / len(flags)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
