"""Generate C++ source files from the AUTOSAR export model.

Produces:
  - senda.domains.cppm: Domain builder with FirBuilder API calls + FrozenMap lookup tables
  - senda.compiler-arxml.cppm: SAX-based ARXML parser using expat
"""

from __future__ import annotations

import os
from schema_model import (
    ExportSchema, ExportPrimitive, ExportEnum, ExportComposite,
    ExportMember, PrimitiveSupertype,
)
from name_converter import pascal_to_snake
from cpp_helpers import (
    multiplicity_str as _multiplicity,
    safe_var as _safe_var,
    type_var as _type_var,
    prim_var as _prim_var,
    role_var as _role_var,
    domain_name as _domain_name,
)


def generate_domain_builder(schema: ExportSchema) -> str:
    """Generate the C++ domain builder function body."""
    lines: list[str] = []
    w = lines.append

    release = schema.release_version
    domain = _domain_name(release)

    # --- Build name->variable mappings ---
    type_vars: dict[str, str] = {}  # PascalCase name -> C++ variable name

    for p in schema.primitives:
        var = _prim_var(p.name)
        type_vars[p.name] = var

    for e in schema.enums:
        var = _type_var(e.name)
        type_vars[e.name] = var

    for c in schema.composites:
        var = _type_var(c.name)
        type_vars[c.name] = var

    # --- Emit function ---
    func_name = "build_" + pascal_to_snake(_domain_name(release).replace("-", "_"))
    w("AutosarSchema %s() {" % func_name)
    w("    fir::Fir type_fir;")
    w("    rupa::fir_builder::FirBuilder b(type_fir);")
    w("")

    # --- Primitives ---
    if schema.primitives:
        w("    // ── Primitives (%d) ──" % len(schema.primitives))
        for p in schema.primitives:
            var = type_vars[p.name]
            w('    auto %s = b.begin_type("%s", fir::M3Kind::Primitive);' % (var, p.name))
        w("")

    # --- Enums ---
    if schema.enums:
        w("    // ── Enums (%d) ──" % len(schema.enums))
        for e in schema.enums:
            var = type_vars[e.name]
            w('    auto %s = b.begin_type("%s", fir::M3Kind::Enum);' % (var, e.name))
            for val in e.values:
                w('    b.add_enum_value(%s, "%s");' % (var, val))
            w("")

    # --- Composites Phase 1: Declare all types ---
    if schema.composites:
        w("    // ── Composites Phase 1: Declare types (%d) ──" % len(schema.composites))
        for c in schema.composites:
            var = type_vars[c.name]
            w('    auto %s = b.begin_type("%s", fir::M3Kind::Composite);' % (var, c.name))
        w("")

        # --- Phase 2: Set supertypes ---
        supertypes = [(c, parent) for c in schema.composites
                      for parent in c.inherits_from if parent in type_vars]
        if supertypes:
            w("    // ── Composites Phase 2: Supertypes ──")
            for c, parent in supertypes:
                w("    b.set_supertype(%s, %s);" % (type_vars[c.name], type_vars[parent]))
            w("")

        # --- Phase 3: Abstract flags ---
        abstracts = [c for c in schema.composites if c.is_abstract]
        if abstracts:
            w("    // ── Composites Phase 3: Abstract flags ──")
            for c in abstracts:
                w("    b.set_abstract(%s, true);" % type_vars[c.name])
            w("")

        # --- Phase 4: Roles ---
        w("    // ── Composites Phase 4: Roles ──")

        # Track role handles per type for lookup table generation
        role_handles: dict[str, list[tuple[str, str, str]]] = {}
        # type_name -> [(role_var, member_xml_element_name, role_name)]

        for c in schema.composites:
            cvar = type_vars[c.name]
            role_handles[c.name] = []
            for i, m in enumerate(c.members):
                rvar = _role_var(cvar, i)
                role_name = ".." if m.name is None else m.name

                # Resolve target type
                target_type = "string_t"  # fallback
                if m.types:
                    first_type = m.types[0]
                    if first_type in type_vars:
                        target_type = type_vars[first_type]

                mult = _multiplicity(m.min_occurs, m.max_occurs)

                xml_elem = m.xml_element_name
                if xml_elem:
                    w('    auto %s = b.add_role(%s, "%s", %s, %s);'
                      % (rvar, cvar, role_name, target_type, mult))
                    role_handles[c.name].append((rvar, xml_elem, role_name))
                else:
                    w('    b.add_role(%s, "%s", %s, %s);'
                      % (cvar, role_name, target_type, mult))
            if c.members:
                w("")

    # --- Lookup tables ---
    w("    // ── Lookup Tables ──")
    w("    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type(%d);"
      % len(schema.composites))
    w("")

    for c in schema.composites:
        if not c.xml_name:
            continue
        cvar = type_vars[c.name]
        roles = role_handles.get(c.name, [])

        w("    {")
        w("        TypeInfo info{{%s.id}, kore::FrozenMap<std::string_view, rupa::domain::RoleHandle>(%d)};"
          % (cvar, len(roles)))
        for rvar, xml_elem, _role_name in roles:
            w('        info.roles.add("%s", rupa::domain::RoleHandle{%s.id});' % (xml_elem, rvar))
        w("        info.roles.freeze();")
        w('        tag_to_type.add("%s", std::move(info));' % c.xml_name)
        w("    }")

    w("    tag_to_type.freeze();")
    w("")
    w('    return AutosarSchema{rupa::domain::Domain("%s", std::move(type_fir)), std::move(tag_to_type)};'
      % domain)
    w("}")

    return "\n".join(lines)


