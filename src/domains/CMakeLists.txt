add_library(senda.domains)
target_sources(senda.domains
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.domains.cppm
        senda.arxml-schema.cppm
        senda.domains.r19-11.cppm
        senda.domains.r20-11.cppm
        senda.domains.r21-11.cppm
        senda.domains.r22-11.cppm
        senda.domains.r23-11.cppm
)
target_link_libraries(senda.domains
    PUBLIC rupa.domain rupa.fir rupa.fir.builder kore
)
target_compile_features(senda.domains PUBLIC cxx_std_26)
senda_target_settings(senda.domains)
