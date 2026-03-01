"""Shared helpers for C++ code generation."""

from __future__ import annotations

from name_converter import pascal_to_snake


CPP_KEYWORDS = frozenset({
    "auto", "bool", "break", "case", "catch", "char", "class", "const",
    "continue", "default", "delete", "do", "double", "else", "enum",
    "extern", "false", "float", "for", "goto", "if", "inline", "int",
    "long", "namespace", "new", "nullptr", "operator", "private",
    "protected", "public", "register", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "template", "this", "throw",
    "true", "try", "typedef", "union", "unsigned", "using", "virtual",
    "void", "volatile", "while",
})


def multiplicity_str(min_occurs: int | None, max_occurs: int | None) -> str:
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


def multiplicity_index(min_occurs: int | None, max_occurs: int | None) -> int:
    """Map (min, max) to fir::Multiplicity integer value.

    One=0, Optional=1, Many=2, OneOrMore=3.
    """
    mn = min_occurs if min_occurs is not None else 0
    mx = max_occurs
    if mn == 1 and mx == 1:
        return 0  # One
    if mn == 0 and mx == 1:
        return 1  # Optional
    if mn == 0 and mx is None:
        return 2  # Many
    if mn == 1 and mx is None:
        return 3  # OneOrMore
    if mn == 0:
        return 2  # Many
    return 3  # OneOrMore


def safe_var(name: str) -> str:
    """Append underscore to C++ reserved keywords."""
    return name + "_" if name in CPP_KEYWORDS else name


def type_var(name: str) -> str:
    """Generate a C++ variable name for a type (snake_case)."""
    return safe_var(pascal_to_snake(name))


def prim_var(name: str) -> str:
    """Variable name for a primitive type (snake_case + _t suffix)."""
    return pascal_to_snake(name) + "_t"


def role_var(type_var_name: str, index: int) -> str:
    """Variable name for a role handle."""
    return f"{type_var_name}_r{index}"


def domain_name(release_version: str) -> str:
    """Convert release version to domain name: R23-11 -> autosar-r23-11."""
    return "autosar-" + release_version.lower()
