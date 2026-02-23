# Pattern 11: FlatMap and Flat Instance Descriptors

The AUTOSAR FlatMap solves a pervasive problem in deeply nested software architectures: how to assign globally unique names to data elements buried inside composition hierarchies. This pattern document maps the FlatMap concept to Rupa's descendant navigation (`.**`), `::descendants` builtin, and transformation functions for generating flat representations from hierarchical models.

---

## AUTOSAR Concept

### The Problem: Unique Names for MCD Tooling

AUTOSAR software architectures are deeply hierarchical. A `VariableDataPrototype` representing a measurable signal lives inside a `PortInterface`, which is referenced by a `PortPrototype`, which belongs to an `SwComponentType`, which is instantiated as an `SwComponentPrototype` inside a `CompositionSwComponentType`, which may itself be nested inside further compositions. MCD (Measurement, Calibration, and Diagnostics) tools -- particularly A2L file generators -- need a single flat name for each such data element that is unique within the scope of an ECU.

There is no AUTOSAR model element called "software signal." Instead, software signals are represented by instance references (`InstanceRef`) to an `AutosarDataPrototype`. The FlatMap provides the missing flat namespace by collecting `FlatInstanceDescriptor` elements, each assigning a globally unique `shortName` to one specific node in the instance tree.

### FlatMap Class

`FlatMap` is an `ARElement` (identifiable, packageable) that aggregates a list of `FlatInstanceDescriptor` instances. Its scope is determined by the `RootSwCompositionPrototype` it is associated with -- typically the top-level composition of a system description, system extract, or ECU extract.

Key properties of `FlatMap`:

| Property | Type | Description |
|----------|------|-------------|
| `shortName` | `Identifier` | Identity of the FlatMap itself |
| `instance` | `FlatInstanceDescriptor*` | Collection of flat descriptors (splitable, variable) |

The aggregation is marked `atpSplitable` because FlatMap content may be contributed by different stakeholders at different workflow stages, and the overall size can be large enough to warrant distribution across multiple files.

### FlatInstanceDescriptor Class

Each `FlatInstanceDescriptor` represents exactly one node in the instance tree and assigns a unique name to it:

| Property | Type | Description |
|----------|------|-------------|
| `shortName` | `Identifier` | The unique flat name (e.g., `Eng_n`) |
| `upstreamReferenceIref` | `InstanceRef` | Structured reference to the target element through context chain |

The `upstreamReferenceIref` is an instance reference containing:

- **Context elements**: An ordered chain of `CONTEXT-ELEMENT-REF` entries (root composition, component prototypes, port prototypes) that trace the path from the composition root down to the target
- **Target reference**: A `TARGET-REF` pointing to the actual data prototype in the archetype

Use cases for `FlatInstanceDescriptor`:

- Specify unique names for measurable data (used by MCD tools)
- Specify unique names for calibration parameters (used by MCD tools)
- Specify unique names for component prototype instances in flattened compositions
- Provide stable identifiers for A2L file generation (mapping `shortName` to `MEASUREMENT` or `CHARACTERISTIC` names)

### ARXML Example

The following ARXML shows a FlatMap with descriptors for an engine speed signal and an array element:

```xml
<AR-PACKAGE>
  <SHORT-NAME>OEM1</SHORT-NAME>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>FlatMaps</SHORT-NAME>
      <ELEMENTS>
        <FLAT-MAP>
          <SHORT-NAME>EcuFlatMap</SHORT-NAME>
          <INSTANCES>
            <!-- Scalar signal: unique name "Eng_n" -->
            <FLAT-INSTANCE-DESCRIPTOR>
              <SHORT-NAME>Eng_n</SHORT-NAME>
              <UPSTREAM-REFERENCE-IREF>
                <CONTEXT-ELEMENT-REF DEST="ROOT-SW-COMPOSITION-PROTOTYPE"
                  >/OEM1/Systems/System/TopLvl</CONTEXT-ELEMENT-REF>
                <CONTEXT-ELEMENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                  >/OEM1/SwComponentTypes/TopLvl/Eng</CONTEXT-ELEMENT-REF>
                <CONTEXT-ELEMENT-REF DEST="PORT-PROTOTYPE"
                  >/OEM1/SwComponentTypes/Eng/EngN</CONTEXT-ELEMENT-REF>
                <TARGET-REF DEST="VARIABLE-DATA-PROTOTYPE"
                  >/OEM1/PortInterfaces/EngN1/EngN</TARGET-REF>
              </UPSTREAM-REFERENCE-IREF>
            </FLAT-INSTANCE-DESCRIPTOR>

            <!-- Array element: index qualifier for first element -->
            <FLAT-INSTANCE-DESCRIPTOR>
              <SHORT-NAME>Esc_vWhlInd_0</SHORT-NAME>
              <UPSTREAM-REFERENCE-IREF>
                <CONTEXT-ELEMENT-REF DEST="ROOT-SW-COMPOSITION-PROTOTYPE"
                  >/OEM1/Systems/System/TopLvl</CONTEXT-ELEMENT-REF>
                <CONTEXT-ELEMENT-REF DEST="SW-COMPONENT-PROTOTYPE"
                  >/OEM1/SwComponentTypes/TopLvl/Pt</CONTEXT-ELEMENT-REF>
                <CONTEXT-ELEMENT-REF DEST="PORT-PROTOTYPE"
                  >/OEM1/SwComponentTypes/Pt/EscVWhlInd</CONTEXT-ELEMENT-REF>
                <CONTEXT-ELEMENT-REF DEST="VARIABLE-DATA-PROTOTYPE"
                  >/OEM1/PortInterfaces/WhlSpdCircuml1/WhlSpdCircuml</CONTEXT-ELEMENT-REF>
                <TARGET-REF DEST="APPLICATION-ARRAY-ELEMENT" INDEX="0"
                  >/OEM1/ApplicationDataTypes/WhlSpdCircumlPerWhl1</TARGET-REF>
              </UPSTREAM-REFERENCE-IREF>
            </FLAT-INSTANCE-DESCRIPTOR>
          </INSTANCES>
        </FLAT-MAP>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AR-PACKAGE>
```

Key structural properties:

- Each `FLAT-INSTANCE-DESCRIPTOR` is essentially a named wrapper around an instance reference
- The `UPSTREAM-REFERENCE-IREF` follows the standard `AtpInstanceRef` pattern (ordered context chain + target)
- Array elements use the `INDEX` attribute on `TARGET-REF` to distinguish individual elements
- The `shortName` of each descriptor becomes the display name in MCD tools and A2L files

**Sources**: AUTOSAR CP R25-11, TPS System Template (FlatMap, FlatInstanceDescriptor classes); TR Modeling and Naming Aspects for Documentation, Measurement, and Calibration (Document ID 537), Section 6.2; SWS RTE (Document ID 84), Section 4.2.9.4; TR Methodology (System Flat Map artifact).

---

## Rupa Mapping

The FlatMap pattern involves two distinct Rupa capabilities: (1) navigating hierarchical models to discover all elements that need flat names, and (2) generating the flat descriptor objects that assign those names.

### Descendant Navigation for Discovery

Rupa's `.**` operator and `::descendants` builtin provide the discovery mechanism. Where AUTOSAR requires manually curating a list of `FlatInstanceDescriptor` entries (or generating them via tooling), Rupa can traverse the composition tree programmatically:

```rupa
// Find all variable data prototypes reachable from the root composition
let measurables = /Systems/System/TopLvl.**<VariableDataPrototype>;

// Same traversal via builtin form, composable with pipes
let calibratables = ::descendants(/Systems/System/TopLvl)
    | filter(x => x is ParameterDataPrototype);
```

The `.**` operator follows containment edges only (never references), which matches the FlatMap's scope: it flattens the containment hierarchy of the composition, not the reference graph. The self-exclusion rule ensures the root composition itself is not included in the results.

### Type-Filtered Descent with Predicates

The `.**<Type>[pred]` syntax combines type filtering and predicate filtering in a single step:

```rupa
// All measurable signals on a specific bus
let can_signals = rootComp.**<VariableDataPrototype>[
    ::ancestors(.) | any(a => a is PortPrototype && a.interface.bus == "CAN")
];
```

### Transform Functions for FlatMap Generation

Generating the FlatMap itself -- creating `FlatInstanceDescriptor` objects with unique names from the hierarchical structure -- is a transformation concern. A `#[transform]` function walks the source composition and produces flat descriptors in the target:

```rupa
#[transform]
let flatten_composition(root: source::RootSwCompositionPrototype) {
    FlatMap (root.shortName + "_FlatMap") {
        // Traverse all variable data prototypes in the composition
        root.**<source::VariableDataPrototype> | each(vdp => {
            let flat_name = build_flat_name(vdp);
            FlatInstanceDescriptor (flat_name) {
                .upstreamRef = build_instance_ref(vdp, root);
            };
        });
    };
}
```

### Name Generation via Ancestor Traversal

The unique flat name is constructed by walking the ancestor chain -- another use of tree builtins:

```rupa
let build_flat_name(vdp: VariableDataPrototype): String =
    ::ancestors(vdp)
    | filter(a => a is SwComponentPrototype || a is PortPrototype)
    | reverse()
    | map(a => a.shortName)
    | join("_")
    + "_" + vdp.shortName;
```

This produces names like `Eng_EngN_EngN` by concatenating the component prototype name, port name, and data element name -- matching the naming convention AUTOSAR recommends for A2L generation.

---

## Worked Example

### Scenario

An OEM has a top-level composition containing an engine management component. The engine component exposes a speed measurement (`EngN`) through a sender-receiver port. The goal is to generate a FlatMap assigning the display name `Eng_n` to this signal.

### Side-by-Side: ARXML vs. Rupa

**ARXML** -- The FlatMap with one descriptor (20+ lines of XML):

```xml
<FLAT-MAP>
  <SHORT-NAME>EcuFlatMap</SHORT-NAME>
  <INSTANCES>
    <FLAT-INSTANCE-DESCRIPTOR>
      <SHORT-NAME>Eng_n</SHORT-NAME>
      <UPSTREAM-REFERENCE-IREF>
        <CONTEXT-ELEMENT-REF DEST="ROOT-SW-COMPOSITION-PROTOTYPE"
          >/OEM1/Systems/System/TopLvl</CONTEXT-ELEMENT-REF>
        <CONTEXT-ELEMENT-REF DEST="SW-COMPONENT-PROTOTYPE"
          >/OEM1/SwComponentTypes/TopLvl/Eng</CONTEXT-ELEMENT-REF>
        <CONTEXT-ELEMENT-REF DEST="PORT-PROTOTYPE"
          >/OEM1/SwComponentTypes/Eng/EngN</CONTEXT-ELEMENT-REF>
        <TARGET-REF DEST="VARIABLE-DATA-PROTOTYPE"
          >/OEM1/PortInterfaces/EngN1/EngN</TARGET-REF>
      </UPSTREAM-REFERENCE-IREF>
    </FLAT-INSTANCE-DESCRIPTOR>
  </INSTANCES>
</FLAT-MAP>
```

**Rupa** -- Metamodel excerpt and instance:

```rupa
// --- Metamodel (M2) ---

type FlatMap {
    #[id]
    .shortName: ShortName;
    .instances: FlatInstanceDescriptor*;
}

#[instance_ref]
type UpstreamReferenceIref {
    #[context]
    .contextComposition: &RootSwCompositionPrototype;

    #[context]
    .contextComponent: &SwComponentPrototype*;

    #[context]
    .contextPort: &PortPrototype;

    #[target]
    .targetDataPrototype: &AutosarDataPrototype;
}

type FlatInstanceDescriptor {
    #[id]
    .shortName: ShortName;
    .upstreamRef: UpstreamReferenceIref;
}
```

```rupa
// --- Instance (M1) ---

FlatMap EcuFlatMap {
    FlatInstanceDescriptor Eng_n {
        .upstreamRef = ./TopLvl/>Eng/>EngN/>EngN;
    }
}
```

