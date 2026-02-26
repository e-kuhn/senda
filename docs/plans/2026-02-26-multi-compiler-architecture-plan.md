# Multi-Compiler Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable multiple compilers (Rupa, ARXML, etc.) to target FIR as the universal compilation output, with a compilation driver that dispatches based on file extension and manages domain scoping through the import chain.

**Architecture:** Layered library stack — FIR at the bottom, Domain system for M2 meta-model management, Compiler API for the interface contract, FIR Builder for construction, Compilation Driver for orchestration. Rupa provides domain-agnostic infrastructure; Senda adds AUTOSAR-specific compilers and pre-built domains. See `docs/plans/2026-02-26-multi-compiler-architecture-design.md` for the full design.

**Tech Stack:** C++26 modules, CMake 3.28+, Ninja, Homebrew LLVM, Google Test

**Design Doc:** `docs/plans/2026-02-26-multi-compiler-architecture-design.md`

**Worktree:** All implementation happens in `.worktrees/feat/multi-compiler-arch/` (create at execution time)

---

## Batch 1: FIR Movability

**Goal:** Make `Fir` a proper movable value type by adding move constructors to the arena types.

**Scope:** `external/rupa/external/kore/` and `external/rupa/src/fir/`

### Task 1.1: Make BumpArena movable

**Files:**
- Modify: `external/rupa/external/kore/src/core/kore.core.arena.cppm` (BumpArena class, ~line 85-159)
- Test: `external/rupa/test/fir/fir-arena-move-test.cpp` (create)

**Step 1: Write the failing test**

```cpp
#include <gtest/gtest.h>
import kore;

TEST(BumpArenaMove, MoveConstructorTransfersOwnership) {
    kore::BumpArena a;
    void* ptr = a.allocate(64);
    ASSERT_NE(ptr, nullptr);

    kore::BumpArena b(std::move(a));
    // b should own the memory now
    // a should be in a valid empty state
    void* ptr2 = b.allocate(64);
    ASSERT_NE(ptr2, nullptr);
}

TEST(BumpArenaMove, MoveAssignmentTransfersOwnership) {
    kore::BumpArena a;
    a.allocate(64);

    kore::BumpArena b;
    b = std::move(a);
    void* ptr = b.allocate(64);
    ASSERT_NE(ptr, nullptr);
}
```

**Step 2: Run test to verify it fails**

Build and run — expect compilation error: use of deleted move constructor.

**Step 3: Implement move constructors for BumpArena**

In `kore.core.arena.cppm`, add to `BumpArena`:

```cpp
BumpArena(BumpArena&& other) noexcept
    : head_(other.head_), block_size_(other.block_size_)
{
    other.head_ = nullptr;
}

BumpArena& operator=(BumpArena&& other) noexcept {
    if (this != &other) {
        // Release our blocks
        while (head_) {
            Block* next = head_->next;
            munmap(head_, head_->mapped_size);
            head_ = next;
        }
        head_ = other.head_;
        block_size_ = other.block_size_;
        other.head_ = nullptr;
    }
    return *this;
}
```

**Step 4: Run test to verify it passes**

```bash
cmake --build --preset debug && ctest --preset debug -R fir-arena-move
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(kore): add move semantics to BumpArena"
```

### Task 1.2: Make VecArena movable

**Files:**
- Modify: `external/rupa/external/kore/src/core/kore.core.arena.cppm` (VecArena class, ~line 204-267)
- Modify: `external/rupa/test/fir/fir-arena-move-test.cpp`

**Step 1: Add VecArena move tests**

```cpp
TEST(VecArenaMove, MoveConstructorTransfersOwnership) {
    kore::VecArena a;
    void* ptr = a.allocate(64);
    ASSERT_NE(ptr, nullptr);

    kore::VecArena b(std::move(a));
    void* ptr2 = b.allocate(64);
    ASSERT_NE(ptr2, nullptr);
}

TEST(VecArenaMove, MoveAssignmentTransfersOwnership) {
    kore::VecArena a;
    a.allocate(64);

    kore::VecArena b;
    b = std::move(a);
    void* ptr = b.allocate(64);
    ASSERT_NE(ptr, nullptr);
}
```

**Step 2: Run test to verify it fails**

**Step 3: Implement move constructors for VecArena**

```cpp
VecArena(VecArena&& other) noexcept
    : arena_(std::move(other.arena_))
{
    for (size_t i = 0; i < kNumBuckets; ++i) {
        buckets_[i] = other.buckets_[i];
        other.buckets_[i] = nullptr;
    }
}

VecArena& operator=(VecArena&& other) noexcept {
    if (this != &other) {
        arena_ = std::move(other.arena_);
        for (size_t i = 0; i < kNumBuckets; ++i) {
            buckets_[i] = other.buckets_[i];
            other.buckets_[i] = nullptr;
        }
    }
    return *this;
}
```

**Step 4: Run tests**

```bash
cmake --build --preset debug && ctest --preset debug -R fir-arena-move
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(kore): add move semantics to VecArena"
```

### Task 1.3: Make Fir movable

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir.cppm` (Fir class)
- Test: `external/rupa/test/fir/fir-move-test.cpp` (create)

**Step 1: Write the failing test**

```cpp
#include <gtest/gtest.h>
import rupa.fir;

TEST(FirMove, MoveConstructorPreservesNodes) {
    fir::Fir a;
    auto name = a.intern("TestType");
    auto id = a.add<fir::TypeDef>();
    a.as<fir::TypeDef>(id).name = name;

    fir::Fir b(std::move(a));
    ASSERT_EQ(b.nodeCount(), 1u);
    ASSERT_EQ(b.getString(b.as<fir::TypeDef>(id).name), "TestType");
}

