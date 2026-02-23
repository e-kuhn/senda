# Design: AUTOSAR XSD Schema to Rupa Domain Converter

**Date**: 2026-02-17
**Status**: Approved
**Purpose**: Design validation — stress-test the Rupa type definition syntax against a real-world 1000+ type metamodel

---

## Overview

A Python script that parses an AUTOSAR XSD schema file and generates a multi-file Rupa domain definition expressing the AUTOSAR metamodel in Rupa's type system. The primary goal is to validate whether Rupa's syntax and type system can faithfully represent a large, complex, real-world schema — and to surface any gaps or friction points.

## Location

```
rupa-spec/tools/autosar-converter/
    converter.py          # Main entry point
    schema_parser.py      # XSD parsing (clean rewrite inspired by autosar-dsl blueprint)
    rupa_generator.py     # Rupa code generation
    name_converter.py     # AUTOSAR name normalization utilities
```

## Input

AUTOSAR XSD schema file (e.g., `AUTOSAR_00052.xsd` for R23-11, ~10MB).

The script parses the XSD directly — no dependency on the existing `autosar-dsl` JSON meta-models. The existing `autosar-dsl/meta-model-generator/schema_analyzer.py` serves as a blueprint for the parsing logic but will be rewritten cleanly.

## Output

A directory of Rupa files plus a mapping report:

```
output/autosar-r23-11/
    domain.rupa             # Domain declaration + imports
    primitives.rupa         # ::string / ::integer / ::float restricted types
    enums.rupa              # ::enum type definitions
    base-types.rupa         # Abstract composite types (ArObject, Referrable, etc.)
    composites-a-e.rupa     # Concrete composite types, alphabetical chunks
    composites-f-n.rupa
    composites-o-z.rupa
    mapping-report.md       # Gaps, decisions, statistics, errors
```

## Usage

```
python tools/autosar-converter/converter.py \
    /path/to/AUTOSAR_00052.xsd \
    output/autosar-r23-11/
```

## Architecture

### Pipeline

```
XSD file
  -> Parse XML (ElementTree)
  -> Extract version info from comments
  -> Analyze top-level elements:
       complexTypes, simpleTypes, groups, attributeGroups, root element
  -> Build internal type model (dataclasses)
  -> Flatten group/attributeGroup inheritance into complex types
  -> Truncate unused types
  -> Generate Rupa source files
  -> Generate mapping report
```

### Module Responsibilities

**`schema_parser.py`** — XSD Parsing

- Parses the XSD using `xml.etree.ElementTree`
- Extracts version info (AUTOSAR release, standard version)
- Analyzes all XSD elements and builds an internal model using Python dataclasses
- Extracts names from `mmt.qualifiedName` in appinfo annotations (primary), falls back to XML-tag-to-PascalCase conversion
- Extracts cardinality from `pureMM.minOccurs`/`pureMM.maxOccurs`
- Extracts stereotypes (`atpObject`, `atpMixed`, `atpMixedString`, `atpIdentityContributor`)
- Detects references (members based on `AR:REF` extension base)
- Resolves subtypes enums for reference member type constraints
- Flattens group/attributeGroup inheritance
- Truncates types not reachable from complex types

**`rupa_generator.py`** — Rupa Code Generation

- Takes the parsed schema model and produces Rupa source files
- Splits output by type kind:
  - `domain.rupa` — domain declaration and imports
  - `primitives.rupa` — primitive type definitions with `#[pattern]` and `#[range]`
  - `enums.rupa` — `::enum` type definitions
  - `base-types.rupa` — abstract composite types
  - `composites-*.rupa` — concrete composites in alphabetical chunks
- Generates proper Rupa syntax per the grammar in `spec/appendix-a-grammar.md`
- Flags errors when variant members lack a common base type
- Produces `mapping-report.md`

**`name_converter.py`** — Name Utilities

- AUTOSAR XML tag name to PascalCase (`ABSOLUTE-TOLERANCE` -> `AbsoluteTolerance`)
- Member name camelCase normalization (lowercase first char unless all-caps)
- Any name sanitization needed for Rupa identifier rules

**`converter.py`** — Orchestration

- Argument parsing (schema file path, output directory)
- Calls parser, then generator
- Writes output files

## Type Mapping Rules

### Name Resolution

AUTOSAR XSD elements carry `mmt.qualifiedName` in their appinfo annotations. These provide:
- **Type names**: PascalCase (e.g., `AbsoluteTolerance`)
- **Member names**: camelCase after the dot (e.g., `AbsoluteTolerance.absolute` -> `absolute`)
- **Enum values**: as-written (e.g., `AlignEnum.center` -> `center`)

The converter uses `mmt.qualifiedName` as the primary name source. Fallback: convert XML tag name from `KEBAB-CASE` to `PascalCase`.

Subtypes enum values (which lack appinfo) retain their raw XML form (e.g., `ABSTRACT-ACCESS-POINT`) and are emitted as quoted strings in Rupa.

### Primitive Types

| XSD base type | Rupa M3 supertype |
|---|---|
| `xsd:string` | `::string` |
| `xsd:double` | `::float` |
| `xsd:unsignedInt` | `::integer` with `#[range(>=0)]` |
| `xsd:INTEGER` | `::integer` |

```rupa
#[pattern("[a-zA-Z_][a-zA-Z0-9_]*")]
type CIdentifierSimple = ::string;

type NumericalValueSimple = ::float;

#[range(>=0)]
type PositiveIntegerSimple = ::integer;

type StringSimple = ::string;
```

### Enumerations

Regular enums (values from `mmt.qualifiedName`):
```rupa
type AlignEnumSimple = ::enum(center, justify, left, right);
```

Subtypes enums (values from XML `value` attribute — hyphenated, quoted):
```rupa
type AbstractAccessPointSubtypesEnum = ::enum(
    "ABSTRACT-ACCESS-POINT",
    "ASYNCHRONOUS-SERVER-CALL-POINT",
    "ASYNCHRONOUS-SERVER-CALL-RESULT-POINT"
);
```

### Composite Types

Basic members:
```rupa
type AbsoluteTolerance = {
    .checksum : StringSimple?;
    .timestamp : DateSimple?;
    .absolute : TimeValue?;
};
```

Cardinality mapping:

| AUTOSAR | Rupa |
|---|---|
| min:0, max:1 | `Type?` |
| min:1, max:1 | `Type` |
| min:0, max:unbounded | `Type*` |
| min:1, max:unbounded | `Type+` |
| min:N, max:M | `Type{N,M}` |

### Reference Members

```rupa
type AccessCount = {
    .accessPoint : &AbstractAccessPoint?;
};
```

Reference members are identified by `AR:REF` extension base in the XSD. The `&` prefix marks the role as a reference in Rupa.

### Abstract Types

Detected via XSD `abstract="true"` attribute on complexType or via group definitions (which are always abstract):

```rupa
#[abstract]
type ArObject = {
    .checksum : StringSimple?;
    .timestamp : DateSimple?;
};
```

### Identity Contributors

Detected via `atpIdentityContributor` stereotype in appinfo:

```rupa
type ArPackage = {
    #[id]
    .shortName : IdentifierSimple;
    .element : ArElement*;
    .arPackage : ArPackage*;
};
```

For compound identity (multiple contributors), `#[id(0)]`, `#[id(1)]`, etc. are used.

### Ordered/Mixed Types

Detected via `atpMixed` or `atpMixedString` stereotypes:

```rupa
#[ordered]
type DocumentationBlock = {
    .. : StringSimple*;
    .traceable : Traceable*;
};
```

- `atpMixedString` types get an unnamed role (`..`) for text content
- `atpMixed` types get `#[ordered]` for cross-role ordering
- Both get `#[ordered]` on the type

### Variant Members (Multiple Accepted Types)

When a member accepts multiple types (XSD `<xsd:choice>` with multiple `<xsd:element>` children), the converter determines the common base type. If all accepted types share a common ancestor in the flattened AUTOSAR type hierarchy, that ancestor is used as the role type.

If no common base type exists, this is flagged as an **error** in the mapping report.

### Root Type

The XSD root element maps to `#[root]` annotation:

```rupa
#[root]
type Autosar = {
    .arPackage : ArPackage*;
};
```

## Gap Handling

The mapping report (`mapping-report.md`) will document:

1. **Statistics**: type counts by category, file sizes
2. **Errors**: variant members where accepted types share no common base
3. **Decisions**: XSD-to-Rupa mapping rules applied
4. **Observations**: patterns that stress the Rupa syntax, readability notes

## Key Constraint

Agents implementing this plan **must read `spec/appendix-a-grammar.md` and `spec/04-declarations.md`** before writing the Rupa code generator, to ensure exact syntactic correctness.

## Blueprint Reference

The existing Python code at `/Users/ekuhn/CLionProjects/autosar-dsl/meta-model-generator/` serves as a blueprint:
- `schema_analyzer.py` — XSD parsing logic (1118 lines)
- `regex_analyzer.py` — regex pattern normalization (363 lines)
- `json_generator.py` — output generation pattern (70 lines)

The new implementation should use this as reference but improve on it with:
- Python dataclasses for the internal model
- Cleaner separation of concerns
- Better error collection (list of warnings/errors, not print statements)
- Type hints throughout
