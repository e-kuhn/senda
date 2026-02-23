# Pattern 09: ECUC Definition-Value — Transformation Pipeline

This pattern maps AUTOSAR's two-layer ECUC architecture onto Rupa's
`#[decode]`/`#[encode]`/`#[transform]` pipeline. ECUC is unusual: both the
metamodel (definitions) and the model (values) are expressed as data in the same
format. In Rupa, definition instances are decoded into a typed domain via the M3
API, generic values are transformed into typed instances, and the encode pipeline
proves round-trip fidelity by reconstructing definitions from the generated types.

---

## AUTOSAR Concept

### The Two-Layer Architecture

AUTOSAR ECU Configuration uses a strict separation between **definition** and
**value** layers:

**Definition layer (schema)**: Specifies *what can be configured*. Module vendors
publish `EcucModuleDef` packages that declare containers, parameters, and their
constraints. This is the ECUC equivalent of a schema or type system.

```
EcucModuleDef                          -- top-level module schema
  +container: EcucContainerDef*        -- structural grouping
    EcucParamConfContainerDef          -- concrete container with parameters
      +parameter: EcucParameterDef*    -- parameter definitions
        EcucIntegerParamDef            -- integer with min/max/default
        EcucBooleanParamDef            -- boolean with default
        EcucEnumerationParamDef        -- enumeration with literals
        EcucFloatParamDef              -- float with min/max/default
      +subContainer: EcucContainerDef* -- nested containers
    EcucChoiceContainerDef             -- exclusive choice among containers
      +choice: EcucParamConfContainerDef*
```

**Value layer (data)**: Specifies *actual configuration*. Integrators fill in
`EcucModuleConfigurationValues` that reference back to the definitions.

```
EcucModuleConfigurationValues          -- top-level module values
  +definition -> EcucModuleDef         -- "I conform to this schema"
  +container: EcucContainerValue*      -- structural grouping
    EcucContainerValue
      +definition -> EcucContainerDef  -- "I conform to this container def"
      +parameterValue: EcucParameterValue*
        +definition -> EcucParameterDef -- "I conform to this param def"
      +referenceValue: EcucAbstractReferenceValue*
      +subContainer: EcucContainerValue*
```

The critical relationship is the `definition` reference: every value element
points back to its corresponding definition element. This reference is
*mandatory at code generation time* (AUTOSAR constraint `[constr_3592]` for
containers, `[constr_3593]` for parameters).

---

## The Insight: Metamodel as Data

ECUC is unusual: the metamodel (definitions) and model (values) are both
expressed as data in the same format. An `EcucModuleDef` XML element is
structurally identical to any other ARXML element — it's not a schema file
or a separate metalanguage. The `DEFINITION-REF` on every value element
is a manual schema-conformance link because ARXML has no type system to
provide one automatically.

In Rupa, this pattern maps directly to the transformation pipeline:

1. ECUC definition types (`EcucModuleDef`, `EcucParamConfContainerDef`, etc.)
   are ordinary types in the `autosar-25-11` domain
2. An NvM definition file creates *instances* of these types — the metamodel
   is just M1 data
3. A `#[decode(domain)]` pipeline reads this data and dynamically produces
   a typed `ecuc-nvm` domain via the M3 API
4. A `#[transform]` pipeline maps generic ECUC values onto the generated types
5. A `#[encode(domain)]` pipeline serializes the types back to definition
   data, proving round-trip fidelity

---

## Pipeline Overview

```
definition.rupa                    values.rupa
(EcucModuleDef instances)          (EcucContainerValue instances)
        |                                  |
   #[decode(domain)]                  #[transform]
        |                                  |
        v                                  v
   ecuc-nvm domain  ──────────>  typed NvM instances
   (generated M2 types)          (generated M1 instances)
        |       \
        |        \── decoded-domain.rupa (materialized view)
        |
   #[encode(domain)]
        |
        v                          decoded-values.rupa
   EcucModuleDef instances         (materialized view)
   (round-trip)
```

### File Overview

