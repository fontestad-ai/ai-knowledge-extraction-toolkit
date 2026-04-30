---
name: flow-hbp-2025-build
description: Orchestration skill for the cpg-htn-2025-acc-aha framework. Drives the closed twenty-eight-phase build pipeline from source acquisition (P1) through Gate-3 attestation and publication versioning (P28), enforces the three non-overridable human gates (Gate 1 / Gate 2 / Gate 3), pins manifest, tools, terminology, risk engine, and TSAs across phases, and routes every phase through its authorized skill with deterministic resume protocol, append-only run log, and PROV-bundle emission. PCE-legacy never feeds CDS. Pregnancy hard-block enforced at order-select. Manifest is immutable; corrections require a new manifest version. Post-Gate-3 publication is signed and time-stamped.
namespace: cpg-htn-2025-acc-aha
category: orchestrate
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<manifest-path> [--phases <list>] [--from <phase>] [--to <phase>] [--resume] [--mode <build|verify|verify+build>] [--strict] [--dry-run]"
---

# flow-hbp-2025-build

Orchestration skill for the `cpg-htn-2025-acc-aha` framework. The
skill drives the **closed twenty-eight-phase build pipeline** from
source acquisition (P1) through Gate-3 attestation and publication
versioning (P28), enforces the **three non-overridable human gates**
(Gate 1 at the cohort layer, Gate 2 at the Library layer, Gate 3 at
the publication layer), pins manifest, tools, terminology, risk
engine, and TSAs across phases, and routes every phase through its
authorized skill with deterministic resume protocol, append-only run
log, and PROV-bundle emission.

This skill is the **only authorized invoker** of phase skills in
production. It does not author records, atomic units, pharm rules,
contraindications, monitoring artifacts, CQL, CDS Hooks descriptors,
the Safety Case, or the IG; it routes inputs to the authorized
producer skill for each phase and verifies the producer's outputs
against the framework's schemas before advancing. It also does not
sign artifacts; signing is performed by the gate-specific signing
skills (`gate1-sme-review`, `cql-clinician-signoff`,
`safety-case-attest`).

This skill aligns to every schema and skill drafted in this thread:

- `schemas/acc-aha-grading.yaml`
- `schemas/sair.yaml`
- `schemas/recommendation-record-htn.yaml`
- `schemas/atomic-unit.yaml`
- `schemas/gate1-register.yaml`
- `schemas/gate2-register.yaml`
- `schemas/gate3-attestation.yaml`
- `schemas/safety-case-htn.yaml`
- `schemas/cds-hooks-services-htn.yaml`
- `schemas/pharm-rule-htn.yaml`
- `schemas/contraindication-artifact-htn.yaml`
- `schemas/guideline-manifest-hbp-2025.yaml`

And to the per-phase producer skills:
`acquire-hbp-2025-source` (P1), `parse-acc-aha-recbox` (P6),
`extract-recommendation-cor-loe` (P9), `bind-htn-vocab` (P10),
`pico-decompose-htn` (P11), `extract-bp-thresholds` (P12),
`extract-pharm-rules` (P13), `extract-contraindications` (P14),
`extract-monitoring` (P15), `bind-risk-engine` (P16),
`emit-cql-htn` (P20), `cql-test-synthea-htn` (P21),
`cds-hooks-package-htn` (P22), `safety-hbp` (P23),
`copyright-quote-check-acc-aha`, `phi-scrub`,
`safety-case-attest` (Gate 3 / P25), `guideline-docs` (P25),
`fhir-implementation-guide-build` (P26), `guideline-version` (P28),
plus the Gate-1 reviewer interface `gate1-sme-review` and the
two-person-rule queue `parse-reconcile-queue`.

Posture: **caution over velocity, fidelity over coverage,
hard-refusal-on-pregnancy over convenience.** No phase advances
without its authorized producer's seal and the framework's gate
preconditions. No paraphrase. No editing of ACC/AHA COR or LOE. No
silent re-runs. No batch acceptance across phases. No LLM-only
paths. PCE-legacy never feeds CDS. Pregnancy hard-block enforced at
order-select; pregnancy denylist held rules categorically rejected
at P14. Manifest is immutable; corrections require a new manifest
version under panel-chair and medical-director signoff. Post-Gate-3
publication is signed and time-stamped.

## When to Use

Invoke this skill when:

- A new build is requested by the panel chair against an active
  manifest version (typical: a fresh build of the framework against
  a newly-pinned manifest after a source-guideline update or an
  errata watch closure).
- A targeted re-run is needed after a Gate-1 reviewer recorded
  `accept-with-edit` or `reject-rework` on a record at Gate 1, or a
  Gate-2 reviewer recorded `reject-rework` on a Library at Gate 2.
- A regression run is needed against the framework's golden build
  set after a schema, skill, or manifest version change.