def generate_arxml_module(schema: ExportSchema) -> str:
    """Generate the complete senda.compiler-arxml.cppm SAX parser module."""
    release = schema.release_version
    domain = _domain_name(release)
    module_version = release.lower().replace("-", "_")  # "r23_11"

    return '''module;

#include <cstring>
#include <filesystem>
#include <fstream>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
#include <expat.h>

export module senda.compiler.arxml;

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;
import senda.domains.{module_version};

export namespace senda
{{

class ArxmlCompiler : public rupa::compiler::Compiler {{
public:
    explicit ArxmlCompiler(const senda::domains::AutosarSchema& schema)
        : schema_(schema) {{}}

    std::span<const std::string_view> extensions() const override {{
        return exts_;
    }}

    rupa::compiler::CompileResult compile(
        const std::filesystem::path& path,
        rupa::compiler::CompileContext& context) override
    {{
        rupa::compiler::Diagnostics diags;

        // Read file content
        std::ifstream file(path, std::ios::binary | std::ios::ate);
        if (!file) {{
            diags.add({{rupa::compiler::Severity::Error,
                       "cannot open file: " + path.string(),
                       {{path.string(), 0, 0}}}});
            return rupa::compiler::CompileResult(
                fir::Fir{{}}, rupa::compiler::DomainExtensions{{}}, std::move(diags));
        }}
        auto size = file.tellg();
        file.seekg(0);
        std::string content(static_cast<size_t>(size), '\\0');
        file.read(content.data(), size);

        // Create expat parser
        XML_Parser parser = XML_ParserCreate(nullptr);
        if (!parser) {{
            diags.add({{rupa::compiler::Severity::Error,
                       "failed to create XML parser",
                       {{path.string(), 0, 0}}}});
            return rupa::compiler::CompileResult(
                fir::Fir{{}}, rupa::compiler::DomainExtensions{{}}, std::move(diags));
        }}

        // Set up parse state
        fir::Fir fir;
        rupa::fir_builder::FirBuilder builder(fir);

        (void)context;

        ParseState state{{
            .schema = schema_,
            .builder = builder,
            .diags = diags,
            .file_path = path.string(),
            .stack = {{}},
        }};

        XML_SetUserData(parser, &state);
        XML_SetElementHandler(parser, on_start_element, on_end_element);
        XML_SetCharacterDataHandler(parser, on_characters);

        // Parse
        if (XML_Parse(parser, content.data(), static_cast<int>(content.size()), XML_TRUE)
            == XML_STATUS_ERROR) {{
            diags.add({{rupa::compiler::Severity::Error,
                       std::string("XML parse error: ")
                           + XML_ErrorString(XML_GetErrorCode(parser))
                           + " at line "
                           + std::to_string(XML_GetCurrentLineNumber(parser)),
                       {{path.string(),
                         static_cast<uint32_t>(XML_GetCurrentLineNumber(parser)), 0}}}});
        }}

        XML_ParserFree(parser);

        return rupa::compiler::CompileResult(
            std::move(fir), rupa::compiler::DomainExtensions{{}}, std::move(diags));
    }}

private:
    static constexpr std::string_view exts_arr_[] = {{".arxml"}};
    std::span<const std::string_view> exts_{{exts_arr_}};
    const senda::domains::AutosarSchema& schema_;

    // --- SAX state machine ---

    enum class FrameKind {{ Object, Property, Skip }};

    struct Frame {{
        FrameKind kind;
        // Object frame
        rupa::fir_builder::ObjectHandle obj{{}};
        const senda::domains::TypeInfo* type_info = nullptr;
        // Property frame
        rupa::domain::RoleHandle role{{}};
        rupa::fir_builder::ObjectHandle parent_obj{{}};
        std::string text;
        bool is_identity = false;  // true for SHORT-NAME capture
        // Skip frame
        int skip_depth = 0;
    }};

    struct ParseState {{
        const senda::domains::AutosarSchema& schema;
        rupa::fir_builder::FirBuilder& builder;
        rupa::compiler::Diagnostics& diags;
        std::string file_path;
        std::vector<Frame> stack;
    }};

    static void XMLCALL on_start_element(void* user_data, const XML_Char* name,
                                          const XML_Char** /*attrs*/) {{
        auto& state = *static_cast<ParseState*>(user_data);
        std::string_view tag(name);

        // Strip namespace prefix if present (e.g., "AR:AUTOSAR" -> "AUTOSAR")
        if (auto pos = tag.find(':'); pos != std::string_view::npos) {{
            tag = tag.substr(pos + 1);
        }}

        // If top of stack is Skip, increment depth
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Skip) {{
            state.stack.back().skip_depth++;
            return;
        }}

        // Try type lookup
        auto* type_info = state.schema.tag_to_type.find(tag);
        if (type_info) {{
            // Known type element — create object
            Frame frame{{}};
            frame.kind = FrameKind::Object;
            frame.type_info = type_info;
            // Identity will be set when we see SHORT-NAME
            frame.obj = {{}};  // deferred
            state.stack.push_back(std::move(frame));
            return;
        }}

        // If we're inside an Object frame, check for SHORT-NAME or role lookup
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Object) {{
            auto& parent = state.stack.back();

            // SHORT-NAME provides the identity for the parent object
            if (tag == "SHORT-NAME" && !parent.obj.valid()) {{
                Frame frame{{}};
                frame.kind = FrameKind::Property;
                frame.is_identity = true;
                state.stack.push_back(std::move(frame));
                return;
            }}

            if (parent.type_info) {{
                auto* role = parent.type_info->roles.find(tag);
                if (role) {{
                    Frame frame{{}};
                    frame.kind = FrameKind::Property;
                    frame.role = *role;
                    frame.parent_obj = parent.obj;
                    state.stack.push_back(std::move(frame));
                    return;
                }}
            }}
        }}

        // If we're inside a Property frame, try type lookup (contained object)
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Property) {{
            auto* nested_type_info = state.schema.tag_to_type.find(tag);
            if (nested_type_info) {{
                Frame frame{{}};
                frame.kind = FrameKind::Object;
                frame.type_info = nested_type_info;
                frame.obj = {{}};
                state.stack.push_back(std::move(frame));
                return;
            }}
        }}

        // Unknown element — skip
        Frame frame{{}};
        frame.kind = FrameKind::Skip;
        frame.skip_depth = 1;
        state.stack.push_back(std::move(frame));
    }}

    static void XMLCALL on_end_element(void* user_data, const XML_Char* /*name*/) {{
        auto& state = *static_cast<ParseState*>(user_data);

        if (state.stack.empty()) return;

        auto& frame = state.stack.back();

        switch (frame.kind) {{
        case FrameKind::Skip:
            if (--frame.skip_depth > 0) return;
            break;

        case FrameKind::Property:
            if (frame.is_identity && !frame.text.empty()) {{
                // SHORT-NAME captured — create the parent object
                if (state.stack.size() >= 2) {{
                    auto& parent = state.stack[state.stack.size() - 2];
                    if (parent.kind == FrameKind::Object && parent.type_info
                        && !parent.obj.valid()) {{
                        parent.obj = state.builder.begin_object(
                            std::string_view(frame.text),
                            rupa::fir_builder::TypeHandle{{parent.type_info->handle.id}});
                    }}
                }}
            }} else if (!frame.text.empty() && frame.parent_obj.valid()) {{
                // Regular property — add to parent object
                state.builder.add_property(
                    frame.parent_obj, rupa::fir_builder::RoleHandle{{frame.role.id}},
                    std::string_view(frame.text));
            }}
            break;

        case FrameKind::Object:
            // Object finalization is implicit (FirBuilder tracks current object)
            break;
        }}

        state.stack.pop_back();
    }}

    static void XMLCALL on_characters(void* user_data, const XML_Char* s, int len) {{
        auto& state = *static_cast<ParseState*>(user_data);

        if (state.stack.empty()) return;

        auto& frame = state.stack.back();
        if (frame.kind == FrameKind::Property) {{
            frame.text.append(s, static_cast<size_t>(len));
        }}
    }}
}};

}}  // namespace senda
'''.format(module_version=module_version)


