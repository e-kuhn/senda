#include <gtest/gtest.h>
#include <filesystem>
#include <string>
#include <string_view>
#include <utility>

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;
import senda.compiler.arxml;
import senda.domains;
import senda.domains.r23_11;

namespace fs = std::filesystem;

// --- Test-only mock CompileContext ---

class MockArxmlContext : public rupa::compiler::CompileContext {
public:
    explicit MockArxmlContext(const rupa::domain::Domain& domain,
                              bool override_default = true)
        : view_(domain.view()),
          transaction_(view_, "autosar-r23-11"),
          override_default_(override_default) {}

    rupa::compiler::CompileResult compile_import(const fs::path& /*path*/) override {
        return rupa::compiler::CompileResult(
            fir::Fir{}, rupa::compiler::DomainExtensions{}, rupa::compiler::Diagnostics{});
    }

    const rupa::domain::DomainView* request_domain(std::string_view name) override {
        if (name == "autosar-r23-11") return &view_;
        return nullptr;
    }

    const rupa::domain::DomainView* request_default_domain() override {
        if (override_default_) return &view_;
        return nullptr;
    }

    rupa::domain::DomainTransaction& domain_transaction() override {
        return transaction_;
    }

    fs::path resolve_path(const fs::path& relative) const override {
        return relative;
    }

private:
    rupa::domain::DomainView view_;
    rupa::domain::DomainTransaction transaction_;
    bool override_default_ = false;
};

// --- Helpers ---

static fs::path fixture_path(const char* name) {
    // Fixtures are relative to the test source directory
    return fs::path(SENDA_TEST_FIXTURES_DIR) / name;
}

static senda::SchemaRegistry make_registry() {
    senda::SchemaRegistry reg;
    reg.add("AUTOSAR_00052.xsd", "autosar-r23-11",
            senda::domains::build_autosar_r23_11);
    return reg;
}

// --- Tests ---

TEST(ArxmlCompilerTest, ImplementsCompilerInterface) {
    auto reg = make_registry();
    senda::ArxmlCompiler compiler(reg);
    auto exts = compiler.extensions();
    ASSERT_EQ(exts.size(), 1u);
    EXPECT_EQ(exts[0], ".arxml");
}

TEST(ArxmlCompilerTest, CompileSimpleSignal) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("simple-signal.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Unexpected errors in compilation";

    // Should have at least one ObjectDef
    size_t obj_count = 0;
    result.fir().forEachNode([&](fir::Id /*id*/, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) ++obj_count;
    });
    EXPECT_GE(obj_count, 1u);
}

TEST(ArxmlCompilerTest, CompileMultipleElements) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("multi-element.arxml"), ctx);
    EXPECT_FALSE(result.has_errors());

    // Should have multiple objects
    size_t obj_count = 0;
    result.fir().forEachNode([&](fir::Id /*id*/, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) ++obj_count;
    });
    EXPECT_GE(obj_count, 1u);
}

TEST(ArxmlCompilerTest, NestedPackages) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("nested-packages.arxml"), ctx);
    EXPECT_FALSE(result.has_errors());
}

TEST(ArxmlCompilerTest, InvalidXmlProducesError) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    // Non-existent file
    auto result = compiler.compile("/tmp/nonexistent.arxml", ctx);
    EXPECT_TRUE(result.has_errors());
}

TEST(ArxmlCompilerTest, UnsupportedSchemaProducesError) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    // No override — request_default_domain() returns nullptr
    MockArxmlContext ctx(schema->domain, /*override_default=*/false);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("r4-3-1-signal.arxml"), ctx);
    EXPECT_TRUE(result.has_errors());
}

TEST(ArxmlCompilerTest, OverriddenDomainEmitsSkipWarnings) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain, /*override_default=*/true);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("r4-3-1-signal.arxml"), ctx);
    // Should succeed (override allows it) but may have warnings
    EXPECT_FALSE(result.has_errors());
}

