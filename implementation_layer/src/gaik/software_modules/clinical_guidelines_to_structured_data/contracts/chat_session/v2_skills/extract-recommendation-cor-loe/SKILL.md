---
name: extract-recommendation-cor-loe
description: Phase-3 (P9) extraction skill for the cpg-htn-2025-acc-aha framework. Produces RecommendationRecordHTN instances by triple-modal consensus (deterministic-text A, VLM-vision V, OCR-fallback O) over recommendation cells already segmented by parse-acc-aha-recbox; decomposes recommendation text into AtomicUnit instances under a dual-LLM, family-distinct agreement rule; runs PICO and numeric-fact prechecks; opens Gate-1 cohorts on schemas/gate1-register.yaml; routes disagreements to the panel chair without majority-voting. Verbatim-only. No paraphrase. No COR/LOE editing. No batch acceptance. Post-Gate-1 records are immutable.
namespace: cpg-htn-2025-acc-aha
category: extract
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> [--records <list>] [--cohort-strategy <by-domain|single>] [--resume] [--dry-run]"
---

# extract-recommendation-cor-loe (refresh)

Phase-3 (P9) extraction skill for the `cpg-htn-2025-acc-aha` framework.
The skill produces `RecommendationRecordHTN` instances by **triple-modal
consensus** over the recommendation cells already segmented by
`parse-acc-aha-recbox`, decomposes the verbatim text into
`AtomicUnit` instances under a **dual-LLM, family-distinct agreement
rule**, runs the PICO and numeric-fact prechecks, opens **Gate-1
cohorts** against `schemas/gate1-register.yaml`, and is the only
authorized writer of records in state `gate-1-pending`. The skill is
the operational driver of Gate 1; the reviewer-interface is
`gate1-sme-review`.

This refresh aligns the skill exactly to the schemas drafted in this
thread:

- `schemas/acc-aha-grading.yaml` — closed COR/LOE enums.
- `schemas/sair.yaml` — input source-of-truth.
- `schemas/recommendation-record-htn.yaml` — output contract.
- `schemas/atomic-unit.yaml` — atomicity contract for child units.
- `schemas/gate1-register.yaml` — Gate-1 cohort register.
- `schemas/guideline-manifest-hbp-2025.yaml` — pin source for tools, terminology editions, TSAs, signature policy, and risk-engine identity.

Posture: **caution over velocity, fidelity over coverage, verbatim
over paraphrase.** No paraphrase of clinical text. No editing of
ACC/AHA COR or LOE. No batch acceptance. No silent re-extraction. No
LLM-only path. No reviewer self-pairing. No majority-voting on
disagreements. Held rows route to the reconciliation queue, never to a
silent fall-through.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P9** for a
  build whose SAIR is sealed (P8 complete) and whose
  `parse-acc-aha-recbox` outputs are present in
  `work/<run_id>/sair.json` under `recommendation_boxes[]`.
- A re-extraction is required after a Gate-1 reviewer recorded
  `accept-with-edit` and the orchestrator regenerated the affected
  record's atomic units (parent-edit-deletes-children per
  `AU-INV-24`).
- A held row in `work/<run_id>/queue/` has been resolved by the
  two-person rule and the orchestrator requests advancement.
- A targeted re-extraction is required after a `tools_lock` change
  authorized by a new manifest version.

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers.
- The SAIR document is not sealed (P8 must complete first).
- `parse-acc-aha-recbox` has not produced
  `recommendation_boxes[*]` of consensus state `agreed` or
  `awaiting-corroboration` for the rows under extraction.
