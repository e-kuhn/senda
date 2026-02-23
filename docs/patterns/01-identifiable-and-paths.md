# Pattern 01: Identifiable, Short Names, and Path Navigation

This pattern maps AUTOSAR's identity and path resolution mechanisms to their Rupa
equivalents. It covers the `Referrable`/`Identifiable` class hierarchy, the
`SHORT-NAME-PATH` reference scheme, the `DEST` attribute on references, and how
each concept translates into Rupa's `#[id]` annotation, `/`-delimited identity
paths, cross-role uniqueness, and typed references.

---

## AUTOSAR Concept

### The Referrable / Identifiable Hierarchy

AUTOSAR's metamodel (M2) defines a class hierarchy for object identity:

- **`Referrable`** -- base class providing `shortName` (type `Identifier`,
  stereotype `atpIdentityContributor`). The spec states: *"This specifies an
  identifying shortName for the object. It needs to be unique within its context
  and is intended for humans but even more for technical reference."*

- **`Identifiable`** -- extends `Referrable` (via `MultilanguageReferrable`),
  adding `longName`, `desc`, `adminData`, `annotation`, and `category`.
  *"Identifiables might contain Identifiables."*

- **`ARElement`** (abstract) -- extends `Identifiable`. Elements aggregated inside
  an `ARPackage`.

- **`ARPackage`** -- extends `Identifiable`. Aggregates `ARElement` instances (role
  `element`) and sub-packages (role `arPackage`).

The inheritance chain for `SystemSignal`:

```
ARObject -> Referrable -> MultilanguageReferrable -> Identifiable
  -> CollectableElement -> PackageableElement -> ARElement -> SystemSignal
```

### SHORT-NAME-PATH Resolution

AUTOSAR references any `Identifiable` via `SHORT-NAME-PATH` -- a `/`-delimited
string of `shortName` values from root through the containment hierarchy:

```
/AUTOSAR/Signals/BrakePedalPosition
```

Each segment corresponds to a `shortName` at one level of the containment tree.

### The DEST Attribute

ARXML references carry a `DEST` attribute declaring the expected target type. This
is necessary because XML has no type system -- the parser needs `DEST` to validate
references and construct the correct in-memory representation.

### ARXML Example

A package hierarchy with nested signals and a cross-reference:

```xml
<AR-PACKAGE>
  <SHORT-NAME>AUTOSAR</SHORT-NAME>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Signals</SHORT-NAME>
      <ELEMENTS>
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
        <SYSTEM-SIGNAL>
          <SHORT-NAME>VehicleSpeed</SHORT-NAME>
          <LENGTH>16</LENGTH>
        </SYSTEM-SIGNAL>
      </ELEMENTS>
    </AR-PACKAGE>
    <AR-PACKAGE>
      <SHORT-NAME>Communication</SHORT-NAME>
      <ELEMENTS>
        <I-SIGNAL>
          <SHORT-NAME>BrakePedalPosition_I</SHORT-NAME>
          <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
          <LENGTH>12</LENGTH>
          <!-- DEST declares the expected target type -->
          <SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL"
            >/AUTOSAR/Signals/BrakePedalPosition</SYSTEM-SIGNAL-REF>
        </I-SIGNAL>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AR-PACKAGE>
```

Key observations:

1. Every `Identifiable` carries a `<SHORT-NAME>` child element.
2. Wrapper elements (`<AR-PACKAGES>`, `<ELEMENTS>`) exist for XML structure -- they
   have no identity and do not participate in path resolution.
3. `SYSTEM-SIGNAL-REF` carries `DEST="SYSTEM-SIGNAL"` to declare the target type.
4. The path `/AUTOSAR/Signals/BrakePedalPosition` resolves through `shortName`
   values only.

---

## Rupa Mapping

### Identity via `#[id(N)]`

AUTOSAR's `Referrable.shortName` maps to Rupa's `#[id]` annotation. `#[id(N)]`
declares a role as an identity contributor (`N` = identity order, 0 = primary):

```rupa
type Identifiable = {
    #[id(0)]
    .shortName: ShortName;
    .category: ShortName?;
    .adminData: AdminData?;
};
```