TEST(FirMove, MoveAssignmentPreservesNodes) {
    fir::Fir a;
    auto name = a.intern("TestType");
    a.add<fir::TypeDef>();

    fir::Fir b;
    b = std::move(a);
    ASSERT_EQ(b.nodeCount(), 1u);
}
```

**Step 2: Run test to verify it fails**

**Step 3: Add move constructors to Fir**

Add to `Fir` class:

```cpp
Fir(Fir&&) noexcept = default;
Fir& operator=(Fir&&) noexcept = default;

// Disable copy
Fir(const Fir&) = delete;
Fir& operator=(const Fir&) = delete;
```

All members are now movable: `VecArena` (from 1.2), `LiteralStore` (already movable), `std::vector` (movable), `SourceMap` (check — likely needs default move too).

If `SourceMap` isn't movable, add `= default` move constructors to it as well.

**Step 4: Run tests**

```bash
cmake --build --preset debug && ctest --preset debug -R fir-move
```

**Step 5: Run ALL existing FIR tests to verify no regressions**

```bash
ctest --preset debug -R fir
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat(fir): add move semantics to Fir"
```

### Task 1.4: CMake for new tests

**Files:**
- Modify: `external/rupa/test/fir/CMakeLists.txt`

Add test targets for the new test files:

```cmake
add_executable(rupa.fir.arena_move_test fir-arena-move-test.cpp)
target_link_libraries(rupa.fir.arena_move_test PRIVATE rupa.fir GTest::gtest_main)
add_test(NAME rupa.fir.arena_move_test COMMAND rupa.fir.arena_move_test)
rupa_target_settings(rupa.fir.arena_move_test)

add_executable(rupa.fir.move_test fir-move-test.cpp)
target_link_libraries(rupa.fir.move_test PRIVATE rupa.fir GTest::gtest_main)
add_test(NAME rupa.fir.move_test COMMAND rupa.fir.move_test)
rupa_target_settings(rupa.fir.move_test)
```

Note: Create this CMakeLists.txt modification BEFORE running the tests in Tasks 1.1-1.3. Listed here separately for clarity but should be done first.

**Commit:**

```bash
git add -A && git commit -m "chore: add FIR move semantics test targets"
```

---

## Batch 2: Domain Library (Rupa)

**Goal:** Create the domain library with Domain, DomainView, DomainTransaction, and DomainExtension.

**Scope:** New library `rupa.domain` in `external/rupa/src/domain/`

### Task 2.1: Scaffold the domain module

**Files:**
- Create: `external/rupa/src/domain/CMakeLists.txt`
- Create: `external/rupa/src/domain/rupa.domain.cppm` (main module)
- Create: `external/rupa/src/domain/rupa.domain-view.cppm` (DomainView partition)
- Create: `external/rupa/src/domain/rupa.domain-storage.cppm` (Domain partition)
- Create: `external/rupa/src/domain/rupa.domain-transaction.cppm` (DomainTransaction partition)
- Create: `external/rupa/src/domain/rupa.domain-extension.cppm` (DomainExtension partition)
- Modify: `external/rupa/CMakeLists.txt` (add subdirectory)
- Create: `external/rupa/test/domain/CMakeLists.txt`
- Modify: `external/rupa/CMakeLists.txt` (add test subdirectory)

**Step 1: Create CMakeLists.txt for domain library**

```cmake
add_library(rupa.domain)
target_sources(rupa.domain
    PUBLIC FILE_SET CXX_MODULES FILES
        rupa.domain.cppm
        rupa.domain-view.cppm
        rupa.domain-storage.cppm
        rupa.domain-transaction.cppm
        rupa.domain-extension.cppm
)
target_link_libraries(rupa.domain
    PUBLIC rupa.fir kore
)
target_compile_features(rupa.domain PUBLIC cxx_std_26)
rupa_target_settings(rupa.domain)
```

**Step 2: Create skeleton module files**

Main module (`rupa.domain.cppm`):
```cpp
module;

export module rupa.domain;

export import :view;
export import :storage;
export import :transaction;
export import :extension;
```

Each partition starts as a skeleton with the types declared but not implemented. Build to verify the module structure compiles.

**Step 3: Add to root CMakeLists.txt**

Add `add_subdirectory(src/domain)` after the fir subdirectory.

**Step 4: Verify build**

```bash
cmake --build --preset debug
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(domain): scaffold domain module structure"
```

### Task 2.2: Implement DomainView (read-only query API)

**Files:**
- Modify: `external/rupa/src/domain/rupa.domain-view.cppm`
- Create: `external/rupa/test/domain/domain-view-test.cpp`

**Step 1: Write failing tests for DomainView**

Test type lookup, role introspection, enum values, and constraints. The DomainView is constructed from a Fir (for testing; in production, Domain creates it).

```cpp
#include <gtest/gtest.h>
import rupa.domain;
import rupa.fir;

class DomainViewTest : public ::testing::Test {
protected:
    fir::Fir type_fir;
    // Set up a small type system: one composite with two roles, one enum
    void SetUp() override {
        // Use FIR directly to create types (FirBuilder doesn't exist yet)
        // Create a "Signal" composite type with "name" (string) and "priority" (integer) roles
        // Create a "Priority" enum with values "HIGH", "MEDIUM", "LOW"
        // ... (populate type_fir with test data)
    }
};

