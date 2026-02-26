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


def pascal_to_snake(name: str) -> str:
    """Convert PascalCase to snake_case for C++ variable names.

    Examples:
        ISignal -> i_signal
        ARObject -> ar_object
        EcuInstance -> ecu_instance
    """
    if not name:
        return name
    result = []
    i = 0
    while i < len(name):
        ch = name[i]
        if ch.isupper():
            # Count consecutive uppercase chars
            j = i
            while j < len(name) and name[j].isupper():
                j += 1
            upper_run = name[i:j]
            if j < len(name) and not name[j].isupper():
                # Uppercase run followed by lowercase: last upper starts new word
                if len(upper_run) > 1:
                    if result:
                        result.append("_")
                    result.append(upper_run[:-1].lower())
                    result.append("_")
                    result.append(upper_run[-1].lower())
                else:
                    if result:
                        result.append("_")
                    result.append(ch.lower())
            else:
                # All remaining chars are uppercase (end of string)
                if result:
                    result.append("_")
                result.append(upper_run.lower())
            i = j
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def normalize_member_name(name: str) -> str:
    """Normalize a member name to camelCase.

    Lowercases first character unless the entire name is ALL_CAPS.
    """
    if not name or name == name.upper():
        return name
    return name[0].lower() + name[1:]
