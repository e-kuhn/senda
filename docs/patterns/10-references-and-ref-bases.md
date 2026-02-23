# Pattern 10: References and Reference Bases

AUTOSAR XML uses three distinct reference mechanisms (REF, TREF, IREF) and a
`REFERENCE-BASE` system for relative path resolution. This pattern maps all three
reference kinds -- plus the `DEST` attribute and reference-base machinery -- to
Rupa's typed reference system (`&Type`), identity paths, the `*` search anchor,
and the import/namespace facilities.

---

## AUTOSAR Concept

### Three Reference Kinds

AUTOSAR ARXML distinguishes three XML element forms for referencing objects:

| Kind | XML element pattern | Purpose |
|------|-------------------|---------|
| **REF** | `<...-REF DEST="...">path</...-REF>` | Standard reference to an identifiable element by SHORT-NAME-PATH |
| **TREF** | `<TYPE-TREF DEST="...">path</TYPE-TREF>` | Type reference -- the target is used as the *type of* the source element |
| **IREF** | `<...-IREF>` containing context + target refs | Instance reference -- composite reference through prototype chains (see Pattern 03) |

All three share the `DEST` attribute, which declares the expected metamodel class
of the target. The difference is semantic intent:

- **REF** is a general-purpose pointer: "this element references that element."
- **TREF** is a type-of pointer: "this element's type is that element." It appears
  on prototypes and data elements where the referenced object serves as a
  classifier rather than a peer.
- **IREF** is a structured composite reference: "follow this chain of instances to
  reach an element defined in an archetype." Covered in depth in Pattern 03.

### The DEST Attribute

Every `REF` and `TREF` element carries a mandatory `DEST` attribute:

```xml
<SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/AUTOSAR/Signals/BrakeForce</SYSTEM-SIGNAL-REF>
<TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/AUTOSAR/DataTypes/Speed</TYPE-TREF>
```

`DEST` serves two purposes in ARXML:

1. **Validation**: The XML parser checks that the referenced element's meta-class
   matches the declared `DEST` value. A `DEST="SYSTEM-SIGNAL"` pointing at a
   `PHYSICAL-DIMENSION` is an error.
2. **Disambiguation**: In the absence of a type system, `DEST` tells tooling what
   kind of object to expect at the end of the path, enabling schema-level checks
   before the full model is resolved.

### The REFERENCE-BASE Mechanism

AUTOSAR defines a `REFERENCE-BASE` element inside `ADMIN-DATA` at the package
level. This mechanism enables relative path references within ARXML files,
reducing verbosity and improving portability when packages are moved.

A `REFERENCE-BASE` declares a named base path:

```xml
<AR-PACKAGE>
  <SHORT-NAME>SwComponentTypes_Example</SHORT-NAME>
  <ADMIN-DATA>
    <SDGS>
      <SDG GID="AutosarStandardReferenceBase">
        <SD GID="SHORT-LABEL">SwComponentTypes</SD>
        <SD GID="LONG-LABEL">/AUTOSAR/AISpecification/SwComponentTypes_Example</SD>
        <SD GID="IS-DEFAULT">true</SD>
      </SDG>
    </SDGS>
  </ADMIN-DATA>
  <!-- ... elements ... -->
</AR-PACKAGE>
```

References then use the `BASE` attribute to resolve relative paths:

```xml
<CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
  BASE="SwComponentTypes">WiprWshr/WiprWshrMgr</CONTEXT-COMPONENT-REF>
```

Here `WiprWshr/WiprWshrMgr` is resolved relative to the base path
`/AUTOSAR/AISpecification/SwComponentTypes_Example`. A relative path is
identified by not starting with a slash.

Key properties of the REFERENCE-BASE mechanism:

| Property | Behavior |
|----------|----------|
| `SHORT-LABEL` | The name used in `BASE="..."` attributes |
| `LONG-LABEL` | The absolute SHORT-NAME-PATH that the base resolves to |
| `IS-DEFAULT` | If `true`, references without an explicit `BASE` attribute use this base |
| Scope | The base is visible to all elements within the containing package and its sub-packages |
| Inheritance | Child packages inherit reference bases from parent packages; a child may override by declaring a base with the same `SHORT-LABEL` |

### ARXML Example: All Three Reference Kinds

The following ARXML fragment illustrates REF, TREF, and the REFERENCE-BASE
mechanism in a component-type context. The IREF is shown for completeness
(detailed treatment in Pattern 03).

