---
name: cql-clinician-signoff
description: Reviewer-interface skill for Gate 2 CQL clinician + informaticist signoff. Renders the data-only review surface for each CQL Library produced by emit-cql-htn, captures two independent reviewer decisions per Library under a domain-correct composition matrix, produces cryptographically-signed LibrarySignoff entries against schemas/gate2-register.yaml, enforces the no-relax-of-hard-block rule, requires Synthea branch coverage ≥ 95%, and finalizes the cohort under panel-chair signoff. No batch acceptance. No changes to denylists. No reviewer self-pairing. Post-signoff Library content is immutable.
namespace: cpg-htn-2025-acc-aha
category: gate
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<register-path> [--cohort <id>] [--reviewer <id>] [--library <id>] [--mode <browse|sign|chair-finalize>] [--resume]"
---

# cql-clinician-signoff

Reviewer-interface skill for **Gate 2** of the `cpg-htn-2025-acc-aha`
framework. The skill is the only authorized producer of `LibrarySignoff`
entries on the Gate 2 cohort register defined in
`schemas/gate2-register.yaml`. It renders a Library-scoped, data-only
review surface, captures two independent reviewer decisions per Library
under the composition matrix in `gate2-register.yaml` §1, escalates
disagreements to the panel chair, and finalizes the Library cohort under
panel-chair signoff so the orchestrator may package CDS Hooks (P22).

This skill does **not** generate clinical content, edit recommendation
text, re-grade COR/LOE, modify CQL code, or perform extraction. It is a
*signature surface* over Library artifacts already produced and gated by
the deterministic pipeline (`emit-cql-htn` and `cql-test-synthea-htn`).
Every reviewer's signature binds a named individual with credential
evidence to the SHA-256 of a specific Library snapshot at a specific time,
time-stamped by an RFC 3161 TSA pinned in the active manifest.

Posture: **caution over velocity, fidelity over coverage, computable
behavior over editorial intent.** Two-person rule, no batch acceptance, no
denylist relaxation, no risk-engine substitution, no self-pairing, no
override on auto-disqualifying COI, and **no Library advances on Synthea
branch coverage below 95%**. Post-signoff Library content is immutable;
corrections require a new Library snapshot with explicit predecessor
chain.

This skill is the operational analogue of `gate1-sme-review`, but with
**Library** as the unit of attestation rather than a single
recommendation record. Library granularity reflects how the Library is
actually deployed: as one indivisible computable artifact wired to one or
more CDS Hooks services.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P21 → ◆ Gate 2**
  and posts a Gate 2 cohort register at
  `work/<run_id>/gate2/<cohort>.signed.jsonld`.
- A specific reviewer (the hypertension specialist, the clinical
  informaticist, or the domain-matched specialist for `PregnancyHTN`,
  `ResistantHTN`, `SecondaryHTNTriggers`, `HypertensiveUrgencyEmergency`)
  is scheduled to review Libraries assigned to them in that cohort.
- A panel chair is scheduled to dispose of escalated Libraries and
  finalize the cohort for advance to P22.
- A previously held cohort needs to be resumed after the orchestrator
  re-authored a Library, regenerated coverage reports, or the manifest's
  TSA list rotated.

Do **not** invoke this skill if:

- The cohort register's `state` is `finalized`, `superseded`, or
  `withdrawn`.
- The active manifest's `medical_director_signoff` is missing or fails
  verification.
- Any Library bound to the cohort has Synthea branch coverage below 95%.
  The skill will display the report, but `--mode sign` is disabled for
  any such Library.
