---
name: acquire-hbp-2025-source
description: Phase-1 ingest skill for the cpg-htn-2025-acc-aha framework. Acquires exactly the four source documents named by the active manifest (main guideline, executive summary, supplement, predecessor-2017), verifies cryptographic and license fidelity, polls publisher errata feeds and CrossRef relations, blocks on any drift, persists the immutable raw byte-streams under raw/<source-id>/, and writes back source-side fixity manifests. Source-admission is closed; no auto-update; no override; no PHI; no real patient data; no fifth document.
namespace: cpg-htn-2025-acc-aha
category: ingest
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<manifest-path> [--mode <verify|fetch|verify+fetch>] [--source <role>] [--strict]"
---

# acquire-hbp-2025-source

Phase-1 ingest skill for the `cpg-htn-2025-acc-aha` framework. The skill
is the only authorized producer of source-side fixity manifests and
errata-watch state under `raw/<source-id>/`. It acquires exactly the
four source documents named by the active
`schemas/guideline-manifest-hbp-2025.yaml` instance, verifies
cryptographic and license fidelity against the manifest's pins, polls
the publisher errata feeds and CrossRef `is-corrected-by` relations,
blocks on any drift, and writes back the immutable raw byte-streams plus
a per-source fixity manifest that downstream phases consume.

This skill does **not** parse PDFs, extract text, normalize content, or
modify byte-streams. It is the ingest gate for the build pipeline:
everything that follows assumes the four sources exist on disk in their
publisher-delivered form and that their SHA-256 hashes match the
manifest's pins exactly. If those assumptions fail, this skill refuses
to advance the build.

Posture: **caution over velocity, fidelity over coverage, no-auto-update
over convenience.** Source-admission is closed. The four roles are the
only roles. A new source — including a different edition, a different
language, a different jurisdiction — requires a new manifest version
with explicit predecessor chain and panel-chair signoff; this skill
will refuse to ingest it. Auto-update is forbidden. Errata clear under
human review only; SHA mismatches BLOCK; license-contract drift BLOCKS.

This skill is the operational counterpart to `safety-case-attest` at
the opposite end of the pipeline: where Gate 3 attests that a build
faithfully honors the source, P1 attests that the source the build
descends from is exactly what the manifest declared.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P1** for a
  manifest in state `active` with verified medical-director signoff and
  `errata_watch.blockers_open == []`.
- A scheduled errata-watch poll is due (cadence per manifest's
  `errata_watch.poll_cadence_iso8601`); this skill polls and reports,
  but does not silently re-baseline.
- A change-control review needs to verify that the on-disk sources
  still match the manifest's pins, without re-fetching (use
  `--mode verify`).
- A new manifest version has been activated with new source pins and
  fresh sources must be fetched and pinned (use `--mode fetch`, which
  also runs `verify`).

Do **not** invoke this skill if:

- The manifest is in any state other than `active`.
- The medical-director signoff fails verification.
- The publisher contract URI cannot be resolved (this is a release
  blocker; the skill will refuse to ingest sources without contract
  evidence even if the bytes are otherwise available).
- Real patient-bearing PDFs are being substituted for the publisher's
  documents (PHI fail-closed at the manifest's policy; the skill checks
  upstream URLs against the manifest's pins).

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `manifest-path` | yes | — | Path to a `guideline-manifest-hbp-2025.yaml` instance with `state == "active"` and a verified medical-director signoff. |
| `--mode <verify\|fetch\|verify+fetch>` | no | `verify+fetch` | `verify` checks on-disk sources against the manifest's pins; `fetch` retrieves missing sources from the publisher; `verify+fetch` does both (fetch any missing, verify all). The skill never overwrites existing source bytes when their on-disk SHA matches the manifest pin. |
| `--source <role>` | no | `all` | One of `main-guideline`, `executive-summary`, `supplement`, `predecessor-2017`, or `all`. Useful for targeted re-verification. |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production; the flag exists only for fixture and golden-set development (e.g., when constructing a draft manifest from non-publisher fixtures during framework bootstrap). |
| `--dry-run` | no | `false` | Emit the planned acquisition steps and pin-comparison report; do not retrieve or write any bytes. Permitted in production for change-control review. |

## Operation

### 1. Preflight

1. Validate `manifest-path` against
   `schemas/guideline-manifest-hbp-2025.yaml`. Reject on any invariant
   failure (`GM-INV-01` … `GM-INV-28`).
2. Verify `state == "active"` and `errata_watch.blockers_open == []`.
3. Cryptographically verify `medical_director_signoff.signature`
   against `fixity.manifest_sha256` per `GM-INV-21`. Producer claims of
   `verifies: true` are ignored; the skill re-verifies.
4. Verify `tools_lock.lock_sha` against the canonicalized
   `tools_lock.items[]` (`GM-INV-08`).
5. Verify the publisher contract URI is well-formed for every source
   under §5.4 of the manifest's policy (`source_admission`); the skill
   does not retrieve the contract document, but it confirms the URI is
   present and the `contract_signed_at` falls within a window the
   skill's tooling considers current (the orchestrator's pre-build
   contract validity check is upstream of this skill's preflight).
6. Verify the framework's resource budget: at least one TSA in
   `tsa_list[]` is currently within `cert_valid_*` (the source-side
   fixity manifest is signed for tamper-evidence).
7. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Source-admission policy enforcement

The skill admits **exactly four** roles, and only these four:
