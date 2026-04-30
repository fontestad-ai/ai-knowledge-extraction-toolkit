---
name: gate1-sme-review
description: Reviewer-interface skill for Gate 1 SME extraction review. Renders the data-only review surface specified in extract-recommendation-cor-loe §10.2, captures two independent reviewer decisions per record under the composition matrix, produces cryptographically-signed ReviewerSignoff entries against schemas/gate1-register.yaml, escalates disagreements to the panel chair, and finalizes the cohort under panel-chair signoff. No batch acceptance. No COR/LOE edits. No reviewer self-pairing. Post-signoff content is immutable.
namespace: cpg-htn-2025-acc-aha
category: gate
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<register-path> [--cohort <id>] [--reviewer <id>] [--record <id>] [--mode <browse|sign|chair-finalize>] [--resume]"
---

# gate1-sme-review

Reviewer-interface skill for **Gate 1** of the `cpg-htn-2025-acc-aha`
framework. The skill is the only authorized producer of `ReviewerSignoff`
entries on the Gate 1 cohort register defined in
`schemas/gate1-register.yaml`. It renders the data-only review surface
specified in `extract-recommendation-cor-loe` §10.2, captures two
independent reviewer decisions per record under the composition matrix in
`gate1-register.yaml` §1, escalates disagreements to the panel chair, and
finalizes the cohort under panel-chair signoff.

This skill does **not** generate clinical content, summarize recommendations,
re-grade COR/LOE, or perform extraction. It is a *signature surface* over
content already produced and gated by the deterministic, triple-modal
pipeline. Every reviewer's signature binds a named individual with credential
evidence to the SHA-256 of a specific record at a specific time, time-stamped
by an RFC 3161 TSA pinned in the active manifest.

Posture: **caution over velocity, fidelity over coverage, verbatim over
paraphrase.** Two-person rule, no batch acceptance, no COR/LOE edits, no
self-pairing, no override on auto-disqualifying COI, no soft-warning relaxation
of pregnancy hard-blocks. Post-signoff content is immutable; corrections
require a new register version with explicit predecessor chain.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P9 → ◆ Gate 1**
  and posts a Gate 1 cohort register at `work/<run_id>/gate1/<cohort>.jsonld`.
- A specific reviewer is scheduled for an interactive review session against
  records assigned to them in that cohort.
- A panel chair is scheduled to dispose of escalated records and finalize a
  cohort for advance.
- A previously held cohort needs to be resumed after a queue resolution or a
  reviewer-driven `accept-with-edit` regenerated downstream artifacts.

Do **not** invoke this skill if:

- The cohort register's `state` is `finalized`, `superseded`, or `withdrawn`.
- The active manifest's `medical_director_signoff` is missing or fails
  verification.
- Any record bound to the cohort has a `provenance.consensus.state` other
  than `gate-1-pending` (e.g., still `escalated-pending` upstream).
