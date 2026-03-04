# FIR Clean-Room Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the existing FIR with a clean-room implementation featuring typed handles, LLVM-style RTTI, separate section arenas, ValueStore, full expression hierarchy, symbol table, and format v6 serialization.

**Architecture:** Section-composed `Fir` with TypeTable (direct `vector<FirType/FirRole>`), ModelGraph (direct `vector<FirNode>` + `vector<FirProp>` + ValueStore), ExpressionStore (VecArena + pointer table), and SymbolTable (VecArena + pointer table). All cross-references use strongly-typed handles (`TypeHandle`, `RoleHandle`, `NodeHandle`, `ValueHandle`, `ExprHandle`, `SymbolHandle`).

**Tech Stack:** C++23 modules, kore library (LiteralStore, VecArena, KORE_DEFINE_HANDLE), GTest, CMake with Ninja

**Design doc:** `docs/plans/2026-03-04-fir-redesign-design.md`

**Working directory:** `external/rupa/` (FIR lives in the Rupa submodule)

**Build commands:**
```bash
# From senda root:
cmake --preset debug && cmake --build --preset debug

# Run specific FIR test (after build):
./build-debug/external/rupa/test/fir/<test-target>
```

---

## Batch 1: RTTI Utilities + Handle Declarations (independent, no dependencies)

### Task 1.1: Create `rupa.fir-rtti.cppm` — LLVM-style RTTI utilities

**Files:**
- Create: `external/rupa/src/fir/rupa.fir-rtti.cppm`
- Create: `external/rupa/test/fir/fir-rtti-test.cpp`
- Modify: `external/rupa/src/fir/CMakeLists.txt` — add to `rupa.fir` target
- Modify: `external/rupa/test/fir/CMakeLists.txt` — add test executable

**Step 1: Write the test**

```cpp
// fir-rtti-test.cpp
import rupa.fir.rtti;
#include <gtest/gtest.h>

namespace {

struct Base {
    enum class Kind : uint8_t { A, B };
    Kind kind;
    explicit Base(Kind k) : kind(k) {}
};

struct DerivedA : Base {
    int value;
    DerivedA(int v) : Base(Kind::A), value(v) {}
    static bool classof(const Base* b) { return b->kind == Kind::A; }
};

struct DerivedB : Base {
    float value;
    DerivedB(float v) : Base(Kind::B), value(v) {}
    static bool classof(const Base* b) { return b->kind == Kind::B; }
};

TEST(FirRtti, IsaIdentifiesCorrectType) {
    DerivedA a{42};
    Base* base = &a;
    EXPECT_TRUE(fir::rtti::isa<DerivedA>(base));
    EXPECT_FALSE(fir::rtti::isa<DerivedB>(base));
}

TEST(FirRtti, IsaNullReturnsFalse) {
    EXPECT_FALSE(fir::rtti::isa<DerivedA>(static_cast<Base*>(nullptr)));
}

TEST(FirRtti, CastReturnsCorrectPointer) {
    DerivedA a{42};
    Base* base = &a;
    DerivedA* result = fir::rtti::cast<DerivedA>(base);
    EXPECT_EQ(result->value, 42);
}

TEST(FirRtti, DynCastReturnsNullOnMismatch) {
    DerivedA a{42};
    Base* base = &a;
    EXPECT_EQ(fir::rtti::dyn_cast<DerivedB>(base), nullptr);
}

TEST(FirRtti, DynCastReturnsPointerOnMatch) {
    DerivedB b{3.14f};
    Base* base = &b;
    auto* result = fir::rtti::dyn_cast<DerivedB>(base);
    ASSERT_NE(result, nullptr);
    EXPECT_FLOAT_EQ(result->value, 3.14f);
}

TEST(FirRtti, DynCastNullReturnsNull) {
    EXPECT_EQ(fir::rtti::dyn_cast<DerivedA>(static_cast<Base*>(nullptr)), nullptr);
}

TEST(FirRtti, ConstOverloads) {
    const DerivedA a{99};
    const Base* base = &a;
    EXPECT_TRUE(fir::rtti::isa<DerivedA>(base));
    const DerivedA* result = fir::rtti::dyn_cast<DerivedA>(base);
    ASSERT_NE(result, nullptr);
    EXPECT_EQ(result->value, 99);
}

} // namespace
```

**Step 2: Run test to verify it fails**

Run: `cmake --build --preset debug --target rupa.fir.rtti_test && ./build-debug/external/rupa/test/fir/rupa.fir.rtti_test`
Expected: FAIL — module `rupa.fir.rtti` does not exist

**Step 3: Write the module**

```cpp
// rupa.fir-rtti.cppm
export module rupa.fir.rtti;

import <cassert>;

export namespace fir::rtti {

template <typename T, typename Base>
bool isa(const Base* b) {
    return b != nullptr && T::classof(b);
}

template <typename T, typename Base>
T* cast(Base* b) {
    assert(isa<T>(b));
    return static_cast<T*>(b);
}

template <typename T, typename Base>
const T* cast(const Base* b) {
    assert(isa<T>(b));
    return static_cast<const T*>(b);
}

template <typename T, typename Base>
T* dyn_cast(Base* b) {
    return isa<T>(b) ? static_cast<T*>(b) : nullptr;
}

template <typename T, typename Base>
const T* dyn_cast(const Base* b) {
    return isa<T>(b) ? static_cast<const T*>(b) : nullptr;
}

} // namespace fir::rtti
```

**Step 4: Update CMakeLists.txt**

Add `rupa.fir-rtti.cppm` to the `rupa.fir` target's `FILE_SET CXX_MODULES` in `external/rupa/src/fir/CMakeLists.txt`.

Add test in `external/rupa/test/fir/CMakeLists.txt`:
```cmake
add_executable(rupa.fir.rtti_test fir-rtti-test.cpp)
target_link_libraries(rupa.fir.rtti_test PRIVATE rupa.fir GTest::gtest_main)
add_test(NAME rupa.fir.rtti_test COMMAND rupa.fir.rtti_test)
rupa_target_settings(rupa.fir.rtti_test)
```

**Step 5: Run test to verify it passes**

Run: `cmake --build --preset debug --target rupa.fir.rtti_test && ./build-debug/external/rupa/test/fir/rupa.fir.rtti_test`
Expected: All 7 tests PASS

**Step 6: Commit**

```bash
cd external/rupa && git add src/fir/rupa.fir-rtti.cppm test/fir/fir-rtti-test.cpp src/fir/CMakeLists.txt test/fir/CMakeLists.txt
git commit -m "feat(fir): add LLVM-style RTTI utilities (isa/cast/dyn_cast)"
```

