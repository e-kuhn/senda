# Use Case 01: Component Architecture

This use case demonstrates how Rupa models an AUTOSAR software component
architecture: interface definitions, atomic component types with provide/require
ports, component prototypes instantiated inside a composition, and assembly
connectors wiring ports across instance boundaries. It exercises the
type/prototype/archetype pattern, instance references, and the `/>` navigation
operator.

---

## Scenario

A braking system composition contains two atomic software components -- a
**BrakeSensor** that provides brake pedal position data and a
**BrakeController** that consumes it. The components communicate through a
`SenderReceiverInterface`. An `AssemblySwConnector` wires the provider port on
the sensor to the requester port on the controller. A `DelegationSwConnector`
exposes the controller's diagnostic port to the composition's outer boundary.

---

## ARXML Baseline

The following abbreviated ARXML captures the full composition: interface, data
types, component types with ports, composition with prototypes and connectors.

```xml
<AR-PACKAGES>
  <!-- Data types -->
  <AR-PACKAGE>
    <SHORT-NAME>DataTypes</SHORT-NAME>
    <ELEMENTS>
      <APPLICATION-PRIMITIVE-DATA-TYPE>
        <SHORT-NAME>BrakePressure_T</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
      </APPLICATION-PRIMITIVE-DATA-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- Interfaces -->
  <AR-PACKAGE>
    <SHORT-NAME>Interfaces</SHORT-NAME>
    <ELEMENTS>
      <SENDER-RECEIVER-INTERFACE>
        <SHORT-NAME>BrakePressureSRI</SHORT-NAME>
        <DATA-ELEMENTS>
          <VARIABLE-DATA-PROTOTYPE>
            <SHORT-NAME>PedalForce</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE"
              >/DataTypes/BrakePressure_T</TYPE-TREF>
          </VARIABLE-DATA-PROTOTYPE>
        </DATA-ELEMENTS>
      </SENDER-RECEIVER-INTERFACE>
      <CLIENT-SERVER-INTERFACE>
        <SHORT-NAME>DiagServiceCSI</SHORT-NAME>
        <OPERATIONS>
          <CLIENT-SERVER-OPERATION>
            <SHORT-NAME>ReadStatus</SHORT-NAME>
          </CLIENT-SERVER-OPERATION>
        </OPERATIONS>
      </CLIENT-SERVER-INTERFACE>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- Atomic component types -->
  <AR-PACKAGE>
    <SHORT-NAME>SwComponents</SHORT-NAME>
    <ELEMENTS>
      <SENSOR-ACTUATOR-SW-COMPONENT-TYPE>
        <SHORT-NAME>BrakeSensor</SHORT-NAME>
        <PORTS>
          <P-PORT-PROTOTYPE>
            <SHORT-NAME>PedalOut</SHORT-NAME>
            <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
              >/Interfaces/BrakePressureSRI</PROVIDED-INTERFACE-TREF>
          </P-PORT-PROTOTYPE>
        </PORTS>
      </SENSOR-ACTUATOR-SW-COMPONENT-TYPE>

      <APPLICATION-SW-COMPONENT-TYPE>
        <SHORT-NAME>BrakeController</SHORT-NAME>
        <PORTS>
          <R-PORT-PROTOTYPE>
            <SHORT-NAME>PedalIn</SHORT-NAME>
            <REQUIRED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
              >/Interfaces/BrakePressureSRI</REQUIRED-INTERFACE-TREF>
          </R-PORT-PROTOTYPE>
          <P-PORT-PROTOTYPE>
            <SHORT-NAME>DiagPort</SHORT-NAME>
            <PROVIDED-INTERFACE-TREF DEST="CLIENT-SERVER-INTERFACE"
              >/Interfaces/DiagServiceCSI</PROVIDED-INTERFACE-TREF>
          </P-PORT-PROTOTYPE>
        </PORTS>
      </APPLICATION-SW-COMPONENT-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- Composition -->
  <AR-PACKAGE>
    <SHORT-NAME>Compositions</SHORT-NAME>
    <ELEMENTS>
      <COMPOSITION-SW-COMPONENT-TYPE>
        <SHORT-NAME>BrakingSystem</SHORT-NAME>
        <PORTS>
          <P-PORT-PROTOTYPE>
            <SHORT-NAME>DiagPort</SHORT-NAME>
            <PROVIDED-INTERFACE-TREF DEST="CLIENT-SERVER-INTERFACE"
              >/Interfaces/DiagServiceCSI</PROVIDED-INTERFACE-TREF>
          </P-PORT-PROTOTYPE>
        </PORTS>
        <COMPONENTS>
          <SW-COMPONENT-PROTOTYPE>
            <SHORT-NAME>Sensor</SHORT-NAME>
            <TYPE-TREF DEST="SENSOR-ACTUATOR-SW-COMPONENT-TYPE"
              >/SwComponents/BrakeSensor</TYPE-TREF>
          </SW-COMPONENT-PROTOTYPE>
          <SW-COMPONENT-PROTOTYPE>
            <SHORT-NAME>Controller</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
              >/SwComponents/BrakeController</TYPE-TREF>
          </SW-COMPONENT-PROTOTYPE>
        </COMPONENTS>
        <CONNECTORS>
          <ASSEMBLY-SW-CONNECTOR>
            <SHORT-NAME>PedalConnection</SHORT-NAME>
            <PROVIDER-IREF>
              <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                >Sensor</CONTEXT-COMPONENT-REF>
              <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE"
                >PedalOut</TARGET-P-PORT-REF>
            </PROVIDER-IREF>
            <REQUESTER-IREF>
              <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                >Controller</CONTEXT-COMPONENT-REF>
              <TARGET-R-PORT-REF DEST="R-PORT-PROTOTYPE"
                >PedalIn</TARGET-R-PORT-REF>
            </REQUESTER-IREF>
          </ASSEMBLY-SW-CONNECTOR>
          <DELEGATION-SW-CONNECTOR>
            <SHORT-NAME>DiagDelegation</SHORT-NAME>
            <INNER-PORT-IREF>
              <P-PORT-IN-COMPOSITION-INSTANCE-REF>
                <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                  >Controller</CONTEXT-COMPONENT-REF>
                <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE"
                  >DiagPort</TARGET-P-PORT-REF>
              </P-PORT-IN-COMPOSITION-INSTANCE-REF>
            </INNER-PORT-IREF>
            <OUTER-PORT-REF DEST="P-PORT-PROTOTYPE"
              >DiagPort</OUTER-PORT-REF>
          </DELEGATION-SW-CONNECTOR>
        </CONNECTORS>
      </COMPOSITION-SW-COMPONENT-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

The ARXML totals approximately 105 lines. Notable structural costs:

- Every element wrapped in `<SHORT-NAME>` child tags.
- Wrapper elements (`<AR-PACKAGES>`, `<ELEMENTS>`, `<PORTS>`, `<COMPONENTS>`,
  `<CONNECTORS>`, `<DATA-ELEMENTS>`, `<OPERATIONS>`) contribute no semantic
  content.
- Instance references (`PROVIDER-IREF`, `REQUESTER-IREF`,
  `P-PORT-IN-COMPOSITION-INSTANCE-REF`) require 4--6 lines each with redundant
  `DEST` attributes.
- The delegation connector's inner-port reference nests three levels deep.

---

## Rupa Solution

The equivalent Rupa model. The M2 metamodel types are assumed to be defined in
a domain library (see Pattern 02 for the type definitions); this is M1 instance
authoring only.

```rupa
// braking-system.rupa
using domain autosar;

