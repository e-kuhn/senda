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


def _multiplicity(min_occurs: int | None, max_occurs: int | None) -> str:
    """Map (min, max) to fir::Multiplicity enum value."""
    mn = min_occurs if min_occurs is not None else 0
    mx = max_occurs  # None = unbounded
    if mn == 1 and mx == 1:
        return "fir::Multiplicity::One"
    if mn == 0 and mx == 1:
        return "fir::Multiplicity::Optional"
    if mn == 0 and mx is None:
        return "fir::Multiplicity::Many"
    if mn == 1 and mx is None:
        return "fir::Multiplicity::OneOrMore"
    # For explicit ranges, use closest approximation
    if mn == 0:
        return "fir::Multiplicity::Many"
    return "fir::Multiplicity::OneOrMore"


def _type_var(name: str) -> str:
    """Generate a C++ variable name for a type (snake_case)."""
    return pascal_to_snake(name)


def _prim_var(name: str) -> str:
    """Variable name for a primitive type (snake_case + _t suffix)."""
    return pascal_to_snake(name) + "_t"


def _role_var(type_var: str, index: int) -> str:
    """Variable name for a role handle."""
    return f"{type_var}_r{index}"


def _domain_name(release_version: str) -> str:
    """Convert release version to domain name: R23-11 -> autosar-r23-11."""
    return "autosar-" + release_version.lower()


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

                w('    auto %s = b.add_role(%s, "%s", %s, %s);'
                  % (rvar, cvar, role_name, target_type, mult))

                xml_elem = m.xml_element_name
                if xml_elem:
                    role_handles[c.name].append((rvar, xml_elem, role_name))
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
        w("        TypeInfo info{%s, kore::FrozenMap<std::string_view, rupa::domain::RoleHandle>(%d)};"
          % (cvar, len(roles)))
        for rvar, xml_elem, _role_name in roles:
            w('        info.roles.add("%s", %s);' % (xml_elem, rvar))
        w("        info.roles.freeze();")
        w('        tag_to_type.add("%s", std::move(info));' % c.xml_name)
        w("    }")

    w("    tag_to_type.freeze();")
    w("")
    w('    return AutosarSchema{rupa::domain::Domain("%s", std::move(type_fir)), std::move(tag_to_type)};'
      % domain)
    w("}")

    return "\n".join(lines)


def generate_domain_module(schema: ExportSchema, output_dir: str) -> None:
    """Generate the complete senda.domains.cppm module file."""
    header = '''module;

#include <string_view>
#include <utility>

export module senda.domains;

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

'''

    body = generate_domain_builder(schema)

    footer = '''
}  // namespace senda::domains
'''

    path = os.path.join(output_dir, "domains", "senda.domains.cppm")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(body)
        f.write(footer)
