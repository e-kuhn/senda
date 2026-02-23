# Use Case 04: Version Migration

Migrate a signal model from AUTOSAR R22-11 (schema AUTOSAR_00051, internal
R4.8.0) to R25-11 (schema AUTOSAR_00054, internal R4.11.0). The migration
involves renamed elements, restructured types, and split containment -- the kind
of changes that accumulate across three minor releases and break every handwritten
migration script. Rupa handles this with two domains, typed transform functions,
multi-phase cross-reference resolution, and compiler-checked completeness.

---

## ARXML Baseline

### R22 Signal Model (Source)

A signal with computation method and data type in the R22 schema. The key
structural elements: `CompuMethod` is referenced directly from `SystemSignal`,
and `SwDataDefProps` nests inside the signal as a single container.

```xml
<AR-PACKAGES>
  <AR-PACKAGE>
    <SHORT-NAME>DataTypes</SHORT-NAME>
    <ELEMENTS>
      <COMPU-METHOD>
        <SHORT-NAME>EngineSpeed_CM</SHORT-NAME>
        <CATEGORY>LINEAR</CATEGORY>
        <COMPU-INTERNAL-TO-PHYS>
          <COMPU-SCALES>
            <COMPU-SCALE>
              <COMPU-RATIONAL-COEFFS>
                <COMPU-NUMERATOR><V>0</V><V>0.25</V></COMPU-NUMERATOR>
                <COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>
              </COMPU-RATIONAL-COEFFS>
            </COMPU-SCALE>
          </COMPU-SCALES>
        </COMPU-INTERNAL-TO-PHYS>
        <UNIT-REF DEST="UNIT">/Units/RPM</UNIT-REF>
      </COMPU-METHOD>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>Signals</SHORT-NAME>
    <ELEMENTS>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>EngineSpeed</SHORT-NAME>
        <LENGTH>16</LENGTH>
        <SW-DATA-DEF-PROPS>
          <COMPU-METHOD-REF DEST="COMPU-METHOD">/DataTypes/EngineSpeed_CM</COMPU-METHOD-REF>
        </SW-DATA-DEF-PROPS>
      </SYSTEM-SIGNAL>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>ThrottlePosition</SHORT-NAME>
        <LENGTH>12</LENGTH>
        <SW-DATA-DEF-PROPS>
          <COMPU-METHOD-REF DEST="COMPU-METHOD">/DataTypes/ThrottlePos_CM</COMPU-METHOD-REF>
        </SW-DATA-DEF-PROPS>
      </SYSTEM-SIGNAL>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

### R25 Signal Model (Target)

In R25, the structure has diverged in three ways:

1. **`SwDataDefProps` split**: The monolithic `SW-DATA-DEF-PROPS` container is
   replaced by separate `SwDataDefPropsConditional` entries, each with its own
   `CompuMethod` reference and optional `Unit` reference. This supports
   variant-conditional data properties.
2. **`CompuMethod` restructured**: The `UNIT-REF` moves from `CompuMethod` into
   `SwDataDefPropsConditional`, decoupling unit assignment from the conversion
   formula.
3. **`dataConstraint` added**: R25 adds a required `DataConstr` reference on
   signals, replacing the implicit range in the computation method.

```xml
<AR-PACKAGES>
  <AR-PACKAGE>
    <SHORT-NAME>DataTypes</SHORT-NAME>
    <ELEMENTS>
      <COMPU-METHOD>
        <SHORT-NAME>EngineSpeed_CM</SHORT-NAME>
        <CATEGORY>LINEAR</CATEGORY>
        <COMPU-INTERNAL-TO-PHYS>
          <COMPU-SCALES>
            <COMPU-SCALE>
              <COMPU-RATIONAL-COEFFS>
                <COMPU-NUMERATOR><V>0</V><V>0.25</V></COMPU-NUMERATOR>
                <COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>
              </COMPU-RATIONAL-COEFFS>
            </COMPU-SCALE>
          </COMPU-SCALES>
        </COMPU-INTERNAL-TO-PHYS>
        <!-- No UNIT-REF here in R25; unit lives in SwDataDefPropsConditional -->
      </COMPU-METHOD>
      <DATA-CONSTR>
        <SHORT-NAME>EngineSpeed_DC</SHORT-NAME>
        <DATA-CONSTR-RULES>
          <DATA-CONSTR-RULE>
            <PHYS-CONSTRS>
              <LOWER-LIMIT>0</LOWER-LIMIT>
              <UPPER-LIMIT>16383.75</UPPER-LIMIT>
            </PHYS-CONSTRS>
          </DATA-CONSTR-RULE>
        </DATA-CONSTR-RULES>
      </DATA-CONSTR>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>Signals</SHORT-NAME>
    <ELEMENTS>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>EngineSpeed</SHORT-NAME>
        <LENGTH>16</LENGTH>
        <SW-DATA-DEF-PROPS>
          <SW-DATA-DEF-PROPS-VARIANTS>
            <SW-DATA-DEF-PROPS-CONDITIONAL>
              <COMPU-METHOD-REF DEST="COMPU-METHOD">/DataTypes/EngineSpeed_CM</COMPU-METHOD-REF>
              <UNIT-REF DEST="UNIT">/Units/RPM</UNIT-REF>
              <DATA-CONSTR-REF DEST="DATA-CONSTR">/DataTypes/EngineSpeed_DC</DATA-CONSTR-REF>
            </SW-DATA-DEF-PROPS-CONDITIONAL>
          </SW-DATA-DEF-PROPS-VARIANTS>
        </SW-DATA-DEF-PROPS>
      </SYSTEM-SIGNAL>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

