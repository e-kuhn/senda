# AUTOSAR Converter Improvements Design

**Date:** 2026-02-17
**Status:** Approved

## Overview

Improve the AUTOSAR XSD-to-Rupa converter to extract documentation, fix formatting, correct integer-with-token inference, and annotate instance-ref types.

## Changes

### 1. Documentation Extraction (Parser Layer)

Extract `<xsd:documentation>` text from XSD annotations on:
- Types (groups, complexTypes, simpleTypes)
- Members (elements within sequences/choices)
- Enum values (each `<xsd:enumeration>`)

**Model changes** — add `doc: str | None` fields to:
- `InternalType` (base class — all types get doc)
- `InternalMember` (member-level docs)
- `ExportPrimitive`, `ExportEnum`, `ExportComposite`, `ExportMember` (carry through to generation)
- `ExportEnum` gets `value_docs: list[str | None]` parallel to `values`

### 2. Enum Formatting (Generator Layer)

Multi-line enum output, one value per line, with doc comments:

```rupa
/// Maximum allowable deviation type
type BswExecutionContextEnum = ::enum(
    /// Context of an OS "hook" routine
    hook,
    /// CAT1 interrupt context
    interruptCat1,
    /// CAT2 interrupt context
    interruptCat2,
);
```

### 3. Composite Variant Comments (Generator Layer)

Multi-line alternatives above the member, each type on its own line:

```rupa
    // also:
    //   AsynchronousServerCallPoint,
    //   AsynchronousServerCallResultPoint,
    //   ExternalTriggeringPointIdent,
    //   InternalTriggeringPoint
    .accessPoint : &AbstractAccessPoint?;
```

No truncation limit — show all alternatives.

### 4. Integer-with-Token Fallback (Parser Layer)

In `analyze_pattern`: when supertype resolves to INTEGER but extracted tokens contain non-numeric values (not `INF`, `-INF`, `NaN`), demote the entire type to STRING. Keep the original full pattern.

### 5. Instance-Ref Annotations (Parser + Generator)

**Detection:** Types with `instanceRef` stereotype get `#[instance_ref]` annotation.

**Role classification from XSD naming:**
- `TARGET-*-REF` members → `#[target]`
- `CONTEXT-*-REF` or `ROOT-*-REF` members → `#[context]`

**Generator output:**

```rupa
/// Navigation reference description from XSD
#[instance_ref]
type AppCompositeElementInstanceRef = AtpInstanceRef {
    /// Entry point doc from XSD
    #[context]
    .rootDataPrototype : &AutosarDataPrototype?;
    /// Context navigation doc from XSD
    #[context]
    .contextDataPrototype : &AppCompositeElementDataPrototype*;
    /// Target element doc from XSD
    #[target]
    .targetDataPrototype : &AppCompositeElementDataPrototype?;
};
```

### 6. Doc Comments on Composites and Members

```rupa
/// Maximum allowable deviation
type AbsoluteTolerance = TimeRangeTypeTolerance {
    /// Maximum allowable deviation in duration (in seconds)
    .absolute : TimeValue?;
};
```

Doc comments (`///`) above types and members when documentation exists in XSD.

## Files Affected

- `tools/autosar-converter/schema_model.py` — add doc fields to models
- `tools/autosar-converter/schema_parser.py` — extract docs, fix integer fallback, detect instance-ref
- `tools/autosar-converter/rupa_generator.py` — all formatting changes
- `tools/autosar-converter/tests/` — update tests for new behavior
- `output/autosar-r23-11/*.rupa` — regenerated output