- Any Library has a typecheck failure under the pinned CQL runtime.
- The orchestrator has not yet posted the cohort to this skill's queue.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `register-path` | yes | — | Path to a Gate 2 register at `work/<run_id>/gate2/<cohort>.signed.jsonld`, validated against `schemas/gate2-register.yaml`. The skill writes back atomically. |
| `--cohort <id>` | no | derived from `register-path` | Cohort id; defaults to the cohort recorded in the register. The skill rejects mismatch. |
| `--reviewer <id>` | no | — | The reviewer id (`rev-<16hex>`) for the current session. Required in `--mode sign`. The skill refuses to act on behalf of any other reviewer in the same session. |
| `--library <id>` | no | `next` | The specific Library id (`lib-<16hex>`) to review next. Defaults to the next Library in the reviewer's pending queue (deterministic ordering by `library_id` ascending, skipping Libraries the reviewer cannot sign per composition / COI / coverage rules). |
| `--mode <browse\|sign\|chair-finalize>` | no | `browse` | `browse` renders the review surface read-only. `sign` opens an authenticated signing session (requires `--reviewer`). `chair-finalize` opens the panel-chair finalization surface (requires the reviewer's role == `panel-chair`). |
| `--resume` | no | `false` | Resume an interrupted session from the last persisted decision. The skill rejects resume if the register's `fixity.register_sha256` has changed since session start. |
| `--strict` | no | `true` | Fail-closed on every invariant. Setting `--strict false` is **never permitted** in production; the flag exists only for fixture and golden-set development. |

## Library scope

The framework emits exactly nine CQL Libraries (per the framework spec §9
and `flow-hbp-2025-build` §8.1). Gate 2 covers all nine:

| Library id | Library name | Domain |
|---|---|---|
| `lib-hbp-staging` | `HBPStaging` | classification |
| `lib-hbp-prevent-risk` | `PreventRisk` | risk-stratification |
| `lib-hbp-treatment-threshold` | `TreatmentThreshold` | pharmacologic-general |
| `lib-hbp-firstline-selection` | `FirstLineSelection` | pharmacologic-general |
| `lib-hbp-special-pop-modifiers` | `SpecialPopulationModifiers` | special-populations-modifiers |
| `lib-hbp-pregnancy` | `PregnancyHTN` | pregnancy-postpartum |
| `lib-hbp-resistant` | `ResistantHTN` | resistant-htn |
| `lib-hbp-secondary` | `SecondaryHTNTriggers` | secondary-htn |
| `lib-hbp-urgency-emergency` | `HypertensiveUrgencyEmergency` | urgency-emergency |

Each Library is reviewed and signed independently. There is no "Library
group" signoff; institutional policy may bundle multiple Libraries into a
single reviewer session, but each Library produces its own
`LibrarySignoff` record.

## Operation

### 1. Preflight

1. Validate `register-path` against `schemas/gate2-register.yaml`. Reject
   on any invariant failure (`G2R-INV-01` … `G2R-INV-30`).
2. Re-resolve `guideline_manifest_ref`; verify the active manifest's
   `medical_director_signoff` cryptographically (`GM-INV-21`); verify
   `state == "active"` and `errata_watch.blockers_open == []`.
3. Verify the register's `cohort.run_id` matches the run id recorded in
   the build's PROV bundle, and that the Gate 1 register(s) feeding this
   build's `RecommendationRecord[]` are in state `finalized`.
4. For every Library bound to the cohort:
   - Load the Library snapshot from `work/<run_id>/cql/<library_id>/`:
     - The CQL source file(s) and their SHA-256.
     - The compiled ELM (if present) and its SHA-256.
     - The typecheck report from the pinned CQL runtime.
     - The Synthea coverage report from `cql-test-synthea-htn`.
     - The reference test outputs.
     - The bound RecommendationRecord ids and atomic-unit ids
       (the Library's "clinical input set").
     - The bound ValueSet/CodeSystem ids and pinned terminology editions
       (the Library's "terminology input set").
     - The bound risk-engine binding (PREVENT) where applicable.
   - Recompute the Library's `library_content_hash` over all of the above
     in JCS-canonical form and verify it equals the value in the register.
   - Verify the typecheck report shows zero errors and no warnings
     promoted to errors by the manifest's policy.
   - Verify the coverage report's per-branch coverage ≥ 95.0%.
5. Verify `tsa_list[]` in the manifest has at least one TSA whose
   `cert_valid_until` covers the wall-clock window. Otherwise BLOCK.
6. In `--mode sign`:
   - Resolve `--reviewer` to a `Reviewer` in `panel.reviewers[]`.
   - Verify the reviewer's `identity_proof.ial` ≥ `IAL2`,
     `identity_proof.aal` ≥ `AAL2`, and at least one `Credential` whose
     `kind` matches the role per the role-credential matrix.
   - Verify the reviewer holds a non-expired `Credential` covering the
     session's wall-clock time.
   - Verify the reviewer has at least one `coi_disclosures[]` entry.
   - Authenticate the reviewer via the institutional KMS bound to the
     reviewer's `key_id`.
7. In `--mode chair-finalize`:
   - Resolve `--reviewer` to a `Reviewer` in `panel.reviewers[]` whose
     `role == "panel-chair"`, `identity_proof.ial == "IAL3"`,
     `aal == "AAL3"`.
   - Authenticate via the KMS as in `sign` mode.
8. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Reviewer-pending queue construction (mode `sign`)

For the authenticated reviewer:

1. Determine the reviewer's eligible Libraries under the Gate 2
   composition matrix (`gate2-register.yaml` §1):

   | Library | Required reviewer roles (independent, non-overlapping) |
   |---|---|
   | `HBPStaging`, `TreatmentThreshold` | `hypertension-specialist` + `clinical-informaticist` |
   | `PreventRisk` | `hypertension-specialist` + `clinical-informaticist` |
   | `FirstLineSelection` | `hypertension-specialist` + `clinical-pharmacologist` |
   | `SpecialPopulationModifiers` | `hypertension-specialist` + `clinical-pharmacologist` |
   | `PregnancyHTN` | `mfm-or-obstetric-medicine` + `clinical-pharmacologist` |
   | `ResistantHTN` | `hypertension-specialist` + `clinical-pharmacologist` |
   | `SecondaryHTNTriggers` | `hypertension-specialist` + `(nephrology OR endocrinology)` |
   | `HypertensiveUrgencyEmergency` | `hypertension-specialist` + `(emergency-medicine OR critical-care)` |

   The clinical informaticist additionally co-signs **every** Library on
   the informatics axis (cohort-level attestation), captured as a
   distinct cohort-axis signoff in §6.3 — not a per-Library signoff
   except where the matrix above already names them as a per-Library
   reviewer.

2. The reviewer is **eligible** for a Library iff the reviewer's `role`
   appears in the Library's required-roles set AND no auto-disqualifying
   COI applies AND the Library passed all hard preconditions
   (typecheck-clean, coverage ≥ 95%).

3. Exclude Libraries the reviewer has already signed; exclude
   Libraries currently in `panel-escalated` state (handled in
   `chair-finalize` mode).

4. Order the remaining Libraries by `library_id` ascending for
   deterministic resumption.

5. The skill rejects any explicit `--library` whose `library_id` is not
   in the reviewer's eligible queue.

### 3. Data-only review surface (Library-scoped)

For each Library presented to the reviewer in `--mode sign`, the skill
renders the following panes side-by-side, **without** requiring scrolling
above the fold (the rendering medium is the platform's reviewer UI; the
skill is the data contract for that UI):

#### 3.1 Library identity pane
- `library_id`, `library_name`, `library_version`, the Library's
  `library_content_hash`, and the bound run id.
- The pinned CQL runtime version and the Library's expected
  `using FHIR version 'X.Y.Z'` declaration (verified to match the
  manifest's IG version).
- The pinned terminology editions referenced by the Library's
  `valueset[]` declarations, displayed as a checked list against the
  manifest's `terminology[]`.

#### 3.2 Source-of-truth bindings pane
- The list of `RecommendationRecord` ids consumed by this Library, with
  hyperlinks (within the reviewer UI) to each record's Gate-1-finalized
  view (read-only).
- The list of `AtomicUnit` ids consumed; per-unit kind chips.
- The list of `ValueSet` and `CodeSystem` ids referenced; per-set
  edition pin.
- A **provenance ribbon** showing the per-input content hashes; any
  drift between the Library snapshot and the recorded inputs renders red
  and disables `--mode sign` until the orchestrator regenerates.

#### 3.3 CQL source pane
- Read-only render of the Library's CQL source (or sources, where the
  Library is split across files), with syntax highlighting, line
  numbers, and the per-statement annotations linking each
  `define`/`function`/`expression` to the source-anchored
  RecommendationRecord ids that justify it.
- A persistent banner: **"CQL source is read-only at Gate 2. Edit
  requests are reclassified as reject-rework and the Library is
  re-authored upstream by emit-cql-htn."**

#### 3.4 Typecheck pane
- The full typecheck report from the pinned CQL runtime: zero errors,
  zero warnings (or warnings explicitly tolerated by the manifest's
  policy).
- Any non-zero count BLOCKS sign-mode and routes the Library back to
  P20 via `reject-rework`.

#### 3.5 Synthea coverage pane
- Per-branch coverage table: branch name, hit count, status (covered /
  uncovered).
- Aggregate coverage % at the Library level.
- A persistent banner: **"Coverage ≥ 95% is a precondition for sign.
  Below threshold blocks the Library; no override exists."**
- The Synthea cohort run-id, seed, and version, all pinned in the
  active manifest. Drift renders red.

#### 3.6 Reference test pane
- The reference-test pack outputs as a green/red list. Each test maps
  to one or more atomic units in the bound RecommendationRecord set.
- For Libraries that emit hard-block decisions (notably
  `PregnancyHTN`), the reference tests **must** include a positive case
  asserting that ACE/ARB/MRA/direct-renin selection in pregnancy
  returns a hard refusal (not a soft warning). The skill highlights this
  test by default.

#### 3.7 Hard-block invariants pane
- A read-only matrix of the Library's hard-block invariants (as
  declared in `gate2-register.yaml` §2 below). For `PregnancyHTN`:
  - "RAAS / MRA / direct-renin denylist in pregnancy is an `order-select`
    hard refusal."
  - "Methyldopa, labetalol, and nifedipine-ER are first-line."
  - "ACEi, ARB, MRA, and direct renin inhibitor are denylisted."
- A persistent banner: **"Hard-block invariants are read-only at Gate 2.
  Proposals to relax a hard-block, weaken a denylist, or convert an
  order-select hard refusal to a soft warning are auto-routed to
  reject-rework regardless of clinical rationale."**
- Each invariant has a "verified-by" link to the reference test that
  asserts it. Missing verification renders red and BLOCKS sign-mode.

#### 3.8 CDS Hooks wiring preview
- The downstream service(s) this Library will be wired into at P22, with
  hook type, intended-use age gate (≥ 18), and a preview of the
  suggestion semantics.
- The `htn-pregnancy-denylist` preview shows the `order-select` hook with
  a hard refusal posture. Soft-warning posture renders red and disables
  signing.

#### 3.9 Decision pane
- Closed-set chooser: `accept`, `accept-with-comment`, `reject-rework`,
  `escalate-panel`, `recused`.
- Required free-text rationale (non-empty; `minLength: 1`).
- For `accept-with-comment`: a free-text comment field. Comments are
  audit-only and **do not modify the Library**; they are persisted on
  the signoff for downstream audit.
- A COI re-attestation: the reviewer confirms `no_undisclosed_coi == true`
  and selects any applicable `COIKind` flags for this Library. Selecting
  an auto-disqualifying COI (e.g., financial-pharmaceutical for a
  drug-bearing Library) rewrites the decision to `recused` and prevents
  the signature.
- A "no-edits" affirmation: the reviewer attests that no proposed change
  affects a Library hard-block invariant. The decision pane offers a
  closed-set "concern category" chooser the reviewer may use to surface
  observed issues without editing:
  - `boundary-too-permissive`
  - `boundary-too-restrictive`
  - `mapping-incorrect`
  - `denylist-incomplete`
  - `coverage-gap`
  - `documentation-only`
  - `other`
  Any concern category other than `documentation-only` automatically
  proposes `reject-rework` as the decision (the reviewer can confirm or
  override to `escalate-panel`); a reviewer cannot record a substantive
  concern and `accept` simultaneously.

### 4. Sign cycle (mode `sign`)

For each `--library` in turn:

1. Lock the Library entry on the register (`library_id`) for write.
2. Recompute the Library's `library_content_hash` over the snapshot at
   sign time; verify it equals the register entry's
   `library_content_hash`. Mismatch → BLOCK.
3. Recompute the typecheck report and the coverage report against the
   recorded run id; verify identical bytes (or, where the runtime is
   declared `nondeterministic` in `tools_lock`, identical aggregate
   metrics within an `eq-tolerance` recorded on the runtime).
4. Ask the reviewer to confirm decision and rationale; produce a
   `LibrarySignoff` candidate (no signature yet) that conforms to
   `gate2-register.yaml` §3.8.
5. Compose the signing payload as the JCS-canonical form of the
   candidate `LibrarySignoff` with `signature` field stripped.
6. Compute `payload_sha256 = SHA-256(canonical_payload)`.
7. Issue a signature request to the reviewer's institutional KMS bound
   to `Reviewer.public_key.key_id`. Signing keys are never exported to
   the framework process; the KMS returns `signature_b64` and metadata.
8. Request an RFC 3161 time-stamp from a TSA in
   `manifest.tsa_list[]` whose certificate validity covers `signed_at`.
   Persist the `TimeStampToken` and metadata. Reject any TSA whose cert
   fails chain verification.
9. Verify the signature locally before persisting:
   - Construct the canonical payload again.
   - Recompute `payload_sha256`.
   - Verify `signature_b64` against `Reviewer.public_key.key_pem` under
     `signature.algorithm`.
   - Confirm the time-stamp token's hash equals `payload_sha256` and the
     TSA cert chains to a trust anchor pinned in the manifest.
   - Set `signature.verifies = true` only after these checks succeed.
10. Persist the `LibrarySignoff` into
    `register.libraries[*].signoffs[]` for this Library, atomically.
11. Update the Library entry's disposition `state`:
    - 1 of 2 signoffs at `accept` / `accept-with-comment`: state remains
      `pending`, awaiting the second reviewer.
    - 2 of 2 with both `accept` (and at most one `accept-with-comment`):
      state becomes `accepted` or `accepted-with-comment`.
    - Any `reject-rework`: state becomes `rework-required`; emit a
      `rework_history[]` entry; signal the orchestrator to re-author the
      Library at P20 and regenerate coverage at P21. The skill never
      modifies the Library itself.
    - Any `escalate-panel`: state becomes `panel-escalated`; open the
      `escalation` block; the orchestrator pauses P22 packaging for that
      Library.
    - `recused`: state remains `pending`; the reviewer is removed from
      this Library's eligible set; if the matrix can no longer be
      satisfied, signal the panel chair to recompose.
12. Append a `RegisterAuditEvent` of kind `signoff-recorded` to
    `audit_log[]`; recompute `fixity.register_sha256` (RFC 8785 with
    `fixity` excluded); persist.
13. Emit a FHIR `Provenance` resource update at
    `work/<run_id>/fhir/provenance/library-<library_id>.json` appending
    a `Provenance.signature` entry for this signoff.

#### 4.1 No-edits handling

Gate 2 has no `accept-with-edit` mode (unlike Gate 1). Any reviewer
proposal to change Library content — including hard-block invariants,
denylists, value-sets, risk-engine bindings, or boundary thresholds —
MUST be expressed as `reject-rework` with a concern category and
rationale. The orchestrator consumes the rework signal, re-authors the
Library upstream at P20, regenerates coverage at P21, and re-posts the
new Library snapshot to a fresh Gate 2 cohort entry. The reviewer's prior
signoff is invalidated by the new `library_content_hash` and a new
signoff is required.

This is the mechanical realization of the Gate 2 immutability rule
(`G2R-INV-12`): post-signoff Library content is immutable; corrections
require a new Library snapshot with a new content hash.

#### 4.2 Decision-protocol auto-routing rules

The skill applies these mechanical rules without operator override:

- **Hard-block-relax detection (no_relax_of_hard_block):** Any reviewer
  decision whose rationale, comment, or concern category proposes:
  - converting an `order-select` hard refusal to a soft warning,
  - removing a class from a Library's denylist,
  - replacing PREVENT with PCE-legacy,
  - lowering the age gate below 18,
  - adding a "permit on attending override" branch to a denylist,
  is auto-rewritten to `reject-rework` with the rationale prefixed
  "Auto-rewrite per `no_relax_of_hard_block`: Gate 2 cannot relax a hard
  block." The skill detects these proposals via the closed concern
  category set plus a small set of regex heuristics over the rationale
  text; any match auto-routes. False positives are routed to the panel
  chair.
- **COI auto-disqualification.** An attempted decision of `accept` or
  `accept-with-comment` while a COI auto-disqualifies the reviewer is
  rewritten to `recused` with the rationale prefixed "Auto-rewrite per
  `coi_auto_disqualification`."
- **Self-pairing rejection.** An attempted second signature by the same
  `reviewer_id` already present on the Library is rejected outright
  (`G2R-INV-21`).
- **Coverage-below-threshold lockout.** Sign-mode is disabled for any
  Library whose coverage report (recomputed at sign time) is below
  95.0%. This is a UI-level lockout, not an auto-rewrite.
- **Typecheck-error lockout.** Sign-mode is disabled for any Library
  whose recomputed typecheck report shows non-zero errors or
  non-tolerated warnings.
- **Pregnancy-Library order-select lockout.** Sign-mode for
  `PregnancyHTN` is disabled if the wired CDS Hooks service preview
  shows anything other than `order-select` with a hard-refusal posture.

#### 4.3 Reviewer disagreement → panel escalation

When two signoffs are present on a Library and at least one is
`reject-rework` or `escalate-panel` while another is `accept` /
`accept-with-comment`, the skill auto-escalates:

1. Set the Library's disposition `state = "panel-escalated"`.
2. Populate `escalation` with `escalated_to_role: panel-chair`, the
   originating reasons, the disagreeing signoffs, and `resolution: null`.
3. Append `RegisterAuditEvent` of kind `escalation-opened`.
4. Notify the panel chair via the platform's notification surface.

The skill does **not** majority-vote, does not auto-resolve, and does not
permit a third specialty reviewer to break a tie outside the panel-chair
process.

### 5. Panel-chair finalization (mode `chair-finalize`)

In `--mode chair-finalize`, the skill renders a chair surface scoped to
the cohort:

#### 5.1 Composition compliance pane
- A Library-by-Library view of `signoffs[*].role` against the matrix.
- Missing-role flags rendered red; satisfied composition rendered green.
- `PregnancyHTN`-specific banner verifying MFM + clinical pharmacology
  presence (`G2R-INV-23`).
- Domain-matched-pair banner verifying the disjunctive matrix entries
  for `SecondaryHTNTriggers` and `HypertensiveUrgencyEmergency`.

#### 5.2 Hard-block invariants pane (cohort-level)
- An aggregated view of every Library's hard-block invariants and which
  reference tests verify them.
- A red banner if any Library's hard-block invariants are unverified or
  if any reference test is missing.
- A persistent reminder: **"Cohort finalization cannot proceed if any
  Library's hard-block invariants are unverified."**

#### 5.3 Coverage compliance pane
- A Library-by-Library view of branch coverage against the 95% floor.
- A red banner if any Library is below the floor; the chair cannot
  finalize the cohort with any Library below floor.

#### 5.4 Escalations pane
- Every Library in `panel-escalated` state.
- For each, the escalation reason and the disagreeing signoffs.
- The chair's options per Library: `accept`, `accept-with-comment`,
  `reject-rework`. The chair's decision is recorded as a
  `resolution.resolver_signoff` on the escalation block.
- The chair's decision is itself a `LibrarySignoff` with role
  `panel-chair`; identical signing flow as §4 but tagged as a resolver.

#### 5.5 Cohort-axis informatics signoff
- A separate cohort-axis attestation by the clinical informaticist
  covering: provenance integrity across all Libraries, terminology pin
  consistency across all Libraries, FHIR-IG version alignment, and
  CDS-Hooks service-Library wiring readiness.
- Captured as a `CohortAxisSignoff` (one per cohort) on the register.

#### 5.6 Cohort-finalization pane
- A scrolling list of every Library's terminal state.
- Three attestation toggles, all required:
  - `composition_compliance_attested`
  - `coverage_floor_satisfied`
  - `hard_block_invariants_verified`
- Plus `escalations_disposed` (auto-true when no Library is in
  `panel-escalated` state).
- A COI re-attestation for the chair (cohort-scope).
- A "Sign cohort" action that produces the `PanelChairSignoff` covering
  `cohort_manifest_hash` (the SHA-256 over JCS-canonical
  `libraries[]` ordered by `library_id` ascending; the skill recomputes
  and rejects mismatch).

#### 5.7 Cohort-signoff cycle

1. Lock the register for write.
2. Recompute `cohort_manifest_hash`; reject if not deterministic.
3. Build the chair's signing payload (`PanelChairSignoff` candidate with
   `signature` stripped); compute `payload_sha256`.
4. Issue signature request to the chair's KMS key (Ed25519 or
   ECDSA-P256-SHA256, AAL3).
