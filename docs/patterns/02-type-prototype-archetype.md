# Pattern 02: Type / Prototype / Archetype

The type/prototype pattern is the most fundamental structural pattern in AUTOSAR.
A **type** defines structure (ports, behavior, sub-elements); a **prototype** instantiates
that type within a containing context. The prototype does not contain the type's
children directly -- it holds a reference back to the type definition. This pattern
maps directly to Rupa's `#[archetype]` annotation and `/>` navigation operator.

---

## AUTOSAR Concept

### The AtpType / AtpPrototype M3 Pattern

At the AUTOSAR M3 (meta-metamodel) level, `AtpType` and `AtpPrototype` form a
universal type/instance pair:

- **`AtpType`** (also `AtpClassifier`): Defines available features -- ports,
  attributes, aggregated sub-elements.
- **`AtpPrototype`**: A named usage of an `AtpType` within some owning context.
  Carries an `isOfType` reference (`tref`) back to its type definition.

This pattern appears everywhere in the AUTOSAR metamodel:

| AtpType (defines structure) | AtpPrototype (instances it) | Owning Context |
|-----------------------------|----------------------------|----------------|
| `SwComponentType`           | `SwComponentPrototype`     | `CompositionSwComponentType` |
| `PortInterface`             | `PortPrototype`            | `SwComponentType` |
| `ApplicationDataType`       | `DataPrototype`            | `PortInterface` |
| `ModeDeclarationGroup`      | `ModeDeclarationGroupPrototype` | `ModeDeclarationGroupProvider` |

The critical point: a `SwComponentPrototype` does **not** contain port definitions.
It references a `SwComponentType` which owns the ports. To refer to "the SpeedPort
on the Sensor instance inside a composition," AUTOSAR uses **instance references**
(`IREF` / `AtpInstanceRef`) -- structured composite references that combine a
context chain with a target element.

### ARXML: Composition with Component Prototypes

The following ARXML shows a `CompositionSwComponentType` that aggregates two
`SwComponentPrototype` elements and connects their ports via an
`AssemblySwConnector`. Note how the connector's provider/requester use instance
references (`PROVIDER-IREF` / `R-PORT-IN-COMPOSITION-INSTANCE-REF`) to
identify a port *through* a component prototype.