- The orchestrator has not posted the cohort to this skill's queue yet
  (the skill refuses to cold-start a cohort).

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `register-path` | yes | — | Path to a Gate 1 register at `work/<run_id>/gate1/<cohort>.jsonld`, validated against `schemas/gate1-register.yaml`. The skill writes back atomically. |
| `--cohort <id>` | no | derived from `register-path` | Cohort id; defaults to the cohort recorded in the register. The skill rejects mismatch. |
| `--reviewer <id>` | no | — | The reviewer id (`rev-<16hex>`) for the current session. Required in `--mode sign`. The skill refuses to act on behalf of any other reviewer in the same session. |
| `--record <id>` | no | `next` | The specific record id (`rec-<16hex>`) to review next. Defaults to the next record in the reviewer's pending queue (deterministic ordering by `record_id` ascending, skipping records the reviewer cannot sign per composition / COI rules). |
| `--mode <browse\|sign\|chair-finalize>` | no | `browse` | `browse` renders the review surface read-only. `sign` opens an authenticated signing session (requires `--reviewer`). `chair-finalize` opens the panel-chair finalization surface (requires the reviewer's role == `panel-chair`). |
| `--resume` | no | `false` | Resume an interrupted session from the last persisted decision. The skill rejects resume if the register's `fixity.register_sha256` has changed since session start. |
| `--strict` | no | `true` | Fail-closed on every invariant. Setting `--strict false` is **never permitted** in production; the flag exists only for fixture and golden-set development. |

## Operation

### 1. Preflight

1. Validate `register-path` against `schemas/gate1-register.yaml`. Reject on
   any invariant failure (`G1-INV-01` … `G1-INV-25`).
2. Re-resolve `guideline_manifest_ref`; verify the active manifest's
   `medical_director_signoff` cryptographically (`GM-INV-21`); verify
   `state == "active"` and `errata_watch.blockers_open == []`.
3. Verify the register's `cohort.run_id` matches the run id recorded in the
   build's PROV bundle.
4. For every record bound to the cohort, load the corresponding
   `RecommendationRecordHTN` from `work/<run_id>/records.json`; verify each
   record's content hash recomputes to the value in `record_content_hash`
   on the register entry. Mismatch → BLOCK (post-signoff mutation detected
   on a prior step).
5. Verify `tsa_list[]` in the manifest has at least one TSA whose
   `cert_valid_until` covers the wall-clock window. Otherwise BLOCK.
6. In `--mode sign`:
   - Resolve `--reviewer` to a `Reviewer` in `panel.reviewers[]`.
   - Verify the reviewer's `identity_proof.ial` ≥ `IAL2`,
     `identity_proof.aal` ≥ `AAL2`, and at least one `Credential` whose
     `kind` matches the role per the role-credential matrix.
   - Verify the reviewer holds a non-expired `Credential` covering the
     session's wall-clock time.
   - Verify the reviewer has at least one `coi_disclosures[]` entry
     (kind `none` or otherwise).
   - Authenticate the reviewer interactively via the institutional KMS
     (the skill does not store credentials; it requests a per-session
     attestation token bound to the reviewer's `key_id`).
7. In `--mode chair-finalize`:
   - Resolve `--reviewer` to a `Reviewer` in `panel.reviewers[]` whose
     `role == "panel-chair"`, `identity_proof.ial == "IAL3"`,
     `aal == "AAL3"`.
   - Authenticate via the KMS as in `sign` mode.
8. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Reviewer-pending queue construction (mode `sign`)

For the authenticated reviewer:

1. Determine the reviewer's eligible records under the composition matrix
   (`gate1-register.yaml` §1):
   - Resolve each record's domain from `RecommendationRecordHTN.section_path`
     and `pico_precheck.populations`.
   - For each record, look up the required-roles set for that domain.
   - The reviewer is **eligible** for a record iff the reviewer's `role`
     appears in the required-roles set AND no auto-disqualifying COI
     applies (`G1-INV-14`).
2. Exclude records the reviewer has already signed (no double-signing per
   `G1-INV-21`).
3. Exclude records currently in `panel-escalated` state unless the reviewer
   is the panel chair (which is handled by `chair-finalize` mode, not
   `sign` mode).
4. Order the remaining records by `record_id` ascending for deterministic
   session resumption.
5. The skill rejects any explicit `--record` whose `record_id` is not in the
   reviewer's eligible queue.

### 3. Data-only review surface (encodes `extract-recommendation-cor-loe` §10.2)

For each record presented to the reviewer in `--mode sign`, the skill
renders the following panes side-by-side, **without** scrolling above the
fold (the rendering medium is the platform's reviewer UI; the skill is the
data contract for that UI):

#### 3.1 Source pane
- The record's anchored region of the source PDF, rasterized at 600 DPI
  using `RecommendationRecordHTN.anchors.bbox` and `anchors.page`.
- The cell bboxes for COR / LOE / Recommendation overlaid as
  non-destructive outlines (color-coded; legend below the pane).
- The full source page index for context navigation; never editable.

#### 3.2 Verbatim text pane
- `RecommendationRecordHTN.text_verbatim` rendered byte-faithfully.
- Hover (or equivalent) reveals the `normalization_log[]` per character
  position (e.g., "soft-hyphen-removed at offset 47", "ligature-decomposed
  fi → fi at offset 92").
- Footnote markers within the text are clickable; each click opens the
  resolved footnote text from SAIR's `footnotes_index` (the skill never
  mutates).

#### 3.3 Grading pane
- `acc_aha_cor` and `acc_aha_loe` displayed verbatim.
- The cell crops alongside the canonical values, so the reviewer can
  visually confirm the OCR / VLM / deterministic extractor agreement.
- The cell's reconciliation history (the per-engine variants) shown on
  request (default collapsed).
- A persistent banner: **"COR and LOE are read-only at Gate 1. Edit requests
  are reclassified as reject-rework."**

#### 3.4 Atomic-units pane
- Each `atomic_units[*].span` highlighted as a colored span within the
  verbatim text pane (cross-pane synchronization).
- Per-unit kind chip (atomic-recommendation, qualifier, exclusion,
  monitoring, citation).
- Per-unit Jaccard agreement displayed.
- The atomicity state: `agreed` / `held` / `conflict`. If `held` or
  `conflict`, the proposal-diff view is shown by default.
- A persistent acknowledgement checkbox: **"I acknowledge the atomicity
  state for this record."** This sets
  `ReviewerSignoff.atomicity_state_acknowledged` (`agreed` or `held`); the
  reviewer cannot sign without acknowledging.

#### 3.5 PICO precheck pane
- `pico_precheck.populations[]`, `population_present`, `intervention_present`,
  `comparator_kind`, `outcome_kind`.
- The mapped HTN-typed Population enum values are shown; if any is
  `secondary-htn-suspected`, `urgency`, or `emergency`, a banner indicates
  the corresponding Library and CDS Hooks service downstream.

#### 3.6 Triple-modal consensus pane
- `provenance.consensus.state` and `provenance.consensus.similarity_min_pairwise`.
- A side-by-side diff of extractor A, V, and O outputs when any pairwise
  similarity is below 1.0 (still passing the 0.99 floor); shown on request.
- The pane refuses to render if the consensus state is anything other than
  `gate-1-pending` (any record displayed for sign-mode review must be in
  that state).

#### 3.7 Predecessor 2017 pane
- `predecessor_2017.relation` and the linked predecessor record id (if any).
- A read-only side-by-side of the 2017 source-anchored region (when
  available), to support the reviewer's relation acknowledgement.
- The skill banner: **"Predecessor mapping is advisory. Acknowledge or
  request panel review; do not edit."**

#### 3.8 Decision pane
- Closed-set chooser: `accept`, `accept-with-edit`, `reject-rework`,
  `escalate-panel`, `recused`.
- Required free-text rationale (non-empty; `minLength: 1`).
- For `accept-with-edit`: an edit form with the closed `EditTarget` enum
  (`text_verbatim_typo`, `supportive_text`, `monitoring_text`,
  `citation_link`). The form **does not list** `acc_aha_cor` or
  `acc_aha_loe`; submitting an attempt to edit either via direct API
  invocation is rejected (`G1-INV-12`).
- A COI re-attestation: the reviewer confirms `no_undisclosed_coi == true`
  and selects any applicable `COIKind` flags for this record. Selecting an
  auto-disqualifying COI rewrites the decision to `recused` and prevents
  the signature.

### 4. Sign cycle (mode `sign`)

For each `--record` in turn:

1. Lock the record entry on the register (`record_id`) for write.
2. Recompute the `RecommendationRecord` content hash with
   `provenance.reviewer_signoffs` stripped at the time of signing; verify
   it equals the register entry's `record_content_hash`. Mismatch → BLOCK.
3. Ask the reviewer to confirm decision and rationale; produce a
   `ReviewerSignoff` candidate (no signature yet) that conforms to
   `gate1-register.yaml` §3.8.
4. Compose the signing payload as the JCS-canonical form of the candidate
   `ReviewerSignoff` with `signature` field stripped.
5. Compute `payload_sha256 = SHA-256(canonical_payload)`.
6. Issue a signature request to the reviewer's institutional KMS bound to
   `Reviewer.public_key.key_id`. The signing keys are never exported to
   the framework process; the KMS returns `signature_b64` and metadata.
7. Request an RFC 3161 time-stamp from a TSA in `manifest.tsa_list[]`
   whose certificate validity covers `signed_at`. Persist the
   `TimeStampToken` and metadata. Reject any TSA whose certificate fails
   chain verification.
8. Verify the signature locally before persisting:
   - Construct the canonical payload again.
   - Recompute `payload_sha256`.
   - Verify `signature_b64` against `Reviewer.public_key.key_pem` under
     `signature.algorithm`.
   - Confirm the time-stamp token's hash equals `payload_sha256` and the
     TSA cert chains to a trust anchor pinned in the manifest.
   - Set `signature.verifies = true` only after these checks succeed.
9. Persist the `ReviewerSignoff` into
   `register.records[*].signoffs[]` for this record, atomically.
10. Update the record entry's disposition `state`:
    - 1 of 2 signoffs at `accept` / `accept-with-edit`: state remains
      `pending`, awaiting the second reviewer.
    - 2 of 2 with both `accept` (and at most one `accept-with-edit`):
      state becomes `accepted` or `accepted-with-edit`.
    - Any `reject-rework`: state becomes `rework-required`; emit a
      `rework_history[]` entry; remove signoffs at the panel-chair's option
      only; signal the orchestrator to regenerate downstream artifacts.
    - Any `escalate-panel`: state becomes `panel-escalated`; open the
      `escalation` block; the orchestrator pauses downstream phases for the
      record.
    - `recused`: state remains `pending`; remove the reviewer from this
      record's eligible set; signal the panel chair to recompose if the
      remaining eligible set cannot satisfy the matrix.
11. Append a `RegisterAuditEvent` of kind `signoff-recorded` to
    `audit_log[]`; recompute `fixity.register_sha256` (RFC 8785 with
    `fixity` excluded); persist.
12. Emit a `Provenance` entity update referencing the signoff for the
    build's PROV bundle.

#### 4.1 Edit handling (`accept-with-edit`)

If the reviewer's decision is `accept-with-edit`:

1. The proposed edits are validated against the closed `EditTarget` enum
   (no `acc_aha_cor`, no `acc_aha_loe`).
2. The skill applies the edits to a working copy of the
   `RecommendationRecord` (never the original; produces a new record content
   hash).
3. **Critical rule:** if the edit targets `text_verbatim_typo`, all child
   `AtomicUnit` instances on the record MUST be deleted and regenerated by
   the orchestrator (`AU-INV-24`). The skill does not perform regeneration;
   it signals the orchestrator and persists the record in
   `pending-regeneration` state until atomic units are restored.
4. The reviewer's signature covers the *new* content hash; the *old* hash is
   retained immutably for audit.
5. The second reviewer's signoff (if already present) is invalidated by
   the content hash change and MUST be re-collected against the new hash.
   The skill emits a `ReviewerSignoff.recused` placeholder for the prior
   signature with rationale "content hash changed under accept-with-edit"
   and re-queues the second reviewer.

This protocol is identical to `gate1-register.yaml`'s
`post_signoff_immutability` rule (`G1-INV-09`).

#### 4.2 Decision-protocol auto-routing rules

The skill applies these mechanical rules without operator override:

- An attempted edit targeting `acc_aha_cor` or `acc_aha_loe` is rewritten
  to `reject-rework` with the rationale prefixed
  "Auto-rewrite per G1-INV-12: COR/LOE edits are forbidden at Gate 1."
- An attempted decision of `accept` or `accept-with-edit` while a COI
  auto-disqualifies the reviewer is rewritten to `recused` with the
  rationale prefixed "Auto-rewrite per G1-INV-14: COI auto-disqualification."
- An attempted second signature by the same `reviewer_id` already present
  on the record is rejected outright (`G1-INV-21`).
- An attempted `accept-with-edit` whose edits fail `Edit` schema
  validation is rejected without auto-rewrite; the reviewer is asked to
  correct the edit form.
- An attempted decision while the cohort's `state` is `awaiting-panel-chair`
  or `finalized` is rejected.

### 5. Reviewer disagreement → panel escalation

When two signoffs are present on a record and at least one is
`reject-rework` or `escalate-panel` while another is `accept` /
`accept-with-edit`, the skill auto-escalates per
`extract-recommendation-cor-loe` §10.3:

1. Set the record's disposition `state = "panel-escalated"`.
2. Populate `escalation` with `escalated_to_role: panel-chair`, the
   originating reasons, and `resolution: null`.
3. Append `RegisterAuditEvent` of kind `escalation-opened`.
4. Notify the panel chair via the platform's reviewer notification surface
   (the skill emits the notification record; delivery is platform).

The skill does **not** majority-vote, does not auto-resolve, and does not
permit a third specialty reviewer to break a tie outside the panel-chair
process.

### 6. Panel-chair finalization (mode `chair-finalize`)

In `--mode chair-finalize`, the skill renders a chair surface scoped to the
cohort:

#### 6.1 Composition compliance pane
- A record-by-record view of `signoffs[*].role` against the composition
  matrix.
- Missing-role flags rendered red; satisfied composition rendered green.
- Pregnancy records have a banner verifying MFM + clinical pharmacology
  presence (`G1-INV-23`).

#### 6.2 Escalations pane
- Every record in `panel-escalated` state.
- For each, the escalation reason and the disagreeing signoffs.
- The chair's options per record: `accept`, `accept-with-edit`,
  `reject-rework`. The chair's decision is recorded as a
  `resolution.resolver_signoff` on the escalation block.
- The chair's decision is itself a `ReviewerSignoff` with role
  `panel-chair`; identical signing flow as §4 but tagged as a resolver.

#### 6.3 Cohort-finalization pane
- A scrolling list of every record's terminal state.
- Two attestation toggles, both required:
  - `composition_compliance_attested`
  - `escalations_disposed`
- A COI re-attestation for the chair (cohort-scope).
- A "Sign cohort" action that produces the `PanelChairSignoff` covering
  `cohort_manifest_hash` (the SHA-256 over JCS-canonical
  `records[]` ordered by `record_id` ascending; the skill recomputes and
  rejects mismatch).

#### 6.4 Cohort-signoff cycle

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
8. Append `audit_log[]` events `panel-chair-signed` and `cohort-finalized`;
   recompute `fixity.register_sha256`; persist.
9. Signal the orchestrator that the cohort is ready to advance (P10–P17).

### 7. Determinism and reproducibility

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
- Time-stamps are authoritative for ordering; the audit log is appended in
  `occurred_at` order and chained by `payload_sha256` per
  `G1-INV-18`.

## DQA Gates Enforced By This Skill

| Gate | Condition for advance |
|---|---|
| **GR1-A** Register integrity | Register validates against `schemas/gate1-register.yaml` invariants `G1-INV-01` … `G1-INV-25` at every write. |
| **GR1-B** Composition matrix | Every record advanced to `accepted` / `accepted-with-edit` carries two signoffs from a domain-correct, distinct, non-overlapping reviewer pair. |
| **GR1-C** Signature integrity | Every persisted `Signature.verifies == true`, recomputed locally; producer claims ignored. |
| **GR1-D** No-COR/LOE-edits | Zero `Edit.target ∈ {acc_aha_cor, acc_aha_loe}` recorded. Auto-rewrite rule observed. |
| **GR1-E** No self-pairing | No two signoffs on the same record share `reviewer_id`. |
| **GR1-F** COI auto-disqualification | Every recused entry carries the COI kind; substitute reviewer assigned where required. |
| **GR1-G** Atomicity acknowledgement | Every signoff carries `atomicity_state_acknowledged` matching the record's atomicity state at signing time. |
| **GR1-H** Panel-chair cohort hash | `panel_chair_signoff.cohort_manifest_hash` recomputes deterministically over `records[]`. |
| **GR1-I** Append-only audit log | `audit_log[]` ordered by `occurred_at`; chained `payload_sha256` continuity verified at every write. |
| **GR1-J** Cohort finalization preconditions | `composition_compliance_attested == true` AND `escalations_disposed == true` AND `errata_watch.blockers_open == []` on the active manifest at finalization time. |

Failure of any gate at any write step → BLOCK; the skill rolls back the
in-flight write, surfaces the specific gate, and emits a
`flagged_items`-style diagnostic into the build's reconciliation queue.

## Outputs

- Updated Gate 1 register at `<register-path>` with new `ReviewerSignoff`
  entries, updated record disposition states, updated escalations and
  rework history, and (in `chair-finalize` mode) the `PanelChairSignoff`.
- Per-session report at
  `work/<run_id>/reports/gate1-<cohort>-<reviewer>-<session>.md` summarizing:
  reviewer identity, eligibility queue, records reviewed, decisions, and
  signature verification outcomes.
- Updated PROV bundle entries at
  `provenance/gate1-<cohort>-<reviewer>-<session>.jsonld`.
- Per-record FHIR `Provenance` resource updates at
  `work/<run_id>/fhir/provenance/<recommendation_id>.json`, appending
  `Provenance.signature` entries for each new signoff.
- Notifications to the orchestrator queue:
  `cohort-ready-for-downstream` on cohort finalization, or
  `record-rework-required` / `record-panel-escalated` per disposition.

## Error Handling

- **Cohort not active or finalized.** Refuse to open in `sign` or
  `chair-finalize` mode; allow `browse` only.
- **Manifest stale.** Refuse all modes; instruct operator to re-run
  `flow-hbp-2025-build` preflight.
- **Reviewer not in panel.** Refuse `sign` mode; instruct operator to add
  the reviewer to the panel via the panel-management skill (a separate,
  out-of-scope skill).
- **Reviewer credential expired.** Refuse `sign` mode; route to credential
  renewal.
- **KMS authentication failure.** Refuse signing; do not retry silently;
  emit a `kms-auth-failure` event.
- **TSA unavailable.** Hold the in-flight signature; the candidate
  `ReviewerSignoff` is persisted with `signature: null` and state
  `awaiting-time-stamp`; the skill polls the next TSA in `tsa_list`. After
  exhausting the TSA list, BLOCK.
- **Signature local verification failure.** Discard the candidate; emit
  `signature-verification-failed` event; instruct operator to investigate
  KMS or canonicalization drift; never accept.
- **Record content hash mismatch.** Indicates upstream mutation; BLOCK the
  signing; signal the orchestrator to investigate (potential post-Gate-1
  immutability violation upstream of this Gate, or stale records file).
- **Edit submitted with `EditTarget` outside the closed enum.** Reject;
  no auto-rewrite (the form should not have permitted submission; this is
  treated as adversarial input).
- **Lock contention.** Wait up to a configured timeout; fail-closed if not
  acquired; concurrent signing on the same record is not permitted.
- **Resume after register hash change.** Reject; require a fresh session.

## Examples

```bash
# Browse a cohort read-only
gate1-sme-review work/run-2026-04-30/gate1/cohort-7c2a8e91b3d4f561.signed.jsonld \
  --mode browse

# Reviewer signing session — auto-pick the next eligible record
gate1-sme-review work/run-2026-04-30/gate1/cohort-7c2a8e91b3d4f561.signed.jsonld \
  --mode sign \
  --reviewer rev-9f1a2b3c4d5e6f70

# Reviewer signing a specific record after a queue resolution, resuming
gate1-sme-review work/run-2026-04-30/gate1/cohort-7c2a8e91b3d4f561.signed.jsonld \
  --mode sign \
  --reviewer rev-9f1a2b3c4d5e6f70 \
  --record rec-1a2b3c4d5e6f7081 \
  --resume

# Panel-chair finalization session
gate1-sme-review work/run-2026-04-30/gate1/cohort-7c2a8e91b3d4f561.signed.jsonld \
  --mode chair-finalize \
  --reviewer rev-c0a1b2c3d4e5f607