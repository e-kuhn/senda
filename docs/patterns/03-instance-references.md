# Pattern 03: Instance References

Instance references are one of the most distinctive mechanisms in the AUTOSAR metamodel. They solve a fundamental problem: how to reference a specific element *within the context of a specific instance* when the element is structurally defined elsewhere (in the archetype/type). This pattern document maps the AUTOSAR `AtpInstanceRef` mechanism to Rupa's `#[instance_ref]` types and `/>` path operator.

---

## AUTOSAR Concept

### The Problem: References Across Instance Boundaries

In AUTOSAR, a `SwComponentPrototype` (an instance) does not directly contain its ports. The ports belong to the `SwComponentType` (the archetype). When an `AssemblySwConnector` needs to reference "the `PPortPrototype` named `SpeedPort` as it appears in the `SwComponentPrototype` named `Sensor`," a simple SHORT-NAME-PATH reference is insufficient -- `SpeedPort` is not a child of `Sensor` in the containment tree.

AUTOSAR solves this with **instance references** (`AtpInstanceRef`): structured composite references that encode a navigation chain through instances to a target element in the archetype's structure.

### AtpInstanceRef Abstract Class

At the M3 level (Generic Structure Template), `AtpInstanceRef` defines two abstract associations:

- **`atpContextElement`** (ordered, 0..\*) -- an ordered chain of prototype/instance objects that form the navigation context
- **`atpTarget`** (0..1) -- the endpoint element in the archetype's structure

Concrete subclasses redefine these associations with specific types and multiplicities. Each subclass defines exactly which types serve as context elements and which type serves as the target.

### Key Concrete Subclasses

| Subclass | Context | Target | Used By |
|----------|---------|--------|---------|
| `PPortInCompositionInstanceRef` | `SwComponentPrototype` (0..1) | `AbstractProvidedPortPrototype` (0..1) | `AssemblySwConnector.provider` |
| `RPortInCompositionInstanceRef` | `SwComponentPrototype` (0..1) | `AbstractRequiredPortPrototype` (0..1) | `AssemblySwConnector.requester` |
| `ComponentInCompositionInstanceRef` | `SwComponentPrototype` (0..\*, ordered) | `SwComponentPrototype` (0..1) | Timing constraints, diagnostics |
| `VariableDataPrototypeInSystemInstanceRef` | `RootSwCompositionPrototype` (0..1), `SwComponentPrototype` (0..\*, ordered), `PortPrototype` (1) | `VariableDataPrototype` (0..1) | Signal-to-port mapping |

The last two illustrate an important characteristic: context chains can have **variable depth** (the `SwComponentPrototype` context is `0..*` ordered) and **multiple distinct context roles** (composition root, component chain, port).

### ARXML: Assembly Connector with Instance References

The following ARXML shows an `AssemblySwConnector` wiring a provider port to a requester port within a `CompositionSwComponentType`:

```xml
<COMPOSITION-SW-COMPONENT-TYPE>
  <SHORT-NAME>TopLevelComposition</SHORT-NAME>
  <COMPONENTS>
    <SW-COMPONENT-PROTOTYPE>
      <SHORT-NAME>Sensor</SHORT-NAME>
      <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE">/SwComponentTypes/SpeedSensor</TYPE-TREF>
    </SW-COMPONENT-PROTOTYPE>
    <SW-COMPONENT-PROTOTYPE>
      <SHORT-NAME>Controller</SHORT-NAME>
      <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE">/SwComponentTypes/EngineController</TYPE-TREF>
    </SW-COMPONENT-PROTOTYPE>
  </COMPONENTS>
  <CONNECTORS>
    <ASSEMBLY-SW-CONNECTOR>
      <SHORT-NAME>SpeedConn</SHORT-NAME>
      <PROVIDER-IREF>
        <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE">Sensor</CONTEXT-COMPONENT-REF>
        <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE">/SwComponentTypes/SpeedSensor/SpeedPort</TARGET-P-PORT-REF>
      </PROVIDER-IREF>
      <REQUESTER-IREF>
        <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE">Controller</CONTEXT-COMPONENT-REF>
        <TARGET-R-PORT-REF DEST="R-PORT-PROTOTYPE">/SwComponentTypes/EngineController/SpeedInput</TARGET-R-PORT-REF>
      </REQUESTER-IREF>
    </ASSEMBLY-SW-CONNECTOR>
  </CONNECTORS>
</COMPOSITION-SW-COMPONENT-TYPE>
```

Key structural properties of the ARXML:

- Each `*-IREF` element is a self-contained composite reference (not a simple path)
- `CONTEXT-COMPONENT-REF` identifies the instance (prototype) in the composition
- `TARGET-*-PORT-REF` identifies the structural element in the archetype (type)
- The `DEST` attribute provides type information for each reference within the chain
- The XML element ordering (`CONTEXT-COMPONENT-REF` before `TARGET-*-PORT-REF`) is governed by `xml.sequenceOffset` values in the metamodel

