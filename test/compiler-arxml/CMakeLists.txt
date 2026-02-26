add_executable(senda.arxml_compiler_test arxml-compiler-test.cpp)
target_link_libraries(senda.arxml_compiler_test PRIVATE
    senda.compiler.arxml
    senda.domains
    rupa.compiler
    rupa.domain
    rupa.fir
    rupa.fir.builder
    kore
    GTest::gtest_main
)
target_compile_definitions(senda.arxml_compiler_test PRIVATE
    SENDA_TEST_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
)
target_compile_features(senda.arxml_compiler_test PUBLIC cxx_std_26)
senda_target_settings(senda.arxml_compiler_test)
add_test(NAME senda.arxml_compiler_test COMMAND senda.arxml_compiler_test)