```xml
<AR-PACKAGE>
  <SHORT-NAME>SwComponentTypes</SHORT-NAME>
  <ADMIN-DATA>
    <SDGS>
      <SDG GID="AutosarStandardReferenceBase">
        <SD GID="SHORT-LABEL">DataTypes</SD>
        <SD GID="LONG-LABEL">/AUTOSAR/DataTypes</SD>
      </SDG>
    </SDGS>
  </ADMIN-DATA>
  <ELEMENTS>
    <APPLICATION-SW-COMPONENT-TYPE>
      <SHORT-NAME>SpeedSensor</SHORT-NAME>
      <PORTS>
        <P-PORT-PROTOTYPE>
          <SHORT-NAME>SpeedPort</SHORT-NAME>
          <!-- REF: standard reference to the port interface -->
          <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
            >/AUTOSAR/Interfaces/SpeedInterface</PROVIDED-INTERFACE-TREF>
        </P-PORT-PROTOTYPE>
      </PORTS>
    </APPLICATION-SW-COMPONENT-TYPE>

    <COMPOSITION-SW-COMPONENT-TYPE>
      <SHORT-NAME>TopComposition</SHORT-NAME>
      <COMPONENTS>
        <SW-COMPONENT-PROTOTYPE>
          <SHORT-NAME>SensorInstance</SHORT-NAME>
          <!-- TREF: type reference to the component type -->
          <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
            >/AUTOSAR/SwComponentTypes/SpeedSensor</TYPE-TREF>
        </SW-COMPONENT-PROTOTYPE>
      </COMPONENTS>
      <CONNECTORS>
        <DELEGATION-SW-CONNECTOR>
          <SHORT-NAME>SpeedDelegation</SHORT-NAME>
          <INNER-PORT-IREF>
            <!-- IREF: instance reference through prototype to port -->
            <P-PORT-IN-COMPOSITION-INSTANCE-REF>
              <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                >SensorInstance</CONTEXT-COMPONENT-REF>
              <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE"
                >/AUTOSAR/SwComponentTypes/SpeedSensor/SpeedPort</TARGET-P-PORT-REF>
            </P-PORT-IN-COMPOSITION-INSTANCE-REF>
          </INNER-PORT-IREF>
          <OUTER-PORT-REF DEST="P-PORT-PROTOTYPE"
            >TopComposition/ExternalSpeed</OUTER-PORT-REF>
        </DELEGATION-SW-CONNECTOR>
      </CONNECTORS>
    </COMPOSITION-SW-COMPONENT-TYPE>
  </ELEMENTS>
</AR-PACKAGE>
```

**Source**: AUTOSAR CP R25-11, EXP Application Interfaces User Guide
(Document ID 442), Sections 10.2.2 (References) and 10.2.2.2 (Type References).

---

## Rupa Mapping

### REF and TREF: Unified as `&Type`

Rupa collapses the REF/TREF distinction into a single mechanism: the `&Type`
typed reference role. The metamodel declares what a reference points to; the
compiler enforces it at compile time.

| AUTOSAR | Rupa |
|---------|------|
| `<SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">path</...>` | `.signalRef: &SystemSignal` + `.signalRef = /path;` |
| `<TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE">path</...>` | `#[archetype] .type: &SwComponentType` + `.type = /path;` |

The "type-of" semantics of TREF are captured by the `#[archetype]` annotation
(see Pattern 02). A reference role annotated with `#[archetype]` is the Rupa
equivalent of TREF: it declares that the referenced object serves as the
classifier/archetype for the containing prototype. A reference role without
`#[archetype]` is the equivalent of a plain REF.

Both forms use the same path syntax. The distinction is metamodel-level (how the
reference is *used*), not syntax-level (how it is *written*).

### DEST Attribute: Eliminated by Static Typing

The `DEST` attribute exists because ARXML is an untyped serialization format. In
Rupa, the role declaration `&SystemSignal` carries the type constraint. The
compiler validates at compile time that the path resolves to an object whose type
conforms to the declared reference target type:

```rupa
type ISignal = ARElement {
    .length: PositiveInteger;
    .systemSignalRef: &SystemSignal;   // compiler checks target type
};

ISignal BrakeForce_I {
    .length = 12;
    .systemSignalRef = /Signals/BrakeForce;   // OK if BrakeForce is SystemSignal
    // .systemSignalRef = /DataTypes/Speed;    // ERROR: Speed is not SystemSignal
}
```

When exporting to ARXML, the compiler generates the correct `DEST` value from
the metamodel type information.

### IREF: `/>` Operator and `#[instance_ref]`

Instance references (IREF) are covered in detail by Pattern 03. In summary: the
`/>` path operator builds `::instance_ref` chains that narrow to specific
`#[instance_ref]` types at the point of assignment.