```xml
<AR-PACKAGES>
  <!-- Interface definition -->
  <AR-PACKAGE>
    <SHORT-NAME>Interfaces</SHORT-NAME>
    <ELEMENTS>
      <SENDER-RECEIVER-INTERFACE>
        <SHORT-NAME>SpeedSensorSI</SHORT-NAME>
        <DATA-ELEMENTS>
          <VARIABLE-DATA-PROTOTYPE>
            <SHORT-NAME>SpeedValue</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE"
              >/DataTypes/Speed</TYPE-TREF>
          </VARIABLE-DATA-PROTOTYPE>
        </DATA-ELEMENTS>
      </SENDER-RECEIVER-INTERFACE>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- Component type definitions -->
  <AR-PACKAGE>
    <SHORT-NAME>Components</SHORT-NAME>
    <ELEMENTS>
      <APPLICATION-SW-COMPONENT-TYPE>
        <SHORT-NAME>SensorSWC</SHORT-NAME>
        <PORTS>
          <P-PORT-PROTOTYPE>
            <SHORT-NAME>SpeedPort</SHORT-NAME>
            <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
              >/Interfaces/SpeedSensorSI</PROVIDED-INTERFACE-TREF>
          </P-PORT-PROTOTYPE>
        </PORTS>
      </APPLICATION-SW-COMPONENT-TYPE>

      <APPLICATION-SW-COMPONENT-TYPE>
        <SHORT-NAME>ControllerSWC</SHORT-NAME>
        <PORTS>
          <R-PORT-PROTOTYPE>
            <SHORT-NAME>SpeedInput</SHORT-NAME>
            <REQUIRED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
              >/Interfaces/SpeedSensorSI</REQUIRED-INTERFACE-TREF>
          </R-PORT-PROTOTYPE>
        </PORTS>
      </APPLICATION-SW-COMPONENT-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- Composition: prototypes + connector with instance references -->
  <AR-PACKAGE>
    <SHORT-NAME>Compositions</SHORT-NAME>
    <ELEMENTS>
      <COMPOSITION-SW-COMPONENT-TYPE>
        <SHORT-NAME>BrakingSystem</SHORT-NAME>
        <COMPONENTS>
          <SW-COMPONENT-PROTOTYPE>
            <SHORT-NAME>Sensor</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
              >/Components/SensorSWC</TYPE-TREF>
          </SW-COMPONENT-PROTOTYPE>
          <SW-COMPONENT-PROTOTYPE>
            <SHORT-NAME>Controller</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
              >/Components/ControllerSWC</TYPE-TREF>
          </SW-COMPONENT-PROTOTYPE>
        </COMPONENTS>
        <CONNECTORS>
          <ASSEMBLY-SW-CONNECTOR>
            <SHORT-NAME>SpeedConnection</SHORT-NAME>
            <PROVIDER-IREF>
              <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                >Sensor</CONTEXT-COMPONENT-REF>
              <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE"
                >SpeedPort</TARGET-P-PORT-REF>
            </PROVIDER-IREF>
            <REQUESTER-IREF>
              <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                >Controller</CONTEXT-COMPONENT-REF>
              <TARGET-R-PORT-REF DEST="R-PORT-PROTOTYPE"
                >SpeedInput</TARGET-R-PORT-REF>
            </REQUESTER-IREF>
          </ASSEMBLY-SW-CONNECTOR>
        </CONNECTORS>
      </COMPOSITION-SW-COMPONENT-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

Key observations from the ARXML:

1. **`SW-COMPONENT-PROTOTYPE`** has a `TYPE-TREF` -- it does not re-declare ports.
2. **`PROVIDER-IREF`** and **`REQUESTER-IREF`** are structured instance references:
   each pairs a `CONTEXT-COMPONENT-REF` (the prototype) with a `TARGET-*-PORT-REF`
   (a port defined on the prototype's type).
3. The instance reference is a *composite value* -- not a simple path. It carries
   both "which instance" and "which element inside that instance's type."

---

## Rupa Mapping

### M2 Metamodel: Type Definitions

In Rupa, the AUTOSAR metamodel is expressed as M2 type definitions. The
type/prototype relationship is captured by `#[archetype]` on the prototype's
type-reference role.

```rupa
// M2: AUTOSAR metamodel fragment in Rupa

type SwComponentType = Identifiable {
    .ports: PortPrototype*;
};

type ApplicationSwComponentType = SwComponentType {};
type SensorActuatorSwComponentType = SwComponentType {};

type SwComponentPrototype = Identifiable {
    #[archetype]
    .type: &SwComponentType;
};

type CompositionSwComponentType = SwComponentType {
    .components: SwComponentPrototype*;
    .connectors: SwConnector*;
};

type PortPrototype = Identifiable {
    .interface: &PortInterface;
};

type PPortPrototype = PortPrototype {};
type RPortPrototype = PortPrototype {};

// Instance reference types for port-in-composition
#[instance_ref]
type PPortInCompositionInstanceRef {
    #[context]
    .contextComponent: &SwComponentPrototype;
    #[target]
    .targetPPort: &PPortPrototype;
};

#[instance_ref]
type RPortInCompositionInstanceRef {
    #[context]
    .contextComponent: &SwComponentPrototype;
    #[target]
    .targetRPort: &RPortPrototype;
};

type AssemblySwConnector = Identifiable {
    .provider: PPortInCompositionInstanceRef;
    .requester: RPortInCompositionInstanceRef;
};
```

### How `#[archetype]` Works

The `#[archetype]` annotation on `SwComponentPrototype.type` tells the Rupa
compiler:

- **This reference is the structural delegation link.** When someone navigates
  "into" a `SwComponentPrototype`, the structure they see comes from the target
  of `.type`, not from the prototype's own children.
- **At most one `#[archetype]` per type.** A prototype delegates to exactly one
  type definition.
- **Must be a required, single-valued reference** (`&T`). Optional or multi-valued
  archetype references are not permitted.

### How `/>` Works

The `/>` path operator performs **archetype identity navigation**: navigate to an
object, follow its archetype reference, then look up a named element inside the
archetype's structure.

Given the path `./Sensor/>SpeedPort`:

1. `./Sensor` -- standard identity navigation within the current scope. Resolves
   to the `SwComponentPrototype` named "Sensor."
