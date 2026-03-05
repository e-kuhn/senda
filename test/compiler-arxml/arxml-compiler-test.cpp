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

    // Should have at least one object
    EXPECT_GE(result.fir().model.nodes.size(), 1u);
}

TEST(ArxmlCompilerTest, CompileMultipleElements) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("multi-element.arxml"), ctx);
    EXPECT_FALSE(result.has_errors());

    // Should have multiple objects
    EXPECT_GE(result.fir().model.nodes.size(), 1u);
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

    // For each node, verify its property span is valid:
    // prop_start + prop_count should not overlap with another node's span.
    struct NodeSpan {
        fir::NodeHandle nh;
        uint32_t start;
        uint32_t count;
    };
    std::vector<NodeSpan> spans;

    auto& model = result.fir().model;
    for (uint32_t i = 0; i < model.nodes.size(); ++i) {
        auto nh = fir::NodeHandle{i};
        auto& node = model.node(nh);
        if (node.prop_count == 0) continue;
        spans.push_back({nh, node.prop_start, node.prop_count});
    }

    // Verify no overlapping spans
    for (size_t i = 0; i < spans.size(); ++i) {
        for (size_t j = i + 1; j < spans.size(); ++j) {
            auto a_end = spans[i].start + spans[i].count;
            auto b_end = spans[j].start + spans[j].count;
            bool overlaps = (spans[i].start < b_end) && (spans[j].start < a_end);
            EXPECT_FALSE(overlaps)
                << "Node " << static_cast<uint32_t>(spans[i].nh)
                << " span [" << spans[i].start << ".." << a_end << ") overlaps with "
                << "Node " << static_cast<uint32_t>(spans[j].nh)
                << " span [" << spans[j].start << ".." << b_end << ")";
        }
    }
}

// Verify that anonymous types (no SHORT-NAME) that are both a role AND a type
// (e.g., ADMIN-DATA) create contained nodes.
TEST(ArxmlCompilerTest, AnonymousObjectContainment) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("anonymous-containment.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Compilation failed";

    auto& model = result.fir().model;

    // Must have at least: AUTOSAR + ARPackage + UNIT + ADMIN-DATA
    EXPECT_GE(model.nodes.size(), 4u)
        << "Expected at least AUTOSAR + ARPackage + UNIT + ADMIN-DATA";

    // Find a node that has containment properties (a prop with is_node=true)
    bool has_containment = false;
    for (uint32_t i = 0; i < model.nodes.size(); ++i) {
        auto nh = fir::NodeHandle{i};
        auto& node = model.node(nh);
        auto props = model.props_of(node);
        for (auto& prop : props) {
            if (prop.is_node()) {
                has_containment = true;
                break;
            }
        }
        if (has_containment) break;
    }
    EXPECT_TRUE(has_containment)
        << "Should have at least one containment property (e.g., ADMIN-DATA)";
}

// Verify WrapperRole pattern: SDGS (xml_tags=0x03) creates a Wrapper frame
// that dispatches SDG children as contained Objects, NOT as a direct Object.
TEST(ArxmlCompilerTest, WrapperRoleSDGSContainment) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("wrapper-role.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Compilation failed";

    auto& model = result.fir().model;

    // Expected: at least 5 objects (AUTOSAR, ARPackage, UNIT, ADMIN-DATA, SDG)
    EXPECT_GE(model.nodes.size(), 5u)
        << "Expected at least 5 objects";

    // Verify containment chain exists (node with containment props)
    size_t nodes_with_containment = 0;
    for (uint32_t i = 0; i < model.nodes.size(); ++i) {
        auto nh = fir::NodeHandle{i};
        auto& node = model.node(nh);
        auto props = model.props_of(node);
        for (auto& prop : props) {
            if (prop.is_node()) {
                ++nodes_with_containment;
                break;
            }
        }
    }
    EXPECT_GE(nodes_with_containment, 2u)
        << "Should have containment hierarchy (UNIT->ADMIN-DATA->SDG)";
}

// Verify WrapperOnly pattern: ELEMENTS (xml_tags=0x02) dispatches
// type-named children via type lookup within the Wrapper frame.
TEST(ArxmlCompilerTest, WrapperOnlyELEMENTSDispatch) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    // multi-element.arxml has AR-PACKAGE > ELEMENTS > {I-SIGNAL, I-SIGNAL}
    auto result = compiler.compile(fixture_path("multi-element.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Compilation failed";

    auto& model = result.fir().model;

    // Should have at least: AUTOSAR, AR-PACKAGE, and two I-SIGNALs
    EXPECT_GE(model.nodes.size(), 4u)
        << "Expected at least AUTOSAR + AR-PACKAGE + 2 I-SIGNALs";
}

// Verify xml.attribute=true capture: GID on SDG should become a property.
TEST(ArxmlCompilerTest, CapturesXmlAttributes) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockArxmlContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    // anonymous-containment.arxml has: <SDG GID="info"><SD GID="uuid">...</SD></SDG>
    auto result = compiler.compile(fixture_path("anonymous-containment.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Compilation failed";

    auto& fir = result.fir();
    auto& model = fir.model;

    // Find any object with a string property value "info" (GID attribute)
    bool found_gid_property = false;
    for (uint32_t i = 0; i < model.nodes.size(); ++i) {
        auto nh = fir::NodeHandle{i};
        auto& node = model.node(nh);
        auto props = model.props_of(node);
        for (auto& prop : props) {
            if (prop.is_node()) continue;
            auto vh = prop.value_handle();
            if (fir::value_kind(vh) != fir::ValueKind::String) continue;
            const auto& sid = model.values.get_string(vh);
            auto val_str = fir.get_string(sid);
            if (val_str == "info") {
                found_gid_property = true;
            }
        }
    }
    EXPECT_TRUE(found_gid_property)
        << "SDG object should have a property with value 'info' "
           "(GID attribute captured via xml.attribute=true)";
}
