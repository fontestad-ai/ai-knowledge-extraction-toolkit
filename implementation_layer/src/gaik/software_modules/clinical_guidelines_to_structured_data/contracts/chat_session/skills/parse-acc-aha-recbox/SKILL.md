---
name: parse-acc-aha-recbox
description: Phase-2 (P6) parse skill for the cpg-htn-2025-acc-aha framework. Detects ACC/AHA recommendation boxes on conditioned PDF pages, segments cells into the canonical (COR, LOE, Recommendation, Supportive Text, Citations) shape, runs five-engine table consensus over each cell, exact-string-validates COR and LOE against the closed enums, captures verbatim recommendation text under reversible normalization, anchors every cell to bbox + page on the conditioned PDF, and writes back into the SAIR document under recommendation_boxes[]. Disagreements route to the queue; figure-only or chart-derived rows are flagged awaiting_corroboration. No paraphrase. No COR/LOE coercion. No silent fall-through. Post-extraction SAIR is read-only at this region.
namespace: cpg-htn-2025-acc-aha
category: parse
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> [--pages <list>] [--engines <list>] [--strict] [--resume] [--dry-run]"
---

# parse-acc-aha-recbox (refresh)

Phase-2 (P6) parse skill for the `cpg-htn-2025-acc-aha` framework. The
skill detects ACC/AHA recommendation boxes on conditioned PDF pages,
segments each box's cells into the canonical
**(COR, LOE, Recommendation, Supportive Text, Citations)** shape, runs
**five-engine table consensus** over each cell, exact-string-validates
COR and LOE against the closed enums declared in
`schemas/acc-aha-grading.yaml`, captures the verbatim recommendation
text under reversible normalization, anchors every cell to `bbox + page`
on the conditioned PDF, and writes back into the
`schemas/sair.yaml`-validated SAIR document at
`work/<run_id>/sair.json` under `recommendation_boxes[]`.

This refresh aligns the skill exactly to the SAIR schema as drafted in
this thread. Disagreements between the five table engines route to the
reconciliation queue; figure-only or chart-derived rows are flagged
`awaiting_corroboration` and held until corroborated by the
text-derived consensus pass at P4 (`parse-extract-text`) or by an OCR
fallback at P7 (`parse-ocr-fallback`).

This skill does **not** extract recommendations as RecommendationRecord
instances — that is P9 (`extract-recommendation-cor-loe`). It does not
bind terminology — that is P10 (`bind-htn-vocab`). It does not run
PICO decomposition, numeric-fact extraction, drug-rule extraction,
contraindication mining, or risk-engine binding. Its single
responsibility is producing the SAIR sub-document
`recommendation_boxes[]` in a form that downstream phases can rely on
byte-for-byte.

Posture: **caution over velocity, fidelity over coverage, verbatim over
paraphrase.** No paraphrase of clinical text. No coercion of COR or
LOE values. No batch acceptance. No silent fall-through. No engine is
bypassed. Every disagreement either advances under explicit consensus
state (`agreed`, `agreed-A-anchored`) or routes to the queue (`held`,
`text-disputed`, `awaiting-corroboration`).

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P6** for a
  build whose conditioned PDFs are pinned (P2 complete), layout is
  detected (P3 complete), text is extracted (P4 complete), and figures
  are extracted (P5 complete).
- A re-parse of a specific page set is required after a queue
  resolution touched the SAIR's text-derived rows that this skill's
  `awaiting_corroboration` flag depends on.
- A targeted re-run is required after a `tools_lock` change authorized
  by a new manifest version (e.g., a table-engine pin update).
- A regression run is needed against the framework's golden box set
  after a schema or skill change.

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers (`GM-INV-23`).
- The SAIR document is already sealed (`meta.write_back_lock_state ==
  "sealed"`); the skill writes into the SAIR's `recommendation_boxes[]`
  region and refuses to do so on a sealed document.
- Pages requested for parsing have not yet been processed by P3, P4,
  and P5 (the box detection consumes layout regions and the
  text-derived corroboration consumes text spans).
