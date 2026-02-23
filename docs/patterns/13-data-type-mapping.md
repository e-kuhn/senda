# Pattern 13: Data Type Mapping

This pattern maps AUTOSAR's `DataTypeMappingSet` -- which bridges
`ApplicationDataType` and `ImplementationDataType` via `DataTypeMap` entries,
with `CompuMethod` categories (LINEAR, TEXTTABLE, SCALE_LINEAR_AND_TEXTTABLE,
IDENTICAL, RAT_FUNC) governing the physical-to-internal conversion -- onto
Rupa's `#[transform]` functions, expression builtins, and domain derivation.
It demonstrates how the two-type-system architecture of AUTOSAR software
components collapses into Rupa's single domain model with explicit
transformation functions bridging the gap.

---

## AUTOSAR Concept

### The Application/Implementation Split

AUTOSAR software component development uses two parallel type systems for data
prototypes:

**ApplicationDataType (ADT)**: Describes the *physical meaning* of data.
Typed with units, computation methods, and data constraints that express
engineering quantities (e.g., "vehicle speed in km/h, range 0..300, resolution
0.01").

**ImplementationDataType (IDT)**: Describes the *binary representation* in
the target programming language. Typed with base types, byte ordering, and
bit sizes (e.g., "uint16, big-endian, 16 bits").

The `DataTypeMappingSet` connects these two worlds. It aggregates `DataTypeMap`
entries, each pairing one `ApplicationDataType` with one
`AbstractImplementationDataType`. The RTE generator consumes these mappings to
produce code that converts between physical and internal representations.

```
DataTypeMappingSet                       -- container for all mappings
  +dataTypeMap: DataTypeMap*             -- one per ADT/IDT pair
    .applicationDataType  -> ADT         -- physical-level type
    .implementationDataType -> IDT       -- binary-level type
  +modeRequestTypeMap: ModeRequestTypeMap*
    .modeGroup -> ModeDeclarationGroup
    .implementationDataType -> IDT
```

### Who References a DataTypeMappingSet

Several AUTOSAR meta-classes hold references to `DataTypeMappingSet`:

- **InternalBehavior** -- component's code-RTE boundary; all data types for
  that component must be uniquely resolvable at the implementation level.
- **CompositionSwComponentType** -- for ComSpec definitions at composition level.
- **ParameterSwComponentType** -- same rationale as InternalBehavior but for
  parameter components that lack an InternalBehavior.
- **NvBlockDescriptor** -- generates code from data types without an
  InternalBehavior association.

The mapping is *not* embedded in the type itself. It is a separate artifact
maintained in its own `ARPackage` (recommended package name:
`DataTypeMappingSets`). This indirection allows the same `ApplicationDataType`
to map to different `ImplementationDataType` instances on different ECU
platforms without modifying the VFB model.

### CompuMethod: The Conversion Specification

The bridge between physical and internal values is the `CompuMethod`, attached
to an `ApplicationPrimitiveDataType` via `SwDataDefProps.compuMethod`. Its
`category` attribute determines the conversion algorithm:

| Category | Meaning | Key Properties |
|----------|---------|----------------|
| IDENTICAL | Pass-through, no conversion | Unit only (optional) |
| LINEAR | `physical = (offset + factor * internal) / divisor` | Exactly 1 `CompuScale` with 2 numerator coeffs + 1 denominator coeff |
| SCALE_LINEAR | Piecewise linear segments | Multiple `CompuScale` entries with `lowerLimit`/`upperLimit` bounds |
| RAT_FUNC | Rational function (polynomial ratio) | Arbitrary-degree numerator/denominator polynomials |
| TEXTTABLE | Integer-to-enumeration mapping | `CompuScale` entries with `compuConst.vt` text values |
| BITFIELD_TEXTTABLE | Masked bit-to-text mapping | `CompuScale` entries with `mask` + `compuConst.vt` |
| SCALE_LINEAR_AND_TEXTTABLE | Mixed numeric + enumeration scales | Some scales carry coefficients, others carry text |

**LINEAR detail**: The `CompuScale` contains `CompuRationalCoeffs` with:
- `compuNumerator.v[0]` = offset, `compuNumerator.v[1]` = factor
- `compuDenominator.v[0]` = divisor

The formula is: `physical = (v_num[0] + v_num[1] * internal) / v_den[0]`.

**TEXTTABLE detail**: Each `CompuScale` maps a numeric range
(`lowerLimit`..`upperLimit`) to a constant text string (`compuConst.vt`).
The `compuPhysToInternal` direction may also exist for bidirectional lookup.

### ARXML Example -- DataTypeMappingSet with LINEAR CompuMethod

```xml
<!-- CompuMethod: raw uint16 -> physical speed in km/h -->
<COMPU-METHOD>
  <SHORT-NAME>CM_VehicleSpeed</SHORT-NAME>
  <CATEGORY>LINEAR</CATEGORY>
  <UNIT-REF DEST="UNIT">/Units/kmh</UNIT-REF>
  <COMPU-INTERNAL-TO-PHYS>
    <COMPU-SCALES>
      <COMPU-SCALE>
        <LOWER-LIMIT INTERVAL-TYPE="CLOSED">0</LOWER-LIMIT>
        <UPPER-LIMIT INTERVAL-TYPE="CLOSED">65535</UPPER-LIMIT>
        <COMPU-RATIONAL-COEFFS>
          <COMPU-NUMERATOR>
            <V>0</V>       <!-- offset -->
            <V>0.01</V>    <!-- factor -->
          </COMPU-NUMERATOR>
          <COMPU-DENOMINATOR>
            <V>1</V>       <!-- divisor -->
          </COMPU-DENOMINATOR>
        </COMPU-RATIONAL-COEFFS>
      </COMPU-SCALE>
    </COMPU-SCALES>
  </COMPU-INTERNAL-TO-PHYS>
</COMPU-METHOD>

<!-- ApplicationPrimitiveDataType referencing the CompuMethod -->
<APPLICATION-PRIMITIVE-DATA-TYPE>
  <SHORT-NAME>VehicleSpeed_Phys</SHORT-NAME>
  <CATEGORY>VALUE</CATEGORY>
  <SW-DATA-DEF-PROPS>
    <SW-DATA-DEF-PROPS-VARIANTS>
      <SW-DATA-DEF-PROPS-CONDITIONAL>
        <COMPU-METHOD-REF DEST="COMPU-METHOD">/CompuMethods/CM_VehicleSpeed</COMPU-METHOD-REF>
        <DATA-CONSTR-REF DEST="DATA-CONSTR">/DataConstraints/DC_VehicleSpeed</DATA-CONSTR-REF>
      </SW-DATA-DEF-PROPS-CONDITIONAL>
    </SW-DATA-DEF-PROPS-VARIANTS>
  </SW-DATA-DEF-PROPS>
</APPLICATION-PRIMITIVE-DATA-TYPE>

<!-- ImplementationDataType -->
<IMPLEMENTATION-DATA-TYPE>
  <SHORT-NAME>VehicleSpeed_Impl</SHORT-NAME>
  <CATEGORY>VALUE</CATEGORY>
  <SW-DATA-DEF-PROPS>
    <SW-DATA-DEF-PROPS-VARIANTS>
      <SW-DATA-DEF-PROPS-CONDITIONAL>
        <BASE-TYPE-REF DEST="SW-BASE-TYPE">/BaseTypes/uint16</BASE-TYPE-REF>
      </SW-DATA-DEF-PROPS-CONDITIONAL>
    </SW-DATA-DEF-PROPS-VARIANTS>
  </SW-DATA-DEF-PROPS>
</IMPLEMENTATION-DATA-TYPE>

<!-- DataTypeMappingSet -->
<DATA-TYPE-MAPPING-SET>
  <SHORT-NAME>VehicleDtMappings</SHORT-NAME>
  <DATA-TYPE-MAPS>
    <DATA-TYPE-MAP>
      <APPLICATION-DATA-TYPE-REF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">
        /AppDataTypes/VehicleSpeed_Phys</APPLICATION-DATA-TYPE-REF>
      <IMPLEMENTATION-DATA-TYPE-REF DEST="IMPLEMENTATION-DATA-TYPE">
        /ImplDataTypes/VehicleSpeed_Impl</IMPLEMENTATION-DATA-TYPE-REF>
    </DATA-TYPE-MAP>
  </DATA-TYPE-MAPS>
</DATA-TYPE-MAPPING-SET>
```

### ARXML Example -- TEXTTABLE CompuMethod

```xml
<COMPU-METHOD>
  <SHORT-NAME>CM_GearPosition</SHORT-NAME>
  <CATEGORY>TEXTTABLE</CATEGORY>
  <COMPU-INTERNAL-TO-PHYS>
    <COMPU-SCALES>
      <COMPU-SCALE>
        <LOWER-LIMIT INTERVAL-TYPE="CLOSED">0</LOWER-LIMIT>
        <UPPER-LIMIT INTERVAL-TYPE="CLOSED">0</UPPER-LIMIT>
        <COMPU-CONST><VT>Park</VT></COMPU-CONST>
      </COMPU-SCALE>
      <COMPU-SCALE>
        <LOWER-LIMIT INTERVAL-TYPE="CLOSED">1</LOWER-LIMIT>
        <UPPER-LIMIT INTERVAL-TYPE="CLOSED">1</UPPER-LIMIT>
        <COMPU-CONST><VT>Reverse</VT></COMPU-CONST>
      </COMPU-SCALE>
      <COMPU-SCALE>
        <LOWER-LIMIT INTERVAL-TYPE="CLOSED">2</LOWER-LIMIT>
        <UPPER-LIMIT INTERVAL-TYPE="CLOSED">2</UPPER-LIMIT>
        <COMPU-CONST><VT>Neutral</VT></COMPU-CONST>
      </COMPU-SCALE>
      <COMPU-SCALE>
        <LOWER-LIMIT INTERVAL-TYPE="CLOSED">3</LOWER-LIMIT>
        <UPPER-LIMIT INTERVAL-TYPE="CLOSED">3</UPPER-LIMIT>
        <COMPU-CONST><VT>Drive</VT></COMPU-CONST>
      </COMPU-SCALE>
    </COMPU-SCALES>
  </COMPU-INTERNAL-TO-PHYS>
</COMPU-METHOD>
```

---

## Rupa Mapping

### Two Domains, One Transformation

In Rupa, the application-level and implementation-level type systems are
modeled as **separate domains**. The `DataTypeMappingSet` becomes a set of
`#[transform]` functions that bridge these domains. The `CompuMethod` is not
a separate data object -- its conversion logic is expressed directly in the
transformation function body using Rupa's expression builtins.

This is a direct application of Rupa's cross-domain transformation mechanism
(Section 8.2): the function signature declares the source and target types
from different domains, and the body performs the conversion.

### CompuMethod Categories as Expression Logic

Each `CompuMethod` category maps to a specific expression pattern inside
a `#[transform]` function:

| CompuMethod Category | Rupa Expression Pattern |
|---------------------|------------------------|
| IDENTICAL | Direct assignment (`.value = src.value`) |
| LINEAR | Arithmetic: `src.raw * factor + offset` using `to_float()`, `round()` |
| TEXTTABLE | Conditional chain or `map` lookup |
| SCALE_LINEAR_AND_TEXTTABLE | Combined conditional: linear for numeric ranges, text lookup otherwise |
| BITFIELD_TEXTTABLE | Bitwise masking (if domain provides bit ops) or `#[transform]` per mask |

### Domain Derivation for Platform Variants

Because `DataTypeMappingSet` is an *external artifact* in AUTOSAR (not embedded
in the types), different ECU platforms can map the same ADT to different IDTs.
In Rupa, this maps to **domain derivation** (`domain D = B;`): a
platform-specific domain derives from the base application domain and provides
its own `#[transform]` functions targeting the platform's implementation domain.

```rupa
// Base application domain -- shared across all platforms
domain app-vehicle-v1;

type VehicleSpeed = float;
type GearPosition = enum { Park, Reverse, Neutral, Drive };

// Platform-specific implementation domain
domain impl-mpc5748g;

#[range(0, 65535)]
type VehicleSpeed_Raw = integer;

#[range(0, 3)]
type GearPosition_Raw = integer;
```

---

## Worked Example

### Step 1: Application Domain Types

```rupa
// file: domains/app-vehicle/types.rupa
domain app-vehicle-v1;

#[range(0.0, 655.35)]
type VehicleSpeed = float;

#[range(-40.0, 215.0)]
type EngineTemp = float;

enum GearPosition {
    Park,
    Reverse,
    Neutral,
    Drive,
};

type VehicleData = {
    #[id(0)]
    .name: Name;
    .speed: VehicleSpeed;
    .engineTemp: EngineTemp;
    .gear: GearPosition;
};
```

### Step 2: Implementation Domain Types

```rupa
// file: domains/impl-mpc5748g/types.rupa
domain impl-mpc5748g;

// Raw uint16 -- factor 0.01, offset 0
#[range(0, 65535)]
type VehicleSpeed_Raw = integer;

// Raw uint8 -- factor 1.0, offset 40
#[range(0, 255)]
type EngineTemp_Raw = integer;

// Raw uint8 -- direct enum encoding
#[range(0, 3)]
type GearPosition_Raw = integer;

type VehicleData_Impl = {
    #[id(0)]
    .name: Name;
    .speed: VehicleSpeed_Raw;
    .engineTemp: EngineTemp_Raw;
    .gear: GearPosition_Raw;
};
```

### Step 3: Transformation Functions (the DataTypeMappingSet)

```rupa
// file: transforms/vehicle-dt-mapping.rupa
// This file IS the Rupa equivalent of a DataTypeMappingSet.
// Each #[transform] function corresponds to one DataTypeMap entry
// with the CompuMethod logic embedded in the function body.

using domain app-vehicle-v1 as app;
using domain impl-mpc5748g as impl;

// --- LINEAR: physical = raw * 0.01 + 0 ---
#[transform]
let map_speed(src: impl::VehicleSpeed_Raw): app::VehicleSpeed =
    to_float(src) * 0.01;

// --- LINEAR: physical = raw * 1.0 + (-40) ---
#[transform]
let map_temp(src: impl::EngineTemp_Raw): app::EngineTemp =
    to_float(src) - 40.0;

// --- TEXTTABLE: integer -> enum ---
#[transform]
let map_gear(src: impl::GearPosition_Raw): app::GearPosition =
    if src == 0 then Park
    else if src == 1 then Reverse
    else if src == 2 then Neutral
    else Drive;

// --- Composite: orchestrate sub-transforms ---
#[transform]
let map_vehicle(src: impl::VehicleData_Impl): app::VehicleData =
    app::VehicleData {
        .name = src.name;
        ::transform(src.speed, .speed);
        ::transform(src.engineTemp, .engineTemp);
        ::transform(src.gear, .gear);
    };
```

### Step 4: Reverse Direction (Encode to Implementation)

For generating implementation values from application data (the inverse
mapping), separate `#[transform]` functions provide the reverse conversion:

```rupa
// file: transforms/vehicle-dt-mapping-inverse.rupa
using domain impl-mpc5748g as impl;
using domain app-vehicle-v1 as app;

// --- LINEAR inverse: raw = physical / 0.01 ---
#[transform]
let encode_speed(src: app::VehicleSpeed): impl::VehicleSpeed_Raw =
    round(src / 0.01);

// --- LINEAR inverse: raw = physical + 40 ---
#[transform]
let encode_temp(src: app::EngineTemp): impl::EngineTemp_Raw =
    round(src + 40.0);

// --- TEXTTABLE inverse: enum -> integer ---
#[transform]
let encode_gear(src: app::GearPosition): impl::GearPosition_Raw =
    if src == Park then 0
    else if src == Reverse then 1
    else if src == Neutral then 2
    else 3;

#[transform]
let encode_vehicle(src: app::VehicleData): impl::VehicleData_Impl =
    impl::VehicleData_Impl {
        .name = src.name;
        ::transform(src.speed, .speed);
        ::transform(src.engineTemp, .engineTemp);
        ::transform(src.gear, .gear);
    };
```

### Structural Comparison

| Concern | ARXML | Rupa |
|---------|-------|------|
| Mapping container | `DataTypeMappingSet` ARElement | Transformation file with `#[transform]` functions |
| Individual mapping | `DataTypeMap` with two refs | `#[transform]` function signature (source -> target) |
| Conversion formula | `CompuMethod` + `CompuRationalCoeffs` | Arithmetic expression in function body |
| Text table | `CompuScale` with `compuConst.vt` entries | `if/then/else` chain or enum matching |
| Bidirectional mapping | Implicit from `compuPhysToInternal` + `compuInternalToPhys` | Two separate `#[transform]` functions (forward + inverse) |
| Platform variability | Different `DataTypeMappingSet` per context | Different transformation files per derived domain |
| Mapping scope | Referenced by `InternalBehavior`, `CompositionSwComponentType` | Imported into compilation scope; compiler discovers via `#[transform]` |
| Type compatibility check | Tooling validates ADT/IDT compatibility | Compiler type-checks transform function signature |

---

## Edge Cases

### SCALE_LINEAR_AND_TEXTTABLE (Mixed Conversion)

The most complex `CompuMethod` category combines numeric linear segments with
discrete text-table entries. Each `CompuScale` is either linear (has
`CompuRationalCoeffs`) or textual (has `compuConst.vt`). In ARXML, scales
carry `lowerLimit`/`upperLimit` to partition the internal value range.

In Rupa, this maps to a conditional transform that dispatches on value range:

```rupa
// SCALE_LINEAR_AND_TEXTTABLE: 0..253 is linear speed, 254=Error, 255=NotAvail
#[transform]
let map_speed_with_status(src: impl::SpeedWithStatus_Raw): app::SpeedOrStatus =
    if src >= 0 && src <= 253 then
        app::SpeedOrStatus { .kind = Measured; .speed = to_float(src) * 0.01; }
    else if src == 254 then
        app::SpeedOrStatus { .kind = Error; }
    else
        app::SpeedOrStatus { .kind = NotAvailable; };
```

This is where the Rupa approach gains clarity over ARXML: the branching logic
that is implicit in the scale partitioning of `CompuMethod` becomes an explicit
conditional expression. No tooling needs to reverse-engineer scale boundaries
to understand the conversion.

### One-to-Many Mappings (Composite Types)

An `ApplicationCompositeDataType` (record or array) maps to an
`ImplementationDataType` with category STRUCTURE or ARRAY. The
`DataTypeMappingSet` carries one `DataTypeMap` for the composite, but the
element-level mappings are determined by following the `subElement` structure.

In Rupa, composite mapping is naturally expressed via nested `::transform`
calls. The composite transform orchestrates; the element transforms convert:

```rupa
#[transform]
let map_record(src: impl::SensorPack_Impl): app::SensorPack =
    app::SensorPack {
        .name = src.name;
        // Each sub-element dispatches to its own #[transform]
        ::transform(src.speed, .speed);
        ::transform(src.temperature, .temperature);
        ::transform(src.status, .status);
    };
```

### No Mapping Required (IDENTICAL Category)

When the `CompuMethod` category is IDENTICAL (or no `CompuMethod` is
referenced), the application value equals the internal value. If both domains
define the type identically, Rupa's default transform strategy auto-maps
without an explicit `#[transform]` function (per Section 8.2: "Type identical
in both domains -> Auto-map, traverse children").

If the types differ in name but not in structure, a minimal transform is still
required:

```rupa
#[transform]
let map_counter(src: impl::Counter_Raw): app::Counter = src;
```

### ModeRequestTypeMap

`DataTypeMappingSet` also aggregates `ModeRequestTypeMap`, which pairs a
`ModeDeclarationGroup` with an `ImplementationDataType`. This is a separate
concern from data type mapping -- it allows mode information to travel through
standard sender-receiver communication. In Rupa, mode groups would be modeled
as enum types, and the mapping follows the same TEXTTABLE pattern:

```rupa
#[transform]
let map_mode(src: impl::EcuMode_Raw): app::EcuMode =
    if src == 0 then Startup
    else if src == 1 then Run
    else if src == 2 then PostRun
    else Shutdown;
```

### Precision Loss in LINEAR Conversion

LINEAR conversions between float application types and integer implementation
types involve rounding. The inverse conversion (`physical -> raw`) must choose
a rounding strategy. AUTOSAR does not mandate a specific rounding mode; it is
implementation-defined.

In Rupa, the `round()`, `floor()`, `ceil()`, and `truncate()` builtins make
the rounding strategy explicit:

```rupa
// Explicit rounding -- no ambiguity
#[transform]
let encode_speed(src: app::VehicleSpeed): impl::VehicleSpeed_Raw =
    round(src / 0.01);           // half-to-even (banker's rounding)

// Alternative: floor for conservative truncation
#[transform]
let encode_speed_floor(src: app::VehicleSpeed): impl::VehicleSpeed_Raw =
    floor(src / 0.01);
```

This is a concrete improvement over ARXML, where the rounding behavior is left
to the RTE generator and may vary across vendors.

### DataPrototypeMapping with TextTableMapping

Beyond `DataTypeMappingSet`, AUTOSAR uses `DataPrototypeMapping` with
`TextTableMapping` for interface-level semantic adaptation (e.g., when two
components use different enumeration encodings for the same concept). The
`TextTableMapping` contains `TextTableValuePair` entries mapping `firstValue`
to `secondValue`.

In Rupa, this is a standard `#[transform]` between two domain-specific enum
types. No special mechanism is needed -- the same pattern applies:

```rupa
#[transform]
let adapt_status(src: sender::DiagStatus): receiver::DiagStatus =
    if src == sender::DiagStatus.OK then receiver::DiagStatus.Pass
    else if src == sender::DiagStatus.NOK then receiver::DiagStatus.Fail
    else receiver::DiagStatus.Unknown;
```

---

## Design Reference

- **Transformation language** (`design/current/08-transformation/transformation-language.md`):
  `#[transform]` functions as the mapping mechanism; cross-domain file structure
  with `using domain X as alias;`; `::transform(source, target)` for
  sub-transformation delegation; default transformation strategy for identical
  types; multi-phase transforms for cross-references (Phase 2 with `::targets`).

- **Expression builtins** (`design/current/06-extensibility/expression-builtins-reference.md`):
  `to_float()`, `to_integer()` for numeric conversion; `round()`, `floor()`,
  `ceil()`, `truncate()` for controlled rounding; `to_enum()` for string-to-enum
  lookup; arithmetic operators for LINEAR formula encoding.

- **Domain mechanism** (`design/current/08-transformation/transformation-language.md`,
  Section 8.1): `domain X;` for domain contribution; `domain D = B;` for
  derivation (platform variants); `using domain X as alias;` for cross-domain
  consumption; domain freezing semantics.

- **AUTOSAR specifications**:
  - `AUTOSAR_CP_TPS_SoftwareComponentTemplate` (R25-11), Section "Data Type
    Mapping": `DataTypeMappingSet`, `DataTypeMap` meta-classes, compatibility
    rules between `ApplicationDataType` and `ImplementationDataType`.
  - `AUTOSAR_CP_TPS_SoftwareComponentTemplate` (R25-11), Section "Computation
    Methods": `CompuMethod` category definitions (IDENTICAL, LINEAR,
    SCALE_LINEAR, RAT_FUNC, TEXTTABLE, BITFIELD_TEXTTABLE,
    SCALE_LINEAR_AND_TEXTTABLE), `CompuRationalCoeffs` structure,
    `CompuScale` semantics.
  - `AUTOSAR_CP_TPS_SystemTemplate` (R25-11): `DataPrototypeMapping`,
    `TextTableMapping` for interface-level semantic adaptation.
