---
name: safety-case-attest
description: Reviewer-interface skill for Gate 3 — pre-publish safety-case attestation by the medical director (and optional second attester per institutional policy). Constructs the canonical Gate-3 bundle, recomputes its content hash from live artifacts, renders a data-only review surface over the safety case, hazard log, gate registers, coverage, PHI/copyright reports, IG build, and supersession communication, and produces a cryptographically-signed Attestation entry against schemas/gate3-attestation.yaml. Decline-without-publish semantics. No relaxation of any prior gate. No publication path bypass. Post-attestation bundle is immutable; corrections require a new attestation version with explicit predecessor.
namespace: cpg-htn-2025-acc-aha
category: gate
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<attestation-path> [--build-id <id>] [--attester <id>] [--mode <browse|attest|decline|second-attest>] [--resume]"
---

# safety-case-attest

Reviewer-interface skill for **Gate 3** of the `cpg-htn-2025-acc-aha`
framework. The skill is the only authorized producer of `Attestation`
entries on the Gate 3 record defined in `schemas/gate3-attestation.yaml`.
It constructs the canonical Gate-3 bundle from live build artifacts,
recomputes the bundle's SHA-256 from those live artifacts, renders a
data-only review surface, captures the medical director's pre-publish
attestation (and an optional second attester where institutional policy
requires dual control), and emits the FHIR `Provenance` resource that
unblocks publication (P28).

This skill does **not** generate clinical content, edit recommendations,
modify CQL Libraries, alter CDS Hooks services, or change the safety
case. It is a *signature surface* over a complete, build-final artifact
set. Every attestation binds a named individual with credential evidence
to the SHA-256 of the canonical Gate-3 bundle at a specific time,
time-stamped by an RFC 3161 TSA pinned in the active manifest.

Posture: **caution over velocity, fidelity over coverage, decline over
override.** No batch attestation. No relaxation of any prior gate. No
publication without verifying attestation. **An attestation may decline
to publish; it cannot override a prior gate's reject.** Post-attestation
bundle content is immutable; corrections require a new attestation
version with an explicit predecessor chain.

This skill is the operational analogue of `gate1-sme-review` and
`cql-clinician-signoff` at the **build** level: where Gate 1 attests
records and Gate 2 attests Libraries, Gate 3 attests the entire build
and authorizes publication.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P28 → ◆ Gate 3**
  and posts a draft Gate 3 attestation document at
  `work/<run_id>/gate3/attestation.draft.jsonld`.
- A medical director (or named designate, per ADR-HTN-001 D9) is
  scheduled to review the bundle and either attest or decline.
- An optional second attester (e.g., compliance officer, chief medical
  informatics officer) is scheduled where institutional policy requires
  dual control.
