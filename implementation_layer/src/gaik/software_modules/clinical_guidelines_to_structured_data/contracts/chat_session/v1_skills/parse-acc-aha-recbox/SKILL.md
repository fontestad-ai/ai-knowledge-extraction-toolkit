---
name: parse-acc-aha-recbox
description: Detect and parse ACC/AHA recommendation boxes, supportive text, and adjacent evidence/drug tables from the 2025 HBP Guideline PDF into the Structured Anchored Intermediate Representation (SAIR), with multi-engine consensus, fail-closed enums, and full source anchoring.
namespace: cpg-htn-2025-acc-aha
category: parse
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> [--pages <range>] [--engines <list>] [--dpi <int>] [--strict] [--resume]"
---

# parse-acc-aha-recbox

Parse ACC/AHA-formatted recommendation boxes, their Recommendation-Specific Supportive Text, and adjacent evidence/drug tables from the conditioned 2025 HBP Guideline working set into the Structured Anchored Intermediate Representation (SAIR). Every cell is established via multi-engine consensus, every COR/LOE value is validated against a closed enum, and every emitted region is anchored to `(pdf_sha256, page, bbox, char_span)`.

This skill is the source-of-truth producer for downstream `extract-recommendation-cor-loe`. It does **not** decide what is "a recommendation"; it deterministically reconstructs the rows, cells, and adjacent paragraphs that recommendation extraction will consume. It refuses to publish ambiguous parses and routes every dispute to the parse-time reconciliation queue.

Posture: **caution over velocity, fidelity over coverage, verbatim over paraphrase.** Fail-closed on every unresolved disagreement. Two-person rule on every queue resolution that touches a recommendation row, COR, LOE, threshold, drug, or population scope.

## When to Use

Invoke this skill **after** the pre-parse conditioning skills (`parse-prepare-pdf`, `parse-detect-layout`, `parse-extract-text`) have produced:

- A fixity-verified, normalized working PDF at `work/<run-id>/02-normalized.pdf`
- A 300 DPI page raster set at `work/<run-id>/03-pages-300dpi/`
- Layout regions with dual-detector consensus per page
- Glyph-level text with reversible Unicode normalization
- A column model and a resolved reading order per page
- Footnote and superscript anchors

Typical trigger points:

- First parse of a freshly acquired 2025 HBP Guideline PDF (full document run)
- Re-parse of a page range after errata detection or tooling-lockfile change
- Targeted re-run of disputed regions following Phase 2 reconciliation queue resolutions

Do **not** invoke this skill on raw, unconditioned PDFs. Skipping pre-parse conditioning bypasses the controls that this skill assumes.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the in-progress SAIR JSON document at `work/<run-id>/sair.json`. Must already contain Phase 2.0–2.2 outputs and a valid `tools_lock`. The skill writes back into this document atomically. |
| `--pages <range>` | no | `all` | Page range to process (e.g., `1-12,40-44`). Defaults to every page whose layout regions include a `table` candidate. |
| `--engines <list>` | no | `camelot-lattice,camelot-stream,tabula-lattice,tabula-stream,pdfplumber,vlm-tablemaster` | Comma-separated table extraction engines to run in parallel. At least four must be enabled; the skill refuses to run with fewer. |
| `--dpi <int>` | no | `300` | Re-render DPI for vision-language fallback on disputed cells. `600` is auto-elevated for any region flagged as fine-ruled or merged-cell. |
| `--strict` | no | `true` | Fail-closed on any enum violation, cell-disputed state, or schema mismatch. Setting `--strict false` is **never permitted** for clinical-content regions; the flag exists only for parser development against fixtures. |
| `--resume` | no | `false` | Resume from the last persisted region in `sair.json`. Required when re-running after a queue resolution. |

## Operation

### 1. Preflight

1. Validate `sair-path` against `schemas/sair.yaml`. Fail-fast if `tools_lock`, `pages[].regions`, `column_model`, or `reading_order_index` are missing for any page in scope.
2. Confirm `pdf_sha256` in `sair.source` matches the on-disk normalized PDF; mismatch → BLOCK.
3. Confirm at least four table extraction engines are configured and reachable; otherwise BLOCK.
4. Load the closed enums:
   - `COR ∈ { I, IIa, IIb, III: No Benefit, III: Harm }`
   - `LOE ∈ { A, B-R, B-NR, C-LD, C-EO }`
   These are loaded from `schemas/acc-aha-grading.yaml` and never inlined.

