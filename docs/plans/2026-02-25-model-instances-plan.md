# Model Instances (M1) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Parse Rupa M1 instantiation syntax, lower it to FIR nodes alongside M2 types, and serve instances via the HTML explorer.

**Architecture:** Extend the existing FIR with three new node kinds (ObjectDef, PropertyVal, ValueDef) and a structured reference path model. A new sema Phase C walks Instantiation/Assignment AST nodes after type resolution, producing M1 FIR nodes. The explorer gets new API endpoints and an Instances tab.

**Tech Stack:** C++23 modules, CMake 3.28+, GoogleTest, kore libraries, fmt for JSON serialization.

**Design doc:** `docs/plans/2026-02-25-model-instances-design.md`

---

## Batch 1: FIR M1 Node Types

### Task 1: Add M1 node kinds and structs to FIR

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-node.cppm:15-18`
- Create: `external/rupa/src/fir/rupa.fir-instances.cppm`
- Modify: `external/rupa/src/fir/rupa.fir.cppm:12-13` (add import)
- Modify: `external/rupa/src/fir/CMakeLists.txt` (add new module)
- Test: `external/rupa/test/fir/fir-instance-test.cpp`

**Step 1: Write the failing test**

Create `external/rupa/test/fir/fir-instance-test.cpp`:

```cpp
#include <gtest/gtest.h>

import rupa.fir;

using namespace fir;

TEST(FirInstances, ObjectDefCreation) {
    Fir fir;
    auto name = fir.intern("::string");
    auto type_id = fir.add<TypeDef>(name, M3Kind::Primitive);
    auto identity = fir.intern("Pressure");

    auto obj_id = fir.add<ObjectDef>(type_id, identity);
    auto& obj = fir.as<ObjectDef>(obj_id);

    EXPECT_EQ(obj.kind, NodeKind::ObjectDef);
    EXPECT_EQ(static_cast<uint32_t>(obj.type_id), static_cast<uint32_t>(type_id));
    EXPECT_EQ(fir.getString(obj.identity), "Pressure");
    EXPECT_EQ(obj.prop_count, 0u);
    EXPECT_EQ(static_cast<uint32_t>(obj.derived_from), UINT32_MAX);
}

TEST(FirInstances, ValueDefInteger) {
    Fir fir;
    auto val_id = fir.add<ValueDef>(ValueKind::Integer, int64_t{42});
    auto& val = fir.as<ValueDef>(val_id);

    EXPECT_EQ(val.kind, NodeKind::ValueDef);
    EXPECT_EQ(val.value_kind, ValueKind::Integer);
    EXPECT_EQ(val.int_val, 42);
}

TEST(FirInstances, ValueDefFloat) {
    Fir fir;
    auto val_id = fir.add<ValueDef>(ValueKind::Float, 3.14);
    auto& val = fir.as<ValueDef>(val_id);

    EXPECT_EQ(val.value_kind, ValueKind::Float);
    EXPECT_DOUBLE_EQ(val.float_val, 3.14);
}

TEST(FirInstances, ValueDefString) {
    Fir fir;
    auto sid = fir.intern("hello");
    auto val_id = fir.add<ValueDef>(ValueKind::String, sid);
    auto& val = fir.as<ValueDef>(val_id);

    EXPECT_EQ(val.value_kind, ValueKind::String);
    EXPECT_EQ(fir.getString(val.string_val), "hello");
}

TEST(FirInstances, ValueDefBoolean) {
    Fir fir;
    auto val_id = fir.add<ValueDef>(ValueKind::Boolean, true);
    auto& val = fir.as<ValueDef>(val_id);

    EXPECT_EQ(val.value_kind, ValueKind::Boolean);
    EXPECT_TRUE(val.bool_val);
}

TEST(FirInstances, PropertyValCreation) {
    Fir fir;
    auto name = fir.intern("::integer");
    auto type_id = fir.add<TypeDef>(name, M3Kind::Primitive);
    auto role_name = fir.intern("length");
    auto role_id = fir.add<RoleDef>(role_name, type_id, Multiplicity::One, false);
    auto val_id = fir.add<ValueDef>(ValueKind::Integer, int64_t{16});

    auto prop_id = fir.add<PropertyVal>(role_id, val_id);
    auto& prop = fir.as<PropertyVal>(prop_id);

    EXPECT_EQ(prop.kind, NodeKind::PropertyVal);
    EXPECT_EQ(static_cast<uint32_t>(prop.role_id), static_cast<uint32_t>(role_id));
    EXPECT_EQ(static_cast<uint32_t>(prop.value_id), static_cast<uint32_t>(val_id));
}

TEST(FirInstances, ObjectDefWithProperties) {
    Fir fir;
    auto str_name = fir.intern("::string");
    auto str_type = fir.add<TypeDef>(str_name, M3Kind::Primitive);
    auto int_name = fir.intern("::integer");
    auto int_type = fir.add<TypeDef>(int_name, M3Kind::Primitive);

    auto sig_name = fir.intern("Signal");
    auto sig_type = fir.add<TypeDef>(sig_name, M3Kind::Composite);

    auto role_name = fir.intern("length");
    auto role_id = fir.add<RoleDef>(role_name, int_type, Multiplicity::One, false);
    auto val_id = fir.add<ValueDef>(ValueKind::Integer, int64_t{16});
    auto prop_id = fir.add<PropertyVal>(role_id, val_id);

    auto identity = fir.intern("Pressure");
    auto obj_id = fir.add<ObjectDef>(sig_type, identity);

    // Attach property via secondary table
    Id prop_ids[] = {prop_id};
    auto& obj = fir.as<ObjectDef>(obj_id);
    obj.prop_start = fir.appendProperties(prop_ids);
    obj.prop_count = 1;

    auto props = fir.propertiesOf(obj);
    EXPECT_EQ(props.size(), 1u);
    EXPECT_EQ(static_cast<uint32_t>(props[0]), static_cast<uint32_t>(prop_id));
}

