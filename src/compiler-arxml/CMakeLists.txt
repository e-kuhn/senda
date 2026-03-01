add_library(senda.compiler.arxml)
target_sources(senda.compiler.arxml
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.compiler-arxml.cppm
    PRIVATE
        xml_pull_parser.cpp
        xml_simd_kernels.cpp
)
target_include_directories(senda.compiler.arxml PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(senda.compiler.arxml
    PUBLIC rupa.compiler rupa.fir.builder rupa.domain rupa.fir kore senda.domains rupa.diagnostics
    PRIVATE expat hwy
)
target_compile_features(senda.compiler.arxml PUBLIC cxx_std_26)
senda_target_settings(senda.compiler.arxml)