2. `/>SpeedPort` -- archetype navigation:
   - Sensor's type has `#[archetype]` on `.type` -- follow it.
   - `.type` resolves to `SensorSWC` (an `ApplicationSwComponentType`).
   - Look up "SpeedPort" by identity inside `SensorSWC` -- found:
     `PPortPrototype SpeedPort`.
3. Result: `::instance_ref([Sensor, SpeedPort])`.
4. Assignment narrows the `::instance_ref` to the target M2 type
   (`PPortInCompositionInstanceRef`), validating that `Sensor` matches
   `#[context] .contextComponent: &SwComponentPrototype` and `SpeedPort`
   matches `#[target] .targetPPort: &PPortPrototype`.

---

## Worked Example

### M1 Model: A Braking System Composition

```rupa
using domain autosar;

// --- Interface ---

SenderReceiverInterface SpeedSensorSI {
    VariableDataPrototype SpeedValue {
        .type = /DataTypes/Speed;
    }
}

// --- Atomic component types (define ports) ---

ApplicationSwComponentType SensorSWC {
    PPortPrototype SpeedPort {
        .interface = /Interfaces/SpeedSensorSI;
    }
}

ApplicationSwComponentType ControllerSWC {
    RPortPrototype SpeedInput {
        .interface = /Interfaces/SpeedSensorSI;
    }
}

// --- Composition (instantiates components, wires ports) ---

CompositionSwComponentType BrakingSystem {
    SwComponentPrototype Sensor {
        .type = /Components/SensorSWC;
    }
    SwComponentPrototype Controller {
        .type = /Components/ControllerSWC;
    }

    AssemblySwConnector SpeedConnection {
        // />  navigates through archetype: prototype -> its type -> port
        .provider  = ./Sensor/>SpeedPort;
        .requester = ./Controller/>SpeedInput;
    }
}
```

### Side-by-Side Comparison

The connector definition is where the difference is most visible:

**ARXML** (11 lines, nested instance reference structure):
```xml
<ASSEMBLY-SW-CONNECTOR>
  <SHORT-NAME>SpeedConnection</SHORT-NAME>
  <PROVIDER-IREF>
    <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
      >Sensor</CONTEXT-COMPONENT-REF>
    <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE"
      >SpeedPort</TARGET-P-PORT-REF>
  </PROVIDER-IREF>
  <REQUESTER-IREF>
    <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
      >Controller</CONTEXT-COMPONENT-REF>
    <TARGET-R-PORT-REF DEST="R-PORT-PROTOTYPE"
      >SpeedInput</TARGET-R-PORT-REF>
  </REQUESTER-IREF>
</ASSEMBLY-SW-CONNECTOR>
```

**Rupa** (4 lines, inline archetype navigation):
```rupa
AssemblySwConnector SpeedConnection {
    .provider  = ./Sensor/>SpeedPort;
    .requester = ./Controller/>SpeedInput;
}
```

The `/>` operator encodes the same information as ARXML's `CONTEXT-COMPONENT-REF`
+ `TARGET-*-PORT-REF` pair, but as a readable path expression. The compiler
decomposes it into the `::instance_ref` chain and validates each step against the
`#[instance_ref]` type.

### Path Resolution Walkthrough

For `.provider = ./Sensor/>SpeedPort`:

| Step | Expression | Resolves To | Mechanism |
|------|-----------|-------------|-----------|
| 1 | `./Sensor` | `SwComponentPrototype "Sensor"` | Identity navigation within `BrakingSystem` |
| 2 | `/>SpeedPort` | `PPortPrototype "SpeedPort"` | Follow `Sensor.type` archetype to `SensorSWC`, find `SpeedPort` |
| 3 | (result) | `::instance_ref([Sensor, SpeedPort])` | M3 generic chain |
| 4 | (narrowing) | `PPortInCompositionInstanceRef` | Assignment to `.provider` validates types match |

### Deep Navigation: Nested Compositions

When compositions are nested (a `CompositionSwComponentType` contains prototypes
typed by other compositions), `/>` can be chained:

```rupa
CompositionSwComponentType VehicleSystem {
    SwComponentPrototype BrakingSubsystem {
        .type = /Compositions/BrakingSystem;
    }

    // Navigate two levels deep: subsystem -> component -> port
    // ./BrakingSubsystem  -->  BrakingSystem (composition type)
    //   />Sensor           -->  SwComponentPrototype inside BrakingSystem
    //   />SpeedPort        -->  PPortPrototype inside SensorSWC
    let sensorSpeed = ./BrakingSubsystem/>Sensor/>SpeedPort;
}
```

