module;

#include <string_view>

export module senda.domains;

export import kore.containers.frozen_map;
export import rupa.fir;
export import rupa.domain;

export namespace senda::domains
{

struct TypeInfo {
    rupa::domain::TypeHandle handle;
    kore::FrozenMap<std::string_view, rupa::domain::RoleHandle> roles;
};

struct AutosarSchema {
    rupa::domain::Domain domain;
    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type;
    std::string_view xsd_filename;
};

}  // namespace senda::domains
