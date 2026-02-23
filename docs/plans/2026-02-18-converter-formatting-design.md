# Converter Formatting & Annotation Improvements

**Date:** 2026-02-18
**Status:** Approved
**Scope:** `tools/autosar-converter/` — `converter.py`, `rupa_generator.py`, `schema_parser.py`, `schema_model.py`

## Summary

Nine improvements to the AUTOSAR XSD → Rupa converter, covering output formatting, missing annotations, and data correctness.

## Changes

### 1. CLI: Suppress Alternatives by Default

Add `--alternatives` flag to `converter.py`. **Off by default.** When enabled, generates the `// also:` variant comments on composite members. Pass the flag through to `generate_composite()`.

```
python converter.py <schema.xsd> <output-dir> [--alternatives]
```

### 2. Blank Line Between Roles

Insert a blank line between each member block inside composite type bodies.

Before:
```rupa
    .returnValueProvision : RteApiReturnValueProvisionEnum?;
    .accessPoint : &AbstractAccessPoint?;
```

After:
```rupa
    .returnValueProvision : RteApiReturnValueProvisionEnum?;

    .accessPoint : &AbstractAccessPoint?;
```

### 3–5. Block Comments with Line Wrapping

Switch from `///` line comments to `/** ... */` block comments for all documentation. Multi-line uses `*`-prefixed continuation lines. Wrap at ~80 characters (prefer sentence boundaries), hard break at 100 characters (any whitespace).

**Type-level (no indent):**
```rupa
/**
 * Abstract class indicating an access point
 * from an ExecutableEntity.
 */
#[abstract]
type AbstractAccessPoint = AtpStructureElement {
```

**Member-level (4-space indent, aligned):**
```rupa
    /**
     * This attribute controls the provision of
     * return values for RTE APIs.
     */
    .returnValueProvision : RteApiReturnValueProvisionEnum?;
```

**Single-line (short enough to fit):**
```rupa
/** Short description. */
type Foo = ::string;
```

**Wrapping rules:**
- Target line width: 80 characters (including indent and ` * ` prefix)
- Hard limit: 100 characters — always break before reaching this
- Prefer splitting at end of sentence (`. `)
- Otherwise split at any whitespace

### 6. Integer Range Annotations

Infer `#[range]` from the XSD regex pattern (§13.4 syntax):

- Pattern has no minus sign (`\-` or literal `-` in character class) → `#[range(>=0)]`
- Pattern doesn't match zero (no standalone `0` alternative) → `#[range(>=1)]`
- Pattern has minus sign → no range annotation (signed)
- No pattern at all → infer from XSD base type:
  - `positiveInteger` → `#[range(>=1)]`
  - `unsignedInt` → `#[range(>=0)]`
  - `int` / `long` / `integer` → no range

Examples from the actual XSD:
```rupa
type IntegerSimple = ::integer;              // signed ([\+\-]?), no range
type UnlimitedIntegerSimple = ::integer;     // signed ([\+\-]?), no range

#[range(>=0)]
type PositiveIntegerSimple = ::integer;      // no minus ([\+]?)

#[range(>=0)]
type PositiveUnlimitedIntegerSimple = ::integer;
```

### 7. Subtypes Enum Values → PascalCase

Convert XML kebab-case type names to PascalCase bare identifiers using `xml_to_pascal_case()`.

Before:
```rupa
type AbstractEventSubtypesEnum = ::enum(
    "ABSTRACT-EVENT",
    "ASYNCHRONOUS-SERVER-CALL-RETURNS-EVENT",
);
```

After:
```rupa
type AbstractEventSubtypesEnum = ::enum(
    AbstractEvent,
    AsynchronousServerCallReturnsEvent,
);
```

### 8. Strip Token Values from String Patterns

When `analyze_pattern()` extracts token values into `#[values()]`, also remove those tokens from the pattern string. Currently they remain in both annotations.

Before:
```rupa
#[pattern("[1-9][0-9]*|0[xX][0-9a-fA-F]*|0[bB][0-1]+|0[0-7]*|UNSPECIFIED|UNKNOWN|BOOLEAN|PTR")]
#[values("UNSPECIFIED", "UNKNOWN", "BOOLEAN", "PTR")]
type AlignmentTypeSimple = ::string;
```

After:
```rupa
#[pattern("[1-9][0-9]*|0[xX][0-9a-fA-F]*|0[bB][0-1]+|0[0-7]*")]
#[values("UNSPECIFIED", "UNKNOWN", "BOOLEAN", "PTR")]
type AlignmentTypeSimple = ::string;
```

If stripping all token values leaves an empty pattern, omit `#[pattern()]` entirely.

### 9. Enum & Primitive Documentation

Carry documentation through the export layer for types that currently lose it:

- **Primitives** (`_export_primitive`): pass `prim.doc` through to `ExportPrimitive`
- **Aliases** (`_export_alias`): pass `alias.doc` through to `ExportPrimitive`
- **Aliases parse** (`_analyze_simple_type`): call `get_documentation(elem)` for alias/primitive cases (currently only done for enumerations)
- **Subtypes enums** (`_export_subtypes_enum`): pass `st.doc` through to `ExportEnum`

## Files Affected

| File | Changes |
|------|---------|
| `converter.py` | Add `--alternatives` CLI flag, pass to generator |
| `rupa_generator.py` | Block comments, line wrapping, blank lines between roles, alternatives flag, range annotations, PascalCase enum values, pattern stripping |
| `schema_parser.py` | Documentation extraction for primitives/aliases, range inference, pattern cleaning |
| `schema_model.py` | Possibly add `range_min` field to `ExportPrimitive` (or compute in generator) |

## Testing

Run against `/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd` and verify output in `output/autosar-r23-11/`. Grammar reference: `/Users/ekuhn/CLionProjects/rupa-spec/spec/appendix-a-grammar.md`.
