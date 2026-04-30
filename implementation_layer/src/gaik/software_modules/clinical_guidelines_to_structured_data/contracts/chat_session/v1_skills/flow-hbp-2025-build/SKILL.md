---
name: flow-hbp-2025-build
description: End-to-end orchestrator for the cpg-htn-2025-acc-aha framework. Chains acquire → parse → extract (Gate 1) → bind → structure → CQL (Gate 2) → safety → publish (Gate 3) with non-overridable human authorization stops, fail-closed gates, deterministic re-runs, and full provenance. Refuses to advance on any unresolved hazard.
namespace: cpg-htn-2025-acc-aha
category: orchestration
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<manifest-path> [--phases <list>] [--from <phase>] [--to <phase>] [--cohort <id>] [--resume] [--dry-run]"
---

# flow-hbp-2025-build

End-to-end orchestrator for the `cpg-htn-2025-acc-aha` framework. Chains the
ten pipeline phases — acquire → parse → extract (Gate 1) → bind → structure
→ CQL (Gate 2) → safety → validate → PHI/copyright → publish (Gate 3) — with
non-overridable human-authorization stops at Gates 1, 2, and 3, fail-closed
DQA gates between every phase, deterministic re-runs against pinned tools,
and a single W3C PROV-O bundle covering the build.

This skill does not perform clinical work itself. It composes the constituent
skills, enforces the architectural rules in **ADR-HTN-001**, and refuses to
advance on any unresolved hazard. Caution over velocity is a property of the
orchestrator, not just of the constituent skills: a green Gate 1 cohort
cannot proceed if a single sibling cohort has an open escalation; a Gate 2
signoff cannot proceed on Libraries with Synthea coverage below 95%; Gate 3
cannot proceed if the cumulative quote envelope is exceeded by a single
character.

Posture: **caution over velocity, fidelity over coverage, verbatim over
paraphrase.** No phase auto-corrects another phase's output. No gate is
overridable. No constituent skill is bypassed. No publication occurs without
the medical-director attestation.

## When to Use

Invoke this skill when:

- A signed `guideline-manifest-hbp-2025.yaml` (state == `active`) is in place.
- A new build is required against that manifest.
- A previous build needs to be resumed after a queue resolution, a Gate 1
  rework, a Gate 2 Library re-author, or a Gate 3 panel-chair decision.
- A regression run is needed against the golden set after a tooling-lockfile
  change.

Do **not** invoke this skill if:

- The manifest is in any state other than `active` (e.g.,
  `pending-medical-director`, `superseded`, `withdrawn`).
- Any open errata blocker exists in `errata_watch.blockers_open[]`.
- The manifest's medical-director signoff fails cryptographic verification.
- The publisher quote-extent envelope contract has expired.

The skill performs preflight checks against all of the above and refuses to
start otherwise.

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `manifest-path` | yes | — | Path to a `guideline-manifest-hbp-2025.yaml` instance with `state == "active"` and a verified medical-director signoff. |
| `--phases <list>` | no | `all` | Comma-separated phase identifiers from the closed phase set in §1. Defaults to all phases. Useful for targeted re-runs. |
| `--from <phase>` | no | — | Resume from this phase inclusive. Mutually exclusive with `--phases`. |
| `--to <phase>` | no | — | Stop after this phase inclusive. Mutually exclusive with `--phases`. |
| `--cohort <id>` | no | — | Restrict the run to a specific Gate 1 cohort id. When set, all downstream phases operate only on records bound to that cohort. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted phase boundary. Required after any queue resolution, Gate rework, or Library re-author. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned phase graph and gate stops; do not execute work-producing steps. Permitted in production for change-control reviews. |
| `--strict` | no | `true` | Fail-closed on every DQA gate. Setting `--strict false` is **never permitted** in production; the flag exists only for fixture and golden-set development. |

## Operation

The orchestrator executes the ten phases in §1, with three non-overridable
human-authorization stops (Gates 1, 2, 3) and DQA gates between every phase.
Each phase is delegated to a constituent skill; this skill owns sequencing,
gate enforcement, lockfile integrity, and provenance composition.

### 1. Phase graph (closed phase set)
