# FIR + Sema Architectural Cleanup — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize patterns, improve encapsulation, simplify over-engineered infrastructure, and add comprehensive documentation across the FIR and sema subsystems.

**Architecture:** 10 batches touching kore (1 module), FIR (12 modules), sema (11 modules), parser (3 modules), and tests (27 files). Changes flow bottom-up: kore → FIR → sema → tests → docs. Each batch is independently completable and testable.

**Tech Stack:** C++23 modules (.cppm), CMake, GoogleTest, kore library

**Design doc:** `docs/plans/2026-03-08-fir-sema-cleanup-design.md`

---

## Batch 1: kore::TinyVector Enhancement

**Scope:** Add `operator[]`, `front()`, `back()`, `empty()`, `begin()`, `end()` to `TinyVector` (the raw storage class). `TinyVectorView` already has these — this batch brings `TinyVector` to parity, then replaces 81 `.data()[i]` sites.

### Task 1.1: Add accessors to TinyVector

**Files:**
- Modify: `external/rupa/external/kore/src/containers/kore.containers.tiny_vector.cppm:108-136`
- Test: `external/rupa/external/kore/test/tiny-vec-test/tiny-vec-test.cpp`

**Step 1: Add methods to TinyVector class (after `data() const` at line 122, before `size()` at line 124)**

```cpp
    // --- Indexed access ---------------------------------------------------
    [[nodiscard]] T& operator[](SizeType i) noexcept { return data()[i]; }
    [[nodiscard]] T const& operator[](SizeType i) const noexcept { return data()[i]; }

    // --- Element access ---------------------------------------------------
    [[nodiscard]] T& front() noexcept { return data()[0]; }
    [[nodiscard]] T const& front() const noexcept { return data()[0]; }
    [[nodiscard]] T& back() noexcept { return data()[size_ - 1]; }
    [[nodiscard]] T const& back() const noexcept { return data()[size_ - 1]; }

    // --- State ------------------------------------------------------------
    [[nodiscard]] bool empty() const noexcept { return size_ == 0; }

    // --- Iterators (raw pointer — storage is contiguous) ------------------
    [[nodiscard]] T* begin() noexcept { return data(); }
    [[nodiscard]] T* end() noexcept { return data() + size_; }
    [[nodiscard]] T const* begin() const noexcept { return data(); }
    [[nodiscard]] T const* end() const noexcept { return data() + size_; }
```

**Step 2: Write tests in tiny-vec-test.cpp**

Add a new test group `TinyVectorAccessorTest` after the existing `TinyVectorStorageTest`:

```cpp
TEST(TinyVectorAccessorTest, OperatorBracket) {
    TinyVector<int> v;
    v.set_size(1);
    v[0] = 99;
    EXPECT_EQ(v[0], 99);
}

TEST(TinyVectorAccessorTest, ConstOperatorBracket) {
    TinyVector<int> v;
    v.set_size(1);
    v.data()[0] = 42;
    const auto& cv = v;
    EXPECT_EQ(cv[0], 42);
}

TEST(TinyVectorAccessorTest, FrontBack) {
    TinyVector<int, uint32_t, 4> v;
    v.set_size(3);
    v[0] = 10; v[1] = 20; v[2] = 30;
    EXPECT_EQ(v.front(), 10);
    EXPECT_EQ(v.back(), 30);
}

TEST(TinyVectorAccessorTest, Empty) {
    TinyVector<int> v;
    EXPECT_TRUE(v.empty());
    v.set_size(1);
    EXPECT_FALSE(v.empty());
}

TEST(TinyVectorAccessorTest, BeginEnd) {
    TinyVector<int, uint32_t, 4> v;
    v.set_size(3);
    v[0] = 1; v[1] = 2; v[2] = 3;
    int sum = 0;
    for (auto x : v) sum += x;
    EXPECT_EQ(sum, 6);
}

TEST(TinyVectorAccessorTest, ConstBeginEnd) {
    TinyVector<int, uint32_t, 4> v;
    v.set_size(2);
    v[0] = 5; v[1] = 7;
    const auto& cv = v;
    int sum = 0;
    for (auto x : cv) sum += x;
    EXPECT_EQ(sum, 12);
}
```

**Step 3: Run tests**

```bash
cd external/rupa/external/kore && cmake --build --preset debug && ctest --preset debug -R tiny -v
```

**Step 4: Commit**

```bash
git add src/containers/kore.containers.tiny_vector.cppm test/tiny-vec-test/tiny-vec-test.cpp
git commit -m "feat(TinyVector): add operator[], front/back, empty, begin/end iterators"
```

### Task 1.2: Replace .data()[i] in parser modules

**Files:**
- Modify: `external/rupa/src/parser/rupa.parser-statements.cppm` (10 sites)
- Modify: `external/rupa/src/parser/rupa.parser-expressions.cppm` (1 site)

**Step 1: Mechanical replacement**

For each `.data()[i]` site, apply one of:
- **Indexed loop** (`for (uint32_t i = 0; i < vec.size(); ++i) ... vec.data()[i]`): Replace with `vec[i]`
- **First element** (`vec.data()[0]`): Replace with `vec.front()` if size check precedes it, or `vec[0]`
- **Range-for eligible** (index not used in body): Convert to `for (auto* elem : vec)`

Key sites in parser-statements.cppm:
- Line 366: `bases.data()[i]` → `bases[i]`
- Line 380: `role_annotations.data()[i]` → `role_annotations[i]`
- Line 544: `trailing_annotations.data()[i]` → `trailing_annotations[i]`
- Line 630: `params.data()[i]` → `params[i]`
- Line 1327: `annotations.data()[0]` → `annotations.front()`
- Line 1332: `annotations.data()[0]` → `annotations.front()`
- Line 1348: `annotations.data()[i]` → `annotations[i]`
- Line 1354: `annotations.data()[i]` → `annotations[i]`
- Line 1400: `file->statements().data()[0]` → `file->statements().front()`
- Line 1401: `file->statements().data()[...]` → `file->statements()[...]` or `.back()`

Key site in parser-expressions.cppm:
- Line 1164: `seq->values().data()[i]` → `seq->values()[i]`

**Step 2: Build to verify compilation**

```bash
cd external/rupa && cmake --build --preset debug
```

**Step 3: Run parser tests**

```bash
cd external/rupa && ctest --preset debug -R parser -v
```

**Step 4: Commit**

```bash
git add src/parser/rupa.parser-statements.cppm src/parser/rupa.parser-expressions.cppm
git commit -m "refactor(parser): replace .data()[i] with operator[] and front/back"
```