The structural diff: a flat `SwDataDefProps` with a single `CompuMethodRef`
becomes a nested `SwDataDefPropsConditional` with three references. Unit
assignment moves. A new `DataConstr` element must be synthesized from the
computation method's implicit range. Every signal in the model needs this
transformation applied consistently.

---

## Rupa Solution

### Step 1: Domain Type Definitions

Each AUTOSAR release is a separate Rupa domain. Types are contributed by files
declaring `domain autosar-r22;` or `domain autosar-r25;`. Only the
migration-relevant types are shown.

```rupa
// r22-signal-types.rupa -- types for the R22 domain
domain autosar-r22;

type Identifiable = {
    #[id(0)]
    .shortName: ShortName;
};

#[abstract]
type ARElement = Identifiable { };

type CompuMethod = ARElement {
    .category: ShortName;
    .compuInternalToPhys: CompuInternalToPhys?;
    .unitRef: &Unit?;                    // R22: unit on CompuMethod
};

type CompuInternalToPhys = {
    .compuScales: CompuScale*;
};

type CompuScale = {
    .compuRationalCoeffs: CompuRationalCoeffs?;
};

type CompuRationalCoeffs = {
    .compuNumerator: NumericalValue*;
    .compuDenominator: NumericalValue*;
};

type SwDataDefProps = {
    .compuMethodRef: &CompuMethod?;      // R22: flat structure
};

type SystemSignal = ARElement {
    .length: PositiveInteger;
    .swDataDefProps: SwDataDefProps?;
};
```

```rupa
// r25-signal-types.rupa -- types for the R25 domain
domain autosar-r25;

type Identifiable = {
    #[id(0)]
    .shortName: ShortName;
};

#[abstract]
type ARElement = Identifiable { };

type CompuMethod = ARElement {
    .category: ShortName;
    .compuInternalToPhys: CompuInternalToPhys?;
    // No .unitRef -- unit moved to SwDataDefPropsConditional
};

type DataConstr = ARElement {            // New in R25
    .dataConstrRules: DataConstrRule*;
};

type DataConstrRule = {
    .physConstrs: PhysConstrs?;
};

type PhysConstrs = {
    .lowerLimit: NumericalValue?;
    .upperLimit: NumericalValue?;
};

type SwDataDefPropsConditional = {       // New: variant-aware container
    .compuMethodRef: &CompuMethod?;
    .unitRef: &Unit?;                    // R25: unit here, not on CompuMethod
    .dataConstrRef: &DataConstr?;        // R25: explicit constraint ref
};

type SwDataDefProps = {
    .swDataDefPropsVariants: SwDataDefPropsConditional*;  // R25: list of conditionals
};

type SystemSignal = ARElement {
    .length: PositiveInteger;
    .swDataDefProps: SwDataDefProps?;
};
```

### Step 2: R22 Source Model

The model being migrated, authored against the R22 domain.

