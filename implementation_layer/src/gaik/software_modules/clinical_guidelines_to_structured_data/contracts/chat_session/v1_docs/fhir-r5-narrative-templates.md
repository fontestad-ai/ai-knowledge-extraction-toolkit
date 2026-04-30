# FHIR R5 Narrative Templates (`cpg-htn-2025-acc-aha`)

**Status:** stable
**Schema lifecycle:** stable
**Last reviewed:** HUMAN_FILL: ISO-8601 date of most recent panel review
**Authority:** ADR-HTN-001 D2, D3, D5, D8, D9, D10, D14, D15
**Owners:** `cpg-htn-2025-acc-aha` framework (panel chair + medical director)
**Consumers:** `fhir-implementation-guide-build` (P26)
**Pinned by:** `manifests/guideline-manifest-hbp-2025.<version>.yaml` —
`tools_lock.items[]` of `kind == "fhir-r5-narrative-template-pack"`

---

## 0. Posture and scope

This document is the **closed deterministic narrative-template set**
that `fhir-implementation-guide-build` (P26) uses to render the
`Resource.text.div` (XHTML) field of every FHIR R5 resource it
composes into the published IG.

The framework's posture is that **every published FHIR resource's
narrative MUST be a deterministic projection of the resource's
structured content under a closed template set**. No LLM is invoked
at narrative-rendering time. No free-text narrative is permitted in
any resource. This is the framework's defense against
narrative-divergence attacks (where a resource's structured content
asserts one clinical fact while its rendered narrative asserts a
different fact).

Posture: **caution over velocity, fidelity over coverage,
hard-refusal-on-pregnancy over convenience.** The pregnancy
denylist's narrative carries the order-select hard-refuse posture
verbatim by construction, with no softening or attending-override
language. PCE-legacy is forbidden in every narrative. Age gate ≥ 18
is recorded in every population-bounded resource's narrative.
Post-Gate-3 narratives are immutable.

This document does **not** define structured FHIR resource shapes
(those are pinned at the manifest's `tools_lock.items[]` of
`kind == "fhir-r5-profile"`); it defines the **narrative
projections** of the structured content. The two are
complementary: the structured content is the contract for the
EHR-side CDS Hooks runtime and the FHIR R5 IG Publisher; the
narrative is the contract for human readability and for downstream
republishers that may render the narrative directly without
re-reading the structured content.

---

## 1. Closed template set

The framework defines exactly **fifteen closed templates**, one per
resource type composed at P26 (mirroring §2 of
`fhir-implementation-guide-build` `SKILL.md`). Adding a new
template requires ADR-HTN-001 amendment under panel-chair signoff
AND a coordinated update of every parent schema and skill.

| # | Template id | Resource type | Source artifact |
|---|---|---|---|
| 1 | `tpl-implementation-guide-1.0.0` | `ImplementationGuide` | (synthesized) |
| 2 | `tpl-capability-statement-1.0.0` | `CapabilityStatement` | (synthesized) |
| 3 | `tpl-library-1.0.0` | `Library` | Gate-2 register snapshots |
| 4 | `tpl-evidence-contraindication-1.0.0` | `Evidence` (contraindication) | contraindication artifact (P14) |
| 5 | `tpl-evidence-monitoring-1.0.0` | `Evidence` (monitoring) | monitoring artifact (P15) |
| 6 | `tpl-evidence-record-1.0.0` | `Evidence` (record-level) | records.json (P9) |
| 7 | `tpl-evidence-variable-1.0.0` | `EvidenceVariable` | contraindication + monitoring + records |
| 8 | `tpl-evidence-report-hazard-1.0.0` | `EvidenceReport` | Safety Case (P23) |
| 9 | `tpl-plan-definition-1.0.0` | `PlanDefinition` | Gate-2 + monitoring artifact |
| 10 | `tpl-activity-definition-1.0.0` | `ActivityDefinition` | pharm-rules.json (P13) |
| 11 | `tpl-service-definition-1.0.0` | `ServiceDefinition` | CDS Hooks service set (P22) |
| 12 | `tpl-citation-1.0.0` | `Citation` | acquire-hbp-2025-source manifest (P1) |
| 13 | `tpl-observation-definitional-1.0.0` | `Observation` (definitional) | bp-thresholds.json (P12) |
| 14 | `tpl-value-set-1.0.0` | `ValueSet` | terminology bindings (P10) |
| 15 | `tpl-concept-map-1.0.0` | `ConceptMap` | terminology bindings (P10) |

Two additional template ids are reserved but **MUST** be rendered
verbatim from upstream artifacts (no narrative projection is
applied):

