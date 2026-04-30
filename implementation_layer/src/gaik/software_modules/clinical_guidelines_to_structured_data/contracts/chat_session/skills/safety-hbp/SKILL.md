---
name: safety-hbp
description: Phase-23 (P23) safety-analysis skill for the cpg-htn-2025-acc-aha framework. Produces the ISO 14971-shaped Safety Case (the `safe` bundle member at Gate 3) covering hazards H-01 through H-10, wires every hazard to one or more mitigations referencing CQL Libraries, CDS Hooks services, or pipeline controls, computes pre-mitigation and post-mitigation risk under closed Severity × Likelihood matrices, and produces a residual-risk justification per hazard. Mitigations are verified at sign time; unverified mitigations BLOCK. Pregnancy hard-block must remain `order-select` hard refusal — no soft warning. PCE-legacy never substitutes for PREVENT. Post-signoff Safety Case content is immutable.
namespace: cpg-htn-2025-acc-aha
category: safety
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> [--records <list>] [--cohort <id>] [--mode <draft|sign>] [--reviewer <id>] [--resume]"
---

# safety-hbp

Phase-23 (P23) safety-analysis skill for the `cpg-htn-2025-acc-aha`
framework. The skill produces the **Safety Case** — the ISO 14971-shaped
hazard log + risk evaluation + residual-risk justification document
that becomes the `safe` member of the Gate-3 bundle hashed and signed
by `safety-case-attest`. The Safety Case covers the framework's ten
named hazards H-01 through H-10 (per framework spec §8 and ADR-HTN-001
D8 / D9 / D10 / D14 / D15), wires every hazard to one or more
mitigations referencing **CQL Libraries**, **CDS Hooks services**, or
**pipeline controls**, computes pre-mitigation and post-mitigation risk
under closed Severity × Likelihood matrices, and produces a per-hazard
residual-risk justification anchored to source evidence.

This skill does **not** produce clinical content, modify CQL Libraries,
edit CDS Hooks service descriptors, change recommendation records,
mutate atomic units, or alter terminology bindings. It is the
**safety-evaluation** surface over content already produced and gated
by upstream phases. Every mitigation reference is **verified** at sign
time: the referenced Library exists, has Gate-2-finalized signoff, and
the Library's hard-block invariant verifies; the referenced CDS Hooks
service exists with the manifest-required hook type and posture; the
referenced pipeline control is a real, machine-checkable behavior of
the orchestrator (e.g., the parser's reversible-normalization log, the
SAIR write-back lock, the gate1-register's append-only audit). Producer
claims are not trusted; the skill recomputes verifications.

Posture: **caution over velocity, fidelity over coverage, residual-risk
over claimed-risk.** The Safety Case may declare residual risks; it
may not declare them away. Pregnancy hard-block must remain
`order-select` hard refusal — no soft warning. PCE-legacy never
substitutes for PREVENT. Hazards without verified mitigations BLOCK
the build. Post-signoff Safety Case content is immutable; corrections
require a new Safety Case version with explicit predecessor chain.

This skill is the operational analogue of `safety-case-attest` at the
upstream end: where Gate 3 attests the build's published artifacts in
aggregate, P23 produces the safety-evaluation document that Gate 3
attests *to*.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P23** for a
  build whose Gate-1 cohort registers and Gate-2 cohort registers are
  in state `finalized`, whose CQL Libraries have all passed the 95%
  Synthea coverage floor, whose CDS Hooks services are packaged at P22,
  and whose `htn-pregnancy-denylist` service is wired as `order-select`
  with hard-refusal posture.
- A re-run is required after a Gate-2 reviewer recorded `reject-rework`
  on a Library that bears on a hazard's mitigation reference (the
  orchestrator regenerates the Library at P20–P21 and re-posts to
  Gate 2; on resume, this skill re-verifies the mitigation and
  re-emits the Safety Case).
- A regression run is needed against the framework's golden hazard
  set after a schema or skill change.
- A change-control review needs to verify that the Safety Case still
  references live, finalized artifacts (`--mode draft`).

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers.
- Any Gate-1 or Gate-2 cohort referenced by mitigations is not in
  state `finalized`.
- Any CQL Library referenced by a mitigation has Synthea branch
  coverage below 95.0%.
- The CDS Hooks packaging at P22 has not produced the
  `htn-pregnancy-denylist` service with `order-select` hook type and
  hard-refusal posture.
- The orchestrator has not posted the Safety Case draft path to this
  skill's queue.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the sealed SAIR document at `work/<run_id>/sair.json` (read-only at this phase). The skill consults the SAIR for source-anchored basis pointers (e.g., the cor-iii-harm or cor-iii-no-benefit anchor that justifies a denylist mitigation). |
| `--records <list>` | no | `all-finalized` | Comma-separated list of recommendation record ids whose hazard implications are to be re-evaluated. Defaults to every record in `work/<run_id>/records.json` whose Gate-1 register state is `finalized`. |
| `--cohort <id>` | no | — | Restrict to records bound to the given Gate-1 cohort id. Useful for targeted re-runs after a single cohort's rework. |
| `--mode <draft\|sign>` | no | `draft` | `draft` produces the Safety Case content under a session-scoped `fixity` block, with no signature; `sign` opens an authenticated signing session for the medical director or hypertension specialist (the framework's default; institutional policy may pin a different signer role) and produces the signed Safety Case at `work/<run_id>/safety/safety-case.signed.jsonld`. |
| `--reviewer <id>` | no | — | The reviewer id (`rev-<16hex>`) for the current session. Required in `--mode sign`. The skill refuses to act on behalf of any other reviewer. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted hazard. The skill rejects resume if any underlying register's `register_sha256` has changed since session start. |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned hazard set, mitigation references, and the verification recompute outcomes; do not write the Safety Case or open a signing session. Permitted in production for change-control review. |

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
4. Verify upstream prerequisites (each is a release blocker if it
   fails):
   - `work/<run_id>/records.json` is sealed and validates against
     `schemas/recommendation-record-htn.yaml`.
   - `work/<run_id>/atomic-units.json` validates against
     `schemas/atomic-unit.yaml`.
   - Every Gate-1 cohort register file under
     `work/<run_id>/gate1/*.signed.jsonld` is in state `finalized`
     and validates against `schemas/gate1-register.yaml`.
   - Every Gate-2 cohort register file under
     `work/<run_id>/gate2/*.signed.jsonld` is in state `finalized`
     and validates against `schemas/gate2-register.yaml`.
   - Every CQL Library snapshot directory has Synthea branch coverage
     ≥ 95.0%.
   - Every CDS Hooks service descriptor under
     `work/<run_id>/cds-hooks/*.json` validates against the framework's
     CDS Hooks schema; `htn-pregnancy-denylist` MUST declare hook type
     `order-select` and hard-refusal posture.
5. Verify `tsa_list[]` in the manifest has at least one TSA whose
   `cert_valid_until` covers the wall-clock window. Otherwise BLOCK.
6. In `--mode sign`:
   - Resolve `--reviewer` to a `Reviewer` in any of the contributing
     Gate-1 / Gate-2 panels (the safety signer is institutional; the
     framework's default is the medical director who also signs the
     manifest, per ADR-HTN-001 D9, but a hypertension specialist
     designated by the panel chair is permitted).
   - Verify `identity_proof.ial >= "IAL2"` and `aal >= "AAL2"`; if
     the institutional policy pins a higher level for safety
     attestation, enforce that level.
   - Authenticate the reviewer via the institutional KMS bound to
     the reviewer's `key_id`.
7. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Hazard set (closed)

The Safety Case covers the framework's ten named hazards exactly:

| Hazard id | Title | Category |
|---|---|---|
| H-01 | RAAS / MRA / direct-renin in pregnancy | drug-population (hard-block) |
| H-02 | Triple-whammy AKI (ACEi/ARB + diuretic + NSAID) | drug-drug-population |
| H-03 | Hyperkalemia on ACEi+ARB+MRA | drug-drug |
| H-04 | Older-adult orthostasis / falls | drug-population |
| H-05 | Beta-blocker rebound on abrupt discontinuation | drug-protocol |
| H-06 | Missed primary aldosteronism in resistant HTN | workup-omission |
| H-07 | In-office-only diagnosis (missed white-coat / masked HTN) | measurement-protocol |
| H-08 | LLM-hallucinated recommendation surfaces in published artifact | pipeline-integrity |
| H-09 | Terminology drift (RxNorm / SNOMED / LOINC editions move) | pipeline-integrity |
| H-10 | Source guideline updated / erratum published after build | pipeline-integrity |

The set is **closed** at the schema level; the skill refuses to add
or remove hazards without a manifest-version-level amendment under
panel-chair signoff. Adding an institution-specific hazard is
permitted only via a separate `safety-hbp-extensions` skill (out of
scope) whose output is concatenated to the canonical ten under a
clearly-marked `extensions` block; the canonical Gate-3 bundle hash
covers the union, and reviewers attest both blocks.

### 3. Per-hazard authoring

For each hazard H-01 through H-10, the skill produces a `Hazard`
entry per `schemas/safety-case-htn.yaml` (the dedicated Safety Case
schema; until that schema is formally drafted, the skill validates
against an inline shape that mirrors the YAML contract embedded in
this file's §6). The shape per hazard is:

```yaml
hazard_id: H-01
title: "..."
category: drug-population
intended_use_scope:
  age_min_inclusive: 18
  populations: [pregnant, postpartum]   # closed enum from schema
  out_of_scope_populations: [pediatric]
narrative:
  description_verbatim_anchored: true
  body: |
    Source-anchored description of the hazard, citing the
    `RecommendationRecord` ids and atomic-unit ids that bear on it.
basis:
  cor: III-Harm                          # closed enum
  loe: B-NR                              # closed enum
  source_anchors:
    - { record_id: rec-..., atomic_unit_id: au-..., anchor_kind: cor-iii-harm-anchor }
clinical_consequence:
  on_occurrence: "..."
pre_mitigation_risk:
  severity: serious                      # closed: minor | major | serious | catastrophic
  likelihood: occasional                 # closed: rare | occasional | probable | frequent
  combined: high                         # derived; see §4
mitigations:
  - mitigation_id: mit-...
    kind: cql-library | cds-hooks-service | pipeline-control | documentation
    target:
      cql_library:
        library_id: lib-hbp-pregnancy
        library_name: PregnancyHTN
        hard_block_invariant_kind: pregnancy-denylist-order-select-hard-refuse
      # OR
      cds_hooks_service:
        service_id: htn-pregnancy-denylist
        hook: order-select
        posture: hard-refuse
      # OR
      pipeline_control:
        control_kind: parse-acc-aha-recbox-cell-shape-compliance | gate1-register-immutability | manifest-no-auto-update | sair-write-back-lock
      # OR
      documentation:
        artifact: guideline-card | regulatory-traceability | retraction-notice
        section: "..."
    asserts_invariant_kind: pregnancy-denylist-order-select-hard-refuse
    verification:
      verifies: true                     # recomputed at sign time
      verified_by_reference_test_id: test-...
      verified_at: "<ISO-8601>"
    rationale: |
      ...
post_mitigation_risk:
  severity: serious                      # severity rarely changes; mitigations affect likelihood
  likelihood: rare
  combined: low
residual_risk_justification:
  is_acceptable_under_iso14971: true
  basis: |
    Source-anchored argument that residual risk is as low as
    reasonably practicable given the four sources, the manifest's
    intended-use scope, and the named mitigations.
  benefit_risk_summary: |
    Quantitative or semi-quantitative summary appropriate to the
    hazard.
  out_of_scope_assertion: |
    Explicit statement of what populations the framework does not
    address (e.g., pediatric is out of scope; the hazard does not
    propagate there because the age gate is enforced).