---

### Task 1.2: Create `rupa.fir-handles.cppm` — Typed handle declarations + foreign bit helpers

**Files:**
- Create: `external/rupa/src/fir/rupa.fir-handles.cppm`
- Create: `external/rupa/test/fir/fir-handles-test.cpp`
- Modify: `external/rupa/src/fir/CMakeLists.txt`
- Modify: `external/rupa/test/fir/CMakeLists.txt`

**Step 1: Write the test**

```cpp
// fir-handles-test.cpp
#include <kore/macros.hpp>
import rupa.fir.handles;
#include <gtest/gtest.h>

TEST(FirHandles, TypeHandleIsDistinctType) {
    static_assert(!std::is_same_v<fir::TypeHandle, fir::RoleHandle>);
    static_assert(!std::is_same_v<fir::TypeHandle, fir::NodeHandle>);
}

TEST(FirHandles, InvalidHandleSentinel) {
    EXPECT_TRUE(kore::IsInvalid(fir::kInvalidType));
    EXPECT_TRUE(kore::IsInvalid(fir::kInvalidRole));
    EXPECT_TRUE(kore::IsInvalid(fir::kInvalidNode));
    EXPECT_TRUE(kore::IsInvalid(fir::kInvalidExpr));
    EXPECT_TRUE(kore::IsInvalid(fir::kInvalidSymbol));
}

TEST(FirHandles, ForeignBitEncoding) {
    auto local = fir::TypeHandle{42};
    EXPECT_TRUE(fir::is_local(local));
    EXPECT_FALSE(fir::is_foreign(local));
    EXPECT_EQ(fir::local_index(local), 42u);

    auto foreign = fir::make_foreign<fir::TypeHandle>(7);
    EXPECT_TRUE(fir::is_foreign(foreign));
    EXPECT_FALSE(fir::is_local(foreign));
    EXPECT_EQ(fir::foreign_index(foreign), 7u);
}

TEST(FirHandles, NoneDetection) {
    EXPECT_TRUE(fir::is_none(fir::kInvalidType));
    EXPECT_FALSE(fir::is_none(fir::TypeHandle{0}));
    EXPECT_FALSE(fir::is_none(fir::make_foreign<fir::TypeHandle>(0)));
}

TEST(FirHandles, ValueHandleKindEncoding) {
    auto int_val = fir::make_value(fir::ValueKind::Integer, 42);
    EXPECT_EQ(fir::value_kind(int_val), fir::ValueKind::Integer);
    EXPECT_EQ(fir::value_index(int_val), 42u);

    auto bool_true = fir::make_value(fir::ValueKind::Boolean, 1);
    EXPECT_EQ(fir::value_kind(bool_true), fir::ValueKind::Boolean);
    EXPECT_EQ(fir::value_index(bool_true), 1u);
}

TEST(FirHandles, ValueHandleWellKnownConstants) {
    EXPECT_EQ(fir::value_kind(fir::kNull), fir::ValueKind::Null);
    EXPECT_EQ(fir::value_kind(fir::kTrue), fir::ValueKind::Boolean);
    EXPECT_EQ(fir::value_index(fir::kTrue), 1u);
    EXPECT_EQ(fir::value_kind(fir::kFalse), fir::ValueKind::Boolean);
    EXPECT_EQ(fir::value_index(fir::kFalse), 0u);
}

TEST(FirHandles, M3KindValues) {
    EXPECT_EQ(static_cast<uint8_t>(fir::M3Kind::Composite), 0);
    EXPECT_EQ(static_cast<uint8_t>(fir::M3Kind::Primitive), 1);
    EXPECT_EQ(static_cast<uint8_t>(fir::M3Kind::List), 2);
    EXPECT_EQ(static_cast<uint8_t>(fir::M3Kind::Map), 3);
    EXPECT_EQ(static_cast<uint8_t>(fir::M3Kind::Union), 4);
    EXPECT_EQ(static_cast<uint8_t>(fir::M3Kind::Enum), 5);
}

TEST(FirHandles, MultiplicityValues) {
    EXPECT_EQ(static_cast<uint8_t>(fir::Multiplicity::One), 0);
    EXPECT_EQ(static_cast<uint8_t>(fir::Multiplicity::Optional), 1);
    EXPECT_EQ(static_cast<uint8_t>(fir::Multiplicity::Many), 2);
    EXPECT_EQ(static_cast<uint8_t>(fir::Multiplicity::OneOrMore), 3);
}

TEST(FirHandles, ProvenanceValues) {
    EXPECT_EQ(static_cast<uint8_t>(fir::Provenance::Local), 0);
    EXPECT_EQ(static_cast<uint8_t>(fir::Provenance::Imported), 1);
    EXPECT_EQ(static_cast<uint8_t>(fir::Provenance::Materialized), 2);
}
```

**Step 2: Run test — expected FAIL**

**Step 3: Write the module**