- A targeted re-publication is needed after a non-content errata
  closure (e.g., a TSA rotation that does not invalidate prior
  signatures but updates the build's TSA pin).
- A `--mode verify` re-check is needed to recompute every phase's
  determinism against the recorded SHAs (used at audit time and
  pre-Gate-3 by `safety-case-attest`).

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers (`GM-INV-23`).
- The medical-director signoff is not verified (`GM-INV-21`).
- The `tools_lock` SHA does not recompute (`GM-INV-08`).
- A prior build run is in `awaiting-resume` state and a different
  caller is requesting `--from p1`; the orchestrator refuses to
  start a fresh run while a resumeable run is open (the operator
  must explicitly `--withdraw` the prior run first).

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `manifest-path` | yes | — | Path to the active manifest at `manifests/guideline-manifest-hbp-2025.<version>.yaml`, validated against `schemas/guideline-manifest-hbp-2025.yaml`. |
| `--phases <list>` | no | `all` | Comma-separated subset of phase ids `P1..P28` (and the gate ids `gate-1`, `gate-2`, `gate-3`). Default runs the full pipeline. |
| `--from <phase>` | no | `P1` | Start at the named phase. Useful for targeted re-runs. The orchestrator verifies that every phase preceding `--from` has a sealed output and a verifying SHA against the manifest's tools_lock. |
| `--to <phase>` | no | `P28` | Stop after the named phase. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted phase output. The orchestrator rejects resume if the manifest's `fixity.manifest_sha256` has changed since session start. |
| `--mode <build\|verify\|verify+build>` | no | `verify+build` | `build` runs every in-scope phase; `verify` recomputes every phase's recorded SHA against on-disk outputs and reports drift; `verify+build` runs missing phases and verifies all. |
| `--strict` | no | `true` | Fail-closed on every gate. `--strict false` is **never permitted** in production. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned phase sequence with predicted outputs and per-phase preconditions; do not invoke any producer skill. Permitted in production for change-control review. |

## Operation

### 1. Preflight

1. Validate `manifest-path` against `schemas/guideline-manifest-hbp-2025.yaml`.
2. Verify `state == "active"` (`GM-INV-23`); refuse `draft` /
   `awaiting-medical-director-signoff` / `superseded` /
   `withdrawn` manifests.
3. Verify `errata_watch.blockers_open == []` (`GM-INV-23`); refuse
   builds against manifests with open errata blockers.
4. Verify `medical_director_signoff` cryptographically (`GM-INV-21`);
   refuse builds whose director signoff fails to verify.
5. Verify `tools_lock.lock_sha` against canonicalized
   `tools_lock.items[]` (`GM-INV-08`); refuse builds whose lock SHA
   does not recompute.
6. Verify pinned canonical decisions:
   - `risk_engine.name == "PREVENT"` AND `legacy_only == false`
     (`GM-INV-12`).
   - `intended_use.age_min_inclusive == 18` (`GM-INV-24` semantics).
   - `intended_use.pregnancy_value_set_id` is non-empty.
   - `terminology[]` carries pinned RxNorm, ICD-10-CM, SNOMED CT,
     LOINC, and CVX editions per the framework's required-binding
     set.
   - `tools_lock.items[]` includes a family-distinct LLM pair
     (`GM-INV-09`), at least one VLM (for numeric verification at
     P9 / P13 / P14), and a pinned FHIR R5 profile.
   - `tsa_list[]` has at least one TSA whose `cert_valid_until`
     covers the wall-clock window.
7. Open or resume the build run:
   - On a fresh start, allocate a new `run_id` (UUID) and create
     `work/<run_id>/` plus `provenance/<run_id>/` plus
     `reports/<run_id>/`.
   - On `--resume`, verify the manifest pin alignment between the
     prior run's `manifest_payload_sha256` and the current
     manifest's `fixity.manifest_sha256`. Mismatch → BLOCK; require
     fresh run.
8. Acquire the run's write-back lock at `work/<run_id>/.lock`. The
   orchestrator is the only writer into the run directory during
   its lifetime.
9. Write the run's manifest pin and tools_lock pin into
   `work/<run_id>/run-manifest.json` (deterministic, JCS-canonical;
   used by every downstream phase as the canonical pin source).
10. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. The closed twenty-eight phase set

The pipeline is composed of exactly the following twenty-eight
phases plus three non-overridable human gates. The set is **closed**
at the orchestrator level; new phases require ADR-HTN-001 amendment.

| Phase | Authorized producer skill | Output | Schema |
|---|---|---|---|
| **P1**  Source acquisition | `acquire-hbp-2025-source` | `work/<run_id>/source/<sha>.pdf` + per-source manifest | `manifests/source-acquisition.json` |
| **P2**  Reversible normalization | `parse-acc-aha-recbox` (preflight pass) | `work/<run_id>/normalization-log.json` | (inline; SAIR consumes) |
| **P3**  PHI scrub | `phi-scrub` | `work/<run_id>/phi-scrub-report.json` | `schemas/phi-scrub-report.yaml` (forthcoming) |
| **P4**  Copyright quote envelope | `copyright-quote-check-acc-aha` | `work/<run_id>/copyright-envelope.json` | `schemas/copyright-envelope.yaml` (forthcoming) |
| **P5**  SAIR composition | `parse-acc-aha-recbox` | `work/<run_id>/sair.json` | `schemas/sair.yaml` |
| **P6**  Recbox parse | `parse-acc-aha-recbox` | `work/<run_id>/sair.json` (recommendation_boxes[]) | `schemas/sair.yaml` |
| **P7**  Atomic-unit decomposition (preflight) | `extract-recommendation-cor-loe` (preflight) | (inline) | `schemas/atomic-unit.yaml` |
| **P8**  PICO precheck | `pico-decompose-htn` | `work/<run_id>/pico-precheck.json` | `schemas/atomic-unit.yaml` (PICO sub-schema) |
| **P9**  COR/LOE + atomic-unit extraction | `extract-recommendation-cor-loe` | `work/<run_id>/records.json` + `work/<run_id>/atomic-units.json` | `schemas/recommendation-record-htn.yaml`, `schemas/atomic-unit.yaml` |
| **Gate 1** | `gate1-sme-review` | `work/<run_id>/gate1/cohort-<id>.signed.jsonld` | `schemas/gate1-register.yaml` |
| **P10** Terminology binding | `bind-htn-vocab` | `work/<run_id>/terminology-bindings.json` | `schemas/terminology-bindings.yaml` (forthcoming) |
| **P11** PICO decomposition | `pico-decompose-htn` | `work/<run_id>/pico.json` | `schemas/atomic-unit.yaml` (PICO sub-schema) |
| **P12** BP threshold extraction | `extract-bp-thresholds` | `work/<run_id>/bp-thresholds.json` | `schemas/bp-thresholds.yaml` (forthcoming) |
| **P13** Pharmacologic-rule extraction | `extract-pharm-rules` | `work/<run_id>/pharm-rules.json` | `schemas/pharm-rule-htn.yaml` |
| **P14** Contraindication cross-check | `extract-contraindications` | `work/<run_id>/contraindications/cross-check.json` + per-rule FHIR R5 Evidence/EvidenceVariable | `schemas/contraindication-artifact-htn.yaml` |
| **P15** Monitoring extraction | `extract-monitoring` | `work/<run_id>/monitoring-artifact.json` + per-rule FHIR R5 PlanDefinition.action | `schemas/monitoring-artifact-htn.yaml` (forthcoming) |
| **P16** Risk-engine binding | `bind-risk-engine` | `work/<run_id>/risk-engine-binding.json` | `schemas/risk-engine-binding.yaml` (forthcoming) |
| **P17** Resistant-HTN workup binding | `bind-htn-vocab` (resistant-HTN sub-pass) | (inline; feeds P20 Library `ResistantHTN`) | `schemas/terminology-bindings.yaml` |
| **P18** Secondary-HTN screening binding | `bind-htn-vocab` (secondary-HTN sub-pass) | (inline; feeds P20 Library `SecondaryHTNTriggers`) | `schemas/terminology-bindings.yaml` |
| **P19** Special-population modifiers binding | `bind-htn-vocab` (special-pop sub-pass) | (inline; feeds P20 Library `SpecialPopulationModifiers`) | `schemas/terminology-bindings.yaml` |
| **P20** CQL Library emission | `emit-cql-htn` | `work/<run_id>/libraries/<lib-id>.cql` (per Library) | `schemas/cql-library-snapshot.yaml` (forthcoming) |
| **P21** Synthea reference-test pack | `cql-test-synthea-htn` | `work/<run_id>/test-packs/<lib-id>.json` (per Library) | `schemas/test-pack.yaml` (forthcoming) |
| **Gate 2** | `cql-clinician-signoff` | `work/<run_id>/gate2/cohort-<id>.signed.jsonld` | `schemas/gate2-register.yaml` |
| **P22** CDS Hooks packaging | `cds-hooks-package-htn` | `work/<run_id>/cds-hooks/<service-id>.json` + service-set manifest | `schemas/cds-hooks-services-htn.yaml` |
| **P23** Safety Case authoring | `safety-hbp` | `work/<run_id>/safety-case.json` | `schemas/safety-case-htn.yaml` |
| **P24** Guideline Card authoring | `guideline-docs` | `work/<run_id>/docs/guideline-card.md` | (markdown; referenced by Safety Case mitigations) |
| **Gate 3 / P25** Gate-3 attestation | `safety-case-attest` | `work/<run_id>/gate3-attestation.signed.jsonld` | `schemas/gate3-attestation.yaml` |
| **P26** FHIR Implementation Guide build | `fhir-implementation-guide-build` | `work/<run_id>/ig/<published-package>` | (FHIR R5 IG; consumes Evidence/EvidenceVariable + PlanDefinition + Library + ServiceDefinition) |
| **P27** NAM CGAT artifact authoring | `guideline-docs` (CGAT sub-pass) | `work/<run_id>/docs/cgat-matrix.md` | (markdown) |
| **P28** Publication versioning + release | `guideline-version` | `releases/v<semver>+ACC-AHA-2025+US+<date>/` | `schemas/release-manifest.yaml` (forthcoming) |

The orchestrator enforces the order strictly. Skipping a phase
requires `--phases <list>` with explicit operator intent, and the
skipped phase's downstream consumers will refuse to advance until
the skipped phase is later re-run. A targeted run that ends before
Gate 3 is permitted (e.g., `--to P21`) for a build that is intended
only to run through Gate 2.

### 3. Per-phase orchestration loop

For each phase in scope, the orchestrator performs the following:

1. **Phase preflight**: verify the phase's per-phase preconditions
   per §4 (closed per-phase precondition matrix). Refuse to enter
   the phase on any precondition failure.
2. **Resume check**: if `--resume` is set, verify the phase's prior
   output exists and its SHA recomputes against the recorded value
   in the run log. Mismatch → BLOCK; the operator must explicitly
   discard the phase's output before re-running.
3. **Producer invocation**: invoke the authorized producer skill
   with the phase's input parameters. The orchestrator is the
   *only* invoker; producer skills refuse direct invocation in
   production.
4. **Producer-output verification**: validate the producer's output
   against the phase's schema. Refuse advancement on any schema
   validation failure or any cross-field invariant failure.
5. **Per-phase fixity recompute**: recompute the JCS canonical SHA
   of the producer's output against its `fixity` field; refuse
   advancement on mismatch (mirrors per-schema invariants such as
   `PR-INV-17`, `CIA-INV-20`, `SC-INV-17`, etc.).
6. **PROV emission**: append a W3C PROV-O record to
   `provenance/<run_id>/<phase>.jsonld` with the phase's Activity,
   the producer's input Entities (with their SHAs), the producer's
   output Entities (with their SHAs), and the producer Agent.
7. **Run-log append**: append a closed-kind event to the build's
   run log at `work/<run_id>/run-log.jsonld` (see §6).
8. **Notify orchestrator queue**: emit a `phase-complete` or
   `phase-blocked` notification to the orchestrator's queue for
   downstream consumers.

If the phase is **Gate 1**, **Gate 2**, or **Gate 3**, the
orchestrator additionally:

- Verifies the gate's signature cryptographically against the
  signer's `public_key` recorded in the gate register or
  attestation.
- Verifies the time-stamp against the manifest's `tsa_list[]` per
  `GM-INV-23`.
- Verifies cohort-axis attestations are all `true` (`GR-INV-*`,
  `GR2-INV-*`, `GR3-INV-*`, `SC-INV-14`).
- BLOCKs unconditionally on any signature, time-stamp, or
  attestation failure.

### 4. Per-phase preconditions (closed matrix)

Each phase has a closed precondition matrix; the orchestrator
verifies every entry mechanically before phase entry. Failure →
BLOCK with `phase-precondition-failed` and the specific gate
diagnostic.

| Phase | Required prior phases sealed | Required artifacts | Required pins |
|---|---|---|---|
| P1  | (none) | (none) | manifest active, tools_lock verified |
| P2  | P1 | source PDF SHAs recorded | reversible-normalization rules pinned |
| P3  | P2 | normalization log present | PHI detector pin |
| P4  | P3 | normalization log present, PHI report ≡ zero hits | publisher contract window verified |
| P5  | P4 | normalization log + copyright envelope present | (inherits) |
| P6  | P5 | SAIR draft present | recbox parser pin |
| P7  | P6 | SAIR sealed | (preflight only; no output) |
| P8  | P7 | SAIR sealed | (none) |
| P9  | P8 | PICO precheck present | family-distinct LLM pair (`GM-INV-09`); VLM pinned |
| Gate 1 | P9 | records.json + atomic-units.json sealed; PICO precheck attached | reviewer roster per `GR-INV-13`; two-person rule; cohort-axis attestations |
| P10 | Gate 1 finalized for in-scope cohort | (none beyond gate) | RxNorm + ICD-10-CM + SNOMED CT + LOINC + CVX editions pinned |
| P11 | P10 | terminology-bindings.json sealed | (none) |
| P12 | P10 | terminology-bindings.json sealed | (none) |
| P13 | P12 | terminology-bindings.json sealed; bp-thresholds.json sealed | family-distinct LLM pair; VLM pinned; RxNorm pinned |
| P14 | P13 | pharm-rules.json sealed (with panel-chair acknowledgement when held rules present) | RxNorm pinned; FHIR R5 profile pinned |
| P15 | P13 | pharm-rules.json sealed | RxNorm pinned; FHIR R5 profile pinned |
| P16 | P13 | pharm-rules.json sealed | risk_engine == PREVENT (`GM-INV-12`) |
| P17 | P10 | terminology-bindings.json sealed | (none) |
| P18 | P10 | terminology-bindings.json sealed | (none) |
| P19 | P10 | terminology-bindings.json sealed | (none) |
| P20 | P14, P15, P16, P17, P18, P19 | every contributing artifact sealed; risk-engine-binding sealed | CQL engine pin (`tools_lock.items[]` of `kind == "cql-engine"`) |
| P21 | P20 | every Library snapshot sealed | Synthea cohort pin; CQL engine pin |
| Gate 2 | P21 | every Library has reference-test pass; coverage floor ≥ 95% (≥ 99% on pregnancy denylist branch); hard-block invariants verified | reviewer roster per `GR2-INV-*`; two-person rule per cohort; closed concern-category set |
| P22 | Gate 2 finalized for every contributing cohort | every contributing Library `accepted` or `accepted-with-comment` | manifest age-gate ≥ 18; pregnancy value-set id pinned |
| P23 | P22, P14, P15 | service-set manifest sealed; contraindication artifact sealed (`pass`-state rows for clinical hazards H-01..H-07); monitoring artifact sealed | (inherits) |
| P24 | P23 | safety case sealed | (none) |
| Gate 3 / P25 | P24, P23, P22, P14, P3, P4 | service-set manifest, safety case, contraindication artifact, copyright envelope, PHI scrub report, IG bundle, all sealed | medical-director signoff (or designated alternate per `GM-INV-21`); manifest-pinned TSA |
| P26 | Gate 3 attested | gate3-attestation.signed.jsonld present and verifies | FHIR R5 profile pinned |
| P27 | P26 | IG package built | (none) |
| P28 | P27 | every prior phase sealed | release semver policy pinned; manifest-pinned TSA |

Failure of any precondition → BLOCK; the orchestrator routes the
failure to the operator with the specific gate diagnostic and the
remediation hint (e.g., "P10 terminology-bindings.json missing;
re-run P10").

### 5. Three-gate enforcement

The framework's three non-overridable human gates are mechanically
enforced. The orchestrator refuses to bypass any gate under any
circumstance.

#### 5.1 Gate 1 (post-P9)

- The orchestrator partitions records into Gate-1 cohorts per the
  manifest's `gate1.cohort_partitioning_policy` (e.g., one cohort
  per topical chapter or one cohort per ACC/AHA section).
- For each cohort, the orchestrator invokes `gate1-sme-review` to
  produce a Gate-1 register.
- Cohort-axis attestations recorded:
  - records-bound-to-source-anchored-basis
  - cor-loe-extraction-verified
  - dual-llm-family-distinct-met
  - vlm-numeric-verification-clean
  - pregnancy-population-correctly-classified
  - predecessor-2017-mapping-advisory-only
- The register is signed by two reviewers (two-person rule per
  `GR-INV-13`) plus a panel-chair finalization signature.
- The orchestrator verifies every register's signature and time-
  stamp before accepting the cohort as `finalized` and advancing
  to P10.

#### 5.2 Gate 2 (post-P21)

- The orchestrator partitions Libraries into Gate-2 cohorts per the
  manifest's `gate2.cohort_partitioning_policy` (typically one
  cohort per Library or one cohort per Library group bound to a
  related clinical domain).