TEST_F(DomainViewTest, FindTypeByName) {
    // Construct DomainView from the type FIR
    // auto view = make_domain_view(type_fir);
    // auto t = view.find_type("Signal");
    // EXPECT_TRUE(t.valid());
    // EXPECT_EQ(view.type_name(t), "Signal");
}

TEST_F(DomainViewTest, TypeNotFound) {
    // auto view = make_domain_view(type_fir);
    // auto t = view.find_type("NonExistent");
    // EXPECT_FALSE(t.valid());
}

TEST_F(DomainViewTest, RoleIntrospection) {
    // auto view = make_domain_view(type_fir);
    // auto t = view.find_type("Signal");
    // EXPECT_EQ(view.role_count(t), 2u);
    // auto r = view.find_role(t, "name");
    // EXPECT_TRUE(r.valid());
    // EXPECT_EQ(view.role_name(r), "name");
}

TEST_F(DomainViewTest, EnumValues) {
    // auto view = make_domain_view(type_fir);
    // auto t = view.find_type("Priority");
    // EXPECT_EQ(view.type_kind(t), fir::M3Kind::Enum);
    // EXPECT_EQ(view.enum_value_count(t), 3u);
}
```

**Step 2: Run to verify failure**

**Step 3: Implement DomainView**

Implement in `rupa.domain-view.cppm`:
- `TypeHandle` and `RoleHandle` as opaque wrappers around FIR `Id`
- All query methods delegate to the underlying FIR
- Build a name→TypeHandle index on construction (e.g., using `absl::flat_hash_map` or linear scan for small sets)

**Step 4: Run tests**

```bash
cmake --build --preset debug && ctest --preset debug -R domain-view
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(domain): implement DomainView read-only query API"
```

### Task 2.3: Implement Domain (storage + accumulation)

**Files:**
- Modify: `external/rupa/src/domain/rupa.domain-storage.cppm`
- Create: `external/rupa/test/domain/domain-storage-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(DomainTest, ConstructFromFir) {
    fir::Fir type_fir;
    // ... populate with a type
    rupa::domain::Domain d("autosar", std::move(type_fir));
    EXPECT_EQ(d.name(), "autosar");
    auto view = d.view();
    // Verify types are queryable through the view
}

TEST(DomainTest, WithExtensionsProducesNewDomain) {
    // Create base domain with type A
    // Create extension with type B
    // auto d2 = d.with_extensions({ext});
    // d2.view() should see both A and B
    // d.view() should still only see A (immutability)
}
```

**Step 2: Run to verify failure**

**Step 3: Implement Domain**

- Owns the name and one or more type FIRs
- `view()` creates a DomainView over all owned FIRs
- `with_extensions()` returns a new Domain incorporating extensions (copies/moves base + extension FIRs)

**Step 4: Run tests**

```bash
cmake --build --preset debug && ctest --preset debug -R domain-storage
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(domain): implement Domain storage and accumulation"
```

### Task 2.4: Implement DomainTransaction (mutable overlay)

**Files:**
- Modify: `external/rupa/src/domain/rupa.domain-transaction.cppm`
- Create: `external/rupa/test/domain/domain-transaction-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(DomainTransactionTest, FindTypeInBase) {
    // Create domain with type "Signal"
    // Create transaction from domain.view()
    // transaction.find_type("Signal") should succeed (delegates to base)
}

TEST(DomainTransactionTest, FindNewlyAddedType) {
    // Create transaction from domain.view()
    // transaction.add_type("NewType", ...)
    // transaction.find_type("NewType") should succeed (found in pending)
}

TEST(DomainTransactionTest, PendingDoesNotAffectBase) {
    // Create transaction, add type "NewType"
    // domain.view().find_type("NewType") should fail (base unchanged)
}

TEST(DomainTransactionTest, IntoExtension) {
    // Create transaction, add types
    // auto ext = std::move(transaction).into_extension();
    // ext.domain_name() should match
    // ext.types() should contain the added types
}
```

**Step 2: Run to verify failure**

**Step 3: Implement DomainTransaction**

- Holds a `const DomainView&` as base
- Maintains a small `Fir` for pending additions
- `find_type()`: check base first (fast), then linear scan pending
- `into_extension()`: moves the pending FIR into a DomainExtension

**Step 4: Run tests**

```bash
cmake --build --preset debug && ctest --preset debug -R domain-transaction
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(domain): implement DomainTransaction mutable overlay"
```

### Task 2.5: Implement DomainExtension

**Files:**
- Modify: `external/rupa/src/domain/rupa.domain-extension.cppm`

This is a simple data type — domain name + type FIR. Likely implemented alongside Task 2.4 since `into_extension()` produces it. If not already done:

```cpp
class DomainExtension {
public:
    DomainExtension(std::string name, fir::Fir types);
    std::string_view domain_name() const;
    const fir::Fir& types() const;
    fir::Fir&& take_types() &&;
private:
    std::string name_;
    fir::Fir types_;
};
```

**Commit:**

```bash
git add -A && git commit -m "feat(domain): implement DomainExtension"
```

### Task 2.6: Test CMake setup for domain

**Files:**
- Create: `external/rupa/test/domain/CMakeLists.txt`

```cmake
add_executable(rupa.domain.view_test domain-view-test.cpp)
target_link_libraries(rupa.domain.view_test PRIVATE rupa.domain rupa.fir GTest::gtest_main)
add_test(NAME rupa.domain.view_test COMMAND rupa.domain.view_test)
rupa_target_settings(rupa.domain.view_test)

add_executable(rupa.domain.storage_test domain-storage-test.cpp)
target_link_libraries(rupa.domain.storage_test PRIVATE rupa.domain rupa.fir GTest::gtest_main)
add_test(NAME rupa.domain.storage_test COMMAND rupa.domain.storage_test)
rupa_target_settings(rupa.domain.storage_test)

