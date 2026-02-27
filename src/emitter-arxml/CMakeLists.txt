add_library(senda.emitter.arxml)
target_sources(senda.emitter.arxml
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.emitter-arxml.cppm
)
target_link_libraries(senda.emitter.arxml
    PUBLIC rupa.fir rupa.domain senda.domains kore
)
target_compile_features(senda.emitter.arxml PUBLIC cxx_std_26)
senda_target_settings(senda.emitter.arxml)
