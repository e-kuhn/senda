# Pattern 05: Blueprints and Derivation

Blueprints are AUTOSAR's mechanism for standardizing reusable model element
templates. A blueprint defines the shape and constraints of an element --
its structure, naming patterns, and modification policies -- while leaving
project-specific details to be filled in when concrete elements are derived.
This pattern maps to Rupa's `from` keyword (object derivation), domain
derivation, and validation rules for conformance checking.

---

## AUTOSAR Concept

### The AtpBlueprint / AtpBlueprintable M3 Pattern

At the AUTOSAR M3 level, two abstract meta-classes govern the blueprint
mechanism:

- **`AtpBlueprint`**: A meta-class representing the ability to *act as* a
  blueprint. Inherits from `Identifiable`. Concrete subclasses include
  `PortInterface`, `ApplicationDataType`, `CompuMethod`, `DataConstr`,
  `SwComponentType`, `ARPackage`, `PortPrototypeBlueprint`, and many others.

- **`AtpBlueprintable`**: A meta-class representing the ability to *be
  derived from* a blueprint. Elements that are `AtpBlueprintable` can
  reference a blueprint and must conform to its constraints.

Many AUTOSAR meta-classes inherit from both `AtpBlueprint` **and**
`AtpBlueprintable` -- a `SenderReceiverInterface` can be a blueprint that
other interfaces derive from, and can itself be derived from another
blueprint. This dual nature is critical: blueprints form chains.

### Blueprint Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| `SHORT-NAME` with `NAME-PATTERN` | `string` | Regex-like pattern constraining derived element names |
| `CATEGORY` | `string` | Set to `BLUEPRINT` for blueprint packages and elements |
| `BLUEPRINT-POLICYS` | `BlueprintPolicy*` | Per-attribute modification rules |
| `BLUEPRINT-CONDITION` | `DocumentationBlock` | Conditions under which the blueprint applies |

The `NAME-PATTERN` attribute on `SHORT-NAME` is the central naming
constraint. It uses a pattern syntax with placeholders:

| Pattern | Meaning |
|---------|---------|
| `{blueprintName}` | The shortName of the blueprint itself |
| `{anyName}` | Any valid identifier (unconstrained) |
| `{blueprintName}({<Keyword>})0..n` | Blueprint name followed by optional keyword suffixes |

### BlueprintPolicy

Each attribute of a blueprint element carries a `BlueprintPolicy` that
declares whether derived elements may modify that attribute:

| Policy | Meaning |
|--------|---------|
| `not-modifiable` | Derived element must preserve the blueprint's value exactly |
| `modifiable` (implicit) | Derived element may override or extend the value |

The `BlueprintPolicy` aggregation uses `attributeName` as its split key,
allowing per-attribute control: a blueprint `SenderReceiverInterface` might
declare its `DATA-ELEMENTS` structure as `not-modifiable` while allowing
`LONG-NAME` and `DESC` to be freely modified.

### BlueprintMapping and BlueprintMappingSet

When a concrete element is derived from a blueprint, a `BlueprintMapping`
records the relationship. These mappings are collected into
`BlueprintMappingSet` containers. The mapping serves two purposes:

1. **Traceability**: Which blueprint was the source for each derived element.
2. **Conformance validation**: Tools can verify that derived elements still
   satisfy their blueprint's constraints.

### Package Organization

AUTOSAR organizes blueprints and derived elements into parallel package
structures using the `CATEGORY` attribute:

```
/AUTOSAR
  /PortInterfaces_Blueprint          CATEGORY=BLUEPRINT
    SenderReceiverInterface BattU1     (blueprint)
    SenderReceiverInterface EngN1      (blueprint)
  /PortInterfaces_Example            CATEGORY=EXAMPLE
    SenderReceiverInterface BattU1     (derived from blueprint)
    SenderReceiverInterface EngN1      (derived from blueprint)
  /BlueprintMappingSets_Example      CATEGORY=EXAMPLE
    BlueprintMappingSet PortInterfaceBlueprintMappings
```