Each `/>` crosses one archetype boundary. The result is
`::instance_ref([BrakingSubsystem, Sensor, SpeedPort])` -- a three-element chain.

---

## Edge Cases

### 1. Circular Archetype Chains -- Compile Error

If type A has `#[archetype]` pointing to type B, and type B has `#[archetype]`
pointing to type A (directly or transitively), the compiler rejects it as a
static error on the type graph.

```rupa
// ERROR: circular archetype chain
type Foo = Identifiable {
    #[archetype]
    .ref: &Bar;
};

type Bar = Identifiable {
    #[archetype]
    .ref: &Foo;    // compile error: circular archetype chain Foo -> Bar -> Foo
};
```

This is a check on the M2 metamodel, not on M1 data. It prevents infinite `/>` chains.

### 2. Multiple Archetypes -- Not Supported

Each type may have at most one `#[archetype]` annotation. Attempting to declare two
is a compile error:

```rupa
// ERROR: multiple archetypes
type BadPrototype = Identifiable {
    #[archetype]
    .primary: &TypeA;
    #[archetype]
    .secondary: &TypeB;    // compile error: at most one #[archetype] per type
};
```

If a domain requires delegation to multiple sources, the model author must choose
which reference is the structural archetype and navigate the other explicitly via
standard role paths.

### 3. `::children` on a Prototype Returns the Prototype's Own Children

Tree navigation builtins operate on the containment tree, not the archetype's
structure:

```rupa
// ::children(./Sensor) returns SwComponentPrototype's own direct children
// (if any), NOT the ports of SensorSWC.
// To access archetype structure, use /> navigation.
let prototypeChildren = ::children(./Sensor);    // likely empty
let archetypePorts     = ./Sensor/>SpeedPort;     // navigates through archetype
```

This distinction is deliberate: `::children` reflects the physical containment
tree (what ARXML would show as nested elements under the prototype), while `/>` is
the semantic navigation through the type system.

### 4. `/>` Without `#[archetype]` -- Compile Error

Using `/>` on a path segment whose type does not declare `#[archetype]` is a
compile error:

```rupa
type PlainElement = Identifiable {
    .ref: &SomeType;    // no #[archetype] annotation
};

// ERROR: PlainElement has no #[archetype] role
let bad = ./SomePlainElement/>Child;
```

The compiler checks at each `/>` step that the left-hand side's type carries
`#[archetype]`. This makes the structural delegation explicit and prevents
accidental navigation through non-archetype references.

### 5. Optional vs. Required Archetype Reference

The `#[archetype]` reference must be required (`&T`), not optional (`&T?`). An
instance always has exactly one archetype. If an AUTOSAR element has a type
reference with multiplicity `0..1`, the M2 mapping must model it as required for
archetype purposes, or forgo `#[archetype]` and use explicit instance reference
construction instead.

---

## Design Reference

The complete specification of the archetype and instance reference mechanisms is in
the canonical design document:

**[Instance References and Archetypes](../../design/current/03-data-modeling/instance-references-and-archetypes.md)**

That document covers:

- `#[archetype]` semantics and constraints
- `/>` path operator resolution rules and precedence
- `::instance_ref` M3 type and narrowing to `#[instance_ref]` M2 types
- `#[instance_ref]`, `#[context]`, and `#[target]` annotations
- Interaction with tree builtins (`::children`, `::descendants`, `::references`)
- Full worked examples with multi-level archetype chains
- Alternatives considered and rationale for the chosen design

### Related AUTOSAR Specifications

- **AUTOSAR CP TPS Software Component Template** (AUTOSAR_CP_TPS_SoftwareComponentTemplate),
  Section 3.3.2 "SwComponentPrototype" and Section D "Modeling of InstanceRef" --
  defines the `SwComponentPrototype` role and `PPortInCompositionInstanceRef` /
  `RPortInCompositionInstanceRef` instance reference types.
- **AUTOSAR CP TPS System Template** (AUTOSAR_CP_TPS_SystemTemplate),
  Section 11.1 -- defines `CompositionSwComponentType` aggregation of components
  and connectors.