5. Time-stamp via a manifest TSA whose cert covers `signed_at`.
6. Locally verify the signature and time-stamp; set `verifies: true`.
7. Persist `panel.panel_chair_signoff`; transition `cohort.state` to
   `finalized`; set `cohort.finalized_at`.
8. Append `audit_log[]` events `panel-chair-signed` and
   `cohort-finalized`; recompute `fixity.register_sha256`; persist.
9. Signal the orchestrator that the cohort is ready to advance to P22
   (CDS Hooks packaging).

### 6. Determinism and reproducibility

- The reviewer-pending queue is deterministic given the register and the
  reviewer id; resume is safe across orchestrator restarts.
- Re-running this skill on a finalized register is a no-op (the skill
  refuses to mutate a finalized register; corrections require a new
  register version).
- Re-running on an in-review register at the same `register_sha256`
  produces identical eligible-queue ordering and identical disposition
  state (modulo new signatures introduced by the resumed session).
- Signature payload canonicalization is RFC 8785 (JCS); identical
  canonical bytes produce identical `payload_sha256` across runs.
- Coverage and typecheck reports are recomputed at sign time and
  compared byte-for-byte (or aggregate-metric-equal under tolerance) to
  the recorded reports; drift triggers a hard re-run upstream.
- Time-stamps are authoritative for ordering; the audit log is appended
  in `occurred_at` order and chained by `payload_sha256` per
  `G2R-INV-18`.

