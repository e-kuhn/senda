add_library(senda.compiler.arxml)
target_sources(senda.compiler.arxml
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.compiler-arxml.cppm
)
target_link_libraries(senda.compiler.arxml
    PUBLIC rupa.compiler rupa.fir.builder rupa.domain rupa.fir kore
    PRIVATE pugixml::pugixml
)
target_compile_features(senda.compiler.arxml PUBLIC cxx_std_26)
senda_target_settings(senda.compiler.arxml)