### Task 1.3: Replace .data()[i] in sema modules

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-expr.cppm` (16 sites)
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm` (10 sites)
- Modify: `external/rupa/src/sema/rupa.sema-lower-types.cppm` (10 sites)
- Modify: `external/rupa/src/sema/rupa.sema-driver.cppm` (1 site)
- Modify: `external/rupa/src/sema/rupa.sema-graph-builder.cppm` (1 site)

**Step 1: Mechanical replacement (same rules as Task 1.2)**

Key patterns:
- `sf->statements().data()[i]` → `sf->statements()[i]` (6 sites across driver, lower-types, lower-instances, lower-expr, graph-builder)
- `block->statements().data()[i]` → `block->statements()[i]` (4 sites in lower-instances, lower-expr)
- `segments.data()[0]` → `segments.front()` (3 sites in lower-expr, lower-instances)
- `segments.data()[i]` → `segments[i]` (loop iterations)
- `ast_args.data()[a]` → `ast_args[a]` (5 sites in lower-expr)
- `ast_params.data()[p]` → `ast_params[p]` (3 sites in lower-expr)
- `match_arms.data()[i]` → `match_arms[i]` (1 site)
- `composite->bases().data()[b]` → `composite->bases()[b]` (1 site)
- `composite->roles().data()[r]` → `composite->roles()[r]` (1 site)
- `enum_body->values().data()[i]` → `enum_body->values()[i]` (1 site)
- `pat_ann->params().data()[0]` → `pat_ann->params().front()` (1 site)
- `range_ann->params().data()[p]` → `range_ann->params()[p]` (2 sites)

**Step 2: Build and run sema tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R sema -v
```

**Step 3: Commit**

```bash
git add src/sema/
git commit -m "refactor(sema): replace .data()[i] with operator[] and front/back"
```

### Task 1.4: Replace .data()[i] in test files

**Files:**
- Modify: `external/rupa/test/parser/parser-type-def-test.cpp` (16 sites)
- Modify: `external/rupa/test/parser/parser-path-test.cpp` (19 sites)
- Modify: `external/rupa/test/parser/parser-integration-test.cpp` (11 sites)
- Modify: `external/rupa/external/kore/test/tiny-vec-test/tiny-vec-test.cpp` (2 sites in storage test)

**Step 1: Mechanical replacement (same rules)**

**Step 2: Run all tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 3: Commit**

```bash
git add test/ external/kore/test/
git commit -m "refactor(tests): replace .data()[i] with operator[] and front/back"
```

---

## Batch 2: Handle Extraction Consistency

**Scope:** Replace `static_cast<uint32_t>(handle)` with `kore::Cast(handle)` and `HandleType{static_cast<uint32_t>(expr)}` with `kore::Cast<HandleType>(expr)` across FIR modules. Only handle-typed casts — leave plain integer narrowing alone.

### Task 2.1: FIR core modules (handles, model, types, value)

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-handles.cppm` (1 site: line 182)
- Modify: `external/rupa/src/fir/rupa.fir-model.cppm` (5 sites: lines 186, 231, 232, 246, 247)
- Modify: `external/rupa/src/fir/rupa.fir-types.cppm` (17 sites)
- Modify: `external/rupa/src/fir/rupa.fir-value.cppm` (6 sites)

**Step 1: Replace handle-related casts**

Rules:
- `static_cast<uint32_t>(handle_enum_value)` → `kore::Cast(handle_enum_value)` when the source is a handle type (TypeHandle, RoleHandle, etc.)
- `HandleType{static_cast<uint32_t>(expr)}` → `kore::Cast<HandleType>(expr)` when constructing a handle from an index
- `static_cast<uint32_t>(nodes.size())` → `kore::Cast<NodeHandle>(static_cast<uint32_t>(nodes.size()))` only if the result is assigned to a handle; otherwise leave as narrowing cast
- `static_cast<uint32_t>(M3Kind::Composite)` — leave alone (enum, not handle)
- `static_cast<uint32_t>(mult)` — leave alone (enum, not handle)
- `static_cast<DomainId>(...)` and `static_cast<ModuleId>(...)` — leave alone (typedef aliases, not enum class handles)
- `static_cast<uint16_t>(...)` for prop_count, segment_count, etc. — leave alone (plain integer narrowing)

Example transformations in fir-model.cppm:
```cpp
// Line 186: auto h = NodeHandle{static_cast<uint32_t>(nodes.size())};
// →        auto h = kore::Cast<NodeHandle>(static_cast<uint32_t>(nodes.size()));

// Line 231: n.prop_start = static_cast<uint32_t>(props.size());
// →        (leave alone — this is uint32_t narrowing from size_t, not handle)
```

Example in fir-types.cppm:
```cpp
// Line 220: auto idx = static_cast<uint32_t>(types.size());
//           ... return TypeHandle{idx};
// →        auto idx = static_cast<uint32_t>(types.size());
//           ... return kore::Cast<TypeHandle>(idx);
```

**Step 2: Fix symbol and expr accessor inconsistency**

In `rupa.fir-symbol.cppm:281` and `:288`:
```cpp
// auto idx = static_cast<uint32_t>(h);
// → auto idx = kore::Cast(h);
```

In `rupa.fir-expr.cppm:699` and `:706`:
```cpp
// auto idx = static_cast<uint32_t>(h);
// → auto idx = kore::Cast(h);
```

**Step 3: Build and test**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R fir -v
```

**Step 4: Commit**

```bash
git add src/fir/
git commit -m "refactor(fir): standardize handle extraction to kore::Cast"
```

### Task 2.2: Serialization module

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-serial.cppm` (~100 handle-related sites out of 126 total)

**Step 1: Replace handle casts in serialize()**

The serialize function writes handle fields to the binary buffer. Pattern:
```cpp
// w32(buf, static_cast<uint32_t>(t.supertype));
// → w32(buf, kore::Cast(t.supertype));
```

Apply to all handle fields: `t.supertype`, `t.name`, `r.target`, `r.name`, `n.type`, `n.parent`, `n.derived_from`, `p.value_type`, `p.ref`, expression handles, symbol handles, etc.

**Do NOT change:** byte-level read helpers (`r32`, `r16`), header offset constants, string remapper internals.

**Step 2: Replace handle casts in deserialize()**

Same pattern for deserialization reads:
```cpp
// t.supertype = TypeHandle{r32(p + 8)};
// → t.supertype = kore::Cast<TypeHandle>(r32(p + 8));
```