**Source**: AUTOSAR CP R25-11, TPS Software Component Template (Document ID 62), Section 3.3.3 (Connectors) and Appendix D.2.1 (Modeling of InstanceRef -- Components and Compositions).

---

## Rupa Mapping

Rupa maps AUTOSAR's instance reference mechanism using four complementary features:

### `#[instance_ref]` Type Annotation

Marks a type as a structured instance reference -- the Rupa equivalent of a concrete `AtpInstanceRef` subclass. The type's roles are divided into context, target, and non-chain roles using role-level annotations.

### `#[context]` Role Annotation

Marks a role as a context element in the delegation chain.

- **Declaration order defines traversal order.** The first `#[context]` role corresponds to the first `/>` step, the second to the second step, and so on. This replaces AUTOSAR's `xml.sequenceOffset` ordering.
- **Must reference a type with `#[archetype]`.** A context step requires an archetype to follow -- otherwise `/>` navigation has nowhere to go. Violation is a compile error.
- **May be multi-valued** (`&T+`, `&T*`) for variable-depth chains. When a context role is multi-valued, the chain can have a variable number of steps at that level. Multi-valued context roles are implicitly ordered.

### `#[target]` Role Annotation

Marks a role as the endpoint of the navigation chain.

- **Exactly one `#[target]` per `#[instance_ref]` type.** Multiple targets would be a different concept (use separate instance refs).
- **May reference any type** -- the target need not have `#[archetype]`. If it does, that archetype is not followed (the chain ends here).

### `::instance_ref` M3 Type

The generic chain type produced by `/>` path expressions. At the M3 level, `::instance_ref` is an ordered sequence of object references carrying no context/target distinction and no type constraints -- just the raw chain. Narrowing to a specific `#[instance_ref]` M2 type occurs at model contact (role assignment, typed `let`, function parameter, `as` cast).

### Non-Annotated Roles

Roles within an `#[instance_ref]` type that carry neither `#[context]` nor `#[target]` are **regular data** -- not part of the navigation chain. This is critical for AUTOSAR, where instance reference types inherit from base types (`ARObject`) that bring roles like `blueprintRef` and `extensionData`. These inherited roles must not be confused with the lookup chain.

### Metamodel Definitions (M2)

```rupa
// --- Supporting types ---

type SwComponentType {
    #[id]
    .shortName: ShortName;
    .ports: PortPrototype*;
}

type ApplicationSwComponentType = SwComponentType {}

type CompositionSwComponentType = SwComponentType {
    .components: SwComponentPrototype*;
    .connectors: SwConnector*;
}

type SwComponentPrototype {
    #[id]
    .shortName: ShortName;

    #[archetype]
    .type: &SwComponentType;
}

type PortPrototype {
    #[id]
    .shortName: ShortName;
}

type PPortPrototype = PortPrototype {}
type RPortPrototype = PortPrototype {}

// --- Instance reference types ---

#[instance_ref]
type PPortInCompositionInstanceRef {
    #[context]
    .contextComponent: &SwComponentPrototype;

    #[target]
    .targetPPort: &PPortPrototype;
}

#[instance_ref]
type RPortInCompositionInstanceRef {
    #[context]
    .contextComponent: &SwComponentPrototype;

    #[target]
    .targetRPort: &RPortPrototype;
}

type SwConnector {
    #[id]
    .shortName: ShortName;
}

type AssemblySwConnector = SwConnector {
    .provider: PPortInCompositionInstanceRef;
    .requester: RPortInCompositionInstanceRef;
}
```

### Instance Usage (M1) with `/>` Paths

```rupa
ApplicationSwComponentType SpeedSensor {
    PPortPrototype SpeedPort {}
}

ApplicationSwComponentType EngineController {
    RPortPrototype SpeedInput {}
}

CompositionSwComponentType TopLevelComposition {
    SwComponentPrototype Sensor {
        .type = /SwComponentTypes/SpeedSensor;
    }

    SwComponentPrototype Controller {
        .type = /SwComponentTypes/EngineController;
    }

    AssemblySwConnector SpeedConn {
        .provider  = ./Sensor/>SpeedPort;      // ::instance_ref -> narrows to PPortInCompositionInstanceRef
        .requester = ./Controller/>SpeedInput;  // ::instance_ref -> narrows to RPortInCompositionInstanceRef
    }
}
```

The `/>` operator at each step:

1. Resolves the left-hand side to an object whose type has `#[archetype]`
2. Follows the archetype reference to discover the archetype's children
3. Looks up the right-hand side name by identity in the archetype's structure
4. Records the step as part of the `::instance_ref` chain being built

