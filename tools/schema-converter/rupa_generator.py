"""Generate Rupa source files from the AUTOSAR export model."""

from __future__ import annotations

import os
import re
import string
from name_converter import xml_to_pascal_case
from schema_model import (
    ExportSchema, ExportPrimitive, ExportEnum, ExportComposite,
    ExportMember, PrimitiveSupertype,
)


# --- Helpers ---

_BARE_TOKEN_CHARS = set(string.ascii_letters + string.digits + "_")


def _needs_quoting(value: str) -> bool:
    """Return True if an enum value needs to be quoted in Rupa syntax."""
    if not value:
        return True
    for ch in value:
        if ch not in _BARE_TOKEN_CHARS:
            return True
    return False



def _wrap_text(text: str, max_width: int, indent: str) -> list[str]:
    """Wrap text to fit within max_width, preferring sentence boundaries.

    Returns a list of lines (without the indent prefix — caller adds it).
    Splits at '. ' first if possible, otherwise at any whitespace.
    Hard breaks at 100 chars minus indent.
    """
    prefix_len = len(indent) + len(" * ")
    target = max_width - prefix_len
    hard_limit = 100 - prefix_len

    if target < 20:
        target = 40
    if hard_limit < target:
        hard_limit = target

    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        test_len = current_len + (1 if current else 0) + len(word)
        if current and test_len > target:
            # Check if we ended on a sentence boundary
            line = " ".join(current)
            lines.append(line)
            current = [word]
            current_len = len(word)
        elif current and test_len > hard_limit:
            # Hard break
            line = " ".join(current)
            lines.append(line)
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len = test_len if current_len > 0 else len(word)

        # If we just passed a sentence end and are near the target, break
        if (current_len >= target - 10
                and len(current) > 0
                and current[-1].endswith(".")):
            line = " ".join(current)
            lines.append(line)
            current = []
            current_len = 0

    if current:
        lines.append(" ".join(current))

    return lines


def _format_block_comment(text: str, indent: str = "") -> str:
    """Format text as a /** ... */ block comment.

    - Single short line: /** text */
    - Multi-line: /**\\n * line1\\n * line2\\n */
    Indentation of all lines aligns with the first.
    """
    if not text:
        return ""

    max_width = 80
    prefix = indent + " * "
    single_line = "%s/** %s */" % (indent, text)

    if len(single_line) <= max_width:
        return single_line

    lines = _wrap_text(text, max_width, indent)
    result = ["%s/**" % indent]
    for line in lines:
        result.append("%s%s" % (prefix, line))
    result.append("%s */" % indent)
    return "\n".join(result)


# --- Parser inference from regex patterns ---

_HAS_HEX_RE = re.compile(r"0\[xX\]")
_HAS_BINARY_RE = re.compile(r"0\[bB\]")
_HAS_OCTAL_RE = re.compile(r"0\[0-7\]")
_HAS_DECIMAL_RE = re.compile(r"\[0-9\]|\[1-9\]")


def _infer_integer_parsers(pattern: str | None) -> list[str]:
    """Determine which integer sub-parsers a regex pattern requires.

    Returns a list of parser names. If it equals the default (c_integer),
    an empty list is returned (meaning: use default, no annotation needed).
    """
    if pattern is None:
        return []

    has_hex = _HAS_HEX_RE.search(pattern) is not None
    has_binary = _HAS_BINARY_RE.search(pattern) is not None
    has_octal = _HAS_OCTAL_RE.search(pattern) is not None
    has_decimal = _HAS_DECIMAL_RE.search(pattern) is not None

    # c_integer = decimal + hex + octal + binary (the default)
    if has_hex and has_binary and has_octal and has_decimal:
        return []  # default, no annotation needed

    parsers: list[str] = []
    if has_decimal:
        parsers.append("decimal")
    if has_hex:
        parsers.append("hex")
    if has_octal:
        parsers.append("octal")
    if has_binary:
        parsers.append("binary")

    return parsers if parsers else []


