---
name: extract-pharm-rules
description: Phase-13 (P13) extraction skill for the cpg-htn-2025-acc-aha framework. Decomposes Gate-1-finalized RecommendationRecord and AtomicUnit content into closed-shape pharmacologic rules — first-line selection, denylist, dose modifier, monitoring, and discontinuation — under a dual-LLM family-distinct atomicity pass with deterministic numeric-fact and RxNorm-pin verification. Hard-anchors every denylist rule to a COR III-Harm or COR III-No-Benefit source span. Pregnancy-denylist rules carry the order-select hard-refuse posture by construction. PCE-legacy never feeds rules. Held rules route to the panel-chair queue. Post-Gate-1 rule sets are immutable.
namespace: cpg-htn-2025-acc-aha
category: extract
platforms: [claude, copilot, cursor, factory, windsurf, warp, codex, opencode, openclaw, hermes]
commandHint:
  argumentHint: "<sair-path> [--records <list>] [--cohort <id>] [--rule-kinds <list>] [--resume] [--dry-run]"
---

# extract-pharm-rules

Phase-13 (P13) extraction skill for the `cpg-htn-2025-acc-aha`
framework. The skill decomposes Gate-1-finalized
`RecommendationRecordHTN` and `AtomicUnit` content into closed-shape
**pharmacologic rules** — first-line selection, denylist, dose
modifier, monitoring, and discontinuation — under a dual-LLM
family-distinct atomicity pass with deterministic numeric-fact and
RxNorm-pin verification. The skill is the only authorized writer of
`work/<run_id>/pharm-rules.json` and the upstream feeder of:

- the CQL Library set produced at P20 (`emit-cql-htn`);
- the CDS Hooks service set packaged at P22 (`cds-hooks-package-htn`);
- the Safety Case mitigations authored at P23 (`safety-hbp`);
- the Implementation Guide build at P26 (`fhir-implementation-guide-build`).

This refresh aligns the skill exactly to the schemas drafted in this
thread:

- `schemas/acc-aha-grading.yaml` — closed COR/LOE enums for basis
  inheritance.
- `schemas/sair.yaml` — input source-of-truth (read-only).
- `schemas/recommendation-record-htn.yaml` — input contract.
- `schemas/atomic-unit.yaml` — input contract; the dual-LLM
  family-distinct rule is mirrored from `AU-INV-09`.
- `schemas/gate1-register.yaml` — finalization preconditions and the
  panel-chair escalation paths.
- `schemas/gate2-register.yaml` — downstream consumer; the rules this
  skill emits feed Library snapshots whose hard-block invariants are
  the rules' enforcement surface at Gate 2.
- `schemas/safety-case-htn.yaml` — downstream consumer; mitigations
  reference rules by id.
- `schemas/cds-hooks-services-htn.yaml` — downstream consumer; the
  pregnancy denylist and first-line-check service descriptors bind to
  Libraries derived from these rules.
- `schemas/guideline-manifest-hbp-2025.yaml` — pin source for tools,
  terminology editions, RxNorm pinning, and risk engine identity.