### ARXML: A SenderReceiverInterface Blueprint and Derivation

The following ARXML shows a blueprint `SenderReceiverInterface` defining a
standardized vehicle speed signal, followed by a derived concrete interface.

**Blueprint definition** (in a `CATEGORY=BLUEPRINT` package):

```xml
<AR-PACKAGE>
  <SHORT-NAME>PortInterfaces_Blueprint</SHORT-NAME>
  <CATEGORY>BLUEPRINT</CATEGORY>
  <ELEMENTS>
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME NAME-PATTERN="{anyName}">VehSpd1</SHORT-NAME>
      <LONG-NAME><L-4 L="EN">Vehicle Speed</L-4></LONG-NAME>
      <DESC>
        <L-2 L="EN">Standardized interface for vehicle speed signal.
        Projects shall derive from this blueprint.</L-2>
      </DESC>
      <IS-SERVICE>false</IS-SERVICE>
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME NAME-PATTERN="{anyName}">VehSpd</SHORT-NAME>
          <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE"
            >/AUTOSAR/ApplicationDataTypes_Blueprint/Spd1</TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>
  </ELEMENTS>
</AR-PACKAGE>
```

**Derived element** (in a `CATEGORY=EXAMPLE` package):

```xml
<AR-PACKAGE>
  <SHORT-NAME>PortInterfaces_Example</SHORT-NAME>
  <CATEGORY>EXAMPLE</CATEGORY>
  <ELEMENTS>
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME>VehSpd1</SHORT-NAME>
      <LONG-NAME><L-4 L="EN">Vehicle Speed</L-4></LONG-NAME>
      <DESC>
        <L-2 L="EN">Project-specific vehicle speed interface derived
        from the standardized blueprint.</L-2>
      </DESC>
      <IS-SERVICE>false</IS-SERVICE>
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME>VehSpd</SHORT-NAME>
          <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE"
            >/Project/DataTypes/Spd1</TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>
  </ELEMENTS>
</AR-PACKAGE>
```

**Blueprint mapping** (recording the derivation relationship):

```xml
<AR-PACKAGE>
  <SHORT-NAME>BlueprintMappingSets_Example</SHORT-NAME>
  <CATEGORY>EXAMPLE</CATEGORY>
  <ELEMENTS>
    <BLUEPRINT-MAPPING-SET>
      <SHORT-NAME>PortInterfaceBlueprintMappings</SHORT-NAME>
      <BLUEPRINT-MAPS>
        <BLUEPRINT-MAPPING>
          <BLUEPRINT-REF DEST="SENDER-RECEIVER-INTERFACE"
            >/AUTOSAR/PortInterfaces_Blueprint/VehSpd1</BLUEPRINT-REF>
          <DERIVED-ELEMENT-REF DEST="SENDER-RECEIVER-INTERFACE"
            >/Project/PortInterfaces_Example/VehSpd1</DERIVED-ELEMENT-REF>
        </BLUEPRINT-MAPPING>
      </BLUEPRINT-MAPS>
    </BLUEPRINT-MAPPING-SET>
  </ELEMENTS>
</AR-PACKAGE>
```

---

## Rupa Mapping

### Object Derivation with `from`

Rupa's `from` keyword (4.4.12) is the direct analog of AUTOSAR blueprint
derivation. An object created with `from` copies non-identity properties
from the source, then applies overrides in the body block.

```rupa
using domain autosar-cp-r25;

// Blueprint package -- define reusable templates
ARPackage PortInterfaces_Blueprint {
    .category = "BLUEPRINT";

    SenderReceiverInterface VehSpd1 {
        .longName = "Vehicle Speed";
        .desc = "Standardized interface for vehicle speed signal.";
        .isService = false;

        VariableDataPrototype VehSpd {
            .type = &/AUTOSAR/ApplicationDataTypes_Blueprint/Spd1;
        }
    }
}
```