- For each cohort, the orchestrator invokes `cql-clinician-signoff`
  to produce a Gate-2 register.
- Cohort-axis attestations recorded:
  - typecheck-clean
  - synthea-coverage-ge-95
  - hard-block-invariants-verified
  - pregnancy-denylist-coverage-ge-99
  - pce-legacy-not-bound
  - prevent-canonical-bound
  - cds-hooks-services-wired-claim-recorded
- The register is signed by two reviewers from distinct families
  per `GR2-INV-*` plus a panel-chair finalization signature.
- The orchestrator verifies every register's signature and time-
  stamp before accepting the cohort as `finalized` and advancing
  to P22.

#### 5.3 Gate 3 (post-P24)

- The orchestrator invokes `safety-case-attest` to produce a Gate-3
  attestation.
- The attestation binds a closed bundle of Gate-3 evidence:
  `gate3.signed`, `safe`, `cdsh`, `ig`, `cont`, `mon`, `cpr`,
  `phi`, plus the build manifest pin.
- Cohort-axis attestations recorded:
  - iso14971-compliance-attested
  - no-relax-of-hard-block-attested
  - pce-legacy-never-propagates-attested
  - pregnancy-order-select-hardrefuse-attested
  - errata-watch-attested
  - source-admission-attested
  - mitigation-verification-attested
  - acceptable-residual-risk-within-ceiling-attested
