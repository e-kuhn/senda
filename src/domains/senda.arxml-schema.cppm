module;

#include <cstdint>
#include <string_view>

export module senda.arxml_schema;

export namespace senda::arxml
{

// ── XML serialization tag bits (packed into uint8_t) ──

enum XmlTagBits : uint8_t {
    RoleElement        = 1 << 0,
    RoleWrapperElement = 1 << 1,
    TypeElement        = 1 << 2,
    TypeWrapperElement = 1 << 3,
    Attribute          = 1 << 4,
};

// ── Classified XML pattern for dispatch ──

enum class XmlPattern : uint8_t {
    RoleOnly,       // rE=T — element name = role, direct containment or scalar
    WrapperRole,    // rE=T, rWE=T — wrapper + role children
    WrapperType,    // rWE=T, tE=T — wrapper + polymorphic type children
    WrapperOnly,    // rWE=T only — wrapper, children from group ref
    TypeOnly,       // tE=T only — polymorphic type element
    Flattened,      // all false — content inlined into parent
    Attribute,      // xml.attribute=T — XML attribute, not element
};

constexpr XmlPattern classify_xml_tags(uint8_t tags) {
    if (tags & Attribute) return XmlPattern::Attribute;
    bool rE  = tags & RoleElement;
    bool rWE = tags & RoleWrapperElement;
    bool tE  = tags & TypeElement;
    if (rE && rWE)  return XmlPattern::WrapperRole;
    if (rWE && tE)  return XmlPattern::WrapperType;
    if (rWE)        return XmlPattern::WrapperOnly;
    if (tE)         return XmlPattern::TypeOnly;
    if (rE)         return XmlPattern::RoleOnly;
    return XmlPattern::Flattened;
}

// ── ARXML-specific lookup descriptors ──

struct TagRoleDesc {
    std::string_view xml_element_name;
    uint16_t role_index;
    uint16_t target_type;
    bool is_reference;
    uint8_t xml_tags;        // packed XmlTagBits
    int16_t sequence_offset;
};

struct TagDesc {
    std::string_view xml_tag;
    uint16_t type_index;
    uint16_t tag_role_start;
    uint16_t tag_role_count;
};

}  // namespace senda::arxml
