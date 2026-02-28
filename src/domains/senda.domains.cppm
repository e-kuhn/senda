module;

#include <string_view>

export module senda.domains;

export import kore.containers.frozen_map;
export import rupa.fir;
export import rupa.domain;

export namespace senda::domains
{

struct RoleInfo {
    rupa::domain::RoleHandle role;
    uint32_t target_type_id;  // fir::Id of the target type (for handle_to_type lookup)
    bool is_reference = false;
};

struct TypeInfo {
    rupa::domain::TypeHandle handle;
    kore::FrozenMap<std::string_view, RoleInfo> roles;
};

struct AutosarSchema {
    rupa::domain::Domain domain;
    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type;
    kore::FrozenMap<uint32_t, const TypeInfo*> handle_to_type;
    std::string_view xsd_filename;
};

}  // namespace senda::domains