def _infer_float_parsers(pattern: str | None) -> list[str]:
    """Determine which float sub-parsers a regex pattern requires.

    Default float = decimal_float + scientific_float.
    Returns non-empty only if non-default parsers are needed.
    """
    if pattern is None:
        return []

    has_scientific = re.search(r"\[eE\]", pattern) is not None
    has_hex = _HAS_HEX_RE.search(pattern) is not None

    # If pattern includes hex forms, use c_float (includes hex_float)
    if has_hex:
        return ["c_float"]

    # default_float covers decimal_float + scientific_float
    return []


def _infer_integer_range(pattern: str | None) -> str | None:
    """Infer a range annotation for an integer type from its regex pattern.

    Returns the annotation content string (e.g. ">=0") or None if signed/unknown.
    """
    if pattern is None:
        return None

    # Check for minus sign in sign-indicating position:
    # [\+\-] or [+-] or -? at start of an alternative
    if "\\-" in pattern or "+-" in pattern:
        return None  # signed integer, no range constraint

    # Check if zero is allowed as a standalone top-level alternative
    alternatives = pattern.split("|")
    has_zero = "0" in [a.strip() for a in alternatives]

    if has_zero:
        return ">=0"
    else:
        return ">=1"


def _format_multiplicity(min_occurs: int | None, max_occurs: int | None) -> str:
    """Return the Rupa multiplicity suffix for a member."""
    mn = min_occurs if min_occurs is not None else 0
    mx = max_occurs  # None means unbounded

    if mn == 1 and mx == 1:
        return ""
    if mn == 0 and mx == 1:
        return "?"
    if mn == 0 and mx is None:
        return "*"
    if mn == 1 and mx is None:
        return "+"
    # Explicit range
    if mx is None:
        return "{%d,}" % mn
    return "{%d,%d}" % (mn, mx)


def _format_type_ref(types: list[str], is_reference: bool) -> tuple[str, list[str]]:
    """Return (type_text, alternatives_list) for a member type reference.

    If there are multiple types (variant), use the first as primary type
    and return the rest as a list of alternative type names.
    """
    if not types:
        return "Unknown", []
    prefix = "&" if is_reference else ""
    primary = prefix + types[0]
    return primary, types[1:]


# --- Public generators ---


def generate_primitive(p: ExportPrimitive) -> str:
    """Generate a Rupa type definition for a primitive type."""
    lines: list[str] = []

    if p.doc:
        lines.append(_format_block_comment(p.doc))

    # Union type: ::integer | ::enum(TOKEN1, TOKEN2, ...)
    if p.supertype == PrimitiveSupertype.INTEGER_ENUM_UNION:
        enum_values = ", ".join(v.upper() for v in p.values) if p.values else ""
        lines.append("type %s = ::integer | ::enum(%s);" % (p.name, enum_values))
        return "\n".join(lines)

    supertype_map = {
        PrimitiveSupertype.STRING: "::string",
        PrimitiveSupertype.INTEGER: "::integer",
        PrimitiveSupertype.FLOAT: "::float",
        PrimitiveSupertype.BOOLEAN: "::boolean",
    }
    builtin = supertype_map[p.supertype]

    if p.supertype == PrimitiveSupertype.STRING:
        # String: #[pattern] for regex validation
        if p.pattern:
            lines.append('#[pattern(r#"%s"#)]' % p.pattern)
        # String values are plain token values
        if p.values:
            formatted = ", ".join('"%s"' % v for v in p.values)
            lines.append("#[values(%s)]" % formatted)

    elif p.supertype == PrimitiveSupertype.INTEGER:
        # Integer: #[parse] for sub-parser selection (omit if default)
        parsers = _infer_integer_parsers(p.pattern)
        if parsers:
            lines.append("#[parse(%s)]" % ", ".join(parsers))
        # Range annotation from pattern analysis
        range_str = _infer_integer_range(p.pattern)
        if range_str:
            lines.append("#[range(%s)]" % range_str)
        # Integer values map tokens to integer literals
        if p.values:
            # Sentinel tokens don't have obvious numeric mappings from
            # the XSD alone, so emit as named values without =
            formatted = ", ".join('"%s"' % v for v in p.values)
            lines.append("#[values(%s)]" % formatted)

    elif p.supertype == PrimitiveSupertype.FLOAT:
        # Float: #[parse] for sub-parser selection (omit if default)
        parsers = _infer_float_parsers(p.pattern)
        if parsers:
            lines.append("#[parse(%s)]" % ", ".join(parsers))
        # Float special values: map to M3 constants
        if p.values:
            mappings: list[str] = []
            for v in p.values:
                if v == "INF":
                    mappings.append('"INF" = ::inf')
                elif v == "-INF":
                    mappings.append('"-INF" = -::inf')
                elif v == "NaN":
                    mappings.append('"NaN" = ::nan')
                else:
                    mappings.append('"%s"' % v)
            lines.append("#[values(%s)]" % ", ".join(mappings))

    elif p.supertype == PrimitiveSupertype.BOOLEAN:
        # Boolean: #[values] maps extra tokens to true/false
        if p.values:
            mappings = []
            for v in p.values:
                if v == "1":
                    mappings.append('"1" = true')
                elif v == "0":
                    mappings.append('"0" = false')
                else:
                    mappings.append('"%s"' % v)
            lines.append("#[values(%s)]" % ", ".join(mappings))

    lines.append("type %s = %s;" % (p.name, builtin))
    return "\n".join(lines)