The `/>` instance reference path `./TopLvl/>Eng/>EngN/>EngN` encodes the same four-step chain as the ARXML's four `CONTEXT-ELEMENT-REF` + `TARGET-REF` entries, in a single line.

### Generating a FlatMap via Transformation

When the FlatMap must be generated from an existing composition rather than hand-authored, the transformation system handles it:

```rupa
using domain autosar-cp;
using domain autosar-cp as source;

// Phase 1: Generate FlatMap structure from composition tree
#[transform]
let generate_flat_map(root: source::RootSwCompositionPrototype) {
    FlatMap (root.shortName + "_FlatMap") {
        // Descend through all component instances to find data prototypes
        root.**<source::SwComponentPrototype> | each(comp => {
            let comp_type = comp.type;   // follow archetype to get ports

            comp_type.ports | each(port => {
                port.interface.dataElements | each(vdp => {
                    let flat_name = comp.shortName + "_" + port.shortName
                                    + "_" + vdp.shortName;

                    FlatInstanceDescriptor (flat_name) {
                        // Build the instance reference through the chain
                        .upstreamRef = $root/>$comp/>$port/>$vdp;
                    };
                });
            });
        });
    };
}

// Phase 2: Resolve alias names from existing naming conventions
#[transform(phase = 2)]
let assign_alias_names(root: source::RootSwCompositionPrototype) {
    let flat_map = ::targets(root) | filter(x => x is FlatMap) | first;

    flat_map.instances | each(desc => {
        // Check if a PartialFlatMap provided a preferred name
        let partial_match = root.**<source::FlatInstanceDescriptor>
            [.upstreamRef == desc.upstreamRef];

        if partial_match | count() > 0 then {
            desc.aliasName = (partial_match | first).shortName;
        };
    });
}
```

### Resolution Walkthrough

For the `/>` path `./TopLvl/>Eng/>EngN/>EngN`:

| Step | Expression | Action | Result |
|------|-----------|--------|--------|
| 1 | `./TopLvl` | Identity navigation to `RootSwCompositionPrototype` | `TopLvl` (has `#[archetype]` on `.type`) |
| 2 | `/>Eng` | Follow archetype to composition type, find `Eng` | `SwComponentPrototype "Eng"` |
| 3 | `/>EngN` | Follow archetype to `SpeedSensor` type, find port `EngN` | `PortPrototype "EngN"` |
| 4 | `/>EngN` | Follow archetype to `EngN1` interface, find element `EngN` | `VariableDataPrototype "EngN"` |
| 5 | (narrowing) | Assignment to `.upstreamRef` of type `UpstreamReferenceIref` | Validate chain against `#[context]`/`#[target]` roles |

---

## Edge Cases

### 1. Array Elements Requiring Index Qualifiers

AUTOSAR uses the `INDEX` attribute on `TARGET-REF` to reference individual array elements. In Rupa, array indexing in paths uses the `[N]` predicate syntax:

```rupa
// ARXML: <TARGET-REF DEST="APPLICATION-ARRAY-ELEMENT" INDEX="0">...</TARGET-REF>
// Rupa: index via path predicate
FlatInstanceDescriptor Esc_vWhlInd_0 {
    .upstreamRef = ./TopLvl/>Pt/>EscVWhlInd/>WhlSpdCircuml/>WhlSpdCircumlPerWhl1[0];
}
```

The `[0]` predicate on the final path step resolves to the first array element, matching the `INDEX="0"` attribute in ARXML. This integrates with Rupa's collection indexing in paths (0-based, negative wraps, Python slicing semantics).

### 2. Partial FlatMaps and Merging

AUTOSAR supports delivering `PartialFlatMap` artifacts alongside software components, which must later be merged into the system-level FlatMap. Name conflicts must be resolved during merging. In Rupa, this maps to the `atpSplitable` import pattern combined with validation:

```rupa
import "component_a_flatmap.rupa";    // contributes partial descriptors
import "component_b_flatmap.rupa";    // contributes partial descriptors

// Validation rule: no duplicate flat names within a FlatMap
#[rule(autosar::flatmap::unique_names)]
let no_duplicate_flat_names() =
    (. is FlatMap) ->
        .instances | map(d => d.shortName) | is_unique();
```