**Step 3: Build and run serialization tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R serial -v
```

**Step 4: Commit**

```bash
git add src/fir/rupa.fir-serial.cppm
git commit -m "refactor(fir-serial): standardize handle casts to kore::Cast"
```

### Task 2.3: Sema modules

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-expr.cppm` (1 site: line 132)
- Modify: `external/rupa/src/sema/rupa.sema-stmt-graph.cppm` (3 sites: lines 45, 59, 82)

**Step 1: Replace casts**

In sema-lower-expr.cppm:132:
```cpp
// scopes_.push_back({static_cast<uint32_t>(entries_.size())});
// → (leave alone — this is plain uint32_t narrowing, not handle)
```

In sema-stmt-graph.cppm:45:
```cpp
// auto idx = static_cast<uint32_t>(nodes.size());
// → (leave alone — graph node index, not a FIR handle)
```

**Result:** After review, all sema `static_cast<uint32_t>` sites are plain integer narrowing, not handle extraction. No changes needed.

**Step 2: Commit (skip if no changes)**

---

## Batch 3: FIR Style Fixes

### Task 3.1: Padding field naming

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-symbol.cppm`
  - Line 124: `uint16_t reserved2_ = 0;` → `uint16_t reserved_ = 0;` in FirFnSym
  - Line 135: `uint8_t reserved2_[3] = {};` → `uint8_t reserved_[3] = {};` in FirRuleSym
  - Line 154: `uint16_t padding_ = 0;` → `uint16_t reserved_ = 0;` in FirImportedSym
- Modify: `external/rupa/src/fir/rupa.fir-expr.cppm`
  - Line 225: `uint8_t reserved2_[3] = {};` → `uint8_t reserved_[3] = {};` in FirRoleNavExpr
  - Lines 326, 341, 355, 368, 381: `uint16_t reserved2_ = 0;` → `uint16_t reserved_ = 0;` in FirCallExpr, FirPipeExpr, FirMatchExpr, FirListExpr, FirBlockExpr

**Note:** Multiple structs can have a field named `reserved_` — they're different types, no conflict.

**Step 1: Make all replacements**

**Step 2: Build**

```bash
cd external/rupa && cmake --build --preset debug
```

**Step 3: Commit**

```bash
git add src/fir/rupa.fir-symbol.cppm src/fir/rupa.fir-expr.cppm
git commit -m "style(fir): standardize padding field names to reserved_"
```

### Task 3.2: FirType field initialization

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-types.cppm:103-112`

**Step 1: Add default initializers**

```cpp
struct FirType {
    uint32_t   flags = 0;
    StringId   name{};
    TypeHandle supertype = kInvalidType;
    uint32_t   role_start = 0;
    uint16_t   role_count = 0;
    uint16_t   aux_count = 0;
    uint32_t   aux_start = 0;
    DomainId   domain = kInvalidDomain;
    uint16_t   reserved_ = 0;
};
```

**Step 2: Update add_type() to remove redundant initialization**

In `TypeTable::add_type()` (line 219-235), the manual field-by-field initialization can remain (it sets non-default values), but verify no aggregate initialization sites break.

**Step 3: Build and test**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R fir -v
```

**Step 4: Commit**

```bash
git add src/fir/rupa.fir-types.cppm
git commit -m "style(fir): add default initializers to FirType fields"
```

### Task 3.3: SourceMap bounds check + serial version comments

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-source-map.cppm:125-127`
- Modify: `external/rupa/src/fir/rupa.fir-serial.cppm:3, 113, 116`

**Step 1: Add bounds check to getFile()**

```cpp
const FileEntry& getFile(uint32_t file_id) const {
    assert(file_id < files_.size());
    return files_[file_id];
}
```

**Step 2: Fix serial version comments**

- Line 3: `/// FIR v9 Binary Serialization` → `/// FIR v11 Binary Serialization`
- Line 116: `constexpr uint32_t kHeaderSizeV6 = 252;` → `constexpr uint32_t kHeaderSize = 252;`
- Update all references to `kHeaderSizeV6` in the file to `kHeaderSize`

**Step 3: Build and test**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 4: Commit**

```bash
git add src/fir/rupa.fir-source-map.cppm src/fir/rupa.fir-serial.cppm
git commit -m "fix(fir): add getFile bounds check, fix serial version comments"
```

---

## Batch 4: FIR Encapsulation

### Task 4.1: FirProp bit manipulation helpers

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-model.cppm:125-162`

**Step 1: Add static helpers to FirProp**

Replace the existing `make_value`/`make_node` static methods and add extraction helpers:

```cpp
struct FirProp {
    static constexpr uint32_t kNodeBit    = 0x4000'0000u;
    static constexpr uint32_t kForeignBit = 0x8000'0000u;
    static constexpr uint32_t kIndexMask  = ~(kNodeBit | kForeignBit);

    uint32_t    role_flags;
    TypeHandle  value_type;
    uint32_t    ref;

    // --- Construction helpers ---
    static FirProp make_value(RoleHandle role, TypeHandle type, ValueHandle val) {
        return {kore::Cast(role), type, kore::Cast(val)};
    }
    static FirProp make_node(RoleHandle role, TypeHandle type, NodeHandle node) {
        return {kore::Cast(role) | kNodeBit, type, kore::Cast(node)};
    }

    // --- Extraction helpers ---
    [[nodiscard]] bool is_node() const { return (role_flags & kNodeBit) != 0; }
    [[nodiscard]] bool is_foreign() const { return (role_flags & kForeignBit) != 0; }

    [[nodiscard]] RoleHandle role() const {
        return kore::Cast<RoleHandle>(role_flags & ~kNodeBit);
    }
    [[nodiscard]] uint32_t role_index() const {
        return role_flags & kIndexMask;
    }

    [[nodiscard]] ValueHandle value_handle() const {
        assert(!is_node());
        return kore::Cast<ValueHandle>(ref);
    }
    [[nodiscard]] NodeHandle node_handle() const {
        assert(is_node());
        return kore::Cast<NodeHandle>(ref);
    }
};
```

**Step 2: Update all FirProp construction sites to use helpers if not already**

Grep for direct `kNodeBit` usage outside of FirProp and update.

**Step 3: Build and test**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 4: Commit**

```bash
git add src/fir/rupa.fir-model.cppm
git commit -m "refactor(fir): encapsulate FirProp bit manipulation in static helpers"
```

### Task 4.2: Property mutation API

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-model.cppm` (add methods to ModelGraph)
- Test: `external/rupa/test/fir/fir-model-test.cpp` (add mutation tests)