### REFERENCE-BASE: The `*` Search Anchor and Import Namespaces

AUTOSAR's `REFERENCE-BASE` mechanism solves two problems:

1. **Brevity** -- avoid repeating long absolute paths
2. **Portability** -- decouple references from the absolute location of packages

Rupa addresses both through existing language features:

**For brevity**, the `*` search anchor performs upward lookup through the
containment hierarchy, finding the nearest matching element without spelling out
the full path:

```rupa
// Instead of /AUTOSAR/SwComponentTypes/SpeedSensor
// when inside a sibling or descendant package:
.type = */SpeedSensor;
```

**For portability**, the `let`-captured import and variable-anchored paths
(`$name/path`) provide named bases:

```rupa
let types = import "component-types.rupa";

// Navigate from the captured base
SwComponentPrototype SensorInstance {
    .type = $types/SpeedSensor;
}
```

**For namespace organization**, `import ... as ns` provides named scopes for
expression-layer symbols while `let` captures model roots:

```rupa
let dtLib = import "data-types.rupa" as dt;

// Model content reachable via $dtLib
.dataType = $dtLib/Speed;

// Expression-layer functions via namespace
let custom = dt::createDataType("CustomSpeed");
```

The mapping between REFERENCE-BASE properties and Rupa features:

| REFERENCE-BASE property | Rupa equivalent |
|------------------------|-----------------|
| `SHORT-LABEL` (named base) | `let name = import "...";` or `let name = /path;` |
| `LONG-LABEL` (absolute path) | The imported file's model root, or an explicit path assignment |
| `IS-DEFAULT` (implicit base) | `*` search anchor (finds nearest match without naming a base) |
| Scope inheritance | Rupa's `let` bindings follow lexical scoping; `*` searches the containment tree |
| `BASE="name"` on references | `$name/relative/path` |

---

## Worked Example

### M2: Metamodel Definitions

```rupa
domain autosar;

type Identifiable = {
    #[id(0)]
    .shortName: ShortName;
};

#[abstract]
type ARElement = Identifiable {};

#[root]
type ARPackage = Identifiable {
    .elements: ARElement*;
    .subPackages: ARPackage*;
};

type SenderReceiverInterface = ARElement {
    .dataElements: VariableDataPrototype*;
};

type VariableDataPrototype = Identifiable {
    .type: &ApplicationDataType;
};

type ApplicationDataType = ARElement {};
type ApplicationPrimitiveDataType = ApplicationDataType {};

type SwComponentType = Identifiable {
    .ports: PortPrototype*;
};

type ApplicationSwComponentType = SwComponentType {};

type PortPrototype = Identifiable {
    .interface: &SenderReceiverInterface;   // REF equivalent
};

type PPortPrototype = PortPrototype {};

type SwComponentPrototype = Identifiable {
    #[archetype]
    .type: &SwComponentType;                // TREF equivalent
};

type CompositionSwComponentType = SwComponentType {
    .components: SwComponentPrototype*;
};
```

### M1: Model Instance

**ARXML** (with REFERENCE-BASE and all three reference kinds):

```xml
<AR-PACKAGE>
  <SHORT-NAME>AUTOSAR</SHORT-NAME>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>DataTypes</SHORT-NAME>
      <ELEMENTS>
        <APPLICATION-PRIMITIVE-DATA-TYPE>
          <SHORT-NAME>Speed</SHORT-NAME>
        </APPLICATION-PRIMITIVE-DATA-TYPE>
      </ELEMENTS>
    </AR-PACKAGE>
    <AR-PACKAGE>
      <SHORT-NAME>Interfaces</SHORT-NAME>
      <ELEMENTS>
        <SENDER-RECEIVER-INTERFACE>
          <SHORT-NAME>SpeedInterface</SHORT-NAME>
          <DATA-ELEMENTS>
            <VARIABLE-DATA-PROTOTYPE>
              <SHORT-NAME>SpeedValue</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE"
                >/AUTOSAR/DataTypes/Speed</TYPE-TREF>
            </VARIABLE-DATA-PROTOTYPE>
          </DATA-ELEMENTS>
        </SENDER-RECEIVER-INTERFACE>
      </ELEMENTS>
    </AR-PACKAGE>
    <AR-PACKAGE>
      <SHORT-NAME>Components</SHORT-NAME>
      <ADMIN-DATA>
        <SDGS>
          <SDG GID="AutosarStandardReferenceBase">
            <SD GID="SHORT-LABEL">Ifaces</SD>
            <SD GID="LONG-LABEL">/AUTOSAR/Interfaces</SD>
            <SD GID="IS-DEFAULT">true</SD>
          </SDG>
        </SDGS>
      </ADMIN-DATA>
      <ELEMENTS>
        <APPLICATION-SW-COMPONENT-TYPE>
          <SHORT-NAME>SpeedSensor</SHORT-NAME>
          <PORTS>
            <P-PORT-PROTOTYPE>
              <SHORT-NAME>SpeedPort</SHORT-NAME>
              <!-- Uses default REFERENCE-BASE: relative to /AUTOSAR/Interfaces -->
              <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
                >SpeedInterface</PROVIDED-INTERFACE-TREF>
            </P-PORT-PROTOTYPE>
          </PORTS>
        </APPLICATION-SW-COMPONENT-TYPE>
        <COMPOSITION-SW-COMPONENT-TYPE>
          <SHORT-NAME>TopComposition</SHORT-NAME>
          <COMPONENTS>
            <SW-COMPONENT-PROTOTYPE>
              <SHORT-NAME>Sensor</SHORT-NAME>
              <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
                >/AUTOSAR/Components/SpeedSensor</TYPE-TREF>
            </SW-COMPONENT-PROTOTYPE>
          </COMPONENTS>
        </COMPOSITION-SW-COMPONENT-TYPE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AR-PACKAGE>
```