- The attestation is signed by the medical director (or designated
  alternate per `GM-INV-21`) at IAL3/AAL3 and time-stamped via a
  manifest-pinned TSA.
- The orchestrator verifies the signature and time-stamp before
  permitting P26 (IG build).

### 6. Run log (append-only)

The orchestrator maintains an append-only run log at
`work/<run_id>/run-log.jsonld` recording every event, with closed
event kinds:

- `run-opened`
- `phase-entered`
- `phase-precondition-failed`
- `phase-completed`
- `phase-output-verified`
- `phase-output-sha-mismatch`
- `gate-1-cohort-partitioned`
- `gate-1-cohort-finalized`
- `gate-2-cohort-partitioned`
- `gate-2-cohort-finalized`
- `gate-3-attested`
- `errata-blocker-detected`
- `manifest-drift-detected`
- `tools-lock-drift-detected`
- `tsa-rotation-detected`
- `held-rule-routed-to-queue`
- `blocked-rule-routed-to-panel-chair`
- `panel-chair-acknowledgement-recorded`
- `family-distinct-rule-violated`
- `pregnancy-denylist-soft-warning-detected`
- `pregnancy-denylist-attending-override-pattern-detected`
- `pce-legacy-binding-detected`
- `phi-fail-closed`
- `copyright-envelope-exceeded`
- `run-paused`
- `run-resumed`
- `run-completed`
- `run-superseded`
- `run-withdrawn`