**Step 1: Write failing tests**

```cpp
TEST_F(FirModelTest, UpdateValueProperty) {
    auto th = builder.add_type("Signal", fir::M3Kind::Composite);
    auto name_rh = builder.add_role(th, "name", fir.builtins.string, fir::Multiplicity::One);
    builder.finalize_roles(th);
    auto nh = builder.begin_object(th);
    auto v1 = builder.add_string("old");
    fir.model.flush_props(nh, {{fir::FirProp::make_value(name_rh, fir.builtins.string, v1)}});
    auto v2 = builder.add_string("new");
    EXPECT_TRUE(fir.model.update_property(nh, name_rh, v2));
    auto props = fir.model.props_of(fir.model.node(nh));
    ASSERT_EQ(props.size(), 1);
    EXPECT_EQ(props[0].value_handle(), v2);
}

TEST_F(FirModelTest, RemoveProperty) {
    auto th = builder.add_type("Signal", fir::M3Kind::Composite);
    auto name_rh = builder.add_role(th, "name", fir.builtins.string, fir::Multiplicity::One);
    builder.finalize_roles(th);
    auto nh = builder.begin_object(th);
    auto v1 = builder.add_string("hello");
    fir.model.flush_props(nh, {{fir::FirProp::make_value(name_rh, fir.builtins.string, v1)}});
    EXPECT_TRUE(fir.model.remove_property(nh, name_rh));
    auto props = fir.model.props_of(fir.model.node(nh));
    bool found = false;
    for (auto& p : props) if (kore::Cast(p.role()) == kore::Cast(name_rh)) found = true;
    EXPECT_FALSE(found);
}
```

**Step 2: Run tests to verify they fail**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R fir.model -v
```

**Step 3: Implement mutation methods in ModelGraph**

Add to `ModelGraph` class (after `props_of`):

```cpp
    /// Update the first property matching `role` to hold `new_val`.
    bool update_property(NodeHandle nh, RoleHandle role, ValueHandle new_val) {
        auto& n = node(nh);
        for (uint16_t i = 0; i < n.prop_count; ++i) {
            auto& p = props[n.prop_start + i];
            if (kore::Cast(p.role()) == kore::Cast(role)) {
                p = FirProp::make_value(role, p.value_type, new_val);
                return true;
            }
        }
        return false;
    }

    /// Update the first property matching `role` to hold a node reference.
    bool update_property(NodeHandle nh, RoleHandle role, NodeHandle new_ref) {
        auto& n = node(nh);
        for (uint16_t i = 0; i < n.prop_count; ++i) {
            auto& p = props[n.prop_start + i];
            if (kore::Cast(p.role()) == kore::Cast(role)) {
                p = FirProp::make_node(role, p.value_type, new_ref);
                return true;
            }
        }
        return false;
    }

    /// Add a value to the property list (appends at end of node's prop span).
    /// Note: only works if node is the last one that had props flushed,
    /// because props are stored contiguously. For general use, rebuild props.
    bool add_to_property(NodeHandle nh, RoleHandle role, ValueHandle val, TypeHandle type) {
        auto& n = node(nh);
        // Append only if this node's props are at the end of the props vector
        if (n.prop_start + n.prop_count == static_cast<uint32_t>(props.size())) {
            props.push_back(FirProp::make_value(role, type, val));
            n.prop_count++;
            return true;
        }
        return false;
    }

    /// Remove all properties matching `role` by zeroing them (tombstone pattern).
    bool remove_property(NodeHandle nh, RoleHandle role) {
        auto& n = node(nh);
        bool found = false;
        for (uint16_t i = 0; i < n.prop_count; ++i) {
            auto& p = props[n.prop_start + i];
            if (kore::Cast(p.role()) == kore::Cast(role)) {
                p.role_flags = kore::Cast(kInvalidRole);
                found = true;
            }
        }
        return found;
    }
```

**Step 4: Run tests to verify they pass**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R fir -v
```

**Step 5: Commit**

```bash
git add src/fir/rupa.fir-model.cppm test/fir/fir-model-test.cpp
git commit -m "feat(fir): add property mutation API to ModelGraph"
```

### Task 4.3: Refactor eval_expr to use property mutation API

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-eval-expr.cppm:796-920`

**Step 1: Replace direct props[] access with ModelGraph methods**

Find all `fir.model.props[prop_start + i]` patterns in the ModelOp evaluation block and replace with calls to `update_property()`, `add_to_property()`, `remove_property()`.

**Step 2: Build and run sema tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R sema -v
```

**Step 3: Commit**

```bash
git add src/sema/rupa.sema-eval-expr.cppm
git commit -m "refactor(sema): use ModelGraph mutation API instead of direct props[] access"
```

---

## Batch 5: StringLiteralExpr + Expression Utilities

### Task 5.1: Add StringLiteralExpr AST node

**Files:**
- Modify: `external/rupa/src/parser/rupa.parser-ast.cppm`
- Modify: `external/rupa/src/parser/rupa.parser-context.cppm` (max_node_size)
- Modify: `external/rupa/src/parser/rupa.parser-expressions.cppm` (parse_literal)
- Modify: `external/rupa/src/parser/rupa.parser-statements.cppm` (string literal creation sites)

**Step 1: Add StringLiteralExpr class after LiteralExpr (ast.cppm:156)**

```cpp
// "hello", r#"raw"#  — string literals with content range
class StringLiteralExpr : public LiteralExpr
{
public:
  StringLiteralExpr(SourceRange range, rupa::lexer::TokenKind token_kind,
                    rupa::lexer::ContentRange content)
      : LiteralExpr(range, token_kind), content_(content) {}

  static bool classof(const AstNode* n) {
      if (n->kind() != NodeKind::LiteralExpr) return false;
      auto tk = static_cast<const LiteralExpr*>(n)->token_kind();
      return tk == rupa::lexer::TokenKind::StringLiteral
          || tk == rupa::lexer::TokenKind::RawString
          || tk == rupa::lexer::TokenKind::RawBlock;
  }

  rupa::lexer::ContentRange content_range() const { return content_; }
  uint32_t content_offset() const { return content_.offset; }
  uint32_t content_length() const { return content_.length; }

private:
  rupa::lexer::ContentRange content_;
};
```

Also add `NodeKind::LiteralExpr` must remain shared — `StringLiteralExpr` reuses the same `NodeKind` and is distinguished only by RTTI (classof checks token_kind). This is correct — no new NodeKind needed.