add_executable(rupa.domain.transaction_test domain-transaction-test.cpp)
target_link_libraries(rupa.domain.transaction_test PRIVATE rupa.domain rupa.fir GTest::gtest_main)
add_test(NAME rupa.domain.transaction_test COMMAND rupa.domain.transaction_test)
rupa_target_settings(rupa.domain.transaction_test)
```

Note: Create this BEFORE running tests in Tasks 2.2-2.4.

---

## Batch 3: Compiler API (Rupa)

**Goal:** Define the Compiler interface, CompileContext, CompileResult, CompilerRegistry, and Diagnostics types.

**Scope:** New library `rupa.compiler` in `external/rupa/src/compiler/`

### Task 3.1: Scaffold the compiler-api module

**Files:**
- Create: `external/rupa/src/compiler/CMakeLists.txt`
- Create: `external/rupa/src/compiler/rupa.compiler.cppm` (main module)
- Create: `external/rupa/src/compiler/rupa.compiler-interface.cppm` (Compiler + CompileContext)
- Create: `external/rupa/src/compiler/rupa.compiler-result.cppm` (CompileResult + Diagnostics)
- Create: `external/rupa/src/compiler/rupa.compiler-registry.cppm` (CompilerRegistry)
- Modify: `external/rupa/CMakeLists.txt` (add subdirectory)

**CMakeLists.txt:**

```cmake
add_library(rupa.compiler)
target_sources(rupa.compiler
    PUBLIC FILE_SET CXX_MODULES FILES
        rupa.compiler.cppm
        rupa.compiler-interface.cppm
        rupa.compiler-result.cppm
        rupa.compiler-registry.cppm
)
target_link_libraries(rupa.compiler
    PUBLIC rupa.fir rupa.domain kore
)
target_compile_features(rupa.compiler PUBLIC cxx_std_26)
rupa_target_settings(rupa.compiler)
```

**Step 1: Create skeleton modules, verify build**

**Step 2: Commit**

```bash
git add -A && git commit -m "feat(compiler): scaffold compiler-api module structure"
```

### Task 3.2: Implement Diagnostics type

**Files:**
- Modify: `external/rupa/src/compiler/rupa.compiler-result.cppm`
- Create: `external/rupa/test/compiler/diagnostics-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(DiagnosticsTest, EmptyByDefault) {
    rupa::compiler::Diagnostics diags;
    EXPECT_EQ(diags.count(), 0u);
    EXPECT_FALSE(diags.has_errors());
}

TEST(DiagnosticsTest, AddAndQuery) {
    rupa::compiler::Diagnostics diags;
    diags.add(/* error diagnostic */);
    diags.add(/* warning diagnostic */);
    EXPECT_EQ(diags.count(), 2u);
    EXPECT_TRUE(diags.has_errors());
}

TEST(DiagnosticsTest, Iterable) {
    rupa::compiler::Diagnostics diags;
    diags.add(/* diagnostic */);
    size_t count = 0;
    for (const auto& d : diags) { ++count; }
    EXPECT_EQ(count, 1u);
}
```

**Step 2: Run to verify failure**

**Step 3: Implement Diagnostics**

Define `Diagnostic` (severity enum + message + source location) and `Diagnostics` (opaque container with iteration support).

**Step 4: Run tests, commit**

```bash
git add -A && git commit -m "feat(compiler): implement Diagnostics type"
```

### Task 3.3: Implement CompileResult

**Files:**
- Modify: `external/rupa/src/compiler/rupa.compiler-result.cppm`

```cpp
class CompileResult {
public:
    CompileResult(fir::Fir fir, DomainExtensions extensions, Diagnostics diagnostics);

    fir::Fir& fir();
    const fir::Fir& fir() const;
    fir::Fir take_fir() &&;

    DomainExtensions& extensions();
    const DomainExtensions& extensions() const;

    Diagnostics& diagnostics();
    const Diagnostics& diagnostics() const;

    bool has_errors() const;
private:
    fir::Fir fir_;
    DomainExtensions extensions_;
    Diagnostics diagnostics_;
};
```

`DomainExtensions` is an opaque container of `DomainExtension` (same pattern as `Diagnostics`).

**Commit:**

```bash
git add -A && git commit -m "feat(compiler): implement CompileResult and DomainExtensions"
```

### Task 3.4: Implement Compiler and CompileContext interfaces

**Files:**
- Modify: `external/rupa/src/compiler/rupa.compiler-interface.cppm`
- Create: `external/rupa/test/compiler/compiler-interface-test.cpp`

**Step 1: Define interfaces**

```cpp
class CompileContext {
public:
    virtual ~CompileContext() = default;
    virtual CompileResult compile_import(const std::filesystem::path& path) = 0;
    virtual const domain::DomainView* request_domain(std::string_view domain_name) = 0;
    virtual domain::DomainTransaction& domain_transaction() = 0;
    virtual std::filesystem::path resolve_path(
        const std::filesystem::path& relative) const = 0;
};

class Compiler {
public:
    virtual ~Compiler() = default;
    virtual /* extension list type */ extensions() const = 0;
    virtual CompileResult compile(
        const std::filesystem::path& path,
        CompileContext& context) = 0;
};
```

**Step 2: Write a test with a mock compiler**

```cpp
// Simple mock compiler that produces an empty FIR
class MockCompiler : public rupa::compiler::Compiler {
public:
    /* extensions */ extensions() const override { return {".mock"}; }
    CompileResult compile(const fs::path& path, CompileContext& ctx) override {
        return CompileResult(fir::Fir{}, {}, {});
    }
};

TEST(CompilerInterfaceTest, MockCompilerProducesEmptyFir) {
    MockCompiler compiler;
    // Use a mock context
    // auto result = compiler.compile("test.mock", mock_context);
    // EXPECT_EQ(result.fir().nodeCount(), 0u);
}
```

**Step 3: Verify build and tests pass**

**Step 4: Commit**

```bash
git add -A && git commit -m "feat(compiler): implement Compiler and CompileContext interfaces"
```

### Task 3.5: Implement CompilerRegistry

**Files:**
- Modify: `external/rupa/src/compiler/rupa.compiler-registry.cppm`
- Create: `external/rupa/test/compiler/registry-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(CompilerRegistryTest, RegisterAndFind) {
    MockCompiler mock;
    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(mock);
    auto* found = registry.find_compiler(".mock");
    EXPECT_EQ(found, &mock);
}

TEST(CompilerRegistryTest, UnknownExtensionReturnsNull) {
    rupa::compiler::CompilerRegistry registry;
    auto* found = registry.find_compiler(".unknown");
    EXPECT_EQ(found, nullptr);
}

TEST(CompilerRegistryTest, MultipleExtensions) {
    // Compiler that handles {".arxml", ".xml"}
    // Both extensions should resolve to the same compiler
}
```

**Step 2: Run to verify failure**

**Step 3: Implement CompilerRegistry**

Simple extension-to-compiler map. Store `std::string_view` → `Compiler*` (non-owning).

**Step 4: Run tests, commit**

```bash
git add -A && git commit -m "feat(compiler): implement CompilerRegistry"
```

### Task 3.6: Test CMake for compiler module

**Files:**
- Create: `external/rupa/test/compiler/CMakeLists.txt`

Create before running tests, following the same pattern as other test directories.

---

## Batch 4: FIR Builder (Rupa)

**Goal:** Create a thin, compiler-friendly construction API on top of Fir. Simple enough to hand-code a domain.

**Scope:** New library `rupa.fir.builder` in `external/rupa/src/fir/` (as a separate CMake target, same directory)

### Task 4.1: Scaffold FIR Builder module

**Files:**
- Create: `external/rupa/src/fir/rupa.fir-builder.cppm`
- Modify: `external/rupa/src/fir/CMakeLists.txt` (add new target)

Add a new library target `rupa.fir.builder` (separate from `rupa.fir`):

```cmake
add_library(rupa.fir.builder)
target_sources(rupa.fir.builder
    PUBLIC FILE_SET CXX_MODULES FILES
        rupa.fir-builder.cppm
)
target_link_libraries(rupa.fir.builder
    PUBLIC rupa.fir kore
)
target_compile_features(rupa.fir.builder PUBLIC cxx_std_26)
rupa_target_settings(rupa.fir.builder)
```

**Commit:**

```bash
git add -A && git commit -m "feat(fir): scaffold FirBuilder module"
```

### Task 4.2: Implement FirBuilder — type construction

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-builder.cppm`
- Create: `external/rupa/test/fir/fir-builder-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(FirBuilderTest, CreateCompositeType) {
    fir::Fir fir;
    rupa::fir::FirBuilder builder(fir);

    auto signal = builder.begin_type("Signal", fir::M3Kind::Composite);
    EXPECT_TRUE(signal.valid());

    auto view = /* create DomainView from fir */;
    auto t = view.find_type("Signal");
    EXPECT_EQ(view.type_kind(t), fir::M3Kind::Composite);
}

TEST(FirBuilderTest, AddRoleToType) {
    fir::Fir fir;
    rupa::fir::FirBuilder builder(fir);

    auto signal = builder.begin_type("Signal", fir::M3Kind::Composite);
    auto string_type = builder.begin_type("string", fir::M3Kind::Primitive);
    builder.add_role(signal, "name", string_type, fir::Multiplicity::One);

    // Verify role exists via DomainView
}

TEST(FirBuilderTest, CreateEnumWithValues) {
    fir::Fir fir;
    rupa::fir::FirBuilder builder(fir);

    auto priority = builder.begin_type("Priority", fir::M3Kind::Enum);
    builder.add_enum_value(priority, "HIGH");
    builder.add_enum_value(priority, "MEDIUM");
    builder.add_enum_value(priority, "LOW");

    // Verify enum values via DomainView
}

TEST(FirBuilderTest, SetSupertype) {
    fir::Fir fir;
    rupa::fir::FirBuilder builder(fir);

    auto base = builder.begin_type("Identifiable", fir::M3Kind::Composite);
    builder.set_abstract(base, true);
    auto derived = builder.begin_type("Signal", fir::M3Kind::Composite);
    builder.set_supertype(derived, base);

    // Verify supertype via DomainView
}

TEST(FirBuilderTest, HandCodedDomain) {
    // End-to-end test: build a small domain programmatically,
    // create a Domain from the FIR, verify through DomainView.
    fir::Fir type_fir;
    rupa::fir::FirBuilder builder(type_fir);

    auto string_t = builder.begin_type("string", fir::M3Kind::Primitive);
    auto int_t = builder.begin_type("integer", fir::M3Kind::Primitive);

    auto signal = builder.begin_type("Signal", fir::M3Kind::Composite);
    builder.add_role(signal, "name", string_t, fir::Multiplicity::One);
    builder.add_role(signal, "priority", int_t, fir::Multiplicity::ZeroOrOne);
    builder.set_domain(signal, "autosar");

    rupa::domain::Domain d("autosar", std::move(type_fir));
    auto view = d.view();
    EXPECT_TRUE(view.has_type("Signal"));
    EXPECT_EQ(view.role_count(view.find_type("Signal")), 2u);
}
```

**Step 2: Run to verify failure**

**Step 3: Implement FirBuilder**

The builder wraps `Fir` and provides high-level methods that manage the secondary tables (role_ids, enum_values, etc.) correctly. Uses opaque handles that map to FIR `Id` internally.

**Step 4: Run tests, commit**

```bash
git add -A && git commit -m "feat(fir): implement FirBuilder type construction API"
```

### Task 4.3: Implement FirBuilder — instance construction

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-builder.cppm`
- Modify: `external/rupa/test/fir/fir-builder-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(FirBuilderTest, CreateObjectInstance) {
    fir::Fir fir;
    rupa::fir::FirBuilder builder(fir);

    auto signal_type = builder.begin_type("Signal", fir::M3Kind::Composite);
    auto name_role = builder.add_role(signal_type, "name", /* string */, fir::Multiplicity::One);

    auto obj = builder.begin_object("MySensor", signal_type);
    builder.add_property(obj, name_role, "MySensor");  // string value

    EXPECT_EQ(fir.countByKind(fir::NodeKind::ObjectDef), 1u);
}
```

**Step 2: Implement instance construction methods**

**Step 3: Run tests, commit**

```bash
git add -A && git commit -m "feat(fir): implement FirBuilder instance construction API"
```

---

## Batch 5: Compilation Driver (Rupa)

**Goal:** Implement the new compilation driver that orchestrates multiple compilers, manages domains, and handles import resolution with cycle detection and disk caching.

**Scope:** New library `rupa.driver` in `external/rupa/src/driver/`

### Task 5.1: Scaffold driver module

**Files:**
- Create: `external/rupa/src/driver/CMakeLists.txt`
- Create: `external/rupa/src/driver/rupa.driver.cppm` (main module)
- Create: `external/rupa/src/driver/rupa.driver-context.cppm` (DriverCompileContext)
- Create: `external/rupa/src/driver/rupa.driver-cache.cppm` (disk cache)
- Modify: `external/rupa/CMakeLists.txt` (add subdirectory)

**CMakeLists.txt:**

```cmake
add_library(rupa.driver)
target_sources(rupa.driver
    PUBLIC FILE_SET CXX_MODULES FILES
        rupa.driver.cppm
        rupa.driver-context.cppm
        rupa.driver-cache.cppm
)
target_link_libraries(rupa.driver
    PUBLIC rupa.compiler rupa.domain rupa.fir rupa.fir.serial kore
)
target_compile_features(rupa.driver PUBLIC cxx_std_26)
rupa_target_settings(rupa.driver)
```

**Commit:**

```bash
git add -A && git commit -m "feat(driver): scaffold compilation driver module"
```

### Task 5.2: Implement CompilationDriver core

**Files:**
- Modify: `external/rupa/src/driver/rupa.driver.cppm`
- Create: `external/rupa/test/driver/driver-test.cpp`

**Step 1: Write failing tests**

```cpp
// Uses MockCompiler from Batch 3 tests
TEST(CompilationDriverTest, CompileSingleFile) {
    MockCompiler mock;  // handles ".mock", returns empty FIR
    CompilerRegistry registry;
    registry.register_compiler(mock);

    CompilationDriver driver(registry);
    auto result = driver.compile("test.mock");
    EXPECT_FALSE(result.has_errors());
}

TEST(CompilationDriverTest, UnknownExtensionProducesError) {
    CompilerRegistry registry;  // empty
    CompilationDriver driver(registry);
    auto result = driver.compile("test.unknown");
    EXPECT_TRUE(result.has_errors());
}

TEST(CompilationDriverTest, AddDomainMakesItAvailable) {
    // Register a compiler that calls context.request_domain("test-domain")
    // Pre-load domain into driver
    // Verify compiler receives the domain
}
```

**Step 2: Implement CompilationDriver**

Core methods:
- `add_domain(Domain)` — stores in name→Domain map
- `compile(path)` — looks up extension, creates context, invokes compiler

**Step 3: Run tests, commit**

```bash
git add -A && git commit -m "feat(driver): implement CompilationDriver core"
```

### Task 5.3: Implement DriverCompileContext

**Files:**
- Modify: `external/rupa/src/driver/rupa.driver-context.cppm`
- Create: `external/rupa/test/driver/driver-import-test.cpp`

**Step 1: Write failing tests for import resolution**

```cpp
TEST(DriverImportTest, ImportResolvesViaRegistry) {
    // MockCompiler A handles ".a", MockCompiler B handles ".b"
    // Compiler A calls context.compile_import("dep.b") during compilation
    // Verify that Compiler B is invoked for "dep.b"
}

TEST(DriverImportTest, CircularImportDetected) {
    // Compiler A imports "b.mock" which imports "a.mock"
    // Verify circular import error is reported
}

TEST(DriverImportTest, CachedFileNotRecompiled) {
    // Compile "file.mock" twice
    // Verify the compiler is only invoked once
}