`#[id(0)]` on `.shortName` means this role's value is the primary identity. When
you write `SystemSignal BrakePedalPosition { ... }`, the name `BrakePedalPosition`
is assigned to `.shortName` and used for path navigation. Subtypes inherit `#[id]`.

| AUTOSAR concept | Rupa equivalent |
|-----------------|-----------------|
| `Referrable.shortName` | Role annotated with `#[id(0)]` |
| `atpIdentityContributor` stereotype | `#[id(N)]` annotation |
| Identity inherited by subtypes | Rupa inheritance propagates `#[id]` |

### Path Anchor `/` = SHORT-NAME-PATH

AUTOSAR's `SHORT-NAME-PATH` maps directly to Rupa's root-anchored identity path.
The leading `/` is both the root anchor and the first identity navigation step.
The syntax is intentionally identical:

| AUTOSAR | Rupa |
|---------|------|
| `/AUTOSAR/Signals/BrakePedalPosition` | `/AUTOSAR/Signals/BrakePedalPosition` |

Each `/`-delimited segment navigates by `#[id]` value. Cross-role identity
uniqueness guarantees each segment resolves to exactly one child.

### Cross-Role Identity Uniqueness

`ARPackage` has two containment roles: `element` and `arPackage`. Rupa enforces
that **all children of a parent must have unique identities regardless of role or
type**. Duplicate identity across roles is a compile error:

```rupa
ARPackage Root {
    ARPackage Foo { }         // lives in .subPackages
    SystemSignal Foo { }      // ERROR: duplicate identity "Foo" within Root
}
```

This is the price of the simple `/Root/Foo` notation -- without cross-role
uniqueness, the path would be ambiguous.

### Non-Identifiable Objects Are Path-Transparent

ARXML wrapper elements (`<AR-PACKAGES>`, `<ELEMENTS>`) carry no `shortName` and do
not participate in path resolution. Rupa handles this identically: objects without
`#[id]` are skipped during identity path resolution. The ARXML exporter
re-introduces wrapper elements when serializing.

### `DEST` Attribute Is Unnecessary

In Rupa, reference roles are typed in the metamodel using `&Type` syntax. The
compiler knows that `.systemSignalRef: &SystemSignal` must point to a
`SystemSignal` -- no runtime type tag is needed:

```rupa
type ISignal = ARElement {
    .length: PositiveInteger;
    .systemSignalRef: &SystemSignal;   // type known at compile time
};
```

| ARXML pattern | Rupa equivalent |
|---------------|-----------------|
| `<...-REF DEST="SYSTEM-SIGNAL">path</...-REF>` | `.systemSignalRef: &SystemSignal` |
| Runtime `DEST` validation | Compile-time type checking |
| `DEST` required on every reference | Type declared once in the metamodel |

---

## Worked Example

### M2: Type Definitions (Metamodel)

```rupa
domain autosar;

#[pattern("[a-zA-Z_][a-zA-Z0-9_]*")]
type ShortName = ::string;
#[range(>=1)]
type PositiveInteger = ::integer;
type NumericalValue = ::float;

type Identifiable = {
    #[id(0)]
    .shortName: ShortName;
    .category: ShortName?;
    .adminData: AdminData?;
};

#[abstract]
type ARElement = Identifiable { };

#[root]
#[ordered]
type ARPackage = Identifiable {
    .elements: ARElement*;
    .subPackages: ARPackage*;
};

type SystemSignal = ARElement {
    .length: PositiveInteger;
    .initValue: NumericalValue?;
};

type ISignal = ARElement {
    .length: PositiveInteger;
    .systemSignalRef: &SystemSignal;
};
```

### M1: Model Instance

```rupa
using domain autosar;

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
    }
}
```

### Path Resolution Walkthrough

The reference `/AUTOSAR/Signals/BrakePedalPosition` resolves step by step:

```
/                          root anchor
  AUTOSAR                  identity nav -> ARPackage "AUTOSAR"
    /Signals               identity nav -> ARPackage "Signals"
      /BrakePedalPosition  identity nav -> SystemSignal "BrakePedalPosition"
```

At each step, the engine searches all containment roles of the current object for a
child whose `#[id(0)]` value matches. Cross-role uniqueness guarantees exactly one
match. The path does not specify which role each child occupies. The structural
path `.subPackages(Signals)` is available for explicit role navigation but is not
needed for standard usage.