This skill does **not** author CQL bytes, build CDS Hooks
descriptors, modify recommendation records, mutate atomic units, alter
terminology bindings (P10's responsibility), bind the risk engine
(P16's responsibility), or attest the Safety Case (P23's
responsibility). Its single responsibility is producing the closed-shape
pharmacologic-rule set that downstream phases bind, package, and
attest.

Posture: **caution over velocity, fidelity over coverage,
hard-refusal-on-pregnancy over convenience.** No paraphrase of
clinical text. No editing of ACC/AHA COR or LOE. No silent
re-extraction. No batch acceptance. No LLM-only path. No softening of
COR III-Harm to soft-warning. No RxNorm-edition substitution.
PCE-legacy never feeds rules. Held rules route to the panel-chair
queue, never to a silent fall-through. Post-Gate-1 rule sets are
immutable.

## When to Use

Invoke this skill when:

- The orchestrator (`flow-hbp-2025-build`) reaches phase **P13** for
  a build whose Gate-1 cohort registers are in state `finalized`,
  whose `records.json` and `atomic-units.json` are sealed, and whose
  P10 (terminology binding) and P12 (BP threshold extraction) outputs
  are persisted.
- A targeted re-extraction is required after a Gate-1 reviewer
  recorded `accept-with-edit` on a record that bears on a
  pharmacologic rule (the orchestrator regenerates the affected
  record's atomic units per `AU-INV-24` and re-posts to this skill on
  resume).
- A held rule in `work/<run_id>/queue/pharm-rules/` has been
  resolved by the two-person rule and the orchestrator requests
  advancement.
- A regression run is needed against the framework's golden
  pharmacologic-rule set after a schema or skill change.
- A targeted re-run is required after a `tools_lock` change
  authorized by a new manifest version (e.g., an RxNorm edition
  rotation or an LLM pair rotation).

Do **not** invoke this skill if:

- The active manifest is not in state `active` or has open errata
  blockers.
- Any Gate-1 cohort referenced by records under extraction is not in
  state `finalized`.
- `records.json` or `atomic-units.json` are not sealed.
- P10 (terminology binding) has not produced a complete RxNorm
  binding for every drug-class anchor in the records under
  extraction.
- A prior P13 run produced rules in the queue that have not been
  resolved by the two-person rule (the skill refuses to overwrite
  unresolved queue entries).

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `sair-path` | yes | — | Path to the sealed SAIR document at `work/<run_id>/sair.json`, validated against `schemas/sair.yaml`. |
| `--records <list>` | no | `all-finalized` | Comma-separated list of `RecommendationRecordHTN` ids whose pharmacologic implications are to be extracted. Defaults to every record in `records.json` whose Gate-1 register state is `finalized` and whose `clinical_topic` is pharmacologic. |
| `--cohort <id>` | no | — | Restrict to records bound to the given Gate-1 cohort id. Useful for targeted re-runs after a single cohort's rework. |
| `--rule-kinds <list>` | no | `all` | Comma-separated subset of the closed rule kinds (`first-line-selection`, `denylist`, `dose-modifier`, `monitoring`, `discontinuation`). Defaults to all five. |
| `--resume` | no | `false` | Resume an interrupted run from the last persisted rule. The skill rejects resume if the SAIR's `fixity.sair_sha256` or any input register's hash has changed since session start. |
| `--strict` | no | `true` | Fail-closed on every gate. Setting `--strict false` is **never permitted** in production. |
| `--dry-run` | no | `false` | Run preflight + plan only; emit the planned record set, the proposed rule decomposition, and the dual-LLM family-distinct verification; do not persist rules or open queue entries. Permitted in production for change-control review. |

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
4. Verify the **two-LLM family-distinct rule** at preflight (mirrored
   from `extract-recommendation-cor-loe` §1.4 and from `AU-INV-09`):
   - Resolve `manifest.tools_lock.llm_pair[]`. Confirm exactly two
     entries (`GM-INV-09`).
   - Confirm the two LLMs are from distinct vendor families per
     `docs/llm-family-matrix.md`.
   - Probe each LLM for liveness with a deterministic test prompt;
     record the response signature.
   - **Family-collapse → BLOCK** with `family-distinct-rule-violated`;
     remediation is a new manifest version with a different pinned
     pair.
5. Verify upstream prerequisites (each is a release blocker):
   - `work/<run_id>/records.json` is sealed and validates against
     `schemas/recommendation-record-htn.yaml`. Specifically `INV-09`
     (denylist requires hard-block basis with source anchor) and
     `INV-10` (PCE-legacy never propagates) must hold on every record
     in scope.
   - `work/<run_id>/atomic-units.json` validates against
     `schemas/atomic-unit.yaml`; every record-bound atomic unit set
     is sealed at `state == "gate-1-passed"`.
   - Every Gate-1 cohort register file under
     `work/<run_id>/gate1/*.signed.jsonld` is in state `finalized`
     and validates against `schemas/gate1-register.yaml`.
   - `work/<run_id>/terminology-bindings.json` (produced at P10) is
     present and binds every drug-class anchor in scope to a
     manifest-pinned RxNorm edition.
   - `work/<run_id>/bp-thresholds.json` (produced at P12) is present;
     dose-modifier rules that trigger on BP thresholds reference
     this artifact by content hash.
6. Verify the **terminology server** is reachable at the pinned
   editions for re-resolution (the skill does not rebind, but it
   re-resolves RxNorm codes at sign time to detect upstream drift).
7. Verify the manifest's pinned `risk_engine.name == "PREVENT"` and
   `risk_engine.legacy_only == false` (PCE-legacy never feeds
   rules).
8. Verify the **pregnancy value-set id** is pinned in the manifest
   (`manifest.intended_use.pregnancy_value_set_id`); the denylist
   rules reference this id by opaque token, resolved at validation
   time.
9. Verify the **TSAs** in `manifest.tsa_list[]`: at least one cert is
   currently within `cert_valid_*` (the rule-set fixity manifest is
   signed for tamper-evidence at sign time).
10. Refuse to proceed if any precondition fails. **Fail-closed.**

### 2. Closed rule kinds

The skill produces rules of exactly the following five kinds; any
other kind is rejected at the schema level. The order below is the
skill's processing order; the order is preserved in the output JSON
for determinism (rules are sorted by `rule_id` ascending only at the
service-set manifest layer downstream, not within the rule set
itself).

| Rule kind | Purpose | Downstream wiring |
|---|---|---|
| `first-line-selection` | Selects first-line antihypertensive class(es) for a population. | CQL Library `FirstLineSelection`; CDS Hooks service `htn-pharm-first-line-check` (informational/soft-warning branch). |
| `denylist` | Refuses a drug class for a population at order-select. | CQL Library `PregnancyHTN` / `FirstLineSelection`; CDS Hooks service `htn-pregnancy-denylist` (hard-refuse) and `htn-pharm-first-line-check` (hard-refuse branch). |
| `dose-modifier` | Adjusts dosing range for a population (e.g., older adult start-low). | CQL Library `SpecialPopulationModifiers`; CDS Hooks service `htn-pharm-first-line-check` (soft-warning branch). |
| `monitoring` | Specifies monitoring requirement after a prescribing event. | CQL Library `SpecialPopulationModifiers`, `ResistantHTN`; CDS Hooks service `htn-pharm-first-line-check`, `htn-resistant-workup`. |
| `discontinuation` | Specifies taper or no-abrupt-discontinuation rule. | CQL Library `SpecialPopulationModifiers`; documentation artifact `guideline-card` (protocolized-taper section). |

The set is **closed**. Adding a sixth kind (e.g., a
combination-therapy rule that encodes both selection and dose
modification atomically) requires an ADR-HTN-001 amendment and is
explicitly out of scope for this skill.

### 3. Per-record rule decomposition

For every record in scope, the skill performs the following
mechanical decomposition. The decomposition is the
**dual-LLM family-distinct atomicity pass** (mirrored from P9's
`extract-recommendation-cor-loe` §3) applied to the record's atomic
units, producing one or more candidate rules.

#### 3.1 Atomic-unit prefiltering

The skill enumerates the record's atomic units and prefilters by
kind:

- `atomic-recommendation` units are candidates for `first-line-selection`,
  `denylist`, or `discontinuation` rules.
- `qualifier` units are candidates for `dose-modifier` rules.
- `exclusion` units are candidates for `denylist` rules.
- `monitoring` units are candidates for `monitoring` rules.
- `citation` units are not rule sources; they remain as anchors.

The skill consults the record's `predecessor_2017` mapping advisory
for context only; the mapping does not propagate as a rule input
(per ADR-HTN-001 D14, mapping is advisory).

#### 3.2 Dual-LLM rule proposal

Two LLMs from distinct families (the verified pair from §1.4)
receive the same closed-prompt template per atomic unit:
