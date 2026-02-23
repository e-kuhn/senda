# Use Case 03: ECUC Configuration

This use case demonstrates how Rupa handles AUTOSAR's two-layer ECU Configuration
(ECUC) architecture: **definition** (schema) and **value** (data). The definition
layer declares what can be configured -- parameter types, ranges, multiplicities --
while the value layer fills in the actual configuration. In AUTOSAR, these are
`EcucModuleDef` and `EcucModuleConfigurationValues`. In Rupa, they map naturally
onto M2 type definitions (domain contribution) and M1 instances (domain
consumption), eliminating the `DEFINITION-REF` indirection that ARXML requires on
every value element.

---

## Scenario

Configure the **NvM (Non-Volatile Memory Manager)** module for an ECU with three
NVRAM blocks: application data, calibration data, and a diagnostic log. The
configuration must satisfy real AUTOSAR constraints: unique block identifiers,
CRC type required when CRC is enabled, and redundant blocks with exactly two NV
copies.

The NvM module is a good stress test because its definition layer includes
integers with ranges (`NvMNvramBlockIdentifier`: 2..65535), booleans
(`NvMBlockUseCrc`), enumerations (`NvMBlockManagementType`,
`NvMBlockCrcType`), and cross-parameter dependencies (CRC type is meaningful
only when CRC is enabled). These constraint patterns recur across every AUTOSAR
BSW module.

---

## ARXML Baseline

### Module Definition (Schema)

The definition layer specifies what parameters exist and their constraints.
Abbreviated from the full `AUTOSAR_CP_MOD_ECUConfigurationParameters` -- a real
NvMBlockDescriptor has 30+ parameters (ECUC_NvM_00476 through ECUC_NvM_00567).

