# Pattern 06: atpSplitable and Multi-File Model Distribution

This pattern maps AUTOSAR's `atpSplitable` stereotype and Splitkey mechanism to
Rupa's multi-file composition and `|=` merge operator. It covers how an AUTOSAR
model can be distributed across multiple ARXML files with the same `ARPackage`
appearing in each, how Splitkey attributes define identity for merging, and how
Rupa handles the equivalent distributed-contribution workflow through explicit
imports and merge operations.

---

## AUTOSAR Concept

### The `atpSplitable` Stereotype

AUTOSAR's metamodel marks certain aggregation roles with the `<<atpSplitable>>`
stereotype. This declares that the contents of that aggregation can be **split
across multiple ARXML files** and merged back together by tooling. The AUTOSAR
spec states:

> *"ARPackages are open sets. This means that in a file based description system
> multiple files can be used to partially describe the contents of a package."*

The `atpSplitable` stereotype appears on three key aggregation roles of
`ARPackage`:

| Role | Type | Splitkey |
|------|------|----------|
| `ARPackage.arPackage` | `ARPackage *` | `arPackage.shortName` |
| `ARPackage.element` | `PackageableElement *` | `element.shortName` |
| `ARPackage.referenceBase` | `ReferenceBase *` | `referenceBase.shortLabel` |

The root `AUTOSAR` class similarly marks its `arPackage` role as `atpSplitable`
with Splitkey `arPackage.shortName`.

### Splitkey: The Merge Identity

The `atp.Splitkey` tagged value defines **which attribute(s) of the aggregated
element determine identity for merging**. When a tool loads multiple ARXML files,
it matches elements within a splitable aggregation by their Splitkey values:

- `ARPackage.arPackage` has Splitkey `arPackage.shortName` -- two sub-packages
  with the same `shortName` across different files are the same package and their
  contents are merged.
- `ARPackage.element` has Splitkey `element.shortName` -- two elements with the
  same `shortName` within the same logical package are the same element.

### Splitable Beyond Packages

The `atpSplitable` stereotype is not limited to packages. It appears throughout
the metamodel on aggregation roles that are expected to receive contributions from
multiple sources. Key examples:

| Class | Role | Splitkey |
|-------|------|----------|
| `AtomicSwComponentType` | `.internalBehavior` | `internalBehavior.shortName` |
| `SwcInternalBehavior` | `.event` | `event.shortName` |
| `SwcInternalBehavior` | `.runnable` (via `.entity`) | `entity.shortName` |
| `CompositionSwComponentType` | `.component` | `component.shortName` |
| `CompositionSwComponentType` | `.connector` | `connector.shortName` |
| `Identifiable` | `.adminData` | `adminData` |
| `Describable` | `.adminData` | `adminData` |

This means an `ApplicationSwComponentType` can have its port declarations in one
file and its `SwcInternalBehavior` (runnables, events) in a separate file. The
tool merges them by matching on `shortName`.

### ARXML Example: Two Files Contributing to One Package

**File 1: `swc-ports.arxml`** -- Defines the component type and its ports.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR xmlns="http://autosar.org/schema/r4.0">
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Powertrain</SHORT-NAME>
      <ELEMENTS>
        <APPLICATION-SW-COMPONENT-TYPE>
          <SHORT-NAME>EngineController</SHORT-NAME>
          <PORTS>
            <R-PORT-PROTOTYPE>
              <SHORT-NAME>EngineSpeed</SHORT-NAME>
              <REQUIRED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
                >/Interfaces/SRIf_EngineSpeed</REQUIRED-INTERFACE-TREF>
            </R-PORT-PROTOTYPE>
            <P-PORT-PROTOTYPE>
              <SHORT-NAME>ThrottleCmd</SHORT-NAME>
              <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE"
                >/Interfaces/SRIf_ThrottleCmd</PROVIDED-INTERFACE-TREF>
            </P-PORT-PROTOTYPE>
          </PORTS>
        </APPLICATION-SW-COMPONENT-TYPE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
```

**File 2: `swc-behavior.arxml`** -- Adds the internal behavior to the same
component.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR xmlns="http://autosar.org/schema/r4.0">
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Powertrain</SHORT-NAME>
      <ELEMENTS>
        <APPLICATION-SW-COMPONENT-TYPE>
          <SHORT-NAME>EngineController</SHORT-NAME>
          <INTERNAL-BEHAVIORS>
            <SWC-INTERNAL-BEHAVIOR>
              <SHORT-NAME>EngineController_IB</SHORT-NAME>
              <RUNNABLES>
                <RUNNABLE-ENTITY>
                  <SHORT-NAME>RE_ControlThrottle</SHORT-NAME>
                  <CAN-BE-INVOKED-CONCURRENTLY>false</CAN-BE-INVOKED-CONCURRENTLY>
                  <SYMBOL>RE_ControlThrottle</SYMBOL>
                </RUNNABLE-ENTITY>
              </RUNNABLES>
              <EVENTS>
                <TIMING-EVENT>
                  <SHORT-NAME>TE_ControlThrottle_10ms</SHORT-NAME>
                  <PERIOD>0.01</PERIOD>
                  <START-ON-EVENT-REF DEST="RUNNABLE-ENTITY"
                    >/Powertrain/EngineController/EngineController_IB/RE_ControlThrottle</START-ON-EVENT-REF>
                </TIMING-EVENT>
              </EVENTS>
            </SWC-INTERNAL-BEHAVIOR>
          </INTERNAL-BEHAVIORS>
        </APPLICATION-SW-COMPONENT-TYPE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
```

When an AUTOSAR tool loads both files:

1. Both declare `<AR-PACKAGE><SHORT-NAME>Powertrain</SHORT-NAME>`. The Splitkey
   is `arPackage.shortName`, so these merge into one `Powertrain` package.
2. Both contain `<APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>EngineController`.
   The Splitkey for `ARPackage.element` is `element.shortName`, so these merge
   into one `EngineController` component.
3. File 1 contributes ports. File 2 contributes `internalBehavior`. The
   `AtomicSwComponentType.internalBehavior` role is `atpSplitable` with Splitkey
   `internalBehavior.shortName`, so the behavior is added to the component.
4. The merged result is a single `EngineController` with both ports and behavior.

### What Is NOT Splitable

Not all aggregation roles carry `atpSplitable`. Single-valued non-splitable
roles (e.g., `SwComponentType.symbolProps` without the stereotype on some
classes) cannot be contributed from multiple files. If two files both set the
same non-splitable role on the same element, the result is a tool-specific error
or undefined behavior. The AUTOSAR Generic Structure Template (TPS) requires that
non-splitable content for a given element resides in exactly one file.

---

## Rupa Mapping

### Multi-File Composition via `|=`

Rupa's `|=` (merge) operator is the direct analog of AUTOSAR's splitable merge
semantics. Instead of implicit tool-level merging based on XML file loading
order, Rupa makes the merge explicit through import and merge statements:

```rupa
let ports = import "swc-ports.rupa";
let behavior = import "swc-behavior.rupa";

// Merge both contributions into the current model
/Powertrain |= $ports;
/Powertrain |= $behavior;
```

The merge algorithm uses identity-based matching (4.4.7): two objects match when
their identity contributors (as defined by the metamodel) are equal. For AUTOSAR
types that inherit from `Identifiable`, this means matching on `shortName` -- the
exact analog of the AUTOSAR Splitkey mechanism.

### Splitkey Maps to `#[id]`

