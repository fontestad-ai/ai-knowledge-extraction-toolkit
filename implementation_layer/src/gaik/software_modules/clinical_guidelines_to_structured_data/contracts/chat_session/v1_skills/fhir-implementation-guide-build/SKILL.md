---
name: fhir-implementation-guide-build
description: Phase-26 (P26) Implementation Guide build skill for the cpg-htn-2025-acc-aha framework. Composes the published FHIR R5 IG package from Gate-3-attested upstream artifacts (records, atomic units, pharm rules, contraindication FHIR Evidence/EvidenceVariable, monitoring FHIR PlanDefinition.action, CDS Hooks service descriptors, CQL Library snapshots, Safety Case, Guideline Card) under the manifest-pinned FHIR R5 profile and the framework's `cpg-htn-*` StructureDefinition extensions, validates every resource at the closed profile set, computes deterministic per-resource and per-package SHAs under FHIR-R5 JCS canonicalization, and emits the IG package consumed at P28 (publication versioning). PCE-legacy never appears. Pregnancy denylist resources carry the order-select hard-refuse posture by construction. Post-Gate-3 IG packages are immutable.
namespace: cpg-htn-2025-acc-aha
category: build
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<gate3-attestation-path> [--profile-pin <id>] [--mode <build|verify|verify+build>] [--strict] [--resume] [--dry-run]"
---

# fhir-implementation-guide-build

Phase-26 (P26) Implementation Guide build skill for the
`cpg-htn-2025-acc-aha` framework. The skill **composes** the
published FHIR R5 IG package from Gate-3-attested upstream artifacts
under the manifest-pinned FHIR R5 profile and the framework's
`cpg-htn-*` StructureDefinition extensions, **validates** every
resource at the closed profile set, **computes** deterministic
per-resource and per-package SHAs under FHIR-R5 JCS canonicalization,
and **emits** the IG package consumed at P28 (publication
versioning).

This skill is a **composer**. It does not author records, atomic
units, pharm rules, contraindications, monitoring artifacts, the
Safety Case, the Guideline Card, CQL Library bytes, CDS Hooks
descriptor bytes, or terminology bindings; those are all upstream
producers. It does not sign artifacts; signing is performed at the
gate-specific signing skills (Gate 1 / Gate 2 / Gate 3) and at P28
release. Its responsibility is the **deterministic, validated,
profile-conformant FHIR R5 IG composition** that materializes the
framework's full evidence chain into a single shippable IG package
that the EHR-side CDS Hooks runtime, the FHIR R5 IG Publisher, and
downstream republishers consume.

This skill aligns to every schema and skill drafted in this thread:

- `schemas/acc-aha-grading.yaml` — closed COR/LOE enums for
  certainty mapping.
- `schemas/sair.yaml` — input source-of-truth (read-only).
- `schemas/recommendation-record-htn.yaml` — input.
- `schemas/atomic-unit.yaml` — input.
- `schemas/gate1-register.yaml` — input.
- `schemas/gate2-register.yaml` — input.
- `schemas/gate3-attestation.yaml` — input. The Gate-3 attestation
  is the gating precondition; without it, this skill refuses to
  build.
- `schemas/safety-case-htn.yaml` — input.
- `schemas/cds-hooks-services-htn.yaml` — input.
- `schemas/pharm-rule-htn.yaml` — input.
- `schemas/contraindication-artifact-htn.yaml` — input. The
  artifact's `pass`-state rows' `materialized.evidence_id` and
  `evidence_variable_id` are the canonical FHIR resource ids
  composed into the IG.
- `schemas/guideline-manifest-hbp-2025.yaml` — pin source.

This skill also aligns to the orchestrator (`flow-hbp-2025-build`),
which is the only authorized invoker in production, and to the
Phase-26 placement explicitly recorded in the orchestrator's closed
twenty-eight-phase set.

Posture: **caution over velocity, fidelity over coverage,
hard-refusal-on-pregnancy over convenience.** No paraphrase. No
editing of ACC/AHA COR or LOE. No coercion of FHIR resources to
non-conformant shapes. No silent re-runs. PCE-legacy never appears
in any FHIR resource, profile, value set, or extension. Pregnancy
denylist FHIR resources carry the order-select hard-refuse posture
by construction. Post-Gate-3 IG packages are immutable; corrections
require a new manifest version and a new build, with the prior IG
package retained immutably for audit.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P26** for
  a build whose **Gate 3 attestation is verified** (state `signed`,
  signature verifies under the medical director's public key, time-
  stamp verifies against a manifest-pinned TSA, every cohort-axis
  attestation flag is `true`).
- A targeted re-build is required after a non-content errata
  closure that requires re-publishing the IG (e.g., a TSA rotation
  that updates the timestamp surface but does not invalidate prior
  signatures; a forthcoming companion schema becomes available and
  is added to the pinned profile set).
- A regression run is needed against the framework's golden IG set
  after a schema or skill change.
- A `--mode verify` re-check is needed by `guideline-version` (P28)
  before publication versioning.

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers (`GM-INV-23`).
- The Gate-3 attestation is not in state `signed` and verifying.
- Any contributing artifact's recorded SHA does not recompute
  against the live artifact at session start.
- The pinned FHIR R5 profile is not present in the manifest's
  `tools_lock.items[]` of `kind == "fhir-r5-profile"`.
- The IG Publisher tooling pin (`tools_lock.items[]` of `kind ==
  "fhir-ig-publisher"`) is not verifying against its recorded SHA.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `gate3-attestation-path` | yes | — | Path to the signed Gate-3 attestation at `work/<run_id>/gate3-attestation.signed.jsonld`, validated against `schemas/gate3-attestation.yaml`. The skill resolves the build pin from the attestation. |
| `--profile-pin <id>` | no | (from manifest) | Override the FHIR R5 profile pin id; used only for change-control review under `--dry-run`. The pin is otherwise resolved from `manifest.tools_lock.items[]`. |
| `--mode <build\|verify\|verify+build>` | no | `verify+build` | `build` composes the IG package from upstream artifacts and writes the IG; `verify` recomputes per-resource and per-package SHAs against on-disk IG outputs and reports drift; `verify+build` builds missing resources and verifies all. |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted resource. The skill rejects resume if any contributing artifact's recorded SHA has changed since session start, or if the Gate-3 attestation's `payload_sha256` has changed. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned resource composition tree, the validated profile bindings, and the predicted per-resource SHA set; do not write the IG package. Permitted in production for change-control review. |

## Operation

### 1. Preflight

1. Validate `gate3-attestation-path` against
   `schemas/gate3-attestation.yaml`. Refuse on any invariant failure.
2. Verify the attestation's signature cryptographically against the
   medical director's `public_key` recorded in the attestation.
   Refuse on signature failure.
3. Verify the attestation's time-stamp against the manifest-pinned
   TSA per `GM-INV-23` and `safety-case-attest`'s recorded
   `tsa_cert_fingerprint_sha256`. Refuse on TSA verification
   failure.
4. Verify every cohort-axis attestation flag in the attestation is
   `true` (mirrors `SC-INV-14` semantics):
   - iso14971-compliance-attested
   - no-relax-of-hard-block-attested
   - pce-legacy-never-propagates-attested
   - pregnancy-order-select-hardrefuse-attested
   - errata-watch-attested
   - source-admission-attested
   - mitigation-verification-attested
   - acceptable-residual-risk-within-ceiling-attested
   Any `false` BLOCKs.
5. Resolve `guideline_manifest_ref` from the attestation's bundled
   manifest pin; verify the active manifest's
   `medical_director_signoff` cryptographically per `GM-INV-21`;
   verify `state == "active"` and
   `errata_watch.blockers_open == []` per `GM-INV-23`.
6. Verify `tools_lock.lock_sha` against canonicalized
   `tools_lock.items[]` per `GM-INV-08`.
7. Verify the manifest's pinned canonical decisions:
   - `risk_engine.name == "PREVENT"` and
     `risk_engine.legacy_only == false` (`GM-INV-12`).
   - `intended_use.age_min_inclusive == 18` (`GM-INV-24` semantics).
   - `intended_use.pregnancy_value_set_id` is non-empty.
   - `tools_lock.items[]` includes a `kind == "fhir-r5-profile"`
     entry (the pinned IG profile) and a
     `kind == "fhir-ig-publisher"` entry (the pinned publisher
     tooling).
8. Verify upstream prerequisites (each is a release blocker):
   - The Gate-3 bundle members referenced by the attestation are all
     present and verify against their recorded SHAs:
     - `cdsh` (CDS Hooks service-set manifest from
       `cds-hooks-package-htn` at P22).
     - `safe` (Safety Case from `safety-hbp` at P23).
     - `cont` (contraindication artifact from
       `extract-contraindications` at P14).
     - `mon` (monitoring artifact from `extract-monitoring` at P15).
     - `cpr` (copyright envelope from
       `copyright-quote-check-acc-aha` at P4).
     - `phi` (PHI scrub report from `phi-scrub` at P3).
     - The Library bundle (Gate-2-finalized snapshots).
     - The Guideline Card (P24).
   - `pharm-rules.json` is in state `sealed` (and
     `panel_chair_acknowledgement` is recorded when held rules are
     present, per `PR-INV-22`).
   - The contraindication artifact's `state == "sealed"` and every
     row in scope has `overall == "pass"` with `materialized` non-
     null (per `CIA-INV-07`).
   - The monitoring artifact's `state == "sealed"` and every row in
     scope has `overall == "pass"` with `materialized` non-null
     (mirrored constraint).
   - Every CDS Hooks service descriptor file under
     `work/<run_id>/cds-hooks/` has `state == "built"` and its
     `fixity.descriptor_sha256` recomputes (per `CDH-INV-04` and
     `CDH-INV-19`).
   - Every CQL Library snapshot referenced in the Gate-2 register
     has `state == "finalized"` (per `GR2-INV-*`).
   - The Safety Case is in state `signed` and its signature verifies
     (per `SC-INV-14`).
9. Verify `tsa_list[]` has at least one TSA whose
   `cert_valid_until` covers the wall-clock window (the IG package
   itself is not signed at P26; the time-stamping of the published
   release happens at P28 by `guideline-version`. P26 verifies TSA
   availability for downstream signing readiness.).
10. Acquire the IG write-back lock at `work/<run_id>/ig/.lock`. The
    skill is the only writer into this directory during its run.
11. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Closed FHIR R5 resource composition matrix

The skill composes exactly the resources in the matrix below; the
matrix is **closed** at the schema level. Adding a new resource
type requires ADR-HTN-001 amendment under panel-chair signoff and a
coordinated update of every parent schema and skill.

