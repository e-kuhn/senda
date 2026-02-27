"""Generate C++ ARXML emitter module from the AUTOSAR export model.

Produces:
  - senda.emitter-arxml.cppm: FIR-to-ARXML emitter with reverse lookup tables
"""

from __future__ import annotations

import os
from schema_model import ExportSchema
from name_converter import pascal_to_snake
from cpp_helpers import type_var, prim_var, role_var, domain_name


def _generate_reverse_lookup_builder(schema: ExportSchema) -> str:
    """Generate C++ function that builds reverse lookup tables (type → XML tag)."""
    lines: list[str] = []
    w = lines.append

    # Build variable name mappings (same as domain builder)
    type_vars: dict[str, str] = {}
    for p in schema.primitives:
        type_vars[p.name] = prim_var(p.name)
    for e in schema.enums:
        type_vars[e.name] = type_var(e.name)
    for c in schema.composites:
        type_vars[c.name] = type_var(c.name)

    # Collect composites with XML names and their roles
    type_entries: list[tuple[str, str, list[tuple[str, str, bool]]]] = []
    # (xml_tag, cvar, [(rvar, xml_element, is_identity)])

    for c in schema.composites:
        if not c.xml_name:
            continue
        cvar = type_vars[c.name]
        roles_info: list[tuple[str, str, bool]] = []
        for i, m in enumerate(c.members):
            if m.xml_element_name:
                rvar = role_var(cvar, i)
                roles_info.append((rvar, m.xml_element_name, m.is_identity))
        type_entries.append((c.xml_name, cvar, roles_info))

    w("EmitLookup build_emit_lookup(const senda::domains::AutosarSchema& schema) {")
    w("    const auto& tag_to_type = schema.tag_to_type;")
    w("")
    w("    // ── Reverse Lookup: type → XML tag ──")
    w("    kore::FrozenMap<uint32_t, EmitTypeInfo> type_to_tag(%d);" % len(type_entries))
    w("")

    for xml_name, cvar, roles_info in type_entries:
        w("    {")
        w('        auto* ti = tag_to_type.find("%s");' % xml_name)
        w("        if (ti) {")
        w('            EmitTypeInfo info{"%s", kore::FrozenMap<uint32_t, EmitRoleInfo>(%d)};'
          % (xml_name, len(roles_info)))
        for rvar, xml_elem, is_identity in roles_info:
            identity_str = "true" if is_identity else "false"
            w("            {")
            w('                auto* role = ti->roles.find("%s");' % xml_elem)
            w("                if (role) {")
            w('                    info.role_to_xml.add(static_cast<uint32_t>(role->role.id), EmitRoleInfo{"%s", %s});'
              % (xml_elem, identity_str))
            w("                }")
            w("            }")
        w("            info.role_to_xml.freeze();")
        w("            type_to_tag.add(static_cast<uint32_t>(ti->handle.id), std::move(info));")
        w("        }")
        w("    }")

    w("    type_to_tag.freeze();")
    w("")
    w("    return EmitLookup{std::move(type_to_tag)};")
    w("}")

    return "\n".join(lines)