**Deriving a concrete element:**

```rupa
// Project-specific derived interface
ARPackage PortInterfaces_Project {
    .category = "EXAMPLE";

    SenderReceiverInterface VehSpd1
        from /PortInterfaces_Blueprint/VehSpd1
    {
        // Override: point data element type to project-local data type
        .dataElements[VehSpd].type = &/Project/DataTypes/Spd1;

        // desc is overridden; longName and structure are copied
        .desc = "Project-specific vehicle speed interface.";
    }
}
```

Derivation semantics from 4.4.14 and 4.4.15 apply:

- The derived object gets a **new identity** (`VehSpd1` in the project
  package, distinct from the blueprint's `VehSpd1`).
- **Compositions are deep-copied**: the `VariableDataPrototype VehSpd`
  child is copied with new identity into the derived interface.
- **References are preserved**: the `type` tref to the data type is
  copied as-is (then overridden in this case).

### Tracking Blueprint Mappings

The `BlueprintMapping` relationship is expressed as a first-class model
element. Rupa does not have a special annotation for this -- it uses the
domain's own `BlueprintMappingSet` type, consistent with the principle that
domain-specific metadata is expressed through domain types (6.4).

```rupa
ARPackage BlueprintMappingSets_Project {
    .category = "EXAMPLE";

    BlueprintMappingSet PortInterfaceBlueprintMappings {
        BlueprintMapping {
            .blueprint = &/PortInterfaces_Blueprint/VehSpd1;
            .derivedElement = &/PortInterfaces_Project/VehSpd1;
        }
    }
}
```

### Name Pattern Validation

AUTOSAR's `NAME-PATTERN` attribute constrains the `shortName` of derived
elements. In Rupa, this maps to validation rules (Topic 7). The domain
package provides validation functions that check naming conformance.

```rupa
// Domain-provided validation rule for blueprint name patterns
#[rule(/autosar/blueprint/name-conformance)]
#[severity(error)]
#[message("Derived element '{self.shortName}' does not match blueprint "
          "name pattern '{blueprint.namePattern}'")]
let check_name_pattern(mapping: BlueprintMapping) =
    let blueprint = mapping.blueprint;
    let derived = mapping.derivedElement;
    match_name_pattern(derived.shortName, blueprint.namePattern);
```

The `match_name_pattern` function (provided via FFI or as a domain
utility) interprets the AUTOSAR name-pattern syntax:

| Pattern | Matches |
|---------|---------|
| `{blueprintName}` | Exactly the blueprint's shortName |
| `{anyName}` | Any valid AUTOSAR identifier |
| `{blueprintName}({<Keyword>})0..n` | Blueprint name + optional keyword suffixes |

### BlueprintPolicy as Validation

AUTOSAR's per-attribute `BlueprintPolicy` (modifiable vs. not-modifiable)
becomes a validation constraint. The domain provides rules that compare
derived elements against their blueprints:

```rupa
#[rule(/autosar/blueprint/policy-conformance)]
#[severity(error)]
#[message("Attribute '{policy.attributeName}' is not-modifiable in "
          "blueprint '{blueprint.shortName}' but was changed")]
let check_blueprint_policy(mapping: BlueprintMapping) =
    let blueprint = mapping.blueprint;
    let derived = mapping.derivedElement;
    blueprint.blueprintPolicys
        | filter(p => p.value == "not-modifiable")
        | all(policy =>
            role_of(derived, policy.attributeName)
                == role_of(blueprint, policy.attributeName));
```

### Domain Derivation for Blueprint Packages

When a project needs to extend the standard AUTOSAR blueprint set with
company-specific blueprints, Rupa's domain derivation (6.4) handles this:

```rupa
// Standard blueprint domain
domain autosar-cp-r25;

// Company extension -- derives a new domain, adds custom blueprints
domain mycompany-autosar-cp-r25 = autosar-cp-r25;

ARPackage PortInterfaces_CompanyBlueprint {
    .category = "BLUEPRINT";

    // Company-specific blueprint extending the standard set
    SenderReceiverInterface WhlSpdFrntLe1 {
        .longName = "Front Left Wheel Speed";
        .desc = "Company-standardized wheel speed interface.";
        .isService = false;

        VariableDataPrototype WhlSpd {
            .type = &/AUTOSAR/ApplicationDataTypes_Blueprint/Spd1;
        }
    }
}
```

Project teams then derive from the company domain:

```rupa
using domain mycompany-autosar-cp-r25;

// Derive from company-level blueprint
SenderReceiverInterface WhlSpdFrntLe1
    from /PortInterfaces_CompanyBlueprint/WhlSpdFrntLe1
{
    .desc = "ECU-specific front-left wheel speed.";
}
```

---

## Worked Example: PortPrototypeBlueprint Derivation

The `PortPrototypeBlueprint` is a particularly important blueprint type in
AUTOSAR Application Interfaces. It defines a reusable port pattern including
the interface reference, communication specifications, and initial values.
The following shows the full lifecycle: blueprint definition, derivation
into a concrete `PortPrototype` within a `SwComponentType`, and the
blueprint mapping that tracks the relationship.

### ARXML Side

**Blueprint:**

```xml
<AR-PACKAGE>
  <SHORT-NAME>PortPrototypeBlueprints_Blueprint</SHORT-NAME>
  <CATEGORY>BLUEPRINT</CATEGORY>
  <ELEMENTS>
    <PORT-PROTOTYPE-BLUEPRINT>
      <SHORT-NAME NAME-PATTERN="{blueprintName}">EngN</SHORT-NAME>
      <LONG-NAME><L-4 L="EN">Actual Engine Speed</L-4></LONG-NAME>
      <INTERFACE-REF DEST="SENDER-RECEIVER-INTERFACE"
        >/AUTOSAR/PortInterfaces_Blueprint/EngN1</INTERFACE-REF>
      <PROVIDED-COM-SPECS>
        <NONQUEUED-SENDER-COM-SPEC>
          <DATA-ELEMENT-REF DEST="VARIABLE-DATA-PROTOTYPE"
            >/AUTOSAR/PortInterfaces_Blueprint/EngN1/EngN</DATA-ELEMENT-REF>
          <INIT-VALUE>
            <NUMERICAL-VALUE-SPECIFICATION>
              <VALUE>0</VALUE>
            </NUMERICAL-VALUE-SPECIFICATION>
          </INIT-VALUE>
        </NONQUEUED-SENDER-COM-SPEC>
      </PROVIDED-COM-SPECS>
    </PORT-PROTOTYPE-BLUEPRINT>
  </ELEMENTS>
</AR-PACKAGE>
```

**Derived PortPrototype in a concrete SwComponentType:**

```xml
<APPLICATION-SW-COMPONENT-TYPE>
  <SHORT-NAME>EngineMgmt</SHORT-NAME>
  <PORTS>
    <P-PORT-PROTOTYPE>
      <SHORT-NAME>EngN</SHORT-NAME>
      <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
        >/Project/PortInterfaces/EngN1</PROVIDED-INTERFACE-TREF>
      <PROVIDED-COM-SPECS>
        <NONQUEUED-SENDER-COM-SPEC>
          <DATA-ELEMENT-REF DEST="VARIABLE-DATA-PROTOTYPE"
            >/Project/PortInterfaces/EngN1/EngN</DATA-ELEMENT-REF>
          <INIT-VALUE>
            <NUMERICAL-VALUE-SPECIFICATION>
              <VALUE>0</VALUE>
            </NUMERICAL-VALUE-SPECIFICATION>
          </INIT-VALUE>
        </NONQUEUED-SENDER-COM-SPEC>
      </PROVIDED-COM-SPECS>
    </P-PORT-PROTOTYPE>
  </PORTS>
</APPLICATION-SW-COMPONENT-TYPE>
```

### Rupa Side

```rupa
using domain autosar-cp-r25;

// Blueprint definition
ARPackage PortPrototypeBlueprints {
    .category = "BLUEPRINT";

    PortPrototypeBlueprint EngN {
        .longName = "Actual Engine Speed";
        .interface = &/AUTOSAR/PortInterfaces_Blueprint/EngN1;
        NonqueuedSenderComSpec {
            .dataElement = &/AUTOSAR/PortInterfaces_Blueprint/EngN1/EngN;
            .initValue = NumericalValueSpecification { .value = 0; };
        }
    }
}

// Concrete component with port derived from blueprint
ApplicationSwComponentType EngineMgmt {
    PPortPrototype EngN from /PortPrototypeBlueprints/EngN {
        // Override interface ref to project-local copy
        .providedInterface = &/Project/PortInterfaces/EngN1;
    }
}

// Record the derivation
BlueprintMappingSet PortPrototypeBlueprintMappings {
    BlueprintMapping {
        .blueprint = &/PortPrototypeBlueprints/EngN;
        .derivedElement = &/EngineMgmt/EngN;
    }
}
```

The `from` keyword copies the communication specifications (the
`NonqueuedSenderComSpec` with its init value) from the blueprint into the
derived port. The body block then overrides the interface reference to point
at the project's own copy of the `EngN1` interface -- itself derived from
the interface blueprint.

---

## Edge Cases

### 1. Blueprint Conformance Checking after Modification

A derived element may be modified after initial derivation (e.g., through
a merge overlay). The blueprint mapping still references the original
blueprint, so conformance validation must run against the final state of
the derived element, not its initial derived state.

```rupa
// Initial derivation
SenderReceiverInterface VehSpd1
    from /PortInterfaces_Blueprint/VehSpd1 { }

// Later overlay modifies a not-modifiable attribute
let patch = import "customer-patch.rupa";
#[merge(conflict = { single = replace })]
/PortInterfaces_Project/VehSpd1 |= $patch;

// Validation must catch: if the patch changed a not-modifiable
// attribute, the blueprint policy rule fires an error
```

This is a strength of separating derivation (copy-time) from validation
(check-time). The `from` keyword performs the copy. Validation rules run
later against the composed model. There is no implicit "blueprint lock"
on derived elements -- the domain's validation rules enforce conformance.

### 2. Partial Derivation

AUTOSAR blueprints may include `BLUEPRINT-CONDITION` elements specifying
when parts of a blueprint apply. A derived `FlatMap` need not contain all
`FlatInstanceDescriptor` entries from the blueprint -- only those whose
conditions are satisfied.

In Rupa, partial derivation requires explicit deletion of inapplicable
parts after the copy:

```rupa
FlatMap ProjectMap from /FlatMaps_Blueprint/ARMap {
    // Remove descriptors not applicable to this project
    #[delete(missing = ignore)]
    .instances -= [
        &/FlatMaps_Blueprint/ARMap/AR_Brake_Pedl,
        &/FlatMaps_Blueprint/ARMap/AR_Trlr_Sts
    ];
}
```

Alternatively, a transform can filter based on blueprint conditions:

```rupa
#[transform]
let derive_flatmap(blueprint: FlatMap) =
    FlatMap from $(blueprint) {
        .instances = blueprint.instances
            | filter(d => evaluate_condition(d.variationPoint));
    };
```

### 3. Name Pattern Regex Validation

The `NAME-PATTERN` syntax uses AUTOSAR-specific placeholders, not standard
regex. The domain must provide a dedicated matcher. Edge cases include:

- **`{blueprintName}` with keyword suffixes**: `EngN` as blueprint name
  allows `EngN`, `EngNFrontLeft`, `EngNRearRight` when the pattern is
  `{blueprintName}({<Keyword>})0..n`.

- **`{anyName}`**: Effectively unconstrained, but still must be a valid
  AUTOSAR identifier (no spaces, no leading digits, specific character set).

- **Nested blueprints**: A blueprint's data element has its own
  `NAME-PATTERN`. When deriving, both the parent element's pattern and the
  child element's pattern must be satisfied independently.

```rupa
// Validation must check patterns at every level
#[rule(/autosar/blueprint/nested-name-conformance)]
let check_nested_names(mapping: BlueprintMapping) =
    let blueprint = mapping.blueprint;
    let derived = mapping.derivedElement;
    // Check top-level name
    match_name_pattern(derived.shortName, blueprint.namePattern)
    // Check all child elements with their own patterns
    && ::children(blueprint)
        | filter(child => child has .namePattern)
        | all(bp_child =>
            let derived_child = ::children(derived)
                | find(dc => dc.shortName == bp_child.shortName
                          || match_name_pattern(dc.shortName,
                                                bp_child.namePattern));
            derived_child? && match_name_pattern(
                derived_child.shortName, bp_child.namePattern));
```

### 4. Blueprint Chains

Since AUTOSAR elements can be both `AtpBlueprint` and `AtpBlueprintable`,
blueprints can derive from other blueprints. A company-level blueprint
might derive from the AUTOSAR standard blueprint, and project-level
elements derive from the company blueprint.

```rupa
// AUTOSAR standard blueprint
SenderReceiverInterface VehSpd1 {
    .category = "BLUEPRINT";
    VariableDataPrototype VehSpd {
        .type = &/AUTOSAR/ApplicationDataTypes_Blueprint/Spd1;
    }
}

// Company blueprint derived from standard
SenderReceiverInterface VehSpd1
    from /AUTOSAR/PortInterfaces_Blueprint/VehSpd1
{
    .category = "BLUEPRINT";  // Still a blueprint
    .desc = "Company-mandated vehicle speed with additional constraints.";
}

// Project element derived from company blueprint
SenderReceiverInterface VehSpd1
    from /Company/PortInterfaces_Blueprint/VehSpd1
{
    .category = "EXAMPLE";  // Final concrete element
    .desc = "ECU-specific vehicle speed interface.";
}
```

Each derivation in the chain produces a `BlueprintMapping`. Conformance
validation can walk the chain to verify that constraints from all ancestor
blueprints are satisfied.

### 5. Cross-Domain Blueprint References

A blueprint may reference types from a different domain version. When the
derived element targets a newer domain, type references must be updated.

```rupa
// Blueprint references v24 data types
SenderReceiverInterface VehSpd1 {
    VariableDataPrototype VehSpd {
        .type = &/AUTOSAR_R24/ApplicationDataTypes/Spd1;
    }
}

// Derivation for v25 project -- must override the type reference
SenderReceiverInterface VehSpd1
    from /Blueprints_R24/VehSpd1
{
    .dataElements[VehSpd].type = &/Project_R25/DataTypes/Spd1;
}
```

Rupa's domain-agnostic `from` handles this naturally: the copy preserves
the original reference, and the body block overrides it. Validation rules
can then check that all references in the derived element resolve within
the target domain.

---

## Design Reference

| Topic | Document | Relevance |
|-------|----------|-----------|
| Object derivation (`from`) | `design/current/04-modularity/model-composition.md` (4.4.12-4.4.16) | Copy semantics, single source, deep-copy of compositions |
| Domain derivation | `design/current/06-extensibility/domain-specific-extensions.md` (Domain Model) | `domain X = Y;` for extending blueprint sets |
| Domain-specific metadata | `design/current/06-extensibility/domain-specific-extensions.md` (Annotations Are Language-Only) | Blueprint tracking as domain types, not annotations |
| Validation rules | `design/current/07-validation/` | `#[rule]`, `#[severity]`, `#[message]` for conformance |
| Merge overlays | `design/current/04-modularity/model-composition.md` (4.4.1-4.4.6) | Post-derivation modifications and conflict detection |
| Delete operations | `design/current/05-modification/` | `#[delete]` for partial derivation pruning |