- A previously declined attestation needs to be reviewed for the
  reasons-of-decline against a re-built bundle (the skill never modifies
  the bundle; the orchestrator re-runs upstream phases under the
  decline's recorded rationale).

Do **not** invoke this skill if:

- The active manifest's `medical_director_signoff` is missing or fails
  verification (manifest signing key and Gate 3 signing key are
  conceptually distinct but both must verify).
- Any Gate 1 cohort or Gate 2 cohort referenced by the build is in any
  state other than `finalized`.
- Any Library is below the 95% Synthea coverage floor.
- The orchestrator's PHI scrub (P24) has any open positive detection.
- The orchestrator's copyright quote-extent check (P25) is in any state
  other than green.
- The HL7 FHIR Validator (P26) is not green across all resources.
- The orchestrator has not posted the Gate 3 bundle to this skill's
  queue.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `attestation-path` | yes | — | Path to a Gate 3 attestation document at `work/<run_id>/gate3/attestation.draft.jsonld`, validated against `schemas/gate3-attestation.yaml`. The skill writes back atomically. After successful attest or decline, the file is renamed to `attestation.signed.jsonld` (attest) or `attestation.declined.jsonld` (decline). |
| `--build-id <id>` | no | derived from `attestation-path` | The build run id; defaults to the run id recorded in the attestation document. The skill rejects mismatch. |
| `--attester <id>` | no | — | The attester id (`rev-<16hex>`) for the current session. Required in `--mode attest`, `--mode decline`, or `--mode second-attest`. The skill refuses to act on behalf of any other attester. |
| `--mode <browse\|attest\|decline\|second-attest>` | no | `browse` | `browse` renders the bundle review surface read-only. `attest` opens an authenticated medical-director attestation session. `decline` opens an authenticated decline session. `second-attest` opens an authenticated session for a second attester (where institutional policy requires dual control). |
| `--resume` | no | `false` | Resume an interrupted session from the last persisted state. The skill rejects resume if the bundle's recomputed `bundle_sha256` has changed since session start. |
| `--strict` | no | `true` | Fail-closed on every invariant. Setting `--strict false` is **never permitted** in production; the flag exists only for fixture and golden-set development. |

## Operation

### 1. Preflight

1. Validate `attestation-path` against `schemas/gate3-attestation.yaml`.
   Reject on any invariant failure (`G3A-INV-01` … `G3A-INV-22`).
2. Re-resolve `guideline_manifest_ref`; verify the active manifest's
   `medical_director_signoff` cryptographically (`GM-INV-21`); verify
   `state == "active"` and `errata_watch.blockers_open == []`.
3. Verify the attestation document's `build.run_id` matches the run id
   recorded in the build's PROV bundle.
4. Verify Gate 1 and Gate 2 prerequisites:
   - Every `gate1_register_ref[*]` resolves to a Gate 1 register file
     whose `cohort.state == "finalized"` and which validates against
     `schemas/gate1-register.yaml`.
   - Every `gate2_register_ref[*]` resolves to a Gate 2 register file
     whose `cohort.state == "finalized"` and which validates against
     `schemas/gate2-register.yaml`.
5. Verify build-level prerequisites:
   - PHI scrub report (P24) has zero hits across every artifact in the
     bundle.
   - Copyright quote-extent report (P25) is green: per-page footprint
     ≤ `quote_envelope.chars_per_page_max` and document-wide footprint
     ≤ `quote_envelope.chars_per_document_max`; figures/tables verbatim
     reproduction permitted only when explicitly enabled.
   - HL7 FHIR Validator (P26) is green across all resources.
   - IG build (P26) succeeded with all Plans, Activities, Libraries,
     ValueSets, CodeSystems, and Communication resources reachable from
     the IG entry point.
   - The supersession `Communication` resource (manifest's
     `supersession.communication_resource.resource_path`) is present in
     `work/<run_id>/fhir/` and is wired to the IG.
6. Verify `tsa_list[]` in the manifest has at least one TSA whose
   `cert_valid_until` covers the wall-clock window. Otherwise BLOCK.
7. In `--mode attest` or `--mode decline`:
   - Resolve `--attester` to a `MedicalDirectorAttester` in
     `attestation.attesters[]`.
   - Verify the attester's `identity_proof.ial == "IAL3"` and
     `aal == "AAL3"`.
   - Verify the attester holds at least one `Credential` of kind
     `medical-director` or `institutional-credential` with appropriate
     scope, valid at session wall-clock time.
   - Verify the attester has at least one `coi_disclosures[]` entry.
   - Authenticate via the institutional KMS bound to the attester's
     `key_id`.
8. In `--mode second-attest`:
   - Resolve `--attester` to a `SecondAttester` in
     `attestation.attesters[]` whose role is one of:
     `compliance-officer`, `chief-medical-informatics-officer`,
     `medical-director` (alternate), or `panel-chair-cohort`.
   - Verify `identity_proof.ial >= "IAL2"`, `aal >= "AAL2"` (institutional
     policy may pin higher).
   - Authenticate via the institutional KMS bound to the second
     attester's `key_id`.
9. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Bundle construction

The Gate 3 bundle is the canonical, exhaustive set of artifacts the
medical director attests. The skill **constructs the bundle from live
artifacts**; it does not trust any pre-recorded hash.

#### 2.1 Bundle members (closed list)

Every member is required. Missing members BLOCK; the skill refuses to
present an incomplete bundle for attestation.

| Member id | Source artifact | Notes |
|---|---|---|
| `mfst` | The active `guideline-manifest-hbp-2025.yaml` instance | Pinned by `guideline_manifest_ref`. |
| `sair` | The sealed SAIR document at `work/<run_id>/sair.json` | Sealed at end of P8. |
| `recs` | The sealed RecommendationRecord set at `work/<run_id>/records.json` | Sealed at end of P9. |
| `aus`  | The atomic-unit set at `work/<run_id>/atomic-units.json` | Produced under §4.2 of `extract-recommendation-cor-loe`. |
| `g1`   | All Gate 1 register files at `work/<run_id>/gate1/*.signed.jsonld` | Each in state `finalized`. |
| `g2`   | All Gate 2 register files at `work/<run_id>/gate2/*.signed.jsonld` | Each in state `finalized`. |
| `cql`  | All CQL Libraries and their ELM under `work/<run_id>/cql/<library_id>/` | Nine Libraries per framework spec §9. |
| `cov`  | Synthea coverage reports at `work/<run_id>/cql/coverage/*.json` | Per-Library; ≥ 95.0%. |
| `cdsh` | All CDS Hooks service descriptors at `work/<run_id>/cds-hooks/*.json` | Seven services per framework spec §7. |
| `safe` | The Safety Case at `work/<run_id>/safety/safety-case.signed.jsonld` | Hazard log + risk evaluation + residual-risk justification. |
| `phi`  | The PHI scrub report at `work/<run_id>/reports/phi-<run_id>.md` | Zero hits. |
| `cpr`  | The copyright quote-extent report at `work/<run_id>/reports/copyright-<run_id>.md` | Per-page and document-wide caps respected. |
| `ig`   | The IG build artifacts at `work/<run_id>/ig/` | HL7 Validator green. |
| `comm` | The supersession `Communication` resource at the manifest's `supersession.communication_resource.resource_path` | Required on first publish from the manifest; idempotent on re-publish. |
| `card` | The Guideline Card at `work/<run_id>/docs/guideline-card.md` | AGREE II ≥ 70% auto-fill; remaining HUMAN-FILL items resolved at this gate or rejected. |
| `cgat` | The NAM CGAT 8-standard attestation matrix at `work/<run_id>/docs/cgat-matrix.md` | Reviewer-completed at this gate. |
| `rtm`  | The Regulatory Traceability Matrix at `work/<run_id>/docs/regulatory-traceability.md` | Cross-references hazards to mitigations to test evidence. |
| `prov` | The build PROV bundle at `provenance/flow-<run_id>.jsonld` | Complete through P27. |

#### 2.2 Canonical bundle hash construction

1. For each bundle member, compute its content hash:
   - For JSON / JSON-LD / YAML files (mfst, sair, recs, aus, g1, g2,
     cdsh, safe, ig, comm, prov), apply RFC 8785 (JCS) canonicalization
     and hash with SHA-256.
   - For CQL/ELM directories (cql), produce a deterministic JCS object
     `{ "files": [ { "path": <relative>, "sha256": <hex> }, ... ] }`
     ordered by path ascending and hash with SHA-256.
   - For text/Markdown files (phi, cpr, card, cgat, rtm), compute the
     SHA-256 of the raw bytes after Unicode NFC normalization and
     trailing-newline normalization.
2. Compose a `BundleManifest` JCS object:
   ```json
   {
     "schema_version": "1.0.0",
     "build_run_id": "<uuid>",
     "manifest_version": "<semver>",
     "members": [
       { "id": "mfst", "kind": "manifest", "sha256": "<hex>" },
       { "id": "sair", "kind": "sair",     "sha256": "<hex>" },
       /* ... every member id from §2.1, in id ascending order ... */
     ]
   }