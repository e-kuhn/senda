# FIR + Sema Architectural Cleanup — Design

**Date:** 2026-03-08
**Scope:** kore::TinyVector, FIR (12 modules), sema (11 modules), tests (27 files)
**Motivation:** Incremental development has introduced style drift, duplicated logic, abstraction leaks, and documentation gaps across the FIR and sema subsystems. This cleanup standardizes patterns, improves encapsulation, simplifies over-engineered infrastructure, and adds comprehensive documentation.

---

## 1. kore::TinyVector Enhancement

**Problem:** TinyVector exposes only `data()`, `size()`, `capacity()`. All 81 element-access sites across 13 files use `.data()[i]`, which is noisy, error-prone, and prevents range-for.

**Solution:** Add standard container accessors to both `TinyVector` and `TinyVectorView`:

```cpp
// Indexed access
T& operator[](SizeType i) noexcept;
T const& operator[](SizeType i) const noexcept;

// Element access
T& front() noexcept;
T const& front() const noexcept;
T& back() noexcept;
T const& back() const noexcept;

// State
[[nodiscard]] bool empty() const noexcept;

// Iterators (raw pointer — TinyVector storage is contiguous)
T* begin() noexcept;
T* end() noexcept;
T const* begin() const noexcept;
T const* end() const noexcept;
```

Then mechanically replace all `.data()[i]` sites. Convert indexed loops to range-for where the index is not otherwise needed.

---

## 2. Handle Extraction Consistency

**Problem:** 176 occurrences of `static_cast<uint32_t>(handle)` compete with the canonical `kore::Cast(handle)` API across 10 files (126 in serialization alone). This makes it impossible to audit handle usage with a single pattern.

**Solution:** Replace all handle-related `static_cast` with `kore::Cast`:
- `static_cast<uint32_t>(handle)` → `kore::Cast(handle)`
- `HandleType{static_cast<uint32_t>(expr)}` → `kore::Cast<HandleType>(expr)`

**Not changed:** `static_cast<uint32_t>(size())` or `static_cast<uint32_t>(enum_value)` where no handle type is involved (these are plain integer narrowing, not handle extraction).

---

## 3. FIR Style Fixes

**3a. Padding field naming:** Rename `padding_`, `reserved2_` → `reserved_` everywhere. Use arrays where multiple bytes needed: `uint8_t reserved_[2]`.

**3b. Field initialization:** Add `= 0` / `= {}` default initializers to all `FirType` members, matching the pattern already used by `FirNode`.

**3c. Bounds checking:** Add `assert(file_id < files_.size())` to `SourceMap::getFile()`.

**3d. Serialization comments:** Fix module doc "FIR v9" → "FIR v11". Rename `kHeaderSizeV6` → `kHeaderSize`.

---

## 4. FIR Encapsulation — Property Mutation API

**Problem:** `eval_expr.cppm:796-920` directly indexes `fir.model.props[]` to mutate properties. This couples sema to FIR's internal storage layout.

**Solution:** Add mutation methods to `ModelGraph`:

```cpp
bool update_property(NodeHandle node, RoleHandle role, ValueHandle new_val);
bool update_property(NodeHandle node, RoleHandle role, NodeHandle new_ref);
bool add_to_property(NodeHandle node, RoleHandle role, ValueHandle val);
bool add_to_property(NodeHandle node, RoleHandle role, NodeHandle ref);
bool remove_property(NodeHandle node, RoleHandle role);
```

Refactor all direct `props[]` access in `eval_expr.cppm` to use these methods.

---

## 5. FirProp Bit Manipulation Helpers

**Problem:** Inline bit masking (`role_flags & ~kNodeBit`, `kore::Cast(role) | kNodeBit`) repeated at multiple call sites without encapsulation.

**Solution:** Add static helpers to `FirProp` or as free functions:

```cpp
static uint32_t make_role_flags(RoleHandle role, bool is_node);
static RoleHandle extract_role(uint32_t role_flags);
static bool is_node_ref(uint32_t role_flags);
static bool is_foreign(uint32_t role_flags);
```

---

## 6. Sema: Eliminate Duplicate String Stripping

**Problem:** `strip_string_literal()` is copy-pasted in `lower_types.cppm` and `lower_expr.cppm`. The lexer already has `content_range()` that does this correctly.

**Solution:**
- Add `StringLiteralExpr : public LiteralExpr` with a `ContentRange content_range_` field.
- Parser creates `StringLiteralExpr` when `token_kind` is `StringLiteral` or `RawString`, populating `content_range_` via the lexer's `content_range()`.
- Bare value literals (`IntegerLiteral`, `FloatLiteral`, `True`, `False`) continue using `LiteralExpr`.
- Delete both copies of `strip_string_literal()`.
- Sema call sites: `source.substr(slit->content_offset(), slit->content_length())`.
- Update `ParserContext` max-size computation to include `sizeof(StringLiteralExpr)`.

**Also:** Move `try_extract_int_literal()` and `try_extract_float_literal()` into a new `rupa.sema-expr-utils.cppm` module (these parse numeric text from source ranges — a sema concern, not a lexer concern).

---

## 7. Sema: Split `lower_assignment()`

**Problem:** `lower_instances.cppm:153-410` is a 257-line, 12-parameter function handling role resolution, type inference, nested instantiation, property management, identity tracking, and assignment semantics.