TEST(DriverImportTest, DomainSnapshotIsolation) {
    // Compiler that adds domain extension
    // Import two siblings from a parent
    // Verify siblings see the same base domain, not each other's extensions
}
```

**Step 2: Implement DriverCompileContext**

The context implements `CompileContext`:
- `compile_import()`: path resolution, cache check, cycle detection, registry dispatch
- `request_domain()`: look up in driver's domain map
- `domain_transaction()`: return the transaction for this compilation
- `resolve_path()`: relative to current file's directory

**Step 3: Run tests, commit**

```bash
git add -A && git commit -m "feat(driver): implement DriverCompileContext with import resolution"
```

### Task 5.4: Implement disk cache

**Files:**
- Modify: `external/rupa/src/driver/rupa.driver-cache.cppm`
- Create: `external/rupa/test/driver/driver-cache-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(DriverCacheTest, CacheHitSkipsCompilation) {
    // Write a .fir file newer than source
    // Compile — verify compiler not invoked, FIR loaded from disk
}

TEST(DriverCacheTest, CacheMissTriggersCompilation) {
    // Source newer than .fir (or no .fir)
    // Compile — verify compiler is invoked
}

TEST(DriverCacheTest, SuccessfulCompilationWritesCache) {
    // Compile a file successfully
    // Verify .fir file written to disk
}
```

**Step 2: Implement cache**

Uses existing FIR serialization (`rupa.fir.serial`) for read/write. Cache key: canonical path. Invalidation: source file modification time vs. cache file modification time.

**Step 3: Run tests, commit**

```bash
git add -A && git commit -m "feat(driver): implement FIR disk caching"
```

---

## Batch 6: RupaCompiler (Rupa)

**Goal:** Wrap the existing lexer + parser + sema pipeline as a `Compiler` implementation.

**Scope:** Refactor `external/rupa/src/sema/` to implement the `Compiler` interface.

### Task 6.1: Create RupaCompiler adapter

**Files:**
- Create: `external/rupa/src/sema/rupa.sema-compiler.cppm` (new partition)
- Modify: `external/rupa/src/sema/rupa.sema.cppm` (export new partition)
- Modify: `external/rupa/src/sema/CMakeLists.txt` (add new file)
- Create: `external/rupa/test/sema/sema-compiler-test.cpp`

**Step 1: Write failing tests**

```cpp
TEST(RupaCompilerTest, ImplementsCompilerInterface) {
    rupa::sema::RupaCompiler compiler;
    // Verify it handles ".rupa" extension
    auto exts = compiler.extensions();
    // EXPECT extension list contains ".rupa"
}

TEST(RupaCompilerTest, CompileSimpleTypeFile) {
    rupa::sema::RupaCompiler compiler;
    // Write a temp .rupa file with a simple type definition
    // Create a mock CompileContext
    // auto result = compiler.compile(temp_path, mock_context);
    // EXPECT_FALSE(result.has_errors());
    // EXPECT result.fir() contains the type
}

TEST(RupaCompilerTest, CompileWithImportDelegates) {
    // Rupa file that imports another file
    // Verify compile_import is called on the context
}
```

**Step 2: Implement RupaCompiler**

The `RupaCompiler` adapts the existing sema pipeline:
- `extensions()` → `{".rupa"}`
- `compile()`:
  1. Read and parse file (existing lexer + parser)
  2. Walk AST for domain declarations → call `context.request_domain()`
  3. Walk AST for imports → call `context.compile_import()`
  4. Run type collection + resolution (existing sema-lower-types)
  5. Run instance lowering (existing sema-lower-instances)
  6. Return CompileResult with per-file FIR

This is an adapter, not a rewrite. The existing sema code does the heavy lifting. The new code translates between the `Compiler`/`CompileContext` interface and the existing sema internals.

**Step 3: Run tests**

```bash
cmake --build --preset debug && ctest --preset debug -R sema-compiler
```

**Step 4: Verify all existing sema tests still pass**

```bash
ctest --preset debug -R sema
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(sema): implement RupaCompiler adapter for Compiler interface"
```

### Task 6.2: Integration test — RupaCompiler + Driver

**Files:**
- Create: `external/rupa/test/driver/driver-rupa-integration-test.cpp`

**Step 1: Write integration test**

```cpp
TEST(DriverRupaIntegration, CompileMultiFileRupaProject) {
    rupa::sema::RupaCompiler rupa_compiler;
    CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);

    CompilationDriver driver(registry);

    // Write temp .rupa files:
    // base.rupa — defines types
    // main.rupa — imports base.rupa, creates instances

    auto result = driver.compile(main_path);
    EXPECT_FALSE(result.has_errors());
    // Verify FIR contains both types and instances
}
```

**Step 2: Run and verify**

**Step 3: Commit**

```bash
git add -A && git commit -m "test(driver): add RupaCompiler + Driver integration test"
```

---

## Batch 7: ARXML Compiler (Senda)

**Goal:** Implement an ARXML compiler in Senda that reads ARXML files and produces M1 FIR instances conforming to AUTOSAR domain types.

**Scope:** New code in Senda's `src/` directory.

### Task 7.1: Scaffold ARXML compiler in Senda

**Files:**
- Create: `src/compiler-arxml/CMakeLists.txt`
- Create: `src/compiler-arxml/senda.compiler-arxml.cppm`
- Modify: `CMakeLists.txt` (add subdirectory, update dependencies)

**CMakeLists.txt:**

```cmake
add_library(senda.compiler.arxml)
target_sources(senda.compiler.arxml
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.compiler-arxml.cppm
)
target_link_libraries(senda.compiler.arxml
    PUBLIC rupa.compiler rupa.fir.builder rupa.domain
)
target_compile_features(senda.compiler.arxml PUBLIC cxx_std_26)
# Add XML parsing dependency (e.g., pugixml or libxml2)
```

**Commit:**

```bash
git add -A && git commit -m "feat(senda): scaffold ARXML compiler module"
```

### Task 7.2: Implement ARXML parsing + FIR generation

**Files:**
- Modify: `src/compiler-arxml/senda.compiler-arxml.cppm`
- Create: `test/compiler-arxml/arxml-compiler-test.cpp`
- Create: `test/compiler-arxml/CMakeLists.txt`
- Create: `test/compiler-arxml/fixtures/` (sample ARXML files)

**Step 1: Write failing tests**

```cpp
TEST(ArxmlCompilerTest, ImplementsCompilerInterface) {
    senda::ArxmlCompiler compiler;
    // Verify handles ".arxml"
}

