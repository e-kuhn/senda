# Unified Type System for AUTOSAR

**Date:** 2026-02-23
**Status:** Implemented
**Use case:** [`docs/use-cases/08-unified-type-system.md`](../use-cases/../../../docs/use-cases/08-unified-type-system.md)

## Problem

AUTOSAR's type system splits every data type into three separate artifacts:

1. **ApplicationDataType (ADT)** — physical meaning (units, ranges, computation methods)
2. **ImplementationDataType (IDT)** — binary representation (base types, byte ordering, bit sizes)
3. **DataTypeMap** — links an ADT to an IDT within a DataTypeMappingSet

This triple-artifact design exists for good reasons (portability across ECUs, separation of physical and binary concerns), but most projects don't need this flexibility. Users just want one type.

## Solution

Create a **unified type system** as a derived AUTOSAR domain that collapses the ADT/IDT/DataTypeMap split into single type declarations. A set of transformation functions then **dissolves** unified types back into the full AUTOSAR triple when needed.

The value proposition: write 4 lines of Rupa, get the equivalent of ~40 lines of ARXML per type.

## Architecture

### Domain Derivation Chain

```
autosar-2411          (generated from XSD by schema converter)
    |
    = (domain derivation with assignment — copies full type system)
    |
autosar-2411-unified  (adds simplified base types on top)
    |
    = (user derives their domain)
    |
vehicle-v1            (user's model)
```

### M2 Layer: Simplified Base Types

The unified domain derives from the full AUTOSAR domain and adds base types that carry conversion parameters as roles. M3 primitives cannot be used directly in M2 composite roles — M2 aliases are required.

```rupa
domain autosar-2411-unified = autosar-2411;

// M2 aliases for M3 primitives
type Factor = ::float;
type Offset = ::float;

// Base type for linear-converted quantities (AUTOSAR LINEAR CompuMethod)
type LinearQuantity = {
    .factor: Factor;
    .offset: Offset;
};

// Pass-through quantities (AUTOSAR IDENTICAL CompuMethod)
// No conversion parameters needed
type IdenticalQuantity = {};
```

Enums (`::enum(...)`) dissolve naturally into TEXTTABLE CompuMethods using ordinal positions. No special base type needed.

### M2 Layer: User Type Definitions

Users derive types from the base types, inheriting the conversion roles:

```rupa
domain vehicle-v1 = autosar-2411-unified;

// Primitive types — inherit .factor and .offset from LinearQuantity
type VehicleSpeed = LinearQuantity;
type EngineTemp = LinearQuantity;

// Enum type — ordinal mapping inferred
type GearPosition = ::enum(Park, Reverse, Neutral, Drive);

// Composite type — dissolution follows from member types
type VehicleData = {
    .speed: VehicleSpeed;
    .engineTemp: EngineTemp;
    .gear: GearPosition;
};
```

### M1 Layer: Scaling Templates and Instances

Values (factor, offset) cannot be assigned at the M2 level — only at M1 (instantiation). Scaling templates are created as variables using `let`, then copied into instances via the `from` keyword:

```rupa
// Scaling templates
let speed_scaling = LinearQuantity {
    .factor = 0.01;
    .offset = 0.0;
};

let temp_scaling = LinearQuantity {
    .factor = 1.0;
    .offset = -40.0;
};

// Instances use `from` to copy scaling values
VehicleSpeed vehicle_speed from speed_scaling {};
EngineTemp engine_temp from temp_scaling {};
```

### Transformation Functions

Overloaded `dissolve` functions handle each type category. One unified type produces multiple AUTOSAR artifacts in a single function call. The orchestrator sets up the target ARPackage structure, then iterates source types.

The transformation creates and places artifacts into the appropriate ARPackages:
- `ApplicationDataTypes/` — for ADTs
- `ImplementationDataTypes/` — for IDTs
- `CompuMethods/` — for CompuMethods
- A `DataTypeMappingSet` — for DataTypeMaps

**Overloads by type category:**

| Input Type | CompuMethod Category | Generated Artifacts |
|---|---|---|
| `LinearQuantity` subtypes | LINEAR | ADT + IDT + CompuMethod + DataTypeMap |
| `IdenticalQuantity` subtypes | IDENTICAL | ADT + IDT + DataTypeMap (no CompuMethod) |
| `::enum(...)` types | TEXTTABLE | ADT + IDT + CompuMethod + DataTypeMap |
| Composite types (`{ ... }`) | — | ApplicationRecordDataType + STRUCTURE IDT + per-element DataTypeMaps |

**Convention-based inference for implementation types:**

| Unified Type | Range / Resolution | Inferred Platform Type |
|---|---|---|
| LinearQuantity, factor=0.01, range 0..655.35 | 65536 discrete values | uint16 |
| LinearQuantity, factor=1.0, range -40..215 | 256 discrete values | uint8 |
| Enum with 4 variants | 4 values | uint8 |
| IdenticalQuantity, float | — | float64 |

**Structure of the dissolve functions:**

1. **Orchestrator** — creates target ARPackage structure, iterates source types, dispatches to overloads
2. **LinearQuantity overload** — creates CompuMethod (LINEAR), ADT, IDT (inferred base type), DataTypeMap; places each in the correct package via `+=`
3. **Enum overload** — creates CompuMethod (TEXTTABLE) with ordinal-to-text scales, ADT, IDT, DataTypeMap
4. **Composite overload** — recurses into member types, creates ApplicationRecordDataType and STRUCTURE IDT, element-level DataTypeMaps

> **IMPORTANT:** The Rupa code examples in this document show intent and structure only. The actual syntax must be validated and corrected against the Rupa grammar (RupaParser.g4, RupaLexer.g4) and specification (design/current/) during implementation. Key areas requiring syntax review:
> - Function declaration and parameter syntax
> - Object construction and inline creation
> - Path navigation and reference syntax
> - Pipe/map operations
> - Assignment operators (`=`, `+=`) on paths

## Demonstration Output

The use case demonstration shows three layers:

### 1. Input (what the user writes)

~15 lines of unified Rupa covering type definitions and scaling templates.

### 2. Dissolved Rupa Model (generated, primary output)

The full AUTOSAR model in Rupa format, showing:
- ApplicationPrimitiveDataType instances in their ARPackage
- ImplementationDataType instances with inferred platform base types
- CompuMethod instances (LINEAR, TEXTTABLE)
- DataTypeMappingSet with DataTypeMaps linking ADTs to IDTs
- ApplicationRecordDataType and STRUCTURE IDTs for composites

This is the readable output that demonstrates the dissolution.

### 3. ARXML Snippet (for contrast)

A short excerpt showing one type (e.g., VehicleSpeed) in ARXML — ApplicationPrimitiveDataType + CompuMethod + ImplementationDataType. ~40 lines of XML for what was 4 lines of unified Rupa. Demonstrates the verbosity reduction.

## Full Type Coverage

| AUTOSAR Category | Unified Representation | Dissolution |
|---|---|---|
| VALUE (primitive, LINEAR) | `LinearQuantity` subtype | ADT + IDT + LINEAR CompuMethod + DataTypeMap |
| VALUE (primitive, IDENTICAL) | `IdenticalQuantity` subtype | ADT + IDT + DataTypeMap |
| BOOLEAN | `::boolean` alias | ADT + IDT (boolean platform type) + DataTypeMap |
| VALUE (enum, TEXTTABLE) | `::enum(...)` | ADT + IDT + TEXTTABLE CompuMethod + DataTypeMap |
| STRUCTURE (record) | Composite `{ .roles }` | ApplicationRecordDataType + STRUCTURE IDT + element maps |
| ARRAY | Multi-valued role (`*`, `+`, `{m,n}`) | ApplicationArrayDataType + ARRAY IDT + element map |
| CURVE | TBD | ApplicationPrimitiveDataType (CURVE) + axis descriptions |
| MAP | TBD | ApplicationPrimitiveDataType (MAP) + axis descriptions |
| SCALE_LINEAR | Multiple `LinearQuantity` segments | ADT + IDT + SCALE_LINEAR CompuMethod |
| SCALE_LINEAR_AND_TEXTTABLE | Mixed linear + enum | ADT + IDT + SCALE_LINEAR_AND_TEXTTABLE CompuMethod |
| BITFIELD_TEXTTABLE | TBD | ADT + IDT + BITFIELD_TEXTTABLE CompuMethod |
| RAT_FUNC | TBD — may need additional base type | ADT + IDT + RAT_FUNC CompuMethod |

CURVE, MAP, BITFIELD_TEXTTABLE, and RAT_FUNC require further design work.

## AUTOSAR Spec References

- **DataTypeMappingSet**: AUTOSAR_CP_TPS_SoftwareComponentTemplate, Data Description chapter
- **CompuMethod categories**: LINEAR, TEXTTABLE, SCALE_LINEAR, IDENTICAL, RAT_FUNC, BITFIELD_TEXTTABLE, SCALE_LINEAR_AND_TEXTTABLE
- **Platform types**: AUTOSAR_CP_SWS_PlatformTypes (uint8, uint16, uint32, sint8, sint16, sint32, float32, float64, boolean)
- **DataTypeMap**: Maps ApplicationDataType to AbstractImplementationDataType
- **Senda Pattern 13**: `docs/patterns/13-data-type-mapping.md` — detailed AUTOSAR-to-Rupa mapping for the data type system
