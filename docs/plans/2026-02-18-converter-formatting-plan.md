# Converter Formatting Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the AUTOSAR XSD → Rupa converter's output formatting, fix missing annotations, and correct data issues across 9 areas.

**Architecture:** All changes are in `tools/autosar-converter/`. The parser (`schema_parser.py`) needs fixes for documentation extraction, pattern stripping, and range inference. The generator (`rupa_generator.py`) needs block comment formatting, line wrapping, blank lines, alternatives flag, range emission, and PascalCase conversion. The CLI (`converter.py`) needs an `--alternatives` flag.

**Tech Stack:** Python 3, xml.etree.ElementTree, argparse

**Testing:** Run against `/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd` and verify `output/autosar-r23-11/`. Grammar reference: `spec/appendix-a-grammar.md`.

**Multi-session support:** After each task, update the progress section at the bottom of this file. Mark tasks `[x]` when complete.

**Worktree:** This work runs in a dedicated git worktree on branch `feature/converter-formatting`.

---

## Progress Tracker

- [x] Task 0: Create worktree and branch
- [x] Task 1: Fix documentation extraction in parser
- [x] Task 2: Carry documentation through export layer
- [x] Task 3: Add block comment formatter to generator
- [x] Task 4: Apply block comments to all type generators
- [x] Task 5: Add blank lines between roles
- [x] Task 6: Add CLI `--alternatives` flag
- [x] Task 7: Add integer range annotations
- [x] Task 8: Convert subtypes enum values to PascalCase
- [x] Task 9: Strip token values from string patterns
- [x] Task 10: Full integration verification

---

### Task 0: Create Worktree and Branch

**Files:** None (git operations only)

**Step 1: Create feature branch and worktree**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec
git branch feature/converter-formatting
git worktree add ../rupa-spec-formatting feature/converter-formatting
```

**Step 2: Verify worktree**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting
git branch --show-current
```

Expected: `feature/converter-formatting`

All subsequent tasks run in `/Users/ekuhn/CLionProjects/rupa-spec-formatting/`.

---

### Task 1: Fix Documentation Extraction in Parser

**Context:** `_analyze_simple_type()` calls `get_documentation(elem)` for enumerations (line 468) but NOT for aliases or bare primitives. Subtypes enums also miss it.

**Files:**
- Modify: `tools/autosar-converter/schema_parser.py` — `_analyze_simple_type()` (lines 442–506)

**Step 1: Add doc extraction for subtypes enums**

In `_analyze_simple_type()`, after `InternalSubTypesEnum` creation (line 479), add:

```python
            subtypes.doc = get_documentation(elem)
```

Insert after line 479 (`schema.sub_types[xml_name] = subtypes`), before the `else:` on line 481.

**Step 2: Add doc extraction for aliases**

After `InternalAlias` creation (line 495, after `_reroute_alias_target(alias)`), add:

```python
        alias.doc = get_documentation(elem)
```

**Step 3: Add doc extraction for bare primitives**

After `InternalPrimitiveType` creation (line 500–503), add:

```python
            schema.types[xml_name].doc = get_documentation(elem)
```

**Step 4: Verify**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting
python3 -c "
from tools.autosar_converter_path import *
import sys; sys.path.insert(0, 'tools/autosar-converter')
from schema_parser import parse_schema
internal = parse_schema('/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd')
# Check a known alias
alias = internal.types.get('ALIGNMENT-TYPE--SIMPLE')
print('AlignmentType doc:', alias.doc[:60] if alias and alias.doc else 'MISSING')
# Check a subtypes enum
st = internal.types.get('ABSTRACT-EVENT--SUBTYPES-ENUM')
print('AbstractEvent subtypes doc:', st.doc[:60] if st and st.doc else 'None (expected for subtypes)')
"
```

If the import path doesn't work, run directly:

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 -c "
from schema_parser import parse_schema
internal = parse_schema('/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd')
from schema_model import InternalAlias, InternalSubTypesEnum
aliases_with_doc = sum(1 for t in internal.types.values() if isinstance(t, InternalAlias) and t.doc)
subtypes_with_doc = sum(1 for t in internal.types.values() if isinstance(t, InternalSubTypesEnum) and t.doc)
print(f'Aliases with doc: {aliases_with_doc}')
print(f'Subtypes enums with doc: {subtypes_with_doc}')
"
```

