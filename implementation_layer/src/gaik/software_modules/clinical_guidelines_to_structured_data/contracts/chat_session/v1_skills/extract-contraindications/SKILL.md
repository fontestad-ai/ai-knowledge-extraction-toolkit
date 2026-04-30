---
name: extract-contraindications
description: Phase-14 (P14) extraction skill for the cpg-htn-2025-acc-aha framework. Cross-checks the denylist subset of pharm-rules.json against the records.json INV-09 hard-block-basis source anchors, the atomic-unit anchors, the recbox cell shape, and the manifest-pinned RxNorm subsets, then produces FHIR R5 Evidence and EvidenceVariable resources for downstream IG composition. Cross-check disagreements route to the panel-chair queue; pregnancy denylist mismatches BLOCK unconditionally. PCE-legacy never appears in any contraindication. Post-Gate-2 contraindication artifacts are immutable.
namespace: cpg-htn-2025-acc-aha
category: extract
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> [--rules <list>] [--cohort <id>] [--mode <build|verify|verify+build>] [--strict] [--resume] [--dry-run]"
---

# extract-contraindications

Phase-14 (P14) extraction skill for the `cpg-htn-2025-acc-aha`
framework. The skill cross-checks the **denylist subset** of
`work/<run_id>/pharm-rules.json` (produced at P13 by
`extract-pharm-rules`) against the `records.json` `INV-09`
hard-block-basis source anchors, the `atomic-unit.json` anchor set,
the recbox cell shape from the SAIR's `recommendation_boxes[]`, and
the manifest-pinned RxNorm subsets, and produces a per-rule
**contraindication artifact** consisting of FHIR R5 `Evidence` and
`EvidenceVariable` resources that the downstream Implementation Guide
build (P26 `fhir-implementation-guide-build`) composes into the
published IG.

This skill is a **cross-check producer**. It does not author CQL,
rebind RxNorm, modify recommendation records, mutate atomic units,
edit pharm rules, or alter terminology bindings. It is the
quadruple-cross-check audit surface (rule ↔ record `INV-09` ↔
atomic-unit anchor ↔ recbox cell ↔ RxNorm subset) plus the FHIR R5
materialization layer for IG `Evidence` resources. Cross-check
agreement is the precondition for advancement; disagreement routes to
the panel-chair queue and BLOCKs the contraindication artifact.

This skill aligns to the schemas drafted in this thread:

- `schemas/acc-aha-grading.yaml` — closed COR/LOE enums.
- `schemas/sair.yaml` — input source-of-truth (read-only).
- `schemas/recommendation-record-htn.yaml` — input. Specifically
  `INV-09` (denylist requires hard-block basis with source anchor)
  is the upstream contract this skill ratifies.
- `schemas/atomic-unit.yaml` — input.
- `schemas/gate1-register.yaml` — finalization preconditions.
- `schemas/pharm-rule-htn.yaml` — input. Specifically the closed
  five-kind enum, the closed `AnchorKind` set for denylist rules
  (`PR-INV-05`), and the pregnancy-denylist constraint block
  (`PR-INV-18..21`) are the upstream contracts this skill cross-checks.
- `schemas/safety-case-htn.yaml` — downstream consumer; the
  contraindication artifact is referenced by Safety Case mitigations
  for hazards H-01, H-02, H-03 (and partially H-04, H-05).
- `schemas/cds-hooks-services-htn.yaml` — downstream consumer; the
  contraindication artifact informs the descriptor metadata for
  `htn-pregnancy-denylist` and `htn-pharm-first-line-check`.
- `schemas/gate3-attestation.yaml` — downstream consumer; the
  contraindication artifact is part of the `cont` (or equivalent)
  evidence under the IG bundle hashed at Gate 3.
- `schemas/guideline-manifest-hbp-2025.yaml` — pin source for
  RxNorm editions, terminology server endpoints, FHIR R5 profile
  versions, and TSAs.