**Step 2: Update max_node_size() in parser-context.cppm**

After the LiteralExpr line (431), add:
```cpp
    m = m > sizeof(StringLiteralExpr) ? m : sizeof(StringLiteralExpr);
```

**Step 3: Update parse_literal() in parser-expressions.cppm**

```cpp
AstNode* parse_literal(ParserContext& ctx)
{
  auto tok = ctx.current();
  AstNode* node;
  if (tok.kind == TK::StringLiteral || tok.kind == TK::RawString || tok.kind == TK::RawBlock) {
      node = ctx.create<StringLiteralExpr>(ctx.range_of(tok), tok.kind,
                                            rupa::lexer::content_range(tok));
  } else {
      node = ctx.create<LiteralExpr>(ctx.range_of(tok), tok.kind);
  }
  ctx.advance();
  return node;
}
```

**Step 4: Update string literal creation in parser-statements.cppm**

Find all `ctx.create<LiteralExpr>(...)` where the token kind is `StringLiteral` and update to `ctx.create<StringLiteralExpr>(...)`. Key sites:
- Line 343: enum string value
- Line 759: import source
- Line 1108: identity string
- Line 1266: identity string

Each should check `tok.kind == TK::StringLiteral` and create `StringLiteralExpr`.

**Step 5: Build and run parser tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R parser -v
```

**Step 6: Commit**

```bash
git add src/parser/
git commit -m "feat(parser): add StringLiteralExpr with content_range from lexer"
```

### Task 5.2: Update sema to use StringLiteralExpr

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-expr.cppm` (delete strip_string_literal, use content_range)
- Modify: `external/rupa/src/sema/rupa.sema-lower-types.cppm` (delete strip_string_literal, use content_range)
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm` (use content_range)

**Step 1: In lower-expr.cppm, delete strip_string_literal (lines 38-50)**

**Step 2: Update LiteralExpr handling in lower_expr (lower-expr.cppm:259-267)**

```cpp
case NK::LiteralExpr: {
    auto* lit = cast<LiteralExpr>(expr);
    auto range = lit->range();
    auto text = source.substr(range.offset, range.length);

    if (auto* slit = fir::rtti::dyn_cast<StringLiteralExpr>(lit)) {
        auto content = source.substr(slit->content_offset(), slit->content_length());
        auto sid = fir.intern(content);
        auto vh = fir.model.values.add_string(sid);
        return fir.expressions.add_literal(vh, fir.builtins.string);
    }
    // ... rest of literal handling (int, float, bool) unchanged
```

**Step 3: In lower-types.cppm, delete strip_string_literal (lines 80-94)**

Update all call sites in lower_types that use `strip_string_literal`:
- Line 400-402: enum string value → use `dyn_cast<StringLiteralExpr>` + `content_range()`
- Line 427-430: pattern annotation → use content_range
- Line 437-438: parse annotation → use content_range

**Step 4: In lower-instances.cppm, update string literal handling**

- Line 246-249: nested identity → use `dyn_cast<StringLiteralExpr>` + `content_range()`
- Line 425-428: string literal value → use content_range
- Line 611-614: identity extraction → use content_range

**Step 5: Build and run all tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 6: Commit**

```bash
git add src/sema/ src/parser/
git commit -m "refactor(sema): use StringLiteralExpr.content_range(), delete strip_string_literal"
```

### Task 5.3: Create sema-expr-utils module

**Files:**
- Create: `external/rupa/src/sema/rupa.sema-expr-utils.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-lower-expr.cppm` (remove try_extract_*)
- Modify: `external/rupa/src/sema/rupa.sema-lower-types.cppm` (remove try_extract_*)
- Modify: CMakeLists.txt for sema module

**Step 1: Create the module**

```cpp
/// Shared expression utility functions for semantic analysis.
///
/// Provides literal extraction helpers used by both type lowering
/// and expression lowering. These parse numeric text from source
/// ranges — a sema concern (the lexer tokenizes but doesn't parse
/// numeric values).
module;

#include <charconv>
#include <cstdint>
#include <optional>
#include <string_view>

export module rupa.sema.expr_utils;

import rupa.parser;

using rupa::parser::AstNode;
using rupa::parser::LiteralExpr;
using rupa::parser::PrefixOpExpr;

export namespace rupa::sema {

/// Try to extract an integer literal from an AST node.
/// Handles both positive literals and negated literals (PrefixOpExpr with '-').
std::optional<int64_t> try_extract_int(const AstNode* node, std::string_view source);

/// Try to extract a float literal from an AST node.
/// Handles both positive and negated float literals.
std::optional<double> try_extract_float(const AstNode* node, std::string_view source);

} // namespace rupa::sema
```

Then implement both functions using the existing logic from lower_types.cppm:203-258.

**Step 2: Update lower_types.cppm and lower_expr.cppm**

Delete the local definitions and `import rupa.sema.expr_utils;` instead. Update call sites:
- `try_extract_int_literal(node, source, &val)` → `auto val = rupa::sema::try_extract_int(node, source);`

**Step 3: Update CMakeLists.txt**

Add `rupa.sema-expr-utils.cppm` to the sema module sources.

**Step 4: Build and test**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 5: Commit**

```bash
git add src/sema/rupa.sema-expr-utils.cppm src/sema/rupa.sema-lower-expr.cppm src/sema/rupa.sema-lower-types.cppm CMakeLists.txt
git commit -m "refactor(sema): extract try_extract_int/float to sema-expr-utils module"
```

---

## Batch 6: Split lower_assignment

### Task 6.1: Extract lower_value_assignment

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm:153-410`

**Step 1: Extract the scalar value assignment path**

Identify the code block in `lower_assignment()` that handles simple value assignments (no nested block, no bare block). Extract into:

```cpp
static void lower_value_assignment(
    const AstNode* value_expr,
    RoleHandle rh,
    TypeHandle role_target,
    NodeHandle obj_nh,
    std::vector<FirProp>& prop_list,
    fir::Fir& fir,
    std::string_view source,
    SemaDiagnostics& diagnostics)
```

**Step 2: Extract lower_nested_instantiation**

Extract the code block that creates nested objects with typed block bodies:

```cpp
static void lower_nested_instantiation(
    const AstNode* type_expr,
    const BlockBody* block,
    RoleHandle rh,
    TypeHandle obj_type_th,
    NodeHandle obj_nh,
    std::vector<FirProp>& prop_list,
    fir::Fir& fir,
    const kore::FrozenMap<StringId, TypeHandle>& type_names,
    const RoleCache& role_cache,
    std::string_view source,
    std::string_view file_path,
    SemaDiagnostics& diagnostics,
    absl::flat_hash_map<uint32_t, StringId>& node_identities)
```

**Step 3: Extract lower_bare_block**

Extract the anonymous block processing:

```cpp
static void lower_bare_block(
    const BlockBody* block,
    RoleHandle rh,
    TypeHandle role_target,
    NodeHandle obj_nh,
    std::vector<FirProp>& prop_list,
    fir::Fir& fir,
    const kore::FrozenMap<StringId, TypeHandle>& type_names,
    const RoleCache& role_cache,
    std::string_view source,
    std::string_view file_path,
    SemaDiagnostics& diagnostics,
    absl::flat_hash_map<uint32_t, StringId>& node_identities)
```

**Step 4: Reduce lower_assignment to dispatcher**

```cpp
static void lower_assignment(
    const Assignment* assign, /* ... same params ... */)
{
    auto role_name = /* resolve role name */;
    auto rh = resolve_role(role_name, obj_type_th, role_cache, fir, diagnostics);
    if (fir::is_none(rh)) return;
    auto role_target = fir.types.role(rh).target;

    auto* rhs = assign->value();
    if (auto* block = dyn_cast<BlockBody>(rhs)) {
        if (/* has type expression */) {
            lower_nested_instantiation(/* ... */);
        } else {
            lower_bare_block(/* ... */);
        }
    } else {
        lower_value_assignment(/* ... */);
    }
}
```

**Step 5: Build and run sema tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R sema -v
```

**Step 6: Commit**

```bash
git add src/sema/rupa.sema-lower-instances.cppm
git commit -m "refactor(sema): split lower_assignment into three focused functions"
```

---

## Batch 7: Merge Statement Graph Modules

### Task 7.1: Merge into single module

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-stmt-graph.cppm` (absorb other two modules)
- Delete: `external/rupa/src/sema/rupa.sema-graph-builder.cppm`
- Delete: `external/rupa/src/sema/rupa.sema-graph-executor.cppm`
- Modify: `external/rupa/src/sema/rupa.sema.cppm` (update re-exports)
- Modify: CMakeLists.txt (remove deleted files)

**Step 1: Copy the exported functions from graph-builder and graph-executor into stmt-graph**

Move `build_stmt_graph()` (graph-builder.cppm:179-332) and `execute_stmt_graph()` (graph-executor.cppm:34-72) into `sema-stmt-graph.cppm`, along with their internal helpers (`expr_reads_model`, `collect_called_symbols`).

**Step 2: Remove duplicated dependency edge computation**

In the current `build_stmt_graph()`, lines 179-230 rebuild dependency edges from `lower_output.dep_edges`. Instead, accept the pre-computed edges directly and wire them into the StmtGraph without rescanning.

**Step 3: Update sema.cppm re-exports**

Remove:
```cpp
export import rupa.sema.graph_builder;
export import rupa.sema.graph_executor;
```

**Step 4: Update CMakeLists.txt**

Remove the two deleted module files.

**Step 5: Update driver.cppm imports**

Replace individual imports with the unified `rupa.sema.stmt_graph`.

**Step 6: Build and run all tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 7: Commit**

```bash
git add src/sema/ CMakeLists.txt
git commit -m "refactor(sema): merge statement graph into single module, remove edge duplication"
```

---

## Batch 8: Error Handling + Depth Guards

### Task 8.1: Standardize depth guard constant

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-context.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-eval-expr.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-stmt-graph.cppm` (post-merge)

**Step 1: Add constant to sema-context.cppm**

After `SemaDiagnosticKind` enum:
```cpp
/// Maximum recursion depth for expression evaluation and type resolution.
static constexpr uint32_t kMaxRecursionDepth = 256;
```

**Step 2: Replace all ad-hoc thresholds**

- `sema-context.cppm:173`: `constexpr uint32_t max_depth = 256;` → `kMaxRecursionDepth`
- `sema-lower-instances.cppm:49`: `constexpr uint32_t max_depth = 256;` → `kMaxRecursionDepth`
- `sema-eval-expr.cppm:140`: `constexpr uint32_t max_depth = 256;` → `kMaxRecursionDepth`
- `sema-eval-expr.cppm:157`: `constexpr uint32_t max_depth = 256;` → `kMaxRecursionDepth`
- `sema-eval-expr.cppm:267`: `if (depth > 1000)` → `if (depth > kMaxRecursionDepth)`
- `sema-stmt-graph.cppm` (merged): `depth > 200` checks → `depth > kMaxRecursionDepth`

**Step 3: Build and test**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 4: Commit**

```bash
git add src/sema/
git commit -m "refactor(sema): standardize depth guards to kMaxRecursionDepth = 256"
```

### Task 8.2: Add source ranges to zero-offset diagnostics

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-context.cppm` (line 141)
- Modify: `external/rupa/src/sema/rupa.sema-driver.cppm` (lines 87, 129, 230)

**Step 1: Review all `error(..., 0, 0)` and `warning(..., 0, 0)` sites**

For each, determine if a source range is available from the AST node being processed. If so, pass `range.offset, range.length` instead of `0, 0`.

Key sites:
- `sema-context.cppm:141`: `DuplicateTypeName, 0, 0` — called from `registerType()` which doesn't receive AST context. Leave as-is but add a comment explaining why.
- `sema-driver.cppm:87`: `CyclicValueDependency, 0, 0` — global diagnostic, no specific node. Leave as-is.
- `sema-driver.cppm:129`: `CircularImport, 0, 0` — file-level, not node-level. Leave as-is.
- `sema-driver.cppm:230`: `DuplicateTypeName, 0, 0` — TypeDef available; extract range from AST.

**Step 2: Build and test**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -v
```

**Step 3: Commit**

```bash
git add src/sema/
git commit -m "refactor(sema): add source ranges to diagnostics where available"
```

---

## Batch 9: Documentation

### Task 9.1: Sema umbrella pipeline overview

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema.cppm`

**Step 1: Add comprehensive module documentation**

Replace the bare re-export file with documented umbrella:

```cpp
/// Rupa Semantic Analysis
///
/// The sema subsystem transforms a parsed AST into a fully resolved FIR
/// (Formal Intermediate Representation). It operates in five phases:
///
///   Phase 1 — lower_types (sema-lower-types)
///     Collects type and role declarations from the AST and populates the
///     FIR TypeTable. Resolves inheritance, enum values, constraints, and
///     role targets. Uses a two-pass approach: collect all names first,
///     then resolve cross-references with a dependency-ordered worklist.
///
///   Phase 2 — lower_exprs (sema-lower-expr)
///     Lowers let-bindings and function definitions from the AST into FIR
///     expression trees and symbols. Builds a scope stack for name resolution,
///     computes inter-symbol dependency edges, and performs topological sort
///     to determine evaluation order. Forward references are supported.
///
///   Phase 3 — stmt_graph (sema-stmt-graph)
///     Builds a unified dependency graph over let-bindings, function defs,
///     and model operations. Handles reads_model detection to sequence
///     model-reading lets after model mutations. Produces a topological
///     execution order that respects both data dependencies and model
///     access ordering.
///
///   Phase 4 — lower_instances (sema-lower-instances)
///     Processes model instantiation blocks from the AST. Creates FIR nodes,
///     resolves roles against the TypeTable, handles nested instantiation,
///     identity tracking, and property construction (via flush_props).
///
///   Phase 5 — eval_expr (sema-eval-expr)
///     Evaluates FIR expressions to produce concrete values. Performs
///     constant folding (arithmetic, string, logical), variable resolution,
///     function calls, model access (path navigation, type filtering),
///     and model mutation (assign, add, reset, delete).
///
/// The pipeline is orchestrated by SemaDriver (sema-driver), which manages
/// multi-file compilation, import resolution, and domain registration.
/// SemaContext (sema-context) holds shared state: the FIR, diagnostics,
/// and frozen type name maps.
///
/// Shared utilities live in sema-expr-utils (literal extraction helpers).
///
/// Module dependencies:
///   sema-context       ← fir, parser
///   sema-expr-utils    ← parser
///   sema-lower-types   ← fir, parser, sema-context, sema-expr-utils
///   sema-lower-expr    ← fir, parser, sema-context, sema-expr-utils
///   sema-stmt-graph    ← fir, sema-lower-expr
///   sema-lower-instances ← fir, parser, sema-context, sema-eval-expr
///   sema-eval-expr     ← fir, sema-context
///   sema-compiler      ← sema-context, compiler-interface
///   sema-driver        ← all of the above
export module rupa.sema;

// ... existing re-exports ...
```

**Step 2: Commit**

```bash
git add src/sema/rupa.sema.cppm
git commit -m "docs(sema): add pipeline overview to umbrella module"
```

### Task 9.2: Document undocumented sema modules

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-driver.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-compiler.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-context.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-lower-types.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-expr-utils.cppm` (already documented in Task 5.3)

**Step 1: Add module-level documentation to each file**

Follow the FIR documentation style: module purpose, key data structures, dependencies, usage examples. Each module doc should be 15-30 lines of `///` comments before the `module;` declaration.

Template:
```cpp
/// [Module Name] — [One-line purpose]
///
/// [2-3 paragraph description of what this module does, its role in the
///  pipeline, and key design decisions.]
///
/// Key types:
///   - [TypeName]: [one-line description]
///   - [TypeName]: [one-line description]
///
/// Dependencies:
///   - rupa.fir (FIR construction and querying)
///   - rupa.parser (AST node types)
///   - [other modules]
///
/// Usage:
///   [brief code example or description of how this module is called]
```

Specific content for each:

**sema-driver.cppm:** Compilation orchestrator, multi-file support, import resolution, FileStatus state machine, CompilationDriver class.

**sema-compiler.cppm:** Compiler interface adapter, maps SemaDiagnosticKind to human-readable messages, provides file extension filtering.

**sema-context.cppm:** Shared compilation state, SemaContext (type name registry, frozen names, source text), SemaDiagnostics (error/warning collection), CompileOutput (compilation result bundle), RoleCache (inherited role lookup), kMaxRecursionDepth.

**sema-lower-instances.cppm:** Phase 4 of pipeline, AST model blocks → FIR nodes + properties, role resolution against TypeTable, nested instantiation, identity tracking, reference creation.

**sema-lower-types.cppm:** Phase 1 of pipeline, AST type/role declarations → FIR TypeTable, two-pass approach (collect names, then resolve), inheritance resolution, constraint extraction.

**Step 2: Build to verify no syntax errors in comments**

```bash
cd external/rupa && cmake --build --preset debug
```

**Step 3: Commit**

```bash
git add src/sema/
git commit -m "docs(sema): add module-level documentation to all sema modules"
```

### Task 9.3: FIR documentation fixes

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-container.cppm` (add function-level docs)
- Modify: `external/rupa/src/fir/rupa.fir-source-map.cppm` (add function-level docs)

**Step 1: Add doc comments to undocumented public methods**

In fir-container.cppm: document `intern()`, `get_string()`, `seed_builtins()`.
In fir-source-map.cppm: document `set()`, `get()`, `clear()`, `density()`, `addFile()`, `getFile()`.

**Step 2: Commit**

```bash
git add src/fir/
git commit -m "docs(fir): add function-level documentation to container and source-map"
```

---

## Batch 10: Test Cleanup

### Task 10.1: Extract SemaTestBase

**Files:**
- Create: `external/rupa/test/sema/sema-test-base.h`
- Modify: `external/rupa/test/sema/sema-eval-expr-test.cpp`
- Modify: `external/rupa/test/sema/sema-instance-test.cpp`
- Modify: `external/rupa/test/sema/sema-driver-test.cpp`
- Modify: `external/rupa/test/sema/sema-model-access-test.cpp`
- Modify: `external/rupa/test/sema/sema-compiler-test.cpp`

**Step 1: Create shared test base header**

```cpp
#pragma once

#include <gtest/gtest.h>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>

import rupa.fir;
import rupa.fir.builder;
import rupa.sema;

namespace fs = std::filesystem;

/// Base class for sema tests that compile from source strings.
class SemaTestBase : public ::testing::Test {
protected:
    fir::Fir fir_;
    rupa::sema::SemaDiagnostics diags_;

    /// Compile a source string through the full sema pipeline.
    rupa::sema::CompileOutput compile_str(std::string_view source);

    /// Get the nth value handle from the symbol table.
    fir::ValueHandle value_of(uint32_t n);

    /// Extract an integer from the nth let binding.
    std::optional<int64_t> int_value_of(uint32_t n);

    /// Extract a float from the nth let binding.
    std::optional<double> float_value_of(uint32_t n);

    /// Extract a boolean from the nth let binding.
    std::optional<bool> bool_value_of(uint32_t n);

    /// Extract a string from the nth let binding (returns copy to avoid lifetime issues).
    std::optional<std::string> string_value_of(uint32_t n);
};

/// Base class for sema tests that compile from files (needs temp directory).
class SemaFileTestBase : public SemaTestBase {
protected:
    fs::path tmp_dir_;

    void SetUp() override;
    void TearDown() override;

    /// Write a file to the temp directory. Returns the full path.
    fs::path write_file(std::string_view name, std::string_view content);

    /// Compile a file from the temp directory.
    rupa::sema::CompileOutput compile_file(std::string_view filename, std::string_view content);
};
```

**Step 2: Implement in sema-test-base.h (inline or in a .cpp)**

Note: `string_value_of` returns `std::string` (not `string_view`) to avoid the dangling reference issue from the original `sema-eval-expr-test.cpp:47-51`.

**Step 3: Migrate test files to use the base class**

Replace each file's local fixture with inheritance from `SemaTestBase` or `SemaFileTestBase`. Remove duplicated helpers.

**Step 4: Build and run all sema tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R sema -v
```

**Step 5: Commit**

```bash
git add test/sema/
git commit -m "refactor(tests): extract SemaTestBase with shared helpers, fix dangling string_view"
```

### Task 10.2: Split sema-lower-expr-test.cpp

**Files:**
- Modify: `external/rupa/test/sema/sema-lower-expr-test.cpp` (keep basics + deps)
- Create: `external/rupa/test/sema/sema-lower-expr-lambda-test.cpp`
- Create: `external/rupa/test/sema/sema-lower-expr-path-test.cpp`
- Modify: `external/rupa/test/sema/CMakeLists.txt`

**Step 1: Identify test groups**

From the 91 tests, split by topic:
- **Basics** (keep in original file): IntegerLiteral through UnaryNot, BinaryAdd through BinaryComparison (~20 tests)
- **Dependencies** (keep in original file): SimpleReference through DeepChaining (~15 tests)
- **Lambda/Function** (new file): FunctionDefSingleParam through LambdaPromotedMultiParam, BlockBody* (~25 tests)
- **Path** (new file): RoleAccessPath through ChainedRolePath, ParentPath, all path-related (~20 tests)

**Step 2: Create new test files**

Each file includes `sema-test-base.h` and defines its own fixture inheriting from `SemaTestBase`.

**Step 3: Update CMakeLists.txt**

Add new test targets:
```cmake
add_rupa_test(rupa.sema.lower_expr_lambda_test sema-lower-expr-lambda-test.cpp)
add_rupa_test(rupa.sema.lower_expr_path_test sema-lower-expr-path-test.cpp)
```

**Step 4: Build and run all tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R lower_expr -v
```

**Step 5: Commit**

```bash
git add test/sema/
git commit -m "refactor(tests): split sema-lower-expr-test into focused files"
```

### Task 10.3: Add negative tests to fir-builder-test

**Files:**
- Modify: `external/rupa/test/fir/fir-builder-test.cpp`

**Step 1: Add negative test cases**

```cpp
TEST_F(FirBuilderTest, DuplicateRoleNameAllowed) {
    auto signal = builder.add_type("Signal", fir::M3Kind::Composite);
    auto r1 = builder.add_role(signal, "value", fir.builtins.integer, fir::Multiplicity::One);
    auto r2 = builder.add_role(signal, "value", fir.builtins.float_, fir::Multiplicity::One);
    builder.finalize_roles(signal);
    // Both roles exist — builder doesn't enforce uniqueness (sema's job)
    EXPECT_NE(kore::Cast(r1), kore::Cast(r2));
}

TEST_F(FirBuilderTest, SetParentToSelf) {
    auto signal = builder.add_type("Signal", fir::M3Kind::Composite);
    builder.finalize_roles(signal);
    auto nh = builder.begin_object(signal);
    // Setting parent to self doesn't crash (validation is sema's concern)
    builder.set_parent(nh, nh);
    EXPECT_EQ(kore::Cast(fir.model.node(nh).parent), kore::Cast(nh));
}

TEST_F(FirBuilderTest, ObjectWithNoProperties) {
    auto signal = builder.add_type("Signal", fir::M3Kind::Composite);
    builder.finalize_roles(signal);
    auto nh = builder.begin_object(signal);
    builder.finalize_properties(nh);
    auto& n = fir.model.node(nh);
    EXPECT_EQ(n.prop_count, 0);
}
```

**Step 2: Run tests**

```bash
cd external/rupa && cmake --build --preset debug && ctest --preset debug -R fir.builder -v
```

**Step 3: Commit**

```bash
git add test/fir/fir-builder-test.cpp
git commit -m "test(fir): add negative and edge case tests to builder"
```

---

## Batch Summary and Dependencies

```
Batch 1 (TinyVector)          ← independent, kore submodule
Batch 2 (Handle consistency)  ← independent, FIR modules
Batch 3 (FIR style)           ← independent, FIR modules
Batch 4 (FIR encapsulation)   ← after Batch 2 (uses kore::Cast)
Batch 5 (StringLiteralExpr)   ← after Batch 1 (uses TinyVector iterators in parser)
Batch 6 (Split lower_assign)  ← after Batch 5 (uses content_range)
Batch 7 (Merge stmt graph)    ← independent of 1-6
Batch 8 (Error/depth)         ← after Batch 7 (merged module)
Batch 9 (Documentation)       ← after all code changes (Batches 1-8)
Batch 10 (Tests)              ← after all code changes (Batches 1-8)
```

Batches 1, 2, 3, 7 can run in parallel.
Batches 4, 5 can run in parallel after their dependencies.
Batch 6 after 5.
Batch 8 after 7.
Batches 9, 10 after all code changes.

---

## Verification

After all batches complete:

```bash
# Full build
cd external/rupa && cmake --build --preset debug

# All tests
ctest --preset debug -v

# Verify no .data()[ remaining (except kore internals)
grep -r '\.data()\[' src/ test/ --include='*.cppm' --include='*.cpp' | grep -v 'kore/' | wc -l
# Expected: 0

# Verify no static_cast<uint32_t>(handle) remaining
grep -r 'static_cast<uint32_t>' src/fir/ src/sema/ --include='*.cppm' | grep -v '// narrowing' | head -20
# Review: should only be plain integer narrowing, not handle extraction

# Verify no strip_string_literal remaining
grep -r 'strip_string_literal' src/ --include='*.cppm' | wc -l
# Expected: 0
```