```xml
<ECUC-MODULE-DEF>
  <SHORT-NAME>NvM</SHORT-NAME>
  <CONTAINERS>
    <ECUC-PARAM-CONF-CONTAINER-DEF>
      <SHORT-NAME>NvMBlockDescriptor</SHORT-NAME>
      <LOWER-MULTIPLICITY>1</LOWER-MULTIPLICITY>
      <UPPER-MULTIPLICITY-INFINITE>true</UPPER-MULTIPLICITY-INFINITE>
      <PARAMETERS>
        <ECUC-INTEGER-PARAM-DEF>
          <SHORT-NAME>NvMNvramBlockIdentifier</SHORT-NAME>
          <LOWER-MULTIPLICITY>1</LOWER-MULTIPLICITY>
          <UPPER-MULTIPLICITY>1</UPPER-MULTIPLICITY>
          <SYMBOLIC-NAME-VALUE>true</SYMBOLIC-NAME-VALUE>
          <MIN>2</MIN>
          <MAX>65535</MAX>
        </ECUC-INTEGER-PARAM-DEF>
        <ECUC-INTEGER-PARAM-DEF>
          <SHORT-NAME>NvMNvBlockLength</SHORT-NAME>
          <LOWER-MULTIPLICITY>1</LOWER-MULTIPLICITY>
          <UPPER-MULTIPLICITY>1</UPPER-MULTIPLICITY>
          <MIN>1</MIN>
          <MAX>65535</MAX>
        </ECUC-INTEGER-PARAM-DEF>
        <ECUC-BOOLEAN-PARAM-DEF>
          <SHORT-NAME>NvMBlockUseCrc</SHORT-NAME>
          <LOWER-MULTIPLICITY>1</LOWER-MULTIPLICITY>
          <UPPER-MULTIPLICITY>1</UPPER-MULTIPLICITY>
          <DEFAULT-VALUE>false</DEFAULT-VALUE>
        </ECUC-BOOLEAN-PARAM-DEF>
        <ECUC-ENUMERATION-PARAM-DEF>
          <SHORT-NAME>NvMBlockCrcType</SHORT-NAME>
          <LOWER-MULTIPLICITY>0</LOWER-MULTIPLICITY>
          <UPPER-MULTIPLICITY>1</UPPER-MULTIPLICITY>
          <LITERALS>
            <ECUC-ENUMERATION-LITERAL-DEF><SHORT-NAME>NVM_CRC8</SHORT-NAME></ECUC-ENUMERATION-LITERAL-DEF>
            <ECUC-ENUMERATION-LITERAL-DEF><SHORT-NAME>NVM_CRC16</SHORT-NAME></ECUC-ENUMERATION-LITERAL-DEF>
            <ECUC-ENUMERATION-LITERAL-DEF><SHORT-NAME>NVM_CRC32</SHORT-NAME></ECUC-ENUMERATION-LITERAL-DEF>
          </LITERALS>
          <DEFAULT-VALUE>NVM_CRC16</DEFAULT-VALUE>
        </ECUC-ENUMERATION-PARAM-DEF>
        <ECUC-ENUMERATION-PARAM-DEF>
          <SHORT-NAME>NvMBlockManagementType</SHORT-NAME>
          <LOWER-MULTIPLICITY>1</LOWER-MULTIPLICITY>
          <UPPER-MULTIPLICITY>1</UPPER-MULTIPLICITY>
          <LITERALS>
            <ECUC-ENUMERATION-LITERAL-DEF><SHORT-NAME>NVM_BLOCK_NATIVE</SHORT-NAME></ECUC-ENUMERATION-LITERAL-DEF>
            <ECUC-ENUMERATION-LITERAL-DEF><SHORT-NAME>NVM_BLOCK_REDUNDANT</SHORT-NAME></ECUC-ENUMERATION-LITERAL-DEF>
            <ECUC-ENUMERATION-LITERAL-DEF><SHORT-NAME>NVM_BLOCK_DATASET</SHORT-NAME></ECUC-ENUMERATION-LITERAL-DEF>
          </LITERALS>
          <DEFAULT-VALUE>NVM_BLOCK_NATIVE</DEFAULT-VALUE>
        </ECUC-ENUMERATION-PARAM-DEF>
        <ECUC-INTEGER-PARAM-DEF>
          <SHORT-NAME>NvMNvBlockNum</SHORT-NAME>
          <LOWER-MULTIPLICITY>1</LOWER-MULTIPLICITY>
          <UPPER-MULTIPLICITY>1</UPPER-MULTIPLICITY>
          <MIN>1</MIN>
          <MAX>255</MAX>
        </ECUC-INTEGER-PARAM-DEF>
      </PARAMETERS>
    </ECUC-PARAM-CONF-CONTAINER-DEF>
  </CONTAINERS>
</ECUC-MODULE-DEF>
```

### Module Values (Data)

Every value element carries a `DEFINITION-REF` pointing back to its definition.
This is the ARXML mechanism for schema conformance -- repeated on every container
and every parameter.