```rupa
// legacy-signals.rupa
using domain autosar-r22;

ARPackage DataTypes {
    CompuMethod EngineSpeed_CM {
        .category = LINEAR;
        .unitRef = /Units/RPM;
        .compuInternalToPhys = CompuInternalToPhys {
            CompuScale {
                .compuRationalCoeffs = CompuRationalCoeffs {
                    .compuNumerator = [0, 0.25];
                    .compuDenominator = [1];
                };
            }
        };
    }

    CompuMethod ThrottlePos_CM {
        .category = LINEAR;
        .unitRef = /Units/Percent;
        .compuInternalToPhys = CompuInternalToPhys {
            CompuScale {
                .compuRationalCoeffs = CompuRationalCoeffs {
                    .compuNumerator = [0, 0.025];
                    .compuDenominator = [1];
                };
            }
        };
    }
}

ARPackage Signals {
    SystemSignal EngineSpeed {
        .length = 16;
        .swDataDefProps = SwDataDefProps {
            .compuMethodRef = /DataTypes/EngineSpeed_CM;
        };
    }

    SystemSignal ThrottlePosition {
        .length = 12;
        .swDataDefProps = SwDataDefProps {
            .compuMethodRef = /DataTypes/ThrottlePos_CM;
        };
    }
}
```

### Step 3: Transform Functions

The migration file references both domains. The active domain (`autosar-r25`)
provides bare names; the source domain (`autosar-r22`) is aliased as `r22`.

```rupa
// r22-to-r25-migration.rupa
using domain autosar-r25;
using domain autosar-r22 as r22;

// ── Phase 1: Structural creation ─────────────────────────────────

// CompuMethod: strip the unitRef (it moves to SwDataDefPropsConditional)
#[transform]
let migrate_compu_method(cm: r22::CompuMethod): CompuMethod = CompuMethod {
    .shortName = cm.shortName;
    .category = cm.category;
    ::transform(cm.compuInternalToPhys, .compuInternalToPhys);
    // .unitRef intentionally omitted -- relocated to SwDataDefPropsConditional
};

// Synthesize a DataConstr from the CompuMethod's implicit range.
// One-to-many: each R22 CompuMethod produces both a CompuMethod and a DataConstr.
#[transform]
let synthesize_data_constr(cm: r22::CompuMethod) {
    let scale = cm.compuInternalToPhys?.compuScales | first();
    let factor = scale?.compuRationalCoeffs?.compuNumerator | last() ?? 1.0;
    let max_raw = 2.0 ** to_float(cm^.**<r22::SystemSignal>
        | filter(s => s.swDataDefProps?.compuMethodRef == cm)
        | first()?.length ?? 16) - 1.0;

    /DataTypes += DataConstr (cm.shortName + "_DC") {
        DataConstrRule {
            .physConstrs = PhysConstrs {
                .lowerLimit = 0;
                .upperLimit = max_raw * factor;
            };
        }
    };
};

// SwDataDefProps: restructure from flat to conditional
#[transform]
let migrate_sw_data_def_props(props: r22::SwDataDefProps): SwDataDefProps =
    SwDataDefProps {
        SwDataDefPropsConditional {
            .compuMethodRef = props.compuMethodRef;
            // Unit migrates from CompuMethod to here
            .unitRef = props.compuMethodRef?.unitRef;
        }
    };

// SystemSignal: map 1:1, delegate children
#[transform]
let migrate_signal(sig: r22::SystemSignal): SystemSignal = SystemSignal {
    .shortName = sig.shortName;
    .length = sig.length;
    ::transform(sig.swDataDefProps, .swDataDefProps);
};

// ARPackage: structural pass-through
#[transform]
let migrate_package(pkg: r22::ARPackage): ARPackage = ARPackage {
    .shortName = pkg.shortName;
    ::transform(pkg.elements, .elements);
    ::transform(pkg.subPackages, .subPackages);
};

// ── Phase 2: Cross-reference fixup ──────────────────────────────

// Wire the new DataConstr references into the migrated SwDataDefPropsConditional.
// By Phase 2 all objects exist; we find targets via ::targets.
#[transform(phase = 2)]
let link_data_constr(sig: r22::SystemSignal) {
    let target_sig = ::targets(sig) | filter(x => x is SystemSignal) | first();
    let source_cm = sig.swDataDefProps?.compuMethodRef;

    if source_cm? then {
        // Find the DataConstr synthesized from this CompuMethod
        let target_dc = /DataTypes/**<DataConstr>[
            .shortName == source_cm.shortName + "_DC"
        ] | first();

        // Set the reference on the conditional
        let cond = target_sig.swDataDefProps?.swDataDefPropsVariants | first();
        if cond? then {
            cond.dataConstrRef = target_dc;
        };
    };
};
```

