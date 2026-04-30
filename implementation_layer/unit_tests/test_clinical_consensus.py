"""Tests for the clinical consensus judge layer."""

from gaik.software_components.validators import (
    ClinicalConsensusEngine,
    ClinicalConsensusPolicy,
    ValidationFlag,
)
from gaik.software_components.validators.llm_judge.schema import (
    JudgePanelResult,
    JudgeUsage,
    ValidationResult,
)


class StubPanel:
    def __init__(self, *, flags, agreement_score=1.0):
        self.flags = flags
        self.agreement_score = agreement_score

    def validate(self, *, source_pages, extracted, rubric):
        del source_pages, extracted, rubric
        result = ValidationResult(
            flags=self.flags,
            raw_judge_text="{}",
            usage=JudgeUsage(provider="stub", model="stub"),
        )
        return JudgePanelResult(
            per_judge=[result, result],
            aggregated_flags=self.flags,
            agreement_score=self.agreement_score,
            total_cost_usd=0.0,
            total_duration_s=0.0,
        )


def test_clinical_consensus_accepts_clean_high_agreement_artifact():
    flags = [ValidationFlag(item_index=0, field="source_quote", severity="ok", score=5)]
    engine = ClinicalConsensusEngine(
        {
            "source_faithfulness": StubPanel(flags=flags),
            "completeness": StubPanel(flags=flags),
            "clinical_logic_consistency": StubPanel(flags=flags),
            "provenance_traceability": StubPanel(flags=flags),
            "normalization_correctness": StubPanel(flags=flags),
        }
    )

    result = engine.validate_artifact(
        source_pages=[b"page"],
        artifact={"items": []},
        artifact_type="extraction",
    )

    assert result.accepted is True
    assert result.requires_human_review is False
    assert result.rejection_reasons == []


def test_clinical_consensus_rejects_wrong_or_traceability_gaps():
    wrong = [ValidationFlag(item_index=0, field="recommendation", severity="wrong", score=1)]
    gap = [ValidationFlag(item_index=0, field="source_quote", severity="suspect", score=2)]
    engine = ClinicalConsensusEngine(
        {
            "source_faithfulness": StubPanel(flags=wrong),
            "completeness": StubPanel(flags=gap),
            "clinical_logic_consistency": StubPanel(flags=gap),
            "provenance_traceability": StubPanel(flags=gap),
            "normalization_correctness": StubPanel(flags=gap),
        },
        policy=ClinicalConsensusPolicy(min_role_score=0.6, completeness_min_score=0.6),
    )

    result = engine.validate_artifact(
        source_pages=[b"page"],
        artifact={"items": []},
        artifact_type="extraction",
    )

    assert result.accepted is False
    assert any(
        "unsupported or incorrect clinical content" in reason
        for reason in result.rejection_reasons
    )
    assert any("traceability" in reason for reason in result.rejection_reasons)


def test_clinical_consensus_escalates_low_agreement_high_risk_artifact():
    flags = [ValidationFlag(item_index=0, field="recommendation", severity="ok", score=5)]
    engine = ClinicalConsensusEngine(
        {
            "source_faithfulness": StubPanel(flags=flags, agreement_score=0.5),
            "completeness": StubPanel(flags=flags, agreement_score=0.5),
            "clinical_logic_consistency": StubPanel(flags=flags, agreement_score=0.5),
            "provenance_traceability": StubPanel(flags=flags, agreement_score=0.5),
            "normalization_correctness": StubPanel(flags=flags, agreement_score=0.5),
        }
    )

    result = engine.validate_artifact(
        source_pages=[b"page"],
        artifact={"items": []},
        artifact_type="extraction",
        risk_level="high",
    )

    assert result.accepted is False
    assert result.requires_human_review is True
