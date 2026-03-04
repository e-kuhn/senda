add_executable(senda.emitter_arxml_test emitter-test.cpp)
target_link_libraries(senda.emitter_arxml_test PRIVATE
    senda.emitter.arxml
    senda.compiler.arxml
    senda.domains
    rupa.compiler
    rupa.domain
    rupa.fir
    kore
    GTest::gtest_main
)
target_compile_definitions(senda.emitter_arxml_test PRIVATE
    SENDA_TEST_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../compiler-arxml/fixtures"
)
target_compile_features(senda.emitter_arxml_test PUBLIC cxx_std_26)
senda_target_settings(senda.emitter_arxml_test)
add_test(NAME senda.emitter_arxml_test COMMAND senda.emitter_arxml_test)
