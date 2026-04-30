---
name: cds-hooks-package-htn
description: Phase-22 (P22) CDS Hooks packaging skill for the cpg-htn-2025-acc-aha framework. Constructs the closed seven-service CDS Hooks service set from Gate-2-finalized CQL Libraries, wires hooks to libraries under the framework's hook-type and posture constraint matrix, builds htn-pregnancy-denylist as `order-select` with hard-refusal posture and no attending-override branch, computes per-service descriptor SHAs and the service-set manifest hash, and emits the descriptors that become the `cdsh` member of the Gate-3 bundle. No soft warning on the pregnancy denylist. No attending-override branch on any denylist. PCE-legacy never feeds CDS. Age gate ≥ 18 enforced on every service. Post-package descriptors are immutable until the next P22 run against a new Library snapshot or a new manifest version.
namespace: cpg-htn-2025-acc-aha
category: package
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> [--services <list>] [--mode <build|verify|verify+build>] [--strict] [--resume] [--dry-run]"
---

# cds-hooks-package-htn

Phase-22 (P22) CDS Hooks packaging skill for the
`cpg-htn-2025-acc-aha` framework. The skill constructs the closed
**seven-service CDS Hooks service set** from Gate-2-finalized CQL
Libraries, wires hooks to Libraries under the framework's
hook-type-and-posture constraint matrix, builds
**`htn-pregnancy-denylist` as `order-select` with hard-refusal
posture and no attending-override branch**, computes per-service
descriptor SHAs and the service-set manifest hash, and emits the
descriptors that become the `cdsh` member of the Gate-3 bundle hashed
and signed by `safety-case-attest`.

This skill does **not** author CQL, modify Library bytes, change
terminology bindings, alter risk-engine identity, edit recommendation
records, or modify atomic units. It is the **wiring** surface between
content (Libraries gated at Gate 2) and the prescribing surface
(EHR-side CDS Hooks consumers). Every wiring is a closed-by-policy
binding; the skill enforces the binding mechanically.

Posture: **caution over velocity, fidelity over coverage,
hard-refusal-on-pregnancy over attending-override.** No soft warning
on the pregnancy denylist under any circumstance. No attending-override
branch on any denylist (the framework default is no attending-override
on any service; institutional policy may opt in to soft-warning posture
on specific non-denylist services where the manifest explicitly
permits, but the pregnancy denylist remains hard refuse). PCE-legacy
never feeds any service. Age gate ≥ 18 on every service. Post-package
descriptors are immutable until the next P22 run against a new Library
snapshot or a new manifest version.

This skill is the operational counterpart of `safety-case-attest` at
the wiring level: where Gate 3 attests that the published service set
is faithful to the safety case, P22 produces the service set that the
Gate-3 bundle covers.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P22** for a
  build whose Gate-2 cohort registers are in state `finalized`, whose
  Libraries pass the 95% Synthea coverage floor, and whose
  hard-block invariants verify.
- A targeted re-package is required after a Gate-2 reviewer recorded
  `reject-rework` on a Library that wires to a service (the
  orchestrator regenerates the Library at P20–P21 and re-posts to
  Gate 2; on resume, this skill re-verifies the Library and re-emits
  the affected service descriptor with a new descriptor SHA).
- A regression run is needed against the framework's golden
  service-set after a schema or skill change.
- A `--mode verify` re-check is needed by `safety-case-attest` at
  Gate 3 (the same descriptor SHAs are recomputed under the same
  canonicalization rule).

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers.
- Any Gate-2 cohort referenced by a wiring is not in state
  `finalized`.
- Any Library bound to a service has Synthea branch coverage below
  95.0%.
- Any Library bound to a service has an unverified hard-block
  invariant.
- The orchestrator has not posted the service-set draft path to this
  skill's queue.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the sealed SAIR document at `work/<run_id>/sair.json` (read-only at this phase). The skill consults the SAIR for source-anchored citations recorded in service descriptor metadata. |
