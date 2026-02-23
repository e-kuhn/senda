> **Status: Superseded** by `autosar/use-cases/`. This file is retained for historical reference.

# Rupa for AUTOSAR: Proof of Concept Use Cases

**Audience**: AUTOSAR tool engineers familiar with ARXML, the AUTOSAR metamodel, and version migration workflows.

---

## 1. Introduction & Value Proposition

Rupa is a human-readable language for expressing and manipulating object models. It sits between you and ARXML — a better authoring layer that imports from and exports to ARXML, with built-in validation, transformation, and domain management. You define your AUTOSAR metamodel as Rupa types, write models as concise structured text, and let the toolchain handle what ARXML makes painful: version migration, cross-reference consistency, ECU-specific overlays, and variant resolution.

**The same signal definition — ARXML vs. Rupa:**

```xml
<!-- ARXML: 12 lines, deeply nested, verbose -->
<SYSTEM-SIGNAL>
  <SHORT-NAME>BrakePedalPosition</SHORT-NAME>
  <DYNAMIC-LENGTH>false</DYNAMIC-LENGTH>
  <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
  <INIT-VALUE>
    <NUMERICAL-VALUE-SPECIFICATION>
      <VALUE>0.0</VALUE>
    </NUMERICAL-VALUE-SPECIFICATION>
  </INIT-VALUE>
  <LENGTH>12</LENGTH>
</SYSTEM-SIGNAL>
```

```rupa
// Rupa: 4 lines, flat, readable
SystemSignal BrakePedalPosition {
    .length = 12;
    .initValue = 0.0;
}
```

**Key advantages for AUTOSAR engineers:**

- **Readability**: One line per attribute instead of nested XML tags. Models fit on a screen.
- **Built-in validation**: Write constraint rules (signal range checks, PDU overlap detection) as first-class language constructs — not external scripts.
- **Version migration**: Transform functions bridge AUTOSAR releases (R21→R22→R25) with type-safe, compiler-checked mappings.
- **Tooling**: LSP-powered IDE support with completion, go-to-definition, and Rust-style error messages.

Rupa imports ARXML models and exports back to ARXML. It is a better authoring and validation layer, not a replacement for the interchange format.

---

## 2. Defining the AUTOSAR Metamodel

This is what a metamodel author writes. Each type definition corresponds to an AUTOSAR M2 element.

### Domain Declaration

```rupa
// autosar-types.rupa — contributes types to the autosar-r22 domain
domain autosar-r22;
```

### Primitive Types

```rupa
// Constrained string: only valid AUTOSAR short names
#[pattern("[a-zA-Z_][a-zA-Z0-9_]*")]
type ShortName = ::string;

// Positive integer with open upper bound
#[range(>=1)]
type PositiveInteger = ::integer;

// Non-negative integer
#[range(>=0)]
type NonNegativeInteger = ::integer;

// Unconstrained float
type NumericalValue = ::float;
```

`#[pattern]` restricts the string value space via regex. `#[range(>=1)]` means "greater than or equal to 1, no upper bound" — omitting a bound leaves it open.

### Enum Types

```rupa
type ByteOrderEnum = ::enum(
    "MOST-SIGNIFICANT-BYTE-FIRST",
    "MOST-SIGNIFICANT-BYTE-LAST"
);
```

Dashed values use quoted tokens in the definition. At use sites, single-word enum values resolve as bare tokens; multi-word/dashed values use quotes or qualified access (`ByteOrderEnum."MOST-SIGNIFICANT-BYTE-LAST"`).

### Composite Types — Identifiable Base

```rupa
// Base type with identity role
type Identifiable = {
    #[id(0)]
    .shortName: ShortName;
    .category: ShortName?;           // ? = optional (0..1)
    .adminData: AdminData?;
};
```

`#[id(0)]` marks `.shortName` as the identity role — this is what makes `/AUTOSAR/Signals/BrakePedalPosition` a valid path.

### Package Hierarchy

```rupa
#[root]                              // valid at file scope
#[ordered]                           // cross-role ordering preserved
type ARPackage = Identifiable {
    .elements: ARElement*;           // * = zero or more
    .subPackages: ARPackage*;
};

#[abstract]                          // cannot instantiate directly
type ARElement = Identifiable { };
```