| File | Role |
|------|------|
| `ecuc-nvm/definition.rupa` | NvM definition — instances of `autosar-25-11::EcucModuleDef` |
| `ecuc-nvm/decode.rupa` | `#[decode(domain)]` — definition data → typed `ecuc-nvm` domain |
| `ecuc-nvm/decoded-domain.rupa` | Materialized view — generated types as plain Rupa |
| `ecuc-nvm/values.rupa` | NvM config values — instances of `autosar-25-11::EcucContainerValue` |
| `ecuc-nvm/transform.rupa` | `#[transform]` — generic ECUC values → typed instances |
| `ecuc-nvm/decoded-values.rupa` | Materialized view — typed instances as plain Rupa |
| `ecuc-nvm/encode.rupa` | `#[encode(domain)]` — types back to `EcucModuleDef` data |

---

## Worked Example

### Step 1: ECUC Definition as Data — `definition.rupa`

This is the "aha" moment. The NvM module definition isn't types — it's
*instances* of `autosar-25-11::EcucModuleDef` and its children. In ARXML, this
is `AUTOSAR_MOD_ECUConfigurationParameters.arxml`. In Rupa, it's ordinary M1
data using the AUTOSAR domain's definition-side types.

```rupa
// file: ecuc-nvm/definition.rupa
// NvM module definition — instances of autosar-25-11 ECUC definition types

using domain autosar-25-11;

EcucModuleDef NvM {
    .containers += EcucParamConfContainerDef NvMBlockDescriptor {
        .lowerMultiplicity = 1;
        .upperMultiplicityInfinite = true;

        .parameters += EcucIntegerParamDef NvMNvramBlockIdentifier {
            .lowerMultiplicity = 1;
            .upperMultiplicity = 1;
            .symbolicNameValue = true;
            .min = 2;
            .max = 65535;
        };

        .parameters += EcucIntegerParamDef NvMNvBlockLength {
            .lowerMultiplicity = 1;
            .upperMultiplicity = 1;
            .min = 1;
            .max = 65535;
        };

        .parameters += EcucBooleanParamDef NvMBlockUseCrc {
            .lowerMultiplicity = 1;
            .upperMultiplicity = 1;
            .defaultValue = false;
        };

        .parameters += EcucEnumerationParamDef NvMBlockManagementType {
            .lowerMultiplicity = 1;
            .upperMultiplicity = 1;
            .literals += EcucEnumerationLiteralDef NVM_BLOCK_NATIVE {};
            .literals += EcucEnumerationLiteralDef NVM_BLOCK_REDUNDANT {};
            .literals += EcucEnumerationLiteralDef NVM_BLOCK_DATASET {};
            .defaultValue = "NVM_BLOCK_NATIVE";
        };
    };
};
```

All parameter constraints — min/max ranges, enum literals, multiplicity bounds,
default values — are expressed as role values on definition instances. The
metamodel is data.

---

### Step 2: Definitions Become Types — `decode.rupa`

The decode pipeline reads definition data and builds a typed domain via the M3
API. Phase 1 creates type and enum shells; Phase 2 adds roles with proper types
and constraints. This two-phase approach is necessary because a container's
parameter roles might reference enum types defined in sibling parameters — all
type names must be registered before roles can reference them.

