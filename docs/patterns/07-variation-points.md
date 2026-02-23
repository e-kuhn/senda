# Pattern 07: Variation Points

This pattern maps AUTOSAR's variant handling mechanism -- the `<<atpVariation>>`
stereotype, `VariationPoint` meta-class, `SwSystemconst` value system, and
`BindingTimeEnum` classification -- to Rupa's `variant` declarations,
`#[variant()]` annotations, and `--variant` CLI binding. It covers how
conditional element existence is encoded in ARXML through `ConditionByFormula`
expressions referencing system constants, how binding times classify when
variation is resolved, and how Rupa collapses this multi-stage mechanism into a
single build-time evaluation model while preserving staged binding metadata as
domain data.

---

## AUTOSAR Concept

### The `<<atpVariation>>` Stereotype

AUTOSAR marks aggregation roles that support conditional existence with the
`<<atpVariation>>` stereotype. This declares that the multiplicity of the
aggregated element depends on a variant condition -- the element may or may not
exist depending on the values assigned to system constants or post-build variant
criteria. The stereotype appears throughout the metamodel:

| Class | Role | Latest Binding Time |
|-------|------|---------------------|
| `CompositionSwComponentType` | `.component` | `postBuild` |
| `CompositionSwComponentType` | `.connector` | `postBuild` |
| `SwComponentType` | `.port` | `preCompileTime` |
| `SwcInternalBehavior` | `.runnable` | `preCompileTime` |
| `SwcInternalBehavior` | `.event` | `preCompileTime` |
| `ISignalIPdu` | `.iSignalToPduMapping` | `postBuild` |
| `System` | `.fibexElement` | `postBuild` |
| `NumericalValueSpecification` | `.value` | `preCompileTime` |

When a role carries `<<atpVariation>>`, each aggregated element may have an
associated `VariationPoint` that determines its conditional existence.

### VariationPoint and ConditionByFormula

The `VariationPoint` meta-class is the core mechanism. It attaches to any
element whose existence is conditional. A `VariationPoint` carries:

- **`shortLabel`** -- a human-readable label identifying this variation point
  (used in Splitkey for identity alongside the element's `shortName`).
- **`swSyscond`** -- a `ConditionByFormula` containing a boolean expression over
  `SwSystemconst` values. If the formula evaluates to non-zero (true), the
  element exists; if zero (false), the element is excluded.
- **`postBuildVariantCondition`** -- for post-build variants, a set of
  `PostBuildVariantCondition` entries that compare a `PostBuildVariantCriterion`
  against a fixed integer value at runtime.

The `ConditionByFormula` also carries a `bindingTime` attribute
(`BindingTimeEnum`) specifying the **earliest** point at which the condition may
be evaluated. The `VariationPoint` itself has a `vh.latestBindingTime` tag
specifying the **latest** allowed binding time.

### SwSystemconst: The Variant Selector

`SwSystemconst` is an `ARElement` that defines a named system constant serving
as input to variation point conditions. System constants are pure variables --
they have a name and optional data definition properties (`swDataDefProps` for
limits and computation methods), but no inherent value. Values are assigned
externally through `SwSystemconstantValueSet` collections containing
`SwSystemconstValue` entries:

```xml
<SW-SYSTEMCONST>
  <SHORT-NAME>VehicleMarket</SHORT-NAME>
  <SW-DATA-DEF-PROPS>
    <SW-DATA-DEF-PROPS-VARIANTS>
      <SW-DATA-DEF-PROPS-CONDITIONAL>
        <COMPU-METHOD-REF DEST="COMPU-METHOD"
          >/CompuMethods/VehicleMarketEnum</COMPU-METHOD-REF>
      </SW-DATA-DEF-PROPS-CONDITIONAL>
    </SW-DATA-DEF-PROPS-VARIANTS>
  </SW-DATA-DEF-PROPS>
</SW-SYSTEMCONST>

<SW-SYSTEMCONSTANT-VALUE-SET>
  <SHORT-NAME>EU_LeftHand_Config</SHORT-NAME>
  <SW-SYSTEMCONSTANT-VALUES>
    <SW-SYSTEMCONST-VALUE>
      <SW-SYSTEMCONST-REF DEST="SW-SYSTEMCONST"
        >/SwSystemconsts/VehicleMarket</SW-SYSTEMCONST-REF>
      <VALUE>1</VALUE> <!-- EU -->
    </SW-SYSTEMCONST-VALUE>
  </SW-SYSTEMCONSTANT-VALUES>
</SW-SYSTEMCONSTANT-VALUE-SET>
```

### PredefinedVariant: Bundling Choices

A `PredefinedVariant` groups multiple system constant value assignments and
post-build criterion values into a named configuration. It represents a coherent
variant selection -- for example, "EU Left-Hand Drive Premium" -- that can be
chosen as a unit:

```xml
<PREDEFINED-VARIANT>
  <SHORT-NAME>EU_LeftHand_Premium</SHORT-NAME>
  <SYSTEM-CONSTANT-VALUE-SET-REFS>
    <SYSTEM-CONSTANT-VALUE-SET-REF DEST="SW-SYSTEMCONSTANT-VALUE-SET"
      >/ValueSets/EU_LeftHand_Config</SYSTEM-CONSTANT-VALUE-SET-REF>
    <SYSTEM-CONSTANT-VALUE-SET-REF DEST="SW-SYSTEMCONSTANT-VALUE-SET"
      >/ValueSets/Premium_Config</SYSTEM-CONSTANT-VALUE-SET-REF>
  </SYSTEM-CONSTANT-VALUE-SET-REFS>
</PREDEFINED-VARIANT>
```

### Binding Times

AUTOSAR classifies binding times as a processing-stage taxonomy, not precise
moments:

| `BindingTimeEnum` Value | Meaning |
|-------------------------|---------|
| `blueprintDerivationTime` | Resolved when deriving concrete types from blueprints |
| `systemDesignTime` | Resolved during system-level design |
| `codeGenerationTime` | Resolved when generating code from ARXML |
| `preCompileTime` | Resolved before C/C++ compilation (via `#define`/`#if`) |
| `linkTime` | Resolved at link stage |
| `postBuild` | Resolved at runtime by comparing `PostBuildVariantCriterion` values |

A variation point's `vh.latestBindingTime` determines the latest stage at which
it must be bound. A `ConditionByFormula.bindingTime` determines the earliest
stage at which its condition can be evaluated.

### Conditional Component Existence: Full ARXML Example

The following shows a `CompositionSwComponentType` with a conditionally existing
`SwComponentPrototype`. The component `ParkAssist` exists only when the system
constant `ParkAssistEnabled` evaluates to non-zero:

```xml
<COMPOSITION-SW-COMPONENT-TYPE>
  <SHORT-NAME>VehicleComposition</SHORT-NAME>
  <COMPONENTS>
    <!-- Unconditional component -->
    <SW-COMPONENT-PROTOTYPE>
      <SHORT-NAME>BrakeController</SHORT-NAME>
      <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
        >/SwComponents/BrakeCtrl</TYPE-TREF>
    </SW-COMPONENT-PROTOTYPE>

    <!-- Conditional component: exists only when ParkAssistEnabled != 0 -->
    <SW-COMPONENT-PROTOTYPE>
      <SHORT-NAME>ParkAssist</SHORT-NAME>
      <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
        >/SwComponents/ParkAssistCtrl</TYPE-TREF>
      <VARIATION-POINT>
        <SHORT-LABEL>VP_ParkAssist</SHORT-LABEL>
        <SW-SYSCOND>
          <SYSC-REF DEST="SW-SYSTEMCONST"
            >/SwSystemconsts/ParkAssistEnabled</SYSC-REF>
        </SW-SYSCOND>
      </VARIATION-POINT>
    </SW-COMPONENT-PROTOTYPE>

    <!-- Conditional connector associated with the conditional component -->
    <ASSEMBLY-SW-CONNECTOR>
      <SHORT-NAME>BrakeCtrl_To_ParkAssist</SHORT-NAME>
      <PROVIDER-IREF>
        <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
          >BrakeController</CONTEXT-COMPONENT-REF>
        <TARGET-P-PORT-REF DEST="P-PORT-PROTOTYPE"
          >/SwComponents/BrakeCtrl/BrakeStatusOut</TARGET-P-PORT-REF>
      </PROVIDER-IREF>
      <REQUESTER-IREF>
        <CONTEXT-COMPONENT-REF DEST="SW-COMPONENT-PROTOTYPE"
          >ParkAssist</CONTEXT-COMPONENT-REF>
        <TARGET-R-PORT-REF DEST="R-PORT-PROTOTYPE"
          >/SwComponents/ParkAssistCtrl/BrakeStatusIn</TARGET-R-PORT-REF>
      </REQUESTER-IREF>
      <VARIATION-POINT>
        <SHORT-LABEL>VP_ParkAssist_Conn</SHORT-LABEL>
        <SW-SYSCOND>
          <SYSC-REF DEST="SW-SYSTEMCONST"
            >/SwSystemconsts/ParkAssistEnabled</SYSC-REF>
        </SW-SYSCOND>
      </VARIATION-POINT>
    </ASSEMBLY-SW-CONNECTOR>
  </COMPONENTS>
</COMPOSITION-SW-COMPONENT-TYPE>
```

Key observations from the AUTOSAR RTE specification:

- When a `SwComponentPrototype` is disabled by its variation point, all
  `RTEEvent`s destined for its runnables are blocked.
- Connectors to disabled components must also be made variable; dangling
  connectors after variant resolution produce **undefined behavior**.
- Post-build disabled components remain in the ECU build but are inactive (not
  scheduled by the RTE).

### Nested Variant Conditions

When a conditional `SwComponentPrototype` is nested inside another conditional
prototype (hierarchical VFB view), flattening to the ECU flat view requires
combining conditions with boolean AND. The AUTOSAR System Template states:

> *"The variation condition formula needs to be altered such that the two (or
> more) individual conditions are combined in a boolean AND function."*