- Any record advanced through Gate 1 in a prior cohort is being
  re-extracted (Gate 1 records are immutable; corrections require a
  new register version).

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the sealed SAIR document at `work/<run_id>/sair.json`, validated against `schemas/sair.yaml`. |
| `--records <list>` | no | `all` | Comma-separated list of recommendation row ids to extract (`row-<16hex>` per the SAIR's `recommendation_boxes[].rows[].row_id`). Defaults to every row not yet bound to a record. |
| `--cohort-strategy <by-domain\|single>` | no | `by-domain` | `by-domain` opens one Gate-1 cohort per domain group per the matrix in §10; `single` opens one cohort containing every record (used only when the cohort scope is institutional policy). |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted record. The skill rejects resume if the SAIR's `fixity.sair_sha256` has changed since session start. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned record set, the proposed cohort partition, and the dual-LLM family-distinct verification; do not execute extraction or open cohorts. |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production. |

## Operation

### 1. Preflight

1. Validate `sair-path` against `schemas/sair.yaml`. Reject on any
   invariant failure.
2. Resolve `guideline_manifest_ref` from the SAIR; verify the active
   manifest's `medical_director_signoff` cryptographically per
   `GM-INV-21`; verify `state == "active"` and
   `errata_watch.blockers_open == []` per `GM-INV-23`.
3. Verify `tools_lock.lock_sha` against canonicalized
   `tools_lock.items[]` per `GM-INV-08`.
4. Verify the **two-LLM family-distinct rule** at preflight:
   - Resolve `manifest.tools_lock.llm_pair[]`. Confirm exactly two
     entries (`GM-INV-09`).
   - Resolve each entry to a `tools_lock.items[]` of `kind == "llm"`.
   - Confirm the two LLMs are from **distinct vendor families** per
     the family-distinct rule (`AU-INV-09`). The schema's family
     classification is the ground-truth list maintained at
     `docs/llm-family-matrix.md`; CI verifies the matrix file exists
     and the two pinned LLMs map to distinct families.
   - Probe each LLM for liveness with a deterministic test prompt;
     record the response signature.
   - **Family-collapse → BLOCK.** If at any point the two LLMs map to
     the same family (vendor reorg, model rebrand, etc.), the build
     blocks with `family-distinct-rule-violated`; remediation is a
     new manifest version with a different pinned pair.
5. Verify the **VLM** referenced in `manifest.tools_lock.vlm` is
   reachable and on the pinned version.
6. Verify the **OCR engines** in `manifest.tools_lock.ocr_engines[]`
   are at least three; probe each.
7. Verify the **terminology server** is reachable at the pinned
   editions (deferred binding occurs at P10, but the server must be
   alive at P9 preflight to fail fast).
8. Verify the **TSAs** in `manifest.tsa_list[]`: at least one cert
   is currently within `cert_valid_*`.
9. Verify **input integrity**:
   - The SAIR is sealed (read-only flag set in
     `meta.write_back_lock_state == "sealed"`).
   - For each row in scope, the parent
     `recommendation_boxes[].consensus.state` is `agreed` or
     `awaiting-corroboration` (only these two are admissible at P9;
     `held` and `text-disputed` route to the queue).
   - Every row's `text_verbatim` is non-empty after Phase-2
     reversible normalization.
   - Every row has anchored `bbox` and `page` references on the
     conditioned PDF, recomputable byte-for-byte.
10. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Triple-modal consensus (mechanical)

For each row in scope, three independent extractor stacks produce
candidate records: **A** (deterministic text), **V** (VLM vision), **O**
(OCR-fallback). All three are independent reads against the same
source region; they are not allowed to consult each other's outputs.

#### 2.1 Extractor A — Deterministic text (no LLM)
- Input: `recommendation_boxes[].rows[]` from the SAIR (already produced
  by the five-engine table reconciliation in `parse-acc-aha-recbox`).
- Output: `RecommendationDraft-A` with the row's `text_verbatim`,
  `acc_aha_cor`, `acc_aha_loe`, supportive-text spans, and citation
  references pulled directly from SAIR cell coordinates.
- This extractor is **fully deterministic**: it does not call any LLM
  or VLM. Its output is byte-stable across re-runs given the same SAIR.

#### 2.2 Extractor V — VLM vision over rasterized region
- Input: the conditioned PDF rasterized at 600 DPI within the row's
  `bbox`, fed to the manifest-pinned VLM with a closed-prompt template
  ("Read the recommendation box. Return COR, LOE, and the verbatim
  recommendation text. Do not paraphrase. Do not interpret.").
- Output: `RecommendationDraft-V` with the same fields. The VLM is
  permitted to read tables and figures; it is forbidden from
  generating text not present in the raster.
- The VLM's output is post-validated character-by-character against
  the raster's OCR'd text (extractor A's text); any insertion or
  paraphrase causes the V draft to be rejected and the row marked
  `text-disputed`.

#### 2.3 Extractor O — OCR-fallback
- Input: the rasterized region.
- Output: `RecommendationDraft-O` with the verbatim recommendation
  text and COR/LOE strings. The OCR engines (≥3) reconcile their
  outputs first; only their consensus is forwarded as O.
- O exists as the tiebreaker on glyph-level disagreements between A
  and V (e.g., `≤` vs `<`, `mg` vs `mEq`).

#### 2.4 Three-way consensus
- Compute pairwise similarity (character-level, after Phase-2
  reversible normalization) for each (A,V), (A,O), (V,O) pair on:
  - `text_verbatim`
  - `acc_aha_cor`
  - `acc_aha_loe`
- Consensus state is set per the matrix in
  `extract-recommendation-cor-loe.spec.md` (this skill's spec
  document; the values are mirrored in
  `RecommendationRecordHTN.provenance.consensus.state`):

  | Pairwise minimum | Consensus state | Disposition |
  |---|---|---|
  | ≥ 0.99 across all three pairs | `agreed` | advance to atomicity |
  | ≥ 0.99 on (A,V) and (A,O), but (V,O) < 0.99 | `agreed-A-anchored` | advance with anchor flag |
  | < 0.99 on any pair | `held` | route to queue with proposal-diff |
  | text disputed (insertions) | `text-disputed` | route to queue; never auto-resolve |

- For COR and LOE specifically, the schema's closed enums make the
  comparison exact-string; any mismatch between extractors on COR or
  LOE is `held` regardless of text agreement.

#### 2.5 No-LLM-only path
- The skill **never** produces a record from LLM output alone. The
  LLM pair is used only for atomicity decomposition (§3); COR, LOE,
  and verbatim text are produced by A/V/O consensus.
- A record whose only support is an LLM output is rejected at the
  consensus step; this is enforced by the schema's
  `provenance.consensus.engines[]` requiring at least one of A/V/O
  per `INV-06` of `recommendation-record-htn.yaml`.

### 3. Atomicity decomposition (dual-LLM, family-distinct)

For every row that reaches `agreed` or `agreed-A-anchored`, the skill
decomposes the verbatim text into `AtomicUnit` instances. Atomicity is
the act of finding non-overlapping spans within `text_verbatim` whose
kind is one of:
