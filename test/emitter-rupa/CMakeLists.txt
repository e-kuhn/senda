add_executable(senda.emitter_rupa_test emitter-rupa-test.cpp)
target_link_libraries(senda.emitter_rupa_test PRIVATE
    rupa.emitter
    senda.compiler.arxml
    senda.domains
    rupa.compiler
    rupa.domain
    rupa.fir
    rupa.fir.builder
    kore
    GTest::gtest_main
)
target_compile_definitions(senda.emitter_rupa_test PRIVATE
    SENDA_TEST_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../compiler-arxml/fixtures"
)
target_compile_features(senda.emitter_rupa_test PUBLIC cxx_std_26)
senda_target_settings(senda.emitter_rupa_test)
add_test(NAME senda.emitter_rupa_test COMMAND senda.emitter_rupa_test)