Expected: Non-zero counts for aliases with doc.

**Step 5: Commit**

```bash
git add tools/autosar-converter/schema_parser.py
git commit -m "fix(autosar-converter): extract documentation for aliases and subtypes enums"
```

---

### Task 2: Carry Documentation Through Export Layer

**Context:** `_export_primitive()`, `_export_alias()`, and `_export_subtypes_enum()` don't pass `doc` to their export models.

**Files:**
- Modify: `tools/autosar-converter/schema_parser.py` — export functions (lines 1375–1412)

**Step 1: Fix `_export_primitive`**

Change line 1380 from:

```python
    return ExportPrimitive(name=prim.name, supertype=supertype)
```

To:

```python
    return ExportPrimitive(name=prim.name, supertype=supertype, doc=prim.doc)
```

**Step 2: Fix `_export_alias`**

In `_export_alias`, the function has two return paths. Both need `doc`:

Path 1 (line 1391–1396, pattern exists):

```python
        return ExportPrimitive(
            name=alias.name,
            supertype=supertype,
            pattern=cleaned_pattern,
            values=values,
            doc=alias.doc,
        )
```

Path 2 (line 1401, no pattern):

```python
    return ExportPrimitive(name=alias.name, doc=alias.doc)
```

**Step 3: Fix `_export_subtypes_enum`**

Change line 1412 from:

```python
    return ExportEnum(name=st.name, values=st.types, is_subtypes_enum=True)
```

To:

```python
    return ExportEnum(name=st.name, values=st.types, is_subtypes_enum=True, doc=st.doc)
```

**Step 4: Verify**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 -c "
from schema_parser import parse_schema, export_schema
internal = parse_schema('/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd')
schema = export_schema(internal)
prims_with_doc = sum(1 for p in schema.primitives if p.doc)
enums_with_doc = sum(1 for e in schema.enums if e.doc)
print(f'Primitives with doc: {prims_with_doc}/{len(schema.primitives)}')
print(f'Enums with doc: {enums_with_doc}/{len(schema.enums)}')
"
```

Expected: Non-zero primitives and enums with doc.

**Step 5: Commit**

```bash
git add tools/autosar-converter/schema_parser.py
git commit -m "fix(autosar-converter): carry documentation through export layer for primitives and subtypes enums"
```

---

### Task 3: Add Block Comment Formatter to Generator

**Context:** Replace `///` doc comments with `/** ... */` block comments. Multi-line uses ` * ` prefixed continuation. Wrap at ~80 chars (sentence boundary), hard break at 100 chars (whitespace).

**Files:**
- Modify: `tools/autosar-converter/rupa_generator.py` — add helper functions after the existing helpers section

**Step 1: Add the `_format_block_comment` function**

Add after line 27 (after `_needs_quoting`), before the parser inference section:

```python
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
```

**Step 2: Verify the formatter works**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 -c "
from rupa_generator import _format_block_comment
# Short text
print(_format_block_comment('Short description.'))
print()
# Long text
long = 'This meta-class provides one count value for a AbstractAccessPoint. This attribute controls the provision of return values for RTE APIs generated by the RTE generator.'
print(_format_block_comment(long))
print()
# Indented (member-level)
print(_format_block_comment(long, '    '))
"
```

Expected:
- Short text → single-line `/** Short description. */`
- Long text → multi-line with `/**`, ` * ` prefixed lines, ` */`
- No line exceeds 100 chars

**Step 3: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py
git commit -m "feat(autosar-converter): add block comment formatter with line wrapping"
```

---

### Task 4: Apply Block Comments to All Type Generators

**Context:** Replace `/// text` with `_format_block_comment(text)` in `generate_primitive`, `generate_enum`, `generate_composite`.