def generate_domain_module(schema: ExportSchema, output_dir: str) -> None:
    """Generate a version-specific domain module file."""
    release = schema.release_version
    version_slug = release.lower()           # "r23-11"
    module_version = version_slug.replace("-", "_")  # "r23_11"

    header = '''module;

#include <string_view>
#include <utility>

export module senda.domains.%s;

import kore.containers.frozen_map;
import rupa.fir;
import rupa.fir.builder;
import rupa.domain;

export namespace senda::domains
{

struct TypeInfo {
    rupa::domain::TypeHandle handle;
    kore::FrozenMap<std::string_view, rupa::domain::RoleHandle> roles;
};

struct AutosarSchema {
    rupa::domain::Domain domain;
    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type;
};

''' % module_version

    body = generate_domain_builder(schema)

    footer = '''
}  // namespace senda::domains
'''

    filename = "senda.domains.%s.cppm" % version_slug
    path = os.path.join(output_dir, "domains", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(body)
        f.write(footer)


def generate_cpp_files(schema: ExportSchema, output_dir: str) -> None:
    """Generate all C++ files from the schema.

    Args:
        schema: The exported schema model.
        output_dir: Base output directory (e.g., 'src/'). Files are written to:
            - <output_dir>/domains/senda.domains.cppm
            - <output_dir>/compiler-arxml/senda.compiler-arxml.cppm
    """
    generate_domain_module(schema, output_dir)

    # Write parser module
    parser_code = generate_arxml_module(schema)
    parser_dir = os.path.join(output_dir, "compiler-arxml")
    os.makedirs(parser_dir, exist_ok=True)
    parser_path = os.path.join(parser_dir, "senda.compiler-arxml.cppm")
    with open(parser_path, "w", encoding="utf-8") as f:
        f.write(parser_code)
