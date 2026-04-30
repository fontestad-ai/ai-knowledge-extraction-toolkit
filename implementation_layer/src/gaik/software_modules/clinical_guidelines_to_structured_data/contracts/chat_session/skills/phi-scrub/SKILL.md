---
name: phi-scrub
description: Clinical guideline framework skill generated from the chat-session backlog. Phase P3. Detect PHI/PII in sources, parses, prompts, outputs, logs, and packaged artifacts using Presidio, spaCy med7, regex, and deterministic allowlists.
---

# phi-scrub

## Phase

P3

## Mission

Detect PHI/PII in sources, parses, prompts, outputs, logs, and packaged artifacts using Presidio, spaCy med7, regex, and deterministic allowlists.

## Safety posture

- Caution over velocity.
- Source-grounded only; never invent clinical guidance.
- Fail closed on missing source anchors, missing terminology bindings, missing signoffs, stale fixity, PHI, copyright envelope breach, or unresolved clinical hazard.
- Use synthetic Synthea data only for executable logic tests.
- Emit deterministic artifacts with SHA-256 fixity and W3C PROV + FHIR Provenance where applicable.

## Inputs

- `work/<run_id>/run-manifest.json`
- `work/<run_id>/source/source-acquisition.yaml`
- Parsed pages with page, section, bounding box when available, and source quote spans.
- Upstream atomic units, recommendation records, pharmacology rules, contraindication artifacts, monitoring artifacts, terminology bindings, and gate registers as required by this phase.

## Outputs

- A phase-specific YAML/JSON/Markdown/FHIR/CQL artifact in `work/<run_id>/`.
- A validation report with `pass`, `held`, or `blocked` state.
- A provenance event with input hashes, output hash, tool versions, operator identity when applicable, and timestamp authority evidence.

## Procedure

1. Load the run manifest and refuse execution if the manifest is missing, stale, or references an unsupported jurisdiction/effective date.
2. Load all declared upstream artifacts and recompute hashes before use.
3. Validate schema shape before reading clinical fields.
4. Apply the phase mission using only source-grounded inputs and closed enums.
5. Route ambiguity to a held/reconcile queue rather than guessing.
6. Run deterministic validation checks and phase-specific clinical safety checks.
7. Write outputs atomically, recompute content hash, append provenance, and update the run log.

## Required mitigations

| Risk | Mitigation |
|---|---|
| Unsupported clinical claim | Require verbatim source quote and page/section locator. |
| Wrong threshold or medication condition | Cross-check against source, pharmacology, contraindication, monitoring, and risk artifacts. |
| Missing terminology or code drift | Block until terminology binding service returns version-pinned binding or approved human hold. |
| PHI or copyright issue | Block and route to PHI/copyright remediation. |
| Model disagreement | Require family-distinct review and two-person reconciliation when human judgement is needed. |
| Incomplete tests | Block release until Synthea/CDS/CQL coverage gates pass. |

## Acceptance criteria

- All required inputs are present and hash-verified.
- All generated records validate against the corresponding schema.
- All clinically actionable output has source quote, source location, and provenance.
- No unresolved `pending`, `blocked`, or unjustified `held` rows remain.
- The run log contains a phase start, validation, write, and verification event.

## CLI contract

```bash
clinical-framework phi-scrub --run-id <run_id> --mode verify+build
```

`--mode build` writes missing outputs, `--mode verify` recomputes and reports drift, and `--mode verify+build` builds missing outputs then verifies all outputs. The skill never overwrites hash-matching artifacts and never advances a failed gate.