| `--services <list>` | no | `all` | Comma-separated list of service ids from the closed seven (see §2.1). Default packages the full seven-service set. |
| `--mode <build\|verify\|verify+build>` | no | `verify+build` | `build` constructs descriptors from live Library snapshots and writes them; `verify` recomputes descriptor SHAs against on-disk descriptors and reports drift; `verify+build` builds any missing descriptors and verifies all. |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted descriptor. The skill rejects resume if any contributing Library's `library_content_hash` has changed since session start. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned service set and the Library-wiring outcomes; do not write descriptors. Permitted in production for change-control review. |

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
   - Every Gate-2 cohort register file under
     `work/<run_id>/gate2/*.signed.jsonld` is in state `finalized`
     and validates against `schemas/gate2-register.yaml`.
   - Every CQL Library required by the wiring matrix in §3 has a
     finalized Library entry with branch coverage ≥ 95.0%, a clean
     typecheck, and verified hard-block invariants.
   - The manifest's `intended_use.age_min_inclusive == 18`
     (`GM-INV-24` semantics; the skill consults the value and
     refuses to build with any other age gate).
   - The manifest's pinned `risk_engine.name == "PREVENT"` and
     `risk_engine.legacy_only == false` (PCE-legacy never feeds
     CDS; `GM-INV-12` semantics).
5. Verify `tsa_list[]` has at least one TSA whose `cert_valid_until`
   covers the wall-clock window. Otherwise BLOCK.
6. Acquire the service-set write-back lock at
   `work/<run_id>/cds-hooks/.lock`. The skill is the only writer
   into this directory during its run.
7. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Closed seven-service set

The skill packages exactly the following seven services, in this
order, each appearing exactly once:

| Service id | Hook type | Posture | Bound Libraries | Hazards mitigated |
|---|---|---|---|---|
| `htn-bp-stage-and-confirm` | `patient-view` | `informational` | `HBPStaging` | H-07 |
| `htn-prevent-risk-and-threshold` | `patient-view` | `informational` | `PreventRisk`, `TreatmentThreshold` | (binds risk engine; consulted by H-04, H-07 indirectly) |
| `htn-pharm-first-line-check` | `order-select` | `hard-refuse` | `FirstLineSelection`, `SpecialPopulationModifiers` | H-02, H-03, H-04 |
| `htn-pregnancy-denylist` | `order-select` | `hard-refuse` | `PregnancyHTN` | H-01 |
| `htn-resistant-workup` | `patient-view` | `informational` | `ResistantHTN` | H-06 |
| `htn-secondary-screen` | `patient-view` | `informational` | `SecondaryHTNTriggers` | (workup advisory) |
| `htn-hbpm-discharge` | `encounter-discharge` | `informational` | `HBPStaging` | H-07 |

The service set is **closed** at the schema level. The skill refuses
to add or remove services without a manifest-version-level amendment
under panel-chair signoff and an ADR-HTN-001 amendment.
Institution-specific services go to a separate `cds-hooks-extensions`
skill (out of scope) only if the manifest's
`cds_extensions_authorized == true`.

### 3. Hook-type and posture constraint matrix (closed)

The skill enforces the per-service hook-type and posture constraints
mechanically. Any deviation BLOCKs the build.

#### 3.1 `htn-bp-stage-and-confirm`
- Hook type: `patient-view` only. `order-select` and other types are
  rejected.
- Posture: `informational` only. `hard-refuse` is rejected (this
  service is advisory; staging cannot refuse a prescribing path).
- Bound Library: `HBPStaging`. The Library's `bp-confirmation-out-of-office`
  invariant MUST verify.
- Card semantics: at most one informational card per encounter; no
  prescription suggestions; no override semantics.

#### 3.2 `htn-prevent-risk-and-threshold`
- Hook type: `patient-view` only.
- Posture: `informational` only.
- Bound Libraries: `PreventRisk`, `TreatmentThreshold`. The
  `prevent-canonical-binding` and `pce-legacy-never-feeds-cql`
  invariants MUST verify on `PreventRisk`.
- Card semantics: a single risk-stratification card; numeric outputs
  cite the manifest's pinned PREVENT risk-engine version; the card
  MUST NOT cite PCE-legacy under any circumstance.
- The skill verifies that `bound_risk_engine.name == "PREVENT"` and
  `legacy_only == false` on the bound Libraries' Gate-2-finalized
  snapshots. PCE-legacy in any binding BLOCKs.

#### 3.3 `htn-pharm-first-line-check`
- Hook type: `order-select` only. `medication-prescribe` is
  rejected (the framework's policy is that first-line checks fire at
  selection, before signing).
