"""Generate C++ source files from the AUTOSAR export model.

Produces:
  - senda.domains.<version>.cppm: Domain builder with FirBuilder API calls + FrozenMap lookup tables
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

    # --- Deduplicate composites (some schemas have duplicate complexTypes) ---
    seen_composites: set[str] = set()
    unique_composites: list[ExportComposite] = []
    for c in schema.composites:
        if c.name not in seen_composites:
            seen_composites.add(c.name)
            unique_composites.append(c)
    composites = unique_composites

    # --- Build name->variable mappings ---
    type_vars: dict[str, str] = {}  # PascalCase name -> C++ variable name

    for p in schema.primitives:
        var = _prim_var(p.name)
        type_vars[p.name] = var

    for e in schema.enums:
        var = _type_var(e.name)
        type_vars[e.name] = var

    for c in composites:
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
    if composites:
        w("    // ── Composites Phase 1: Declare types (%d) ──" % len(composites))
        for c in composites:
            var = type_vars[c.name]
            w('    auto %s = b.begin_type("%s", fir::M3Kind::Composite);' % (var, c.name))
        w("")

        # --- Phase 2: Set supertypes ---
        supertypes = [(c, parent) for c in composites
                      for parent in c.inherits_from if parent in type_vars]
        if supertypes:
            w("    // ── Composites Phase 2: Supertypes ──")
            for c, parent in supertypes:
                w("    b.set_supertype(%s, %s);" % (type_vars[c.name], type_vars[parent]))
            w("")

        # --- Phase 3: Abstract flags ---
        abstracts = [c for c in composites if c.is_abstract]
        if abstracts:
            w("    // ── Composites Phase 3: Abstract flags ──")
            for c in abstracts:
                w("    b.set_abstract(%s, true);" % type_vars[c.name])
            w("")

        # --- Phase 4: Roles ---
        w("    // ── Composites Phase 4: Roles ──")

        # Track role handles per type for lookup table generation
        role_handles: dict[str, list[tuple[str, str, str, str, bool]]] = {}
        # type_name -> [(role_var, member_xml_element_name, role_name, target_type_var, is_reference)]

        for c in composites:
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
                    role_handles[c.name].append((rvar, xml_elem, role_name, target_type, m.is_reference))
                else:
                    w('    b.add_role(%s, "%s", %s, %s);'
                      % (cvar, role_name, target_type, mult))
            if c.members:
                w("")

    # --- Build inner REF role injection map ---
    # When a wrapper member (e.g. I-SIGNAL-PORT-REFS) has inner_ref_tag (e.g. I-SIGNAL-PORT-REF),
    # inject that inner tag as a role entry on the wrapper's target type (e.g. ISignalPort).
    inner_ref_injections: dict[str, list[tuple[str, str, str, str, bool]]] = {}
    # target_type_name -> [(rvar, inner_ref_tag, role_name, target_type_var, is_reference=True)]
    if composites:
        for c in composites:
            for i, m in enumerate(c.members):
                if not m.inner_ref_tag or not m.types:
                    continue
                target_name = m.types[0]
                cvar = type_vars[c.name]
                rvar = _role_var(cvar, i)
                target_var = type_vars.get(target_name, "string_t")
                if target_name not in inner_ref_injections:
                    inner_ref_injections[target_name] = []
                inner_ref_injections[target_name].append(
                    (rvar, m.inner_ref_tag, m.name, target_var, True))

    # --- Collect inherited + inlined (composition-hoisted) roles ---
    composite_by_name: dict[str, ExportComposite] = {c.name: c for c in composites}

    # Build a map from type name to its members (for composition detection)
    members_by_type: dict[str, list[ExportMember]] = {c.name: c.members for c in composites}

    def _inlined_roles(cname: str, visited: set[str] | None = None) -> list[tuple[str, str, str, str, bool]]:
        """Collect roles hoisted from composition members without xml_element_name.

        When a type has a composition member (no xml_element_name) pointing to
        a composite type, that target type's XML children appear directly in
        the parent's XML.  We hoist those roles into the parent's lookup table.

        Handles transitive chains and cycles via visited-set tracking.
        """
        if visited is None:
            visited = set()
        if cname in visited:
            return []
        visited.add(cname)
        result: list[tuple[str, str, str, str, bool]] = []
        for m in members_by_type.get(cname, []):
            if m.xml_element_name is not None:
                continue  # Has its own XML tag — not a composition-inline
            if not m.types:
                continue
            target = m.types[0]
            if target not in composite_by_name:
                continue  # Points to a primitive/enum, not a composite
            # Hoist direct roles from the target type
            for role in role_handles.get(target, []):
                result.append(role)
            # Recursively hoist from the target's own composition members
            for role in _inlined_roles(target, visited):
                result.append(role)
            # Also hoist inherited roles from the target's ancestors
            target_comp = composite_by_name.get(target)
            if target_comp:
                for parent in target_comp.inherits_from:
                    for role in _all_roles_no_inline(parent, set(visited)):
                        result.append(role)
        return result

    def _all_roles_no_inline(cname: str, visited: set[str] | None = None) -> list[tuple[str, str, str, str, bool]]:
        """Collect roles from a type and all ancestors (no composition inlining)."""
        if visited is None:
            visited = set()
        if cname in visited:
            return []
        visited.add(cname)
        result = list(role_handles.get(cname, []))
        comp = composite_by_name.get(cname)
        if comp:
            for parent in comp.inherits_from:
                for role in _all_roles_no_inline(parent, visited):
                    if role[1] not in {r[1] for r in result}:
                        result.append(role)
        return result

    def _all_roles(cname: str, visited: set[str] | None = None) -> list[tuple[str, str, str, str, bool]]:
        """Collect roles from a type, all ancestors, inlined compositions, and injected inner REF roles."""
        if visited is None:
            visited = set()
        if cname in visited:
            return []
        visited.add(cname)
        result = list(role_handles.get(cname, []))
        # Hoist roles from composition members (no xml_element_name)
        # Pass a fresh visited set — _inlined_roles manages its own cycle detection
        for role in _inlined_roles(cname):
            if role[1] not in {r[1] for r in result}:
                result.append(role)
        # Inherit roles from parent types
        comp = composite_by_name.get(cname)
        if comp:
            for parent in comp.inherits_from:
                for role in _all_roles(parent, visited):
                    # Child roles override parent roles with the same xml element
                    if role[1] not in {r[1] for r in result}:
                        result.append(role)
        # Append injected inner REF roles (Pattern B wrappers)
        for role in inner_ref_injections.get(cname, []):
            if role[1] not in {r[1] for r in result}:
                result.append(role)
        return result

    # --- Lookup tables ---
    w("    // ── Lookup Tables ──")
    w("    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type(%d);"
      % len(composites))
    w("")

    for c in composites:
        if not c.xml_name:
            continue
        cvar = type_vars[c.name]
        roles = _all_roles(c.name)

        w("    {")
        w("        TypeInfo info{{%s.id}, kore::FrozenMap<std::string_view, RoleInfo>(%d)};"
          % (cvar, len(roles)))
        for rvar, xml_elem, _role_name, target_type_var, is_ref in roles:
            ref_str = "true" if is_ref else "false"
            w('        info.roles.add("%s", RoleInfo{rupa::domain::RoleHandle{%s.id}, static_cast<uint32_t>(%s.id), %s});'
              % (xml_elem, rvar, target_type_var, ref_str))
        w("        info.roles.freeze();")
        w('        tag_to_type.add("%s", std::move(info));' % c.xml_name)
        w("    }")

    w("    tag_to_type.freeze();")
    w("")

    # --- handle_to_type reverse lookup ---
    w("    kore::FrozenMap<uint32_t, const TypeInfo*> handle_to_type(%d);" % len(composites))
    for c in composites:
        if not c.xml_name:
            continue
        cvar = type_vars[c.name]
        w('    handle_to_type.add(static_cast<uint32_t>(%s.id), tag_to_type.find("%s"));'
          % (cvar, c.xml_name))
    w("    handle_to_type.freeze();")
    w("")
    w('    return AutosarSchema{rupa::domain::Domain("%s", std::move(type_fir)), std::move(tag_to_type), std::move(handle_to_type), "%s"};'
      % (domain, schema.xsd_filename))
    w("}")

    return "\n".join(lines)


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
import senda.domains;

export namespace senda::domains
{

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
            - <output_dir>/domains/senda.domains.<version>.cppm
    """
    generate_domain_module(schema, output_dir)