### Side-by-Side Comparison

| Aspect | ARXML | Rupa |
|--------|-------|------|
| Identity | `<SHORT-NAME>X</SHORT-NAME>` | `SystemSignal X { }` |
| Package nesting | `<AR-PACKAGES><AR-PACKAGE>...` | `ARPackage A { ARPackage B { } }` |
| Wrapper elements | `<AR-PACKAGES>`, `<ELEMENTS>` | Not needed |
| Reference | `<...-REF DEST="SYSTEM-SIGNAL">/path</...-REF>` | `.ref = /path;` |
| Reference typing | `DEST` attribute (runtime) | `&Type` (compile-time) |
| Lines per signal | ~8 | 4 |

---

## Edge Cases

### 1. shortName Absent on Non-Identifiable Elements

Some AUTOSAR meta-classes (e.g., `ISignalMapping`) extend `ARObject` but not
`Identifiable` -- they have no `shortName` and are not path-addressable. In Rupa,
this is explicit: types without `#[id]` have no identity and are path-transparent.
They are accessed via role navigation or wildcards:

```rupa
// No #[id] -- accessed as .signalMappings[0] or .**<ISignalMapping>
type ISignalMapping = {
    .sourceSignal: &ISignalTriggering;
    .targetSignal: &ISignalTriggering;
};
```

### 2. DEST Attribute Redundancy

ARXML requires `DEST` on every reference. Rupa eliminates this: type information
lives in the metamodel (`&SystemSignal`). The ARXML exporter generates `DEST` from
metamodel types; the importer validates and discards it. Mismatched `DEST` errors
cannot occur in Rupa-authored models.

### 3. Cross-Role Uniqueness Conflicts

`ARPackage` has both `.elements` and `.subPackages` roles. AUTOSAR specifies
`shortName` uniqueness "within its context" but enforces it only by convention.
Rupa makes it a hard compile-time constraint:

```
error[E0042]: duplicate identity "Signals" within parent AUTOSAR
  --> system-model.rupa:3:5
   |
 3 |     ARPackage Signals { }
   |               ------- first defined here (in role .subPackages)
 6 |     SystemSignal Signals { }
   |                  ^^^^^^^ duplicate identity
   = note: all children of a parent must have unique identities
           regardless of role or type
```

### 4. The Root Object

In Rupa, `#[root]` marks types that can appear at file scope. `ARPackage` carries
`#[root]`, so `ARPackage AUTOSAR { }` is the equivalent of ARXML's `<AUTOSAR>`
document root. The root's `shortName` appears as the first segment of absolute
paths: `/AUTOSAR/Signals/...`.

### 5. shortName Character Restrictions

AUTOSAR restricts `shortName` to `[a-zA-Z][a-zA-Z_0-9]{0,127}`. In Rupa, this is
a primitive type constraint:

```rupa
#[pattern("[a-zA-Z_][a-zA-Z0-9_]*")]
type ShortName = ::string;
```

Any role typed as `ShortName` automatically inherits the validation.

---

## Design Reference

| Feature | Design document |
|---------|----------------|
| Identity paths, `/` anchor, path resolution | `design/current/03-data-modeling/references-and-paths.md` |
| Cross-role identity uniqueness | `design/current/03-data-modeling/cross-role-identity-uniqueness.md` |
| `#[id]` annotation, identity mechanism | `design/current/03-data-modeling/object-node-structure.md` |
| `&Type` references | `design/current/03-data-modeling/references-and-paths.md` |
| `#[root]` annotation | `design/current/03-data-modeling/root-types.md` |
| Type inheritance | `design/current/03-data-modeling/type-system.md` |
| `#[abstract]` types | `design/current/03-data-modeling/abstract-types.md` |
| Containment role inference | `design/current/03-data-modeling/containment-role-inference.md` |
| Path transparency (non-identifiable) | `design/current/03-data-modeling/references-and-paths.md` |

### Related Patterns

- **Pattern 02** (planned): Containment and role inference.
- **Pattern 03** (planned): References and the signal stack (`&Type` across
  ISignal/ISignalIPdu/Frame).