### 2. Table region candidate generation (encodes §3.3 Task 2.3.1)

For each in-scope page:

1. Take the union of:
   - Layout-detector `table` boxes (from Phase 2.1.2 dual-detector consensus).
   - Vector ruling lines from `pdfplumber` (horizontal + vertical line clusters).
   - OpenCV-detected line segments on the 300 DPI raster (Hough + morphology).
2. Merge overlapping candidates whose IoU ≥ 0.6 into a single `table-candidate` region.
3. Persist each candidate with: `region_id`, `page`, `bbox`, `evidence: [layout|vector|raster]`, and `provisional_class: unknown`.
4. Threats controlled: F8 (table structure), F11 (raster-only tables), F13 (page-split tables — flagged when a candidate touches the bottom margin and a sibling candidate touches the top of the next page).

### 3. Multi-engine extraction (encodes §3.3 Task 2.3.2)

For each `table-candidate`, run **all** configured engines independently:

1. `camelot-lattice` (ruled tables).
2. `camelot-stream` (whitespace-ruled tables).
3. `tabula-lattice` and `tabula-stream`.
4. `pdfplumber.extract_table` with explicit `vertical_strategy` and `horizontal_strategy` derived from the candidate's vector lines.
5. A vision-language extractor (`Marker` / `TableMaster` / Donut-table) on the rasterized region at the selected DPI.

For each engine output, persist:

- The full grid with per-cell text, cell `bbox`, and engine name.
- The engine's confidence score (where exposed).
- A `parse_log` entry with engine version (from `tools_lock`).

Engines run in parallel; failures of one engine do not block the others, but at least four must succeed per candidate. Otherwise the candidate is escalated as `engine-quorum-failure`.

### 4. Cell-level reconciliation (encodes §3.3 Task 2.3.3)

For each candidate that produced ≥ 4 successful parses:

1. Align grids by row and column header text using normalized-string matching (NFC, case-folded, whitespace-collapsed). Header alignment failures themselves are escalated as `header-alignment-failure`.
2. For every aligned cell, compute the majority value across engines after the same normalization.
3. Classify each cell:
   - `cell-consensus` when ≥ 4 of 5 engines agree.
   - `cell-quorum` when exactly 3 of 5 agree (logged; advances only for non-clinical-content cells).
   - `cell-disputed` when < 3 of 5 agree.
4. Any `cell-disputed` state in a row that is later classified as `acc-aha-recommendation-box` (see §5) is a **hard escalation**; the row does not enter the SAIR's recommendation-box channel until resolved.
5. Cells where original NFC text differs from the consensus form retain both: `text_consensus` (the canonical value) and `text_variants` (per-engine outputs with bboxes).

### 5. Recommendation-box schema detection (encodes §3.3 Task 2.3.4)

For each reconciled table:

1. Detect the ACC/AHA recommendation-box schema by all of the following, evaluated together:
   - The header row (after consensus) contains tokens matching `^COR$` or `^Class of Recommendation$` **and** `^LOE$` or `^Level of Evidence$`, with exact, case-insensitive match modulo NFC.
   - A third column exists whose header matches `^Recommendation(s)?$`.
   - The number of body rows is ≥ 1 and each body row has non-empty cells in all three columns after consensus.
2. If the schema matches, set `schema_detected: acc-aha-recommendation-box` on the table region. If only some heuristics match, set `schema_detected: acc-aha-recommendation-box-candidate` and escalate as `schema-partial-match`.
3. For each body row of a confirmed recommendation box, validate:
   - The COR cell value, after NFC + whitespace-collapse, is exactly one member of the COR enum. Any deviation → `enum-violation`. **Never auto-correct.** Examples like `IIA`, `2a`, `Class IIa`, or stray footnote markers in the COR cell all escalate.
   - The LOE cell value is exactly one member of the LOE enum. Identical fail-closed handling.
4. Capture the recommendation cell's text **verbatim** (NFC, with the reversible normalization log retained) along with:
   - The cell `bbox` and the per-character `char_span` covering that bbox in the underlying glyph stream.
   - Any superscripts present, resolved to footnote IDs from Phase 2.2.5. Unresolved superscripts → `footnote-orphan` and the row is held.