```xml
<ECUC-MODULE-CONFIGURATION-VALUES>
  <SHORT-NAME>NvM</SHORT-NAME>
  <DEFINITION-REF DEST="ECUC-MODULE-DEF">/AUTOSAR/EcucDefs/NvM</DEFINITION-REF>
  <CONTAINERS>
    <ECUC-CONTAINER-VALUE>
      <SHORT-NAME>NvMBlock_AppData</SHORT-NAME>
      <DEFINITION-REF DEST="ECUC-PARAM-CONF-CONTAINER-DEF">
        /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor</DEFINITION-REF>
      <PARAMETER-VALUES>
        <ECUC-NUMERICAL-PARAM-VALUE>
          <DEFINITION-REF DEST="ECUC-INTEGER-PARAM-DEF">
            /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMNvramBlockIdentifier
          </DEFINITION-REF>
          <VALUE>2</VALUE>
        </ECUC-NUMERICAL-PARAM-VALUE>
        <ECUC-NUMERICAL-PARAM-VALUE>
          <DEFINITION-REF DEST="ECUC-INTEGER-PARAM-DEF">
            /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMNvBlockLength
          </DEFINITION-REF>
          <VALUE>128</VALUE>
        </ECUC-NUMERICAL-PARAM-VALUE>
        <ECUC-NUMERICAL-PARAM-VALUE>
          <DEFINITION-REF DEST="ECUC-BOOLEAN-PARAM-DEF">
            /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMBlockUseCrc
          </DEFINITION-REF>
          <VALUE>true</VALUE>
        </ECUC-NUMERICAL-PARAM-VALUE>
        <ECUC-TEXTUAL-PARAM-VALUE>
          <DEFINITION-REF DEST="ECUC-ENUMERATION-PARAM-DEF">
            /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMBlockCrcType
          </DEFINITION-REF>
          <VALUE>NVM_CRC16</VALUE>
        </ECUC-TEXTUAL-PARAM-VALUE>
        <ECUC-TEXTUAL-PARAM-VALUE>
          <DEFINITION-REF DEST="ECUC-ENUMERATION-PARAM-DEF">
            /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMBlockManagementType
          </DEFINITION-REF>
          <VALUE>NVM_BLOCK_NATIVE</VALUE>
        </ECUC-TEXTUAL-PARAM-VALUE>
        <ECUC-NUMERICAL-PARAM-VALUE>
          <DEFINITION-REF DEST="ECUC-INTEGER-PARAM-DEF">
            /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMNvBlockNum
          </DEFINITION-REF>
          <VALUE>1</VALUE>
        </ECUC-NUMERICAL-PARAM-VALUE>
      </PARAMETER-VALUES>
    </ECUC-CONTAINER-VALUE>
  </CONTAINERS>
</ECUC-MODULE-CONFIGURATION-VALUES>
```

That is one block descriptor out of three. The full ARXML for all three blocks
would be roughly 150 lines of XML, with the `DEFINITION-REF` path repeated
identically on every parameter of every block.

---

## Rupa Solution

### M2 Domain Contribution -- NvM Type Definitions

The ECUC definition layer maps to M2 type definitions. Each
`EcucParamConfContainerDef` becomes a composite type. Each `EcucParameterDef`
becomes a typed role with constraints encoded via `#[range]` annotations and
`enum` types. The `DEFINITION-REF` from the ARXML value layer is eliminated
entirely -- an instance of a type IS the thing conforming to its definition.

```rupa
// file: domains/ecuc-nvm/types.rupa
// Domain contribution: NvM configuration schema as M2 types

// --- Constrained primitive types for NvM parameters ---

#[range(2, 65535)]
type NvramBlockIdentifier = integer;

#[range(1, 65535)]
type NvBlockLength = integer;

#[range(1, 255)]
type NvBlockNum = integer;

#[range(0, 1)]
type NvramDeviceId = integer;

// --- Enumerations from EcucEnumerationParamDef ---

enum NvMBlockManagementType {
    NVM_BLOCK_NATIVE,
    NVM_BLOCK_REDUNDANT,
    NVM_BLOCK_DATASET,
};

enum NvMBlockCrcType {
    NVM_CRC8,
    NVM_CRC16,
    NVM_CRC32,
};

// --- Composite types (container definitions) ---

type NvMBlockDescriptor = {
    #[id(0)]
    .name: Name;
    .nvramBlockIdentifier: NvramBlockIdentifier;
    .nvBlockLength: NvBlockLength;
    .blockUseCrc: Boolean;
    .blockCrcType: NvMBlockCrcType?;         // optional: only meaningful when CRC enabled
    .blockManagementType: NvMBlockManagementType;
    .nvBlockNum: NvBlockNum;
    .nvramDeviceId: NvramDeviceId;
    .blockUseSyncMechanism: Boolean;
    .romBlockDataAddress: Name?;
    .ramBlockDataAddress: Name?;
};

type NvMCommon = {
    #[id(0)]
    .name: Name;
    .compiledConfigId: NvramBlockIdentifier;
    .datasetSelectionBits: DatasetSelectionBits;
};

#[range(0, 8)]
type DatasetSelectionBits = integer;

type NvM = {
    #[id(0)]
    .name: Name;
    .common: NvMCommon;
    .blockDescriptors: NvMBlockDescriptor+;  // one or more (LOWER-MULTIPLICITY=1)
};
```