TEST(ArxmlCompilerTest, CompileSimpleArxml) {
    senda::ArxmlCompiler compiler;
    // Create a minimal ARXML fixture file with a known structure
    // Provide a mock context with AUTOSAR domain loaded
    // auto result = compiler.compile(arxml_path, mock_context);
    // EXPECT_FALSE(result.has_errors());
    // Verify FIR contains expected M1 instances
}

TEST(ArxmlCompilerTest, SchemaReferenceMapsToDomain) {
    // ARXML file with schemaLocation pointing to AUTOSAR schema
    // Verify compiler calls context.request_domain() with correct name
}
```

**Step 2: Implement ArxmlCompiler**

- `extensions()` → `{".arxml"}`
- `compile()`:
  1. Parse XML (using pugixml or libxml2)
  2. Extract schema reference → map to domain name
  3. Call `context.request_domain(domain_name)` to get the meta-model
  4. Walk XML elements, use `context.domain_transaction()` to look up types
  5. Use `FirBuilder` to create M1 ObjectDef/PropertyVal/ValueDef nodes
  6. Return CompileResult

**Step 3: Run tests, commit**

```bash
git add -A && git commit -m "feat(senda): implement ArxmlCompiler"
```

### Task 7.3: Pre-built AUTOSAR domains

**Files:**
- Create: `src/domains/CMakeLists.txt`
- Create: `src/domains/senda.domains.cppm`

Build AUTOSAR domains programmatically using the FirBuilder API. This replaces the current schema-converter → .rupa → compile pipeline with direct FirBuilder calls, or loads pre-serialized .fir files.

Two approaches (decide during implementation):
1. **FirBuilder at startup**: C++ code that calls FirBuilder to create all AUTOSAR types. Fast, no file I/O, but verbose.
2. **Pre-serialized FIR**: Use the schema converter to generate .rupa, compile once to .fir, ship the .fir file. Load at startup via deserialization.

Option 2 is more practical initially — leverages existing schema converter.

**Commit:**

```bash
git add -A && git commit -m "feat(senda): add pre-built AUTOSAR domain loading"
```

---

## Batch 8: CLI Integration (Senda)

**Goal:** Wire everything together in Senda's CLI: register compilers, load domains, run the compilation driver.

**Scope:** `src/main.cpp` and Senda's CMakeLists.txt.

### Task 8.1: Update Senda CLI

**Files:**
- Modify: `src/main.cpp`
- Modify: `CMakeLists.txt` (update link dependencies)

**Step 1: Wire up startup**

```cpp
#include <filesystem>
import rupa.compiler;
import rupa.driver;
import rupa.sema;          // RupaCompiler
import senda.compiler.arxml;  // ArxmlCompiler
import senda.domains;         // AUTOSAR domain loading

int main(int argc, char* argv[]) {
    // Parse CLI args (build command)

    // Create compilers
    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler;

    // Register
    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    // Create driver
    rupa::driver::CompilationDriver driver(registry);

    // Load pre-built AUTOSAR domains
    driver.add_domain(senda::domains::load_autosar_r23_11());

    // Compile
    auto result = driver.compile(input_path);

    // Handle result (serialize, serve, diagnostics)
}
```

**Step 2: Update CMakeLists.txt**

```cmake
target_link_libraries(senda PRIVATE
    rupa.driver
    rupa.sema
    senda.compiler.arxml
    senda.domains
)
```

**Step 3: Integration test**

```bash
# Create a test .rupa file that imports an .arxml file
# Run: ./build-debug/senda build test-project.rupa
# Verify output .fir file is produced
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat(senda): wire multi-compiler CLI with ARXML support"
```

### Task 8.2: End-to-end test

**Files:**
- Create: `test/integration/e2e-arxml-import-test.cpp` (or shell-based test)

Test the full pipeline: Rupa file imports ARXML file → compilation produces FIR with both type references and M1 instances.

**Commit:**

```bash
git add -A && git commit -m "test(senda): add end-to-end ARXML import integration test"
```

---

## Batch Dependencies

```
Batch 1 (FIR Movability)
    ↓
Batch 2 (Domain Library) ───→ Batch 3 (Compiler API)
    ↓                              ↓
Batch 4 (FIR Builder)        Batch 5 (Compilation Driver)
    ↓                              ↓
    └──────────────────→ Batch 6 (RupaCompiler)
                               ↓
                         Batch 7 (ARXML Compiler) ← Senda
                               ↓
                         Batch 8 (CLI Integration) ← Senda
```

Batches 2 and 3 can be worked on in parallel.
Batch 4 can start as soon as Batch 1 is done (independent of 2 and 3).
Batches 5 and 6 depend on 2, 3, and 4.
Batches 7 and 8 are Senda-specific and depend on all Rupa batches.

## Submodule Commit Strategy

Since most work is in `external/rupa/` (Batches 1-6), follow the inside-out rule:
1. Commit inside `external/rupa/external/kore/` first (Batch 1 arena changes)
2. Commit inside `external/rupa/` (Batches 1-6)
3. Commit in Senda root (Batches 7-8 + submodule pointer updates)