5. Emit one `recommendation-box-row` SAIR record per validated row, with:
   - `region_id` (deterministic from `pdf_sha256 + page + row_bbox`).
   - `cor`, `loe`, `text_verbatim`, `cell_bboxes`, `char_spans`, `footnote_refs`, `section_path` (resolved from the heading stack at this position in the reading order).
   - `consensus_state: cell-consensus`.
   - `parent_table_region_id`.

Threats controlled: F2 (cell mis-association), F8 (merged/rotated cells), F14 (supportive text mistaken for recommendation).

### 6. Recommendation-Specific Supportive Text association (encodes §3.3 Task 2.3.5)

For each emitted recommendation-box row:

1. Walk forward in reading order from the recommendation box. Collect contiguous text regions (class `text`) until one of these stop conditions:
   - The next region is another `acc-aha-recommendation-box`.
   - A section heading is encountered (heading-stack depth changes).
   - A figure or non-supportive table appears.
   - The reading-order continuity check fails (column or page break without a continuation cue).
2. Confirm the candidate block is supportive text using both:
   - A heading regex in the immediately-preceding text region matching `Recommendation-Specific Supportive Text` (case-insensitive, hyphen-tolerant), **or**
   - The block immediately follows the recommendation box in reading order with no intervening heading and the typographic style matches the supportive-text body style learned for this document.
3. Persist as a separate `supportive_text` field on the row, with its own `region_ids`, `char_spans`, and `footnote_refs`. **Never merge supportive text into the recommendation text.**
4. Where a supportive block could plausibly bind to two adjacent recommendations (e.g., a single block following two recommendation boxes that share a numbered group), bind it to **all** plausible parents and flag `supportive-multi-bind` for §8 reconciliation.

### 7. Drug, lab, and evidence tables (encodes §3.3 Task 2.3.6)

For tables that did **not** match the recommendation-box schema:

1. Classify against the additional schemas in `schemas/acc-aha-table-schemas.yaml`:
   - `drug-table` when header tokens include any of `Drug`, `Class`, `Dose`, `Daily Dose`, `Usual Dose`, `Comments` and the body rows match RxNorm ingredient class headers within the HTN scope.
   - `lab-table` when headers match LOINC analyte families (e.g., `K+`, `Cr`, `eGFR`, `Aldosterone`, `Renin`).
   - `evidence-table` when headers include `Trial`, `N`, `Comparator`, `Outcome`, `Effect`.
   - `other` otherwise.
2. Validate header text against the controlled vocabulary for that schema. Header tokens not in the controlled vocabulary → `header-unmapped` and the table is held until §8 review.
3. Preserve merged-cell ranges explicitly with `cell_span: { row_start, row_end, col_start, col_end }`. Do **not** flatten merged cells; downstream skills depend on the merge geometry.
4. Persist row schemas explicitly. Multi-line cells retain internal newlines; bullet markers and en/em dashes used as range separators are preserved verbatim with normalization metadata.

### 8. Reconciliation queue handoff

For every flagged item — `engine-quorum-failure`, `header-alignment-failure`, `cell-disputed`, `enum-violation`, `schema-partial-match`, `footnote-orphan`, `supportive-multi-bind`, `header-unmapped`, `page-split-table` — emit a queue entry containing:

- The raster crop of the disputed region at 600 DPI.
- All engine outputs for affected cells, side-by-side.
- The proposed parse and the specific failure reason.
- A `decision_required` field listing the exact options (e.g., for `enum-violation`: `accept-as-typo`, `correct-and-record`, `defer-to-SME-panel`).

The skill never resolves these itself. Two-person rule applies to every clinical-content resolution. Each resolution emits a W3C PROV `Activity` and an updated `consensus_state` on the affected row.

### 9. SAIR write-back

1. Acquire an exclusive lock on `sair.json`.
2. Append/upsert all new and updated regions atomically.
3. Update `sair.run.steps[]` with this skill's invocation: tool versions, pages processed, engines used, counts of consensus / quorum / disputed cells, counts of recommendation-box rows emitted, queue entries created.
4. Compute and persist a SHA-256 of the SAIR document; record into `sair.fixity.sair_sha256`.
5. Release the lock.

### 10. Determinism and reproducibility