**Files:**
- Modify: `tools/autosar-converter/rupa_generator.py` — three generator functions

**Step 1: Update `generate_primitive`**

Replace lines 127–128:

```python
    if p.doc:
        lines.append("/// %s" % p.doc)
```

With:

```python
    if p.doc:
        lines.append(_format_block_comment(p.doc))
```

**Step 2: Update `generate_enum`**

Replace lines 199–200:

```python
    if e.doc:
        lines.append("/// %s" % e.doc)
```

With:

```python
    if e.doc:
        lines.append(_format_block_comment(e.doc))
```

Also replace the value-level doc comment (line 209):

```python
        if doc:
            lines.append("    /// %s" % doc)
```

With:

```python
        if doc:
            lines.append(_format_block_comment(doc, "    "))
```

**Step 3: Update `generate_composite`**

Replace type-level doc (lines 221–222):

```python
    if c.doc:
        lines.append("/// %s" % c.doc)
```

With:

```python
    if c.doc:
        lines.append(_format_block_comment(c.doc))
```

Replace member-level doc (lines 248–249):

```python
            if m.doc:
                member_lines.append("    /// %s" % m.doc)
```

With:

```python
            if m.doc:
                member_lines.append(_format_block_comment(m.doc, "    "))
```

**Step 4: Run the converter and verify**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
```

Check output:

```bash
head -30 ../../output/autosar-r23-11/abstract-types.rupa
```

Expected: `/** ... */` block comments instead of `///`.

Verify no line exceeds 100 chars:

```bash
awk 'length > 100' ../../output/autosar-r23-11/abstract-types.rupa | head -5
```

Expected: Empty or very few lines (only code lines, not comments).

**Step 5: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py
git commit -m "feat(autosar-converter): switch all doc comments to block comment format"
```

---

### Task 5: Add Blank Lines Between Roles

**Context:** Insert a blank line between each member declaration in composite type bodies.

**Files:**
- Modify: `tools/autosar-converter/rupa_generator.py` — `generate_composite()` (around line 244)

**Step 1: Add blank line separator between members**

In `generate_composite`, the member loop (starting around line 244) iterates `c.members` and appends `member_lines` to `lines`. Add a blank line before each member except the first.

Replace the member loop section:

```python
        for m in c.members:
            member_lines: list[str] = []
```

With:

```python
        for i, m in enumerate(c.members):
            member_lines: list[str] = []
            if i > 0:
                member_lines.append("")
```

**Step 2: Run and verify**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
grep -A 15 "type AccessCount = " ../../output/autosar-r23-11/composites-a-d.rupa
```

Expected: Blank line between each member declaration.

**Step 3: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py
git commit -m "feat(autosar-converter): add blank line between role declarations"
```

---

### Task 6: Add CLI `--alternatives` Flag

**Context:** Variant alternative comments (`// also:`) should be off by default. Add `--alternatives` flag to enable them.

**Files:**
- Modify: `tools/autosar-converter/converter.py` — switch from sys.argv to argparse
- Modify: `tools/autosar-converter/rupa_generator.py` — add `show_alternatives` parameter

**Step 1: Update `converter.py` to use argparse**

Replace the entire `main()` function:

```python
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Convert AUTOSAR XSD schema to Rupa domain files."
    )
    parser.add_argument("schema", help="Path to AUTOSAR XSD schema file")
    parser.add_argument("output_dir", help="Output directory for .rupa files")
    parser.add_argument(
        "--alternatives", action="store_true", default=False,
        help="Generate variant alternative comments (// also:) on members",
    )
    args = parser.parse_args()

    if not os.path.exists(args.schema):
        print(f"Error: Schema file not found: {args.schema}")
        sys.exit(1)

    print(f"Parsing {args.schema}...")
    internal = parse_schema(args.schema)

    print("Exporting schema model...")
    schema = export_schema(internal)

    print(f"Generating Rupa files in {args.output_dir}/...")
    os.makedirs(args.output_dir, exist_ok=True)
    generate_rupa_files(schema, args.output_dir, show_alternatives=args.alternatives)

    print(f"Done. {len(schema.primitives)} primitives, "
          f"{len(schema.enums)} enums, "
          f"{len(schema.composites)} composites.")
    if schema.warnings:
        print(f"  {len(schema.warnings)} warnings (see mapping-report.md)")
    if schema.errors:
        print(f"  {len(schema.errors)} ERRORS (see mapping-report.md)")
```