def generate_arxml_emitter_module(schema: ExportSchema) -> str:
    """Generate the complete senda.emitter.arxml module."""
    release = schema.release_version
    module_version = release.lower().replace("-", "_")  # "r23_11"

    lookup_builder = _generate_reverse_lookup_builder(schema)

    return f'''module;

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <ostream>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

export module senda.emitter.arxml;

import rupa.domain;
import rupa.fir;
import senda.domains;
import senda.domains.{module_version};
import kore.containers.frozen_map;

export namespace senda
{{

struct EmitRoleInfo {{
    std::string_view xml_element;
    bool is_identity;
}};

struct EmitTypeInfo {{
    std::string_view xml_tag;
    kore::FrozenMap<uint32_t, EmitRoleInfo> role_to_xml;
}};

struct EmitLookup {{
    kore::FrozenMap<uint32_t, EmitTypeInfo> type_to_tag;
}};

{lookup_builder}

class ArxmlEmitter {{
public:
    explicit ArxmlEmitter(const senda::domains::AutosarSchema& schema)
        : lookup_(build_emit_lookup(schema)) {{}}

    bool emit(const fir::Fir& fir, std::ostream& out) {{
        // Write XML header
        out << "<?xml version=\\"1.0\\" encoding=\\"UTF-8\\"?>\\n";
        out << "<AUTOSAR>\\n";

        // Walk FIR objects and emit XML
        emit_objects(fir, out, 1);

        out << "</AUTOSAR>\\n";
        return true;
    }}

    bool emit(const fir::Fir& fir, const std::filesystem::path& path) {{
        std::ofstream file(path);
        if (!file) return false;
        return emit(fir, file);
    }}

private:
    EmitLookup lookup_;

    void write_indent(std::ostream& out, int indent) {{
        for (int i = 0; i < indent; ++i) out << "  ";
    }}

    void emit_object(const fir::Fir& fir, const fir::ObjectDef& obj,
                     std::ostream& out, int indent) {{
        // Look up type -> XML tag
        auto* type_info = lookup_.type_to_tag.find(static_cast<uint32_t>(obj.type_id));
        if (!type_info) return;  // Unknown type, skip

        // Write opening tag
        write_indent(out, indent);
        out << "<" << type_info->xml_tag << ">\\n";

        // Write SHORT-NAME (identity)
        auto identity = fir.getString(obj.identity);
        if (!identity.empty()) {{
            write_indent(out, indent + 1);
            out << "<SHORT-NAME>" << identity << "</SHORT-NAME>\\n";
        }}

        // Write properties
        auto props = fir.propertiesOf(obj);
        for (auto prop_id : props) {{
            auto& pv = fir.as<fir::PropertyVal>(prop_id);

            // Look up role -> XML element
            auto* role_info = type_info->role_to_xml.find(
                static_cast<uint32_t>(pv.role_id));
            if (!role_info || role_info->is_identity) continue;

            auto& val_node = fir.get(pv.value_id);
            if (val_node.kind == fir::NodeKind::ObjectDef) {{
                // Nested object — recurse
                auto& nested = fir.as<fir::ObjectDef>(pv.value_id);
                emit_object(fir, nested, out, indent + 1);
            }} else if (val_node.kind == fir::NodeKind::ValueDef) {{
                auto& vd = fir.as<fir::ValueDef>(pv.value_id);
                write_indent(out, indent + 1);
                out << "<" << role_info->xml_element << ">";
                switch (vd.value_kind) {{
                case fir::ValueKind::String:
                    out << fir.getString(vd.string_val);
                    break;
                case fir::ValueKind::Integer:
                    out << vd.int_val;
                    break;
                case fir::ValueKind::Float:
                    out << vd.float_val;
                    break;
                case fir::ValueKind::Boolean:
                    out << (vd.bool_val ? "true" : "false");
                    break;
                default:
                    break;
                }}
                out << "</" << role_info->xml_element << ">\\n";
            }}
        }}

        // Write closing tag
        write_indent(out, indent);
        out << "</" << type_info->xml_tag << ">\\n";
    }}

    void emit_objects(const fir::Fir& fir, std::ostream& out, int indent) {{
        // Collect IDs of objects that are nested (referenced as containment values)
        // so we only emit top-level objects at this level
        std::vector<uint32_t> nested_ids;
        fir.forEachNode([&](fir::Id id, const fir::Node& node) {{
            if (node.kind != fir::NodeKind::ObjectDef) return;
            auto& obj = fir.as<fir::ObjectDef>(id);
            auto props = fir.propertiesOf(obj);
            for (auto prop_id : props) {{
                auto& pv = fir.as<fir::PropertyVal>(prop_id);
                auto& val_node = fir.get(pv.value_id);
                if (val_node.kind == fir::NodeKind::ObjectDef) {{
                    nested_ids.push_back(static_cast<uint32_t>(pv.value_id));
                }}
            }}
        }});

        // Emit only top-level objects
        fir.forEachNode([&](fir::Id id, const fir::Node& node) {{
            if (node.kind != fir::NodeKind::ObjectDef) return;
            auto raw = static_cast<uint32_t>(id);
            for (auto nid : nested_ids) {{
                if (nid == raw) return;
            }}
            auto& obj = fir.as<fir::ObjectDef>(id);
            emit_object(fir, obj, out, indent);
        }});
    }}
}};

}}  // namespace senda
'''


def generate_emitter_module(schema: ExportSchema, output_dir: str) -> None:
    """Generate the senda.emitter-arxml.cppm module file."""
    code = generate_arxml_emitter_module(schema)
    emitter_dir = os.path.join(output_dir, "emitter-arxml")
    os.makedirs(emitter_dir, exist_ok=True)
    path = os.path.join(emitter_dir, "senda.emitter-arxml.cppm")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