### M1 Domain Consumption -- NvM Configuration Values

The ECUC value layer maps to M1 instances. Each `EcucContainerValue` becomes an
instance of its corresponding M2 type. Each `EcucParameterValue` becomes a role
assignment. No `DEFINITION-REF` is needed -- the type annotation on the role
provides that link.

```rupa
// file: config/nvm-config.rupa
// Domain consumption: NvM configuration values as M1 instances
using domain ecuc-nvm;

NvM NvM {
    .common = NvMCommon NvMCommonSettings {
        .compiledConfigId = 1;
        .datasetSelectionBits = 4;
    };

    // Block 1: Application data -- native, CRC16
    .blockDescriptors += NvMBlockDescriptor NvMBlock_AppData {
        .nvramBlockIdentifier = 2;
        .nvBlockLength = 128;
        .blockUseCrc = true;
        .blockCrcType = NVM_CRC16;
        .blockManagementType = NVM_BLOCK_NATIVE;
        .nvBlockNum = 1;
        .nvramDeviceId = 0;
        .blockUseSyncMechanism = false;
    };

    // Block 2: Calibration data -- redundant, CRC32, sync mechanism
    .blockDescriptors += NvMBlockDescriptor NvMBlock_Calibration {
        .nvramBlockIdentifier = 3;
        .nvBlockLength = 256;
        .blockUseCrc = true;
        .blockCrcType = NVM_CRC32;
        .blockManagementType = NVM_BLOCK_REDUNDANT;
        .nvBlockNum = 2;
        .nvramDeviceId = 0;
        .blockUseSyncMechanism = true;
        .romBlockDataAddress = "Cal_RomBlock";
    };

    // Block 3: Diagnostic log -- dataset, no CRC
    .blockDescriptors += NvMBlockDescriptor NvMBlock_DiagLog {
        .nvramBlockIdentifier = 4;
        .nvBlockLength = 64;
        .blockUseCrc = false;
        .blockManagementType = NVM_BLOCK_DATASET;
        .nvBlockNum = 8;
        .nvramDeviceId = 1;
        .blockUseSyncMechanism = false;
    };
};
```

### Validation Rules

ECUC definitions carry cross-parameter constraints that the type system alone
cannot express. These map to `#[rule]` functions with self-guarding via `->`.

```rupa
// file: domains/ecuc-nvm/rules.rupa
using domain ecuc-nvm;

// Block identifiers must be unique across all blocks in a module
#[rule(ecuc::nvm::unique_block_ids)]
let unique_block_ids() = (. is NvM) ->
    .blockDescriptors | map(b => b.nvramBlockIdentifier) | is_unique();

// Redundant blocks must have nvBlockNum == 2 (one original + one copy)
#[rule(ecuc::nvm::redundant_block_num)]
let redundant_block_num() = (. is NvMBlockDescriptor) ->
    (.blockManagementType == NVM_BLOCK_REDUNDANT) -> .nvBlockNum == 2;

// CRC type is required when CRC is enabled
#[rule(ecuc::nvm::crc_type_required)]
let crc_type_required() = (. is NvMBlockDescriptor) ->
    .blockUseCrc -> .blockCrcType | exists();

// Dataset blocks must have nvBlockNum >= 1
#[rule(ecuc::nvm::dataset_block_count)]
let dataset_block_count() = (. is NvMBlockDescriptor) ->
    (.blockManagementType == NVM_BLOCK_DATASET) ->
        .nvBlockNum >= 1 && .nvBlockNum <= 255;
```

### Activating Validation at the Type Level