## DQA Gates Enforced By This Skill

| Gate | Condition for advance |
|---|---|
| **GR2-A** Register integrity | Register validates against `schemas/gate2-register.yaml` invariants `G2R-INV-01` … `G2R-INV-30` at every write. |
| **GR2-B** Composition matrix | Every Library advanced to `accepted` / `accepted-with-comment` carries two signoffs from a matrix-correct, distinct, non-overlapping reviewer pair. |
| **GR2-C** Signature integrity | Every persisted `Signature.verifies == true`, recomputed locally; producer claims ignored. |
| **GR2-D** No-edits / no-relax | Zero `LibrarySignoff` carries any modification of Library content; auto-routing of hard-block-relax proposals to `reject-rework` observed. |
| **GR2-E** No self-pairing | No two signoffs on the same Library share `reviewer_id`. |
| **GR2-F** COI auto-disqualification | Every recused entry carries the COI kind; substitute reviewer assigned where required. |
| **GR2-G** Coverage floor | Every advanced Library carries a coverage report with branch coverage ≥ 95.0%, recomputed at sign time. |
| **GR2-H** Typecheck clean | Every advanced Library carries a typecheck report with zero errors and no warnings promoted to errors. |
| **GR2-I** Hard-block verification | Every advanced Library has every hard-block invariant verified by a reference test; no unverified hard-blocks. |
| **GR2-J** Pregnancy order-select | `PregnancyHTN` carries a CDS Hooks wiring preview asserting `order-select` with hard refusal; soft-warning posture is rejected. |
| **GR2-K** Risk-engine canonical | Any Library binding a risk engine binds PREVENT (`legacy_only == false`); no PCE-legacy binding feeds the Library. |
| **GR2-L** Provenance integrity | The Library snapshot's recorded RecommendationRecord, AtomicUnit, ValueSet, CodeSystem content hashes match the live artifacts at sign time; drift BLOCKS. |
| **GR2-M** Append-only audit log | `audit_log[]` ordered by `occurred_at`; chained `payload_sha256` continuity verified at every write. |
| **GR2-N** Cohort finalization preconditions | `composition_compliance_attested == true` AND `coverage_floor_satisfied == true` AND `hard_block_invariants_verified == true` AND `escalations_disposed == true` AND `errata_watch.blockers_open == []` on the active manifest at finalization time. |

