add_executable(senda.arxml_compiler_test arxml-compiler-test.cpp)
target_link_libraries(senda.arxml_compiler_test PRIVATE
    senda.compiler.arxml
    senda.domains
    rupa.compiler
    rupa.domain
    rupa.fir
    kore
    GTest::gtest_main
)
target_compile_definitions(senda.arxml_compiler_test PRIVATE
    SENDA_TEST_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
)
target_compile_features(senda.arxml_compiler_test PUBLIC cxx_std_26)
senda_target_settings(senda.arxml_compiler_test)
add_test(NAME senda.arxml_compiler_test COMMAND senda.arxml_compiler_test)

# XmlPullParser unit tests
add_executable(senda.xml_pull_parser_test xml-pull-parser-test.cpp)
target_link_libraries(senda.xml_pull_parser_test PRIVATE
    senda.compiler.arxml
    GTest::gtest_main
)
target_include_directories(senda.xml_pull_parser_test PRIVATE
    ${CMAKE_SOURCE_DIR}/src/compiler-arxml
)
target_compile_definitions(senda.xml_pull_parser_test PRIVATE
    SENDA_TEST_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
)
target_compile_features(senda.xml_pull_parser_test PUBLIC cxx_std_26)
senda_target_settings(senda.xml_pull_parser_test)
add_test(NAME senda.xml_pull_parser_test COMMAND senda.xml_pull_parser_test)