def generate_enum(e: ExportEnum) -> str:
    """Generate a Rupa enum type definition (multi-line, one value per line)."""
    lines: list[str] = []

    if e.doc:
        lines.append(_format_block_comment(e.doc))

    is_subtypes = e.is_subtypes_enum
    value_docs = e.value_docs if e.value_docs else []

    lines.append("type %s = ::enum(" % e.name)
    for i, val in enumerate(e.values):
        doc = value_docs[i] if i < len(value_docs) else None
        if doc:
            lines.append(_format_block_comment(doc, "    "))
        if is_subtypes:
            formatted_val = xml_to_pascal_case(val)
        elif _needs_quoting(val):
            formatted_val = '"%s"' % val
        else:
            formatted_val = val
        lines.append("    %s," % formatted_val)
    lines.append(");")

    return "\n".join(lines)


def generate_composite(c: ExportComposite, *, show_alternatives: bool = False) -> str:
    """Generate a Rupa composite type definition."""
    lines: list[str] = []

    # Type-level doc comment
    if c.doc:
        lines.append(_format_block_comment(c.doc))

    # Type-level annotations
    if c.is_abstract:
        lines.append("#[abstract]")
    if c.is_ordered:
        lines.append("#[ordered]")
    if c.is_instance_ref:
        lines.append("#[instance_ref]")

    # Type header with optional inheritance
    if c.inherits_from:
        parents = ", ".join(c.inherits_from)
        lines.append("type %s = %s {" % (c.name, parents))
    else:
        lines.append("type %s = {" % c.name)

    if not c.members:
        # Empty body: close on same line as opening brace
        lines[-1] = lines[-1][:-1] + "{ };"
    else:
        for i, m in enumerate(c.members):
            member_lines: list[str] = []
            if i > 0:
                member_lines.append("")

            # Member-level doc comment
            if m.doc:
                member_lines.append(_format_block_comment(m.doc, "    "))

            # Variant alternatives as multi-line comment above member
            type_text, alternatives = _format_type_ref(m.types, m.is_reference)
            if alternatives and show_alternatives:
                member_lines.append("    // also:")
                for alt in alternatives:
                    member_lines.append("    //   %s," % alt)

            # Instance-ref role annotation
            if m.instance_ref_role == "context":
                member_lines.append("    #[context]")
            elif m.instance_ref_role == "target":
                member_lines.append("    #[target]")

            # Member-level annotations
            if m.is_identity:
                member_lines.append("    #[id]")

            # Role name
            if m.name is None:
                role = ".."
            else:
                role = ".%s" % m.name

            # Multiplicity
            mult = _format_multiplicity(m.min_occurs, m.max_occurs)

            member_lines.append("    %s : %s%s;" % (role, type_text, mult))
            lines.extend(member_lines)

        lines.append("};")
    return "\n".join(lines)


# --- File generation ---


def _release_to_domain(release_version: str) -> str:
    """Convert 'R24-11' to 'autosar_r24_11' (underscores for lexer compatibility)."""
    return "autosar_" + release_version.lower().replace("-", "_")


