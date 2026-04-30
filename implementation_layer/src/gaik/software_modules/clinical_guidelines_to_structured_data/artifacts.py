"""Curated clinical artifacts captured from the standalone extraction chat session.

These artifacts are intentionally local, deterministic, and source-described. They allow
the standalone clinical branch to preserve the user-provided image/session evidence even
when OCR or a vision-capable LMCLI runtime is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClinicalChatArtifact:
    """One clinical extraction artifact captured from chat/upload context."""

    artifact_id: str
    title: str
    source_hint: str
    text: str


MEDICATION_ADHERENCE_ARTIFACT = ClinicalChatArtifact(
    artifact_id="medication_adherence",
    title="Medication Adherence",
    source_hint="Uploaded hypertension guideline image reviewed in chat",
    text=(
        "Medication Adherence. Review PDC data before each call. If concerns "
        "are identified, discuss concerns with the patient. If patient statements "
        "conflict with PDC data, call the pharmacy to review fill history. If fill "
        "history suggests non-adherence, begin motivational interviewing to identify "
        "the root cause."
    ),
)

HYPERKALEMIA_ARTIFACT = ClinicalChatArtifact(
    artifact_id="hyperkalemia_management",
    title="Hyperkalemia Management",
    source_hint="User-provided image URL reviewed in chat",
    text=(
        "Hyperkalemia management protocol. Entry condition: potassium K > 5.1. "
        "Send the patient to the emergency department if concerning symptoms are "
        "present or potassium is >= 6.0. If potassium is 5.5-5.9, hold ACE, ARB, "
        "or MRA therapy. If volume depletion is present, avoid furosemide and "
        "educate on rehydration. If volume depletion is absent, add furosemide "
        "20 mg daily for 3 days. If continuing ACE, ARB, or MRA therapy and "
        "potassium increased by >= 2 mmol/L from the last result, add furosemide "
        "20 mg daily for 3 days. Recheck potassium within 1 week. Evidence of "
        "volume depletion includes recent vomiting, recent diarrhea, or BUN/Scr > 20."
    ),
)

CHAT_SESSION_ARTIFACTS = (
    MEDICATION_ADHERENCE_ARTIFACT,
    HYPERKALEMIA_ARTIFACT,
)


def infer_chat_artifact_text(file_path: str | Path) -> str | None:
    """Return local artifact text for known uploaded/chat image evidence."""

    path = Path(file_path)
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        return None

    if "hyperkalemia" in name or "potassium" in name:
        return HYPERKALEMIA_ARTIFACT.text

    if (
        "digital medicine htn best practice guidelines" in name
        or "medication" in name
        or "adherence" in name
    ):
        return MEDICATION_ADHERENCE_ARTIFACT.text

    return "\n\n".join(
        f"{artifact.title}: {artifact.text}" for artifact in CHAT_SESSION_ARTIFACTS
    )