| AUTOSAR mechanism | Rupa equivalent |
|-------------------|-----------------|
| `atp.Splitkey=element.shortName` | `#[id(0)]` on `.shortName` role |
| `atp.Splitkey=adminData` (singleton) | Singleton role matching (no identity key needed) |
| `atpSplitable` on aggregation role | All aggregation roles are implicitly mergeable via `\|=` |
| Implicit file-loading merge | Explicit `\|=` statements with import order |

A critical difference: in AUTOSAR, `atpSplitable` is a per-role opt-in. In Rupa,
**all** aggregation roles support merge via `|=`. The metamodel does not need to
declare splitability because the merge semantics are defined by the language, not
by the serialization format. Whether a role *should* be split across files is a
modeling convention, not a language constraint.

### Import Order Is Explicit

AUTOSAR tools typically process files in an unspecified or configuration-defined
order. The merge result should be order-independent for splitable elements (each
file contributes disjoint content to the same container). In Rupa, import order
is explicit and determines merge sequence:

```rupa
let base = import "base.rupa";
let overlay = import "overlay.rupa";

/Model |= $base;     // first
/Model |= $overlay;  // second -- in case of conflict, this is the "later" contribution
```

For non-conflicting contributions (the normal case for splitable elements), order
does not matter. For conflicting contributions, the `#[merge(...)]` annotation
controls resolution explicitly.

---

## Worked Example

### M2: Type Definitions (Metamodel Excerpt)

```rupa
domain autosar;

type Identifiable = {
    #[id(0)]
    .shortName: ShortName;
    .category: ShortName?;
    .adminData: AdminData?;
};

#[abstract]
type ARElement = Identifiable { };

#[root]
type ARPackage = Identifiable {
    .elements: ARElement*;
    .subPackages: ARPackage*;
};

// --- Interfaces ---

type SenderReceiverInterface = ARElement {
    .dataElements: VariableDataPrototype*;
};

type VariableDataPrototype = Identifiable {
    .typeRef: &ImplementationDataType;
};

// --- Software Component Types ---

type PortPrototype = Identifiable {
    .interfaceRef: &SenderReceiverInterface;
};

type RPortPrototype = PortPrototype { };
type PPortPrototype = PortPrototype { };

#[abstract]
type SwComponentType = ARElement {
    .ports: PortPrototype*;
};

#[abstract]
type AtomicSwComponentType = SwComponentType {
    .internalBehavior: SwcInternalBehavior?;
};

type ApplicationSwComponentType = AtomicSwComponentType { };

type SwcInternalBehavior = Identifiable {
    .runnables: RunnableEntity*;
    .events: RTEEvent*;
};

type RunnableEntity = Identifiable {
    .canBeInvokedConcurrently: ::boolean;
    .symbol: ::string;
};

#[abstract]
type RTEEvent = Identifiable { };

type TimingEvent = RTEEvent {
    .period: ::float;
    .startOnEventRef: &RunnableEntity;
};
```

### M1: File 1 -- `swc-ports.rupa` (Ports Contribution)

```rupa
using domain autosar;

ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .ports += RPortPrototype EngineSpeed {
            .interfaceRef = /Interfaces/SRIf_EngineSpeed;
        };
        .ports += PPortPrototype ThrottleCmd {
            .interfaceRef = /Interfaces/SRIf_ThrottleCmd;
        };
    }
}
```

### M1: File 2 -- `swc-behavior.rupa` (Behavior Contribution)

```rupa
using domain autosar;

ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .internalBehavior = SwcInternalBehavior EngineController_IB {
            .runnables += RunnableEntity RE_ControlThrottle {
                .canBeInvokedConcurrently = false;
                .symbol = "RE_ControlThrottle";
            };
            .events += TimingEvent TE_ControlThrottle_10ms {
                .period = 0.01;
                .startOnEventRef = /Powertrain/EngineController/EngineController_IB/RE_ControlThrottle;
            };
        };
    }
}
```

### M1: Composition File -- `system.rupa` (Merges Both)