Failure of any gate at any write step → BLOCK; the skill rolls back the
in-flight write, surfaces the specific gate, and emits a
`flagged_items`-style diagnostic into the build's reconciliation queue.

## Outputs

- Updated Gate 2 register at `<register-path>` with new `LibrarySignoff`
  entries, updated Library disposition states, updated escalations and
  rework history, and (in `chair-finalize` mode) the
  `PanelChairSignoff` and the cohort-axis informatics signoff.
- Per-session report at
  `work/<run_id>/reports/gate2-<cohort>-<reviewer>-<session>.md`
  summarizing reviewer identity, eligibility queue, Libraries reviewed,
  decisions, and signature verification outcomes.
- Updated PROV bundle entries at
  `provenance/gate2-<cohort>-<reviewer>-<session>.jsonld`.
- Per-Library FHIR `Provenance` resource updates at
  `work/<run_id>/fhir/provenance/library-<library_id>.json`, appending
  `Provenance.signature` entries for each new signoff.
- Notifications to the orchestrator queue:
  `cohort-ready-for-cds-packaging` on cohort finalization, or
  `library-rework-required` / `library-panel-escalated` per disposition.

## Error Handling

- **Cohort not active or finalized.** Refuse to open in `sign` or
  `chair-finalize` mode; allow `browse` only.
