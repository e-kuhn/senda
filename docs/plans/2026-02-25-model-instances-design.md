# Model Instances (M1) — Design

## Goal

Parse Rupa M1 instantiation syntax, lower it to FIR nodes alongside existing M2 types, and make instances queryable via the HTML explorer. Full spec chapter 06 scope: all assignment operators (`=`, `+=`, `|=`, `= _`), derivation (`from`), identity tracking, type inference, multiplicity validation.

Expression evaluation is limited to literals (int, float, string, bool) and simple forward-slash path references (`/a/b/c`). Unsupported expressions emit `UnsupportedExpression` warnings (reusing existing diagnostic). Unresolved references after lowering emit `UnresolvedReference` warnings.

## Context

- Parser already handles `Instantiation`, `Assignment`, `ResetAssignment`, `WithBlock` AST nodes
- FIR currently has 2 node kinds: `TypeDef` (M2), `RoleDef` (M2)
- Sema has Phase A (collect types) and Phase B (resolve types) — no M1 handling
- OML's M1 implementation was incomplete — this is new ground

## Architecture

### FIR M1 Node Types

Three new `NodeKind` values added to the existing enum:

```cpp
enum class NodeKind : uint8_t {
    TypeDef,       // M2 — existing
    RoleDef,       // M2 — existing
    ObjectDef,     // M1 — instance of an M2 type
    PropertyVal,   // M1 — role assignment on an instance
    ValueDef,      // M1 — leaf value (literal or reference)
};
```

**ObjectDef** — an M1 instance:
```cpp
struct ObjectDef : Node {
    Id       type_id;                         // → TypeDef this instantiates
    StringId identity;                        // object identity (empty = anonymous)
    uint32_t prop_start = 0;                  // range into property_ids_ table
    uint16_t prop_count = 0;
    Id       derived_from = Id{UINT32_MAX};   // → ObjectDef (for 'from' derivation)
};
```

**PropertyVal** — a role assignment on an instance:
```cpp
struct PropertyVal : Node {
    Id role_id;    // → RoleDef being assigned
    Id value_id;   // → ValueDef or ObjectDef (nested instance)
};
```

**ValueDef** — a leaf value (literal or reference):
```cpp
enum class ValueKind : uint8_t {
    Integer, Float, String, Boolean, Null, Reference, InstanceRef
};

struct ValueDef : Node {
    ValueKind value_kind;
    union {
        int64_t  int_val;
        double   float_val;
        bool     bool_val;
        StringId string_val;
    };
    // For Reference/InstanceRef: structured path segments
    uint32_t segment_start = 0;
    uint16_t segment_count = 0;
    // Resolved target (UINT32_MAX = unresolved/dangling)
    Id       ref_target = Id{UINT32_MAX};
};
```

### Structured Reference Paths

References are stored as typed path segments, not raw text:

```cpp
enum class PathSegmentKind : uint8_t {
    Id,    // simple identifier segment
    // Future: Filter, ArchetypeNav, Predicate, etc.
};

struct PathSegment {
    PathSegmentKind kind;
    Id value;    // → ValueDef or ObjectDef (typed identity value)
};
```

`/Components/SensorSWC` becomes:
```
[IdSegment(→ValueDef{String,"Components"}), IdSegment(→ValueDef{String,"SensorSWC"})]
```

The `value` field points to a FIR node, keeping identity values typed by their M2 type. For initial implementation, all segment identities are string ValueDefs. Compound identities (ObjectDef) and richer segment types (Filter, ArchetypeNav) are future extensions.

### Fir Class Extensions

New secondary tables:
```cpp
std::vector<Id>          property_ids_;    // flattened property lists (like role_ids_)
std::vector<PathSegment> path_segments_;   // reference path segments
```

New accessors:
```cpp
uint32_t appendProperties(std::span<const Id> ids);
std::span<const Id> propertiesOf(const ObjectDef& obj) const;
uint32_t appendPathSegments(std::span<const PathSegment> segs);
std::span<const PathSegment> pathSegments(uint32_t start, uint16_t count) const;
```

