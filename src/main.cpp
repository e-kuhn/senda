#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <string_view>

import rupa.compiler;
import rupa.driver;
import rupa.fir;
import rupa.sema;
import senda.compiler.arxml;
import senda.domains.r23_11;

namespace fs = std::filesystem;

int main(int argc, char* argv[]) {
    std::string domain_override;
    int max_warnings = 10;
    fs::path input_path;

    for (int i = 1; i < argc; ++i) {
        std::string_view arg(argv[i]);
        if (arg == "--domain" && i + 1 < argc) {
            domain_override = argv[++i];
        } else if (arg == "--max-warnings" && i + 1 < argc) {
            max_warnings = std::atoi(argv[++i]);
        } else if (arg[0] == '-') {
            std::fprintf(stderr, "unknown option: %s\n", argv[i]);
            return 1;
        } else {
            input_path = arg;
        }
    }

    if (input_path.empty()) {
        std::puts("senda 0.1.0 — Automotive DSL built on Rupa");
        std::puts("Usage: senda [--domain <name>] [--max-warnings <N>] <file>");
        return 0;
    }

    // Build AUTOSAR schema (domain + lookup tables)
    auto schema = senda::domains::build_autosar_r23_11();

    // Build XSD → domain registry
    senda::SchemaRegistry schema_registry;
    schema_registry.add(schema.xsd_filename, schema.domain.name());

    // Create compilers
    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler(schema, schema_registry, max_warnings);

    // Register compilers
    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    // Create driver
    rupa::driver::CompilationDriver driver(registry);

    // Load domain from schema
    driver.add_domain(std::move(schema.domain));

    // Set domain override if specified
    if (!domain_override.empty()) {
        if (!driver.find_domain(domain_override)) {
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
    std::printf("Compiled %s: %zu objects\n", input_path.c_str(), obj_count);

    return 0;
}