**Step 2: Update `generate_rupa_files` signature**

In `rupa_generator.py`, change:

```python
def generate_rupa_files(schema: ExportSchema, output_dir: str) -> None:
```

To:

```python
def generate_rupa_files(schema: ExportSchema, output_dir: str, *, show_alternatives: bool = False) -> None:
```

**Step 3: Pass `show_alternatives` to `generate_composite`**

Update `generate_composite` signature:

```python
def generate_composite(c: ExportComposite, *, show_alternatives: bool = False) -> str:
```

In the variant alternatives block (around line 253), wrap with the flag:

```python
            if alternatives and show_alternatives:
```

(Was `if alternatives:`)

**Step 4: Update all `generate_composite` call sites in `generate_rupa_files`**

There are 3 calls to `generate_composite` in `generate_rupa_files`:

```python
        parts = [generate_composite(c, show_alternatives=show_alternatives) for c in abstract_sorted]
```

```python
        parts = [generate_composite(c, show_alternatives=show_alternatives) for c in base_types]
```

```python
            parts = [generate_composite(c, show_alternatives=show_alternatives) for c in chunk]
```

**Step 5: Verify alternatives are suppressed by default**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
grep "// also:" ../../output/autosar-r23-11/composites-a-d.rupa | wc -l
```

Expected: 0 (no alternative comments without `--alternatives` flag)

```bash
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11 --alternatives
grep "// also:" ../../output/autosar-r23-11/composites-a-d.rupa | wc -l
```

Expected: Non-zero count (alternatives enabled).

**Step 6: Run without flag for final output**

```bash
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
```

**Step 7: Commit**

```bash
git add tools/autosar-converter/converter.py tools/autosar-converter/rupa_generator.py
git commit -m "feat(autosar-converter): add --alternatives flag, suppress variant comments by default"
```

---

### Task 7: Add Integer Range Annotations

**Context:** Infer `#[range(>=0)]` or `#[range(>=1)]` for integer primitives based on their XSD regex pattern. If pattern has a minus sign (`\-`), it's signed → no range. Otherwise check if zero is a standalone alternative.

**Files:**
- Modify: `tools/autosar-converter/rupa_generator.py` — `generate_primitive()` and new helper

**Step 1: Add `_infer_integer_range` helper**

Add after `_infer_float_parsers` (around line 86):

```python
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
```

**Step 2: Emit range in `generate_primitive`**

In `generate_primitive`, in the INTEGER branch (after the `#[parse]` annotation, around line 151), add:

```python
        # Range annotation from pattern analysis
        range_str = _infer_integer_range(p.pattern)
        if range_str:
            lines.append("#[range(%s)]" % range_str)
```

Insert this after the `#[parse]` block (lines 149–151) and before the `#[values]` block (lines 153–157).

**Step 3: Verify**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
grep -B1 "type PositiveIntegerSimple" ../../output/autosar-r23-11/primitives.rupa
grep -B1 "type IntegerSimple" ../../output/autosar-r23-11/primitives.rupa
grep -B1 "type UnlimitedIntegerSimple" ../../output/autosar-r23-11/primitives.rupa
```

Expected:
- `PositiveIntegerSimple` → preceded by `#[range(>=0)]`
- `IntegerSimple` → NO range annotation (signed, has `\-`)
- `UnlimitedIntegerSimple` → NO range annotation (signed, has `\-`)