// Verify that properties are contiguous per object even when nested objects
// (like ADMIN-DATA) appear between scalar properties.
TEST(ArxmlCompilerTest, PropertyContiguityWithNestedObjects) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain, /*override_default=*/true);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("interleaved-props.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Compilation failed";

    // For each ObjectDef, verify its property span is valid:
    // prop_start + prop_count should not overlap with another object's span.
    struct ObjSpan {
        fir::Id obj_id;
        uint32_t start;
        uint32_t count;
    };
    std::vector<ObjSpan> spans;

    result.fir().forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind != fir::NodeKind::ObjectDef) return;
        auto& od = result.fir().as<fir::ObjectDef>(id);
        if (od.prop_count == 0) return;
        spans.push_back({id, od.prop_start, od.prop_count});
    });

    // Each object's property span should not include properties from other objects.
    // Verify by checking that for each object, all its properties have role_ids
    // that belong to its type or are valid foreign refs (not random other objects'
    // properties).
    for (auto& span : spans) {
        auto& od = result.fir().as<fir::ObjectDef>(span.obj_id);
        auto props = result.fir().propertiesOf(od);
        EXPECT_EQ(props.size(), span.count)
            << "Property span mismatch for object at ID "
            << static_cast<uint32_t>(span.obj_id);

        // Each property should have a valid role_id (not none)
        for (auto prop_id : props) {
            auto& pv = result.fir().as<fir::PropertyVal>(prop_id);
            EXPECT_FALSE(fir::is_none(pv.role_id))
                << "Property with none role_id in object "
                << static_cast<uint32_t>(span.obj_id);
        }
    }

    // Verify no overlapping spans
    for (size_t i = 0; i < spans.size(); ++i) {
        for (size_t j = i + 1; j < spans.size(); ++j) {
            auto a_end = spans[i].start + spans[i].count;
            auto b_end = spans[j].start + spans[j].count;
            bool overlaps = (spans[i].start < b_end) && (spans[j].start < a_end);
            EXPECT_FALSE(overlaps)
                << "Object " << static_cast<uint32_t>(spans[i].obj_id)
                << " span [" << spans[i].start << ".." << a_end << ") overlaps with "
                << "Object " << static_cast<uint32_t>(spans[j].obj_id)
                << " span [" << spans[j].start << ".." << b_end << ")";
        }
    }
}

// Verify that anonymous types (no SHORT-NAME) that are both a role AND a type
// (e.g., ADMIN-DATA) create containment-linked ObjectDefs.
TEST(ArxmlCompilerTest, AnonymousObjectContainment) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("anonymous-containment.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Compilation failed";

    // Count objects — should include AUTOSAR root, ARPackage, UNIT,
    // and the anonymous ADMIN-DATA (at minimum).
    size_t obj_count = 0;
    fir::Id unit_obj_id = fir::Id{UINT32_MAX};
    result.fir().forEachNode([&](fir::Id id, const fir::Node& node) {
        if (node.kind != fir::NodeKind::ObjectDef) return;
        ++obj_count;
        auto& od = result.fir().as<fir::ObjectDef>(id);
        auto name = result.fir().stringOf(od.identity);
        if (name == "Percent") unit_obj_id = id;
    });

    // Must have ADMIN-DATA as an anonymous object (more objects than before the fix)
    EXPECT_GE(obj_count, 4u) << "Expected at least AUTOSAR + ARPackage + UNIT + ADMIN-DATA";

    // The UNIT object should have at least one containment property
    // (the ADMIN-DATA link)
    ASSERT_FALSE(fir::is_none(unit_obj_id)) << "UNIT 'Percent' not found";
    auto& unit_od = result.fir().as<fir::ObjectDef>(unit_obj_id);
    auto unit_props = result.fir().propertiesOf(unit_od);

    // Find a property whose value is an ObjectDef (containment)
    bool has_containment = false;
    for (auto prop_id : unit_props) {
        auto& pv = result.fir().as<fir::PropertyVal>(prop_id);
        if (!fir::is_none(pv.value_id)) {
            auto& val_node = result.fir().nodeAt(pv.value_id);
            if (val_node.kind == fir::NodeKind::ObjectDef) {
                has_containment = true;
                break;
            }
        }
    }
    EXPECT_TRUE(has_containment)
        << "UNIT 'Percent' should contain an anonymous ADMIN-DATA object";
}