- **Manifest stale.** Refuse all modes; instruct operator to re-run
  `flow-hbp-2025-build` preflight.
- **Reviewer not in panel.** Refuse `sign` mode; instruct operator to
  add the reviewer to the panel via the panel-management skill (a
  separate, out-of-scope skill).
- **Reviewer credential expired.** Refuse `sign` mode; route to
  credential renewal.
- **KMS authentication failure.** Refuse signing; do not retry silently;
  emit a `kms-auth-failure` event.
- **TSA unavailable.** Hold the in-flight signature; the candidate
  `LibrarySignoff` is persisted with `signature: null` and state
  `awaiting-time-stamp`; the skill polls the next TSA in `tsa_list`.
  After exhausting the list, BLOCK.
- **Signature local verification failure.** Discard the candidate; emit
  `signature-verification-failed` event; investigate KMS or
  canonicalization drift; never accept.
- **Library content hash mismatch at sign time.** Indicates upstream
  re-author without re-posting to Gate 2; BLOCK; signal the orchestrator
  to repost a fresh cohort entry.
- **Coverage report mismatch at sign time.** BLOCK; signal the
  orchestrator to re-run `cql-test-synthea-htn`.
- **Typecheck report mismatch at sign time.** BLOCK; signal the
  orchestrator to re-run `emit-cql-htn` typecheck.