TEST(FirInstances, ReferenceValueWithPathSegments) {
    Fir fir;
    auto comp_str = fir.intern("Components");
    auto sensor_str = fir.intern("SensorSWC");

    auto comp_val = fir.add<ValueDef>(ValueKind::String, comp_str);
    auto sensor_val = fir.add<ValueDef>(ValueKind::String, sensor_str);

    PathSegment segs[] = {
        {PathSegmentKind::Id, comp_val},
        {PathSegmentKind::Id, sensor_val},
    };

    auto ref_id = fir.add<ValueDef>(ValueKind::Reference);
    auto& ref = fir.as<ValueDef>(ref_id);
    ref.segment_start = fir.appendPathSegments(segs);
    ref.segment_count = 2;

    auto segments = fir.pathSegments(ref.segment_start, ref.segment_count);
    EXPECT_EQ(segments.size(), 2u);
    EXPECT_EQ(segments[0].kind, PathSegmentKind::Id);

    auto& seg0_val = fir.as<ValueDef>(segments[0].value);
    EXPECT_EQ(fir.getString(seg0_val.string_val), "Components");
}

TEST(FirInstances, CountByKindIncludesM1) {
    Fir fir;
    auto name = fir.intern("Signal");
    auto type_id = fir.add<TypeDef>(name, M3Kind::Composite);
    auto identity = fir.intern("Pressure");
    fir.add<ObjectDef>(type_id, identity);
    fir.add<ValueDef>(ValueKind::Integer, int64_t{42});

    EXPECT_EQ(fir.countByKind(NodeKind::TypeDef), 1u);
    EXPECT_EQ(fir.countByKind(NodeKind::ObjectDef), 1u);
    EXPECT_EQ(fir.countByKind(NodeKind::ValueDef), 1u);
}
```

Register the test in `external/rupa/test/fir/CMakeLists.txt` (add `fir-instance-test.cpp` to the test sources).

**Step 2: Run test to verify it fails**

Run: `cd external/rupa && cmake --build --preset debug --target fir-instance-test 2>&1 | tail -20`
Expected: Compilation failure — `ObjectDef`, `ValueDef`, `PropertyVal`, `PathSegment` not defined.

**Step 3: Extend NodeKind enum**

Modify `external/rupa/src/fir/rupa.fir-node.cppm` lines 15-18:

```cpp
enum class NodeKind : uint8_t {
    TypeDef,
    RoleDef,
    ObjectDef,
    PropertyVal,
    ValueDef,
};
```

**Step 4: Create M1 instance structs**

Create `external/rupa/src/fir/rupa.fir-instances.cppm`:

```cpp
module;

#include <cstdint>

export module rupa.fir:instances;

import :node;

export namespace fir
{

// --- M1 value kinds ---

enum class ValueKind : uint8_t {
    Integer,
    Float,
    String,
    Boolean,
    Null,
    Reference,
    InstanceRef,
};

// --- Structured reference path segments ---

enum class PathSegmentKind : uint8_t {
    Id,
    // Future: Filter, ArchetypeNav, etc.
};

struct PathSegment {
    PathSegmentKind kind;
    Id value;    // -> ValueDef or ObjectDef (typed identity value)
};

// --- M1 instance node ---

struct ObjectDef : Node {
    Id       type_id;
    StringId identity;
    uint32_t prop_start = 0;
    uint16_t prop_count = 0;
    Id       derived_from = Id{UINT32_MAX};

    ObjectDef(Id type_id, StringId identity)
        : Node{NodeKind::ObjectDef}, type_id(type_id), identity(identity) {}
};

// --- M1 role assignment ---

struct PropertyVal : Node {
    Id role_id;
    Id value_id;

    PropertyVal(Id role_id, Id value_id)
        : Node{NodeKind::PropertyVal}, role_id(role_id), value_id(value_id) {}
};

// --- M1 leaf value ---

struct ValueDef : Node {
    ValueKind value_kind;
    union {
        int64_t  int_val;
        double   float_val;
        bool     bool_val;
        StringId string_val;
    };
    uint32_t segment_start = 0;
    uint16_t segment_count = 0;
    Id       ref_target = Id{UINT32_MAX};

    // Integer
    ValueDef(ValueKind vk, int64_t v)
        : Node{NodeKind::ValueDef}, value_kind(vk), int_val(v) {}

    // Float
    ValueDef(ValueKind vk, double v)
        : Node{NodeKind::ValueDef}, value_kind(vk), float_val(v) {}

    // String (also used for null reference path text)
    ValueDef(ValueKind vk, StringId v)
        : Node{NodeKind::ValueDef}, value_kind(vk), string_val(v) {}

    // Boolean
    ValueDef(ValueKind vk, bool v)
        : Node{NodeKind::ValueDef}, value_kind(vk), bool_val(v) {}

    // Reference (no initial value — segments set after construction)
    explicit ValueDef(ValueKind vk)
        : Node{NodeKind::ValueDef}, value_kind(vk), int_val(0) {}
};

}  // namespace fir
```

**Step 5: Add import and secondary tables to Fir class**

Modify `external/rupa/src/fir/rupa.fir.cppm`:

Add to exports (after line 13 `export import :types;`):
```cpp
export import :instances;
```

Add new private members (after `role_ids_` on line 26):
```cpp
    std::vector<Id>          property_ids_;
    std::vector<PathSegment> path_segments_;
```

Add new public methods (after `rolesOf` on line 126):
```cpp
    // --- Property secondary table ---

    uint32_t appendProperties(std::span<const Id> ids) {
        auto start = static_cast<uint32_t>(property_ids_.size());
        property_ids_.insert(property_ids_.end(), ids.begin(), ids.end());
        return start;
    }

    std::span<const Id> propertiesOf(const ObjectDef& obj) const {
        if (obj.prop_count == 0) return {};
        return {property_ids_.data() + obj.prop_start, obj.prop_count};
    }

    // --- Path segment secondary table ---

    uint32_t appendPathSegments(std::span<const PathSegment> segs) {
        auto start = static_cast<uint32_t>(path_segments_.size());
        path_segments_.insert(path_segments_.end(), segs.begin(), segs.end());
        return start;
    }

    std::span<const PathSegment> pathSegments(uint32_t start, uint16_t count) const {
        if (count == 0) return {};
        return {path_segments_.data() + start, count};
    }
```

**Step 6: Register new module in CMakeLists.txt**

Add `rupa.fir-instances.cppm` to the FIR library's module sources in `external/rupa/src/fir/CMakeLists.txt`.

**Step 7: Run tests to verify they pass**

Run: `cd external/rupa && cmake --preset debug && cmake --build --preset debug --target fir-instance-test && ctest --test-dir build-debug -R fir-instance -V`
Expected: All 8 tests PASS.

**Step 8: Commit**

```bash
cd external/rupa
git add src/fir/rupa.fir-node.cppm src/fir/rupa.fir-instances.cppm src/fir/rupa.fir.cppm src/fir/CMakeLists.txt test/fir/fir-instance-test.cpp test/fir/CMakeLists.txt
git commit -m "feat(fir): add M1 node types — ObjectDef, PropertyVal, ValueDef, PathSegment"
```

---

## Batch 2: New Diagnostics + Basic Instance Lowering (= assignment)

### Task 2: Add M1 diagnostic kinds

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-context.cppm:17-26`

**Step 1: Add new diagnostic kinds**

Add to `SemaDiagnosticKind` enum after `UnsupportedExpression` (line 25):

```cpp
    UnresolvedRoleName,
    DuplicateIdentity,
    TypeMismatch,
    MultiplicityViolation,
    UnresolvedReference,
```

**Step 2: Build to verify compilation**

Run: `cd external/rupa && cmake --build --preset debug 2>&1 | tail -10`
Expected: Clean compilation (enum extension is backward-compatible).

**Step 3: Commit**

```bash
cd external/rupa
git add src/sema/rupa.sema-context.cppm
git commit -m "feat(sema): add M1 diagnostic kinds for instance lowering"
```

### Task 3: Create instance lowering module (Phase C)

**Files:**
- Create: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Modify: `external/rupa/src/sema/rupa.sema-driver.cppm:16-17,61-62`
- Modify: `external/rupa/src/sema/CMakeLists.txt`
- Test: `external/rupa/test/sema/sema-instance-test.cpp`

**Step 1: Write the failing test — basic named instantiation with = assignment**

Create `external/rupa/test/sema/sema-instance-test.cpp`:

```cpp
#include <gtest/gtest.h>
#include <filesystem>
#include <fstream>

import rupa.sema;
import rupa.fir;

namespace fs = std::filesystem;

class InstanceTest : public ::testing::Test {
protected:
    fs::path tmp_dir_;

    void SetUp() override {
        tmp_dir_ = fs::temp_directory_path() / "rupa-instance-test";
        fs::create_directories(tmp_dir_);
    }

    void TearDown() override {
        fs::remove_all(tmp_dir_);
    }

    void write_file(const std::string& name, const std::string& content) {
        std::ofstream f(tmp_dir_ / name);
        f << content;
    }

    rupa::sema::SemaResult compile(const std::string& source) {
        write_file("test.rupa", source);
        rupa::sema::CompilationDriver driver;
        return driver.compile(tmp_dir_ / "test.rupa");
    }
};

TEST_F(InstanceTest, BasicNamedInstantiation) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal Pressure {
            .length = 16;
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 1u);
}

TEST_F(InstanceTest, AnonymousInstantiation) {
    auto result = compile(R"(
        type AdminData = {
            .language : ::string;
        };
        AdminData {
            .language = "EN";
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 1u);
}

TEST_F(InstanceTest, StringIdentity) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal "Amb-Temp" {
            .length = 8;
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 1u);
}

TEST_F(InstanceTest, IntegerAssignment) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal Pressure {
            .length = 16;
        };
    )");
    EXPECT_FALSE(result.hasErrors());

    // Find the ObjectDef and verify its property
    fir::Id obj_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) obj_id = id;
    });
    auto& obj = result.fir->as<fir::ObjectDef>(obj_id);
    EXPECT_EQ(obj.prop_count, 1u);

    auto props = result.fir->propertiesOf(obj);
    auto& prop = result.fir->as<fir::PropertyVal>(props[0]);
    auto& val = result.fir->as<fir::ValueDef>(prop.value_id);
    EXPECT_EQ(val.value_kind, fir::ValueKind::Integer);
    EXPECT_EQ(val.int_val, 16);
}

TEST_F(InstanceTest, StringAssignment) {
    auto result = compile(R"(
        type AdminData = {
            .language : ::string;
        };
        AdminData {
            .language = "EN";
        };
    )");
    EXPECT_FALSE(result.hasErrors());

    fir::Id obj_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) obj_id = id;
    });
    auto& obj = result.fir->as<fir::ObjectDef>(obj_id);
    auto props = result.fir->propertiesOf(obj);
    auto& prop = result.fir->as<fir::PropertyVal>(props[0]);
    auto& val = result.fir->as<fir::ValueDef>(prop.value_id);
    EXPECT_EQ(val.value_kind, fir::ValueKind::String);
    EXPECT_EQ(result.fir->getString(val.string_val), "EN");
}

TEST_F(InstanceTest, BooleanAssignment) {
    auto result = compile(R"(
        type Config = {
            .enabled : ::boolean;
        };
        Config Settings {
            .enabled = true;
        };
    )");
    EXPECT_FALSE(result.hasErrors());

    fir::Id obj_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) obj_id = id;
    });
    auto& obj = result.fir->as<fir::ObjectDef>(obj_id);
    auto props = result.fir->propertiesOf(obj);
    auto& prop = result.fir->as<fir::PropertyVal>(props[0]);
    auto& val = result.fir->as<fir::ValueDef>(prop.value_id);
    EXPECT_EQ(val.value_kind, fir::ValueKind::Boolean);
    EXPECT_TRUE(val.bool_val);
}

TEST_F(InstanceTest, FloatAssignment) {
    auto result = compile(R"(
        type Measurement = {
            .value : ::float;
        };
        Measurement Temp {
            .value = 3.14;
        };
    )");
    EXPECT_FALSE(result.hasErrors());

    fir::Id obj_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) obj_id = id;
    });
    auto& obj = result.fir->as<fir::ObjectDef>(obj_id);
    auto props = result.fir->propertiesOf(obj);
    auto& prop = result.fir->as<fir::PropertyVal>(props[0]);
    auto& val = result.fir->as<fir::ValueDef>(prop.value_id);
    EXPECT_EQ(val.value_kind, fir::ValueKind::Float);
    EXPECT_DOUBLE_EQ(val.float_val, 3.14);
}

TEST_F(InstanceTest, MultipleProperties) {
    auto result = compile(R"(
        type Signal = {
            .name : ::string;
            .length : ::integer;
        };
        Signal Pressure {
            .name = "Pressure";
            .length = 16;
        };
    )");
    EXPECT_FALSE(result.hasErrors());

    fir::Id obj_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) obj_id = id;
    });
    auto& obj = result.fir->as<fir::ObjectDef>(obj_id);
    EXPECT_EQ(obj.prop_count, 2u);
}

TEST_F(InstanceTest, NestedInstantiation) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        type Package = {
            .signals : Signal*;
        };
        Package Messaging {
            .signals += Signal Speed {
                .length = 16;
            };
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 2u);
}

TEST_F(InstanceTest, UnresolvedTypeError) {
    auto result = compile(R"(
        NonExistent Foo {
        };
    )");
    EXPECT_TRUE(result.hasErrors());
    bool found = false;
    for (auto& d : result.diagnostics) {
        if (d.kind == rupa::sema::SemaDiagnosticKind::UnresolvedTypeName)
            found = true;
    }
    EXPECT_TRUE(found);
}

TEST_F(InstanceTest, UnresolvedRoleError) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal Pressure {
            .nonexistent = 42;
        };
    )");
    EXPECT_TRUE(result.hasErrors());
    bool found = false;
    for (auto& d : result.diagnostics) {
        if (d.kind == rupa::sema::SemaDiagnosticKind::UnresolvedRoleName)
            found = true;
    }
    EXPECT_TRUE(found);
}

TEST_F(InstanceTest, ReferenceValue) {
    auto result = compile(R"(
        type SwComponentType = {
            .name : ::string;
        };
        type SwComponentPrototype = {
            .type : SwComponentType;
        };
        SwComponentType SensorSWC {
            .name = "Sensor";
        };
        SwComponentPrototype Sensor {
            .type = /SensorSWC;
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 2u);

    // Find the prototype's property and verify it's a reference
    bool found_ref = false;
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ValueDef) {
            auto& val = static_cast<const fir::ValueDef&>(node);
            if (val.value_kind == fir::ValueKind::Reference) {
                found_ref = true;
                auto segs = result.fir->pathSegments(val.segment_start, val.segment_count);
                EXPECT_EQ(segs.size(), 1u);
            }
        }
    });
    EXPECT_TRUE(found_ref);
}

TEST_F(InstanceTest, UnsupportedExpressionWarning) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal Pressure {
            .length = 8 + 8;
        };
    )");
    // Should warn, not error — the unsupported expression is skipped
    bool found_warning = false;
    for (auto& d : result.diagnostics) {
        if (d.kind == rupa::sema::SemaDiagnosticKind::UnsupportedExpression
            && d.severity == rupa::sema::SemaSeverity::Warning)
            found_warning = true;
    }
    EXPECT_TRUE(found_warning);
}
```

Register in `external/rupa/test/sema/CMakeLists.txt`.

**Step 2: Run test to verify it fails**

Run: `cd external/rupa && cmake --build --preset debug --target sema-instance-test 2>&1 | tail -20`
Expected: Compilation failure — `lower_instances` not found.

**Step 3: Create the instance lowering module**

Create `external/rupa/src/sema/rupa.sema-lower-instances.cppm`:

This module implements Phase C. Key logic:

1. **`lower_instances()`** — entry point. Walks SourceFile AST statements, finds Instantiation nodes, dispatches to `lower_instantiation()`.

2. **`lower_instantiation()`** — resolves type_ref to a TypeDef, extracts identity, creates ObjectDef, processes block statements.

3. **`lower_assignment()`** — resolves role name from LHS (a PathExpr starting with `.`), evaluates RHS expression, creates PropertyVal + ValueDef.

4. **`eval_expr()`** — limited expression evaluator:
   - `IdentifierExpr` with text matching `true`/`false` → boolean ValueDef
   - `IdentifierExpr` with numeric text → integer ValueDef (via `std::from_chars`)
   - `LiteralExpr` (string) → string ValueDef
   - `PathExpr` starting with `/` → reference ValueDef with IdSegment path segments
   - Multi-token float (path expression that parses as float via `node->range()`) → float ValueDef
   - Anything else → `UnsupportedExpression` warning, return null

5. **`resolve_role()`** — given a TypeDef and a role name (from `.name` LHS), search the type's roles for a match. Returns RoleDef Id or emits `UnresolvedRoleName`.

The function signature:

```cpp
void lower_instances(
    const rupa::parser::AstNode* root,
    fir::Fir& fir,
    const kore::FrozenMap<fir::StringId, fir::Id>& type_names,
    std::string_view source,
    std::string_view file_path,
    std::vector<SemaDiagnostic>& diagnostics);
```

**Important:** Reuse the numeric extraction patterns from `rupa.sema-lower-types.cppm` (lines 200-257) — `try_extract_int_literal` for integers via IdentifierExpr, and source-range `from_chars` for floats. See `docs/plans/2026-02-25-fir-type-system-continuation.md` for the multi-token literal problem details.

**Step 4: Integrate into the compilation driver**

Modify `external/rupa/src/sema/rupa.sema-driver.cppm`:

Add import (after line 17 `import :lower_types;`):
```cpp
import :lower_instances;
```

In `compile()` method, after `resolve_types_with_pool` (after line 61), add Phase C:
```cpp
        // Phase C: lower instances
        for (auto& entry : file_cache_) {
            if (entry.second.status != FileStatus::Done) continue;
            auto* root = entry.second.parse_result.root;
            auto source_view = std::string_view(*/* find source for entry */);
            lower_instances(root, *fir_, type_names_, source_view,
                           entry.second.canonical_path, diagnostics_);
        }
```

Note: The driver must iterate over all processed files and call `lower_instances` for each. The source text is available from `source_storage_` — the driver needs a way to map FileEntry back to its source. Add a `std::string_view source` field to `FileEntry` or store it alongside the canonical path.

**Step 5: Register module in CMakeLists.txt**

Add `rupa.sema-lower-instances.cppm` to sema library sources in `external/rupa/src/sema/CMakeLists.txt`.

**Step 6: Run tests to verify they pass**

Run: `cd external/rupa && cmake --preset debug && cmake --build --preset debug --target sema-instance-test && ctest --test-dir build-debug -R sema-instance -V`
Expected: All 13 tests PASS.

**Step 7: Run all existing tests to verify no regressions**

Run: `cd external/rupa && cmake --build --preset debug && ctest --test-dir build-debug -V`
Expected: All tests PASS (existing sema and parser tests unaffected).

**Step 8: Commit**

```bash
cd external/rupa
git add src/sema/rupa.sema-lower-instances.cppm src/sema/rupa.sema-driver.cppm src/sema/CMakeLists.txt test/sema/sema-instance-test.cpp test/sema/CMakeLists.txt
git commit -m "feat(sema): add Phase C instance lowering with = assignment"
```

---

## Batch 3: += Assignment with Identity-Merge

### Task 4: Implement += add semantics

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Test: `external/rupa/test/sema/sema-instance-test.cpp` (add tests)

**Step 1: Write failing tests for += semantics**

Add to `sema-instance-test.cpp`:

```cpp
TEST_F(InstanceTest, PlusEqualSingleValuedEmptyRole) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal Pressure {
            .length += 16;
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    // += on empty single-valued role → set the value
    fir::Id obj_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) obj_id = id;
    });
    auto& obj = result.fir->as<fir::ObjectDef>(obj_id);
    EXPECT_EQ(obj.prop_count, 1u);
}

TEST_F(InstanceTest, PlusEqualMultiValuedAddsElements) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        type Package = {
            .signals : Signal*;
        };
        Package Messaging {
            .signals += Signal Speed { .length = 16; };
            .signals += Signal Brake { .length = 12; };
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    // Two Signal objects + one Package
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 3u);
}

TEST_F(InstanceTest, PlusEqualIdentityMerge) {
    auto result = compile(R"(
        type Signal = {
            .name : ::string;
            .length : ::integer;
        };
        type Package = {
            .signals : Signal*;
        };
        Package Messaging {
            .signals += Signal Speed {
                .name = "VehicleSpeed";
            };
            .signals += Signal Speed {
                .length = 16;
            };
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    // Identity merge: one Package + one Signal (Speed merged)
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 2u);

    // The merged Signal should have 2 properties
    fir::Id signal_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) {
            auto& obj = static_cast<const fir::ObjectDef&>(node);
            if (result.fir->getString(obj.identity) == "Speed")
                signal_id = id;
        }
    });
    auto& sig = result.fir->as<fir::ObjectDef>(signal_id);
    EXPECT_EQ(sig.prop_count, 2u);
}

TEST_F(InstanceTest, PlusEqualTopLevelMerge) {
    // RUPA-MOD-019: writing same identity twice reopens existing
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        type Package = {
            .signals : Signal*;
        };
        Package Messaging {
            .signals += Signal Speed { .length = 16; };
        };
        Package Messaging {
            .signals += Signal Brake { .length = 12; };
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    // One Package (Messaging merged), two Signals
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 3u);
}
```

**Step 2: Run to verify failures**

Run: `cd external/rupa && cmake --build --preset debug --target sema-instance-test && ctest --test-dir build-debug -R sema-instance -V`
Expected: New tests FAIL (identity-merge not yet implemented).

**Step 3: Implement += in lower_instances**

Extend the assignment handler in `rupa.sema-lower-instances.cppm`:

- For `TK::PlusEqual`:
  1. Check if the role is single-valued (Multiplicity::One or Optional):
     - If role empty → set value (same as `=`)
     - If role occupied and value is identifiable with same identity → merge (reopen)
     - Otherwise → `MultiplicityViolation` error
  2. Check if the role is multi-valued (Many or OneOrMore):
     - If value is identifiable and same identity exists → merge
     - Otherwise → append to collection

- **Identity matching:** When the RHS is an Instantiation with an identity, look up existing PropertyVal entries for the same role. Compare identities (string comparison of `ObjectDef.identity`).

- **Top-level merge:** When encountering a top-level Instantiation with the same type+identity as an existing ObjectDef, reopen it (add properties to existing ObjectDef rather than creating a new one). Maintain a lookup map `(TypeId, identity_string) → ObjectDef Id` during Phase C.

**Step 4: Run tests**

Run: `cd external/rupa && cmake --build --preset debug --target sema-instance-test && ctest --test-dir build-debug -R sema-instance -V`
Expected: All tests PASS.

**Step 5: Commit**

```bash
cd external/rupa
git add src/sema/rupa.sema-lower-instances.cppm test/sema/sema-instance-test.cpp
git commit -m "feat(sema): implement += assignment with identity-merge"
```

---

## Batch 4: |= Create-and-Merge + = _ Reset

### Task 5: Implement |= and = _ operators

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Test: `external/rupa/test/sema/sema-instance-test.cpp` (add tests)

**Step 1: Write failing tests**

```cpp
TEST_F(InstanceTest, PipeEqualCreateAndMerge) {
    auto result = compile(R"(
        type Signal = {
            .name : ::string;
            .length : ::integer;
        };
        type Package = {
            .signals : Signal*;
        };
        Package Messaging {
            .signals |= Signal Speed {
                .name = "VehicleSpeed";
            };
            .signals |= Signal Speed {
                .length = 16;
            };
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    // |= merges same identity
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 2u);
}

TEST_F(InstanceTest, ResetAssignmentOptionalRole) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer?;
        };
        Signal Pressure {
            .length = 16;
            .length = _;
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    // After reset, the optional role should have no value
    fir::Id obj_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) obj_id = id;
    });
    auto& obj = result.fir->as<fir::ObjectDef>(obj_id);
    EXPECT_EQ(obj.prop_count, 0u);
}

TEST_F(InstanceTest, ResetAssignmentOneOrMoreError) {
    auto result = compile(R"(
        type Package = {
            .signals : ::string+;
        };
        Package Messaging {
            .signals = _;
        };
    )");
    // RUPA-MOD-102: reset on 1+ role is compile error
    bool found = false;
    for (auto& d : result.diagnostics) {
        if (d.kind == rupa::sema::SemaDiagnosticKind::MultiplicityViolation)
            found = true;
    }
    EXPECT_TRUE(found);
}
```

**Step 2: Implement |= and = _**

- `|=`: Same as `+=` but creates the object if it doesn't exist yet. Semantically equivalent to `+=` for initial creation, with merge on same identity.
- `= _` (ResetAssignment AST node): Remove all PropertyVal entries for the given role on the current object. Error if role is OneOrMore (RUPA-MOD-102) or required composite (RUPA-MOD-103).

**Step 3-5: Run tests, verify, commit**

```bash
git commit -m "feat(sema): implement |= create-and-merge and = _ reset operators"
```

---

## Batch 5: Object Derivation (from)

### Task 6: Implement from derivation

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Test: `external/rupa/test/sema/sema-instance-test.cpp` (add tests)

**Step 1: Write failing tests**

```cpp
TEST_F(InstanceTest, FromDerivationCopiesProperties) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
            .value : ::integer;
        };
        Signal Base {
            .length = 16;
            .value = 0;
        };
        Signal Extended from /Base {
            .value = 42;
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 2u);

    // Extended should have 2 properties: .length copied from Base, .value overridden
    fir::Id ext_id{0};
    result.fir->forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) {
            auto& obj = static_cast<const fir::ObjectDef&>(node);
            if (result.fir->getString(obj.identity) == "Extended")
                ext_id = id;
        }
    });
    auto& ext = result.fir->as<fir::ObjectDef>(ext_id);
    EXPECT_EQ(ext.prop_count, 2u);
    EXPECT_NE(static_cast<uint32_t>(ext.derived_from), UINT32_MAX);
}

TEST_F(InstanceTest, AnonymousDerivation) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal Base {
            .length = 16;
        };
        Signal from /Base {
            .length = 32;
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 2u);
}
```

**Step 2: Implement from derivation**

When an Instantiation has a non-null `derivation()`:
1. Evaluate the derivation path expression to find the source ObjectDef
2. Create a new ObjectDef with the given identity
3. Set `derived_from` to the source ObjectDef Id
4. Copy all PropertyVal entries from the source to the new object (deep copy for containment, shallow for references — per RUPA-MOD-030)
5. Process the block to override/add properties

**Step 3-5: Run tests, verify, commit**

```bash
git commit -m "feat(sema): implement from derivation with property copying"
```

---

## Batch 6: Type-Inferred Blocks

### Task 7: Implement type inference for bare blocks

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Test: `external/rupa/test/sema/sema-instance-test.cpp` (add tests)

**Step 1: Write failing tests**