---

## Rupa Mapping

### Variant Dimensions Replace SwSystemconst

In AUTOSAR, `SwSystemconst` is an opaque integer compared in formula
expressions. In Rupa, variant dimensions are **declared with named values**,
providing a closed, enumerable domain:

| AUTOSAR | Rupa |
|---------|------|
| `SwSystemconst` with `CompuMethod` for named values | `variant` declaration with value list |
| `SwSystemconstantValueSet` with numeric assignments | `--variant Dim=Value` CLI flag |
| `PredefinedVariant` grouping multiple value sets | Multiple `--variant` flags (or future config files) |
| `ConditionByFormula` boolean expression | `#[variant()]` annotation with boolean predicate |
| `VariationPoint` on aggregated element | `#[variant()]` annotation on assignment |

```rupa
// AUTOSAR: SwSystemconst /SwSystemconsts/VehicleMarket with CompuMethod
//          mapping 1=EU, 2=US, 3=APAC
// AUTOSAR: SwSystemconst /SwSystemconsts/ParkAssistEnabled (0 or 1)
variant Market = [EU, US, APAC];
variant ParkAssist = [enabled, disabled];
```

### Conditional Component Existence

The ARXML conditional `SwComponentPrototype` maps to a `#[variant()]` annotation
on the assignment that creates the component instance:

```rupa
CompositionSwComponentType VehicleComposition {
    // Unconditional component -- always present
    .component += SwComponentPrototype BrakeController {
        .typeTref = $/SwComponents/BrakeCtrl;
    };

    // Conditional component: exists only when ParkAssist == enabled
    #[variant(ParkAssist == enabled)]
    .component += SwComponentPrototype ParkAssist {
        .typeTref = $/SwComponents/ParkAssistCtrl;
    };

    // Conditional connector tracks the component's variant condition
    #[variant(ParkAssist == enabled)]
    .connector += AssemblySwConnector BrakeCtrl_To_ParkAssist {
        .providerIref = InstanceRef {
            .contextComponentRef = $(.component[.shortName == "BrakeController"])!;
            .targetPPortRef = $/SwComponents/BrakeCtrl/BrakeStatusOut;
        };
        .requesterIref = InstanceRef {
            .contextComponentRef = $(.component[.shortName == "ParkAssist"])!;
            .targetRPortRef = $/SwComponents/ParkAssistCtrl/BrakeStatusIn;
        };
    };
}
```