Posture: **caution over velocity, fidelity over coverage,
hard-refusal-on-pregnancy over convenience.** No paraphrase. No
editing of ACC/AHA COR or LOE. No coercion of RxNorm subsets. No
silent re-extraction. No batch acceptance. PCE-legacy never appears
in any contraindication. Pregnancy denylist mismatches BLOCK
unconditionally — this is a clinical safety failure, not a
remediation. Post-Gate-2 contraindication artifacts are immutable.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P14** for
  a build whose Gate-1 cohort registers are in state `finalized`,
  whose `records.json` and `atomic-units.json` are sealed, whose
  `pharm-rules.json` is in state `sealed` (with panel-chair
  acknowledgement when held rules are present), and whose P10
  (terminology binding) outputs are persisted.
- A targeted re-extraction is required after P13 produced a new
  `pharm-rules.json` version (e.g., after a Gate-1 reviewer
  recorded `accept-with-edit` on a parent record, P9 re-extracted,
  and P13 re-emitted). On resume, this skill re-cross-checks every
  affected rule.
- A held cross-check entry in `work/<run_id>/queue/contraindications/`
  has been resolved by the two-person rule and the orchestrator
  requests advancement.
- A regression run is needed against the framework's golden
  contraindication set after a schema or skill change.

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers.
- `pharm-rules.json` is not in state `sealed` (with panel-chair
  acknowledgement when held rules are present).
- Any Gate-1 cohort referenced by parent records is not `finalized`.
- The terminology server is unreachable at the manifest's pinned
  RxNorm edition (the skill re-resolves drug-class subsets at every
  run, even though the rule set already records the resolution at
  P13; the re-resolution is the drift-detection mechanism).

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the sealed SAIR document at `work/<run_id>/sair.json`, validated against `schemas/sair.yaml`. |
| `--rules <list>` | no | `all-denylist` | Comma-separated list of `pharm-rule-htn` rule ids of `kind == "denylist"` whose contraindication artifacts are to be produced. Defaults to every denylist rule in `pharm-rules.json` whose `state == "advanced"`. |
| `--cohort <id>` | no | — | Restrict to denylist rules whose parent record is bound to the given Gate-1 cohort id. |
| `--mode <build\|verify\|verify+build>` | no | `verify+build` | `build` constructs FHIR `Evidence` / `EvidenceVariable` resources from cross-checked rules and writes them; `verify` recomputes cross-checks against on-disk artifacts and reports drift; `verify+build` builds any missing artifacts and verifies all. |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted artifact. The skill rejects resume if any input register's `register_sha256`, the SAIR's `fixity.sair_sha256`, the records or atomic-units SHAs, or `pharm-rules.json`'s `rule_set_sha256` has changed since session start. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned cross-check set and the proposed FHIR resource shapes; do not write artifacts. Permitted in production for change-control review. |

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
4. Verify upstream prerequisites (each is a release blocker):
   - `work/<run_id>/records.json` is sealed and validates against
     `schemas/recommendation-record-htn.yaml`. Specifically `INV-09`
     (denylist requires hard-block basis with source anchor) and
     `INV-10` (PCE-legacy never propagates) hold on every record in
     scope.
   - `work/<run_id>/atomic-units.json` validates against
     `schemas/atomic-unit.yaml`; every record-bound atomic unit set
     is sealed at `state == "gate-1-passed"`.
   - `work/<run_id>/pharm-rules.json` is in state `sealed` and
     validates against `schemas/pharm-rule-htn.yaml`. Every denylist
     rule in scope MUST have `agreement.state == "agreed"`; the skill
     refuses to materialize a contraindication for a `held` denylist
     rule and refuses categorically for any pregnancy denylist held
     rule (mirrors `PR-INV-21`).
   - Every Gate-1 cohort register file under
     `work/<run_id>/gate1/*.signed.jsonld` is in state `finalized`
     and validates against `schemas/gate1-register.yaml`.
   - `work/<run_id>/terminology-bindings.json` (produced at P10) is
     present and binds every drug-class anchor in scope to a
     manifest-pinned RxNorm edition.
   - The SAIR's `recommendation_boxes[]` for every parent record's
     row is in `consensus.state ∈ {"agreed","agreed-A-anchored"}`.