- A prior P6 run produced rows in the queue that have not been
  resolved by the two-person rule (the skill refuses to overwrite
  unresolved queue entries).

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the in-flight SAIR document at `work/<run_id>/sair.json`, validated against `schemas/sair.yaml`. The skill writes back atomically under the SAIR write-back lock. |
| `--pages <list>` | no | `all` | Comma-separated page indices on the conditioned PDF for the active source role (`main-guideline` by default; the skill accepts a `--source <role>` form for the rare case of supplement-borne boxes; non-default sources require explicit operator authorization). Defaults to all pages where layout detection produced a box-class region. |
| `--engines <list>` | no | the manifest's pinned five | Comma-separated engine ids from `manifest.tools_lock.items[]` of `kind == "table-engine"` and `kind == "vlm"`. The default is the manifest's pinned five (camelot + tabula + pdfplumber + tablemaster + donut-table). Listing fewer than five blocks unless `--strict false` (which is **never permitted in production**). |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production; the flag exists only for fixture and golden-set development. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted page. The skill rejects resume if the SAIR's `fixity.sair_sha256` has changed since session start. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned page set, the engine roster, and the expected output regions; do not modify the SAIR. Permitted in production for change-control reviews. |

## Operation

### 1. Preflight

1. Validate `sair-path` against `schemas/sair.yaml`. Reject on any
   invariant failure.
2. Resolve `guideline_manifest_ref` from the SAIR; verify the active
   manifest's `medical_director_signoff` cryptographically per
   `GM-INV-21`; verify `state == "active"` and
   `errata_watch.blockers_open == []` per `GM-INV-23`.
3. Verify `tools_lock.lock_sha` against canonicalized
   `tools_lock.items[]` per `GM-INV-08`. The skill consumes:
   - At least three `kind == "table-engine"` entries (camelot, tabula,
     pdfplumber are the framework defaults).
   - At least two `kind == "vlm"` entries (tablemaster, donut-table
     are the framework defaults).
   - The manifest's `tools_lock.ocr_engines[]` (≥3) for OCR fallback
     within this skill on raster-only cells.
4. Probe each engine in the run set for liveness with a deterministic
   probe table; confirm version pin matches the manifest's
   `tools_lock.items[*].pin`. Failure → BLOCK with
   `engine-pin-mismatch`.
5. Verify the SAIR is **not sealed**:
   `meta.write_back_lock_state ∈ {"open", "appending"}`. A `sealed`
   SAIR refuses writes; the skill BLOCKs.
6. Verify the SAIR's per-page artifacts produced upstream are
   complete for every page in `--pages`:
   - `pages[*].layout_regions[]` populated by P3 with at least one
     region of class `box`, `table`, or `recbox`.
   - `pages[*].text_spans[]` populated by P4 with reversible-
     normalization log.
   - `pages[*].figures[]` populated by P5.
   - `pages[*].pdf_anchor.bbox` and `pages[*].pdf_anchor.page` non-null
     and recomputable byte-for-byte against the conditioned PDF.
7. Verify the active manifest's pinned **conditioned PDF SHA-256**
   matches the SAIR's recorded `sources[role].conditioned_pdf_sha256`.
   Mismatch → BLOCK; the skill refuses to operate on a PDF whose pin
   does not match the manifest.
8. Acquire the SAIR write-back lock. The skill is the only writer
   into `recommendation_boxes[]` during its run.
9. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Box detection

For each page in `--pages`:

1. Resolve the page's layout regions of class `box`, `table`, or
   `recbox`.
2. For each region, compute a **box probability** under the closed
   feature set:
   - Region aspect ratio is consistent with ACC/AHA recbox proportions
     observed in the framework's golden set.
   - Region contains at least one cell whose visual style matches the
     ACC/AHA color-shading scheme for COR and LOE (the scheme is
     pinned in `docs/acc-aha-recbox-style-matrix.md`; CI verifies the
     file exists and is consulted).
   - Region's text-span density is bounded; pure-figure regions are
     excluded by the figure-class filter from P5.
3. A region with box probability ≥ the manifest-pinned threshold
   (default 0.85) is admitted as a candidate recbox. Lower-probability
   regions are emitted as advisory hints only and are **not** parsed
   by this skill (they are visible to operators in the SAIR's
   `pages[*].layout_regions[]` but produce no `recommendation_boxes[]`
   entry).

### 3. Cell segmentation

For each admitted candidate recbox, the skill segments cells under
the canonical ACC/AHA shape:
