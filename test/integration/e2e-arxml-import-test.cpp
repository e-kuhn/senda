#include <gtest/gtest.h>
#include <filesystem>
#include <fstream>
#include <string>

import rupa.compiler;
import rupa.driver;
import rupa.fir;
import rupa.sema;
import senda.compiler.arxml;
import senda.domains;

namespace fs = std::filesystem;

// --- Helpers ---

class E2EArxmlImportTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Create temp directory for test files
        tmp_dir_ = fs::temp_directory_path() / "senda-e2e-test";
        fs::create_directories(tmp_dir_);
    }

    void TearDown() override {
        fs::remove_all(tmp_dir_);
    }

    void write_file(const std::string& name, const std::string& content) {
        std::ofstream f(tmp_dir_ / name);
        f << content;
    }

    fs::path file_path(const std::string& name) const {
        return tmp_dir_ / name;
    }

    fs::path tmp_dir_;
};

TEST_F(E2EArxmlImportTest, ArxmlCompilationThroughDriver) {
    // Write an ARXML file
    write_file("signals.arxml", R"(<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Signals</SHORT-NAME>
      <ELEMENTS>
        <I-SIGNAL>
          <SHORT-NAME>BrakePedal</SHORT-NAME>
          <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
          <LENGTH>16</LENGTH>
        </I-SIGNAL>
        <ECU-INSTANCE>
          <SHORT-NAME>BrakeECU</SHORT-NAME>
        </ECU-INSTANCE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
)");

    // Set up compilers and driver
    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler;

    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    rupa::driver::CompilationDriver driver(registry);
    driver.add_domain(senda::domains::build_autosar_r23_11());

    // Compile ARXML through the driver
    auto result = driver.compile(file_path("signals.arxml"));

    EXPECT_FALSE(result.has_errors()) << "Compilation should succeed";

    // Verify objects created
    size_t obj_count = 0;
    result.fir().forEachNode([&](fir::Id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) ++obj_count;
    });
    EXPECT_EQ(obj_count, 2u) << "Should have BrakePedal and BrakeECU";
}

TEST_F(E2EArxmlImportTest, MultiCompilerRegistration) {
    // Verify both compilers are registered and discoverable
    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler;

    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    EXPECT_NE(registry.find_compiler(".rupa"), nullptr);
    EXPECT_NE(registry.find_compiler(".arxml"), nullptr);
    EXPECT_EQ(registry.find_compiler(".unknown"), nullptr);
}

TEST_F(E2EArxmlImportTest, UnknownExtensionReportsError) {
    write_file("test.xyz", "some content");

    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler;

    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    rupa::driver::CompilationDriver driver(registry);
    auto result = driver.compile(file_path("test.xyz"));

    EXPECT_TRUE(result.has_errors()) << "Unknown extension should produce error";
}

TEST_F(E2EArxmlImportTest, DomainAvailableToArxmlCompiler) {
    write_file("ecu.arxml", R"(<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>ECUs</SHORT-NAME>
      <ELEMENTS>
        <ECU-INSTANCE>
          <SHORT-NAME>PowertrainECU</SHORT-NAME>
        </ECU-INSTANCE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
)");

    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler;

    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    rupa::driver::CompilationDriver driver(registry);
    driver.add_domain(senda::domains::build_autosar_r23_11());

    auto result = driver.compile(file_path("ecu.arxml"));
    EXPECT_FALSE(result.has_errors());

    // Find the ECU instance
    bool found_ecu = false;
    result.fir().forEachNode([&](fir::Id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) {
            auto& od = static_cast<const fir::ObjectDef&>(node);
            if (result.fir().getString(od.identity) == "PowertrainECU") {
                found_ecu = true;
            }
        }
    });
    EXPECT_TRUE(found_ecu);
}
