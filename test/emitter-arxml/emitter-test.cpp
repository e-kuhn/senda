#include <gtest/gtest.h>
#include <filesystem>
#include <sstream>
#include <string>
#include <string_view>

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;
import senda.compiler.arxml;
import senda.emitter.arxml;
import senda.domains;
import senda.domains.r23_11;

namespace fs = std::filesystem;

// Mock compile context (same as compiler tests)
class MockEmitterContext : public rupa::compiler::CompileContext {
public:
    explicit MockEmitterContext(const rupa::domain::Domain& domain)
        : view_(domain.view()),
          transaction_(view_, "autosar-r23-11") {}

    rupa::compiler::CompileResult compile_import(const fs::path&) override {
        return rupa::compiler::CompileResult(
            fir::Fir{}, rupa::compiler::DomainExtensions{}, rupa::compiler::Diagnostics{});
    }

    const rupa::domain::DomainView* request_domain(std::string_view name) override {
        if (name == "autosar-r23-11") return &view_;
        return nullptr;
    }

    const rupa::domain::DomainView* request_default_domain() override {
        return &view_;
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

static fs::path fixture_path(const char* name) {
    return fs::path(SENDA_TEST_FIXTURES_DIR) / name;
}

TEST(ArxmlEmitter, EmitsXmlHeader) {
    auto schema = senda::domains::build_autosar_r23_11();
    senda::ArxmlEmitter emitter(schema);

    fir::Fir fir;
    std::ostringstream out;
    emitter.emit(fir, out);

    auto result = out.str();
    EXPECT_NE(result.find("<?xml version="), std::string::npos);
    EXPECT_NE(result.find("<AUTOSAR>"), std::string::npos);
    EXPECT_NE(result.find("</AUTOSAR>"), std::string::npos);
}

TEST(ArxmlEmitter, RoundTripSimpleSignal) {
    senda::SchemaRegistry reg;
    reg.add("AUTOSAR_00052.xsd", "autosar-r23-11",
            senda::domains::build_autosar_r23_11);
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    MockEmitterContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");
    senda::ArxmlEmitter emitter(*schema);

    // Compile ARXML -> FIR
    auto compile_result = compiler.compile(fixture_path("simple-signal.arxml"), ctx);
    ASSERT_FALSE(compile_result.has_errors()) << "Compilation failed";

    // Verify objects were produced
    ASSERT_GE(compile_result.fir().model.nodes.size(), 1u)
        << "Should have at least one object";

    // Emit FIR -> ARXML
    std::ostringstream out;
    bool ok = emitter.emit(compile_result.fir(), out);
    ASSERT_TRUE(ok);

    auto result = out.str();

    // Should contain XML structure
    EXPECT_NE(result.find("<?xml version="), std::string::npos);
    EXPECT_NE(result.find("<AUTOSAR>"), std::string::npos);
    EXPECT_NE(result.find("</AUTOSAR>"), std::string::npos);

    // Should contain the objects that were compiled
    EXPECT_NE(result.find("<SHORT-NAME>"), std::string::npos);
}
