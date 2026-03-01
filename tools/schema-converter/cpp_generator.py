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
    multiplicity_index as _mult_idx,
)


def generate_domain_builder(schema: ExportSchema) -> str:
    """Generate the C++ domain builder function body with static data arrays."""
    lines: list[str] = []
    w = lines.append

    release = schema.release_version
    domain = _domain_name(release)

    # --- Deduplicate composites ---
    seen_composites: set[str] = set()
    unique_composites: list[ExportComposite] = []
    for c in schema.composites:
        if c.name not in seen_composites:
            seen_composites.add(c.name)
            unique_composites.append(c)
    composites = unique_composites

    # --- Assign sequential type indices ---
    # Order: primitives, enums, composites
    type_index: dict[str, int] = {}
    all_types: list = []  # (name, kind_int, supertype_idx, is_abstract, members, is_enum, enum_values)

    for p in schema.primitives:
        type_index[p.name] = len(all_types)
        all_types.append((p.name, 1, None, False, [], False, []))  # M3Kind::Primitive = 1

    for e in schema.enums:
        type_index[e.name] = len(all_types)
        all_types.append((e.name, 4, None, False, [], True, e.values))  # M3Kind::Enum = 4

    for c in composites:
        type_index[c.name] = len(all_types)
        all_types.append((c.name, 0, None, c.is_abstract, c.members, False, []))  # M3Kind::Composite = 0

    # --- Build flat role list ---
    role_list: list[tuple[str, int, int]] = []  # (name, target_type_idx, mult_idx)
    role_starts: list[int] = []
    role_counts: list[int] = []
    # Also track (type_index, member_index) -> role_index for lookup table generation
    role_index_map: dict[tuple[int, int], int] = {}

    for ti, (tname, kind, _, _, members, is_enum, _) in enumerate(all_types):
        start = len(role_list)
        count = 0
        for mi, m in enumerate(members):
            role_name = ".." if m.name is None else m.name
            target_idx = 0  # fallback
            if m.types:
                first_type = m.types[0]
                if first_type in type_index:
                    target_idx = type_index[first_type]
            mult = _mult_idx(m.min_occurs, m.max_occurs)
            if m.xml_element_name:
                role_index_map[(ti, mi)] = len(role_list)
            role_list.append((role_name, target_idx, mult))
            count += 1
        role_starts.append(start)
        role_counts.append(count)

    # --- Build flat enum value list ---
    enum_list: list[str] = []
    enum_starts: list[int] = []
    enum_counts: list[int] = []

    for ti, (tname, kind, _, _, _, is_enum, values) in enumerate(all_types):
        start = len(enum_list)
        count = 0
        if is_enum:
            for v in values:
                enum_list.append(v)
                count += 1
        enum_starts.append(start)
        enum_counts.append(count)

    # --- Resolve supertypes ---
    supertype_indices: list[int] = []
    for ti, (tname, kind, _, _, _, _, _) in enumerate(all_types):
        sup = 0xFFFF
        if kind == 0:  # Composite
            # Find the ExportComposite
            ci = ti - len(schema.primitives) - len(schema.enums)
            if 0 <= ci < len(composites):
                c = composites[ci]
                for parent in c.inherits_from:
                    if parent in type_index:
                        sup = type_index[parent]
                        break  # Only first supertype
        supertype_indices.append(sup)

    # --- Build role_handles equivalent for lookup tables ---
    # Map: type_name -> [(role_global_idx, xml_element_name, role_name, target_type_idx, is_reference)]
    composite_by_name: dict[str, ExportComposite] = {c.name: c for c in composites}
    members_by_type: dict[str, list[ExportMember]] = {c.name: c.members for c in composites}

    role_handles: dict[str, list[tuple[int, str, str, int, bool]]] = {}
    for c in composites:
        ti = type_index[c.name]
        role_handles[c.name] = []
        for mi, m in enumerate(c.members):
            if m.xml_element_name:
                ri = role_index_map.get((ti, mi))
                if ri is not None:
                    target_idx = 0
                    if m.types and m.types[0] in type_index:
                        target_idx = type_index[m.types[0]]
                    role_handles[c.name].append(
                        (ri, m.xml_element_name, m.name or "..", target_idx, m.is_reference))

    # --- Build inner REF injection map ---
    inner_ref_injections: dict[str, list[tuple[int, str, str, int, bool]]] = {}
    for c in composites:
        ti = type_index[c.name]
        for mi, m in enumerate(c.members):
            if not m.inner_ref_tag or not m.types:
                continue
            target_name = m.types[0]
            ri = role_index_map.get((ti, mi))
            if ri is None:
                continue
            target_idx = type_index.get(target_name, 0)
            if target_name not in inner_ref_injections:
                inner_ref_injections[target_name] = []
            inner_ref_injections[target_name].append(
                (ri, m.inner_ref_tag, m.name or "..", target_idx, True))

    # --- Collect inherited + inlined roles (same logic as before) ---
    def _inlined_roles(cname: str, visited: set[str] | None = None) -> list[tuple[int, str, str, int, bool]]:
        if visited is None:
            visited = set()
        if cname in visited:
            return []
        visited.add(cname)
        result: list[tuple[int, str, str, int, bool]] = []
        for m in members_by_type.get(cname, []):
            if m.xml_element_name is not None:
                continue
            if not m.types:
                continue
            target = m.types[0]
            if target not in composite_by_name:
                continue
            for role in role_handles.get(target, []):
                result.append(role)
            for role in _inlined_roles(target, visited):
                result.append(role)
            target_comp = composite_by_name.get(target)
            if target_comp:
                for parent in target_comp.inherits_from:
                    for role in _all_roles_no_inline(parent, set(visited)):
                        result.append(role)
        return result

    def _all_roles_no_inline(cname: str, visited: set[str] | None = None) -> list[tuple[int, str, str, int, bool]]:
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

    def _all_roles(cname: str, visited: set[str] | None = None) -> list[tuple[int, str, str, int, bool]]:
        if visited is None:
            visited = set()
        if cname in visited:
            return []
        visited.add(cname)
        result = list(role_handles.get(cname, []))
        for role in _inlined_roles(cname):
            if role[1] not in {r[1] for r in result}:
                result.append(role)
        comp = composite_by_name.get(cname)
        if comp:
            for parent in comp.inherits_from:
                for role in _all_roles(parent, visited):
                    if role[1] not in {r[1] for r in result}:
                        result.append(role)
        for role in inner_ref_injections.get(cname, []):
            if role[1] not in {r[1] for r in result}:
                result.append(role)
        return result

    # --- Build flat tag and tag-role lists ---
    tag_list: list[tuple[str, int, int, int]] = []  # (xml_tag, type_idx, tag_role_start, tag_role_count)
    tag_role_list: list[tuple[str, int, int, bool]] = []  # (xml_elem, role_idx, target_type_idx, is_ref)

    for c in composites:
        if not c.xml_name:
            continue
        ti = type_index[c.name]
        roles = _all_roles(c.name)
        tr_start = len(tag_role_list)
        for ri, xml_elem, _rn, target_idx, is_ref in roles:
            tag_role_list.append((xml_elem, ri, target_idx, is_ref))
        tag_list.append((c.xml_name, ti, tr_start, len(tag_role_list) - tr_start))

    # --- Emit static arrays ---
    N = len(all_types)

    w("// ── Static type descriptors (%d) ──" % N)
    w("constexpr TypeDesc kTypes[] = {")
    for ti in range(N):
        name = all_types[ti][0]
        kind = all_types[ti][1]
        sup = supertype_indices[ti]
        abstract = all_types[ti][3]
        rs = role_starts[ti]
        rc = role_counts[ti]
        es = enum_starts[ti]
        ec = enum_counts[ti]
        w('    {"%s", %d, %d, %s, %d, %d, %d, %d},'
          % (name, kind, sup, "true" if abstract else "false", rs, rc, es, ec))
    w("};")
    w("")

    if role_list:
        w("// ── Static role descriptors (%d) ──" % len(role_list))
        w("constexpr RoleDesc kRoles[] = {")
        for rname, target_idx, mult in role_list:
            w('    {"%s", %d, %d},' % (rname, target_idx, mult))
        w("};")
    else:
        w("constexpr RoleDesc kRoles[] = {};")
    w("")

    if enum_list:
        w("// ── Static enum value descriptors (%d) ──" % len(enum_list))
        w("constexpr EnumValDesc kEnumValues[] = {")
        for v in enum_list:
            w('    {"%s"},' % v)
        w("};")
    else:
        w("constexpr EnumValDesc kEnumValues[] = {};")
    w("")

    if tag_role_list:
        w("// ── Lookup tag-role descriptors (%d) ──" % len(tag_role_list))
        w("constexpr TagRoleDesc kTagRoles[] = {")
        for xml_elem, ri, target_idx, is_ref in tag_role_list:
            w('    {"%s", %d, %d, %s},'
              % (xml_elem, ri, target_idx, "true" if is_ref else "false"))
        w("};")
    else:
        w("constexpr TagRoleDesc kTagRoles[] = {};")
    w("")

    if tag_list:
        w("// ── Lookup tag descriptors (%d) ──" % len(tag_list))
        w("constexpr TagDesc kTags[] = {")
        for xml_tag, ti, tr_start, tr_count in tag_list:
            w('    {"%s", %d, %d, %d},' % (xml_tag, ti, tr_start, tr_count))
        w("};")
    else:
        w("constexpr TagDesc kTags[] = {};")
    w("")

    # --- Emit driver function ---
    func_name = "build_" + pascal_to_snake(_domain_name(release).replace("-", "_"))
    w("AutosarSchema %s() {" % func_name)
    w("    fir::Fir type_fir;")
    w("    rupa::fir_builder::FirBuilder b(type_fir);")
    w("")
    w("    constexpr size_t N = std::size(kTypes);")
    w("    std::vector<rupa::fir_builder::TypeHandle> th(N);")
    w("    for (size_t i = 0; i < N; ++i)")
    w("        th[i] = b.begin_type(kTypes[i].name, static_cast<fir::M3Kind>(kTypes[i].kind));")
    w("")
    w("    for (size_t i = 0; i < N; ++i) {")
    w("        if (kTypes[i].supertype != UINT16_MAX)")
    w("            b.set_supertype(th[i], th[kTypes[i].supertype]);")
    w("        if (kTypes[i].is_abstract)")
    w("            b.set_abstract(th[i], true);")
    w("    }")
    w("")
    w("    for (size_t i = 0; i < N; ++i)")
    w("        for (uint16_t j = 0; j < kTypes[i].enum_count; ++j)")
    w("            b.add_enum_value(th[i], kEnumValues[kTypes[i].enum_start + j].value);")
    w("")
    w("    std::vector<rupa::fir_builder::RoleHandle> rh(std::size(kRoles));")
    w("    for (size_t i = 0; i < N; ++i)")
    w("        for (uint16_t j = 0; j < kTypes[i].role_count; ++j) {")
    w("            auto ri = kTypes[i].role_start + j;")
    w("            rh[ri] = b.add_role(th[i], kRoles[ri].name,")
    w("                                th[kRoles[ri].target_type],")
    w("                                static_cast<fir::Multiplicity>(kRoles[ri].mult));")
    w("        }")
    w("")
    w("    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type(std::size(kTags));")
    w("    for (const auto& tag : kTags) {")
    w("        TypeInfo info{{th[tag.type_index].id},")
    w("                      kore::FrozenMap<std::string_view, RoleInfo>(tag.tag_role_count)};")
    w("        for (uint16_t j = 0; j < tag.tag_role_count; ++j) {")
    w("            const auto& tr = kTagRoles[tag.tag_role_start + j];")
    w("            info.roles.add(tr.xml_element_name,")
    w("                RoleInfo{rupa::domain::RoleHandle{rh[tr.role_index].id},")
    w("                         static_cast<uint32_t>(th[tr.target_type].id),")
    w("                         tr.is_reference});")
    w("        }")
    w("        info.roles.freeze();")
    w("        tag_to_type.add(tag.xml_tag, std::move(info));")
    w("    }")
    w("    tag_to_type.freeze();")
    w("")
    w("    kore::FrozenMap<uint32_t, const TypeInfo*> handle_to_type(std::size(kTags));")
    w("    for (const auto& tag : kTags)")
    w("        handle_to_type.add(static_cast<uint32_t>(th[tag.type_index].id),")
    w("                          tag_to_type.find(tag.xml_tag));")
    w("    handle_to_type.freeze();")
    w("")
    w('    return AutosarSchema{rupa::domain::Domain("%s", std::move(type_fir)),'
      % domain)
    w('                         std::move(tag_to_type), std::move(handle_to_type), "%s"};'
      % schema.xsd_filename)
    w("}")

    return "\n".join(lines)


def generate_domain_module(schema: ExportSchema, output_dir: str) -> None:
    """Generate a version-specific domain module file."""
    release = schema.release_version
    version_slug = release.lower()           # "r23-11"
    module_version = version_slug.replace("-", "_")  # "r23_11"

    header = '''module;

#include <cstdint>
#include <string_view>
#include <utility>
#include <vector>

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