**Solution:** Split into three focused functions:
- `lower_value_assignment()` — scalar value property (`=`, `+=`)
- `lower_nested_instantiation()` — nested object creation with block body
- `lower_bare_block()` — anonymous block body processing

The parent `lower_assignment()` becomes a ~20-line dispatcher.

---

## 8. Sema: Simplify Statement Graph

**Problem:** Three modules (`sema-stmt-graph`, `sema-graph-builder`, `sema-graph-executor`) handle let-binding ordering. The graph builder rebuilds dependency edges that `lower_exprs` already computed, duplicating work.

**Decision:** Merge all three into a single `rupa.sema-stmt-graph.cppm`. Remove the duplicated dependency computation — accept pre-computed edges from `lower_exprs` instead of rescanning the AST. The graph still handles `reads_model` sequencing (its primary value-add beyond simple topological sort).

---

## 9. Sema: Standardize Error Handling

**Problem:** Three inconsistent patterns: return-invalid-handle, diagnostic+continue, warning+return.

**Solution:** Adopt a single pattern: **diagnostic + return sentinel**.
- All lowering functions return typed sentinels (`kInvalidType`, `kInvalidExpr`, `kInvalidNode`).
- All diagnostics include source range (offset + length) — no more `0, 0`.
- Warnings only for recoverable issues (e.g., unresolved names in non-strict mode).
- Errors for anything that produces invalid FIR.

---

## 10. Sema: Standardize Depth Guards

**Problem:** Ad-hoc recursion limits vary: 200, 256, 1000 across different functions.

**Solution:** Define in `sema-context.cppm`:
```cpp
static constexpr uint32_t kMaxRecursionDepth = 256;
```
Replace all ad-hoc thresholds.

---

## 11. Documentation

**FIR modules (12 files):** Already well-documented (12/12 have module-level docs). Fix only stale comments (serial version mismatch from item 3d).

**Sema modules (11 files):** Add module-level documentation to the 6 undocumented files (`sema.cppm`, `sema-driver.cppm`, `sema-compiler.cppm`, `sema-context.cppm`, `sema-lower-instances.cppm`, `sema-lower-types.cppm`) matching FIR style:
- Module purpose and responsibility
- Key data structures with field explanations
- Module dependencies (imports)
- Usage examples where appropriate

**Sema umbrella (`rupa.sema.cppm`):** Add pipeline overview diagram:
```
/// Rupa Semantic Analysis Pipeline
///
/// Phase 1: lower_types      — AST type/role declarations → FIR TypeTable
/// Phase 2: lower_exprs      — AST let-statements → FIR expressions + symbols
/// Phase 3: stmt_graph       — dependency analysis + topological ordering + reads_model sequencing
/// Phase 4: lower_instances  — AST model blocks → FIR nodes + properties
/// Phase 5: eval_expr        — FIR expression evaluation + model mutation
///
/// Orchestrated by SemaDriver, which manages multi-file compilation,
/// import resolution, and context sharing across phases.
```

**FIR modules:** Review and enhance existing docs where function-level comments are missing (primarily in `fir-container.cppm` and `fir-source-map.cppm`).

---

## 12. Test Cleanup

**12a. Shared test base:** Extract `SemaTestBase` with common helpers:
- `compile_str(source)` — parse + lower + eval
- `value_of(n)` / `int_value_of(n)` / `string_value_of(n)` — value extraction
- Temp directory setup/teardown

**12b. Fix dangling `string_view`:** In `sema-eval-expr-test.cpp:47-51`, `string_value_of()` can return a view into a temporary SSO handle. Fix by ensuring stable reference.

**12c. Split large test files:** Break `sema-lower-expr-test.cpp` (1,226 lines) into:
- `sema-lower-expr-basics-test.cpp`
- `sema-lower-expr-deps-test.cpp`
- `sema-lower-expr-lambda-test.cpp`
- `sema-lower-expr-path-test.cpp`

**12d. Add negative tests:** To `fir-builder-test.cpp`: duplicate roles, double finalization, invalid parents.

---

## Dependencies

```
Item 1 (TinyVector)     — independent, touches kore submodule
Items 2-5 (FIR fixes)   — independent of each other, all touch FIR modules
Items 6-10 (sema fixes) — item 6 depends on parser change; items 7-10 independent of each other
Item 11 (docs)          — depends on items 1-10 (document final state)
Item 12 (tests)         — depends on items 1-10 (test final state)
```

## Risk Assessment

| Item | Risk | Mitigation |
|------|------|------------|
| 1 (TinyVector) | Low | Mechanical replacement, compile errors catch misses |
| 2 (Handle cast) | Low | Mechanical replacement, type-safe |
| 3 (FIR style) | Low | Cosmetic + one bounds check |
| 4 (Property API) | Medium | New API must cover all eval_expr mutation patterns |
| 5 (Bit helpers) | Low | Encapsulation of existing logic |
| 6 (StringLiteralExpr) | Medium | New AST subclass, parser change, arena sizing |
| 7 (Split lower_assignment) | Medium | Must preserve exact semantics across all assignment kinds |
| 8 (Graph merge) | Medium-High | Most complex refactor; must preserve let ordering semantics |
| 9 (Error handling) | Low-Medium | Adding source ranges to existing diagnostics |
| 10 (Depth guards) | Low | Constant replacement |
| 11 (Docs) | Low | Additive only |
| 12 (Tests) | Low-Medium | Refactoring test infrastructure |
