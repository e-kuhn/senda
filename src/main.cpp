#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>

import rupa.compiler;
import rupa.driver;
import rupa.fir;
import rupa.sema;
import senda.compiler.arxml;
import senda.domains;

namespace fs = std::filesystem;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::puts("senda 0.1.0 — Automotive DSL built on Rupa");
        std::puts("Usage: senda <file.rupa|file.arxml>");
        return 0;
    }

    fs::path input_path(argv[1]);

    // Create compilers
    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler;

    // Register compilers
    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    // Create driver
    rupa::driver::CompilationDriver driver(registry);

    // Load pre-built AUTOSAR domain
    driver.add_domain(senda::domains::build_autosar_r23_11());

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