---

## Worked Example

### Side-by-Side: ARXML vs. Rupa

The following shows the assembly connector portion of the model in both notations. The metamodel (M2) definitions above apply; here we focus on the M1 instance.

**ARXML** (35 lines for the connector alone):

```xml
<ASSEMBLY-SW-CONNECTOR>
  <SHORT-NAME>SpeedConn</SHORT-NAME>
  <PROVIDER-IREF>
    <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE">Sensor</CONTEXT-COMPONENT-REF>
    <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE">/SwComponentTypes/SpeedSensor/SpeedPort</TARGET-P-PORT-REF>
  </PROVIDER-IREF>
  <REQUESTER-IREF>
    <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE">Controller</CONTEXT-COMPONENT-REF>
    <TARGET-R-PORT-REF DEST="R-PORT-PROTOTYPE">/SwComponentTypes/EngineController/SpeedInput</TARGET-R-PORT-REF>
  </REQUESTER-IREF>
</ASSEMBLY-SW-CONNECTOR>
```

**Rupa** (4 lines for the connector):

```rupa
AssemblySwConnector SpeedConn {
    .provider  = ./Sensor/>SpeedPort;
    .requester = ./Controller/>SpeedInput;
}
```

### Path Resolution Walkthrough

For `.provider = ./Sensor/>SpeedPort`:

| Step | Expression | Action | Result |
|------|-----------|--------|--------|
| 1 | `./Sensor` | Identity navigation within `TopLevelComposition` | `SwComponentPrototype "Sensor"` |
| 2 | `/>SpeedPort` | `Sensor`'s type has `#[archetype]` on `.type` -- follow it to `/SwComponentTypes/SpeedSensor` | Look up `SpeedPort` by identity inside `SpeedSensor` |
| 3 | (end) | Chain complete | `::instance_ref([Sensor, SpeedPort])` |
| 4 | (narrowing) | Target role `.provider` has type `PPortInCompositionInstanceRef` | Validate: `Sensor` is `SwComponentPrototype` (matches `#[context] .contextComponent`) and `SpeedPort` is `PPortPrototype` (matches `#[target] .targetPPort`) |

For `.requester = ./Controller/>SpeedInput`:

| Step | Expression | Action | Result |
|------|-----------|--------|--------|
| 1 | `./Controller` | Identity navigation within `TopLevelComposition` | `SwComponentPrototype "Controller"` |
| 2 | `/>SpeedInput` | Follow archetype to `/SwComponentTypes/EngineController` | Look up `SpeedInput` by identity inside `EngineController` |
| 3 | (end) | Chain complete | `::instance_ref([Controller, SpeedInput])` |
| 4 | (narrowing) | Target role `.requester` has type `RPortInCompositionInstanceRef` | Validate: `Controller` is `SwComponentPrototype` (matches `#[context]`) and `SpeedInput` is `RPortPrototype` (matches `#[target]`) |

### Compiler Error Example

If the user accidentally swaps provider and requester:

```rupa
AssemblySwConnector SpeedConn {
    .provider  = ./Controller/>SpeedInput;  // ERROR
    .requester = ./Sensor/>SpeedPort;       // ERROR
}
```

The compiler rejects both assignments:

- `.provider` expects `PPortInCompositionInstanceRef` but `SpeedInput` is `RPortPrototype`, not `PPortPrototype` -- target type mismatch
- `.requester` expects `RPortInCompositionInstanceRef` but `SpeedPort` is `PPortPrototype`, not `RPortPrototype` -- target type mismatch

This type safety is enforced at compile time through the narrowing step, catching wiring errors that ARXML can only detect with external schema validation.

---

## Edge Cases

### 1. Multi-Valued Context for Variable-Depth Chains

Some AUTOSAR instance references have context chains of variable depth. `VariableDataPrototypeInSystemInstanceRef` is a representative example with multiple distinct context roles:

```
contextComposition:  RootSwCompositionPrototype (0..1)
contextComponent:    SwComponentPrototype       (0..*, ordered)
contextPort:         PortPrototype              (1)
targetDataPrototype: VariableDataPrototype       (0..1)
```

The `contextComponent` role has multiplicity `0..*` because the component nesting depth depends on how deeply compositions are nested.

In Rupa, this maps to a multi-valued `#[context]` role:

```rupa
#[instance_ref]
type VariableDataPrototypeInSystemInstanceRef {
    #[context]
    .contextComposition: &RootSwCompositionPrototype;

    #[context]
    .contextComponent: &SwComponentPrototype*;   // variable-depth chain

    #[context]
    .contextPort: &PortPrototype;

    #[target]
    .targetDataPrototype: &VariableDataPrototype;
}
```

Usage with `/>`:

```rupa
// Shallow: component directly in root composition
./RootComp/>Sensor/>SpeedPort/>SpeedSignal

// Deep: component nested inside a sub-composition
./RootComp/>SubAssembly/>Sensor/>SpeedPort/>SpeedSignal
```

Both resolve to `::instance_ref` chains of different lengths. During narrowing, the compiler maps the variable-length middle segment to the multi-valued `.contextComponent` role, validating that each element is a `SwComponentPrototype`.

### 2. Multiple M2 Types with Same Context Chain, Different Target Types

`PPortInCompositionInstanceRef` and `RPortInCompositionInstanceRef` share an identical context structure (`SwComponentPrototype`) but differ in their target type (`PPortPrototype` vs. `RPortPrototype`). The `/>` path expression produces the same `::instance_ref` chain structure for both.

Disambiguation happens entirely at narrowing: the assignment target's M2 type determines which instance ref type the chain must conform to. If both M2 types could accept the chain, the assignment context resolves the ambiguity.

```rupa
// Same syntax, different M2 type depending on assignment context
.provider  = ./Sensor/>SpeedPort;      // narrows to PPortInCompositionInstanceRef (SpeedPort is PPortPrototype)
.requester = ./Controller/>SpeedInput;  // narrows to RPortInCompositionInstanceRef (SpeedInput is RPortPrototype)
```

If the target element's type is ambiguous (e.g., a port type that is both `PPortPrototype` and `RPortPrototype` via inheritance), the assignment context (`.provider` vs. `.requester`) provides the definitive disambiguation.

### 3. Inherited Non-Lookup Roles from Base Types

In AUTOSAR, all types ultimately inherit from `ARObject`. Many `AtpInstanceRef` subclasses inherit roles like `AdminData`, extension slots, or annotation references. These are not part of the instance reference navigation chain.

In Rupa, only roles explicitly annotated with `#[context]` or `#[target]` participate in the chain. All other roles -- whether locally defined or inherited -- are treated as regular data:

```rupa
#[instance_ref]
type PPortInCompositionInstanceRef = ARObject {
    // Inherited from ARObject -- NOT part of navigation chain:
    //   .adminData: AdminData?;
    //   .annotations: Annotation*;

    #[context]
    .contextComponent: &SwComponentPrototype;

    #[target]
    .targetPPort: &PPortPrototype;
}
```

The `/>` path expression populates only `#[context]` and `#[target]` roles. Inherited roles like `.adminData` must be assigned independently if needed.

### 4. Bare `/>` Path Without Assignment Context

A `/>` path expression without an assignment context produces a value of M3 type `::instance_ref` -- not narrowed to any specific M2 type:

```rupa
let ref = ./Sensor/>SpeedPort;  // type: ::instance_ref (M3 level, not narrowed)
```

This is valid for passing to generic functions, storing in generically typed variables, or deferring type resolution. Narrowing occurs later when the value meets a typed context:

```rupa
let ref = ./Sensor/>SpeedPort;
.provider = ref;  // narrowing happens here: ::instance_ref -> PPortInCompositionInstanceRef
```

Without any narrowing context, `::instance_ref` values can still be compared, inspected via builtins, or passed to functions parameterized on `::instance_ref`.

### 5. The `base` / `atpDerived` Role

In AUTOSAR's metamodel, each `AtpInstanceRef` subclass has a `base` role (stereotyped `atpDerived`) that points to the containing type (e.g., `CompositionSwComponentType`). This role is automatically derived from the containment hierarchy and does not appear in the IREF XML elements.

In Rupa, this derived role is unnecessary -- the `/>` path already encodes the navigation from within the containing object. The base is implicitly the object in which the `/>` path is evaluated. This is one case where Rupa's path system eliminates a structural artifact of ARXML serialization.

---

## Design Reference

The canonical design document for instance references and archetypes is:

**[`design/current/03-data-modeling/instance-references-and-archetypes.md`](../../design/current/03-data-modeling/instance-references-and-archetypes.md)**

This document covers the full design rationale for:

- `#[archetype]` annotation and its constraints
- `/>` path operator syntax, resolution, and alternatives considered
- `::instance_ref` M3 type and the narrowing mechanism
- `#[instance_ref]`, `#[context]`, and `#[target]` annotations with validation rules
- Interaction with existing path operators, M3 type system, tree builtins, and validation rules

**AUTOSAR specification sources**:

- AUTOSAR CP R25-11, TPS Software Component Template (Document ID 62), Section 3.3.3 (Connectors), Appendix D (Modeling of InstanceRef)
- AUTOSAR CP R25-11, TPS System Template (Document ID 63), Appendix B (Detailed Representation of InstanceRef Associations)
- AUTOSAR CP R25-11, TPS Generic Structure Template (AtpInstanceRef, atpContextElement, atpTarget)