### Binding Time as Metamodel Data

AUTOSAR's binding time taxonomy (`preCompileTime`, `linkTime`, `postBuild`) is a
**domain concern**, not a language concern. Rupa does not interpret binding times
during evaluation. Instead, binding time information is preserved as metamodel
attributes:

```rupa
// The VariationPoint's binding metadata is just data in Rupa.
// The language evaluates all variant conditions at build time.
// Downstream tools interpret the binding time classification.

SwComponentPrototype ParkAssist {
    .typeTref = $/SwComponents/ParkAssistCtrl;

    // Binding time is carried as a role on the VariationPoint,
    // not as a language-level concept
    .variationPoint = VariationPoint {
        .shortLabel = "VP_ParkAssist";
        #[doc("Latest binding time from AUTOSAR metamodel")]
        .latestBindingTime = postBuild;
    };
}
```

For the common case (import/export between ARXML and Rupa), the importer maps
AUTOSAR's `ConditionByFormula` expressions over `SwSystemconst` values to Rupa's
`#[variant()]` annotations for design-time variants. Post-build variants that
cannot be resolved at design time remain as metamodel data -- the
`PostBuildVariantCondition` structure is preserved but not evaluated by Rupa.

### Processing Pipeline

```
Source (.rupa with variant annotations)
    | parse
    v
Unbound IR (preserves all variant annotations and dimensions)
    | --variant Market=EU --variant ParkAssist=enabled
    v
Bound Model (variant conditions resolved, conditional elements included/excluded)
    | export --format arxml
    v
ARXML output (resolved: no VariationPoint elements)
       -- or --
ARXML output (template: VariationPoint elements preserved)
```

---

## Worked Example

### Scenario: Multi-Dimensional Variant with Conditional Ports and Components

A vehicle ECU composition where:
- The `HeatedSeatCtrl` component exists only for `Market == EU` or `Market == US`
- The `SeatVentCtrl` component exists only for `Market == US` or `Market == APAC`
- The CAN signal mapping depends on the market

#### ARXML (abbreviated)

```xml
<!-- System constants -->
<SW-SYSTEMCONST>
  <SHORT-NAME>MarketSelector</SHORT-NAME>
</SW-SYSTEMCONST>
<SW-SYSTEMCONST>
  <SHORT-NAME>SeatHeatingPresent</SHORT-NAME>
</SW-SYSTEMCONST>
<SW-SYSTEMCONST>
  <SHORT-NAME>SeatVentilationPresent</SHORT-NAME>
</SW-SYSTEMCONST>

<!-- Value sets for each market -->
<SW-SYSTEMCONSTANT-VALUE-SET>
  <SHORT-NAME>EU_Market_Values</SHORT-NAME>
  <SW-SYSTEMCONSTANT-VALUES>
    <SW-SYSTEMCONST-VALUE>
      <SW-SYSTEMCONST-REF DEST="SW-SYSTEMCONST"
        >/SwSystemconsts/MarketSelector</SW-SYSTEMCONST-REF>
      <VALUE>1</VALUE>
    </SW-SYSTEMCONST-VALUE>
    <SW-SYSTEMCONST-VALUE>
      <SW-SYSTEMCONST-REF DEST="SW-SYSTEMCONST"
        >/SwSystemconsts/SeatHeatingPresent</SW-SYSTEMCONST-REF>
      <VALUE>1</VALUE>
    </SW-SYSTEMCONST-VALUE>
    <SW-SYSTEMCONST-VALUE>
      <SW-SYSTEMCONST-REF DEST="SW-SYSTEMCONST"
        >/SwSystemconsts/SeatVentilationPresent</SW-SYSTEMCONST-REF>
      <VALUE>0</VALUE>
    </SW-SYSTEMCONST-VALUE>
  </SW-SYSTEMCONSTANT-VALUES>
</SW-SYSTEMCONSTANT-VALUE-SET>

<!-- Composition with conditional components -->
<COMPOSITION-SW-COMPONENT-TYPE>
  <SHORT-NAME>SeatECU</SHORT-NAME>
  <COMPONENTS>
    <SW-COMPONENT-PROTOTYPE>
      <SHORT-NAME>SeatPositionCtrl</SHORT-NAME>
      <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
        >/SwComponents/SeatPositionCtrlType</TYPE-TREF>
    </SW-COMPONENT-PROTOTYPE>

    <SW-COMPONENT-PROTOTYPE>
      <SHORT-NAME>HeatedSeatCtrl</SHORT-NAME>
      <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
        >/SwComponents/HeatedSeatCtrlType</TYPE-TREF>
      <VARIATION-POINT>
        <SHORT-LABEL>VP_HeatedSeat</SHORT-LABEL>
        <SW-SYSCOND>
          <SYSC-REF DEST="SW-SYSTEMCONST"
            >/SwSystemconsts/SeatHeatingPresent</SYSC-REF>
        </SW-SYSCOND>
      </VARIATION-POINT>
    </SW-COMPONENT-PROTOTYPE>

    <SW-COMPONENT-PROTOTYPE>
      <SHORT-NAME>SeatVentCtrl</SHORT-NAME>
      <TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE"
        >/SwComponents/SeatVentCtrlType</TYPE-TREF>
      <VARIATION-POINT>
        <SHORT-LABEL>VP_SeatVent</SHORT-LABEL>
        <SW-SYSCOND>
          <SYSC-REF DEST="SW-SYSTEMCONST"
            >/SwSystemconsts/SeatVentilationPresent</SYSC-REF>
        </SW-SYSCOND>
      </VARIATION-POINT>
    </SW-COMPONENT-PROTOTYPE>
  </COMPONENTS>
</COMPOSITION-SW-COMPONENT-TYPE>
```

