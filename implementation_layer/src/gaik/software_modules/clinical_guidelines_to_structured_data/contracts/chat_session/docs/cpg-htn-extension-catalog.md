# CPG HTN Extension Catalog

## Status

Normative clinical framework artifact, generated from the Copilot chat-session backlog and packaged for the clinical knowledge extraction framework.

## Purpose

Catalog of CPG hypertension StructureDefinition extensions used by generated PlanDefinition, Library, Evidence, ActivityDefinition, and CDS Hooks artifacts.

## Applicability

This document applies to the standalone hypertension clinical guideline extraction workflow and to any downstream CPG-on-FHIR, CQL, CDS Hooks, safety-case, or publication artifact generated from extracted clinical knowledge.

## Normative controls

- **fail-closed default.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **source quote required.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **W3C PROV and FHIR Provenance.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **deterministic JSON canonicalization.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **two-person review where human judgement is required.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **no real patient data.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **synthetic Synthea-only test data.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **terminology binding required.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **audit log append-only.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.
- **release blocker on unresolved hazard.** The control is mandatory unless an explicit higher-level clinical governance artifact supersedes it.

## Required inputs

- Source guideline manifest with DOI/URL, publisher, jurisdiction, effective date, and SHA-256 fixity.
- Parsed source pages with page numbers, section headings, and stable source anchors.
- Atomic recommendation records with PICO, COR/LOE when present, contraindications, monitoring obligations, and source quotes.
- Terminology bindings for every clinical concept that can affect eligibility, action, medication, measurement, safety, or follow-up.
- Gate registers and attestations for SME review, CQL/informatics signoff, and medical director safety release.

## Required outputs

- A deterministic JSON, YAML, Markdown, FHIR, CQL, or CDS Hooks artifact with a content hash.
- A provenance event naming inputs, tool versions, reviewer/agent identity where applicable, timestamp authority evidence, and validation result.
- A release-blocking error list whenever a required input, hash, terminology binding, test, or signoff is absent.

## Validation checklist

1. Verify all referenced files exist in the active run manifest.
2. Recompute source and artifact SHA-256 values using the canonicalization rule for the artifact type.
3. Confirm no PHI is present in guideline source, generated text, logs, or test fixtures.
4. Confirm clinical claims are supported by verbatim source quotes and source locations.
5. Confirm risk, contraindication, pregnancy, pediatric, renal/hepatic, and drug interaction controls were evaluated when in scope.
6. Confirm all unresolved warnings are explicitly routed to a hold, block, or human review queue.
7. Confirm release cannot proceed while any required row is pending, held without justification, blocked, or missing.

## Integration notes

The clinical extraction prompt loader includes this artifact as part of the contract corpus. Implementations may summarize it for token budget, but they must preserve the normative controls, required inputs/outputs, and validation checklist in the effective prompt or deterministic validation stage.

## Traceability

- Source: `copilot-chat-sessions/thu_apr_30_2026_unstructured_clinical_guidelines_to_structured_output/chat-session.md` late backlog section.
- Framework hazards: H-01 unsupported recommendation, H-02 wrong threshold, H-03 missing contraindication, H-04 missing monitoring, H-05 terminology drift, H-06 PHI/copyright, H-07 CQL logic error, H-08 incomplete review, H-09 stale source, H-10 unsafe publication.