```rupa
using domain autosar;

let ports = import "swc-ports.rupa";
let behavior = import "swc-behavior.rupa";

// Merge both contributions -- identity matching on shortName
/Powertrain |= $ports;
/Powertrain |= $behavior;
```

### Merge Resolution Walkthrough

When `system.rupa` is processed:

1. **`$ports` is merged into `/Powertrain`.**
   - `/Powertrain` does not yet exist in the current model. The merge creates it.
   - The `EngineController` component is added with its two ports.

2. **`$behavior` is merged into `/Powertrain`.**
   - `/Powertrain` already exists. Identity match on `shortName = "Powertrain"`.
   - Inside, `EngineController` already exists. Identity match on
     `shortName = "EngineController"`.
   - `EngineController` in `$behavior` contributes `.internalBehavior`. The
     existing `EngineController` has no `.internalBehavior` yet (it came from
     `$ports` which did not set this role). No conflict -- the behavior is added.
   - The ports from step 1 are preserved (merge preserves unmatched target items).

3. **Result:** A single `EngineController` component with:
   - Two ports: `EngineSpeed` (R-Port), `ThrottleCmd` (P-Port)
   - One internal behavior: `EngineController_IB` with one runnable and one event

### Alternative: Same-File Implicit Merge

If both contributions are in the same file, Rupa uses implicit merge (4.4.8):

```rupa
using domain autosar;

// First occurrence -- creates EngineController with ports
ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .ports += RPortPrototype EngineSpeed {
            .interfaceRef = /Interfaces/SRIf_EngineSpeed;
        };
        .ports += PPortPrototype ThrottleCmd {
            .interfaceRef = /Interfaces/SRIf_ThrottleCmd;
        };
    }
}

// Second occurrence -- adds behavior (implicit merge by identity)
ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .internalBehavior = SwcInternalBehavior EngineController_IB {
            .runnables += RunnableEntity RE_ControlThrottle {
                .canBeInvokedConcurrently = false;
                .symbol = "RE_ControlThrottle";
            };
        };
    }
}
```

Duplicate identity within the same file triggers implicit merge. The two
`ARPackage Powertrain` declarations combine, and the two `EngineController`
declarations combine. This is the closest analog to AUTOSAR's behavior of loading
multiple files into a single in-memory model.

---

## Edge Cases

### 1. Merge Conflicts on Single-Valued Roles

If both contributions set the same single-valued role on the same element,
the default `|=` behavior is `error`:

```rupa
// File A: sets .category on EngineController
ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .category = "APPLICATION";
    }
}

// File B: also sets .category on EngineController
ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .category = "SENSOR_ACTUATOR";
    }
}
```

```rupa
let a = import "file-a.rupa";
let b = import "file-b.rupa";

/Powertrain |= $a;
/Powertrain |= $b;  // ERROR: merge conflict on .category (single-valued)
                     // "APPLICATION" vs "SENSOR_ACTUATOR"
```

This is the Rupa equivalent of AUTOSAR's constraint that non-splitable content
for a given element must reside in exactly one file. To resolve:

```rupa
#[merge(conflict = { single = replace })]
/Powertrain |= $b;  // File B's .category wins
```

### 2. Non-Splitable Elements in AUTOSAR

AUTOSAR's `symbolProps` on `AtomicSwComponentType` does not carry `atpSplitable`
in all contexts. In ARXML, setting it in two files is undefined behavior. In
Rupa, the merge operator catches this as a conflict on a single-valued role,
providing a clear error rather than silent data loss or tool-specific behavior.

### 3. Splitkey With Compound Keys

Some AUTOSAR Splitkeys use compound values:

```
atp.Splitkey=arPackage.shortName, arPackage.variationPoint.shortLabel
```

This means identity matching considers both `shortName` and the variation point's
`shortLabel`. In Rupa, compound identity is expressed via multiple `#[id(N)]`
annotations:

```rupa
type ARPackage = Identifiable {
    #[id(0)]
    .shortName: ShortName;         // primary identity
    #[id(1)]
    .variationLabel: ShortName?;   // secondary identity contributor
    .elements: ARElement*;
    .subPackages: ARPackage*;
};
```

Two packages match only if both `shortName` and `variationLabel` are equal.

### 4. Order of Contributions

AUTOSAR's splitable semantics assume contributions are **disjoint** -- each file
adds new items to a collection, and no two files contribute the same leaf-level
data. When this assumption holds, merge order is irrelevant. When it does not
(e.g., two files both add a `RunnableEntity` with the same `shortName` but
different content), AUTOSAR behavior is tool-dependent.

Rupa makes this explicit: the `|=` operator has well-defined merge semantics for
every scenario. The default `conflict = { single = error }` surfaces violations
immediately rather than silently accepting the last-loaded file.

### 5. Splitting a Component Across Organizational Boundaries

A realistic AUTOSAR workflow has the OEM defining the component type and ports
while a supplier provides the internal behavior. Each party delivers an ARXML
file. In Rupa, this maps cleanly to the import/merge pattern:

```rupa
// oem-assembly.rupa
let oemTypes = import "oem/swc-types.rupa";
let supplierBehavior = import "supplier/swc-behavior.rupa";

/VehicleModel |= $oemTypes;
/VehicleModel |= $supplierBehavior;
```

The supplier never sees or modifies the OEM's file. Each party authors
independently, and the integration point explicitly merges them.

### 6. Deep Splitting: Behavior Runnables Across Files

`SwcInternalBehavior` roles like `.event` and `.runnable` are `atpSplitable`.
This means even the internals of a behavior can be split:

```rupa
// runnables.rupa
ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .internalBehavior = SwcInternalBehavior EngineController_IB {
            .runnables += RunnableEntity RE_ControlThrottle {
                .canBeInvokedConcurrently = false;
                .symbol = "RE_ControlThrottle";
            };
            .runnables += RunnableEntity RE_ReadSensors {
                .canBeInvokedConcurrently = true;
                .symbol = "RE_ReadSensors";
            };
        };
    }
}

// events.rupa
ARPackage Powertrain {
    ApplicationSwComponentType EngineController {
        .internalBehavior = SwcInternalBehavior EngineController_IB {
            .events += TimingEvent TE_ControlThrottle_10ms {
                .period = 0.01;
                .startOnEventRef = /Powertrain/EngineController/EngineController_IB/RE_ControlThrottle;
            };
            .events += TimingEvent TE_ReadSensors_5ms {
                .period = 0.005;
                .startOnEventRef = /Powertrain/EngineController/EngineController_IB/RE_ReadSensors;
            };
        };
    }
}
```

Both files contribute to the same `EngineController_IB`. The merge matches by
`shortName` at every level: package, component, behavior. Each file adds to
different collection roles (`.runnables` vs `.events`), so no conflict arises.

---

## Design Reference

| Feature | Design document |
|---------|----------------|
| File organization, `.rupa` extension, multi-definition files | `design/current/04-modularity/file-organization.md` |
| `\|=` merge operator, identity-based matching, merge depth | `design/current/04-modularity/model-composition.md` |
| `#[merge(...)]` annotation, conflict strategies | `design/current/04-modularity/model-composition.md` |
| `=`, `+=`, `\|=` operator semantics | `design/current/05-operations/modification-operations.md` |
| `#[id(N)]` identity mechanism | `design/current/03-data-modeling/object-node-structure.md` |
| Cross-role identity uniqueness | `design/current/03-data-modeling/cross-role-identity-uniqueness.md` |
| Import system, variable binding | `design/current/04-modularity/imports.md` |

### Related Patterns

- **Pattern 01**: Identifiable, Short Names, and Path Navigation -- covers the
  identity foundation that splitable merge depends on.
- **Pattern 02**: Type/Prototype/Archetype -- covers the component type system
  used in the worked examples.