`#[root]` marks types that can appear at file scope. `#[abstract]` prevents direct instantiation of grouping types. `#[ordered]` preserves statement order across roles (AUTOSAR's atpMixed semantics).

### Signal Stack Types

```rupa
type SystemSignal = ARElement {
    .length: PositiveInteger;
    .initValue: NumericalValue?;
};

type ISignal = ARElement {
    .length: PositiveInteger;
    .systemSignalRef: &SystemSignal;  // & = reference (not containment)
};

type ISignalIPdu = ARElement {
    .length: PositiveInteger;
    .iSignalToPduMappings: ISignalToPduMapping*;
};

type ISignalToPduMapping = Identifiable {
    .iSignalRef: &ISignal;
    .startPosition: NonNegativeInteger;
    .packingByteOrder: ByteOrderEnum;
};
```

Bare types (`ISignalToPduMapping*`) declare containment — the parent owns the children. `&Type` declares a reference — a pointer to an object owned elsewhere.

### Frame and ECU Types

```rupa
type Frame = ARElement {
    .frameLength: PositiveInteger;
    .pduToFrameMappings: PduToFrameMapping*;
};

type PduToFrameMapping = Identifiable {
    .iPduRef: &ISignalIPdu;
    .startPosition: NonNegativeInteger;
    .packingByteOrder: ByteOrderEnum;
};

type EcuInstance = ARElement {
    .comControllers: CommunicationController*;
};

type CommunicationController = Identifiable {
    .commConnectors: CommunicationConnector*;
};

type CommunicationConnector = Identifiable { };
```

### Multiplicity Summary

| Syntax | Meaning | ARXML equivalent |
|--------|---------|------------------|
| bare   | exactly 1 (required) | `<LOWER-MULTIPLICITY>1</LOWER-MULTIPLICITY>` |
| `?`    | 0..1 (optional) | upper=1, lower=0 |
| `*`    | 0..* | unbounded |
| `+`    | 1..* | lower=1, unbounded |
| `{2,4}`| 2..4 | explicit bounds |

### Type Reopening — Vendor Extensions

```rupa
// vendor-ext.rupa — extend Signal with company-specific roles
domain mycompany-ext = autosar-r22;   // derive from base domain

type SystemSignal = SystemSignal {    // self-reference = reopen
    .vendorCategory: ShortName?;
    .internalId: PositiveInteger?;
};
```

Reopening a type adds roles without modifying the original domain. The derived domain `mycompany-ext` includes all of `autosar-r22` plus the extensions.

### Bidirectional References

```rupa
type EcuInstance = ARElement {
    #[opposite(.ecuInstance)]
    .comControllers: CommunicationController*;
};

type CommunicationController = Identifiable {
    #[opposite(.comControllers)]
    .ecuInstance: &EcuInstance;
};
```

`#[opposite]` declares that both sides of the relationship are automatically maintained — assigning a controller to an ECU also sets the controller's back-reference.

---

## 3. Writing AUTOSAR Instance Models

This is what a model author writes. Types come from the metamodel; the author creates instances.

### Package Hierarchy

```rupa
// system-model.rupa
using domain autosar-r22;

ARPackage AUTOSAR {
    ARPackage Signals {
        SystemSignal BrakePedalPosition {
            .length = 12;
            .initValue = 0.0;
        }

        SystemSignal VehicleSpeed {
            .length = 16;
        }
    }

    ARPackage Communication {
        ISignal BrakePedalPosition_I {
            .length = 12;
            .systemSignalRef = /AUTOSAR/Signals/BrakePedalPosition;
        }

        ISignalIPdu BrakingIPdu {
            .length = 64;

            ISignalToPduMapping BrakePedal_Mapping {
                .iSignalRef = /AUTOSAR/Communication/BrakePedalPosition_I;
                .startPosition = 0;
                .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
            }
        }

        Frame BrakingFrame {
            .frameLength = 8;

            PduToFrameMapping BrakingIPdu_Mapping {
                .iPduRef = /AUTOSAR/Communication/BrakingIPdu;
                .startPosition = 0;
                .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
            }
        }
    }
}
```

### Key Concepts

**Containment inference**: `SystemSignal BrakePedalPosition { }` inside `ARPackage` doesn't need an explicit role assignment. The compiler matches it to `.elements` — the only containment role accepting `SystemSignal` (via `ARElement` subtyping). When ambiguous, you write it explicitly: `.elements += SystemSignal BrakePedalPosition { };`.

**Absolute path references**: `.systemSignalRef = /AUTOSAR/Signals/BrakePedalPosition;` navigates from the model root by identity segments. This replaces ARXML's `<SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/AUTOSAR/Signals/BrakePedalPosition</SYSTEM-SIGNAL-REF>`.

**Forward references**: References can point to objects defined later in the file. The compiler resolves all paths after building the complete model graph.

**Computed identity**: When the name needs to be derived:

```rupa
ISignal (config.prefix + "_I") {
    .length = 12;
    .systemSignalRef = /AUTOSAR/Signals/BrakePedalPosition;
}
```

**Containment-chain instantiation**: Compact form for deeply nested structures:

```rupa
// Instead of nesting three levels of braces:
ISignalIPdu BrakingIPdu/BrakePedal_Mapping {
    .iSignalRef = /AUTOSAR/Communication/BrakePedalPosition_I;
    .startPosition = 0;
    .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
}
```

**Cross-role identity uniqueness**: If `ARPackage` has both `.elements` and `.subPackages`, names are unique across both roles — no two children of the same parent can share a name, regardless of which role they occupy. This is what makes `/`-delimited paths unambiguous.

### CLI

```sh
rupa check signals.rupa        # syntax + type check, no output artifact
rupa build signals.rupa        # full compilation to .rupac
```

---

## 4. Validation Rules for AUTOSAR Constraints

Validation rules are boolean functions annotated with `#[rule]`. They use self-guarding: the `->` (implies) operator means "if the LHS is true, the RHS must also be true; if the LHS is false, the rule passes."

### Signal Validation

```rupa
// signal-validation.rupa
using domain autosar-r22;

// Signal length must be positive
#[rule(autosar::signal::length_positive)]
let signal_length_positive() =
    (. is ISignal) -> .length > 0;

// ISignal length must match its SystemSignal's length
#[rule(autosar::signal::ref_length)]
let ref_length_consistent() =
    (. is ISignal) -> .length == .systemSignalRef.length;
```

### PDU Constraints

```rupa
// No overlapping signal mappings within a PDU
#[rule(autosar::pdu::no_overlap)]
let pdu_no_overlap() =
    (. is ISignalIPdu) ->
        .iSignalToPduMappings | combinations(2) | all((m1, m2) =>
            m1.startPosition + m1.iSignalRef.length <= m2.startPosition
            || m2.startPosition + m2.iSignalRef.length <= m1.startPosition
        );

// Every PDU must have at least one signal mapping
#[rule(autosar::pdu::min_signals)]
let pdu_has_signals() =
    (. is ISignalIPdu) ->
        .iSignalToPduMappings | count() >= 1;
```

`combinations(2)` generates all unordered pairs. The pipe `|` chains list operations. Lambdas use `param => expr` syntax.

### Reverse Navigation

```rupa
// Every ISignal must be mapped in at least one PDU
#[rule(autosar::signal::must_be_mapped)]
let signal_must_be_mapped() =
    (. is ISignal) ->
        ::referrers(.) | any(r => r is ISignalToPduMapping);
```

`::referrers(target)` returns all objects holding references to the target — the inverse of ARXML's one-directional `REF` elements. Index-backed, not a tree walk.

### Naming Conventions

```rupa
#[rule(autosar::naming::shortname_convention)]
let shortname_convention() =
    (. is Identifiable) ->
        matches(.shortName, "[A-Z][a-zA-Z0-9_]*");
```

### M2-Level Validation — On Type Definitions

```rupa
// In the metamodel file: every ISignal instance must have positive length
#[validate(.length > 0)]
type ISignal = ARElement {
    .length: PositiveInteger;
    .systemSignalRef: &SystemSignal;
};
```

`#[validate]` on a type definition activates the rule on every instance of that type, everywhere. No need to import and activate separately.

### Activation and Suppression

```rupa
// Activate a rule set by prefix — all rules under autosar::signal
#[validate(autosar::signal)]

// Suppress a specific rule with justification
#[suppress(autosar::signal::ref_length, reason = "Legacy signal, length mismatch accepted")]
ISignal LegacyBrake_I {
    .length = 8;
    .systemSignalRef = /AUTOSAR/Signals/BrakePedalPosition;
}
```

Hierarchical rule IDs (`autosar::signal::ref_length`) enable prefix-based activation — `#[validate(autosar)]` activates all AUTOSAR rules.

### CLI

```sh
rupa build model.rupa --validate   # build + run activated validation rules
```

Validation errors use Rust-style diagnostics:

```
error[E0147]: validation rule `autosar::signal::ref_length` failed
  --> signals.rupa:14:5
   |
14 |     .length = 8;
   |               ^ ISignal length (8) != SystemSignal length (12)
   |
   = note: .systemSignalRef points to /AUTOSAR/Signals/BrakePedalPosition
   = help: change .length to 12, or update the SystemSignal
```

---

## 5. Transformations — AUTOSAR Version Migration

Transformation functions bridge domains. They are regular functions annotated with `#[transform]` — the compiler infers source and target domains from the function signature.

### Domain Derivation

```rupa
// system-to-ecu.rupa
domain ecu-local = autosar-r22;     // derive new domain from base

type EcuLocalSignal = Identifiable {
    .bitPosition: NonNegativeInteger;
    .bitLength: PositiveInteger;
    .direction: DirectionEnum;
};

type DirectionEnum = ::enum(SEND, RECEIVE);

type EcuLocalPdu = Identifiable {
    .signals: EcuLocalSignal*;
    .lengthBytes: PositiveInteger;
};
```

### Transform Functions

```rupa
// Map ISignalToPduMapping → EcuLocalSignal
#[transform]
let migrate_signal(mapping: ISignalToPduMapping): EcuLocalSignal =
    EcuLocalSignal (mapping.shortName) {
        .bitPosition = mapping.startPosition;
        .bitLength = mapping.iSignalRef.length;
        .direction = RECEIVE;
    };

// Map ISignalIPdu → EcuLocalPdu
#[transform]
let migrate_pdu(pdu: ISignalIPdu): EcuLocalPdu =
    EcuLocalPdu (pdu.shortName) {
        .lengthBytes = pdu.length / 8;    // integer division → integer
        ::transform(pdu.iSignalToPduMappings, .signals);
    };
```

`::transform(source, target_role)` delegates to the engine: for each element in the source collection, find the matching `#[transform]` function and place the result in the target role.

### Multi-Phase Transforms

```rupa
// Phase 1: structural mapping (objects created, references deferred)
#[transform(phase = 1)]
let create_structure(pkg: r21::ARPackage): ARPackage = ARPackage {
    .shortName = pkg.shortName;
    ::transform(pkg.signals, .elements);
};

// Phase 2: cross-reference fixup (all objects exist, wire up refs)
#[transform(phase = 2)]
let fixup_refs(sig: r21::ISignal) {
    let target = /.**<ISignal>[.shortName == sig.shortName];
    target.systemSignalRef = /.**<SystemSignal>[.shortName == sig.systemSignalRef.shortName];
};
```

### Cross-Version Migration

```rupa
using domain autosar-r22;
using domain autosar-r21 as r21;

// r21 types accessed via alias, r22 types bare
#[transform]
let migrate_signal(sig: r21::Signal): SystemSignal = SystemSignal {
    .shortName = sig.name;
    .length = sig.bitLength;
};
```

### Auto-Transform During Linking

```rupa
using domain autosar-r25;
import "r22-to-r25-migration.rupac";           // provides #[transform] functions
let legacy = import "legacy-signals.rupac";     // built against autosar-r22

// Compiler detects domain mismatch (r22 → r25).
// Finds #[transform] functions in scope.
// Applies them automatically during linking.
```

### Decode / Encode — Format-Level Transforms

For ARXML import/export, `#[decode]` and `#[encode]` handle format-specific mappings at the domain boundary:

```rupa
// Decode: ARXML → Rupa domain (extract typed structure from XML data)
#[decode(autosar-r22)]
let decode_admin_data(raw: ::map): AdminData = AdminData {
    .category = raw["CATEGORY"];
    .revision = raw["REVISION"];
};

// Encode: Rupa domain → ARXML (generate output format)
#[encode(autosar-r22)]
let encode_signal(sig: SystemSignal): ::map =
    ["SHORT-NAME" = sig.shortName, "LENGTH" = sig.length];
```

Pipeline order: decode (all phases) → freeze → encode (all phases) → transform (all phases). Each stage runs sequentially.

### CLI

```sh
rupa build --transform r22-to-r25.rupa legacy-model.rupa -o migrated.rupac
```

---

## 6. Modifications & Overlays — ECU-Specific Customization

Overlays modify an existing model without rewriting it. Import the base, merge it, then apply targeted changes.

### Import and Merge

```rupa
// ecu-overlay.rupa
using domain autosar-r22;
import base from "system-model.rupa";

|= base;    // merge base model into this file's model root
```

### Path Block Modification

```rupa
// Merge: modify specific roles, preserve everything else
/AUTOSAR/Communication/BrakingIPdu |= {
    .length = 128;
};
```

`|=` means "merge into existing object" — roles not mentioned retain their current values. Compare to `=` which would replace the entire object.

### Adding to Collections

```rupa
// Add a new signal mapping to an existing PDU
/AUTOSAR/Communication/BrakingIPdu |= {
    ISignalToPduMapping VehicleSpeed_Mapping {
        .iSignalRef = /AUTOSAR/Communication/VehicleSpeed_I;
        .startPosition = 16;
        .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
    }
};
```

### The `with` Block

```rupa
// Modify multiple objects under the same parent
with /AUTOSAR/Signals {
    SystemSignal BrakePedalPosition |= {
        .initValue = 0.5;
    };
    SystemSignal VehicleSpeed |= {
        .initValue = 0.0;
    };
}
```

### Distributed Mutation

```rupa
// Set a flag on ALL ISignals in the entire model tree
.**<ISignal>.verified = true;
```

`.**<ISignal>` descends the entire containment tree, matching all `ISignal` instances. The assignment distributes over the resolved set — each matching object gets `.verified = true`.

### Operator Semantics

| Operator | Single-valued role | Multi-valued role |
|----------|-------------------|-------------------|
| `=`      | Replace unconditionally | Replace entire collection |
| `+=`     | Error if occupied | Add to collection |
| `\|=`    | Merge (per 4.4 rules) | Merge (identity-based) |

### CLI

```sh
rupa build base.rupa overlay.rupa -o combined.rupac
```

Multiple source files are composed in order — later files overlay earlier ones.

---

## 7. Variants — Vehicle Line Configurations

Rupa provides build-time variant resolution. Variant dimensions are declared in the model; annotations on statements control which variant configurations include them.

### Variant Declaration and Use

```rupa
// variant-model.rupa
using domain autosar-r22;

variant VehicleLine = [Standard, Premium, Sport];

ARPackage AUTOSAR {
    ARPackage Signals {
        // Signal exists only for Premium and Sport
        #[variant(VehicleLine == Premium || VehicleLine == Sport)]
        SystemSignal ParkAssist_Status {
            .length = 8;
            .initValue = 1.0;
        }

        SystemSignal BrakePedalPosition {
            .length = 12;

            // initValue present only for Premium/Sport;
            // for Standard, .initValue stays absent (it's optional)
            #[variant(VehicleLine == Premium || VehicleLine == Sport)]
            .initValue = 0.5;
        }
    }
}
```

Variant annotations are conditional operations. If no condition matches, the operation is skipped — for optional roles, this means the role stays absent. No exhaustiveness requirement.

### CLI

```sh
rupa build model.rupa --variant "VehicleLine=Premium" -o premium.rupac
```

The `--variant` flag resolves all variant conditions at build time, producing a fully resolved model. Without it, the model retains variant annotations as unresolved metadata for downstream tooling.

---

## 8. Domain Management — Multi-Version AUTOSAR

Domains are named, versioned type sets. They are the mechanism for managing AUTOSAR release versions, vendor extensions, and cross-version interoperability.

### Domain Declaration — Contributing Types

```rupa
// autosar-r22-types.rupa
domain autosar-r22;

type SystemSignal = ARElement { .length: PositiveInteger; };
type ISignal = ARElement { .systemSignalRef: &SystemSignal; };
// ... all R22 types
```

Multiple files can contribute to the same domain. The type set is the union of all contributions.

### Domain Consumption — Model Authoring

```rupa
// my-model.rupa
using domain autosar-r22;    // freeze domain, use types as bare names

SystemSignal EngineSpeed { .length = 16; }
```

`using domain` freezes the domain — no further type contributions are allowed after this point. Types from the domain are available as bare names.

### Domain Derivation — Vendor Extensions

```rupa
// mycompany-types.rupa
domain mycompany-ext = autosar-r22;    // derive, freeze base

// Extend with company-specific types
type CompanySignal = SystemSignal { .companyId: ShortName; };

// Reopen existing type
type SystemSignal = SystemSignal { .internalTag: ShortName?; };
```

### Cross-Version References

```rupa
// migration.rupa
using domain autosar-r22;
using domain autosar-r21 as r21;    // aliased: types via r21::

#[transform]
let migrate(sig: r21::SystemSignal): SystemSignal = SystemSignal {
    .shortName = sig.name;
    .length = sig.bitLength;
};
```

Active domain (`autosar-r22`) types use bare names. Aliased domain (`autosar-r21`) types use qualified access (`r21::SystemSignal`).

### Domain-Agnostic Functions

```rupa
// Utility that works across any AUTOSAR version
let count_signals(pkg: ARPackage): ::integer =
    pkg.**<SystemSignal> | count();
```

When `ARPackage` and `SystemSignal` appear without a `using domain`, the function is domain-agnostic — it uses structural contracts (any type named `ARPackage` with a compatible structure). The compiler checks structural compatibility at link time.

### Structural Conditionals

```rupa
// Works even if the signal type varies across domain versions
let describe(sig) =
    if sig has .initValue
        then format("{}: length={}, init={}", sig.shortName, sig.length, sig.initValue)
        else format("{}: length={}", sig.shortName, sig.length);
```

`has` checks whether a role exists on the object's type. Inside the `then` branch, the compiler narrows the type — `sig.initValue` is valid.

### Domain Compatibility at Link Time

When linking compiled artifacts, the compiler checks domain compatibility:
- Same domain: direct merge
- Compatible domains (one derives from another): structural check
- Incompatible domains: error unless `#[transform]` functions bridge the gap

### CLI

```sh
rupa build --domain autosar-r22 model.rupa    # enforce domain constraint
rupa build --no-domain model.rupa             # domain-agnostic build
```

---

## 9. Advanced Features for AUTOSAR Power Users

### M3 Reflection

```rupa
// Type introspection
type_of(sig)                   // → ::type value for sig's type
sig is SystemSignal            // → true/false type check
sig has .initValue             // → true if type has this role

// Role introspection
role_of(sig.shortName)         // → ::role for .shortName
role_of(SystemSignal, .length) // → ::role for .length on SystemSignal

// Navigate type metadata
type_of(sig).roles             // → all roles (declared + inherited)
type_of(sig).is_abstract       // → false for SystemSignal
type_of(sig).domain.name       // → "autosar-r22"
```

### Tree Navigation

```rupa
// Find all SystemSignals anywhere in the package tree
root.**<SystemSignal>

// Find all children of a package (any type)
pkg.*

// Tree builtins (composable with pipes)
::root(sig)                    // containment root of sig
::children(pkg)                // immediate children across all roles
::descendants(pkg)             // all descendants (recursive)
```

### Reverse References

```rupa
// Find all objects that reference a given signal
::referrers(sig)               // → [composite] of all referencing objects

// Find which PDUs use this signal
::referrers(sig)
    | filter(r => r is ISignalToPduMapping)
    | map(m => m^)             // navigate to parent PDU
```

### Lambda + Pipe Chains

```rupa
// Filter, sort, and aggregate signals
let long_signals = pkg.**<SystemSignal>
    | filter(s => s.length > 8)
    | sort_by(s => s.shortName);

// Group signals by length
let by_length = pkg.**<SystemSignal>
    | group_by(s => s.length);

// Total bits in a PDU
let total_pdu_bits(pdu: ISignalIPdu) =
    pdu.iSignalToPduMappings
    | map(m => m.iSignalRef.length)
    | sum();
```

### Instance References / Archetypes (ECUC Pattern)

```rupa
type SwComponentPrototype = Identifiable {
    #[archetype]
    .type: &ApplicationSwComponentType;
};

// Navigate through the archetype boundary
let port = inst/>VehicleSpeed;   // /> follows the #[archetype] reference
                                 // finds VehicleSpeed in the component type
```

The `/>` operator traverses the archetype link — navigating from an instance (SwComponentPrototype) into the structural definition (ApplicationSwComponentType) to find child elements.

### FFI — External Tool Integration

```rupa
// Call a Python DBC validator
#[python]
let validate_dbc(file: ::string): ::boolean = r#{
    import cantools
    try:
        db = cantools.database.load_file(file)
        return True
    except:
        return False
}#;
```

FFI functions are read-only — they can inspect the model but cannot modify it directly. Results are returned as detached values for the Rupa code to integrate.

### Custom Functions

```rupa
// Reusable signal analysis
let signal_utilization(pdu: ISignalIPdu): ::float =
    pdu.iSignalToPduMappings
    | map(m => m.iSignalRef.length)
    | sum()
    | to_float() / to_float(pdu.length) * 100.0;
```

Functions are parameterized `let` bindings: `let name(params) = body;`. The `.` inside a function refers to the call-site context, not the function's definition site.

---

## 10. Tooling & Workflow

### Project Configuration

```toml
# rupa.toml
[project]
name = "vehicle-braking-system"
edition = "2026"

[domain]
name = "autosar-r22"

[source]
paths = ["src/", "metamodel/"]

[build]
output = "build/"
```

### CLI Commands

```sh
# Project setup
rupa init                          # scaffold a new project with rupa.toml

# Development cycle
rupa check src/signals.rupa        # syntax + type check (fast, no artifact)
rupa build                         # full compilation → .rupac
rupa build --validate              # build + run validation rules
rupa fmt src/                      # format source files
rupa lint src/                     # advisory checks (naming, style)

# Analysis
rupa inspect model.rupac           # dump model structure (human-readable)
rupa inspect model.rupac --json    # JSON output for scripting
rupa explain E0147                 # detailed error explanation

# Migration
rupa migrate --edition 2027        # automated source migration to new edition
rupa build --transform r22-to-r25.rupa legacy.rupa  # version migration

# Variant resolution
rupa build model.rupa --variant "VehicleLine=Premium"
```

### Error Messages

Rust-style diagnostics with error codes, source locations, and actionable hints:

```
error[E0042]: type mismatch in role assignment
  --> src/signals.rupa:8:16
   |
 8 |     .length = "twelve";
   |                ^^^^^^^^ expected PositiveInteger (::integer), found ::string
   |
   = help: use a numeric literal: .length = 12;

error[E0091]: unresolved reference
  --> src/model.rupa:23:26
   |
23 |     .systemSignalRef = /AUTOSAR/Signals/BrakePosition;
   |                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ path not found
   |
   = note: did you mean /AUTOSAR/Signals/BrakePedalPosition?
```

### LSP Features

- **Completion**: type names, signal names, path segments, role names, enum values
- **Go-to-definition**: jump from reference to target object or type definition
- **Find references**: all objects referencing a given signal or type
- **Hover**: type info, multiplicity, documentation from `#[doc]`
- **Semantic tokens**: metamodel-aware syntax highlighting (types, instances, references are visually distinct)
- **Diagnostics**: real-time validation as you type

### Documentation Annotations

```rupa
/// The length of the signal in bits.
/// Must match the corresponding SystemSignal's length.
type ISignal = ARElement {
    #[doc("Bit length of the I-Signal payload")]
    .length: PositiveInteger;
    .systemSignalRef: &SystemSignal;
};
```

`///` is sugar for `#[doc("...")]`. Documentation is Markdown and appears in LSP hover.

### Binary Artifact Format

Compiled `.rupac` files contain the resolved model graph, validation rules, and transformation functions in a compact binary format. They are the interchange format between Rupa tools — not intended for human editing. Use `rupa inspect` to examine them, `rupa emit` to convert to ARXML/JSON.