```rupa
// file: ecuc-nvm/decode.rupa
// Decode pipeline: EcucModuleDef instances → typed ecuc-nvm domain

using domain autosar-25-11 as src;

// ── Phase 1: Create type shells ─────────────────────────────────

#[decode(domain)]
let create_container_types(mod: src::EcucModuleDef) = {
    mod.**<src::EcucParamConfContainerDef> | each(cdef => {
        let t = ::create_type(cdef.name);
        ::set_tag(t, "ecuc-def", cdef.path);
        ::register_type(t);
    });
};

#[decode(domain)]
let create_enum_types(mod: src::EcucModuleDef) = {
    mod.**<src::EcucEnumerationParamDef> | each(edef => {
        let t = ::create_enum(edef.name);
        edef.literals | each(lit => {
            ::add_enum_value(t, lit.name);
        });
        ::set_tag(t, "ecuc-def", edef.path);
        ::register_type(t);
    });
};

// ── Phase 2: Add roles with types and constraints ───────────────

#[decode(domain, phase = 2)]
let add_parameter_roles(mod: src::EcucModuleDef) = {
    mod.**<src::EcucParamConfContainerDef> | each(cdef => {
        let t = ::lookup_type(cdef.name);
        if t? then {
            cdef.parameters | each(pdef => {
                let r = match (type_of(pdef)) with {
                    src::EcucIntegerParamDef => {
                        let pt = ::create_primitive(pdef.name, ::integer);
                        if pdef has .min then ::set_range(pt, pdef.min, pdef.max);
                        ::register_type(pt);
                        ::create_role(pdef.name, pt)
                    },
                    src::EcucBooleanParamDef => {
                        ::create_role(pdef.name, ::boolean)
                    },
                    src::EcucFloatParamDef => {
                        let pt = ::create_primitive(pdef.name, ::float);
                        if pdef has .min then ::set_range(pt, pdef.min, pdef.max);
                        ::register_type(pt);
                        ::create_role(pdef.name, pt)
                    },
                    src::EcucEnumerationParamDef => {
                        let et = ::lookup_type(pdef.name);
                        ::create_role(pdef.name, et)
                    },
                    _ => ::create_role(pdef.name, ::string),
                };
                ::add_role(t, r);
            });
        };
    });
};

#[decode(domain, phase = 2)]
let create_module_type(mod: src::EcucModuleDef) = {
    let t = ::create_type(mod.name);
    mod.containers | each(cdef => {
        let ct = ::lookup_type(cdef.name);
        if ct? then {
            let r = ::create_role(cdef.name, ct);
            if cdef.upperMultiplicityInfinite then {
                ::set_multiplicity(r, cdef.lowerMultiplicity, none);
            } else {
                ::set_multiplicity(r, cdef.lowerMultiplicity, cdef.upperMultiplicity);
            };
            ::add_role(t, r);
        };
    });
    ::set_tag(t, "ecuc-def", mod.path);
    ::register_type(t);
};
```

The M3 API calls mirror the ECUC definition structure exactly — each
`EcucIntegerParamDef` with min/max becomes `::create_primitive` + `::set_range`,
each `EcucEnumerationParamDef` with literals becomes `::create_enum` +
`::add_enum_value`. The definition data drives the type construction.

---

### Step 3: The Generated Domain — `decoded-domain.rupa`

This materialized view shows what the decode pipeline produced, expressed as
hand-written Rupa. This file is not pipeline input — it's documentation showing
the generated `ecuc-nvm` domain in a form that's easy to read and compare.

```rupa
// file: ecuc-nvm/decoded-domain.rupa
// Materialized view — what the decode pipeline produces
// This is NOT input to the pipeline; it documents the generated domain.

domain ecuc-nvm;

#[range(2, 65535)]
type NvMNvramBlockIdentifier = integer;

#[range(1, 65535)]
type NvMNvBlockLength = integer;

enum NvMBlockManagementType {
    NVM_BLOCK_NATIVE,
    NVM_BLOCK_REDUNDANT,
    NVM_BLOCK_DATASET,
};

type NvMBlockDescriptor = {
    .NvMNvramBlockIdentifier: NvMNvramBlockIdentifier;
    .NvMNvBlockLength: NvMNvBlockLength;
    .NvMBlockUseCrc: Boolean;
    .NvMBlockManagementType: NvMBlockManagementType;
};

type NvM = {
    .NvMBlockDescriptor: NvMBlockDescriptor{1,};
};
```

Role names match ECUC parameter names directly (`.NvMNvramBlockIdentifier`,
`.NvMBlockUseCrc`) — the decode pipeline uses the definition's `name` as both
type name and role name, faithful to ECUC conventions.

---

### Step 4: Configuration Values as Generic Data — `values.rupa`

The integrator's NvM configuration, expressed as generic ECUC value data. All
parameter values are strings; the `definitionRef` is the only thing that gives
them meaning. This is what you find in a project's `NvM_Cfg.arxml`.

```rupa
// file: ecuc-nvm/values.rupa
// NvM configuration values — generic ECUC data with definition references

using domain autosar-25-11;

EcucModuleConfigurationValues NvM {
    .definitionRef = /AUTOSAR/EcucDefs/NvM;

    .containers += EcucContainerValue NvMBlock_AppData {
        .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor;

        .parameterValues += EcucNumericalParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMNvramBlockIdentifier;
            .value = "2";
        };
        .parameterValues += EcucNumericalParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMNvBlockLength;
            .value = "128";
        };
        .parameterValues += EcucNumericalParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMBlockUseCrc;
            .value = "true";
        };
        .parameterValues += EcucTextualParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMBlockManagementType;
            .value = "NVM_BLOCK_NATIVE";
        };
    };

    .containers += EcucContainerValue NvMBlock_Calibration {
        .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor;

        .parameterValues += EcucNumericalParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMNvramBlockIdentifier;
            .value = "3";
        };
        .parameterValues += EcucNumericalParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMNvBlockLength;
            .value = "256";
        };
        .parameterValues += EcucNumericalParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMBlockUseCrc;
            .value = "true";
        };
        .parameterValues += EcucTextualParamValue {
            .definitionRef = /AUTOSAR/EcucDefs/NvM/NvMBlockDescriptor/NvMBlockManagementType;
            .value = "NVM_BLOCK_REDUNDANT";
        };
    };
};
```