#### Rupa Equivalent

```rupa
// Variant dimensions -- closed, enumerable domains
variant Market = [EU, US, APAC];

// Composition with conditional components
CompositionSwComponentType SeatECU {
    // Unconditional: always present
    .component += SwComponentPrototype SeatPositionCtrl {
        .typeTref = $/SwComponents/SeatPositionCtrlType;
    };

    // Heated seat: EU and US only
    #[variant(Market == EU || Market == US)]
    .component += SwComponentPrototype HeatedSeatCtrl {
        .typeTref = $/SwComponents/HeatedSeatCtrlType;
    };

    // Seat ventilation: US and APAC only
    #[variant(Market == US || Market == APAC)]
    .component += SwComponentPrototype SeatVentCtrl {
        .typeTref = $/SwComponents/SeatVentCtrlType;
    };

    // Connectors also carry variant conditions
    #[variant(Market == EU || Market == US)]
    .connector += AssemblySwConnector SeatPos_To_HeatedSeat {
        .providerIref = InstanceRef {
            .contextComponentRef = $(.component[.shortName == "SeatPositionCtrl"])!;
            .targetPPortRef = $/SwComponents/SeatPositionCtrlType/SeatStateOut;
        };
        .requesterIref = InstanceRef {
            .contextComponentRef = $(.component[.shortName == "HeatedSeatCtrl"])!;
            .targetRPortRef = $/SwComponents/HeatedSeatCtrlType/SeatStateIn;
        };
    };

    #[variant(Market == US || Market == APAC)]
    .connector += AssemblySwConnector SeatPos_To_SeatVent {
        .providerIref = InstanceRef {
            .contextComponentRef = $(.component[.shortName == "SeatPositionCtrl"])!;
            .targetPPortRef = $/SwComponents/SeatPositionCtrlType/SeatStateOut;
        };
        .requesterIref = InstanceRef {
            .contextComponentRef = $(.component[.shortName == "SeatVentCtrl"])!;
            .targetRPortRef = $/SwComponents/SeatVentCtrlType/SeatStateIn;
        };
    };
}
```

#### Build and Export