5. Verify the **terminology server** is reachable at the pinned
   RxNorm edition and resolves a manifest-pinned probe class
   non-empty.
6. Verify the manifest's pinned `risk_engine.name == "PREVENT"` and
   `risk_engine.legacy_only == false`.
7. Verify the `manifest.intended_use.pregnancy_value_set_id` is
   pinned (the IG's `EvidenceVariable.useContext` references this id
   for pregnancy denylist contraindications).
8. Verify `tsa_list[]` has at least one TSA whose `cert_valid_until`
   covers the wall-clock window. The contraindication artifact's
   per-resource fixity is signed for tamper-evidence at Gate 2's
   downstream signing step (P21 → Gate 2); this skill does not sign
   itself, but it requires TSA availability for the eventual
   downstream signing.
9. Acquire the contraindication-artifact write-back lock at
   `work/<run_id>/contraindications/.lock`. The skill is the only
   writer into this directory during its run.
10. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Per-rule quadruple cross-check

For each denylist rule in scope, the skill performs a **quadruple
cross-check**: every assertion below MUST hold; failure on any
assertion routes the rule to the panel-chair queue and BLOCKs the
contraindication artifact for that rule.

#### 2.1 Cross-check 1: rule ↔ record `INV-09`
- The denylist rule's `parent_record_id` resolves to a
  `RecommendationRecordHTN` whose `acc_aha_cor` is `III-Harm` or
  `III-No-Benefit`.
- The record carries an `INV-09` denylist-basis anchor with
  `anchor_kind` from the closed set
  {`cor-iii-harm-anchor`, `cor-iii-no-benefit-anchor`,
  `explicit-should-not-anchor`, `explicit-not-recommended-anchor`}.
- The rule's `anchor_kind` MUST equal the record's `INV-09`
  basis anchor's `anchor_kind`.
- Mismatch emits `cross-check-1-record-inv09-mismatch` and BLOCKs.

#### 2.2 Cross-check 2: rule ↔ atomic-unit anchor
- The rule's `parent_atomic_unit_id` resolves to an `AtomicUnit`
  whose `anchors.anchor_kind` matches the rule's `anchor_kind`.
- The unit's `anchors.sair_sha256`, `anchors.page`, and
  `anchors.bbox` MUST match the rule's `anchors` block.
- The unit's `text_verbatim` MUST round-trip byte-for-byte against
  the rule's `source_text_verbatim` after the rule's
  `normalization_log[]` is applied in reverse.
- Mismatch emits `cross-check-2-atomic-unit-anchor-mismatch` and
  BLOCKs.

#### 2.3 Cross-check 3: rule ↔ recbox cell shape
- The rule's `parent_record_id` resolves to a record whose
  `recommendation_box.row.cells[]` (in the SAIR) carry the canonical
  ACC/AHA shape (COR, LOE, Recommendation, Supportive Text,
  Citations).
- The recbox cell of `kind == "cor"` matches the rule's `acc_aha_cor`
  exactly.
- The recbox cell of `kind == "loe"` matches the rule's `acc_aha_loe`
  exactly.
- The recbox cell of `kind == "recommendation"` carries the parent
  atomic unit's `text_verbatim` span at the recorded byte offsets.
- Mismatch emits `cross-check-3-recbox-cell-mismatch` and BLOCKs;
  in practice this would indicate an upstream P6 or P9 corruption
  and remediates via re-running the upstream phases under the
  orchestrator's resume protocol.

#### 2.4 Cross-check 4: rule ↔ RxNorm subset
- For every drug class in the rule's `drug_classes[]`, re-resolve
  against the manifest's pinned RxNorm edition.