Rules are activated on M2 types so that every instance is checked automatically.

```rupa
// file: domains/ecuc-nvm/validation.rupa
using domain ecuc-nvm;
import "rules.rupa";

#[validate(ecuc::nvm::unique_block_ids)]
type NvM = NvM;

#[validate(ecuc::nvm::redundant_block_num)]
#[validate(ecuc::nvm::crc_type_required)]
#[validate(ecuc::nvm::dataset_block_count)]
type NvMBlockDescriptor = NvMBlockDescriptor;
```

---

## Key Features Demonstrated

| Feature | Where it appears |
|---------|-----------------|
| **M2/M1 separation** | Type definitions in `types.rupa` (domain contribution) vs. instances in `nvm-config.rupa` (domain consumption) |
| **`DEFINITION-REF` elimination** | Instances are typed -- `NvMBlockDescriptor NvMBlock_AppData { }` IS the conformance link |
| **Constrained primitives** | `#[range(2, 65535)] type NvramBlockIdentifier = integer;` replaces `EcucIntegerParamDef` with `MIN`/`MAX` |
| **Enumerations** | `enum NvMBlockCrcType` replaces `EcucEnumerationParamDef` with `ECUC-ENUMERATION-LITERAL-DEF` children |
| **Multiplicity** | `.blockDescriptors: NvMBlockDescriptor+` (one or more) maps `LOWER-MULTIPLICITY=1` / `UPPER-MULTIPLICITY-INFINITE=true` |
| **Optional roles** | `.blockCrcType: NvMBlockCrcType?` maps `LOWER-MULTIPLICITY=0` / `UPPER-MULTIPLICITY=1` |
| **Cross-parameter rules** | `crc_type_required`: CRC type is required when CRC is enabled (cross-role dependency) |
| **Uniqueness constraints** | `unique_block_ids`: block IDs must be unique via `is_unique()` |
| **Implication chains** | `redundant_block_num`: management type == REDUNDANT implies nvBlockNum == 2 |
| **M2-level `#[validate]`** | Rules activated on type definitions apply to all instances automatically |
| **Collection append (`+=`)** | `.blockDescriptors +=` for multi-valued containment roles |

---

## Comparison

| Aspect | ARXML | Rupa |
|--------|-------|------|
| **Schema conformance** | `DEFINITION-REF` on every container and parameter value | Implicit via type system -- instance IS conformance |
| **Parameter type checking** | Tooling validates against `MIN`/`MAX` in definition | `#[range]` on M2 primitive type -- checked at parse time |
| **Enumeration literals** | `ECUC-ENUMERATION-LITERAL-DEF` children in definition XML | `enum` type with values -- first-class language construct |
| **Container multiplicity** | `LOWER-MULTIPLICITY` / `UPPER-MULTIPLICITY` attributes | Role multiplicity suffixes: `+`, `*`, `?`, `{m,n}` |
| **Cross-parameter constraints** | Not expressible in ARXML; external tool or documentation | `#[rule]` functions with `->` implication |
| **Lines for 3 blocks** | ~150 (values only, no definition) | ~45 (instances) + ~50 (types) + ~20 (rules) |
| **Redundant type info** | `DEST` attribute on every reference | Eliminated -- role type IS the definition |
| **CRC consistency** | Manual review or external script | `crc_type_required` rule, auto-checked |
| **Unique ID enforcement** | External tooling (AUTOSAR methodology tools) | `unique_block_ids` rule with `is_unique()` |
| **Validation activation** | N/A (no built-in mechanism) | `#[validate]` on M2 types -- all instances inherit rules |

The fundamental difference is that ARXML encodes schema conformance as
*data* (the `DEFINITION-REF` path on every value element) while Rupa encodes it
as *types* (the M2 type system). This eliminates an entire category of
consistency errors -- a mistyped `DEFINITION-REF` path in ARXML is a silent
failure until a tool happens to check it, while a misspelled type name in Rupa
is a compile error.