### 3. Variable-Depth Composition Nesting

The `.**` operator handles variable-depth nesting naturally. When compositions contain sub-compositions, the flat name generator must traverse all levels:

```rupa
// Works regardless of nesting depth
root.**<SwComponentPrototype> | each(comp => {
    // comp may be at depth 1, 2, or N in the composition hierarchy
    let depth_prefix = ::ancestors(comp)
        | filter(a => a is SwComponentPrototype)
        | map(a => a.shortName)
        | join("_");
    // ...
});
```

The `::ancestors` builtin returns parents ordered closest-to-furthest, so `reverse()` is needed for top-down name construction. The `.**` operator's DFS pre-order traversal ensures that parent compositions are visited before their children, which matters when building name prefixes incrementally.

### 4. FlatMap Scope and Multiple Root Compositions

A FlatMap is scoped to one `RootSwCompositionPrototype`. A system with multiple ECU extracts may have multiple FlatMaps, each scoped differently. The `.**` traversal naturally respects scope because it starts from a specific root:

```rupa
// ECU-specific flat maps derived from different root compositions
let ecu1_map = generate_flat_map(/Systems/System/Ecu1Root);
let ecu2_map = generate_flat_map(/Systems/System/Ecu2Root);
```

Each invocation traverses only the containment subtree of its root, producing a correctly scoped FlatMap.

### 5. Manually Maintained vs. Auto-Generated Names

AUTOSAR explicitly supports a mix of manually maintained and auto-generated flat names (the `atpSplitable` stereotype enables this). In Rupa, the transformation approach handles this by checking for pre-existing descriptors before generating new ones:

```rupa
// Only generate a descriptor if no manual one exists
if !(existing_map.instances | any(d => d.upstreamRef == ref)) then {
    FlatInstanceDescriptor (auto_name) {
        .upstreamRef = ref;
    };
};
```

---

## Design Reference

The Rupa features used in this pattern are specified in:

- **Descendant navigation (`.**`)**: [`design/current/03-data-modeling/references-and-paths.md`](../../design/current/03-data-modeling/references-and-paths.md) -- Wildcard Navigation section. Covers `.**<Type>[pred]` syntax, self-exclusion rule, containment-only traversal, and pipe integration.

- **Tree builtins (`::descendants`, `::ancestors`, `::root`)**: Same document, Tree Navigation Builtins section. `::descendants` returns all transitively contained objects in DFS pre-order; `::ancestors` returns all parents from closest to furthest.

- **Instance references (`/>`)**: [`design/current/03-data-modeling/instance-references-and-archetypes.md`](../../design/current/03-data-modeling/instance-references-and-archetypes.md) -- Covers `/>` path operator, `#[instance_ref]`, `#[context]`, `#[target]`, and `::instance_ref` M3 type.

- **Transformation functions (`#[transform]`)**: [`design/current/08-transformation/transformation-language.md`](../../design/current/08-transformation/transformation-language.md) -- Sections 8.2 (transform functions, `::transform` statement, write mode) and 8.3 (multi-phase transforms, `::targets` for cross-reference resolution in Phase 2+).

- **Collection indexing in paths (`[N]`)**: [`design/current/03-data-modeling/collection-indexing-in-paths.md`](../../design/current/03-data-modeling/collection-indexing-in-paths.md) -- 0-based indexing, negative wrap, Python slice semantics.

**AUTOSAR specification sources**:

- AUTOSAR CP R25-11, TPS System Template -- `FlatMap` and `FlatInstanceDescriptor` class definitions, System Flat Map and ECU Flat Map artifacts
- AUTOSAR CP R25-11, TR Modeling and Naming Aspects for Documentation, Measurement, and Calibration (Document ID 537), Section 6.2 -- FlatMap methodology, naming conventions, A2L mapping
- AUTOSAR CP R25-11, SWS RTE (Document ID 84), Section 4.2.9.4 -- McSupportData generation from FlatMap, `McDataInstance` derivation rules
- AUTOSAR CP R25-11, TR Methodology -- "Generate or Adjust System Flat Map" task, Partial Flat Map merging workflow