- All engines are version-pinned via `tools_lock`.
- Engine input bytes (cropped page rasters, vector-line strategies) are hashed; identical inputs produce identical outputs across runs (excluding engines that are not deterministic — those are flagged in `tools_lock` as `nondeterministic` and cannot be the sole basis for `cell-consensus`).
- Re-running this skill on the same SAIR with the same parameters and lockfile must produce a byte-identical SAIR section for the in-scope pages, modulo `processed_at` timestamps recorded with `now-skew-tolerance`.

## DQA Gates Enforced By This Skill

| Gate | Condition for advance |
|---|---|
| **G2.3-A** Recommendation-box completeness | Every detected recommendation box on in-scope pages has every row reconciled to `cell-consensus` or escalated. No silent drops. |
| **G2.3-B** Enum strictness | 100% of COR and LOE cells in confirmed recommendation boxes match the closed enums verbatim (NFC, whitespace-collapsed). |
| **G2.3-C** Verbatim capture | 100% of recommendation cells have `text_verbatim` plus reversible normalization log; no paraphrase, no ASCII fold. |
| **G2.3-D** Footnote integrity | 100% of superscripts in recommendation cells are resolved to footnote IDs or escalated. |
| **G2.3-E** Supportive-text disjointness | 0 recommendation rows have supportive text merged into `text_verbatim`. |
| **G2.3-F** Engine quorum | Every advanced row reached `cell-consensus` (≥ 4 of 5 engines). `cell-quorum` rows are not allowed in recommendation boxes. |
| **G2.3-G** Reproducibility | Re-run on identical inputs and lockfile produces byte-identical recommendation-box section in SAIR. |

Failure of any gate → BLOCK. The orchestrator (`flow-hbp-2025-build`) does not proceed to `extract-recommendation-cor-loe` until all gates are green.

## Outputs

- Updated SAIR document at `<sair-path>` containing:
  - Reconciled `table` regions with `schema_detected` set.
  - Per-row `recommendation-box-row` records with COR, LOE, verbatim text, anchors, and supportive-text references.
  - Drug, lab, and evidence tables with explicit row schemas and merged-cell geometry.
- Reconciliation queue entries at `work/<run-id>/queue/parse/recbox/`.
- Per-run report at `reports/parse-recbox-<run-id>.md` with:
  - Counts: pages processed, candidates generated, engines per candidate, consensus distribution, recommendation rows emitted, queue entries opened.
  - Per-page heatmap of disputed cells.
  - Lockfile diff vs. previous run (if any).
- W3C PROV bundle update at `provenance/parse-recbox-<run-id>.jsonld`.
- An `activity.log` append documenting invocation, parameters, gates passed/failed, and operator identity.

## Error Handling

- **Pre-parse outputs missing or stale.** Fail-fast with the missing field path; instruct operator to rerun the relevant Phase 2.0–2.2 skills.
- **PDF SHA mismatch.** BLOCK; emit a `version-drift` event; do not auto-update.
- **Insufficient engines.** BLOCK; surface which engines failed to initialize (binary missing, license check, model unavailable).
- **Enum violation in COR/LOE.** Never auto-correct. Hold the row, escalate to queue, continue with remaining rows.
- **Footnote-orphan.** Hold the row; remaining rows continue.
- **Cell-disputed in recommendation row.** Hold the row; remaining rows continue.
- **Schema partial match.** Persist as `acc-aha-recommendation-box-candidate`; escalate; do not emit recommendation-box rows from it.
- **Engine-side crash mid-page.** Retry once with the same input; on second failure, log the engine as `quorum-failed` for that candidate and continue with remaining engines.
- **SAIR lock contention.** Wait up to a configured timeout, then fail-closed; concurrent writers are not supported on the same SAIR document.

## Examples

```bash
# Full-document first parse over the conditioned 2025 HBP Guideline working set
parse-acc-aha-recbox work/run-2026-04-30/sair.json

# Targeted re-run of pages 40–44 after a queue resolution, resuming from the last persisted region
parse-acc-aha-recbox work/run-2026-04-30/sair.json \
  --pages 40-44 \
  --resume

# Disputed-region re-render at 600 DPI with the vision-language engine emphasized
parse-acc-aha-recbox work/run-2026-04-30/sair.json \
  --pages 12,57 \
  --engines camelot-lattice,camelot-stream,pdfplumber,vlm-tablemaster \
  --dpi 600