```cpp
TEST_F(InstanceTest, TypeInferredFromRole) {
    // RUPA-MOD-005: bare block infers type from role
    auto result = compile(R"(
        type Config = {
            .mode : ::string;
            .timeout : ::integer;
        };
        type Service = {
            .config : Config;
        };
        Service MyService {
            .config = {
                .mode = "active";
                .timeout = 30;
            };
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 2u);
}

TEST_F(InstanceTest, TypeInferredAbstractError) {
    // RUPA-MOD-007: abstract type cannot be inferred
    auto result = compile(R"(
        #[abstract]
        type Base = {
            .value : ::integer;
        };
        type Container = {
            .item : Base;
        };
        Container C {
            .item = {
                .value = 42;
            };
        };
    )");
    EXPECT_TRUE(result.hasErrors());
}
```

**Step 2: Implement type inference**

When processing `.role = { block }` and the RHS is a bare Block (not an Instantiation with a type_ref):
1. Look up the role's target_type from the RoleDef
2. If the target type is abstract → error (RUPA-MOD-007)
3. Otherwise, create an ObjectDef with the inferred type (anonymous, no identity)
4. Process the block as usual

**Step 3-5: Run tests, verify, commit**

```bash
git commit -m "feat(sema): implement type-inferred blocks for role assignments"
```

---

## Batch 7: Multiplicity Validation + Unresolved Reference Warning

### Task 8: Post-lowering validation

**Files:**
- Modify: `external/rupa/src/sema/rupa.sema-lower-instances.cppm`
- Test: `external/rupa/test/sema/sema-instance-test.cpp` (add tests)

**Step 1: Write failing tests**

```cpp
TEST_F(InstanceTest, MaxMultiplicityViolation) {
    auto result = compile(R"(
        type Signal = {
            .length : ::integer;
        };
        Signal Pressure {
            .length = 16;
            .length += 32;
        };
    )");
    // Single-valued role already set, += should error
    bool found = false;
    for (auto& d : result.diagnostics) {
        if (d.kind == rupa::sema::SemaDiagnosticKind::MultiplicityViolation)
            found = true;
    }
    EXPECT_TRUE(found);
}

TEST_F(InstanceTest, UnresolvedReferenceWarning) {
    auto result = compile(R"(
        type SwComponentType = {
            .name : ::string;
        };
        type SwComponentPrototype = {
            .type : SwComponentType;
        };
        SwComponentPrototype Sensor {
            .type = /NonExistent;
        };
    )");
    // Should warn about unresolved reference
    bool found = false;
    for (auto& d : result.diagnostics) {
        if (d.kind == rupa::sema::SemaDiagnosticKind::UnresolvedReference)
            found = true;
    }
    EXPECT_TRUE(found);
}
```

**Step 2: Implement post-lowering validation**

After all instantiations are processed:
1. **Max multiplicity check:** During `+=` operations, track how many values have been assigned to each role. If exceeding `Multiplicity::One` or `Optional`, emit `MultiplicityViolation`.
2. **Unresolved reference scan:** Walk all ValueDef nodes with `value_kind == Reference`. For each, check if any ObjectDef exists with a matching identity path. If not, emit `UnresolvedReference` warning.

