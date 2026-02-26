add_executable(senda.e2e_arxml_import_test e2e-arxml-import-test.cpp)
target_link_libraries(senda.e2e_arxml_import_test PRIVATE
    rupa.driver
    rupa.sema
    rupa.compiler
    senda.compiler.arxml
    senda.domains
    rupa.domain
    rupa.fir
    rupa.fir.builder
    kore
    GTest::gtest_main
)
target_compile_features(senda.e2e_arxml_import_test PUBLIC cxx_std_26)
senda_target_settings(senda.e2e_arxml_import_test)
add_test(NAME senda.e2e_arxml_import_test COMMAND senda.e2e_arxml_import_test)