// --- Data Types ---

ApplicationPrimitiveDataType BrakePressure_T {
    .category = "VALUE";
}

// --- Interfaces ---

SenderReceiverInterface BrakePressureSRI {
    VariableDataPrototype PedalForce {
        .type = /DataTypes/BrakePressure_T;
    }
}

ClientServerInterface DiagServiceCSI {
    ClientServerOperation ReadStatus {}
}

// --- Atomic Component Types ---

SensorActuatorSwComponentType BrakeSensor {
    PPortPrototype PedalOut {
        .interface = /Interfaces/BrakePressureSRI;
    }
}

ApplicationSwComponentType BrakeController {
    RPortPrototype PedalIn {
        .interface = /Interfaces/BrakePressureSRI;
    }
    PPortPrototype DiagPort {
        .interface = /Interfaces/DiagServiceCSI;
    }
}

// --- Composition ---

CompositionSwComponentType BrakingSystem {
    // Outer port: exposed to the composition's parent
    PPortPrototype DiagPort {
        .interface = /Interfaces/DiagServiceCSI;
    }

    // Component prototypes (instances of the atomic types)
    SwComponentPrototype Sensor {
        .type = /SwComponents/BrakeSensor;
    }
    SwComponentPrototype Controller {
        .type = /SwComponents/BrakeController;
    }

    // Assembly connector: sensor provides -> controller requires
    //   /> navigates through archetype: prototype -> its type -> port
    AssemblySwConnector PedalConnection {
        .provider  = ./Sensor/>PedalOut;
        .requester = ./Controller/>PedalIn;
    }

    // Delegation connector: inner port -> outer port
    DelegationSwConnector DiagDelegation {
        .innerPort = ./Controller/>DiagPort;
        .outerPort = ./DiagPort;
    }
}
```

### Path Resolution Walkthrough

For `.provider = ./Sensor/>PedalOut` inside the assembly connector:

| Step | Expression | Resolves To | Mechanism |
|------|-----------|-------------|-----------|
| 1 | `./Sensor` | `SwComponentPrototype "Sensor"` | Identity navigation within `BrakingSystem` |
| 2 | `/>PedalOut` | `PPortPrototype "PedalOut"` | Follow `Sensor.type` archetype to `BrakeSensor`, find `PedalOut` by identity |
| 3 | (result) | `::instance_ref([Sensor, PedalOut])` | Generic M3 chain |
| 4 | (narrowing) | `PPortInCompositionInstanceRef` | Assignment to `.provider` validates: `Sensor` matches `#[context]`, `PedalOut` matches `#[target]` |

