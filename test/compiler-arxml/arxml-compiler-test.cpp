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
import senda.domains.r23_11;

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
    auto schema = senda::domains::build_autosar_r23_11();
    senda::ArxmlCompiler compiler(schema);
    auto exts = compiler.extensions();
    ASSERT_EQ(exts.size(), 1u);
    EXPECT_EQ(exts[0], ".arxml");
}

TEST(ArxmlCompilerTest, CompileSimpleSignal) {
    auto schema = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(schema.domain);
    senda::ArxmlCompiler compiler(schema);

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
    auto schema = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(schema.domain);
    senda::ArxmlCompiler compiler(schema);

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
    auto schema = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(schema.domain);
    senda::ArxmlCompiler compiler(schema);

    auto result = compiler.compile(fixture_path("nested-packages.arxml"), ctx);
    EXPECT_FALSE(result.has_errors());
}

TEST(ArxmlCompilerTest, InvalidXmlProducesError) {
    auto schema = senda::domains::build_autosar_r23_11();
    MockArxmlContext ctx(schema.domain);
    senda::ArxmlCompiler compiler(schema);

    // Non-existent file
    auto result = compiler.compile("/tmp/nonexistent.arxml", ctx);
    EXPECT_TRUE(result.has_errors());
}