```cpp
// rupa.fir-handles.cppm
export module rupa.fir.handles;

#include <kore/macros.hpp>
import kore;

export namespace fir {

// ── Typed handles ──
KORE_DEFINE_HANDLE(Type, 32);
KORE_DEFINE_HANDLE(Role, 32);
KORE_DEFINE_HANDLE(Node, 32);
KORE_DEFINE_HANDLE(Value, 32);
KORE_DEFINE_HANDLE(Expr, 32);
KORE_DEFINE_HANDLE(Symbol, 32);

using DomainId = uint16_t;
using ModuleId = uint16_t;
using StringId = kore::LiteralHandle<64>;

inline constexpr DomainId kInvalidDomain = UINT16_MAX;
inline constexpr ModuleId kInvalidModule = UINT16_MAX;

// ── Sentinel handles ──
inline constexpr auto kInvalidType   = kore::kInvalidHandle<TypeHandle>;
inline constexpr auto kInvalidRole   = kore::kInvalidHandle<RoleHandle>;
inline constexpr auto kInvalidNode   = kore::kInvalidHandle<NodeHandle>;
inline constexpr auto kInvalidValue  = kore::kInvalidHandle<ValueHandle>;
inline constexpr auto kInvalidExpr   = kore::kInvalidHandle<ExprHandle>;
inline constexpr auto kInvalidSymbol = kore::kInvalidHandle<SymbolHandle>;

// ── Foreign bit (bit 31) helpers for TypeHandle, RoleHandle, NodeHandle ──
inline constexpr uint32_t kForeignBit = 0x8000'0000u;

template <typename H>
constexpr bool is_none(H h) { return kore::IsInvalid(h); }

template <typename H>
constexpr bool is_foreign(H h) {
    return !is_none(h) && (kore::Cast(h) & kForeignBit) != 0;
}

template <typename H>
constexpr bool is_local(H h) {
    return !is_none(h) && (kore::Cast(h) & kForeignBit) == 0;
}

template <typename H>
constexpr uint32_t local_index(H h) { return kore::Cast(h); }

template <typename H>
constexpr uint32_t foreign_index(H h) { return kore::Cast(h) & ~kForeignBit; }

template <typename H>
constexpr H make_foreign(uint32_t index) { return kore::Cast<H>(index | kForeignBit); }

// ── ValueHandle encoding: [31:28] kind, [27:0] index ──
enum class ValueKind : uint8_t {
    Integer   = 0,
    Float     = 1,
    String    = 2,
    Boolean   = 3,
    Null      = 4,
    Reference = 5,
    EnumValue = 6,
};

constexpr ValueHandle make_value(ValueKind kind, uint32_t index) {
    return kore::Cast<ValueHandle>((static_cast<uint32_t>(kind) << 28) | (index & 0x0FFF'FFFFu));
}

constexpr ValueKind value_kind(ValueHandle h) {
    return static_cast<ValueKind>(kore::Cast(h) >> 28);
}

constexpr uint32_t value_index(ValueHandle h) {
    return kore::Cast(h) & 0x0FFF'FFFFu;
}

// Well-known constants
inline constexpr auto kNull  = make_value(ValueKind::Null, 0);
inline constexpr auto kTrue  = make_value(ValueKind::Boolean, 1);
inline constexpr auto kFalse = make_value(ValueKind::Boolean, 0);

// ── Enums ──
enum class M3Kind : uint8_t {
    Composite = 0,
    Primitive = 1,
    List      = 2,
    Map       = 3,
    Union     = 4,
    Enum      = 5,
};

enum class Multiplicity : uint8_t {
    One       = 0,
    Optional  = 1,
    Many      = 2,
    OneOrMore = 3,
};

enum class Provenance : uint8_t {
    Local        = 0,
    Imported     = 1,
    Materialized = 2,
};

// ── ForeignRef ──
struct ForeignRef {
    ModuleId module;
    uint32_t local_id;
};

// ── Domain/Module entries ──
struct DomainEntry {
    StringId name;
};

struct ModuleEntry {
    StringId name;
};

} // namespace fir
```

**Step 4: Update CMakeLists.txt** — add `rupa.fir-handles.cppm` to `rupa.fir` target, add test

**Step 5: Run test — expected PASS** (all 9 tests)

**Step 6: Commit**

```bash
git add src/fir/rupa.fir-handles.cppm test/fir/fir-handles-test.cpp src/fir/CMakeLists.txt test/fir/CMakeLists.txt
git commit -m "feat(fir): add typed handle declarations, foreign bit encoding, ValueKind"
```

---

## Batch 2: ValueStore (depends on Batch 1)

### Task 2.1: Create `rupa.fir-value.cppm` — ValueStore

**Files:**
- Create: `external/rupa/src/fir/rupa.fir-value.cppm`
- Create: `external/rupa/test/fir/fir-value-test.cpp`
- Modify: `external/rupa/src/fir/CMakeLists.txt`
- Modify: `external/rupa/test/fir/CMakeLists.txt`

**Step 1: Write the test**

```cpp
// fir-value-test.cpp
#include <kore/macros.hpp>
import rupa.fir.handles;
import rupa.fir.value;
import kore;
#include <gtest/gtest.h>

class ValueStoreTest : public ::testing::Test {
protected:
    kore::LiteralStore<64> strings;
    fir::ValueStore store;
};

TEST_F(ValueStoreTest, AddInteger) {
    auto h = store.add_integer(42);
    EXPECT_EQ(fir::value_kind(h), fir::ValueKind::Integer);
    EXPECT_EQ(store.get_integer(h), 42);
}

TEST_F(ValueStoreTest, AddNegativeInteger) {
    auto h = store.add_integer(-1);
    EXPECT_EQ(store.get_integer(h), -1);
}

TEST_F(ValueStoreTest, AddFloat) {
    auto h = store.add_float(3.14);
    EXPECT_EQ(fir::value_kind(h), fir::ValueKind::Float);
    EXPECT_DOUBLE_EQ(store.get_float(h), 3.14);
}

TEST_F(ValueStoreTest, AddString) {
    auto sid = strings.AddTransient("hello");
    auto h = store.add_string(sid);
    EXPECT_EQ(fir::value_kind(h), fir::ValueKind::String);
    EXPECT_EQ(store.get_string(h), sid);
}

TEST_F(ValueStoreTest, BooleanNoStorage) {
    auto t = store.add_boolean(true);
    auto f = store.add_boolean(false);
    EXPECT_EQ(t, fir::kTrue);
    EXPECT_EQ(f, fir::kFalse);
    EXPECT_TRUE(store.get_boolean(fir::kTrue));
    EXPECT_FALSE(store.get_boolean(fir::kFalse));
}

TEST_F(ValueStoreTest, NullNoStorage) {
    auto h = store.add_null();
    EXPECT_EQ(h, fir::kNull);
    EXPECT_EQ(fir::value_kind(h), fir::ValueKind::Null);
}

TEST_F(ValueStoreTest, AddReference) {
    auto seg1 = strings.AddTransient("AR-PACKAGES");
    auto seg2 = strings.AddTransient("MyPackage");
    fir::PathSegment segments[] = {{seg1}, {seg2}};
    auto h = store.add_reference(segments);
    EXPECT_EQ(fir::value_kind(h), fir::ValueKind::Reference);
    auto& ref = store.get_reference(h);
    EXPECT_EQ(ref.segment_count, 2);
    EXPECT_TRUE(fir::is_none(ref.target));
}

TEST_F(ValueStoreTest, AddEnum) {
    auto type_h = fir::TypeHandle{0};
    auto member = strings.AddTransient("RED");
    auto h = store.add_enum(type_h, member);
    EXPECT_EQ(fir::value_kind(h), fir::ValueKind::EnumValue);
    auto& e = store.get_enum(h);
    EXPECT_EQ(e.enum_type, type_h);
    EXPECT_EQ(e.member_name, member);
}

TEST_F(ValueStoreTest, ResolveReference) {
    auto seg = strings.AddTransient("target");
    fir::PathSegment segments[] = {{seg}};
    auto h = store.add_reference(segments);
    auto target = fir::NodeHandle{99};
    store.resolve_reference(h, target);
    EXPECT_EQ(store.get_reference(h).target, target);
}

TEST_F(ValueStoreTest, MultipleIntegersGetDistinctHandles) {
    auto h1 = store.add_integer(1);
    auto h2 = store.add_integer(2);
    EXPECT_NE(h1, h2);
    EXPECT_EQ(store.get_integer(h1), 1);
    EXPECT_EQ(store.get_integer(h2), 2);
}
```

**Step 2: Run test — expected FAIL**

**Step 3: Write the module** following the design doc Section 3 ValueStore. Key structs: `PathSegment`, `RefValue`, `EnumEntry`, `ValueStore` with per-kind vectors and the API methods.

```cpp
// rupa.fir-value.cppm
export module rupa.fir.value;

#include <kore/macros.hpp>
import rupa.fir.handles;
import kore;
import <vector>;
import <span>;
import <cassert>;

export namespace fir {

struct PathSegment {
    StringId value;   // interned segment text
};

struct RefValue {
    uint32_t   segment_start;
    uint16_t   segment_count;
    uint16_t   reserved_ = 0;
    NodeHandle target;        // kInvalidNode = unresolved
};

struct EnumEntry {
    TypeHandle enum_type;
    StringId   member_name;
};

struct ValueStore {
    std::vector<int64_t>     integers;
    std::vector<double>      floats;
    std::vector<StringId>    strings;
    std::vector<RefValue>    references;
    std::vector<EnumEntry>   enum_values;
    std::vector<PathSegment> path_segments;

    ValueHandle add_integer(int64_t v) {
        auto idx = static_cast<uint32_t>(integers.size());
        integers.push_back(v);
        return make_value(ValueKind::Integer, idx);
    }

    ValueHandle add_float(double v) {
        auto idx = static_cast<uint32_t>(floats.size());
        floats.push_back(v);
        return make_value(ValueKind::Float, idx);
    }

    ValueHandle add_string(StringId s) {
        auto idx = static_cast<uint32_t>(strings.size());
        strings.push_back(s);
        return make_value(ValueKind::String, idx);
    }

    ValueHandle add_boolean(bool v) {
        return v ? kTrue : kFalse;
    }

    ValueHandle add_null() { return kNull; }

    ValueHandle add_reference(std::span<const PathSegment> segments) {
        auto seg_start = static_cast<uint32_t>(path_segments.size());
        for (auto& s : segments) path_segments.push_back(s);
        auto idx = static_cast<uint32_t>(references.size());
        references.push_back({seg_start, static_cast<uint16_t>(segments.size()), 0, kInvalidNode});
        return make_value(ValueKind::Reference, idx);
    }

    ValueHandle add_enum(TypeHandle type, StringId member) {
        auto idx = static_cast<uint32_t>(enum_values.size());
        enum_values.push_back({type, member});
        return make_value(ValueKind::EnumValue, idx);
    }

    void resolve_reference(ValueHandle h, NodeHandle target) {
        assert(value_kind(h) == ValueKind::Reference);
        references[value_index(h)].target = target;
    }

    int64_t     get_integer(ValueHandle h) const { return integers[value_index(h)]; }
    double      get_float(ValueHandle h)   const { return floats[value_index(h)]; }
    StringId    get_string(ValueHandle h)  const { return strings[value_index(h)]; }
    bool        get_boolean(ValueHandle h) const { return value_index(h) != 0; }
    const RefValue&  get_reference(ValueHandle h) const { return references[value_index(h)]; }
    RefValue&        get_reference(ValueHandle h)       { return references[value_index(h)]; }
    const EnumEntry& get_enum(ValueHandle h) const { return enum_values[value_index(h)]; }

    std::span<const PathSegment> ref_segments(const RefValue& ref) const {
        return {path_segments.data() + ref.segment_start, ref.segment_count};
    }
};

} // namespace fir
```

**Step 4: Update CMakeLists.txt** — add module and test

**Step 5: Run test — expected PASS** (10 tests)

**Step 6: Commit**

```bash
git add src/fir/rupa.fir-value.cppm test/fir/fir-value-test.cpp src/fir/CMakeLists.txt test/fir/CMakeLists.txt
git commit -m "feat(fir): add ValueStore with per-kind SOA storage and typed ValueHandle"
```

---

## Batch 3: TypeTable (depends on Batch 1)

### Task 3.1: Create `rupa.fir-types.cppm` (new) — FirType, FirRole, TypeTable

**Files:**
- Replace: `external/rupa/src/fir/rupa.fir-types.cppm` (completely rewrite)
- Replace: `external/rupa/test/fir/fir-types-test.cpp` (completely rewrite)

**Step 1: Write the test** — Cover FirType creation (all M3Kinds), FirRole creation (all multiplicities, containment, identity flags), bitfield packing/unpacking, role_ids secondary table, enum_values, variant_ids, constraint tables, domain/module tables, root types.

Test structure mirrors old `fir-types-test.cpp` but uses new `TypeTable` directly:

```cpp
// fir-types-test.cpp (new)
#include <kore/macros.hpp>
import rupa.fir.handles;
import rupa.fir.types;
import kore;
#include <gtest/gtest.h>

class TypeTableTest : public ::testing::Test {
protected:
    kore::LiteralStore<64> strings;
    fir::TypeTable table;
};

TEST_F(TypeTableTest, AddCompositeType) {
    auto name = strings.AddTransient("Signal");
    auto h = table.add_type(name, fir::M3Kind::Composite);
    EXPECT_TRUE(fir::is_local(h));
    auto& t = table.type(h);
    EXPECT_EQ(t.m3_kind(), fir::M3Kind::Composite);
    EXPECT_EQ(t.name, name);
    EXPECT_FALSE(t.is_abstract());
    EXPECT_TRUE(fir::is_none(t.supertype));
}

TEST_F(TypeTableTest, AddEnumType) {
    auto name = strings.AddTransient("Color");
    auto h = table.add_type(name, fir::M3Kind::Enum);
    auto red = strings.AddTransient("RED");
    auto green = strings.AddTransient("GREEN");
    table.add_enum_value(h, red);
    table.add_enum_value(h, green);
    auto& t = table.type(h);
    auto values = table.enum_values_of(t);
    EXPECT_EQ(values.size(), 2);
    EXPECT_EQ(values[0], red);
    EXPECT_EQ(values[1], green);
}

TEST_F(TypeTableTest, AddRole) {
    auto type_name = strings.AddTransient("Package");
    auto th = table.add_type(type_name, fir::M3Kind::Composite);
    auto elem_name = strings.AddTransient("Element");
    auto elem_th = table.add_type(elem_name, fir::M3Kind::Composite);
    auto role_name = strings.AddTransient("elements");
    auto rh = table.add_role(th, role_name, elem_th, fir::Multiplicity::Many, true);
    auto& r = table.role(rh);
    EXPECT_EQ(r.name, role_name);
    EXPECT_EQ(r.target, elem_th);
    EXPECT_EQ(r.multiplicity(), fir::Multiplicity::Many);
    EXPECT_TRUE(r.is_containment());
    EXPECT_FALSE(r.is_identity());
}

TEST_F(TypeTableTest, SetIdentityRole) {
    auto tn = strings.AddTransient("Named");
    auto th = table.add_type(tn, fir::M3Kind::Composite);
    auto sn = strings.AddTransient("::string");
    auto st = table.add_type(sn, fir::M3Kind::Primitive);
    auto rn = strings.AddTransient("shortName");
    auto rh = table.add_role(th, rn, st, fir::Multiplicity::One, false);
    table.set_identity(rh, true);
    EXPECT_TRUE(table.role(rh).is_identity());
}

TEST_F(TypeTableTest, SetSupertype) {
    auto base_n = strings.AddTransient("Base");
    auto base_h = table.add_type(base_n, fir::M3Kind::Composite);
    auto der_n = strings.AddTransient("Derived");
    auto der_h = table.add_type(der_n, fir::M3Kind::Composite);
    table.set_supertype(der_h, base_h);
    EXPECT_EQ(table.type(der_h).supertype, base_h);
}

TEST_F(TypeTableTest, SetAbstract) {
    auto n = strings.AddTransient("Abstract");
    auto h = table.add_type(n, fir::M3Kind::Composite);
    table.set_abstract(h, true);
    EXPECT_TRUE(table.type(h).is_abstract());
}

TEST_F(TypeTableTest, RolesOfType) {
    auto tn = strings.AddTransient("T");
    auto th = table.add_type(tn, fir::M3Kind::Composite);
    auto pn = strings.AddTransient("::string");
    auto pt = table.add_type(pn, fir::M3Kind::Primitive);
    auto r1n = strings.AddTransient("a");
    auto r2n = strings.AddTransient("b");
    table.add_role(th, r1n, pt, fir::Multiplicity::One, false);
    table.add_role(th, r2n, pt, fir::Multiplicity::Optional, false);
    table.finalize_roles(th);
    auto roles = table.roles_of(table.type(th));
    EXPECT_EQ(roles.size(), 2);
}

TEST_F(TypeTableTest, DomainTable) {
    auto dn = strings.AddTransient("AUTOSAR");
    auto did = table.add_domain(dn);
    EXPECT_EQ(table.domain_name(did), dn);
}

TEST_F(TypeTableTest, ForeignTypeRef) {
    auto mid = table.add_module(strings.AddTransient("external"));
    auto fh = table.add_foreign_type(mid, 5);
    EXPECT_TRUE(fir::is_foreign(fh));
    auto& ref = table.foreign_type_ref(fh);
    EXPECT_EQ(ref.module, mid);
    EXPECT_EQ(ref.local_id, 5u);
}
```