---

### Step 5: Values Become Typed Instances — `transform.rupa`

The transform reads generic ECUC values, uses `definitionRef` to resolve which
generated type and role to target, and parses string values into proper typed
values. The `definitionRef` at transform time does what `DEFINITION-REF` does at
ARXML validation time — it bridges the two layers.

```rupa
// file: ecuc-nvm/transform.rupa
// Transform pipeline: generic ECUC values → typed ecuc-nvm instances

using domain ecuc-nvm;
using domain autosar-25-11 as src;

// Helper: extract the leaf name from a definition reference path
let def_name(ref) = ref | split("/") | last;

// ── Module-level transformation ─────────────────────────────────

#[transform]
let transform_module(mod: src::EcucModuleConfigurationValues) = {
    let module_type = ::lookup_type(def_name(mod.definitionRef));
    module_type mod.name {
        mod.containers | each(cv => {
            let container_name = def_name(cv.definitionRef);
            let ct = ::lookup_type(container_name);
            . += transform_container(cv, ct);
        });
    };
};

// ── Container-level transformation ──────────────────────────────

let transform_container(cv: src::EcucContainerValue, ct: ::type) = {
    ct cv.name {
        cv.parameterValues | each(pv => {
            let role_name = def_name(pv.definitionRef);
            let r = ct.roles | find(r => r.name == role_name);
            let typed_value = match (r.element_type.representation) with {
                "integer" => to_integer(pv.value),
                "float"   => to_float(pv.value),
                "boolean" => to_boolean(pv.value),
                "enum"    => pv.value,
                _         => pv.value,
            };
            .{role_name} = typed_value;
        });
    };
};

// ── Drop consumed generic types ─────────────────────────────────

#[transform]
let drop_container_value(cv: src::EcucContainerValue) {};

#[transform]
let drop_numerical_param(pv: src::EcucNumericalParamValue) {};

#[transform]
let drop_textual_param(pv: src::EcucTextualParamValue) {};
```

The key move: `definitionRef` at transform time bridges the generic value layer
and the generated type layer. The `match` on `r.element_type.representation`
mirrors what AUTOSAR tooling does internally — interpreting string-encoded
parameter values according to the definition type.

---

### Step 6: The Typed Result — `decoded-values.rupa`

Materialized view of the transform output. Compare this to `values.rupa` — no
`definitionRef` indirection, no string-encoded values, no redundant type
annotations. The instances are typed by the generated `ecuc-nvm` domain.

```rupa
// file: ecuc-nvm/decoded-values.rupa
// Materialized view — what the transform pipeline produces
// This is NOT input to the pipeline; it documents the typed result.

using domain ecuc-nvm;

NvM NvM {
    .NvMBlockDescriptor += NvMBlockDescriptor NvMBlock_AppData {
        .NvMNvramBlockIdentifier = 2;
        .NvMNvBlockLength = 128;
        .NvMBlockUseCrc = true;
        .NvMBlockManagementType = NVM_BLOCK_NATIVE;
    };

    .NvMBlockDescriptor += NvMBlockDescriptor NvMBlock_Calibration {
        .NvMNvramBlockIdentifier = 3;
        .NvMNvBlockLength = 256;
        .NvMBlockUseCrc = true;
        .NvMBlockManagementType = NVM_BLOCK_REDUNDANT;
    };
};
```

---

### Step 7: Types Become Definitions Again — `encode.rupa`

The reverse direction — `#[encode(domain)]` reads the dynamically-created types
via `::type` reflection and serializes them back as `EcucModuleDef` instances.
The output should match `definition.rupa` structurally, proving round-trip
fidelity.

