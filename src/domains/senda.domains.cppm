module;

#include <cstdint>
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

// ── Data-driven domain descriptor types ──

struct TypeDesc {
    std::string_view name;
    uint8_t kind;           // fir::M3Kind as integer (Composite=0, Primitive=1, Enum=4)
    uint16_t supertype;     // index into types array, UINT16_MAX = none
    bool is_abstract;
    uint16_t role_start;    // index into roles array
    uint16_t role_count;
    uint16_t enum_start;    // index into enum_values array
    uint16_t enum_count;
};

struct RoleDesc {
    std::string_view name;
    uint16_t target_type;   // index into types array
    uint8_t mult;           // fir::Multiplicity as integer (One=0, Optional=1, Many=2, OneOrMore=3)
};

struct EnumValDesc {
    std::string_view value;
};

}  // namespace senda::domains