| Resource type | Source | Profile (manifest-pinned) | One per |
|---|---|---|---|
| `ImplementationGuide` | (synthesized) | `cpg-htn-2025-implementation-guide` | run |
| `CapabilityStatement` | (synthesized) | `cpg-htn-2025-capability-statement` | run |
| `Library` | Gate-2 register snapshots | `cpg-htn-2025-library` | CQL Library |
| `Evidence` | contraindication artifact (P14) + monitoring artifact (P15) + records.json (P9) | `cpg-htn-2025-evidence` | rule + record |
| `EvidenceVariable` | contraindication artifact (P14) + monitoring artifact (P15) + records.json (P9) | `cpg-htn-2025-evidence-variable` | rule |
| `EvidenceReport` | Safety Case (P23) | `cpg-htn-2025-evidence-report` | hazard |
| `PlanDefinition` | Gate-2 register snapshots + monitoring artifact (P15) | `cpg-htn-2025-plan-definition` | clinical scenario |
| `ActivityDefinition` | pharm-rules.json (P13) `kind == "monitoring"` and `kind == "discontinuation"` rules | `cpg-htn-2025-activity-definition` | monitoring/discontinuation rule |
| `ServiceDefinition` | CDS Hooks service-set manifest (P22) | `cpg-htn-2025-service-definition` | CDS Hooks service |
| `Citation` | acquire-hbp-2025-source manifest (P1) + recommendation records' citations | `cpg-htn-2025-citation` | source guideline (single) |
| `Observation` (definitional) | bp-thresholds.json (P12) | `cpg-htn-2025-observation-definition` | BP threshold band |
| `ValueSet` | bind-htn-vocab terminology bindings (P10) + manifest-pinned pregnancy value-set | `cpg-htn-2025-value-set` | value set |
| `CodeSystem` | (referenced; not authored) | (not authored) | — |
| `ConceptMap` | bind-htn-vocab terminology bindings (P10) where cross-edition mappings are recorded | `cpg-htn-2025-concept-map` | mapping |
| `Provenance` | every produced resource (PROV bundle from P26) | `cpg-htn-2025-provenance` | resource |
| `Group` | manifest's `intended_use` populations | `cpg-htn-2025-group` | population |
| `StructureDefinition` (extensions) | (synthesized; the framework's `cpg-htn-*` extensions) | (self) | extension |

The composition order is fixed: `ImplementationGuide` and
`CapabilityStatement` last (after every resource referenced is
materialized); `StructureDefinition` extensions first (so every
downstream resource's profile validation can resolve them). The
ordering is enforced by the skill's processing pipeline and is
verified at the per-package fixity recompute step (§5).

### 3. Resource construction

For each resource type in scope, the skill constructs FHIR R5
resources under the deterministic shape rules below. The `id`
derivation, the `meta.profile[]` setting, the `text.div`
generation, the `meta.security` SHA recording, and the
`Provenance.signature` ↔ source-anchor binding are all
deterministic and reproducible.

#### 3.1 Deterministic id derivation

Every resource's `id` is deterministic from its source:

- `Library`: `library-<library-name-kebab>-<library-content-hash[:16]>`
- `Evidence` for contraindication: `ev-cont-<rule_id>` (mirrored
  from `CIA-INV-17`).
- `EvidenceVariable` for contraindication: `ev-<rule_id>` (mirrored
  from `CIA-INV-17`).
- `Evidence` for monitoring: `ev-mon-<rule_id>` (mirrored shape).
- `EvidenceVariable` for monitoring: `ev-mon-var-<rule_id>`.
- `EvidenceReport` for hazard: `er-<hazard_id>` (e.g., `er-H-01`).
- `PlanDefinition`: `pd-<scenario-id>`.
- `ActivityDefinition`: `ad-<rule_id>`.
- `ServiceDefinition`: `sd-<cds-hooks-service-id>` (e.g.,
  `sd-htn-pregnancy-denylist`).
- `Citation`: `cit-acc-aha-2025-hbp` (single resource).
- `Observation` (definitional): `od-bp-threshold-<band-id>`.
- `ValueSet`: `vs-<value-set-name-kebab>`.
- `ConceptMap`: `cm-<source>-to-<target>`.
- `Provenance`: `prov-<target-resource-id>`.
- `Group`: `grp-<population-filter-kebab>` (e.g., `grp-pregnant`).
- `StructureDefinition`: `sd-cpg-htn-<extension-name-kebab>`.

Re-runs against identical inputs produce identical resource ids.
The id derivation is byte-stable under the deterministic
canonicalization rules in §4.

#### 3.2 The framework's `cpg-htn-*` extensions

The skill synthesizes the following closed StructureDefinition
extensions, mirroring the extension URLs used in upstream artifacts
(specifically the `cpg-htn-source-anchor` extension on
contraindication `Evidence` resources at P14):

| Extension URL | Cardinality | Encoded fields |
|---|---|---|
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-source-anchor` | 0..1 per resource | `record_id`, `atomic_unit_id`, `anchor_kind`, `sair_sha256`, `page`, `bbox`, `rxnorm_edition_pin` |
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-cor-loe` | 0..1 per resource | `acc_aha_cor`, `acc_aha_loe`, `inheritance_kind`, `note` |
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-population-filter` | 0..* per resource | `population_filter` (closed PopulationFilter values) |
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-cds-posture` | 0..1 per resource | `posture_at_cds`, `cds_hook`, `attending_override_permitted (const false)`, `documentation_only (const false)` |
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-rxnorm-pin` | 0..1 per resource | `rxnorm_edition_pin` |
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-pregnancy-denylist` | 0..1 per resource | `applicability` (closed enum), `manifest_pregnancy_value_set_id`, `attending_override_pattern_scan_clean (const true)` |
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-two-person-witnesses` | 0..* per resource | `role`, `reviewer_id`, `gate`, `cohort_id` |
| `https://aiwg.io/cpg-htn-2025-acc-aha/StructureDefinition/cpg-htn-build-fixity` | 1..1 per resource | `build_run_id`, `build_version_label`, `manifest_payload_sha256`, `gate3_attestation_sha256` |

Every extension is authored as a `StructureDefinition` resource
with the URL above and validated at composition time. Resources
that depend on an extension MUST resolve the extension URL against
the skill's authored set; any unresolved extension URL BLOCKs.

#### 3.3 Per-resource invariants (defense-in-depth)

The skill enforces every parent-schema invariant relevant to the
resource at composition time, even though the upstream artifact's
producer skill already verified them. This is defense-in-depth
against upstream artifact corruption between Gate 3 and P26.

For every resource, the skill verifies:

1. **Source-anchor extension present** (when applicable): every
   `Evidence`, `EvidenceVariable`, `EvidenceReport`,
   `ActivityDefinition`, `ServiceDefinition` MUST carry the
   `cpg-htn-source-anchor` extension with a non-empty
   `record_id` and `atomic_unit_id`.
2. **COR/LOE inheritance preserved**: the `cpg-htn-cor-loe`
   extension's COR / LOE values match the parent record's exactly.
3. **Population filter closed-enum membership**: every
   `cpg-htn-population-filter` extension value is from the closed
   `PopulationFilter` enum.
4. **CDS posture closed-enum membership**: every
   `cpg-htn-cds-posture` extension's `posture_at_cds` and
   `cds_hook` values are from the closed enums in
   `cds-hooks-services-htn.yaml` §2.2 / §2.3.
5. **Attending-override pattern absent**: recursive scan over every
   string field in the resource (and in every authored extension
   URL string content) for the closed AttendingOverridePattern
   from `cds-hooks-services-htn.yaml` §2.5. Match → BLOCK.
6. **PCE-legacy literal absent**: recursive scan over every string
   field for the literal `PCE-legacy`. Match → BLOCK.
7. **Age gate ≥ 18**: every population-bounded resource's
   `useContext` or characteristic carries a non-empty age range
   `low.value == 18`.
8. **Pregnancy denylist mechanical reinforcement**: for every
   resource whose `cpg-htn-population-filter` includes `pregnant`
   or `postpartum` AND whose source rule is a denylist, the
   `cpg-htn-cds-posture` extension MUST satisfy:
   - `posture_at_cds == "hard-refuse"`
   - `cds_hook == "order-select"`
   - `attending_override_permitted == false`
   - `documentation_only == false`
   Validators MUST refuse any deviation; this is the third
   defense-in-depth enforcement of ADR-HTN-001 D8 (the first is at
   P13's `PR-INV-18`, the second at P14's `CIA-INV-13`, the third
   here).
9. **RxNorm pin alignment**: every resource carrying a
   `cpg-htn-rxnorm-pin` extension MUST have its
   `rxnorm_edition_pin` equal to the manifest's pinned RxNorm
   edition. Drift → BLOCK.
10. **Source-anchor SHA recompute**: the
    `cpg-htn-source-anchor.sair_sha256` MUST recompute against
    `work/<run_id>/sair.json` and the parent atomic unit's anchor.
    Drift → BLOCK.

#### 3.4 Profile binding and validation

Every resource's `meta.profile[]` MUST include exactly the manifest-
pinned profile URL for the resource type (per the matrix in §2).
The skill validates every resource against the pinned profile via
the FHIR R5 IG Publisher's profile validator. Any validation
failure BLOCKs with `fhir-profile-validation-failed`.

The skill records the per-resource validation outcome in the IG
package's per-resource `Provenance` resource (see §3.6) and in the
build's per-package fixity manifest (see §5).

#### 3.5 Resource serialization and canonicalization

Every resource is serialized to JSON under FHIR R5 JCS
canonicalization (RFC 8785 with FHIR-specific element ordering
exceptions documented in `docs/fhir-r5-jcs-notes.md`). The
canonicalization is byte-stable across re-runs given identical
input. The per-resource SHA is the SHA-256 of the canonical bytes.

The serialization rules are:

- Every resource's `text.div` is the deterministic narrative
  rendered from the resource's structured content under a closed
  template set in `docs/fhir-r5-narrative-templates.md`. The
  narrative is NOT free-text; it is a deterministic projection of
  the resource's structured fields. This is the framework's
  defense against narrative-divergence attacks.
- Every resource's `meta.security[]` carries a coding from the
  framework's `cpg-htn-2025-security-codes` CodeSystem with
  `code == "fixity-recorded"` and `valueString` set to the
  per-resource SHA. The SHA is the value computed against the
  resource's JCS canonical form with the `meta.security` element
  excluded, then attached after computation. Validators MUST
  recompute and compare.
- Every resource's `meta.versionId` is set to the build's
  `build_version_label` (e.g.,
  `v1.0.0+ACC-AHA-2025+US+2026-04-30`).
- Every resource's `meta.lastUpdated` is set to the IG build's
  composition time-stamp.

#### 3.6 Per-resource `Provenance`

For every resource composed (other than `Provenance` resources
themselves), the skill emits a corresponding `Provenance` resource
that binds the produced resource to:

- The parent run id (`build_run_id`).
- The Gate-3 attestation SHA (`gate3_attestation_sha256`).
- The active manifest payload SHA.
- The producing skill's id (`fhir-implementation-guide-build`).
- The upstream producer skill's id (e.g., `extract-pharm-rules`,
  `extract-contraindications`, `cds-hooks-package-htn`,
  `safety-hbp`).
- Every contributing source-anchor SHA (sair_sha256, atomic unit
  id, record id, rule id).

`Provenance.signature[]` is omitted at this phase (the IG package
itself is not signed at P26; downstream P28 release publishing
applies the release-level signature). However,
`Provenance.signature` is reserved at the resource level for a
non-cryptographic "fixity binding" entry whose `data` field is
the resource's canonical SHA. This makes the per-resource SHA
provable against the `Provenance` resource without recomputation.

### 4. IG package layout

The IG package is materialized at `work/<run_id>/ig/` under the
deterministic layout below. The layout is closed; new directories
require ADR-HTN-001 amendment.