```rupa
// file: ecuc-nvm/encode.rupa
// Encode pipeline: ecuc-nvm domain types → EcucModuleDef instances (round-trip)

using domain autosar-25-11;

// ── Encode containers and parameters ────────────────────────────

let encode_container_def(t: ::composite) = {
    EcucParamConfContainerDef (t.name) {
        .lowerMultiplicity = 1;
        .upperMultiplicityInfinite = true;

        t.declared_roles | each(r => {
            .parameters += match (r.element_type.representation) with {
                "integer" => EcucIntegerParamDef (r.name) {
                    .lowerMultiplicity = r.min;
                    .upperMultiplicity = if r.max? then r.max else 1;
                    .min = r.element_type.range_min;
                    .max = r.element_type.range_max;
                },
                "boolean" => EcucBooleanParamDef (r.name) {
                    .lowerMultiplicity = r.min;
                    .upperMultiplicity = if r.max? then r.max else 1;
                },
                "float" => EcucFloatParamDef (r.name) {
                    .lowerMultiplicity = r.min;
                    .upperMultiplicity = if r.max? then r.max else 1;
                    .min = r.element_type.range_min;
                    .max = r.element_type.range_max;
                },
                "enum" => EcucEnumerationParamDef (r.name) {
                    .lowerMultiplicity = r.min;
                    .upperMultiplicity = if r.max? then r.max else 1;
                    r.element_type.values | each(v => {
                        .literals += EcucEnumerationLiteralDef (v) {};
                    });
                },
                _ => EcucGenericParamDef (r.name) {},
            };
        });
    };
};

// ── Encode the module type ──────────────────────────────────────

#[encode(domain)]
let encode_module(t: ::composite) = {
    if t.tags | any(tag => tag.key == "ecuc-def") then {
        // Only encode types tagged as ECUC definitions
        let container_roles = t.declared_roles
            | filter(r => r.element_type is ::composite);

        if container_roles | count() > 0 then {
            // This is a module-level type — encode as EcucModuleDef
            EcucModuleDef (t.name) {
                container_roles | each(r => {
                    .containers += encode_container_def(r.element_type);
                });
            };
        };
    };
};
```

---

## Structural Comparison

| Concern | ARXML | Rupa Pipeline |
|---------|-------|---------------|
| Schema representation | `EcucModuleDef` XML data + manual `DEFINITION-REF` | Same data decoded into typed domain via M3 API |
| Parameter type safety | String values validated by external tooling | Typed roles with `#[range]` enforced at M2 |
| Schema-data link | Explicit `DEFINITION-REF` on every value element | Implicit — instances are typed by the generated domain |
| Enumeration safety | String matching against `ECUC-ENUMERATION-LITERAL-DEF` | `enum` types with compile-time checking |
| Round-trip fidelity | N/A (definitions and values are always separate XML) | `#[encode]` reconstructs definitions from types |
| Schema evolution | Edit XML definition files, re-validate all values | Modify definition instances, re-run decode pipeline |

---

## Design Reference

- **Transformation language** (`design/current/08-transformation/transformation-language.md`):
  `#[decode]`/`#[encode]`/`#[transform]` pipeline, phase ordering
  (decode → freeze → encode → transform), return vs write mode,
  `::transform` statement for sub-transformation invocation.

- **M3 API** (`design/current/06-extensibility/m3-api-reference.md`):
  `::create_type`, `::create_primitive`, `::create_enum`, `::create_role`,
  `::add_role`, `::set_range`, `::add_enum_value`, `::register_type`,
  `::lookup_type`; `::type`/`::role` reflection properties (`.name`, `.roles`,
  `.declared_roles`, `.representation`, `.tags`, `.values`).

- **Metamodel support** (`design/current/06-extensibility/metamodel-support.md`):
  M2 type definitions, primitive types with `#[range]`, composite types with
  roles, multiplicity suffixes, domain freezing semantics.

- **Extension data encoding example** (`design/current/examples/extension-data-encoding.md`):
  Precedent for `#[encode]`/`#[decode]` round-trip with the same pipeline
  structure — Acme Corp measurement metadata encoded as ExtensionData/ExtGroup.

- **AUTOSAR specification** (`AUTOSAR_CP_TPS_ECUConfiguration`, R25-11):
  Section 2.3 (ECU Configuration Parameter Definition Metamodel), Section 2.4
  (ECU Configuration Value Metamodel).
