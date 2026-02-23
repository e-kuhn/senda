"""Name conversion utilities for AUTOSAR XSD -> Rupa."""

import re

_QUALIFIED_NAME_RE = re.compile(r'mmt\.qualifiedName="(?:\w+\.)?([^"]+)"')


def xml_to_pascal_case(xml_name: str) -> str:
    """Convert AUTOSAR XML tag name (KEBAB-CASE) to PascalCase.

    Examples:
        ABSOLUTE-TOLERANCE -> AbsoluteTolerance
        ALIGN-ENUM--SIMPLE -> AlignEnumSimple
    """
    return "".join(part.title() for part in xml_name.split("-") if part)


def extract_qualified_name(appinfo_text: str) -> str | None:
    """Extract the name from an mmt.qualifiedName annotation.

    For 'mmt.qualifiedName="ClassName.memberName"', returns 'memberName'.
    For 'mmt.qualifiedName="TypeName"', returns 'TypeName'.
    Returns None if no match.
    """
    match = _QUALIFIED_NAME_RE.search(appinfo_text)
    return match.group(1) if match else None


def normalize_member_name(name: str) -> str:
    """Normalize a member name to camelCase.

    Lowercases first character unless the entire name is ALL_CAPS.
    """
    if not name or name == name.upper():
        return name
    return name[0].lower() + name[1:]
