# XSD-to-C++ Code Generator Design

**Date:** 2026-02-26
**Status:** Approved

## Goal

Create a Python code generator that takes an AUTOSAR XSD schema and produces two C++ module files:

1. **Domain builder** — registers all types, roles, and enum values via the Rupa Domain/FirBuilder API, and builds pre-resolved XML tag → TypeHandle/RoleHandle lookup tables
2. **SAX-based ARXML parser** — streaming expat-based parser that uses the lookup tables to construct FIR from ARXML files

These generated files replace the existing hand-coded `senda.domains.cppm` (6 types) and `senda.compiler-arxml.cppm` (pugixml DOM-based) with auto-generated versions covering the full AUTOSAR schema (~2,700 composites, 870 enums, 50 primitives).

## Architecture

### Python Generator (extends `tools/schema-converter/`)

New file: `cpp_generator.py`. Reuses the existing 3-stage pipeline:

```
XSD → [schema_parser] → ExportSchema → [cpp_generator] → .cppm files
                                      → [rupa_generator] → .rupa files (existing)
```

CLI: `python converter.py <schema.xsd> <output-dir> --cpp`

### Generated C++ Files (checked into repo)

Two `.cppm` files replacing the current hand-coded versions:

- `src/domains/senda.domains.cppm`
- `src/compiler-arxml/senda.compiler-arxml.cppm`

### Runtime Flow

```
build_autosar_r23_11()  →  AutosarSchema { Domain, tag_to_type FrozenMap }
ArxmlCompiler(schema)   →  stores reference to lookup tables
compile(path)           →  expat SAX parse → FIR
```

## Generated Domain Builder (`senda.domains.cppm`)

### Return Type

```cpp
struct TypeInfo {
    rupa::domain::TypeHandle handle;
    kore::FrozenMap<std::string_view, rupa::domain::RoleHandle> roles;
};

struct AutosarSchema {
    rupa::domain::Domain domain;
    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type;
};
```

### Construction Phases

The `build_autosar_r23_11()` function:

1. **Primitives** — `begin_type(name, M3Kind::Primitive)` for each (4 base + 46 domain-specific)
2. **Enums** — `begin_type(name, M3Kind::Enum)` + `add_enum_value()` for each value
3. **Composites Phase 1** — `begin_type(name, M3Kind::Composite)` for all (captures TypeHandles)
4. **Composites Phase 2** — `set_supertype()` for inheriting types
5. **Composites Phase 3** — `set_abstract()` for abstract types
6. **Composites Phase 4** — `add_role()` for all members (captures RoleHandles)
7. **Lookup tables** — Build `FrozenMap<string_view, TypeInfo>` with the TypeHandles and RoleHandles captured above

### Key Mappings

- Variable names: PascalCase type name → snake_case C++ variable (e.g., `ISignal` → `i_signal`)
- XML tags: derived from XSD element names (UPPER-KEBAB-CASE, e.g., `I-SIGNAL`)
- Multiplicity: `(1,1)` → `One`, `(0,1)` → `Optional`, `(0,∞)` → `Many`, `(1,∞)` → `OneOrMore`
- Role targets: resolved to the TypeHandle of the target type
- Containment: `ExportMember.is_containment` → `RoleDef.is_containment`

### Ordered Types and Mixed Content

- Types with `is_ordered=True` (atpMixedOrdering stereotype) preserve child element ordering
- Types with `is_mixed_string=True` (atpMixedString stereotype) have an unnamed role `..` that receives text content between child elements

## Generated SAX Parser (`senda.compiler-arxml.cppm`)

### XML Library

**expat** — lightweight C SAX parser. Added as a CMake dependency (FetchContent or find_package).

### State Machine

No special-cased structural elements. `AUTOSAR`, `AR-PACKAGE`, `AR-PACKAGES`, `ELEMENTS` are all regular types/roles in the domain, treated uniformly.

```
Stack frame types:
  OBJECT    → inside a type element, building a FIR ObjectDef
  PROPERTY  → inside a role element (captures text or contains child objects)
  SKIP      → unknown element, ignoring subtree (depth counter)
```

#### startElement(tag)

1. Look up `tag` in `tag_to_type` → found? Push OBJECT frame, `builder.begin_object(identity, type_handle)`
2. Else if current frame is OBJECT, look up `tag` in current type's `roles` → found? Push PROPERTY frame
3. Else → push SKIP frame

#### endElement

- Pop frame
- OBJECT → finalize object
- PROPERTY with captured text → `builder.add_property(obj, role, text)`
- PROPERTY with child objects → objects already constructed by nested OBJECT frames
- SKIP → decrement depth, pop when zero

#### characters(text)

- If current frame is PROPERTY → append to text buffer
- If current frame is OBJECT and type has unnamed `..` role → append to `..` role

### Compiler Integration

```cpp
class ArxmlCompiler : public rupa::compiler::Compiler {
    const AutosarSchema* schema_;
public:
    ArxmlCompiler(const AutosarSchema& schema);
    std::span<const std::string_view> extensions() const override;  // {".arxml"}
    CompileResult compile(const fs::path& path, CompileContext& ctx) override;
};
```

The compiler receives a reference to the `AutosarSchema` (with pre-built lookup tables) at construction time. No runtime name lookups during parsing.

## Error Handling

### Parse-time Diagnostics

- Unknown XML tag → `Warning`, skip subtree
- Missing SHORT-NAME for identifiable type → `Warning`, use empty identity
- XML parse error (malformed) → `Error` from expat, abort
- Empty/missing file → `Error`

### Generator-time Validation (Python)

- Unresolved type references → warning in output
- Enum types with no values → skip with warning
- Duplicate role names on a type → error

## Testing

- Extend existing Python tests in `tools/schema-converter/tests/`
- Add `test_cpp_generator.py` — unit tests for C++ code generation (output format, correctness)
- Existing C++ integration tests continue to work against the generated code
- Manual verification: generate from `AUTOSAR_00052.xsd`, build, run existing test fixtures

## Dependencies

### New

- **expat** — C SAX XML parser library (replaces pugixml for ARXML parsing)

### Existing (unchanged)

- **kore** — `FrozenMap` (backed by `absl::flat_hash_map`)
- **rupa.domain** — Domain, DomainView, TypeHandle, RoleHandle
- **rupa.fir.builder** — FirBuilder
- **rupa.compiler** — Compiler interface, CompileResult, Diagnostics