**Step 4: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py
git commit -m "feat(autosar-converter): add integer range annotations from pattern analysis"
```

---

### Task 8: Convert Subtypes Enum Values to PascalCase

**Context:** Subtypes enum values are currently raw XML kebab-case names (e.g., `"ABSTRACT-EVENT"`). Convert to PascalCase bare identifiers (e.g., `AbstractEvent`).

**Files:**
- Modify: `tools/autosar-converter/rupa_generator.py` — `generate_enum()`

**Step 1: Import `xml_to_pascal_case`**

Add to the imports at the top of `rupa_generator.py`:

```python
from name_converter import xml_to_pascal_case
```

**Step 2: Update `generate_enum` for subtypes**

In `generate_enum`, the loop that formats values (around line 206–211) needs to handle subtypes enums differently. Replace:

```python
    needs_quoting = e.is_subtypes_enum or any(_needs_quoting(v) for v in e.values)
```

With:

```python
    is_subtypes = e.is_subtypes_enum
    needs_quoting = (not is_subtypes) and any(_needs_quoting(v) for v in e.values)
```

And replace the value formatting line:

```python
        formatted_val = '"%s"' % val if needs_quoting else val
```

With:

```python
        if is_subtypes:
            formatted_val = xml_to_pascal_case(val)
        elif needs_quoting:
            formatted_val = '"%s"' % val
        else:
            formatted_val = val
```

**Step 3: Verify**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
head -16 ../../output/autosar-r23-11/enums.rupa
```

Expected:
```rupa
type AbstractAccessPointSubtypesEnum = ::enum(
    AbstractAccessPoint,
    AsynchronousServerCallPoint,
    ...
);
```

(PascalCase, unquoted)

Also verify non-subtypes enums are unchanged:

```bash
grep -A 5 "type AccessControlEnum" ../../output/autosar-r23-11/enums.rupa
```

Expected: Still uses qualifiedName values (`custom`, `modeled`).

**Step 4: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py
git commit -m "feat(autosar-converter): convert subtypes enum values to PascalCase identifiers"
```

---

### Task 9: Strip Token Values from String Patterns

**Context:** In `analyze_pattern()`, when an integer type is demoted to string (has non-float tokens), the cleaned pattern incorrectly includes both regex parts AND token values. The tokens should be stripped since they're already in `#[values()]`.

**Files:**
- Modify: `tools/autosar-converter/schema_parser.py` — `analyze_pattern()` (lines 194–202)

**Step 1: Fix the integer-demotion path**

Replace lines 194–202:

```python
    # Integer with non-numeric tokens: demote to string.
    # Float special values (INF, -INF, NaN) are fine — they have M3 mappings.
    if supertype == PrimitiveSupertype.INTEGER and tokens:
        non_float_tokens = [t for t in tokens if t not in _FLOAT_SPECIAL_VALUES]
        if non_float_tokens:
            supertype = PrimitiveSupertype.STRING
            # Restore original pattern (tokens + regex together)
            cleaned = "|".join(regex_parts + tokens) if regex_parts else "|".join(tokens)
            return supertype, cleaned, tokens
```

With:

```python
    # Integer with non-numeric tokens: demote to string.
    # Float special values (INF, -INF, NaN) are fine — they have M3 mappings.
    if supertype == PrimitiveSupertype.INTEGER and tokens:
        non_float_tokens = [t for t in tokens if t not in _FLOAT_SPECIAL_VALUES]
        if non_float_tokens:
            supertype = PrimitiveSupertype.STRING
            # Strip token values from pattern — they go into #[values()]
            cleaned = "|".join(regex_parts) if regex_parts else None
            return supertype, cleaned, tokens
```

The only change is line 201: `"|".join(regex_parts + tokens)` → `"|".join(regex_parts)`.

**Step 2: Verify**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 -c "
from schema_parser import analyze_pattern
p = '[1-9][0-9]*|0[xX][0-9a-fA-F]*|0[bB][0-1]+|0[0-7]*|UNSPECIFIED|UNKNOWN|BOOLEAN|PTR'
supertype, cleaned, values = analyze_pattern(p, 'AlignmentTypeSimple')
print('cleaned:', cleaned)
print('values:', values)
assert 'UNSPECIFIED' not in cleaned, 'Token still in pattern!'
print('OK: tokens stripped from pattern')
"
```

Expected: `cleaned` should NOT contain `UNSPECIFIED`, `UNKNOWN`, `BOOLEAN`, or `PTR`.

**Step 3: Run full converter and verify output**

```bash
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
grep -A 2 "type AlignmentTypeSimple" ../../output/autosar-r23-11/primitives.rupa
```

Expected:
```rupa
#[pattern("[1-9][0-9]*|0[xX][0-9a-fA-F]*|0[bB][0-1]+|0[0-7]*")]
#[values("UNSPECIFIED", "UNKNOWN", "BOOLEAN", "PTR")]
type AlignmentTypeSimple = ::string;
```

**Step 4: Commit**

```bash
git add tools/autosar-converter/schema_parser.py
git commit -m "fix(autosar-converter): strip token values from string patterns when values annotation exists"
```

---

### Task 10: Full Integration Verification

**Context:** Run the complete converter and verify all 9 changes are working correctly together.

**Files:** None (verification only)

**Step 1: Run converter (without alternatives)**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
```

**Step 2: Verify each change**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting

# 1. No alternative comments (suppressed by default)
echo "=== Check 1: No alternatives ==="
grep -c "// also:" output/autosar-r23-11/composites-a-d.rupa

# 2. Blank lines between roles
echo "=== Check 2: Blank lines between roles ==="
grep -A 8 "type AccessCount = " output/autosar-r23-11/composites-a-d.rupa | head -12

# 3-5. Block comments with wrapping
echo "=== Check 3-5: Block comments ==="
head -15 output/autosar-r23-11/abstract-types.rupa

# 6. Integer range annotations
echo "=== Check 6: Integer ranges ==="
grep -B 2 "type PositiveIntegerSimple" output/autosar-r23-11/primitives.rupa
grep -B 2 "type IntegerSimple" output/autosar-r23-11/primitives.rupa

# 7. PascalCase subtypes enums
echo "=== Check 7: PascalCase enums ==="
head -16 output/autosar-r23-11/enums.rupa

# 8. Stripped patterns
echo "=== Check 8: Stripped patterns ==="
grep -B 2 "type AlignmentTypeSimple" output/autosar-r23-11/primitives.rupa

# 9. Enum/primitive documentation
echo "=== Check 9: Documentation ==="
grep -B 3 "type AccessControlEnum" output/autosar-r23-11/enums.rupa
```

**Step 3: Check line lengths**

```bash
for f in output/autosar-r23-11/*.rupa; do
    long=$(awk 'length > 100' "$f" | wc -l)
    if [ "$long" -gt 0 ]; then
        echo "$f: $long lines > 100 chars"
    fi
done
```

Expected: Minimal or zero lines exceeding 100 chars (some code lines may legitimately be long).

**Step 4: Verify with --alternatives too**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec-formatting/tools/autosar-converter
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11 --alternatives
grep -c "// also:" ../../output/autosar-r23-11/composites-a-d.rupa
```

Expected: Non-zero.

**Step 5: Final run without alternatives (production output)**

```bash
python3 converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd ../../output/autosar-r23-11
```

**Step 6: Commit generated output**

```bash
git add output/autosar-r23-11/
git commit -m "chore: regenerate output with formatting improvements"
```

---

## File Reference

| File | Path | Role |
|------|------|------|
| CLI entry point | `tools/autosar-converter/converter.py` | argparse, orchestration |
| Generator | `tools/autosar-converter/rupa_generator.py` | All output formatting |
| Parser | `tools/autosar-converter/schema_parser.py` | Doc extraction, pattern analysis |
| Models | `tools/autosar-converter/schema_model.py` | Data classes (no changes needed) |
| Name utils | `tools/autosar-converter/name_converter.py` | `xml_to_pascal_case` (used, not modified) |
| Test schema | `/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd` | Input XSD |
| Output | `output/autosar-r23-11/` | Generated .rupa files |
| Grammar ref | `spec/appendix-a-grammar.md` | Syntax reference |