**Step 2: Run test — expected FAIL** (old module doesn't export new API)

**Step 3: Write new `rupa.fir-types.cppm`** following design doc Section 2. Implement `FirType` with bitfield accessor methods (`m3_kind()`, `is_abstract()`, `set_abstract()`, etc.), `FirRole` with flag accessors, and `TypeTable` struct with all secondary tables and API methods.

Key implementation detail: `FirType::flags` bitfield accessors:
```cpp
M3Kind m3_kind() const { return static_cast<M3Kind>(flags & 0xF); }
bool is_abstract() const { return (flags >> 4) & 1; }
void set_abstract(bool v) { flags = (flags & ~(1u << 4)) | (static_cast<uint32_t>(v) << 4); }
// etc.
```

`FirRole::flags` bitfield accessors:
```cpp
Multiplicity multiplicity() const { return static_cast<Multiplicity>(flags & 0x3); }
bool is_containment() const { return (flags >> 2) & 1; }
bool is_identity() const { return (flags >> 3) & 1; }
// setters similar
```

`TypeTable` must track roles added per type. Use a `pending_role_start` / `pending_role_count` approach: `add_role()` pushes into the flat `roles` vector and accumulates `role_ids`. `finalize_roles(th)` writes `role_start/role_count` into the FirType.

**Step 4: Run test — expected PASS**

**Step 5: Commit**

```bash
git add src/fir/rupa.fir-types.cppm test/fir/fir-types-test.cpp
git commit -m "feat(fir): rewrite TypeTable with FirType/FirRole bitfield-packed structs"
```

---

## Batch 4: ModelGraph (depends on Batch 1, 2)

### Task 4.1: Create `rupa.fir-model.cppm` — FirNode, FirProp, ModelGraph

**Files:**
- Create: `external/rupa/src/fir/rupa.fir-model.cppm` (replaces `rupa.fir-instances.cppm`)
- Replace: `external/rupa/test/fir/fir-instance-test.cpp` → `fir-model-test.cpp`
- Modify: `external/rupa/src/fir/CMakeLists.txt`
- Modify: `external/rupa/test/fir/CMakeLists.txt`

**Step 1: Write the test** — FirNode creation, FirProp with containment discriminator, property assignment via props secondary table, parent/derived_from, provenance flags.

```cpp
// fir-model-test.cpp
#include <kore/macros.hpp>
import rupa.fir.handles;
import rupa.fir.value;
import rupa.fir.model;
import kore;
#include <gtest/gtest.h>

class ModelGraphTest : public ::testing::Test {
protected:
    kore::LiteralStore<64> strings;
    fir::ModelGraph model;
};

TEST_F(ModelGraphTest, AddNode) {
    auto type = fir::TypeHandle{0};
    auto h = model.add_node(type);
    EXPECT_TRUE(fir::is_local(h));
    auto& n = model.node(h);
    EXPECT_EQ(n.type, type);
    EXPECT_TRUE(fir::is_none(n.parent));
    EXPECT_TRUE(fir::is_none(n.derived_from));
    EXPECT_EQ(n.provenance(), fir::Provenance::Local);
}

TEST_F(ModelGraphTest, SetParent) {
    auto type = fir::TypeHandle{0};
    auto parent = model.add_node(type);
    auto child = model.add_node(type);
    model.set_parent(child, parent);
    EXPECT_EQ(model.node(child).parent, parent);
}

TEST_F(ModelGraphTest, AddValueProperty) {
    auto type = fir::TypeHandle{0};
    auto obj = model.add_node(type);
    auto role = fir::RoleHandle{0};
    auto val = fir::make_value(fir::ValueKind::Integer, 0);
    model.add_value_prop(obj, role, type, val);
    model.finalize_props(obj);
    auto props = model.props_of(model.node(obj));
    EXPECT_EQ(props.size(), 1);
    EXPECT_FALSE(props[0].is_node());
    EXPECT_EQ(props[0].role(), role);
    EXPECT_EQ(props[0].value_type, type);
}

TEST_F(ModelGraphTest, AddContainmentProperty) {
    auto type = fir::TypeHandle{0};
    auto parent = model.add_node(type);
    auto child = model.add_node(type);
    auto role = fir::RoleHandle{0};
    model.add_containment_prop(parent, role, type, child);
    model.finalize_props(parent);
    auto props = model.props_of(model.node(parent));
    EXPECT_EQ(props.size(), 1);
    EXPECT_TRUE(props[0].is_node());
    EXPECT_EQ(props[0].node_handle(), child);
}

TEST_F(ModelGraphTest, FlushProperties) {
    auto type = fir::TypeHandle{0};
    auto obj = model.add_node(type);
    auto r0 = fir::RoleHandle{0};
    auto r1 = fir::RoleHandle{1};
    auto v0 = fir::make_value(fir::ValueKind::Integer, 0);
    auto v1 = fir::make_value(fir::ValueKind::String, 0);
    fir::FirProp batch[] = {
        fir::FirProp::make_value(r0, type, v0),
        fir::FirProp::make_value(r1, type, v1),
    };
    model.flush_props(obj, batch);
    auto props = model.props_of(model.node(obj));
    EXPECT_EQ(props.size(), 2);
}

TEST_F(ModelGraphTest, RootObject) {
    EXPECT_TRUE(fir::is_none(model.root_object));
    auto obj = model.add_node(fir::TypeHandle{0});
    model.root_object = obj;
    EXPECT_EQ(model.root_object, obj);
}
```

**Step 2: Run test — expected FAIL**

**Step 3: Write the module** following design doc Section 3. `FirNode` (24 bytes), `FirProp` (12 bytes with `is_node` bit on role_flags), `ModelGraph` struct.

Key implementation for `FirProp`:
```cpp
struct FirProp {
    uint32_t   role_flags;    // [31] is_node, [30:0] role index
    TypeHandle value_type;
    uint32_t   ref;           // ValueHandle or NodeHandle raw bits

    static constexpr uint32_t kNodeBit = 0x8000'0000u;

    static FirProp make_value(RoleHandle role, TypeHandle type, ValueHandle val) {
        return {kore::Cast(role), type, kore::Cast(val)};
    }
    static FirProp make_node(RoleHandle role, TypeHandle type, NodeHandle node) {
        return {kore::Cast(role) | kNodeBit, type, kore::Cast(node)};
    }

    bool is_node() const { return (role_flags & kNodeBit) != 0; }
    RoleHandle role() const { return kore::Cast<RoleHandle>(role_flags & ~kNodeBit); }
    ValueHandle value_handle() const { assert(!is_node()); return kore::Cast<ValueHandle>(ref); }
    NodeHandle node_handle() const { assert(is_node()); return kore::Cast<NodeHandle>(ref); }
};
```

**Step 4: Run test — expected PASS**

**Step 5: Commit**

```bash
git add src/fir/rupa.fir-model.cppm test/fir/fir-model-test.cpp src/fir/CMakeLists.txt test/fir/CMakeLists.txt
git commit -m "feat(fir): add ModelGraph with FirNode, FirProp containment discriminator"
```

---

## Batch 5: Fir Container + FirBuilder (depends on Batch 2, 3, 4)

### Task 5.1: Rewrite `rupa.fir.cppm` — Section-composed Fir container

**Files:**
- Replace: `external/rupa/src/fir/rupa.fir.cppm`
- Replace: `external/rupa/test/fir/fir-context-test.cpp`

**Step 1: Write the test** — string interning, type creation through `fir.types`, model node creation through `fir.model`, value creation through `fir.model.values`.

**Step 2: Run test — expected FAIL**

**Step 3: Write the module** — `Fir` struct composing `strings`, `types`, `model`, `expressions`, `symbols`, `exports`, `external_refs`, `metadata`, `source_map`. Seed M3 builtins in constructor.

**Step 4: Run test — expected PASS**

**Step 5: Commit**

### Task 5.2: Rewrite `rupa.fir-builder.cppm` — New FirBuilder API

**Files:**
- Replace: `external/rupa/src/fir/rupa.fir-builder.cppm`
- Replace: `external/rupa/test/fir/fir-builder-test.cpp`

**Step 1: Write the test** — Cover all FirBuilder methods from design doc Section 8. Type creation, role creation with identity, value addition (all kinds), object creation, property assignment (value and containment), flush_properties, foreign refs, root markers.

**Step 2: Run test — expected FAIL**

**Step 3: Write the module** — `FirBuilder` wrapping `Fir&`, delegating to TypeTable/ModelGraph/ValueStore. Expression and symbol construction methods can be stubbed initially (assert false) and filled in Batch 6/7.

**Step 4: Run test — expected PASS**

**Step 5: Commit**

```bash
git add src/fir/rupa.fir.cppm src/fir/rupa.fir-builder.cppm test/fir/fir-context-test.cpp test/fir/fir-builder-test.cpp
git commit -m "feat(fir): rewrite Fir container and FirBuilder with section composition"
```

---

## Batch 6: ExpressionStore (depends on Batch 1)

### Task 6.1: Create `rupa.fir-expr.cppm` — Full expression hierarchy

**Files:**
- Create: `external/rupa/src/fir/rupa.fir-expr.cppm`
- Create: `external/rupa/test/fir/fir-expr-test.cpp`
- Modify: `external/rupa/src/fir/CMakeLists.txt`
- Modify: `external/rupa/test/fir/CMakeLists.txt`

**Step 1: Write the test** — Test creation of each structural subtype (leaf, value, unary, binary, ternary, role access, identity nav, type op, call, pipe, match). Test RTTI via `isa`/`dyn_cast`. Test secondary tables (call_args, pipe_steps, match_arms).

```cpp
// fir-expr-test.cpp (key tests)
TEST(ExprStore, AddLiteral) {
    fir::ExpressionStore store;
    auto val = fir::make_value(fir::ValueKind::Integer, 0);
    auto type = fir::TypeHandle{0};
    auto h = store.add_literal(val, type);
    auto* e = store.expr(h);
    EXPECT_TRUE(fir::rtti::isa<fir::FirValueExpr>(e));
    EXPECT_EQ(fir::rtti::cast<fir::FirValueExpr>(e)->value, val);
    EXPECT_EQ(e->result_type, type);
}

TEST(ExprStore, BinaryExprKindRange) {
    fir::ExpressionStore store;
    auto type = fir::TypeHandle{0};
    auto leaf = store.add_self_ref(type);
    auto add = store.add_binary(fir::FirExpr::Kind::Add, leaf, leaf, type);
    auto* e = store.expr(add);
    EXPECT_TRUE(fir::rtti::isa<fir::FirBinaryExpr>(e));
    EXPECT_EQ(e->kind, fir::FirExpr::Kind::Add);
}

TEST(ExprStore, FnCallWithArgs) {
    fir::ExpressionStore store;
    auto type = fir::TypeHandle{0};
    auto sym = fir::SymbolHandle{0};
    auto a1 = store.add_self_ref(type);
    auto a2 = store.add_self_ref(type);
    fir::ExprHandle args[] = {a1, a2};
    auto h = store.add_fn_call(sym, args, type);
    auto* e = fir::rtti::cast<fir::FirCallExpr>(store.expr(h));
    EXPECT_EQ(e->arg_count, 2);
    auto call_args = store.call_args_of(*e);
    EXPECT_EQ(call_args[0], a1);
    EXPECT_EQ(call_args[1], a2);
}
```

**Step 2: Run test — expected FAIL**

**Step 3: Write the module** — All 12 structural subtypes from design doc Section 4, `ExpressionStore` struct with VecArena + `vector<FirExpr*>` pointer table + secondary tables. Each `add_*` method arena-allocates the node and pushes the pointer.

**Step 4: Run test — expected PASS**

**Step 5: Commit**

```bash
git add src/fir/rupa.fir-expr.cppm test/fir/fir-expr-test.cpp src/fir/CMakeLists.txt test/fir/CMakeLists.txt
git commit -m "feat(fir): add ExpressionStore with full 35-kind expression hierarchy"
```

---

## Batch 7: SymbolTable (depends on Batch 1, 6)

### Task 7.1: Create `rupa.fir-symbol.cppm` — Symbol hierarchy

**Files:**
- Create: `external/rupa/src/fir/rupa.fir-symbol.cppm`
- Create: `external/rupa/test/fir/fir-symbol-test.cpp`
- Modify: `external/rupa/src/fir/CMakeLists.txt`
- Modify: `external/rupa/test/fir/CMakeLists.txt`

**Step 1: Write the test** — Test all 6 symbol kinds (Type, Value, Function, Rule, Transform, Imported). Test RTTI. Test params secondary table. Test name_index lookup.

**Step 2: Run test — expected FAIL**

**Step 3: Write the module** — All FirSymbol subtypes from design doc Section 5, `SymbolTable` struct with VecArena + `vector<FirSymbol*>` + secondary tables.

**Step 4: Run test — expected PASS**

**Step 5: Commit**

```bash
git add src/fir/rupa.fir-symbol.cppm test/fir/fir-symbol-test.cpp src/fir/CMakeLists.txt test/fir/CMakeLists.txt
git commit -m "feat(fir): add SymbolTable with 6-kind symbol hierarchy"
```

---

## Batch 8: Wire ExpressionStore + SymbolTable into Fir + FirBuilder

### Task 8.1: Integrate ExpressionStore/SymbolTable into Fir container

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir.cppm` — import and compose ExpressionStore + SymbolTable
- Modify: `external/rupa/src/fir/rupa.fir-builder.cppm` — implement expression/symbol builder methods
- Create: `external/rupa/test/fir/fir-expr-builder-test.cpp` — test expression construction through FirBuilder

**Step 1: Write the test** — Build expressions through `FirBuilder`, build symbols through `FirBuilder`, verify round-trip via `fir.expressions` / `fir.symbols`.

**Step 2: Run test — expected FAIL**

**Step 3: Implement** — Fill in the stubbed expression/symbol methods in FirBuilder.

**Step 4: Run test — expected PASS**

**Step 5: Commit**

---

## Batch 9: Serialization — Format v6 (depends on all previous)

### Task 9.1: Rewrite `rupa.fir-serial.cppm` — Format v6 write path

**Files:**
- Replace: `external/rupa/src/fir/rupa.fir-serial.cppm`

**Step 1: Write serialize tests** — Empty FIR, types only, types + roles, instances, values, expressions, symbols, foreign refs, root markers. Error cases (bad magic, wrong version, truncated).

**Step 2: Run tests — expected FAIL**

**Step 3: Implement serialize** — 220-byte header, section mask, compact index remapping, string table, per-section serialization. Follow format v6 from design doc Section 7.

**Step 4: Run serialize tests — expected PASS for write path**

### Task 9.2: Format v6 read path + round-trip

**Step 1: Implement deserialize** — Read header, validate magic/version, load sections based on section mask.

**Step 2: Run all serial tests — expected PASS** (including round-trips)

**Step 3: Commit**

```bash
git add src/fir/rupa.fir-serial.cppm test/fir/fir-serial-test.cpp
git commit -m "feat(fir): rewrite serialization for format v6 with section-aligned layout"
```

---

## Batch 10: Delete old FIR code + remaining tests (depends on Batch 9)

### Task 10.1: Remove old files, update remaining tests

**Files:**
- Delete: `external/rupa/src/fir/rupa.fir-node.cppm` (replaced by handles)
- Delete: `external/rupa/src/fir/rupa.fir-instances.cppm` (replaced by model)
- Modify: `external/rupa/test/fir/fir-move-test.cpp` — adapt to new Fir
- Modify: `external/rupa/test/fir/fir-root-test.cpp` — adapt to new Fir + FirBuilder + serial
- Modify: `external/rupa/test/fir/fir-integration-test.cpp` — adapt to new type hierarchy
- Modify: `external/rupa/test/fir/fir-source-map-test.cpp` — adapt if SourceMap interface changed
- Delete: `external/rupa/test/fir/fir-node-test.cpp` (replaced by handles test)
- Delete: `external/rupa/test/fir/fir-arena-move-test.cpp` (kore arena tests, not FIR-specific)

**Step 1: Update each remaining test file to compile with new FIR API**

**Step 2: Run all FIR tests — expected PASS**

**Step 3: Commit**

```bash
git add -A src/fir/ test/fir/
git commit -m "chore(fir): remove old FIR files, adapt remaining tests to new API"
```

---

## Batch 11: Emitter Adaptation (depends on Batch 10)

### Task 11.1: Adapt `rupa.emitter.cppm` to new FIR

**Files:**
- Modify: `external/rupa/src/emitter/rupa.emitter.cppm`
- Modify: `external/rupa/test/emitter/emitter-test.cpp`

**Step 1: Update imports** — `import rupa.fir.handles; import rupa.fir.value;` etc.

**Step 2: Update `emit_types`** — Use `fir.types.type(h)` instead of `fir.as<TypeDef>(id)`, iterate via `fir.types.types` vector, use `FirType` accessors (`m3_kind()`, `is_abstract()`), get roles via `fir.types.roles_of(t)`.

**Step 3: Update `emit_instances`** — Use `fir.model.node(h)` instead of `fir.as<ObjectDef>(id)`, iterate properties via `fir.model.props_of(n)`, get values via `fir.model.values.get_*(vh)`, check `prop.is_node()` for containment.

**Step 4: Update `ForeignResolver`** — Now resolves `TypeHandle` and `RoleHandle` via TypeTable.

**Step 5: Update `type_name()` helper** — Handle foreign TypeHandles by looking up foreign ref, resolving module, indexing into external TypeTable.

**Step 6: Run emitter tests — expected PASS** (all 11 tests)

**Step 7: Commit**

```bash
git add src/emitter/rupa.emitter.cppm test/emitter/emitter-test.cpp
git commit -m "refactor(emitter): adapt to new FIR API with typed handles and ValueStore"
```

---

## Batch 12: Sema Adaptation (depends on Batch 10)

### Task 12.1: Adapt `rupa.sema-context.cppm`

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-context.cppm`

Update `SemaContext`/`SemaResult`/`RoleCache`/`build_role_cache()` to use `TypeHandle`/`RoleHandle`/`StringId` from new FIR handles.

### Task 12.2: Adapt `rupa.sema-lower-types.cppm`

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-types.cppm`

Update Phase A/B to use `FirBuilder` new API: `add_type()`, `add_role()`, `set_supertype()`, `add_enum_value()`, builtin seeding via `fir::builtin::kInteger` etc.

### Task 12.3: Adapt `rupa.sema-lower-instances.cppm`

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`

Update to use `begin_object()`, `add_property()`, `add_containment()`, `flush_properties()`, `add_reference()` with new typed handles.

### Task 12.4: Run all sema/build tests

Run: `cmake --build --preset debug && ctest --preset debug`
Expected: All existing sema and CLI tests pass.

### Task 12.5: Commit

```bash
git add src/sema/
git commit -m "refactor(sema): adapt type/instance lowering to new FIR API"
```

---

## Batch 13: Senda ARXML Compiler Adaptation (depends on Batch 10)

### Task 13.1: Adapt `senda.compiler-arxml.cppm`

**Files:**
- Modify: `src/compiler-arxml/senda.compiler-arxml.cppm` (from senda root)

Update `ArxmlCompiler`/`ParseState` to use new FirBuilder API:
- Replace `fir::Id` with `fir::TypeHandle`/`fir::RoleHandle`/`fir::NodeHandle`
- Replace `fir.as<ObjectDef>(id)` with `fir.model.node(h)`
- Replace `builder.add_property(obj, role, value)` with `builder.add_property(obj, role, type, value)`
- Replace `builder.create_reference_value(path)` with `builder.add_reference(segments)`
- Replace `builder.flush_properties(obj, pairs)` with `builder.flush_properties(obj, fir_props)`
- Update `path_index` hash map: `flat_hash_map<size_t, fir::NodeHandle>`
- Update `resolve_references` to iterate `fir.model.values.references` instead of walking all nodes

### Task 13.2: Adapt domain code generation

**Files:**
- Modify: `tools/schema-converter/converter/cpp_emitter.py` — update generated domain code to use new handle types
- Regenerate: `src/domains/senda.domains.r*.cppm`

Update the Python emitter to generate `fir::TypeHandle` / `fir::RoleHandle` instead of `fir::Id`, and use the new `FirBuilder` API.

### Task 13.3: Adapt Senda emitter tests

**Files:**
- Modify: `test/compiler-arxml/arxml-compiler-test.cpp`
- Modify: `test/emitter-rupa/emitter-rupa-test.cpp`
- Modify: `test/emitter-arxml/emitter-test.cpp`

Update all tests to use new FIR API.

### Task 13.4: Run all Senda tests

Run: `cmake --build --preset debug && ctest --preset debug`
Expected: All 12 compiler tests, 3 emitter-rupa tests, 2 emitter-arxml tests pass.

### Task 13.5: Commit

```bash
cd /Users/ekuhn/CLionProjects/senda
git add src/ test/ tools/
git commit -m "refactor(senda): adapt ARXML compiler and domain codegen to new FIR API"
```

---

## Batch 14: CLI Adaptation + Final Integration (depends on all previous)

### Task 14.1: Adapt CLI modules

**Files:**
- Modify: `external/rupa/src/cli/rupa.cli-emit.cppm` — use new FIR serial + emitter
- Modify: `external/rupa/src/cli/rupa.cli-build.cppm` — use new FIR serial

### Task 14.2: Full integration test

Run: Build and test the full pipeline:
```bash
cmake --preset debug && cmake --build --preset debug
ctest --preset debug
./build-debug/senda --schema r20-11 --emit /dev/null test/data/arxml/vehicle-comms-r20-11.arxml
```

Expected: All tests pass. ARXML compilation produces correct output.

### Task 14.3: Commit and submodule update

```bash
# Commit CLI changes in rupa
cd external/rupa
git add src/cli/
git commit -m "refactor(cli): adapt to new FIR API"

# Update submodule pointer in senda
cd ../..
git add external/rupa
git commit -m "chore: update rupa submodule for FIR redesign"
```

---

## Dependency Graph

```
Batch 1 (RTTI + Handles)
    ├── Batch 2 (ValueStore)
    │       └── Batch 4 (ModelGraph) ──┐
    ├── Batch 3 (TypeTable) ───────────┤
    │                                  ├── Batch 5 (Fir + FirBuilder) ──┐
    ├── Batch 6 (ExprStore) ───────────┤                                │
    └── Batch 7 (SymbolTable) ─────────┘                                │
                                    Batch 8 (Wire Expr/Sym into Fir) ───┤
                                    Batch 9 (Serialization v6) ─────────┤
                                    Batch 10 (Delete old + fix tests) ──┤
                                        ├── Batch 11 (Emitter) ────────┤
                                        ├── Batch 12 (Sema) ──────────┤
                                        ├── Batch 13 (ARXML compiler) ─┤
                                        └── Batch 14 (CLI + integration)┘
```

**Parallelizable:** Batches 2, 3, 6, 7 are independent once Batch 1 completes. Batches 11, 12, 13 are independent once Batch 10 completes.

**Estimated scope:** ~3,500 lines new FIR core + ~2,000 lines new tests + ~3,000 lines consumer adaptation = ~8,500 lines total across ~14 batches.
