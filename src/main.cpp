#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <string_view>

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
    size_t obj_count = 0;
    result.fir().forEachNode([&](fir::Id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) ++obj_count;
    });
    std::fprintf(stderr, "Compiled %s: %zu objects\n", input_path.c_str(), obj_count);

    // Emit to Rupa if requested
    if (emit_flag) {
        rupa::emitter::RupaEmitter emitter;
        if (emit_output.empty()) {
            emitter.emit(result.fir(), std::cout);
        } else {
            if (!emitter.emit(result.fir(), fs::path(emit_output))) {
                std::fprintf(stderr, "error: cannot write '%s'\n",
                             emit_output.c_str());
                return 1;
            }
            std::fprintf(stderr, "Wrote %s\n", emit_output.c_str());
        }
    }

    return 0;
}