```bash
# Build for EU market -- HeatedSeatCtrl included, SeatVentCtrl excluded
rupa build --variant Market=EU seat-ecu.rupa -o eu-seat.model

# Build for US market -- both optional components included
rupa build --variant Market=US seat-ecu.rupa -o us-seat.model

# Export resolved ARXML for APAC (no VariationPoint elements in output)
rupa export --format arxml --variant Market=APAC seat-ecu.rupa -o apac-seat.arxml

# Export template ARXML (VariationPoint elements preserved for downstream tools)
rupa export --format arxml --template seat-ecu.rupa -o seat-ecu-template.arxml

# Validate all configurations
rupa validate --all-configs seat-ecu.rupa
```

---

## Edge Cases

### 1. Multiple Binding Times on the Same Composition

AUTOSAR allows different variation points within the same `CompositionSwComponentType`
to have different latest binding times. A component might be `preCompileTime`
while a connector is `postBuild`:

```xml
<SW-COMPONENT-PROTOTYPE>
  <SHORT-NAME>DiagLogger</SHORT-NAME>
  ...
  <VARIATION-POINT>
    <SHORT-LABEL>VP_DiagLogger</SHORT-LABEL>
    <!-- Latest binding: preCompileTime -->
    <SW-SYSCOND BINDING-TIME="PRE-COMPILE-TIME">
      <SYSC-REF ...>/SwSystemconsts/DiagEnabled</SYSC-REF>
    </SW-SYSCOND>
  </VARIATION-POINT>
</SW-COMPONENT-PROTOTYPE>

<ASSEMBLY-SW-CONNECTOR>
  <SHORT-NAME>DiagLogger_DataConn</SHORT-NAME>
  ...
  <VARIATION-POINT>
    <SHORT-LABEL>VP_DiagConn</SHORT-LABEL>
    <!-- Latest binding: postBuild (different from component!) -->
    <POST-BUILD-VARIANT-CONDITIONS>
      <POST-BUILD-VARIANT-CONDITION>
        <MATCHING-CRITERION-REF ...>DiagCriterion</MATCHING-CRITERION-REF>
        <VALUE>1</VALUE>
      </POST-BUILD-VARIANT-CONDITION>
    </POST-BUILD-VARIANT-CONDITIONS>
  </VARIATION-POINT>
</ASSEMBLY-SW-CONNECTOR>
```

**Rupa handling**: All variant conditions evaluate at Rupa build time regardless
of AUTOSAR binding time. The binding time metadata is preserved as domain data
but does not affect evaluation semantics. This means a Rupa build resolves
everything simultaneously, while AUTOSAR toolchains would resolve these at
different stages. The importer must map pre-build conditions to `#[variant()]`
annotations; pure post-build conditions (those with no design-time equivalent)
remain as uninterpreted `PostBuildVariantCondition` data.

### 2. Nested Variant Conditions

A conditional component nested inside another conditional component requires
combined conditions. In AUTOSAR's flat ECU view, this means boolean AND:

```rupa
variant BodyControl = [present, absent];
variant ParkAssist = [enabled, disabled];

// Outer composition: BodyControl module is conditional
CompositionSwComponentType VehicleTop {
    #[variant(BodyControl == present)]
    .component += SwComponentPrototype BodyCtrlModule {
        .typeTref = $/SwComponents/BodyCtrlComposition;
    };
}

// Inner composition: ParkAssist is conditional within BodyCtrl
CompositionSwComponentType BodyCtrlComposition {
    #[variant(ParkAssist == enabled)]
    .component += SwComponentPrototype ParkAssistCtrl {
        .typeTref = $/SwComponents/ParkAssistCtrlType;
    };
}
```

When flattened, `ParkAssistCtrl` effectively requires
`BodyControl == present AND ParkAssist == enabled`. In Rupa, this composition
is preserved hierarchically -- the nesting itself encodes the AND relationship.
When the outer component is excluded (bound model with `BodyControl == absent`),
its entire subtree disappears, so the inner variant condition on `ParkAssistCtrl`
is never evaluated.

### 3. Variant Interaction with Merge (`|=`)

When using `|=` to merge contributions from multiple files, variant annotations
on the same role from different files must not overlap:

```rupa
// file: base-seat-ecu.rupa
CompositionSwComponentType SeatECU {
    .component += SwComponentPrototype SeatPositionCtrl {
        .typeTref = $/SwComponents/SeatPositionCtrlType;
    };
}

// file: heated-seat-option.rupa
import "base-seat-ecu.rupa";

SeatECU |= {
    #[variant(Market == EU || Market == US)]
    .component += SwComponentPrototype HeatedSeatCtrl {
        .typeTref = $/SwComponents/HeatedSeatCtrlType;
    };
};
```

This works because `|=` adds to multi-valued roles (`.component` is `*`
multiplicity). The variant annotation scopes the addition. Potential conflict:
if two files both contribute a `HeatedSeatCtrl` with different variant
conditions, the Splitkey-based merge (Pattern 06) identifies them as the same
element, and the overlapping variant conditions produce an error.

### 4. Variant Conditions on Attribute Values (Not Just Existence)

AUTOSAR's `AttributeValueVariationPoint` allows an attribute's **value** (not
just existence) to vary. For example, an array size depending on a system
constant:

```xml
<IMPLEMENTATION-DATA-TYPE-ELEMENT>
  <SHORT-NAME>SensorReadings</SHORT-NAME>
  <ARRAY-SIZE>
    <VARIATION-POINT>
      <SHORT-LABEL>VP_ArraySize</SHORT-LABEL>
      <SW-SYSCOND>
        <!-- Formula: if MarketSelector == 1 then 8 else 16 -->
      </SW-SYSCOND>
    </VARIATION-POINT>
  </ARRAY-SIZE>
</IMPLEMENTATION-DATA-TYPE-ELEMENT>
```

In Rupa, this maps to variant annotations on competing assignments to the same
single-valued role:

```rupa
ImplementationDataTypeElement SensorReadings {
    #[variant(Market == EU)]
    .arraySize = 8;

    #[variant(Market == US || Market == APAC)]
    .arraySize = 16;
}
```

Since `.arraySize` is a single-valued role, overlapping variant conditions (where
more than one could match for a given configuration) are an error. The normal
metamodel multiplicity validation catches missing values when no condition
matches and the role is required.

### 5. Post-Build Variants as Unresolvable Data

Some AUTOSAR variation points are purely `postBuild` -- they reference
`PostBuildVariantCriterion` values determined at ECU runtime, not at any design
or build stage. These cannot be mapped to Rupa `#[variant()]` annotations
because Rupa evaluates at build time:

```rupa
// Post-build variant condition preserved as metamodel data, not as
// a Rupa variant annotation. The importer leaves this as-is.
SwComponentPrototype RuntimeConfigurable {
    .typeTref = $/SwComponents/RuntimeConfigType;
    .variationPoint = VariationPoint {
        .shortLabel = "VP_RuntimeCfg";
        .postBuildVariantCondition += PostBuildVariantCondition {
            .matchingCriterion = $/PostBuildVariantCriterions/RuntimeMode;
            .value = 1;
        };
    };
}
```

This element is always present in the Rupa model. The `VariationPoint` with its
`PostBuildVariantCondition` is carried as data for downstream tools (RTE
generator, MCAL configurator) that handle post-build binding.

---

## Design Reference

- **Rupa variants and configurations**: `design/current/03-data-modeling/variants-and-configurations.md`
- **Rupa annotations**: `design/current/02-syntax/` (annotation syntax, `#[...]`)
- **Rupa merge operator**: `design/current/03-data-modeling/` (merge semantics, `|=`)
- **AUTOSAR Generic Structure Template** (`FO-TPS-GenericStructureTemplate`):
  defines `VariationPoint`, `ConditionByFormula`, `SwSystemconst`,
  `PostBuildVariantCondition`, `PredefinedVariant`, `BindingTimeEnum`
- **AUTOSAR Software Component Template** (`CP-TPS-SoftwareComponentTemplate`):
  defines `VariationPointProxy`, structural vs. functional variation points
- **AUTOSAR System Template** (`CP-TPS-SystemTemplate`): appendix H lists all
  variation points and their latest binding times
- **AUTOSAR RTE Specification** (`CP-SWS-RTE`): defines runtime behavior of
  disabled components, connector variability, condition value macros
- **Pattern 06** (`06-splitable-and-multi-file.md`): interaction between
  `atpSplitable` Splitkeys and `atpVariation` short labels