## Sema Phase C: Instance Lowering

New phase after type resolution, added to the compilation driver:

```cpp
SemaResult compile(const fs::path& root_path) {
    seed_builtins_into(*fir_, type_names_);
    process_file(root_path);          // Phase A: collect types
    type_names_.freeze();
    resolve_types_with_pool(...);     // Phase B: resolve types
    lower_instances(...);             // Phase C: M1 instances (NEW)
    return {std::move(fir_), diagnostics_};
}
```

### Phase C Steps

1. **Walk top-level statements** — find `Instantiation` nodes in the SourceFile
2. **Resolve type reference** — look up `type_ref` in `type_names_` → TypeDef Id
3. **Extract identity** — from the `identity` AST node, create a string ValueDef
4. **Create ObjectDef** — with type_id and identity
5. **Process the block** — for each statement:
   - **Assignment** (`.role = expr`): resolve role name against TypeDef's roles, evaluate expression, create PropertyVal
   - **Nested Instantiation**: recurse, create nested ObjectDef
6. **Handle assignment operators:**
   - `=` — create/replace PropertyVal
   - `+=` — append to property list (identity-merge if identifiable)
   - `|=` — create-and-merge (create if absent, merge if present)
   - `= _` — reset (remove PropertyVal)
7. **Expression evaluation** (limited):
   - Integer/float/string/boolean literals → ValueDef
   - Path expressions (`/a/b/c`) → ValueDef{Reference} with IdSegment path
   - Anything else → `UnsupportedExpression` warning, skip
8. **Post-lowering validation:**
   - Scan all Reference ValueDefs, warn on unresolved (`UnresolvedReference`)
   - Check multiplicity constraints on assigned roles

### New Diagnostics

- `UnresolvedRoleName` — assignment to a role not defined on the type
- `DuplicateIdentity` — two objects of same type with same identity
- `TypeMismatch` — value doesn't match role's target type
- `MultiplicityViolation` — cardinality constraint violated
- `UnresolvedReference` — reference path couldn't be resolved after lowering
- `UnsupportedExpression` — reuse existing

## Serialization

Format version bump: 2 → 3.

New header fields (appended after existing):
```
ObjectDef table:      offset(4) + count(4)
PropertyVal table:    offset(4) + count(4)
ValueDef table:       offset(4) + count(4)
Path segments table:  offset(4) + count(4)
Property IDs table:   offset(4) + count(4)
```

Record sizes:
- ObjectDef: ~19 bytes (kind + type_id + identity + prop_start + prop_count + derived_from)
- PropertyVal: ~9 bytes (kind + role_id + value_id)
- ValueDef: ~20 bytes (kind + value_kind + value_union + segment_start + segment_count + ref_target)
- PathSegment: ~5 bytes (kind + value_id)

Same remapping strategy as existing nodes (sparse → compact sequential indices).

## Explorer

### New API Endpoints

- `GET /api/objects` — list all ObjectDef instances (type name, identity, property count)
- `GET /api/objects/:id` — full ObjectDef with resolved properties
- `GET /api/types/:id/instances` — all instances of a given type
- `GET /api/stats` — extended with `object_count`, `property_count`, `value_count`

### UI

Add "Instances" tab alongside existing "Types" tab. Objects grouped by type, expandable property trees showing role names, values, and nested instances.

## Test Strategy

- Unit tests for each FIR node type (construction, accessors)
- Sema tests: parse + lower simple instantiations, verify ObjectDef/PropertyVal/ValueDef in FIR
- Assignment operator tests: `=`, `+=`, `|=`, `= _` semantics
- Diagnostic tests: unresolved type, unresolved role, duplicate identity, type mismatch
- Serialization round-trip: write M1 FIR → read back → verify
- Explorer integration: verify API returns instance data
- End-to-end: AUTOSAR M1 data in Rupa syntax → FIR → explorer
