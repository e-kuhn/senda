#include <gtest/gtest.h>
#include <filesystem>
#include <sstream>
#include <string>

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
    auto root_id = result.fir().rootObject();
    EXPECT_NE(static_cast<uint32_t>(root_id), UINT32_MAX)
        << "Root object not set after compilation";
}

// Full emitter pipeline: build types + instances in same FIR, emit to Rupa.
// This simulates the end-to-end ARXML->FIR->Rupa pipeline with types
// co-located in the same FIR (future: ARXML compiler will import domain types).
TEST(RupaEmitterPipeline, FullPipelineWithManualTypes) {
    using namespace fir;
    using namespace rupa::fir_builder;

    Fir fir;
    FirBuilder builder(fir);

    // Build AUTOSAR-like domain types
    auto str_prim = builder.begin_type("::string", M3Kind::Primitive);
    auto str_type = builder.begin_type("Str", M3Kind::Primitive);
    builder.set_supertype(str_type, str_prim);

    auto int_prim = builder.begin_type("::integer", M3Kind::Primitive);
    auto int_type = builder.begin_type("PositiveInteger", M3Kind::Primitive);
    builder.set_supertype(int_type, int_prim);

    auto base = builder.begin_type("ARObject", M3Kind::Composite);
    builder.set_abstract(base, true);
    builder.set_domain(base, "autosar-r23-11");

    auto referrable = builder.begin_type("Referrable", M3Kind::Composite);
    builder.set_supertype(referrable, base);
    auto ref_name = builder.add_role(referrable, "shortName", str_type, Multiplicity::One);
    fir.as<RoleDef>(ref_name.id).is_identity = true;
    builder.set_domain(referrable, "autosar-r23-11");

    auto signal = builder.begin_type("SystemSignal", M3Kind::Composite);
    builder.set_supertype(signal, referrable);
    auto sig_len = builder.add_role(signal, "length", int_type, Multiplicity::One);
    builder.set_domain(signal, "autosar-r23-11");

    auto pkg = builder.begin_type("ARPackage", M3Kind::Composite);
    builder.set_supertype(pkg, referrable);
    auto pkg_subs = builder.add_role(pkg, "subPackages", pkg, Multiplicity::Many);
    auto pkg_elements = builder.add_role(pkg, "elements", signal, Multiplicity::Many);
    builder.set_domain(pkg, "autosar-r23-11");

    builder.add_root_type(pkg);

    // Build instance tree:
    // ARPackage AUTOSAR {
    //   .subPackages += ARPackage Signals {
    //     .elements += SystemSignal BrakePedalPosition { .length = 12; };
    //   };
    // }
    auto brake = builder.begin_object("BrakePedalPosition", signal);
    builder.add_property(brake, ref_name, std::string_view("BrakePedalPosition"));
    builder.add_property(brake, sig_len, int64_t{12});

    auto signals_pkg = builder.begin_object("Signals", pkg);
    builder.add_property(signals_pkg, ref_name, std::string_view("Signals"));
    {
        auto prop_id = fir.add<PropertyVal>(pkg_elements.id, brake.id);
        auto& od = fir.as<ObjectDef>(signals_pkg.id);
        if (od.prop_count == 0) {
            od.prop_start = fir.appendProperties({&prop_id, 1});
        } else {
            fir.appendProperties({&prop_id, 1});
        }
        od.prop_count++;
    }

    auto root = builder.begin_object("AUTOSAR", pkg);
    builder.add_property(root, ref_name, std::string_view("AUTOSAR"));
    {
        auto prop_id = fir.add<PropertyVal>(pkg_subs.id, signals_pkg.id);
        auto& od = fir.as<ObjectDef>(root.id);
        if (od.prop_count == 0) {
            od.prop_start = fir.appendProperties({&prop_id, 1});
        } else {
            fir.appendProperties({&prop_id, 1});
        }
        od.prop_count++;
    }
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
    EXPECT_NE(result.find(".subPackages += ARPackage Signals {"), std::string::npos);
    EXPECT_NE(result.find(".elements += SystemSignal BrakePedalPosition {"),
              std::string::npos);
    EXPECT_NE(result.find(".length = 12;"), std::string::npos);
}
