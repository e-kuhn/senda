#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <string_view>
#include <unordered_map>

import rupa.compiler;
import rupa.driver;
import rupa.emitter;
import rupa.fir;
import rupa.sema;
import senda.compiler.arxml;
import senda.domains;
import senda.domains.r19_11;
import senda.domains.r20_11;
import senda.domains.r21_11;
import senda.domains.r22_11;
import senda.domains.r23_11;

namespace fs = std::filesystem;

class SchemaForeignResolver : public rupa::emitter::ForeignResolver {
public:
    const fir::Fir* resolve(fir::ModuleId module) const override {
        auto it = firs_.find(static_cast<uint16_t>(module));
        return it != firs_.end() ? it->second : nullptr;
    }

    void register_module(fir::ModuleId module, const fir::Fir* fir) {
        firs_[static_cast<uint16_t>(module)] = fir;
    }

private:
    std::unordered_map<uint16_t, const fir::Fir*> firs_;
};

int main(int argc, char* argv[]) {
    std::string domain_override;
    std::string emit_output;
    int max_warnings = 10;
    bool emit_flag = false;
    fs::path input_path;

    for (int i = 1; i < argc; ++i) {
        std::string_view arg(argv[i]);
        if (arg == "--domain" && i + 1 < argc) {
            domain_override = argv[++i];
        } else if (arg == "--max-warnings" && i + 1 < argc) {
            max_warnings = std::atoi(argv[++i]);
        } else if (arg == "--emit" || arg == "-e") {
            emit_flag = true;
        } else if (arg == "--emit-output" && i + 1 < argc) {
            emit_output = argv[++i];
        } else if (arg[0] == '-') {
            std::fprintf(stderr, "unknown option: %s\n", argv[i]);
            return 1;
        } else {
            input_path = arg;
        }
    }

    if (input_path.empty()) {
        std::puts("senda 0.1.0 — Automotive DSL built on Rupa");
        std::puts("Usage: senda [--domain <name>] [--max-warnings <N>] [--emit [output.rupa]] <file>");
        return 0;
    }

    // Register all AUTOSAR schemas (lazy — only built when needed)
    senda::SchemaRegistry schema_registry;
    schema_registry.add("AUTOSAR_00048.xsd", "autosar-r19-11",
                        senda::domains::build_autosar_r19_11);
    schema_registry.add("AUTOSAR_00049.xsd", "autosar-r20-11",
                        senda::domains::build_autosar_r20_11);
    schema_registry.add("AUTOSAR_00050.xsd", "autosar-r21-11",
                        senda::domains::build_autosar_r21_11);
    schema_registry.add("AUTOSAR_00051.xsd", "autosar-r22-11",
                        senda::domains::build_autosar_r22_11);
    schema_registry.add("AUTOSAR_00052.xsd", "autosar-r23-11",
                        senda::domains::build_autosar_r23_11);

    // Create compilers
    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler(schema_registry, domain_override,
                                        max_warnings);

    // Register compilers
    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    // Create driver with lazy domain builders
    rupa::driver::CompilationDriver driver(registry);
    driver.register_domain_builder("autosar-r19-11", [&schema_registry] {
        return std::move(schema_registry.resolve_by_domain("autosar-r19-11")
                             ->domain);
    });
    driver.register_domain_builder("autosar-r20-11", [&schema_registry] {
        return std::move(schema_registry.resolve_by_domain("autosar-r20-11")
                             ->domain);
    });
    driver.register_domain_builder("autosar-r21-11", [&schema_registry] {
        return std::move(schema_registry.resolve_by_domain("autosar-r21-11")
                             ->domain);
    });
    driver.register_domain_builder("autosar-r22-11", [&schema_registry] {
        return std::move(schema_registry.resolve_by_domain("autosar-r22-11")
                             ->domain);
    });
    driver.register_domain_builder("autosar-r23-11", [&schema_registry] {
        return std::move(schema_registry.resolve_by_domain("autosar-r23-11")
                             ->domain);
    });

    // Validate domain override if specified
    if (!domain_override.empty()) {
        if (!schema_registry.has_domain(domain_override)) {
            std::fprintf(stderr, "error: domain '%s' is not available\n",
                         domain_override.c_str());
            return 1;
        }
        driver.set_domain_override(domain_override);
    }

    // Compile
    auto result = driver.compile(input_path);

    // Report diagnostics
    for (const auto& diag : result.diagnostics()) {
        const char* severity = "note";
        if (diag.severity == rupa::compiler::Severity::Error) severity = "error";
        else if (diag.severity == rupa::compiler::Severity::Warning) severity = "warning";

        std::fprintf(stderr, "%s:%u:%u: %s: %s\n",
            diag.location.file.c_str(),
            diag.location.line,
            diag.location.column,
            severity,
            diag.message.c_str());
    }

    if (result.has_errors()) {
        return 1;
    }

    // Report success
    size_t obj_count = result.fir().model.nodes.size();
    std::fprintf(stderr, "Compiled %s: %zu objects\n", input_path.c_str(), obj_count);

    // Emit to Rupa if requested
    if (emit_flag) {
        // Build foreign resolver from the domain that was used
        SchemaForeignResolver resolver;

        auto& fir = result.fir();
        for (size_t i = 0; i < fir.types.modules.size(); ++i) {
            auto mod_id = fir::ModuleId{static_cast<uint16_t>(i)};
            auto name_sid = fir.types.modules[i].name;
            if (fir::is_none(name_sid)) continue;
            auto name = fir.get_string(name_sid);
            auto* dom = driver.find_domain(name);
            if (dom) {
                resolver.register_module(mod_id, dom->view().fir());
            }
        }

        rupa::emitter::RupaEmitter emitter;
        if (emit_output.empty()) {
            emitter.emit(fir, std::cout, &resolver);
        } else {
            if (!emitter.emit(fir, fs::path(emit_output), &resolver)) {
                std::fprintf(stderr, "error: cannot write '%s'\n",
                             emit_output.c_str());
                return 1;
            }
            std::fprintf(stderr, "Wrote %s\n", emit_output.c_str());
        }
    }

    return 0;
}
