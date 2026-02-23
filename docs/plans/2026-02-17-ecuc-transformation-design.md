# Design: ECUC Pattern 09 — Transformation Showcase

**Date**: 2026-02-17
**Replaces**: Current static type-definition approach in `autosar/patterns/09-ecuc-definition-value.md`

## Motivation

The current pattern 09 maps ECUC definitions to static M2 types and ECUC values to M1 instances. While structurally correct, it misses the defining characteristic of ECUC: both metamodel (definitions) and model (values) live as data at the same level. The correct showcase leverages Rupa's transformation system to demonstrate this.

## Core Insight

ECUC definition types (`EcucModuleDef`, `EcucParamConfContainerDef`, `EcucIntegerParamDef`, etc.) are ordinary types in the `autosar-25-11` domain. An NvM definition file creates *instances* of these types — the metamodel is just data. Rupa's `#[decode(domain)]` pipeline reads this data and dynamically produces a typed domain via the M3 API.

## Pipeline Overview

```
definition.rupa                    values.rupa
(EcucModuleDef instances)          (EcucContainerValue instances)
        |                                  |
   #[decode(domain)]                  #[transform]
        |                                  |
        v                                  v
   ecuc-nvm domain  ──────────>  typed NvM instances
   (generated M2 types)          (generated M1 instances)
        |
   #[encode(domain)]
        |
        v
   EcucModuleDef instances (round-trip)
```

Materialized views (`decoded-domain.rupa`, `decoded-values.rupa`) show pipeline output as plain Rupa for clarity.

## File Structure

| File | Role |
|------|------|
| `ecuc-nvm/definition.rupa` | NvM definition — instances of `autosar-25-11::EcucModuleDef` |
| `ecuc-nvm/decode.rupa` | `#[decode(domain)]` — definition data → typed `ecuc-nvm` domain |
| `ecuc-nvm/decoded-domain.rupa` | Materialized view — generated types as plain Rupa |
| `ecuc-nvm/values.rupa` | NvM config values — instances of `autosar-25-11::EcucContainerValue` |
| `ecuc-nvm/transform.rupa` | `#[transform]` — generic ECUC values → typed instances |
| `ecuc-nvm/decoded-values.rupa` | Materialized view — typed instances as plain Rupa |
| `ecuc-nvm/encode.rupa` | `#[encode(domain)]` — types back to `EcucModuleDef` data |

## Document Narrative Structure

1. **AUTOSAR Concept** — Two-layer architecture, reframed: both layers are data in the same format
2. **The Insight** — ECUC encodes metamodel and model at the same level; `DEFINITION-REF` is a manual schema-conformance link
3. **Pipeline Overview** — Diagram showing the full decode → transform → encode flow
4. **Worked Example** — Seven files in order, each with narrative lead-in
5. **Structural Comparison** — Before/after table (ARXML vs typed Rupa)
6. **Design Reference** — Links to transformation-language.md, m3-api-reference.md, metamodel-support.md

## Key Design Decisions

- **No `ecuc-base` domain**: ECUC definition types are part of `autosar-25-11`, not a separate domain
- **Fully replaces old content**: The static approach is misleading; the transformation IS the pattern
- **Role names match ECUC parameter names**: e.g., `.NvMNvramBlockIdentifier` — faithful to how ECUC works
- **Tags for traceability**: `::set_tag(t, "ecuc-def", cdef.path)` links generated types back to their source definitions
- **String-typed values in generic layer**: `EcucParameterValue.value` is `String` — interpretation depends on definition type, resolved at transform time via `match` on definition type