- **Provenance drift on RecommendationRecord, AtomicUnit, or ValueSet
  inputs.** BLOCK; signal the orchestrator to re-bind upstream.
- **Hard-block invariant unverified by any reference test.** BLOCK;
  signal the orchestrator to re-author the reference-test pack.
- **Lock contention.** Wait up to a configured timeout; fail-closed if
  not acquired; concurrent signing on the same Library is not
  permitted.
- **Resume after register hash change.** Reject; require a fresh session.
- **Reviewer attempts to edit Library content via direct API.** Reject;
  emit a `gate2-edit-attempt` audit event; investigate as adversarial
  input.

## Examples

```bash
# Browse a cohort read-only
cql-clinician-signoff work/run-2026-04-30/gate2/cohort-9bf7e1a2c3d4e5f6.signed.jsonld \
  --mode browse

# Specialist signing session — auto-pick the next eligible Library
cql-clinician-signoff work/run-2026-04-30/gate2/cohort-9bf7e1a2c3d4e5f6.signed.jsonld \
  --mode sign \
  --reviewer rev-1a2b3c4d5e6f7081

# Pharmacology signing session for PregnancyHTN specifically
cql-clinician-signoff work/run-2026-04-30/gate2/cohort-9bf7e1a2c3d4e5f6.signed.jsonld \
  --mode sign \
  --reviewer rev-2b3c4d5e6f708192 \
  --library lib-hbp-pregnancy

# Resume after orchestrator re-authored a Library and reposted it
cql-clinician-signoff work/run-2026-04-30/gate2/cohort-9bf7e1a2c3d4e5f6.signed.jsonld \
  --mode sign \
  --reviewer rev-1a2b3c4d5e6f7081 \
  --resume

# Panel-chair finalization session
cql-clinician-signoff work/run-2026-04-30/gate2/cohort-9bf7e1a2c3d4e5f6.signed.jsonld \
  --mode chair-finalize \
  --reviewer rev-c0a1b2c3d4e5f607