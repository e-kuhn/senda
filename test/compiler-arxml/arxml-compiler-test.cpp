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

namespace fs = std::filesystem;

// --- Test-only mock CompileContext ---

class MockArxmlContext : public rupa::compiler::CompileContext {
public:
    explicit MockArxmlContext(const rupa::domain::Domain& domain)
        : view_(domain.view()),
          transaction_(view_, "autosar-r23-11") {}

    rupa::compiler::CompileResult compile_import(const fs::path& /*path*/) override {
        return rupa::compiler::CompileResult(
            fir::Fir{}, rupa::compiler::DomainExtensions{}, rupa::compiler::Diagnostics{});
    }

    const rupa::domain::DomainView* request_domain(std::string_view name) override {
        if (name == "autosar-r23-11") return &view_;
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
};

// --- Helpers ---

static fs::path fixture_path(const char* name) {
    // Fixtures are relative to the test source directory
    return fs::path(SENDA_TEST_FIXTURES_DIR) / name;
}

// --- Tests ---

TEST(ArxmlCompilerTest, ImplementsCompilerInterface) {
    senda::ArxmlCompiler compiler;
    auto exts = compiler.extensions();
    ASSERT_EQ(exts.size(), 1u);
    EXPECT_EQ(exts[0], ".arxml");
}

TEST(ArxmlCompilerTest, CompileSimpleSignal) {
    auto domain = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(domain);
    senda::ArxmlCompiler compiler;

    auto result = compiler.compile(fixture_path("simple-signal.arxml"), ctx);
    EXPECT_FALSE(result.has_errors()) << "Unexpected errors in compilation";

    // Should have one ObjectDef (BrakePedalPosition)
    size_t obj_count = 0;
    result.fir().forEachNode([&](fir::Id /*id*/, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) ++obj_count;
    });
    EXPECT_EQ(obj_count, 1u);

    // Verify the object's identity
    bool found_brake = false;
    result.fir().forEachNode([&](fir::Id /*id*/, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) {
            auto& od = static_cast<const fir::ObjectDef&>(node);
            if (result.fir().getString(od.identity) == "BrakePedalPosition") {
                found_brake = true;
            }
        }
    });
    EXPECT_TRUE(found_brake);
}

TEST(ArxmlCompilerTest, CompileMultipleElements) {
    auto domain = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(domain);
    senda::ArxmlCompiler compiler;

    auto result = compiler.compile(fixture_path("multi-element.arxml"), ctx);
    EXPECT_FALSE(result.has_errors());

    // Should have 3 objects: BrakePedalPosition, VehicleSpeed, BrakeECU
    size_t obj_count = 0;
    result.fir().forEachNode([&](fir::Id /*id*/, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) ++obj_count;
    });
    EXPECT_EQ(obj_count, 3u);
}

TEST(ArxmlCompilerTest, NestedPackages) {
    auto domain = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(domain);
    senda::ArxmlCompiler compiler;

    auto result = compiler.compile(fixture_path("nested-packages.arxml"), ctx);
    EXPECT_FALSE(result.has_errors());

    // Should find NestedSignal from the nested package
    bool found = false;
    result.fir().forEachNode([&](fir::Id /*id*/, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) {
            auto& od = static_cast<const fir::ObjectDef&>(node);
            if (result.fir().getString(od.identity) == "NestedSignal") {
                found = true;
            }
        }
    });
    EXPECT_TRUE(found);
}

TEST(ArxmlCompilerTest, InvalidXmlProducesError) {
    auto domain = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(domain);
    senda::ArxmlCompiler compiler;

    // Non-existent file
    auto result = compiler.compile("/tmp/nonexistent.arxml", ctx);
    EXPECT_TRUE(result.has_errors());
}

TEST(ArxmlCompilerTest, PropertiesMappedCorrectly) {
    auto domain = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(domain);
    senda::ArxmlCompiler compiler;

    auto result = compiler.compile(fixture_path("simple-signal.arxml"), ctx);
    EXPECT_FALSE(result.has_errors());

    // Verify properties exist on the object
    size_t prop_count = 0;
    result.fir().forEachNode([&](fir::Id /*id*/, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) {
            auto& od = static_cast<const fir::ObjectDef&>(node);
            prop_count = od.prop_count;
        }
    });
    // iSignalType + length = 2 properties
    EXPECT_EQ(prop_count, 2u);
}