**Rupa** (equivalent model):

```rupa
using domain autosar;

ARPackage AUTOSAR {
    ARPackage DataTypes {
        ApplicationPrimitiveDataType Speed {}
    }

    ARPackage Interfaces {
        SenderReceiverInterface SpeedInterface {
            VariableDataPrototype SpeedValue {
                .type = /AUTOSAR/DataTypes/Speed;      // TREF -> #[archetype] not needed here;
            }                                          // just a &ApplicationDataType reference
        }
    }

    ARPackage Components {
        ApplicationSwComponentType SpeedSensor {
            PPortPrototype SpeedPort {
                .interface = */SpeedInterface;          // REF: * search replaces REFERENCE-BASE
            }
        }

        CompositionSwComponentType TopComposition {
            SwComponentPrototype Sensor {
                .type = */SpeedSensor;                  // TREF: #[archetype] role
            }
        }
    }
}
```

### Key Observations

| Aspect | ARXML | Rupa |
|--------|-------|------|
| REF to interface | `<PROVIDED-INTERFACE-TREF DEST="...">SpeedInterface</...>` with `BASE` | `.interface = */SpeedInterface;` |
| TREF to type | `<TYPE-TREF DEST="...">path</TYPE-TREF>` | `.type = */SpeedSensor;` (role has `#[archetype]`) |
| REFERENCE-BASE setup | 7 lines of `ADMIN-DATA`/`SDGS`/`SDG` XML | Not needed -- `*` search or `let` binding |
| Relative path via BASE | `BASE="Ifaces">SpeedInterface` | `*/SpeedInterface` |
| DEST attribute | Required on every REF/TREF element | Absent -- type declared once in metamodel |
| IREF structure | Nested XML with CONTEXT + TARGET refs | `./Sensor/>SpeedPort` (see Pattern 03) |

---

## Edge Cases

### 1. REF vs. TREF Distinction in Round-Tripping

When exporting Rupa to ARXML, the serializer must decide whether to emit a
`<...-REF>` or a `<TYPE-TREF>` element. This is determined by the metamodel:

- Roles annotated with `#[archetype]` export as `TYPE-TREF`
- All other `&Type` reference roles export as the appropriate `*-REF` element

The element name (e.g., `SYSTEM-SIGNAL-REF`, `PROVIDED-INTERFACE-TREF`) is
derived from the AUTOSAR metamodel's XML binding metadata, not from Rupa syntax.
The Rupa-to-ARXML exporter must carry this metadata in the domain definition or
in ARXML-specific export annotations.

### 2. REFERENCE-BASE with Overlapping Scopes

AUTOSAR allows nested packages to override a parent's reference base by
declaring a new `REFERENCE-BASE` with the same `SHORT-LABEL`. This creates a
scope-shadowing effect.

In Rupa, `let` bindings follow lexical scoping. A nested block can shadow an
outer binding:

```rupa
let base = /AUTOSAR/Components;

ARPackage Outer {
    // $base resolves to /AUTOSAR/Components here
    .ref1 = $base/SpeedSensor;

    ARPackage Inner {
        let base = /AUTOSAR/Interfaces;    // shadows outer 'base'
        // $base resolves to /AUTOSAR/Interfaces here
        .ref2 = $base/SpeedInterface;
    }
}
```

However, Rupa's strict collision handling means that re-declaring `base` in the
same scope is an error. Shadowing only occurs across nested scopes, which is a
cleaner semantic than AUTOSAR's inheritance-with-override model.