Each event carries `event_id`, `occurred_at`, `kind`, `actor_id`,
`payload_sha256`, and (when applicable) the originating phase id
and the affected artifact id. The run log is signed at
`run-completed` time with a JCS canonical SHA-256 over the chained
event hash; mutation attempts are tamper-evident.

### 7. Manifest-pin propagation

The orchestrator's central responsibility is **manifest-pin
propagation**. Every producer skill consumes the same canonical
pin source at `work/<run_id>/run-manifest.json`, which records:

- The active manifest's `fixity.manifest_sha256`.
- `tools_lock.items[]` (LLM pair, VLM, CQL engine, FHIR R5 profile,
  recbox parser, PHI detector, etc.).
- `terminology[]` (RxNorm + ICD-10-CM + SNOMED CT + LOINC + CVX
  editions).
- `risk_engine.name == "PREVENT"`, `legacy_only == false`.
- `intended_use.age_min_inclusive == 18`,
  `intended_use.pregnancy_value_set_id`.
- `tsa_list[]` (TSAs with cert validity windows).
- `signature_policy` (algorithms, IAL/AAL minimums per signer
  role).

Producer skills do **not** read the live manifest; they read
`run-manifest.json`. The orchestrator is the only writer to this
file, and the file is sealed with a JCS canonical SHA at run open.
This isolates each build run from concurrent manifest updates: a
new manifest version supersedes the prior version, but in-flight
runs continue under their pinned snapshot until completion or
withdrawal.