For `.innerPort = ./Controller/>DiagPort` inside the delegation connector:

| Step | Expression | Resolves To | Mechanism |
|------|-----------|-------------|-----------|
| 1 | `./Controller` | `SwComponentPrototype "Controller"` | Identity navigation within `BrakingSystem` |
| 2 | `/>DiagPort` | `PPortPrototype "DiagPort"` | Follow `Controller.type` archetype to `BrakeController`, find `DiagPort` |
| 3 | (result) | `::instance_ref([Controller, DiagPort])` | Generic M3 chain |
| 4 | (narrowing) | `PPortInCompositionInstanceRef` | Assignment to `.innerPort` validates types |

For `.outerPort = ./DiagPort` -- this is standard identity navigation (no `/>`)
because the outer port is directly owned by the composition, not reached
through an archetype boundary.

### Compile-Time Error Detection

If the user accidentally wires the wrong port direction:

```rupa
AssemblySwConnector PedalConnection {
    .provider  = ./Controller/>PedalIn;   // ERROR
    .requester = ./Sensor/>PedalOut;      // ERROR
}
```

```
error[E0147]: instance reference type mismatch
  --> braking-system.rupa:52:20
   |
52 |     .provider  = ./Controller/>PedalIn;
   |                  ^^^^^^^^^^^^^^^^^^^^^^^^
   |                  target "PedalIn" is RPortPrototype
   |                  but .provider expects PPortInCompositionInstanceRef
   |                  (target must be PPortPrototype)
   |
   = help: did you mean ./Sensor/>PedalOut?
```

---

## Key Features Demonstrated

- **`#[archetype]` and `/>` operator**: `SwComponentPrototype` delegates structure
  to its `SwComponentType` via `#[archetype]` on `.type`. The `/>` operator
  crosses this boundary to reach ports defined on the type, producing
  `::instance_ref` chains that narrow to the appropriate `#[instance_ref]` M2
  type.

- **Typed references (`&Type`)**: Port interface references (`.interface =
  /Interfaces/BrakePressureSRI`) are compile-time typed. The `DEST` attribute
  from ARXML is unnecessary -- the metamodel declares `.interface: &PortInterface`
  and the compiler validates the target type.

- **Identity paths (`/`-delimited)**: Absolute paths like
  `/SwComponents/BrakeSensor` and relative paths like `./Sensor` use the same
  `#[id]`-based resolution. No wrapper elements participate in path navigation.

- **`#[instance_ref]` with `#[context]` and `#[target]`**: The
  `PPortInCompositionInstanceRef` and `RPortInCompositionInstanceRef` types
  encode the structured instance reference pattern. The compiler validates that
  each `/>` step matches the expected context and target types.

- **Containment role inference**: `PPortPrototype PedalOut { ... }` inside
  `SensorActuatorSwComponentType` infers assignment to the `.ports` role
  because `PPortPrototype` is a subtype of `PortPrototype` and `.ports` is the
  only containment role accepting that type.

- **Assembly vs. delegation connectors**: Both connector types use `/>` for
  inner port references, but delegation connectors also use standard identity
  navigation (`./DiagPort`) for the outer port that is directly owned by the
  composition.

---

## Comparison

| Aspect | ARXML | Rupa |
|--------|-------|------|
| **Total lines** (full example) | ~105 | ~48 |
| **Assembly connector** | 11 lines (nested IREF structure) | 4 lines (`/>` paths) |
| **Delegation connector** | 10 lines (nested IREF + outer ref) | 4 lines |
| **Port declaration** | 5 lines (SHORT-NAME + TREF + DEST) | 3 lines |
| **Reference typing** | `DEST` attribute on every reference (runtime) | `&Type` in metamodel (compile-time) |
| **Wrapper elements** | 7 distinct wrapper tags | None |
| **Instance reference encoding** | Explicit XML structure per IREF | `/>` operator decomposes automatically |
| **Error detection** | External schema validation | Compiler type checking with source locations |
| **Tooling support** | XML-generic (no domain awareness) | LSP with go-to-definition through `/>`, completion for port names |

The Rupa representation is roughly 55% shorter while preserving all semantic
information. The reduction comes primarily from eliminating XML wrapper elements,
collapsing `DEST`-attributed references into typed paths, and expressing instance
references as `/>` path chains instead of nested XML structures.

---

## Related Patterns

- **[Pattern 01: Identifiable and Paths](../patterns/01-identifiable-and-paths.md)** --
  `#[id]`, `/`-anchored paths, cross-role identity uniqueness
- **[Pattern 02: Type / Prototype / Archetype](../patterns/02-type-prototype-archetype.md)** --
  `#[archetype]`, `/>` operator, `SwComponentPrototype` / `SwComponentType` relationship
- **[Pattern 03: Instance References](../patterns/03-instance-references.md)** --
  `#[instance_ref]`, `#[context]`, `#[target]`, narrowing from `::instance_ref`