### 3. The `*` Search Anchor and Ambiguity

The `*` anchor searches upward through containment. If multiple ancestors
contain a child with the matching identity, `*` finds the nearest one. This
parallels AUTOSAR's `IS-DEFAULT` reference base, which resolves from the
nearest enclosing package.

Ambiguity arises when the user expects a specific base but `*` finds a closer
match:

```rupa
ARPackage AUTOSAR {
    ARPackage Common {
        SystemSignal Speed { .length = 8; }       // common definition
    }
    ARPackage Vehicle {
        SystemSignal Speed { .length = 16; }      // domain-specific override

        ISignal VehicleSpeed_I {
            .systemSignalRef = */Speed;            // resolves to Vehicle/Speed (nearest)
            // To reach Common/Speed explicitly:
            .altRef = /AUTOSAR/Common/Speed;       // absolute path
        }
    }
}
```

This is a feature, not a bug -- `*` is intentionally nearest-first. When the
user needs a specific target, they use an absolute path or a `let`-bound base.

### 4. Absolute vs. Relative Paths in Imported Files

AUTOSAR's REFERENCE-BASE mechanism is critical for ARXML file portability:
references within a file use relative paths so the file can be relocated.

In Rupa, absolute paths in an imported file are relative to that file's subtree
root (per design decision 4.2.17), providing the same portability guarantee:

```rupa
// speed-components.rupa
// Absolute paths here are relative to THIS file's root, not the final model
ApplicationSwComponentType SpeedSensor {
    PPortPrototype SpeedPort {
        .interface = /Interfaces/SpeedInterface;   // within this file's subtree
    }
}
```

```rupa
// main-model.rupa
let components = import "speed-components.rupa";
/AUTOSAR/Components |= $components;
// The /Interfaces/SpeedInterface reference in speed-components.rupa
// resolves within the imported subtree, not in the outer model
```

Cross-subtree references require the `*` search anchor or explicit wiring at the
import site.

### 5. Dangling References Across File Boundaries

AUTOSAR tools commonly work with split ARXML files where references span file
boundaries. A `SYSTEM-SIGNAL-REF` in one file may target a `SYSTEM-SIGNAL` in
another file; resolution happens when all files are loaded.

In Rupa, the same behavior applies: references are resolved after the model is
fully built. Within a single compilation unit, dangling references produce
warnings. At link boundary (when all units are assembled), unresolved references
become errors. This matches the AUTOSAR toolchain's behavior of validating
references only when the complete model is available.

---

## Design Reference

| Feature | Design document |
|---------|----------------|
| `&Type` references and typed paths | `design/current/03-data-modeling/references-and-paths.md` |
| `#[archetype]` annotation (TREF equivalent) | `design/current/03-data-modeling/instance-references-and-archetypes.md` |
| `/>` operator and `#[instance_ref]` (IREF equivalent) | `design/current/03-data-modeling/instance-references-and-archetypes.md` |
| `*` search anchor | `design/current/03-data-modeling/references-and-paths.md` |
| `$` variable-anchored paths | `design/current/03-data-modeling/references-and-paths.md` |
| Import, `let`-capture, `import as` | `design/current/04-modularity/imports-and-dependencies.md` |
| Absolute paths in imported files | `design/current/04-modularity/imports-and-dependencies.md` (4.2.17) |
| Cross-role identity uniqueness | `design/current/03-data-modeling/cross-role-identity-uniqueness.md` |
| Forward and dangling reference resolution | `design/current/03-data-modeling/references-and-paths.md` |

### Related Patterns

- **Pattern 01**: Identifiable, SHORT-NAME-PATH, `#[id]`, and the `/` anchor.
- **Pattern 03**: Instance references (IREF), `/>` operator, `#[instance_ref]`.
- **Pattern 06**: Splitable and multi-file models -- interaction with cross-file references.

### AUTOSAR Specification Sources

- AUTOSAR CP R25-11, EXP Application Interfaces User Guide (Document ID 442),
  Sections 10.2.2 (References), 10.2.2.2 (Type References)
- AUTOSAR CP R25-11, TPS Generic Structure Template (Referrable, Identifiable,
  SHORT-NAME-PATH, REFERENCE-BASE)
- AUTOSAR CP R25-11, TPS Software Component Template (Document ID 62),
  Section 3.3 (Component Types and Prototypes), Appendix D (InstanceRef)
- AUTOSAR CP R25-11, SWS RTE (Document ID 84), Appendix F.4
  (Structure type with self-reference -- DATA_REFERENCE category)