### 8. Drift detection

The orchestrator runs the following drift detectors at every phase
entry and at `--mode verify`:

- **Manifest drift**: re-resolve the active manifest's
  `fixity.manifest_sha256` and compare to the run's pinned value.
  Drift indicates a new manifest version was activated mid-run;
  the orchestrator pauses the run and records `manifest-drift-
  detected`. The operator must explicitly choose to resume against
  the new manifest (rare; typically the run is withdrawn and a new
  run started).
- **Tools-lock drift**: re-resolve `tools_lock.lock_sha` and
  compare. Drift indicates the lock was rotated; the orchestrator
  pauses and records `tools-lock-drift-detected`.
- **TSA rotation**: re-resolve `tsa_list[]`. If the originally-pinned
  TSA's `cert_valid_until` has expired since run open, the
  orchestrator records `tsa-rotation-detected` and routes
  downstream signing steps to a non-expired TSA.
- **Errata watch**: re-resolve `errata_watch.blockers_open[]`. If
  any blocker has opened since run open, the orchestrator pauses
  and records `errata-blocker-detected`. Resume requires either
  closure of the blocker or a new manifest version excluding the
  blocker.
- **Per-input drift**: at every phase, the orchestrator recomputes
  the SHA of every input artifact against the value recorded in the
  prior phase's PROV bundle. Drift indicates artifact mutation
  outside the orchestrator's lock (e.g., a manual edit) and BLOCKs
  with `phase-output-sha-mismatch`.

### 9. Held / blocked routing

The orchestrator handles held and blocked outcomes from producer
skills uniformly:

- **Held**: a producer recorded a held outcome (e.g., a P13 held
  rule, a P14 held cross-check row). The orchestrator:
  - records `held-rule-routed-to-queue` in the run log;
  - confirms the queue entry exists at the producer-recorded path
    and validates against `parse-reconcile-queue`'s schema;
  - pauses downstream phases that consume the held artifact (per
    each held artifact's downstream-consumer matrix);
  - waits for the two-person-rule resolution before resuming.
  - For pharm-rule-htn `panel_chair_acknowledgement` paths
    (`PR-INV-21` semantics), the orchestrator additionally verifies
    that the chair's acknowledgement is signed and time-stamped,
    that no pregnancy denylist held rule is acknowledged, and that
    downstream phases consume the held rule with the held flag
    intact.
- **Blocked**: a producer recorded a blocked outcome (e.g., a P14
  blocked row, a `pregnancy-denylist-attending-override-pattern-
  detected` event). The orchestrator:
  - records `blocked-rule-routed-to-panel-chair` in the run log;
  - pauses every downstream phase for the blocked artifact's
    parent record;
  - routes the parent record to `gate1-sme-review --mode chair-
    finalize` with the closed concern category;
  - waits for the panel-chair adjudication before resuming.

The orchestrator never auto-resolves held or blocked outcomes.

### 10. Determinism and reproducibility

- The orchestrator's behavior is deterministic given:
  - identical manifest pin;
  - identical inputs (source PDF SHAs);
  - identical pinned tools (LLM pair, VLM, CQL engine, FHIR R5
    profile, etc.);
  - identical pinned terminology editions.
- Re-running the orchestrator on a sealed build with `--mode
  verify` is a no-op that recomputes every phase's SHA and reports
  drift if any phase output has been mutated outside the lock.
- Re-running with `--mode build` and `--from <phase>` against a
  sealed build re-executes the phase's producer; the produced
  artifact's SHA is compared to the recorded value, and the
  orchestrator BLOCKs on any drift.
- The deterministic id derivation cascades from manifest +
  source SHAs through every downstream artifact: every artifact's
  id is recomputable from its inputs, so re-runs renumber nothing.
- Held rules' downstream consumption respects the held flag; a
  re-run on identical inputs produces identical held / pass /
  blocked outcomes (modulo non-deterministic LLM outputs at P9 /
  P13, which the orchestrator routes to the queue rather than into
  canonical artifacts).

## DQA Gates Enforced By This Skill

| Gate | Condition for advance |
|---|---|
| **GO-A** Manifest active | Active manifest with verified medical-director signoff and zero open errata blockers. |
| **GO-B** Tools lock verified | `tools_lock.lock_sha` recomputes against canonicalized items. |
| **GO-C** Run-manifest sealed | `run-manifest.json` is written and SHA-recorded at run open. |
| **GO-D** Closed phase set | Every phase invoked is in the closed twenty-eight-phase set; phases are entered in the canonical order modulo `--phases <list>` overrides. |
| **GO-E** Per-phase preconditions | Every phase's per-phase precondition matrix is satisfied before entry. |
| **GO-F** Authorized producer only | Every phase is invoked exclusively against its authorized producer skill. |
| **GO-G** Producer-output schema validation | Every producer's output validates against its schema and every cross-field invariant. |
| **GO-H** Per-phase fixity recompute | Every artifact's recorded SHA recomputes deterministically from its JCS canonical form. |
| **GO-I** Three-gate enforcement | Gate 1, Gate 2, Gate 3 are all reached, signed, time-stamped, and cohort-axis-attested before downstream phases advance. |
| **GO-J** Drift detection clean | No manifest, tools-lock, TSA, or errata drift between phase entries. |
| **GO-K** Held / blocked routing accounted | Every held outcome has a queue entry; every blocked outcome has paused downstream phases and routed for panel-chair re-review. |
| **GO-L** PCE-legacy never propagates | No phase output references PCE-legacy in any field; the orchestrator scans cumulative outputs at every phase entry. |
| **GO-M** Pregnancy hard-block enforced | Gate 1 attests pregnancy population correctly classified; Gate 2 attests pregnancy denylist branch coverage ≥ 99%; P22 enforces order-select hard-refuse with no attending-override; Gate 3 attests pregnancy-order-select-hardrefuse-attested. |
| **GO-N** Append-only run log | Every event recorded in canonical order; chained-hash continuity verifies. |
| **GO-O** Post-Gate-3 immutability | Once Gate 3 attests, neither phase outputs nor the run log may be mutated; mutation attempts are tamper-evident. |

Failure of any gate at any phase → BLOCK; the orchestrator routes
the failure to the operator with the specific gate diagnostic.
There is **no override**.

## Outputs

- Run directory at `work/<run_id>/` with all phase outputs.
- Run manifest pin at `work/<run_id>/run-manifest.json`.
- Append-only run log at `work/<run_id>/run-log.jsonld`.
- PROV bundle directory at `provenance/<run_id>/<phase>.jsonld`.
- Per-phase reports at
  `reports/<run_id>/<phase>-report.md` summarizing inputs, outputs,
  preconditions verified, and any blockers.
- Per-run summary report at `reports/<run_id>/run-summary.md`.
- Release directory at `releases/v<semver>+ACC-AHA-2025+US+<date>/`
  (P28 only).
- Notifications to the orchestrator's queue:
  - `phase-complete` per phase.
  - `phase-blocked` per phase failure.
  - `gate-finalized` per gate finalization.
  - `run-completed` on full success.
  - `run-paused` on held / blocked.
  - `run-superseded` / `run-withdrawn` on lifecycle transitions.

## Error Handling

- **Manifest stale or not active.** BLOCK preflight; emit
  `manifest-drift-detected`; require new manifest version or
  revert to active.
- **Tools-lock drift.** BLOCK preflight; emit
  `tools-lock-drift-detected`.
- **Phase precondition failed.** BLOCK phase entry; emit
  `phase-precondition-failed`; route to operator with remediation
  hint.
- **Producer schema validation failed.** BLOCK; emit the
  producer's specific failure event; require upstream re-run.
- **Per-phase fixity mismatch.** BLOCK; emit
  `phase-output-sha-mismatch`; investigate canonicalization drift
  or external mutation.
- **Held outcome.** Pause downstream phases; emit
  `held-rule-routed-to-queue`; await two-person-rule resolution.
- **Blocked outcome.** Pause downstream phases; emit
  `blocked-rule-routed-to-panel-chair`; await panel-chair
  adjudication.
- **Family-distinct rule violated.** BLOCK at P9 / P13 / P14; emit
  `family-distinct-rule-violated`; require new manifest version
  with a different LLM pair.
- **Pregnancy denylist soft-warning detected.** BLOCK
  unconditionally at P13 / P14 / P22 / P23; emit
  `pregnancy-denylist-soft-warning-detected`; investigate as
  adversarial input.
- **Pregnancy denylist attending-override pattern detected.** BLOCK
  unconditionally at P13 / P14 / P22 / P23; emit
  `pregnancy-denylist-attending-override-pattern-detected`;
  investigate as adversarial input.
- **PCE-legacy binding detected.** BLOCK unconditionally at any
  phase; emit `pce-legacy-binding-detected`; require upstream
  remediation under ADR-HTN-001 D5.
- **PHI fail-closed.** BLOCK at P3; emit `phi-fail-closed`; require
  source remediation or new source acquisition.
- **Copyright envelope exceeded.** BLOCK at P4; emit
  `copyright-envelope-exceeded`; require quote-envelope
  remediation.
- **Gate signature failed.** BLOCK at the gate; emit a gate-specific
  signature-failure event; require the gate's signing skill to
  re-sign.
- **TSA unavailable.** Hold the in-flight gate signing; poll the
  next TSA in `tsa_list[]`; after exhausting, BLOCK.
- **Errata blocker opened mid-run.** Pause the run; emit
  `errata-blocker-detected`; await closure or new manifest version.
- **Lock contention** on the run directory. Wait up to a configured
  timeout; fail-closed if not acquired; concurrent writers are not
  permitted.
- **Resume after manifest SHA change.** Reject; require fresh run.
- **Direct-edit attempt against any phase output.** Reject; emit
  `phase-output-sha-mismatch` (the orchestrator detects via SHA
  recompute on next phase entry); investigate as adversarial input.

## Examples

```bash
# Default first-pass full build of the framework
flow-hbp-2025-build manifests/guideline-manifest-hbp-2025.v1.0.0+ACC-AHA-2025+US+2026-04-30.yaml

# Targeted re-run from P13 to Gate 2 after a Gate-1 reviewer
# accept-with-edit triggered P9 re-extract
flow-hbp-2025-build manifests/guideline-manifest-hbp-2025.v1.0.0+ACC-AHA-2025+US+2026-04-30.yaml \
  --from P13 --to gate-2 \
  --resume

# Verify-only re-check of a sealed build (used by audit teams)
flow-hbp-2025-build manifests/guideline-manifest-hbp-2025.v1.0.0+ACC-AHA-2025+US+2026-04-30.yaml \
  --mode verify

# Build through Gate 2 only (no Gate-3 attestation; useful for
# dry-runs against a draft manifest version)
flow-hbp-2025-build manifests/guideline-manifest-hbp-2025.v1.0.0-rc1+ACC-AHA-2025+US+2026-04-30.yaml \
  --to gate-2

# Re-publication after a TSA rotation that does not invalidate the
# prior signature
flow-hbp-2025-build manifests/guideline-manifest-hbp-2025.v1.0.1+ACC-AHA-2025+US+2026-05-15.yaml \
  --from P28

# Dry-run plan emission for change-control review
flow-hbp-2025-build manifests/guideline-manifest-hbp-2025.v1.0.0+ACC-AHA-2025+US+2026-04-30.yaml \
  --dry-run