- The resolved subset MUST be:
  - non-empty (the contraindication is unenforceable if the class
    resolves to nothing);
  - byte-identical to the upstream P10 binding's recorded subset
    SHA-256;
  - byte-identical to the rule's recorded resolution at P13 (the
    rule records the subset SHA in
    `verification.methods_passed`'s `rxnorm-resolution` evidence; the
    skill recomputes against the live terminology server and against
    the recorded value).
- Mismatch emits `cross-check-4-rxnorm-subset-drift` and BLOCKs;
  remediation is a coordinated re-bind at P10 followed by P13
  re-extract and P14 re-run.

#### 2.5 Pregnancy denylist mechanical reinforcement
For every denylist rule whose `population_filter[]` includes
`pregnant` or `postpartum`, the skill enforces ALL of the
following in addition to §2.1–§2.4:

- The rule's `posture_at_cds == "hard-refuse"`.
- The rule's `cds_hook == "order-select"`.
- The rule's `attending_override_permitted == false`.
- The rule's `documentation_only == false`.
- The rule's `indicator_set == ["critical"]`.
- The closed AttendingOverridePattern scan from
  `cds-hooks-services-htn.yaml` §2.5 (recursively over the rule's
  `rationale`, `clinical_consequence`, and any
  `agreement.held_remediation_hint`) returns zero matches.
- The corresponding `Evidence.useContext[]` MUST include the
  manifest-pinned pregnancy value-set id; the
  `EvidenceVariable.characteristic[]` MUST include a
  population-filter characteristic referencing the closed
  PopulationFilter values `pregnant` and `postpartum` exactly.

Any violation BLOCKs unconditionally with the corresponding closed
audit event from §6 (`pregnancy-denylist-cross-check-failed`,
`pregnancy-denylist-attending-override-pattern-detected`, etc.).
This is a clinical safety failure; remediation is upstream re-author,
not a soft routing through the panel-chair queue.

#### 2.6 PCE-legacy exclusion (mechanical)
- The skill recursively scans every string field in the rule and in
  the produced FHIR resources for the literal `PCE-legacy`. Any
  match BLOCKs unconditionally.

### 3. FHIR R5 Evidence + EvidenceVariable materialization

For every denylist rule passing all four cross-checks plus the
pregnancy reinforcement (when applicable), the skill produces two
FHIR R5 resources:

#### 3.1 `EvidenceVariable`
A `EvidenceVariable` resource encodes the population definition
under which the contraindication applies. The shape:

```json
{
  "resourceType": "EvidenceVariable",
  "id": "ev-<rule_id>",
  "url": "https://aiwg.io/cpg-htn-2025-acc-aha/EvidenceVariable/ev-<rule_id>",
  "version": "1.0.0",
  "status": "active",
  "publisher": "<from manifest.publisher>",
  "useContext": [
    {
      "code": { "system": "http://terminology.hl7.org/CodeSystem/usage-context-type", "code": "focus" },
      "valueCodeableConcept": { "text": "Hypertension pharmacologic contraindication" }
    },
    {
      "code": { "system": "http://terminology.hl7.org/CodeSystem/usage-context-type", "code": "age" },
      "valueRange": { "low": { "value": 18, "unit": "years" } }
    }
  ],
  "characteristic": [
    {
      "linkId": "population",
      "description": "Population filter (closed enum from pharm-rule-htn)",
      "definitionCodeableConcept": { "text": "<closed PopulationFilter values joined>" }
    },
    {
      "linkId": "drug-classes",
      "description": "RxNorm-resolved drug classes contraindicated",
      "definitionReference": { "reference": "ValueSet/<manifest-pinned-rxnorm-subset-vs-id>" }
    },
    {
      "linkId": "trigger",
      "description": "<closed Trigger value>"
    },
    {
      "linkId": "consequence",
      "description": "<closed Consequence value>"
    }
  ]
}