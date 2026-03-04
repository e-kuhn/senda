#include <gtest/gtest.h>
#include <filesystem>
#include <sstream>
#include <string>
#include <unordered_map>

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;
import rupa.emitter;
import senda.compiler.arxml;
import senda.domains;
import senda.domains.r23_11;

namespace fs = std::filesystem;

// Mock CompileContext (same pattern as arxml-compiler-test)
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

static senda::SchemaRegistry make_registry() {
    senda::SchemaRegistry reg;
    reg.add("AUTOSAR_00052.xsd", "autosar-r23-11",
            senda::domains::build_autosar_r23_11);
    return reg;
}

// Verify the ARXML compiler now sets root object in the FIR
TEST(RupaEmitterPipeline, ArxmlCompilerSetsRootObject) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    ASSERT_NE(schema, nullptr);

    MockEmitterContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("simple-signal.arxml"), ctx);
    ASSERT_FALSE(result.has_errors()) << "ARXML compilation failed";

    // Root object should be set after compilation
    auto root_nh = result.fir().model.root_object;
    EXPECT_FALSE(fir::is_none(root_nh))
        << "Root object not set after compilation";
}

// Full emitter pipeline: build types + instances in same FIR, emit to Rupa.
TEST(RupaEmitterPipeline, FullPipelineWithManualTypes) {
    using namespace fir;

    Fir fir;
    FirBuilder builder(fir);

    // Build AUTOSAR-like domain types
    auto str_prim = builder.add_type("::string", M3Kind::Primitive);
    auto str_type = builder.add_type("Str", M3Kind::Primitive);
    builder.set_supertype(str_type, str_prim);

    auto int_prim = builder.add_type("::integer", M3Kind::Primitive);
    auto int_type = builder.add_type("PositiveInteger", M3Kind::Primitive);
    builder.set_supertype(int_type, int_prim);

    auto base = builder.add_type("ARObject", M3Kind::Composite);
    builder.set_abstract(base, true);
    builder.set_domain(base, "autosar-r23-11");

    auto referrable = builder.add_type("Referrable", M3Kind::Composite);
    builder.set_supertype(referrable, base);
    auto ref_name = builder.add_role(referrable, "shortName", str_type, Multiplicity::One);
    builder.set_identity(ref_name, true);
    builder.finalize_roles(referrable);
    builder.set_domain(referrable, "autosar-r23-11");

    auto signal = builder.add_type("SystemSignal", M3Kind::Composite);
    builder.set_supertype(signal, referrable);
    auto sig_len = builder.add_role(signal, "length", int_type, Multiplicity::One);
    builder.finalize_roles(signal);
    builder.set_domain(signal, "autosar-r23-11");

    auto pkg = builder.add_type("ARPackage", M3Kind::Composite);
    builder.set_supertype(pkg, referrable);
    auto pkg_subs = builder.add_role(pkg, "subPackages", pkg, Multiplicity::Many);
    auto pkg_elements = builder.add_role(pkg, "elements", signal, Multiplicity::Many);
    builder.finalize_roles(pkg);
    builder.set_domain(pkg, "autosar-r23-11");

    builder.add_root_type(pkg);

    // Build instance tree:
    // ARPackage AUTOSAR {
    //   .subPackages += ARPackage Signals {
    //     .elements += SystemSignal BrakePedalPosition { .length = 12; };
    //   };
    // }
    auto brake = builder.begin_object(signal);
    builder.add_property(brake, ref_name, str_type, builder.add_string("BrakePedalPosition"));
    builder.add_property(brake, sig_len, int_type, builder.add_integer(12));
    builder.finalize_properties(brake);

    auto signals_pkg = builder.begin_object(pkg);
    builder.add_property(signals_pkg, ref_name, str_type, builder.add_string("Signals"));
    builder.add_containment(signals_pkg, pkg_elements, signal, brake);
    builder.finalize_properties(signals_pkg);

    auto root = builder.begin_object(pkg);
    builder.add_property(root, ref_name, str_type, builder.add_string("AUTOSAR"));
    builder.add_containment(root, pkg_subs, pkg, signals_pkg);
    builder.finalize_properties(root);
    builder.set_root_object(root);

    // Emit to Rupa
    rupa::emitter::RupaEmitter emitter;
    std::ostringstream out;
    ASSERT_TRUE(emitter.emit(fir, out));

    auto result = out.str();
    ASSERT_FALSE(result.empty()) << "Emitter produced empty output";

    // Type definitions
    EXPECT_NE(result.find("domain autosar-r23-11;"), std::string::npos);
    EXPECT_NE(result.find("#[abstract]"), std::string::npos);
    EXPECT_NE(result.find("type ARObject = {};"), std::string::npos);
    EXPECT_NE(result.find("type SystemSignal = Referrable {"), std::string::npos);
    EXPECT_NE(result.find("type ARPackage = Referrable {"), std::string::npos);
    EXPECT_NE(result.find("#[root]"), std::string::npos);

    // Instance data
    EXPECT_NE(result.find("using domain autosar-r23-11;"), std::string::npos);
    EXPECT_NE(result.find("ARPackage AUTOSAR {"), std::string::npos);
    EXPECT_NE(result.find(".subPackages = ARPackage Signals {"), std::string::npos);
    EXPECT_NE(result.find(".elements = SystemSignal BrakePedalPosition {"),
              std::string::npos);
    EXPECT_NE(result.find(".length = 12;"), std::string::npos);
}

// Test the full ARXML compile -> foreign ID -> emit pipeline with ForeignResolver.
TEST(RupaEmitterPipeline, ArxmlToRupaWithForeignResolver) {
    auto reg = make_registry();
    auto* schema = reg.resolve_by_domain("autosar-r23-11");
    ASSERT_NE(schema, nullptr);

    MockEmitterContext ctx(schema->domain);
    senda::ArxmlCompiler compiler(reg, "autosar-r23-11");

    auto result = compiler.compile(fixture_path("simple-signal.arxml"), ctx);
    ASSERT_FALSE(result.has_errors()) << "ARXML compilation failed";

    // Build foreign resolver from the domain
    struct TestForeignResolver : rupa::emitter::ForeignResolver {
        std::unordered_map<uint16_t, const fir::Fir*> firs;
        const fir::Fir* resolve(fir::ModuleId module) const override {
            auto it = firs.find(static_cast<uint16_t>(module));
            return it != firs.end() ? it->second : nullptr;
        }
    };
    TestForeignResolver resolver;

    auto& fir = result.fir();
    // Register domain FIRs for foreign resolution
    for (size_t i = 0; i < fir.types.modules.size(); ++i) {
        auto name_sid = fir.types.modules[i].name;
        if (fir::is_none(name_sid)) continue;
        auto name = fir.get_string(name_sid);
        auto* s = reg.resolve_by_domain(name);
        if (s) resolver.firs[static_cast<uint16_t>(i)] = s->domain.view().fir();
    }

    // Emit with resolver
    rupa::emitter::RupaEmitter emitter;
    std::ostringstream out;
    ASSERT_TRUE(emitter.emit(fir, out, &resolver));

    auto rupa_output = out.str();
    ASSERT_FALSE(rupa_output.empty());

    // Should have domain declaration and type-resolved instance names
    EXPECT_NE(rupa_output.find("using domain"), std::string::npos);
    // Should NOT have unresolved "?" for type names
    EXPECT_EQ(rupa_output.find("? "), std::string::npos)
        << "Found unresolved '?' in output:\n" << rupa_output.substr(0, 500);
}