### Step 4: Build and Migrate

```sh
# Compile the R22 model
rupa build legacy-signals.rupa -o legacy-signals.rupac

# Migrate to R25 -- compiler detects domain mismatch, applies transforms
rupa build --domain autosar-r25 \
    r22-to-r25-migration.rupa \
    legacy-signals.rupac \
    -o migrated-signals.rupac

# Inspect the result
rupa inspect migrated-signals.rupac
```

Or use auto-transform during linking:

```rupa
// project.rupa -- consuming the migrated model
using domain autosar-r25;
import "r22-to-r25-migration.rupac";           // transform functions
let legacy = import "legacy-signals.rupac";     // R22 model

// Compiler detects autosar-r22 -> autosar-r25 mismatch.
// Finds #[transform] functions in scope.
// Applies migration automatically during linking.

// Reference migrated objects directly
let engine_speed = $legacy/Signals/EngineSpeed;
```

### Completeness Checking

The compiler enforces that every R22 type has a migration path. If a type exists
in the source domain but no `#[transform]` function handles it, the build fails:

```
error[E0401]: domain mismatch — no transform for type
  --> legacy-signals.rupac
  |
  = note: source domain `autosar-r22` contains type `AdminData`
  = note: target domain `autosar-r25` has no matching type
  = note: no #[transform] function found for r22::AdminData
  = help: add a transform function or an empty body `{}` to explicitly drop
```

---

## Key Features Demonstrated

| Feature | Where it appears |
|---------|-----------------|
| **Multi-domain** | `using domain autosar-r25;` + `using domain autosar-r22 as r22;` -- two frozen domains in one file |
| **Domain aliasing** | `r22::CompuMethod`, `r22::SystemSignal` -- source types qualified, target types bare |
| **Transform functions (`#[transform]`)** | Five Phase 1 functions mapping R22 types to R25 types |
| **One-to-many transform** | `synthesize_data_constr` creates a new `DataConstr` from a `CompuMethod` -- source type fans out |
| **`::transform` delegation** | `::transform(pkg.elements, .elements)` -- engine recursively applies matching transforms |
| **Multi-phase transforms** | Phase 1 creates structure; Phase 2 (`link_data_constr`) wires cross-references after all objects exist |
| **`::targets` lookup** | `::targets(sig)` finds the R25 `SystemSignal` created from the R22 source |
| **Completeness enforcement** | Compiler errors on unmapped source types -- no silent data loss during migration |
| **Auto-transform at link time** | Importing an R22 artifact into an R25 project triggers migration automatically |
| **Schema evolution patterns** | Flat-to-nested restructuring, reference relocation, synthesized new elements |

---

## Comparison

| Aspect | Manual ARXML migration | Rupa-assisted migration |
|--------|----------------------|------------------------|
| **Type safety** | XSLT/Python scripts operate on untyped XML nodes; typos in element names are runtime failures | Transform functions are type-checked against both domain metamodels at compile time |
| **Completeness** | No guarantee every element type is handled; missing cases produce silent data loss | Compiler requires a transform (or explicit drop) for every source-domain type |
| **Cross-references** | Must be rewritten by hand; broken refs found only by downstream validation | Phase 2 resolves cross-refs using `::targets`; broken refs are compile errors |
| **Structural changes** | Flat-to-nested restructuring requires careful XML tree surgery | `SwDataDefProps` -> `SwDataDefPropsConditional` expressed as a typed function return |
| **Synthesized elements** | Must be generated by custom scripts alongside the migration | `synthesize_data_constr` creates new R25 elements inline with the transform |
| **Unit relocation** | Manual find-and-move across XML subtrees | One line: `.unitRef = props.compuMethodRef?.unitRef;` |
| **Reusability** | Scripts are project-specific, rarely shared | Transform files compile to `.rupac` artifacts, reusable across projects |
| **Incremental migration** | Full re-run on every change | Compiler links pre-built R22 artifacts; only changed files recompile |
| **Auditability** | Script logic scattered across files, hard to review | Each type mapping is a named, self-contained function with clear input/output |
| **Error reporting** | Stack traces from Python/XSLT | Rust-style diagnostics with source locations in both source and target models |

The fundamental difference: manual migration is a batch script that transforms
XML trees with no type system to catch mistakes. Rupa migration is a compiled,
type-checked program that the build system enforces. Missing a type is a compile
error, not a silent data loss discovered three months later in a vehicle test.