- `tpl-provenance-passthrough-1.0.0` (`Provenance`): the narrative
  is `"<div xmlns=\"http://www.w3.org/1999/xhtml\">Generated
  Provenance for <code>{target_id}</code>; signature data
  recorded in fixity manifest.</div>"`. No template substitution is
  applied beyond `{target_id}`.
- `tpl-structure-definition-passthrough-1.0.0`
  (`StructureDefinition`): the narrative is the deterministic
  rendering of the StructureDefinition's `differential.element[]`
  by the FHIR R5 IG Publisher's standard rendering, frozen at the
  manifest's pinned IG Publisher version. No framework-specific
  template applies.

The skill MUST refuse to render any narrative against a template id
not in this closed set. Adding `Group` or any other resource type's
template requires ADR-HTN-001 amendment.

---

## 2. Template-rendering invariants (apply to every template)

The following invariants apply to every template. Validators MUST
enforce all of them at narrative composition time.

### 2.1 Determinism
- Identical structured input MUST produce identical narrative
  bytes.
- The narrative is rendered by string substitution against the
  template; no dynamic logic, no LLM, no live network call is
  invoked.

### 2.2 Closed substitution variable set
- Each template defines a closed list of substitution variables
  (e.g., `{rule_id}`, `{cor}`, `{loe}`, `{drug_classes_list}`,
  `{population_filter_list}`, etc.). Variables outside the template's
  declared list MUST NOT appear in the output. Templates MUST refuse
  rendering on undeclared variable references.

### 2.3 Verbatim-clinical-text invariant
- When a template substitutes a variable that originates from
  clinical text in the source guideline (e.g.,
  `{source_text_verbatim}`), the substitution MUST be byte-for-byte
  the parent atomic unit's `text_verbatim` after Phase-2 reversible
  normalization. No paraphrase, no truncation, no formatting
  modification. The narrative MAY wrap the verbatim text in a
  `<blockquote>` or `<q>` element but MUST NOT alter the text's
  characters.

### 2.4 ACC/AHA grading verbatim
- COR and LOE values MUST be rendered verbatim from the closed enums
  in `schemas/acc-aha-grading.yaml`. The framework's policy is that
  ACC/AHA grading is the primary rating system (per ADR-HTN-001 D3);
  no remapping is permitted in narratives. The HL7 certainty
  mapping is rendered as a **secondary** annotation per
  `docs/acc-aha-to-hl7-certainty.md` §3.

### 2.5 Closed AttendingOverridePattern denylist
- The output XHTML MUST be free of attending-override semantics.
  The skill recursively scans the rendered output (case-insensitive
  after Unicode NFC) for any pattern in the closed
  `AttendingOverridePattern` set
  (`schemas/cds-hooks-services-htn.yaml` §2.5,
  `schemas/pharm-rule-htn.yaml` §2.7,
  `schemas/contraindication-artifact-htn.yaml` §2.6 — all mirrored).
  Match → BLOCK with `attending-override-pattern-detected`.
  This rule applies even when the upstream source-text contains the
  pattern by accident (e.g., a quoted reviewer note); upstream
  remediation is required.

### 2.6 PCE-legacy literal denylist
- The output XHTML MUST be free of the literal `PCE-legacy`
  (case-insensitive after Unicode NFC). Match → BLOCK with
  `pce-legacy-binding-detected`. The framework's policy is that
  PCE-legacy never appears in any published artifact (ADR-HTN-001
  D5); narratives are no exception.

### 2.7 Age-gate annotation
- Every population-bounded resource's narrative MUST include the
  literal sentence:
  > "Age gate: ≥ 18 years (intended use; pediatric populations
  > out of scope)."
- The age-gate sentence is a verbatim string and MUST be the exact
  byte sequence above (no synonyms, no rephrasing). Validators
  recompute the sentence's SHA against the manifest's pinned
  age-gate string and refuse on mismatch.

### 2.8 Pregnancy hard-refuse annotation
- For every resource whose `cpg-htn-population-filter` extension
  includes `pregnant` or `postpartum` AND whose source-rule kind is
  `denylist`, the narrative MUST include the literal sentence:
  > "Posture: order-select hard refuse. Attending override: not
  > permitted. Documentation-only override: not permitted."
- Like §2.7, the sentence is a verbatim string with no permitted
  variations. Validators recompute the sentence's SHA and refuse on
  mismatch.

### 2.9 Source-anchor footnote
- Every resource whose `cpg-htn-source-anchor` extension is non-
  empty MUST render the source-anchor footnote at the end of the
  narrative under a closed format:
  > "Source: 2025 ACC/AHA Hypertension Guideline; recommendation
  > {record_id}; atomic unit {atomic_unit_id}; anchor
  > <code>{anchor_kind}</code>; SAIR
  > <code>{sair_sha256[:16]}…</code>; page {page}."
- The footnote MUST appear exactly once per narrative. Duplicates
  or omissions are a release blocker.

### 2.10 XHTML safety
- The output XHTML MUST satisfy the FHIR R5 narrative XHTML
  subset:
  - Only `<div>`, `<p>`, `<h2>`–`<h6>`, `<a>`, `<ul>`, `<ol>`,
    `<li>`, `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`,
    `<td>`, `<code>`, `<pre>`, `<blockquote>`, `<q>`, `<em>`,
    `<strong>`, `<br/>`, `<hr/>`, `<span>`, `<small>` elements.
  - No `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>`,
    `<form>`, `<input>`, `<button>`, `<svg>`, `<canvas>`.
  - No `style` attribute.
  - No `on*` event handlers.
  - No external resource URLs in `href` other than RFC-3986
    canonical-form URIs to FHIR Reference targets and to the
    framework's `https://aiwg.io/cpg-htn-2025-acc-aha/...` URL
    space.
  - No inline base64-encoded data.
- The skill's renderer MUST validate every produced narrative
  against this subset; violations BLOCK with
  `narrative-xhtml-violation`.

### 2.11 Deterministic timestamps
- Templates MUST NOT embed wall-clock timestamps in the narrative
  (e.g., "rendered at 2026-04-30 14:32:01 UTC"). Where a timestamp
  is required for human reference, the template substitutes
  `{build_version_label}` (e.g., `v1.0.0+ACC-AHA-2025+US+2026-04-30`),
  which is deterministic from the build pin.

### 2.12 Length bounds (per template)
- Every template declares a `max_chars_after_substitution` integer.
  Renderings exceeding the bound BLOCK with
  `narrative-length-exceeded`. Bounds are listed per template in §3.

### 2.13 Localization
- The framework's published narratives are English-only at v1.0.0.
  Localization to other languages is out of scope for v1.0.0 and
  routes through a manifest-version-level amendment with a
  per-language template pack. Validators MUST refuse non-English
  narrative content at v1.0.0.

---

## 3. Template definitions (closed)

Each template below is normative. The substitution variables are
listed exhaustively; templates MUST refuse undeclared variables.
The XHTML is shown with `{variable}` placeholders that the renderer
substitutes at composition time.

> **Notation.** All templates wrap their output in
> `<div xmlns="http://www.w3.org/1999/xhtml">…</div>` (FHIR R5
> requires this exact namespace declaration).

> **Legend (status):**
> - **enum-substitution**: variable value MUST be a member of the
>   declared closed enum.
> - **byte-verbatim**: variable value is byte-for-byte from
>   upstream (no transformation).
> - **id-substitution**: variable value is a deterministic id from
>   the framework's id-derivation rules.
> - **hash-prefix-substitution**: variable value is the first 16
>   hex characters of a SHA-256.
> - **list-substitution**: variable value is a comma-joined list
>   from a closed enum.

---

### 3.1 `tpl-implementation-guide-1.0.0`

**Resource:** `ImplementationGuide`
**Source:** synthesized.
**Max chars after substitution:** 8000.

#### Substitution variables
| Variable | Kind | Constraint |
|---|---|---|
| `{ig_canonical_url}` | id-substitution | `https://aiwg.io/cpg-htn-2025-acc-aha/ImplementationGuide/cpg-htn-2025` |
| `{build_version_label}` | byte-verbatim | from `manifest.build_version_label` |
| `{publisher}` | byte-verbatim | from `manifest.publisher` |
| `{manifest_payload_sha256_prefix}` | hash-prefix-substitution | `manifest.fixity.manifest_sha256[:16]` |
| `{gate3_attestation_sha256_prefix}` | hash-prefix-substitution | from Gate-3 attestation |
| `{ig_package_sha256_prefix}` | hash-prefix-substitution | computed at IG build |

#### Template

```xhtml
<div xmlns="http://www.w3.org/1999/xhtml">
  <h2>Implementation Guide: 2025 ACC/AHA Hypertension Guideline</h2>
  <p>Canonical URL: <code>{ig_canonical_url}</code></p>
  <p>Build version: <code>{build_version_label}</code></p>
  <p>Publisher: {publisher}</p>
  <p>Pin chain (truncated SHA-256 prefixes for display):</p>
  <ul>
    <li>Manifest payload: <code>{manifest_payload_sha256_prefix}…</code></li>
    <li>Gate-3 attestation: <code>{gate3_attestation_sha256_prefix}…</code></li>
    <li>IG package: <code>{ig_package_sha256_prefix}…</code></li>
  </ul>
  <p>Posture: caution over velocity; fidelity over coverage;
     hard-refusal-on-pregnancy over convenience. Risk function:
     PREVENT (canonical). PCE-legacy: not used.</p>
  <p>Age gate: ≥ 18 years (intended use; pediatric populations
     out of scope).</p>
</div>