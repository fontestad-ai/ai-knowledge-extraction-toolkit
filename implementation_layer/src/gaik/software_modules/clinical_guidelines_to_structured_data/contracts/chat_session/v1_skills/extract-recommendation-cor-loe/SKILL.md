---
name: extract-recommendation-cor-loe
description: Construct atomic clinical recommendation records from SAIR recommendation-box rows via triple-modal consensus (PDF-text, vision-language, OCR), preserve native ACC/AHA COR and LOE verbatim, decompose into atomic units with span-only outputs, and gate every record at the non-overridable Gate 1 SME extraction review.
namespace: cpg-htn-2025-acc-aha
category: extract
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> <records-path> [--rows <ids>] [--llm-pair <a,b>] [--vlm <name>] [--ocr <list>] [--similarity <float>] [--resume]"
---

# extract-recommendation-cor-loe

Construct atomic clinical recommendation records from the recommendation-box rows produced by `parse-acc-aha-recbox`, preserving the source's native ACC/AHA Class of Recommendation (COR) and Level of Evidence (LOE) **verbatim**, and gate every record at the non-overridable Gate 1 SME extraction review.

This skill implements §4.1 (Recommendation candidate construction) and §4.2 (Atomicity decomposition) of the Parse + Extraction Phase Specification. It is the **first clinically-loaded** step in the pipeline: nothing it emits enters terminology binding, FHIR structuring, or CQL authoring without two independent specialist signoffs.

Posture: **caution over velocity, fidelity over coverage, verbatim over paraphrase.** Triple-modal consensus is mandatory. Span-only LLM outputs are mandatory. Two-person SME signoff is mandatory. Any uncertainty is escalated, never resolved silently. No LLM may emit free-text recommendation content. No COR or LOE may be auto-corrected. No record advances on fewer than three independent extractions agreeing.

## When to Use

Invoke this skill **after** `parse-acc-aha-recbox` has produced a SAIR document in which:

- All in-scope recommendation-box rows reached `cell-consensus`.
- All COR and LOE cells passed enum strictness (G2.3-B).
- All recommendation-cell text is captured verbatim with reversible normalization metadata (G2.3-C).
- All superscripts are resolved to footnote IDs (G2.3-D).
- All supportive-text blocks are bound separately and never merged into recommendation text (G2.3-E).
- Engine quorum (≥4 of 5) is met across the recommendation-box channel (G2.3-F).

Typical trigger points:

- First extraction pass after Phase 2 (PARSE) DQA gates G2-A through G2-G are green.
- Targeted re-run of specific recommendation rows after Gate 1 reviewer requests rework.
- Re-extraction after a tooling-lockfile change, with regression evaluation against the golden set.

Do **not** invoke this skill if any Phase 2 gate is yellow or red, or if the SAIR fixity SHA differs from the manifest. Skipping these conditions invalidates the consensus controls this skill assumes.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the sealed SAIR document at `work/<run-id>/sair.json`. Must have `sair.fixity.sair_sha256` set and Phase 2 gates green. The skill reads this document and never mutates it. |
| `records-path` | yes | — | Output path for the recommendation records document (`work/<run-id>/records.json`), validated against `schemas/recommendation-record-htn.yaml`. The skill writes back atomically. |
| `--rows <ids>` | no | `all` | Comma-separated `recommendation-box-row` region IDs to process. Defaults to all rows in the SAIR for this run. |
| `--llm-pair <a,b>` | no | `claude-opus-<pinned>,gpt-class-<pinned>` | Two LLM identifiers from different families used for atomicity decomposition. Both must be pinned in `tools_lock`. The skill refuses to run with a single LLM. |
| `--vlm <name>` | no | `vlm-<pinned>` | Vision-language model used for the independent re-extraction over the rasterized recommendation-box row crop. Must be pinned in `tools_lock`. |
| `--ocr <list>` | no | `tesseract,paddleocr,surya` | OCR engines used for the independent OCR re-extraction. At least three must be enabled. |
| `--similarity <float>` | no | `0.99` | Minimum text similarity (NFC, whitespace-collapsed, character-level) required for triple-consensus on recommendation text. Lowering this value below `0.99` is **never permitted** in production runs. |
| `--resume` | no | `false` | Resume from the last persisted record. Required after a Gate 1 reviewer-driven rework. |

## Operation

### 1. Preflight

1. Validate `sair-path` against `schemas/sair.yaml`. Confirm:
   - `sair.fixity.sair_sha256` is present and matches the on-disk content.
   - All in-scope rows have `consensus_state: cell-consensus`.
   - All in-scope rows carry `cor`, `loe`, `text_verbatim`, `cell_bboxes`, `char_spans`, `footnote_refs`, and `section_path`.
2. Confirm `records-path` either does not exist (fresh run) or has `--resume` set with a matching `sair_sha256`.
3. Confirm the LLM pair, the VLM, and the OCR engines are reachable, version-pinned in `tools_lock`, and have non-zero per-call confidence-reporting hooks.
4. Load the closed enums from `schemas/acc-aha-grading.yaml`:
   - `COR ∈ { I, IIa, IIb, III: No Benefit, III: Harm }`
   - `LOE ∈ { A, B-R, B-NR, C-LD, C-EO }`
5. Load the HTN-typed Population enum from `schemas/recommendation-record-htn.yaml` (used in §4 below; PICO mapping itself is delegated to `pico-decompose-htn`, but population-completeness is checked here).
6. Refuse to run if any precondition fails. **Fail-closed.**

### 2. Recommendation candidate construction — extractor A (PDF-text, deterministic)

For each in-scope `recommendation-box-row`:

1. Construct `RecommendationDraft-A`:
   - `recommendation_id`: deterministic from `(pdf_sha256, page, row_bbox)` using the same hashing rule the parser used.
   - `cor`: read directly from the SAIR row's COR cell. Validate against the enum; mismatch is a precondition violation, not an extraction failure.
   - `loe`: identical handling.
   - `text_verbatim`: copied byte-for-byte from `sair.row.text_verbatim` (NFC, with the reversible normalization log retained).
   - `text_bbox`, `page`, `char_spans`: copied from SAIR.
   - `supportive_text_ids`: copied from SAIR.
   - `references`: footnote-resolved citation IDs from SAIR.
   - `section_path`: copied from SAIR (e.g., `["7", "7.3", "7.3.4 Pregnancy"]`).
2. **No paraphrase. No edits. No "clarifications." Verbatim only.**
3. Persist `RecommendationDraft-A` with provenance `extractor: A (pdf-text-deterministic)`.

Threats controlled: F2 (cell mis-association — caught by SAIR pre-checks), F14 (supportive text leakage — guaranteed by SAIR disjointness), F19 (LLM hallucination — A is fully deterministic).

### 3. Recommendation candidate construction — extractor V (vision-language)

For each row:

1. Render the row's bounding box from the 600 DPI page raster (re-rendering at 600 DPI if SAIR holds only 300 DPI, with a margin of `±32 px` to preserve cell borders). Persist the crop at `work/<run-id>/extract/crops/<row-id>.png`.
2. Submit the crop to the configured VLM with a strict tool schema that requires the model to return:
   ```json
   {
     "cor": "<one of the COR enum values, exactly>",
     "loe": "<one of the LOE enum values, exactly>",
     "text_verbatim": "<verbatim recommendation text, NFC>"
   }