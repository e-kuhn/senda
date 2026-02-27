# Cross-Reference Resolution Design

**Date:** 2026-02-27
**Status:** Approved
**Approach:** Schema-Driven (Approach 1)

## Problem

After composition flattening (PR #25) and the skip-warning always-fire fix (PR #26), ~5,622 elements are still skipped in the R20-11 ARXML file (73,374 in R4.3.1). All are `*-REF` reference elements appearing inside Property frames where the target type's role table doesn't include them.

## Goal

Full cross-reference resolution: capture `*-REF` elements as `ValueKind::Reference` path values in the FIR, then resolve them to actual `ObjectDef` handles post-parse.

## Scope

All four AUTOSAR reference categories:

| Category | Count (R23-11 XSD) | Example |
|----------|-------------------|---------|
| Direct `*-REF` | 955 element names | `SYSTEM-SIGNAL-REF` as child of `I-SIGNAL` |
| Wrapped `*-REF` (inside `*-REFS`) | 283 wrappers | `I-SIGNAL-PORT-REF` inside `I-SIGNAL-PORT-REFS` |
| Instance refs (`*-IREF`) | 99 element names | `DATA-ELEMENT-IREF` with `CONTEXT-*-REF` + `TARGET-*-REF` children |
| `*-REF-CONDITIONAL` | 58 types | Wrapper with inner `*-REF` + `VARIATION-POINT` |

## Key Decision: No DEST Attribute

The `DEST` attribute on `*-REF` elements is implicit — it's determined by the role's `target_type_id` in the schema. We do not capture or store DEST. An emitter can reconstruct it from the role's target type if needed.

## Design

### Layer 1: Schema Converter

**Export model** (`export_model.py`):
- Add `is_reference: bool` to `ExportMember`
- Add `inner_ref_tag: Optional[str]` to `ExportMember` — for Pattern B wrappers, the inner element's XML tag name

**Schema parser** (`schema_parser.py`):
- `_get_ref_member()` already sets `is_reference = True` — ensure propagation to `ExportMember`
- For Pattern B: extract the inner element's `name` attribute from the `xsd:choice → xsd:element` path, store as `inner_ref_tag`
- For IREF composites: ensure child REF members carry `is_reference = True`
- For REF-CONDITIONAL: ensure inner `*-REF` child carries `is_reference = True`

**C++ generator** (`cpp_generator.py`):
- Emit `is_reference` in `RoleInfo` constructor
- For Pattern B wrappers: emit an additional role entry on the wrapper's target type for the inner REF element tag, with `is_reference = true`
- Regenerate all 5 domain files

### Layer 2: Domain File Changes

**`RoleInfo` struct** (in `senda.compiler-arxml.cppm` or shared header):
```cpp
struct RoleInfo {
    uint32_t role_id;
    uint32_t target_type_id;
    bool is_reference;  // true for *-REF roles
};
```

Inner REF elements registered as roles on wrapper target types:
- `I-SIGNAL-PORT-REF` → role on `ISignalPort` type, `is_reference = true`
- Pattern: strip trailing `S` from wrapper tag to get inner REF tag

### Layer 3: FirBuilder Reference API

New method in `rupa.fir-builder.cppm`:
```cpp
void add_reference(ObjectHandle obj, RoleHandle role, std::string_view path);
```

Behavior:
1. Parse AUTOSAR path string (`/pkg/sub/signal`) into `PathSegment` entries (split on `/`, each segment → `PathSegment{Kind::Id, interned_string}`)
2. Create `ValueDef` with `ValueKind::Reference`, `segment_start/count`, `ref_target = UINT32_MAX`
3. Create `PropertyVal` binding role to value
4. Append to object's property list

No raw path string stored — `PathSegment` representation is canonical.

### Layer 4: ARXML Compiler Changes

**Reference-aware property creation** — In `on_end_element`, when closing a Property frame:
- If `role_info.is_reference == false`: call `builder.add_property(obj, role, text)` (current behavior)
- If `role_info.is_reference == true`: call `builder.add_reference(obj, role, text)`

**Pattern B inner elements** work automatically: the schema now registers inner REF tags as roles on the target type, so the existing `prop.target_type_info->roles.find(tag)` lookup finds them.

**IREF children** work automatically: IREF composites already have child members in the schema. Adding `is_reference = true` on those members triggers `add_reference()`.

**REF-CONDITIONAL** works automatically: same pattern as IREF.

### Layer 5: Reference Resolution Pass

**Incremental path index during parsing:**
- Maintain a `current_path` vector of SHORT-NAME segments in the parse state
- Push segment when entering an Object frame (after SHORT-NAME is seen)
- Pop when leaving an Object frame
- When an object is created, register `join(current_path, "/") → ObjectDef.Id` in a map

**Post-parse resolution:**
- Walk all `ValueDef` nodes with `ValueKind::Reference`
- Reconstruct path string from `PathSegment` entries
- Look up in path index
- If found: set `ref_target = resolved_id`
- If not found: emit diagnostic warning

**Diagnostics:**
- Unresolved references: warning with path and containing object's identity
- Summary: count of resolved vs. unresolved references

## Testing Strategy

**Schema converter tests:**
- `is_reference` flag correctly set for all 4 patterns
- Pattern B `inner_ref_tag` extraction
- Generated C++ `RoleInfo` includes `is_reference`

**ARXML compiler tests:**
- Reference properties create `ValueKind::Reference` (not `ValueKind::String`)
- Pattern B inner elements no longer skipped
- Path index correctly built during parsing
- Reference resolution: verify `ref_target` set for valid paths
- Unresolved reference diagnostic for invalid paths

**Integration tests:**
- R20-11: skip count drops from ~5,622 to near zero
- R4.3.1: skip count drops from ~73,374 proportionally
- Object counts remain correct
- All existing tests pass (non-reference properties unchanged)

## Files Modified

| File | Change |
|------|--------|
| `tools/schema-converter/export_model.py` | Add `is_reference`, `inner_ref_tag` |
| `tools/schema-converter/schema_parser.py` | Propagate `is_reference`, extract `inner_ref_tag` |
| `tools/schema-converter/cpp_generator.py` | Emit `is_reference` in `RoleInfo`, inner REF roles |
| `src/domains/senda.domains.r*.cppm` (x5) | Regenerated |
| `external/rupa/src/fir/rupa.fir-builder.cppm` | Add `add_reference()` |
| `src/compiler-arxml/senda.compiler-arxml.cppm` | `is_reference` dispatch, path index, resolution pass |
| `tools/schema-converter/tests/` | New reference tests |
| `test/` | New compiler reference tests |