- Posture: `hard-refuse` is permitted; `soft-warning` is permitted
  only for non-denylist subroutines (e.g., the older-adult
  orthostasis monitoring suggestion); `informational` is permitted
  only for non-blocking suggestions. The skill enforces per-branch
  posture (a single service may carry multiple posture-distinct
  branches per CQL output).
- Bound Libraries: `FirstLineSelection`, `SpecialPopulationModifiers`.
  The `aki-triple-whammy-warning` and
  `hyperkalemia-aceiarb-mra-warning` invariants MUST verify.
- Card semantics: when a hard-refuse branch fires (triple-whammy or
  hyperkalemia ACEi+ARB+MRA), the descriptor declares
  `suggestions[]` only — never a `card.indicator: "warning"` with a
  permissive override; the skill rejects any descriptor whose
  hard-refuse branch carries override semantics.

#### 3.4 `htn-pregnancy-denylist` — the safety-critical service

This service is the most-restricted of the seven. The skill enforces
**every** rule below; any single violation BLOCKs.

- Hook type: **`order-select` only**. `order-sign` is rejected.
  `medication-prescribe` is rejected. `patient-view` is rejected. The
  rationale is that the denylist must fire **before** the prescribing
  decision is made; firing at sign or prescribe would permit a
  partial workflow path on which the user has already committed
  cognitively to the prescription.
- Posture: **`hard-refuse` only**. `soft-warning` is rejected
  unconditionally. `informational` is rejected. The framework's
  posture is that a recommendation graded **COR III-Harm** in the
  source guideline cannot be downgraded to a warning at the wiring
  layer; doing so would substitute the framework's judgment for the
  source guideline's.
- **No attending-override branch.** The descriptor MUST NOT contain a
  `permit_on_attending_override` flag, an `override_role` field, an
  `override_reason_required` field, or any equivalent semantic. The
  skill scans the descriptor's JSON tree for the closed pattern set
  in §3.4.1 and rejects any match.
- **No card.indicator override semantics.** The descriptor MUST
  declare `suggestions[]` containing zero suggestions for the
  denylist branch (i.e., the EHR's decision panel renders no
  permissive options); the descriptor MUST NOT declare any
  `card.indicator` of `info` or `warning` on the denylist branch;
  only `critical` is permitted.
- **No documentationOnly bypass.** The descriptor MUST NOT declare
  `documentationOnly: true` or any equivalent flag that would let
  the EHR render the denylist as commentary rather than a refusal.
- **Bound Library invariant.** The bound Library `PregnancyHTN` MUST
  declare the `pregnancy-denylist-order-select-hard-refuse`
  hard-block invariant in its Gate-2 register entry, AND the
  verifying reference test MUST pass.
- **Coverage floor on the denylist branch.** The bound Library's
  Synthea branch coverage MUST be ≥ 99.0% on the denylist branch
  specifically (the framework default coverage floor is 95%, but
  the pregnancy denylist branch is held to 99% by manifest pin).
  Below the branch floor → BLOCK.
- **Two-person rule witness.** The skill records, in the descriptor's
  metadata, the Gate-1 cohort id and the Gate-2 cohort id whose
  signoffs cover the pregnancy records and the `PregnancyHTN`
  Library, including the MFM and clinical-pharmacology signoff
  entries. The descriptor's metadata is part of the
  canonicalization payload, so any later mutation invalidates the
  descriptor SHA.
- **No card on out-of-pregnancy population.** The descriptor's
  prefetch query MUST gate the denylist branch on the manifest's
  pregnancy-population value-set; an empty pregnancy population
  produces no card. The skill verifies that the prefetch query
  references the manifest-pinned pregnancy value-set id and rejects
  any deviation.
- **No silent enable.** The descriptor MUST set `enabled: true`
  unconditionally; runtime toggles that disable the denylist are
  rejected at packaging time. The framework's policy is that the
  denylist cannot be disabled at deployment; institutions wishing to
  scope the framework's deployment to non-pregnancy populations must
  do so by EHR-side filtering of the consuming clinical workflow,
  not by disabling the service.

##### 3.4.1 Closed pattern set for attending-override scan

The skill scans every key/value pair in the descriptor JSON tree and
rejects any descriptor containing any of the following patterns
(case-insensitive, after Unicode NFC):
