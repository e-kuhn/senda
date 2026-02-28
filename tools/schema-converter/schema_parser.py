"""AUTOSAR XSD schema parser.

Parses AUTOSAR XSD schema files into an internal model (InternalSchema),
then exports to a consumer-facing model (ExportSchema).

Based on the meta-model-generator/schema_analyzer.py blueprint, rewritten
to use the dataclass models from schema_model.py.
"""

from __future__ import annotations

import os
import re
from xml.etree import ElementTree

from name_converter import xml_to_pascal_case, extract_qualified_name, normalize_member_name
from schema_model import (
    ExportComposite,
    ExportEnum,
    ExportMember,
    ExportPrimitive,
    ExportSchema,
    InternalAlias,
    InternalComplexType,
    InternalEnumeration,
    InternalMember,
    InternalPrimitiveType,
    InternalSchema,
    InternalSubTypesEnum,
    InternalType,
    PrimitiveSupertype,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_XSD_NS = {"xsd": "http://www.w3.org/2001/XMLSchema"}

_MIN_OCCURS_RE = re.compile(r'pureMM\.minOccurs="(\d+|\w+)"')
_MAX_OCCURS_RE = re.compile(r'pureMM\.maxOccurs="(-?\d+|\w+)"')

_RELEASE_RE = re.compile(r"Part of AUTOSAR Release:\s*(R\d\d-\d\d)")
_VERSION_RE = re.compile(r"Covered Standards:\s*(\d\.\d\.\d)")
_MAX_HEADER_LINES = 20

_PRIM_ALIAS: dict[str, str] = {
    "string": "StringSimple",
    "INTEGER": "IntegerSimple",
    "unsignedInt": "PositiveIntegerSimple",
    "double": "NumericalValueSimple",
    "float": "NumericalValueSimple",
    "decimal": "NumericalValueSimple",
    "boolean": "BooleanSimple",
    "int": "IntegerSimple",
    "long": "IntegerSimple",
    "positiveInteger": "PositiveIntegerSimple",
}

# Namespace prefixes for internal dict keys
_GROUP_NS = "groups"
_ATTRIBUTE_GROUP_NS = "attributes"
_COMPLEX_NS = "complex"
_ALIAS_NS = "alias"
_ENUM_NS = "enumeration"
_PRIMITIVE_NS = "primitive"
_SUBTYPES_NS = "subtypes"

# ---------------------------------------------------------------------------
# Pattern analysis — infer M3 supertype and extract token values from regex
# ---------------------------------------------------------------------------

# A bare token: an identifier like "ANY", "NaN", or "UNSPECIFIED".
# Optionally prefixed with +/- (for "-INF").
_BARE_TOKEN_RE = re.compile(r"^[+\-]?[a-zA-Z_][a-zA-Z0-9_]*(-[a-zA-Z0-9_]+)*$")

# Float indicator: scientific notation [eE] is the most reliable signal.
# Decimal-point patterns like \.[0-9] are ambiguous (also appear in
# version strings, IP addresses, format strings) so we don't use them.
_FLOAT_INDICATOR_RE = re.compile(r"\[eE\]")

# Patterns that are purely integer: digits, hex, octal, binary, optional sign
_INTEGER_ONLY_RE = re.compile(
    r"^[\[\]0-9a-fA-FxXbB+\\\-?*{}()|,\s]+$"
)

# Known float special values (not treated as generic tokens)
_FLOAT_SPECIAL_VALUES = {"INF", "-INF", "NaN"}

# Boolean tokens — the default parser handles true/false; 0/1 need values
_BOOLEAN_TOKENS = {"true", "false", "0", "1"}


def _split_top_level_alternatives(pattern: str) -> list[str]:
    """Split a regex pattern on top-level '|' (outside parens and brackets)."""
    alternatives: list[str] = []
    depth_paren = 0
    depth_bracket = 0
    current: list[str] = []
    prev = ""

    for ch in pattern:
        if ch == "[" and depth_bracket == 0 and prev != "\\":
            depth_bracket += 1
            current.append(ch)
        elif ch == "]" and depth_bracket > 0 and prev != "\\":
            depth_bracket -= 1
            current.append(ch)
        elif depth_bracket > 0:
            current.append(ch)
        elif ch == "(" and prev != "\\":
            depth_paren += 1
            current.append(ch)
        elif ch == ")" and prev != "\\":
            depth_paren -= 1
            current.append(ch)
        elif ch == "|" and depth_paren == 0:
            alternatives.append("".join(current))
            current = []
        else:
            current.append(ch)
        prev = ch

    alternatives.append("".join(current))
    return alternatives


def _is_bare_token(alt: str) -> bool:
    """Check if a pattern alternative is a bare identifier token."""
    return _BARE_TOKEN_RE.match(alt) is not None


def _has_float_indicators(pattern_parts: list[str]) -> bool:
    """Check if any non-token pattern part contains float indicators.

    Looks for decimal-point-then-digit patterns and scientific notation [eE].
    Standalone alternatives like '\\.0' (the float literal 0.0) also count.
    Escaped dots used as separators (like in IP addresses) do NOT count.
    """
    for part in pattern_parts:
        if _FLOAT_INDICATOR_RE.search(part):
            return True
        # Standalone "\\.0" is the float literal 0.0
        if part == r"\.0":
            return True
    return False


def analyze_pattern(pattern: str | None, name: str) -> tuple[
    PrimitiveSupertype, str | None, list[str]
]:
    """Analyze a regex pattern to determine M3 supertype and extract tokens.

    Returns (supertype, cleaned_pattern_or_None, token_values).
    """
    if pattern is None:
        return PrimitiveSupertype.STRING, None, []

    alternatives = _split_top_level_alternatives(pattern)

    tokens: list[str] = []
    regex_parts: list[str] = []

    for alt in alternatives:
        alt_stripped = alt.strip()
        if _is_bare_token(alt_stripped):
            tokens.append(alt_stripped)
        else:
            regex_parts.append(alt_stripped)

    # Special case: boolean pattern "0|1|true|false"
    all_parts = set(tokens + regex_parts)
    if all_parts and all_parts <= _BOOLEAN_TOKENS:
        # Extra values beyond true/false
        extra = [t for t in tokens + regex_parts if t in ("0", "1")]
        return PrimitiveSupertype.BOOLEAN, None, extra

    # Determine supertype from the regex parts
    if regex_parts:
        if _has_float_indicators(regex_parts):
            supertype = PrimitiveSupertype.FLOAT
            # Float special values (INF, -INF, NaN) are part of the float
            # semantics, not generic tokens — keep them as values though
            # so the runtime knows to accept them
        elif _INTEGER_ONLY_RE.match("|".join(regex_parts)):
            supertype = PrimitiveSupertype.INTEGER
        else:
            supertype = PrimitiveSupertype.STRING
    elif tokens:
        # Pattern is all tokens, no regex — stays as string
        supertype = PrimitiveSupertype.STRING
    else:
        supertype = PrimitiveSupertype.STRING

    # Integer with non-numeric tokens: emit as union type (::integer | ::enum(...)).
    # Float special values (INF, -INF, NaN) are fine — they have M3 mappings.
    if supertype == PrimitiveSupertype.INTEGER and tokens:
        non_float_tokens = [t for t in tokens if t not in _FLOAT_SPECIAL_VALUES]
        if non_float_tokens:
            supertype = PrimitiveSupertype.INTEGER_ENUM_UNION
            cleaned = "|".join(regex_parts) if regex_parts else None
            return supertype, cleaned, tokens

    # Rebuild pattern from regex parts only (tokens become values)
    cleaned = "|".join(regex_parts) if regex_parts else None

    return supertype, cleaned, tokens


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_appinfo(element: ElementTree.Element, source: str) -> str | None:
    """Extract appinfo text from an element's annotation with the given source.

    Looks for <xsd:annotation>/<xsd:appinfo source="<source>"> and returns
    the text content. Returns None if not found.
    """
    anno = element.find("xsd:annotation", _XSD_NS)
    if anno is None:
        return None

    for info in anno.findall("xsd:appinfo", _XSD_NS):
        if info.attrib.get("source") == source:
            return info.text
    return None


def get_documentation(element: ElementTree.Element) -> str | None:
    """Extract documentation text from an element's annotation.

    Looks for <xsd:annotation>/<xsd:documentation> and returns the text.
    Multi-line text is preserved as-is. Returns None if not found.
    """
    anno = element.find("xsd:annotation", _XSD_NS)
    if anno is None:
        return None
    doc = anno.find("xsd:documentation", _XSD_NS)
    if doc is None or doc.text is None:
        return None
    text = doc.text.strip()
    return text if text else None


def get_stereotypes(element: ElementTree.Element) -> list[str]:
    """Extract stereotype names from an element's annotation.

    Returns a list of stereotype strings, or an empty list if none found.
    """
    text = get_appinfo(element, "stereotypes")
    if text is None:
        return []
    return text.split(",")


def drop_ar_prefix(type_ref: str) -> str:
    """Strip the 'AR:' namespace prefix from a type reference.

    'AR:TIME-VALUE' -> 'TIME-VALUE'
    'PLAIN-NAME' -> 'PLAIN-NAME'
    """
    if type_ref.upper().startswith("AR:"):
        return type_ref[3:]
    return type_ref


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_path(element: ElementTree.Element, tags: list[str]) -> ElementTree.Element | None:
    """Walk a chain of child tags, returning the final element or None."""
    where = element
    for tag in tags:
        where = where.find(tag, _XSD_NS)
        if where is None:
            return None
    return where


def _get_member_from_appinfo(element: ElementTree.Element) -> InternalMember | None:
    """Build an InternalMember from an element's appinfo annotation.

    Extracts member name (via mmt.qualifiedName), cardinality
    (pureMM.minOccurs / pureMM.maxOccurs), and stereotypes.
    Returns None if the element has no usable appinfo.
    """
    info_text = get_appinfo(element, "tags")
    if info_text is None:
        return None

    qname = extract_qualified_name(info_text)
    if qname is None:
        return None

    name = normalize_member_name(qname)
    member = InternalMember(name=name, doc=get_documentation(element))
    if "name" in element.attrib:
        member.xml_element_name = element.attrib["name"]

    match = _MIN_OCCURS_RE.search(info_text)
    if match:
        try:
            member.min_occurs = int(match.group(1))
        except ValueError:
            pass

    match = _MAX_OCCURS_RE.search(info_text)
    if match:
        val = match.group(1)
        if val == "-1" or val == "unbounded":
            member.max_occurs = None
        else:
            try:
                member.max_occurs = int(val)
            except ValueError:
                pass

    stereos = get_stereotypes(element)
    if stereos:
        member.stereotypes = stereos

    return member


def _deduce_type_name(xml_name: str, appinfo_name: str | None) -> str:
    """Determine the type name from an XML name and optional appinfo name."""
    pascal = xml_to_pascal_case(xml_name)

    if appinfo_name is None:
        return pascal

    # Hardcoded workaround for RefConditional pattern
    if pascal.endswith("RefConditional"):
        return f"{appinfo_name}RefConditional"

    return appinfo_name


def _get_name(element: ElementTree.Element) -> str:
    """Get the logical type name for an element (from appinfo or XML name)."""
    xml_name = element.attrib["name"]
    appinfo_text = get_appinfo(element, "tags")
    appinfo_name = extract_qualified_name(appinfo_text) if appinfo_text else None
    return _deduce_type_name(xml_name, appinfo_name)


def _add_choice_info(choice_elem: ElementTree.Element, member: InternalMember) -> None:
    """Add cardinality from XSD choice element attributes to a member."""
    if "maxOccurs" in choice_elem.attrib:
        val = choice_elem.attrib["maxOccurs"]
        if val == "unbounded" or val == "-1":
            member.max_occurs = None
        else:
            member.max_occurs = int(val)

    if "minOccurs" in choice_elem.attrib:
        member.min_occurs = int(choice_elem.attrib["minOccurs"])


def _get_choice_group_ref_member(
    group_elem: ElementTree.Element, choice_elem: ElementTree.Element
) -> InternalMember:
    """Build a member for a group ref inside a choice."""
    ref_name = drop_ar_prefix(group_elem.attrib["ref"])
    name = xml_to_pascal_case(ref_name)
    member = InternalMember(name=normalize_member_name(name))
    member.is_ordered = True
    member.min_occurs = 0
    member.max_occurs = None
    member.xml_types = [ref_name]
    _add_choice_info(choice_elem, member)
    return member


def _get_unnamed_string_member() -> InternalMember:
    """Build an unnamed string member for atpMixedString types."""
    member = InternalMember(name=None)
    member.type_names = [_PRIM_ALIAS["string"]]
    member.is_ordered = True
    member.min_occurs = 0
    member.max_occurs = None
    return member


# ---------------------------------------------------------------------------
# Tag predicates
# ---------------------------------------------------------------------------


def _is_element(elem: ElementTree.Element) -> bool:
    return elem.tag.endswith("element")


def _is_choice(elem: ElementTree.Element) -> bool:
    return elem.tag.endswith("choice")


def _is_restriction(elem: ElementTree.Element) -> bool:
    return elem.tag.endswith("restriction")


# ---------------------------------------------------------------------------
# Simple type analysis
# ---------------------------------------------------------------------------


def _get_base_name(restriction: ElementTree.Element) -> str:
    return restriction.attrib["base"].split(":")[-1]


def _get_enum_value(elem: ElementTree.Element) -> tuple[str | None, str | None]:
    """Extract enum value name and doc from appinfo and documentation."""
    info_text = get_appinfo(elem, "tags")
    if info_text is None:
        return None, None
    name = extract_qualified_name(info_text)
    doc = get_documentation(elem)
    return name, doc


def _get_enum_values(restriction: ElementTree.Element) -> tuple[list[str], list[str | None]]:
    pairs = [_get_enum_value(child) for child in restriction]
    values = [name for name, _ in pairs if name is not None]
    docs = [doc for name, doc in pairs if name is not None]
    return values, docs


def _reroute_alias_target(alias: InternalAlias) -> None:
    """Map XSD base types to internal primitive names, handle NMTOKEN/S."""
    if alias.target in _PRIM_ALIAS:
        alias.target = _PRIM_ALIAS[alias.target]
    if alias.target == "NMTOKEN":
        alias.pattern = r"[\w\.\-:]+"
    elif alias.target == "NMTOKENS":
        alias.pattern = r"[\w\.\-:]+( [\w\.\-:]+)+"


def _analyze_simple_type(
    elem: ElementTree.Element, schema: InternalSchema, warnings: list[str]
) -> None:
    xml_name = elem.attrib["name"]

    if len(elem) == 0:
        return

    restriction = elem.find("xsd:restriction", _XSD_NS)
    if restriction is None:
        return

    base_name = _get_base_name(restriction)
    has_enumeration = restriction.find("xsd:enumeration", _XSD_NS) is not None

    if base_name == "string" and has_enumeration:
        values, value_docs = _get_enum_values(restriction)
        if len(values) > 0:
            # Regular enumeration with named values
            enumeration = InternalEnumeration(
                name=xml_to_pascal_case(xml_name),
                xml_name=xml_name,
                namespace=_ENUM_NS,
                values=values,
                value_docs=value_docs,
            )
            enumeration.doc = get_documentation(elem)
            schema.types[xml_name] = enumeration
        else:
            # Subtypes enum - values come from XML value attr, not appinfo
            es = restriction.findall("xsd:enumeration", _XSD_NS)
            subtypes = InternalSubTypesEnum(
                name=xml_to_pascal_case(xml_name),
                xml_name=xml_name,
                namespace=_SUBTYPES_NS,
                types=[val.attrib["value"] for val in es],
            )
            subtypes.doc = get_documentation(elem)
            schema.types[xml_name] = subtypes
            schema.sub_types[xml_name] = subtypes
    else:
        # Alias or primitive
        pattern_elem = restriction.find("xsd:pattern", _XSD_NS)
        pattern = None
        if pattern_elem is not None and "value" in pattern_elem.attrib:
            pattern = pattern_elem.attrib["value"]

        pascal_name = xml_to_pascal_case(xml_name)
        alias = InternalAlias(
            name=pascal_name,
            xml_name=xml_name,
            namespace=_ALIAS_NS,
            target=base_name,
            pattern=pattern,
        )
        _reroute_alias_target(alias)
        alias.doc = get_documentation(elem)

        if alias.target == alias.name:
            # Self-referencing alias => unrestricted primitive type
            schema.types[xml_name] = InternalPrimitiveType(
                name=alias.name,
                xml_name=xml_name,
                namespace=_PRIMITIVE_NS,
            )
            schema.types[xml_name].doc = alias.doc
        else:
            schema.types[xml_name] = alias


# ---------------------------------------------------------------------------
# Group analysis: sequence members
# ---------------------------------------------------------------------------


def _get_ref_member(elem: ElementTree.Element) -> InternalMember | None:
    """Try to extract a reference member (base=AR:REF) from an element."""
    member = _get_member_from_appinfo(elem)
    if member is None:
        return None

    paths = [
        ["xsd:complexType", "xsd:simpleContent", "xsd:extension"],
        [
            "xsd:complexType",
            "xsd:choice",
            "xsd:element",
            "xsd:complexType",
            "xsd:simpleContent",
            "xsd:extension",
        ],
    ]
    ext = None
    for path in paths:
        ext = _get_path(elem, path)
        if ext is not None:
            break

    if ext is None:
        return None

    if ext.attrib.get("base") != "AR:REF":
        return None

    member.is_reference = True

    # Pattern B: extract inner REF element name from xsd:choice → xsd:element
    inner_elem = _get_path(elem, ["xsd:complexType", "xsd:choice", "xsd:element"])
    if inner_elem is not None and "name" in inner_elem.attrib:
        member.inner_ref_tag = inner_elem.attrib["name"]

    attr = _get_path(ext, ["xsd:attribute"])
    if attr is not None and "type" in attr.attrib:
        member.xml_sub_types = drop_ar_prefix(attr.attrib["type"])

    return member


def _get_sequence_ref_element(
    ct: InternalComplexType, elem: ElementTree.Element
) -> bool | None:
    """Detect reference element (no type attr, extension base=AR:REF)."""
    if "type" in elem.attrib:
        return False

    member = _get_ref_member(elem)
    if member is None:
        return None

    ct.members.append(member)
    return True


def _get_sequence_invariant_element(
    ct: InternalComplexType, elem: ElementTree.Element
) -> bool:
    """Detect invariant element: has type attr, single typed member."""
    if "type" not in elem.attrib:
        return False

    member = _get_member_from_appinfo(elem)
    if member is None:
        return False

    member.xml_types.append(drop_ar_prefix(elem.attrib["type"]))
    ct.members.append(member)
    return True


def _get_sequence_variant_element(
    ct: InternalComplexType, elem: ElementTree.Element, warnings: list[str]
) -> bool | None:
    """Detect variant element: no type attr, contains choice with typed elements."""
    if "type" in elem.attrib:
        return False

    member = _get_member_from_appinfo(elem)
    if member is None:
        return False

    choice = _get_path(elem, ["xsd:complexType", "xsd:choice"])
    if choice is None:
        return False

    elems = choice.findall("xsd:element", _XSD_NS)
    for es in elems:
        if "type" not in es.attrib:
            warnings.append(
                f"{es.attrib.get('name', '?')} in {elem.attrib['name']} "
                f"does not have a type attribute."
            )
            return None
        member.xml_types.append(drop_ar_prefix(es.attrib["type"]))

    groups = choice.findall("xsd:group", _XSD_NS)
    for gr in groups:
        if "ref" not in gr.attrib:
            warnings.append(
                f"group in {elem.attrib['name']} does not have a ref attribute."
            )
            return None
        member.xml_types.append(drop_ar_prefix(gr.attrib["ref"]))

    ct.members.append(member)
    return True


def _get_sequence_variant_wrapped_element(
    ct: InternalComplexType, elem: ElementTree.Element
) -> bool:
    """Detect wrapped variant: appinfo is on inner choice/element, not wrapper."""
    if "type" in elem.attrib:
        return False

    inner = _get_path(elem, ["xsd:complexType", "xsd:choice", "xsd:element"])
    if inner is None or "type" not in inner.attrib:
        return False

    member = _get_member_from_appinfo(inner)
    if member is None:
        return False

    # Use the outer wrapper's XML name (e.g. DATA-IDS) rather than the inner
    # element's name (e.g. DATA-ID). The wrapper is what appears in ARXML.
    if "name" in elem.attrib:
        member.xml_element_name = elem.attrib["name"]

    member.xml_types.append(drop_ar_prefix(inner.attrib["type"]))
    ct.members.append(member)
    return True


# ---------------------------------------------------------------------------
# Group analysis: choice members
# ---------------------------------------------------------------------------


def _get_sequence_choice_group(
    ct: InternalComplexType, choice_elem: ElementTree.Element
) -> bool:
    """Handle choice containing one or more group refs."""
    groups = choice_elem.findall("xsd:group", _XSD_NS)
    groups = [g for g in groups if "ref" in g.attrib]
    if not groups:
        return False

    for group in groups:
        xml_types = [drop_ar_prefix(group.attrib["ref"])]

        if "name" in choice_elem.attrib:
            name = choice_elem.attrib["name"]
            member = InternalMember(name=name)
            member.xml_types = xml_types
            _add_choice_info(choice_elem, member)
        else:
            member = _get_choice_group_ref_member(group, choice_elem)

        ct.members.append(member)
    return True


def _get_sequence_choice_element(
    ct: InternalComplexType, choice_elem: ElementTree.Element
) -> bool:
    """Handle choice containing a typed element."""
    e = choice_elem.find("xsd:element", _XSD_NS)
    if e is None or "type" not in e.attrib:
        return False

    xml_types = [drop_ar_prefix(e.attrib["type"])]

    if "name" in e.attrib:
        name = xml_to_pascal_case(e.attrib["name"])
        name = normalize_member_name(name)
    else:
        name = None

    member = InternalMember(name=name)
    member.xml_types = xml_types
    _add_choice_info(choice_elem, member)

    ct.members.append(member)
    return True


# ---------------------------------------------------------------------------
# Group analysis: top level
# ---------------------------------------------------------------------------


def _analyze_group_sequence(
    elem: ElementTree.Element,
    name: str,
    seq: ElementTree.Element,
    warnings: list[str],
) -> InternalComplexType:
    """Analyze a group with a sequence child."""
    res = InternalComplexType(
        name=name, xml_name=elem.attrib["name"], namespace=_GROUP_NS
    )
    res.doc = get_documentation(elem)

    # Detect group refs at sequence level as inheritance
    for child in seq:
        if child.tag.endswith("group") and "ref" in child.attrib:
            ref = drop_ar_prefix(child.attrib["ref"])
            res.inherits_from.append(_GROUP_NS + ":" + ref)

    seq_element_analyzers = [
        lambda ct, e: _get_sequence_ref_element(ct, e),
        lambda ct, e: _get_sequence_variant_element(ct, e, warnings),
        lambda ct, e: _get_sequence_variant_wrapped_element(ct, e),
        lambda ct, e: _get_sequence_invariant_element(ct, e),
    ]
    seq_choice_analyzers = [
        _get_sequence_choice_group,
        _get_sequence_choice_element,
    ]

    for child in seq:
        if _is_element(child):
            for analyzer in seq_element_analyzers:
                if analyzer(res, child):
                    break
            else:
                warnings.append(
                    f"sequence element '{child.attrib.get('name', '?')}' "
                    f"in group '{name}' could not be processed."
                )
        elif _is_choice(child):
            for analyzer in seq_choice_analyzers:
                if analyzer(res, child):
                    break
            else:
                warnings.append(
                    f"sequence choice in group '{name}' could not be processed."
                )

    return res


def _analyze_mixed(
    elem: ElementTree.Element,
    choice: ElementTree.Element,
    name: str,
    stereos: list[str],
    warnings: list[str],
) -> InternalComplexType | None:
    """Analyze a group with mixed content (atpMixed / atpMixedString)."""
    cc = choice.find("xsd:choice", _XSD_NS)
    if cc is None:
        return None

    res = InternalComplexType(
        name=name, xml_name=elem.attrib["name"], namespace=_GROUP_NS
    )

    ccc = cc.find("xsd:choice", _XSD_NS)
    if ccc is not None:
        g = ccc.find("xsd:group", _XSD_NS)
        if g is None:
            warnings.append(f"nested group in '{name}' could not be processed.")
        else:
            res.members.append(_get_choice_group_ref_member(g, ccc))

    is_mixed = "atpMixed" in stereos or "atpMixedString" in stereos
    if not is_mixed:
        return None

    if "atpMixedString" in stereos:
        res.members.append(_get_unnamed_string_member())

    elems = cc.findall("xsd:element", _XSD_NS)
    for es in elems:
        if "type" not in es.attrib:
            member = _get_ref_member(es)
            if member is None:
                warnings.append(
                    f"Reference member {es.attrib.get('name', '?')} "
                    f"in type {name} could not be processed."
                )
                continue
        else:
            info_text = get_appinfo(es, "tags")
            member_name = extract_qualified_name(info_text) if info_text else None
            member = InternalMember(name=normalize_member_name(member_name) if member_name else None)
            member.xml_types = [drop_ar_prefix(es.attrib["type"])]

        member.xml_element_name = es.attrib.get("name")
        member.is_ordered = True
        member.min_occurs = 0
        member.max_occurs = None
        res.members.append(member)

    return res


def _analyze_group_choice(
    elem: ElementTree.Element,
    name: str,
    choice: ElementTree.Element,
    warnings: list[str],
) -> InternalComplexType | None:
    """Analyze a group with a choice child (mixed content)."""
    stereos = get_stereotypes(elem)

    res = _analyze_mixed(elem, choice, name, stereos, warnings)
    if res is not None:
        res.doc = get_documentation(elem)
        return res

    warnings.append(f"choice element '{elem.attrib['name']}' could not be processed.")
    return None


def _analyze_group(
    elem: ElementTree.Element, schema: InternalSchema, warnings: list[str]
) -> None:
    xml_name = elem.attrib["name"]
    name = _get_name(elem)

    stereos = get_stereotypes(elem)

    seq = elem.find("xsd:sequence", _XSD_NS)
    if seq is not None:
        result_type = _analyze_group_sequence(elem, name, seq, warnings)
        result_type.is_abstract = True
        if stereos:
            result_type.stereotypes = stereos
        schema.types[_GROUP_NS + ":" + xml_name] = result_type
        return

    choice = elem.find("xsd:choice", _XSD_NS)
    if choice is not None:
        result_type = _analyze_group_choice(elem, name, choice, warnings)
        if result_type is not None:
            result_type.is_abstract = True
            if stereos:
                result_type.stereotypes = stereos
            schema.types[_GROUP_NS + ":" + xml_name] = result_type
        return

    warnings.append(f"group: {xml_name} has no sequence or choice child")


# ---------------------------------------------------------------------------
# Attribute group analysis
# ---------------------------------------------------------------------------


def _analyze_attribute_group(
    elem: ElementTree.Element, schema: InternalSchema, warnings: list[str]
) -> None:
    xml_name = elem.attrib["name"]
    name = _get_name(elem)
    ct = InternalComplexType(
        name=name, xml_name=xml_name, namespace=_ATTRIBUTE_GROUP_NS
    )

    attrs = elem.findall("xsd:attribute", _XSD_NS)
    for attr in attrs:
        member = _get_member_from_appinfo(attr)
        if member is None:
            continue
        if "type" in attr.attrib:
            member.xml_types = [drop_ar_prefix(attr.attrib["type"])]
        elif "ref" in attr.attrib and attr.attrib["ref"] == "xml:space":
            member.type_names.append(_PRIM_ALIAS["string"])
        else:
            warnings.append(
                f"Attribute {attr.attrib.get('name', '?')} in type {name} "
                f"does not have a type."
            )
        ct.members.append(member)

    schema.types[_ATTRIBUTE_GROUP_NS + ":" + xml_name] = ct


# ---------------------------------------------------------------------------
# Complex type analysis
# ---------------------------------------------------------------------------


def _add_groups(ct: InternalComplexType, elem: ElementTree.Element) -> None:
    """Add group and attributeGroup refs to a complex type's inherits_from."""
    for gr in elem.findall("xsd:group", _XSD_NS):
        ct.inherits_from.append(_GROUP_NS + ":" + drop_ar_prefix(gr.attrib["ref"]))

    for attr in elem.findall("xsd:attributeGroup", _XSD_NS):
        ct.inherits_from.append(
            _ATTRIBUTE_GROUP_NS + ":" + drop_ar_prefix(attr.attrib["ref"])
        )


def _analyze_complex_simple(ct: InternalComplexType, elem: ElementTree.Element) -> bool:
    """Handle complexType with simpleContent/extension (e.g. REF types, primitive wrappers)."""
    simple = _get_path(elem, ["xsd:simpleContent"])
    if simple is None:
        return False

    ext = _get_path(simple, ["xsd:extension"])
    if ext is None:
        return False

    base_type = drop_ar_prefix(ext.attrib["base"])

    if base_type == "REF":
        # REF types keep an unnamed member (reference pattern, not inheritance)
        base = InternalMember(name=None)
        base.xml_types = [base_type]
        base.is_ordered = False
        ct.members.append(base)
    else:
        # Primitive/enum wrapper: unnamed member carrying the base type
        member = InternalMember(name=None)
        member.xml_types = [base_type]
        member.min_occurs = 1
        member.max_occurs = 1
        # Identifier wrapper types get identity annotation
        if "identifier" in ct.name.lower():
            member.stereotypes = ["atpIdentityContributor"]
        ct.members.append(member)

    _add_groups(ct, ext)
    return True


def _analyze_complex_sequence(ct: InternalComplexType, elem: ElementTree.Element) -> bool:
    """Handle complexType with sequence."""
    seq = _get_path(elem, ["xsd:sequence"])
    if seq is None:
        return False

    _add_groups(ct, seq)
    _add_groups(ct, elem)
    return True


def _analyze_complex_choice(ct: InternalComplexType, elem: ElementTree.Element) -> bool:
    """Handle complexType with choice."""
    choice = _get_path(elem, ["xsd:choice"])
    if choice is None:
        return False

    _add_groups(ct, choice)
    _add_groups(ct, elem)
    return True


def _analyze_complex_type(
    elem: ElementTree.Element, schema: InternalSchema, warnings: list[str]
) -> None:
    xml_name = elem.attrib["name"]
    type_name = _get_name(elem)
    ct = InternalComplexType(
        name=type_name, xml_name=xml_name, namespace=_COMPLEX_NS
    )
    ct.doc = get_documentation(elem)

    stereos = get_stereotypes(elem)
    if stereos:
        ct.stereotypes = stereos

    analyzers = [
        _analyze_complex_simple,
        _analyze_complex_sequence,
        _analyze_complex_choice,
    ]

    for analyzer in analyzers:
        if analyzer(ct, elem):
            break
    else:
        warnings.append(f"complex type '{type_name}' could not be processed.")

    schema.types[xml_name] = ct


# ---------------------------------------------------------------------------
# Root element
# ---------------------------------------------------------------------------


def _analyze_root_element(
    elem: ElementTree.Element, schema: InternalSchema
) -> None:
    member = _get_member_from_appinfo(elem)
    if member is None:
        return
    member.min_occurs = 1
    member.max_occurs = 1
    member.xml_types = [drop_ar_prefix(elem.attrib["type"])]
    schema.root = member


# ---------------------------------------------------------------------------
# Top-level analysis dispatch
# ---------------------------------------------------------------------------


def _analyze(root: ElementTree.Element, schema: InternalSchema, warnings: list[str]) -> None:
    for child in root:
        tag = child.tag
        if tag.endswith("complexType"):
            _analyze_complex_type(child, schema, warnings)
        elif tag.endswith("simpleType"):
            _analyze_simple_type(child, schema, warnings)
        elif tag.endswith("group"):
            _analyze_group(child, schema, warnings)
        elif tag.endswith("attributeGroup"):
            _analyze_attribute_group(child, schema, warnings)
        elif tag.endswith("element"):
            _analyze_root_element(child, schema)
        elif tag.endswith("import"):
            pass  # Skip import declarations
        # Other elements are silently ignored


# ---------------------------------------------------------------------------
# Version info
# ---------------------------------------------------------------------------


def _read_version_info_from_lines(lines: list[str], schema: InternalSchema) -> None:
    for line in lines[:_MAX_HEADER_LINES]:
        m = _RELEASE_RE.search(line)
        if m:
            schema.release_version = m.group(1)
        m = _VERSION_RE.search(line)
        if m:
            schema.autosar_version = m.group(1)


def _read_version_info(filepath: str, schema: InternalSchema) -> None:
    with open(filepath, mode="r") as f:
        lines = []
        for i, line in enumerate(f):
            lines.append(line)
            if i >= _MAX_HEADER_LINES:
                break
    _read_version_info_from_lines(lines, schema)


# ---------------------------------------------------------------------------
# Attribute group merging
# ---------------------------------------------------------------------------


def _merge_attribute_groups_into_groups(schema: InternalSchema) -> None:
    """Merge attribute groups into their matching groups by shared name.

    Groups and attrGroups that share the same PascalCase name are paired.
    The attrGroup's members are appended to the group, the attrGroup is
    removed, and all inherits_from references are redirected.
    """
    # Build xml_name -> key maps
    groups_by_xml: dict[str, str] = {}
    attr_groups_by_xml: dict[str, str] = {}

    for key, t in schema.types.items():
        if not isinstance(t, InternalComplexType):
            continue
        if t.namespace == _GROUP_NS:
            groups_by_xml[t.xml_name] = key
        elif t.namespace == _ATTRIBUTE_GROUP_NS:
            attr_groups_by_xml[t.xml_name] = key

    # Build redirect map: attrGroup key -> group key
    redirect: dict[str, str] = {}
    keys_to_remove: list[str] = []

    for xml_name, attr_key in attr_groups_by_xml.items():
        if xml_name not in groups_by_xml:
            continue
        group_key = groups_by_xml[xml_name]
        group = schema.types[group_key]
        attr_group = schema.types[attr_key]
        assert isinstance(group, InternalComplexType)
        assert isinstance(attr_group, InternalComplexType)

        # Merge attrGroup members into group
        group.members.extend(attr_group.members)
        redirect[attr_key] = group_key
        keys_to_remove.append(attr_key)

    # Remove merged attrGroups
    for key in keys_to_remove:
        del schema.types[key]

    # Redirect all inherits_from references and deduplicate
    for t in schema.types.values():
        if isinstance(t, InternalComplexType) and t.inherits_from:
            seen: set[str] = set()
            deduped: list[str] = []
            for ref in t.inherits_from:
                resolved = redirect.get(ref, ref) if redirect else ref
                if resolved not in seen:
                    seen.add(resolved)
                    deduped.append(resolved)
            t.inherits_from = deduped

    # Inline remaining (unmerged) attrGroups into their referencing types
    remaining_attr_keys = {
        key for key in schema.types
        if key.startswith(_ATTRIBUTE_GROUP_NS + ":")
    }
    if remaining_attr_keys:
        for t in schema.types.values():
            if not isinstance(t, InternalComplexType) or not t.inherits_from:
                continue
            new_parents: list[str] = []
            for ref in t.inherits_from:
                if ref in remaining_attr_keys:
                    attr_group = schema.types[ref]
                    assert isinstance(attr_group, InternalComplexType)
                    t.members.extend(attr_group.members)
                else:
                    new_parents.append(ref)
            t.inherits_from = new_parents
        # Remove inlined attrGroups
        for key in remaining_attr_keys:
            del schema.types[key]

    # Build group hierarchy from complex type group ref chains.
    # In AUTOSAR XSD, the complex type's sequence lists ALL ancestor groups
    # in order: base-first, most-derived-last. Each consecutive pair defines
    # a parent-child relationship between groups.
    # Process longest chains first so that the most detailed (and correct)
    # parent relationships take precedence. Short chains (e.g. BSW-SERVICE-
    # DEPENDENCY: [AR-OBJECT, SERVICE-DEPENDENCY, BSW-...]) would otherwise
    # set SERVICE-DEPENDENCY's parent to AR-OBJECT, skipping intermediate
    # groups like IDENTIFIABLE.
    group_parent: dict[str, str] = {}  # group_key -> direct parent group_key
    complex_chains: list[list[str]] = []
    for t in schema.types.values():
        if not isinstance(t, InternalComplexType) or t.namespace != _COMPLEX_NS:
            continue
        group_refs = [ref for ref in t.inherits_from if ref.startswith(_GROUP_NS + ":")]
        if group_refs:
            complex_chains.append(group_refs)
    complex_chains.sort(key=len, reverse=True)
    for group_refs in complex_chains:
        for i in range(1, len(group_refs)):
            child_key = group_refs[i]
            parent_key = group_refs[i - 1]
            if child_key not in group_parent:
                group_parent[child_key] = parent_key

    # Set group inherits_from to direct parent only
    for key, t in schema.types.items():
        if isinstance(t, InternalComplexType) and t.namespace == _GROUP_NS:
            if key in group_parent:
                t.inherits_from = [group_parent[key]]
            # Groups that aren't in group_parent are roots (like ARObject)

    # Handle complex types that are pure wrappers for same-named groups:
    # mark the group as concrete and mark the complex type for skipping.
    # The complex type's inherits_from chain is fully captured by the group
    # hierarchy now, so the complex type adds nothing.
    keys_to_remove = []
    for key, t in schema.types.items():
        if not isinstance(t, InternalComplexType) or t.namespace != _COMPLEX_NS:
            continue
        group_key = _GROUP_NS + ":" + t.xml_name
        if group_key not in t.inherits_from:
            continue
        group = schema.types.get(group_key)
        if group is None or not isinstance(group, InternalComplexType):
            continue
        if len(t.members) == 0:
            # Complex type adds nothing — group becomes the concrete type
            group.is_abstract = False
            # Carry over stereotypes from complex type to group
            if t.stereotypes:
                for s in t.stereotypes:
                    if s not in group.stereotypes:
                        group.stereotypes.append(s)
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del schema.types[key]

    # Reduce remaining complex types to direct parent only (last group ref)
    for t in schema.types.values():
        if not isinstance(t, InternalComplexType) or t.namespace != _COMPLEX_NS:
            continue
        group_refs = [ref for ref in t.inherits_from if ref.startswith(_GROUP_NS + ":")]
        non_group_refs = [ref for ref in t.inherits_from if not ref.startswith(_GROUP_NS + ":")]
        if group_refs:
            # Keep only the most-derived group (last one)
            t.inherits_from = [group_refs[-1]] + non_group_refs
        else:
            t.inherits_from = non_group_refs




# ---------------------------------------------------------------------------
# Unused type truncation
# ---------------------------------------------------------------------------


def _truncate_unused(schema: InternalSchema) -> None:
    """Remove types not reachable from complex types, groups, or subtypes."""
    used_types: set[str] = set()
    used_subtypes: set[str] = set()

    for name, t in schema.types.items():
        if isinstance(t, InternalPrimitiveType):
            used_types.add(name)
        if isinstance(t, InternalComplexType) and t.namespace in (_COMPLEX_NS, _GROUP_NS):
            used_types.add(name)
            for m in t.members:
                for mt in m.xml_types:
                    used_types.add(mt)
                if m.xml_sub_types:
                    used_subtypes.add(m.xml_sub_types)
            # Mark parent types from inherits_from as used
            for parent_key in t.inherits_from:
                used_types.add(parent_key)

    # Transitively mark parents of parents as used
    changed = True
    while changed:
        changed = False
        for key in list(used_types):
            if key not in schema.types:
                continue
            t = schema.types[key]
            if isinstance(t, InternalComplexType):
                for parent_key in t.inherits_from:
                    if parent_key not in used_types:
                        used_types.add(parent_key)
                        changed = True

    unused = {
        name
        for name in schema.types
        if name not in used_types and name not in used_subtypes
    }
    for name in unused:
        del schema.types[name]


# ---------------------------------------------------------------------------
# Public parsing API
# ---------------------------------------------------------------------------


def parse_schema_from_string(xml_string: str) -> InternalSchema:
    """Parse an XSD schema from an XML string. Useful for testing."""
    root = ElementTree.fromstring(xml_string)
    schema = InternalSchema()
    warnings: list[str] = []

    # Try to extract version info from raw text
    _read_version_info_from_lines(xml_string.splitlines(), schema)

    _analyze(root, schema, warnings)
    return schema


def parse_schema(filepath: str) -> InternalSchema:
    """Parse an XSD schema file and return the internal model."""
    tree = ElementTree.parse(filepath)
    schema = InternalSchema()
    schema.xsd_filename = os.path.basename(filepath)
    warnings: list[str] = []

    _read_version_info(filepath, schema)
    _analyze(tree.getroot(), schema, warnings)
    return schema


# ---------------------------------------------------------------------------
# Export: internal model -> export model
# ---------------------------------------------------------------------------


def _resolve_member_type_names(
    member_xml_types: list[str], schema: InternalSchema
) -> list[str]:
    """Convert XML type names to PascalCase names, skipping missing types."""
    result = []
    for xml_name in member_xml_types:
        if xml_name in schema.types:
            result.append(schema.types[xml_name].name)
        elif _GROUP_NS + ":" + xml_name in schema.types:
            result.append(schema.types[_GROUP_NS + ":" + xml_name].name)
    return result


def _export_member(mem: InternalMember, schema: InternalSchema) -> ExportMember:
    """Convert an internal member to an export member."""
    if mem.is_reference and mem.xml_sub_types and mem.xml_sub_types in schema.sub_types:
        member_types = schema.sub_types[mem.xml_sub_types].types
    else:
        member_types = mem.xml_types

    type_names = mem.type_names + _resolve_member_type_names(member_types, schema)

    is_identity = "atpIdentityContributor" in mem.stereotypes

    return ExportMember(
        name=mem.name,
        types=type_names,
        is_reference=mem.is_reference,
        is_ordered=mem.is_ordered,
        min_occurs=mem.min_occurs,
        max_occurs=mem.max_occurs,
        is_identity=is_identity,
        doc=mem.doc,
        xml_element_name=mem.xml_element_name,
        inner_ref_tag=mem.inner_ref_tag,
    )


def _resolve_inherits_from(
    comp: InternalComplexType, schema: InternalSchema
) -> list[str]:
    """Resolve inherits_from keys to PascalCase type names."""
    result = []
    for key in comp.inherits_from:
        if key in schema.types:
            result.append(schema.types[key].name)
        else:
            # Direct XML type name (e.g. primitive wrapper base type)
            result.append(xml_to_pascal_case(key))
    return result


def _classify_instance_ref_role(xml_element_name: str | None) -> str | None:
    """Classify a member's instance-ref role from its XML element name."""
    if xml_element_name is None:
        return None
    upper = xml_element_name.upper()
    if upper.startswith("TARGET-") and upper.endswith("-REF"):
        return "target"
    if (upper.startswith("CONTEXT-") or upper.startswith("ROOT-")) and upper.endswith("-REF"):
        return "context"
    return None


def _export_composite(
    comp: InternalComplexType, schema: InternalSchema
) -> ExportComposite:
    """Convert an internal complex type to an export composite."""
    stereos = comp.stereotypes or []
    is_ordered = "atpMixedString" in stereos or "atpMixed" in stereos
    is_instance_ref = "instanceRef" in stereos

    members = [_export_member(m, schema) for m in comp.members]
    identifiers = [
        m.name
        for m in comp.members
        if "atpIdentityContributor" in m.stereotypes
    ]
    has_unnamed_string = any(
        m.name is None and _PRIM_ALIAS["string"] in m.type_names
        for m in comp.members
    )

    if is_instance_ref:
        for em, im in zip(members, comp.members):
            em.instance_ref_role = _classify_instance_ref_role(im.xml_element_name)

    return ExportComposite(
        name=comp.name,
        members=members,
        identifiers=identifiers,
        is_ordered=is_ordered,
        has_unnamed_string_member=has_unnamed_string,
        is_abstract=comp.is_abstract,
        inherits_from=_resolve_inherits_from(comp, schema),
        doc=comp.doc,
        is_instance_ref=is_instance_ref,
        xml_name=comp.xml_name,
    )


# Map known primitive names (from XSD base types) to their M3 supertypes.
# Used for InternalPrimitiveType which has no pattern to analyze.
_SUPERTYPE_BY_NAME: dict[str, PrimitiveSupertype] = {
    "IntegerSimple": PrimitiveSupertype.INTEGER,
    "PositiveIntegerSimple": PrimitiveSupertype.INTEGER,
    "NumericalValueSimple": PrimitiveSupertype.FLOAT,
    "BooleanSimple": PrimitiveSupertype.BOOLEAN,
}


def _export_primitive(
    prim: InternalPrimitiveType, aliases_by_name: dict[str, InternalAlias],
    xml_to_name: dict[str, str],
) -> ExportPrimitive:
    supertype = _SUPERTYPE_BY_NAME.get(prim.name, PrimitiveSupertype.STRING)
    return ExportPrimitive(name=prim.name, supertype=supertype, doc=prim.doc,
                           xml_name=prim.xml_name)


def _export_alias(
    alias: InternalAlias, aliases_map: dict[str, str],
    aliases_by_name: dict[str, InternalAlias],
    xml_to_name: dict[str, str],
) -> ExportPrimitive:
    """Export an alias as a primitive, using pattern analysis for supertype."""
    if alias.pattern is not None:
        supertype, cleaned_pattern, values = analyze_pattern(alias.pattern, alias.name)
        return ExportPrimitive(
            name=alias.name,
            supertype=supertype,
            pattern=cleaned_pattern,
            values=values,
            doc=alias.doc,
            xml_name=alias.xml_name,
        )
    elif alias.name != alias.target:
        # Resolve target to PascalCase name for lookup in primitive_by_name
        target_name = xml_to_name.get(alias.target, alias.target)
        aliases_map[alias.name] = target_name
    return ExportPrimitive(name=alias.name, doc=alias.doc, xml_name=alias.xml_name)


def _export_enum(enum: InternalEnumeration) -> ExportEnum:
    return ExportEnum(
        name=enum.name, values=enum.values, is_subtypes_enum=False,
        doc=enum.doc, value_docs=enum.value_docs,
        xml_name=enum.xml_name,
    )


def _export_subtypes_enum(st: InternalSubTypesEnum) -> ExportEnum:
    return ExportEnum(name=st.name, values=st.types, is_subtypes_enum=True, doc=st.doc,
                      xml_name=st.xml_name)


def export_schema(internal: InternalSchema) -> ExportSchema:
    """Convert an InternalSchema to an ExportSchema.

    Steps:
    1. Flatten inheritance (merge group members into complex types)
    2. Truncate unused types
    3. Convert internal types to export types
    4. Resolve alias patterns
    5. Set root type
    """
    # Step 1: Merge attribute groups into their matching groups
    _merge_attribute_groups_into_groups(internal)

    # Step 2: Truncate unused types
    _truncate_unused(internal)

    # Step 3: Convert to export model
    result = ExportSchema(
        release_version=internal.release_version,
        autosar_version=internal.autosar_version,
        xsd_filename=internal.xsd_filename,
    )

    aliases_map: dict[str, str] = {}
    primitive_by_name: dict[str, ExportPrimitive] = {}
    aliases_by_name: dict[str, InternalAlias] = {
        t.name: t for t in internal.types.values() if isinstance(t, InternalAlias)
    }
    xml_to_name: dict[str, str] = {
        t.xml_name: t.name for t in internal.types.values()
    }

    for t in internal.types.values():
        if isinstance(t, InternalPrimitiveType):
            ep = _export_primitive(t, aliases_by_name, xml_to_name)
            result.primitives.append(ep)
            primitive_by_name[ep.name] = ep
        elif isinstance(t, InternalEnumeration):
            result.enums.append(_export_enum(t))
        elif isinstance(t, InternalSubTypesEnum):
            result.enums.append(_export_subtypes_enum(t))
        elif isinstance(t, InternalAlias):
            ep = _export_alias(t, aliases_map, aliases_by_name, xml_to_name)
            result.primitives.append(ep)
            primitive_by_name[ep.name] = ep
        elif isinstance(t, InternalComplexType) and t.namespace in (_COMPLEX_NS, _GROUP_NS):
            result.composites.append(_export_composite(t, internal))

    # Step 4: Resolve alias patterns from targets, then run pattern analysis
    for alias_name, target_name in aliases_map.items():
        if alias_name in primitive_by_name and target_name in primitive_by_name:
            source = primitive_by_name[target_name]
            dest = primitive_by_name[alias_name]
            # Copy the full original pattern from target for analysis
            if source.pattern is not None:
                supertype, cleaned, values = analyze_pattern(source.pattern, dest.name)
                dest.supertype = supertype
                dest.pattern = cleaned
                dest.values = values
            else:
                # Target has no pattern — inherit supertype and values
                dest.supertype = source.supertype
                dest.values = list(source.values)

    # Step 5: Set root type
    if internal.root is not None and len(internal.root.xml_types) > 0:
        root_xml = internal.root.xml_types[0]
        if root_xml in internal.types:
            result.root_type = internal.types[root_xml].name
        elif _GROUP_NS + ":" + root_xml in internal.types:
            result.root_type = internal.types[_GROUP_NS + ":" + root_xml].name

    return result