def _file_header(domain_name: str, imports: list[str] | None = None) -> str:
    """Return the domain statement + import statements that start each .rupa file."""
    lines = ["domain %s;\n" % domain_name]
    if imports:
        lines.append("")
        for imp in imports:
            lines.append('import "%s.rupa";' % imp)
    lines.append("")
    return "\n".join(lines)


def generate_rupa_files(schema: ExportSchema, output_dir: str, *, show_alternatives: bool = False) -> None:
    """Write all Rupa files for the given schema to output_dir."""
    os.makedirs(output_dir, exist_ok=True)

    domain_name = _release_to_domain(schema.release_version)

    # --- domain.rupa ---
    _write(output_dir, "domain.rupa", "domain %s;\n" % domain_name)

    # --- primitives.rupa (no imports — leaf file) ---
    if schema.primitives:
        header = _file_header(domain_name)
        parts = [generate_primitive(p) for p in schema.primitives]
        _write(output_dir, "primitives.rupa", header + "\n\n".join(parts) + "\n")

    # --- enums.rupa (no imports — leaf file) ---
    if schema.enums:
        header = _file_header(domain_name)
        parts = [generate_enum(e) for e in schema.enums]
        _write(output_dir, "enums.rupa", header + "\n\n".join(parts) + "\n")

    # --- Split composites ---
    abstract_types: list[ExportComposite] = []
    base_types: list[ExportComposite] = []
    regular: list[ExportComposite] = []

    for c in schema.composites:
        if c.is_abstract:
            abstract_types.append(c)
        elif c.is_ordered or c.has_unnamed_string_member:
            base_types.append(c)
        else:
            regular.append(c)

    # abstract-types.rupa (imports primitives, enums)
    if abstract_types:
        header = _file_header(domain_name, ["primitives", "enums"])
        abstract_sorted = sorted(abstract_types, key=lambda c: c.name.lower())
        parts = [generate_composite(c, show_alternatives=show_alternatives) for c in abstract_sorted]
        _write(output_dir, "abstract-types.rupa", header + "\n\n".join(parts) + "\n")

    # base-types.rupa (imports primitives, enums, abstract-types)
    if base_types:
        header = _file_header(domain_name, ["primitives", "enums", "abstract-types"])
        parts = [generate_composite(c, show_alternatives=show_alternatives) for c in base_types]
        _write(output_dir, "base-types.rupa", header + "\n\n".join(parts) + "\n")

    # composites.rupa — single file for all regular composites
    if regular:
        header = _file_header(domain_name, ["primitives", "enums", "abstract-types", "base-types"])
        regular_sorted = sorted(regular, key=lambda c: c.name.lower())
        parts = [generate_composite(c, show_alternatives=show_alternatives) for c in regular_sorted]
        _write(output_dir, "composites.rupa", header + "\n\n".join(parts) + "\n")

    # --- index.rupa (root entry point with domain + imports to all sub-files) ---
    sub_files = []
    if schema.primitives:
        sub_files.append("primitives")
    if schema.enums:
        sub_files.append("enums")
    if abstract_types:
        sub_files.append("abstract-types")
    if base_types:
        sub_files.append("base-types")
    if regular:
        sub_files.append("composites")
    index_content = _file_header(domain_name, sub_files)
    _write(output_dir, "index.rupa", index_content)

    # --- mapping-report.md ---
    report_lines = [
        "# AUTOSAR to Rupa Mapping Report",
        "",
        "## Statistics",
        "",
        "- Primitives: %d" % len(schema.primitives),
        "- Enums: %d" % len(schema.enums),
        "- Composites: %d" % len(schema.composites),
        "  - Abstract: %d" % len(abstract_types),
        "  - Base types (ordered/mixed): %d" % len(base_types),
        "  - Regular: %d" % len(regular),
        "",
    ]

    if schema.warnings:
        report_lines.append("## Warnings")
        report_lines.append("")
        for w in schema.warnings:
            report_lines.append("- %s" % w)
        report_lines.append("")

    if schema.errors:
        report_lines.append("## Errors")
        report_lines.append("")
        for e in schema.errors:
            report_lines.append("- %s" % e)
        report_lines.append("")

    _write(output_dir, "mapping-report.md", "\n".join(report_lines))


def _write(output_dir: str, filename: str, content: str) -> None:
    """Write content to a file in output_dir."""
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