Note: Min multiplicity is NOT checked at this stage (RUPA-MOD-090 says it's checked at domain freeze, not per-statement).

**Step 3-5: Run tests, verify, commit**

```bash
git commit -m "feat(sema): add multiplicity validation and unresolved reference warnings"
```

---

## Batch 8: Binary Serialization for M1 Nodes

### Task 9: Extend FIR serialization format

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-serial.cppm`
- Test: `external/rupa/test/fir/fir-serial-test.cpp` (add tests)

**Step 1: Write failing test**

```cpp
TEST(FirSerial, RoundTripWithInstances) {
    Fir fir;
    auto str_name = fir.intern("::string");
    auto str_type = fir.add<TypeDef>(str_name, M3Kind::Primitive);
    auto int_name = fir.intern("::integer");
    auto int_type = fir.add<TypeDef>(int_name, M3Kind::Primitive);

    auto sig_name = fir.intern("Signal");
    auto sig_type = fir.add<TypeDef>(sig_name, M3Kind::Composite);

    auto role_name = fir.intern("length");
    auto role_id = fir.add<RoleDef>(role_name, int_type, Multiplicity::One, false);

    auto val_id = fir.add<ValueDef>(ValueKind::Integer, int64_t{16});
    auto prop_id = fir.add<PropertyVal>(role_id, val_id);

    auto identity = fir.intern("Pressure");
    auto obj_id = fir.add<ObjectDef>(sig_type, identity);
    Id prop_ids[] = {prop_id};
    fir.as<ObjectDef>(obj_id).prop_start = fir.appendProperties(prop_ids);
    fir.as<ObjectDef>(obj_id).prop_count = 1;

    // Serialize
    auto bytes = serialize(fir);

    // Deserialize
    auto result = deserialize(bytes);
    ASSERT_TRUE(result.has_value());
    auto& fir2 = *result.value();

    EXPECT_EQ(fir2.countByKind(NodeKind::ObjectDef), 1u);
    EXPECT_EQ(fir2.countByKind(NodeKind::PropertyVal), 1u);
    EXPECT_EQ(fir2.countByKind(NodeKind::ValueDef), 1u);
}
```

**Step 2: Extend serialization**

Modify `external/rupa/src/fir/rupa.fir-serial.cppm`:

- Bump `kFormatVersion` from 2 to 3
- Extend `kHeaderSize` from 80 to 120 (5 new table pairs: ObjectDef, PropertyVal, ValueDef, PathSegments, PropertyIDs = 40 bytes)
- In `serialize()`:
  - Intern strings from ObjectDef identities and string ValueDefs
  - Write ObjectDef records: kind(1) + type_id(4) + identity(4) + prop_start(4) + prop_count(2) + derived_from(4) = 19 bytes
  - Write PropertyVal records: kind(1) + role_id(4) + value_id(4) = 9 bytes
  - Write ValueDef records: kind(1) + value_kind(1) + value_data(8) + segment_start(4) + segment_count(2) + ref_target(4) = 20 bytes
  - Write PathSegment table: kind(1) + value_id(4) = 5 bytes per entry
  - Write Property IDs table: uint32_t per entry
  - Patch new header offsets
- In `deserialize()`:
  - Read new header fields (gracefully handle v2 files by checking version)
  - Reconstruct ObjectDef, PropertyVal, ValueDef nodes
  - Rebuild secondary tables

**Step 3-5: Run tests, verify, commit**

```bash
git commit -m "feat(fir): extend binary serialization for M1 instance nodes (format v3)"
```

---

## Batch 9: Explorer API + UI for Instances

### Task 10: Add instance API endpoints

**Files:**
- Modify: `external/rupa/src/cli/rupa.cli-serve.cppm`
- Test: Manual verification via browser

**Step 1: Add /api/objects endpoint**

In `register_routes()`, add:

```cpp
// GET /api/objects — list all ObjectDef instances
// Response: [{id, type_name, identity, prop_count}]

// GET /api/objects/:id — full ObjectDef with properties
// Response: {id, type_name, identity, derived_from, properties: [{role_name, value}]}

// GET /api/types/:id/instances — all instances of a type
// Response: [{id, identity, prop_count}]
```

Extend `/api/stats` to include `object_count`, `property_count`, `value_count`.

**Step 2: Add value serialization helpers**

```cpp
// Serialize a ValueDef to JSON
// Integer: {"kind":"integer","value":42}
// Float: {"kind":"float","value":3.14}
// String: {"kind":"string","value":"hello"}
// Boolean: {"kind":"boolean","value":true}
// Reference: {"kind":"reference","path":["Components","SensorSWC"]}
```

**Step 3: Commit**

```bash
git commit -m "feat(cli): add instance API endpoints to explorer"
```

### Task 11: Add Instances tab to explorer UI

**Files:**
- Modify: `external/rupa/src/cli/web/explorer.html`

**Step 1: Add tab switching and instance list**

Add an "Instances" tab next to "Types". When selected:
- Fetch `/api/objects`
- Group by type name
- Display as expandable tree: type → instances → properties

**Step 2: Add property value display**

Render property values based on kind:
- Integers/floats as numbers
- Strings in quotes
- Booleans as true/false
- References as clickable paths
- Nested objects as expandable sub-trees

**Step 3: Commit**

```bash
git commit -m "feat(cli): add Instances tab to explorer UI"
```

---

## Batch 10: End-to-End Verification

### Task 12: AUTOSAR M1 data test

**Files:**
- Create: `external/rupa/test/sema/autosar-instance-test.rupa` (test fixture)
- Test: `external/rupa/test/sema/sema-instance-test.cpp` (add test)

**Step 1: Write an AUTOSAR-realistic test**

```cpp
TEST_F(InstanceTest, AutosarEndToEnd) {
    auto result = compile(R"(
        // M2 types (simplified AUTOSAR)
        type ShortName = ::string;
        type SwComponentType = {
            #[id] .shortName : ShortName;
            .ports : PortPrototype*;
        };
        type SwComponentPrototype = {
            #[id] .shortName : ShortName;
            .type : SwComponentType;
        };
        type PortPrototype = {
            #[id] .shortName : ShortName;
        };
        type CompositionSwComponentType = SwComponentType {
            .components : SwComponentPrototype*;
        };

        // M1 instances
        SwComponentType SensorSWC {
            .shortName = "SensorSWC";
            .ports += PortPrototype SpeedPort {
                .shortName = "SpeedPort";
            };
        };

        CompositionSwComponentType VehicleControl {
            .shortName = "VehicleControl";
            .components += SwComponentPrototype Sensor {
                .shortName = "Sensor";
                .type = /SensorSWC;
            };
        };
    )");
    EXPECT_FALSE(result.hasErrors());
    // 3 objects: SensorSWC, SpeedPort, VehicleControl, Sensor
    EXPECT_EQ(result.fir->countByKind(fir::NodeKind::ObjectDef), 4u);
}
```

**Step 2: Run full test suite**

Run: `cd external/rupa && cmake --build --preset debug && ctest --test-dir build-debug -V`
Expected: All tests PASS.

**Step 3: Manual explorer verification**

```bash
cd external/rupa
./build-debug/rupa serve test/sema/autosar-instance-test.fir -o
```

Verify in browser: Types tab shows M2 types, Instances tab shows M1 objects with properties.

**Step 4: Commit**

```bash
git commit -m "test(sema): add AUTOSAR end-to-end instance test"
```

### Task 13: Run all tests and final cleanup

**Step 1: Full regression test**

Run: `cd external/rupa && cmake --build --preset debug && ctest --test-dir build-debug -V`
Expected: All tests PASS.

**Step 2: Commit any cleanup**

```bash
git commit -m "chore: cleanup after model instances implementation"
```

---

## Summary

| Batch | Tasks | Focus |
|-------|-------|-------|
| 1 | 1 | FIR M1 node types + secondary tables |
| 2 | 2-3 | Diagnostics + Phase C with basic = assignment |
| 3 | 4 | += with identity-merge |
| 4 | 5 | |= and = _ operators |
| 5 | 6 | from derivation |
| 6 | 7 | Type-inferred blocks |
| 7 | 8 | Multiplicity validation + unresolved ref warnings |
| 8 | 9 | Binary serialization v3 |
| 9 | 10-11 | Explorer API + UI |
| 10 | 12-13 | End-to-end + cleanup |

Each batch is independently completable. Stop at any checkpoint and resume with this plan file.
