# AUTOSAR Converter Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the AUTOSAR XSD-to-Rupa converter to extract documentation, format output readably, fix integer-with-token inference, and annotate instance-ref types.

**Architecture:** Incremental changes to the existing 3-layer pipeline (schema_parser → schema_model → rupa_generator). Each task adds one capability, tested independently. Model fields added first, then parser extraction, then generator formatting.

**Tech Stack:** Python 3, unittest, xml.etree.ElementTree

**Working directory:** `tools/autosar-converter/` (all relative paths below are from here)

**Run tests with:** `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`

---

### Task 1: Add `doc` fields to model classes

**Files:**
- Modify: `schema_model.py:19-52` (ExportMember, ExportPrimitive, ExportEnum, ExportComposite)
- Modify: `schema_model.py:71-95` (InternalMember, InternalType)
- Test: `tests/test_schema_parser.py` (existing tests should still pass)

**Step 1: Add `doc` to internal model classes**

In `schema_model.py`, add `doc: str | None = None` to:

- `InternalMember` (line 72, after `name`):
```python
@dataclass
class InternalMember:
    name: str | None
    doc: str | None = None
    xml_types: list[str] = field(default_factory=list)
    # ... rest unchanged
```

- `InternalType` (line 84, after `namespace`):
```python
@dataclass
class InternalType:
    name: str
    xml_name: str
    namespace: str
    doc: str | None = None
    is_abstract: bool = False
    stereotypes: list[str] = field(default_factory=list)
```

- `InternalEnumeration` — add `value_docs` parallel to `values`:
```python
@dataclass
class InternalEnumeration(InternalType):
    values: list[str] = field(default_factory=list)
    value_docs: list[str | None] = field(default_factory=list)
```

**Step 2: Add `doc` to export model classes**

In `schema_model.py`, add `doc: str | None = None` to:

- `ExportMember` (after `is_identity`):
```python
@dataclass
class ExportMember:
    name: str | None
    types: list[str]
    is_reference: bool = False
    is_ordered: bool = False
    min_occurs: int | None = None
    max_occurs: int | None = None
    is_identity: bool = False
    doc: str | None = None
```

- `ExportPrimitive` (after `values`):
```python
@dataclass
class ExportPrimitive:
    name: str
    supertype: PrimitiveSupertype = PrimitiveSupertype.STRING
    pattern: str | None = None
    values: list[str] = field(default_factory=list)
    doc: str | None = None
```

- `ExportEnum` — add `doc` and `value_docs`:
```python
@dataclass
class ExportEnum:
    name: str
    values: list[str]
    is_subtypes_enum: bool = False
    doc: str | None = None
    value_docs: list[str | None] = field(default_factory=list)
```

- `ExportComposite` (after `inherits_from`):
```python
@dataclass
class ExportComposite:
    name: str
    members: list[ExportMember] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)
    is_ordered: bool = False
    has_unnamed_string_member: bool = False
    is_abstract: bool = False
    inherits_from: list[str] = field(default_factory=list)
    doc: str | None = None
```

**Step 3: Run existing tests to verify no regressions**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All existing tests PASS (new fields have defaults, no breakage)

**Step 4: Commit**

```bash
git add tools/autosar-converter/schema_model.py
git commit -m "feat(autosar-converter): add doc fields to model classes"
```

---

### Task 2: Add `get_documentation` helper and extract docs during parsing

**Files:**
- Modify: `schema_parser.py:205-218` (add `get_documentation` next to `get_appinfo`)
- Modify: `schema_parser.py:258-298` (`_get_member_from_appinfo` — extract member doc)
- Modify: `schema_parser.py:315-320` (`_get_name` — extract type doc)
- Modify: `schema_parser.py:387-397` (`_get_enum_value`/`_get_enum_values` — extract enum value docs)
- Modify: `schema_parser.py:410-472` (`_analyze_simple_type` — store doc on enums)
- Modify: `schema_parser.py:663-710` (`_analyze_group_sequence` — store doc on group)
- Modify: `schema_parser.py:785-806` (`_analyze_group` — store doc on group type)
- Modify: `schema_parser.py:906-931` (`_analyze_complex_type` — store doc on complex type)
- Test: `tests/test_schema_parser.py` (add new tests)

**Step 1: Write failing tests for doc extraction**

Add to `tests/test_schema_parser.py`:

```python
class TestDocumentationExtraction(unittest.TestCase):
    def test_get_documentation_from_group(self):
        from schema_parser import get_documentation
        root = ElementTree.fromstring(SIMPLE_GROUP_XSD)
        ns = {"xsd": "http://www.w3.org/2001/XMLSchema"}
        group = root.find("xsd:group", ns)
        doc = get_documentation(group)
        self.assertEqual(doc, "Maximum allowable deviation")

    def test_get_documentation_from_element(self):
        from schema_parser import get_documentation
        root = ElementTree.fromstring(SIMPLE_GROUP_XSD)
        ns = {"xsd": "http://www.w3.org/2001/XMLSchema"}
        group = root.find("xsd:group", ns)
        seq = group.find("xsd:sequence", ns)
        elem = seq.find("xsd:element", ns)
        doc = get_documentation(elem)
        self.assertEqual(doc, "Max deviation in seconds")

    def test_get_documentation_missing(self):
        from schema_parser import get_documentation
        # Element with no annotation at all
        elem = ElementTree.fromstring('<xsd:element xmlns:xsd="http://www.w3.org/2001/XMLSchema" name="X" type="xsd:string"/>')
        doc = get_documentation(elem)
        self.assertIsNone(doc)

    def test_group_type_has_doc(self):
        from schema_parser import parse_schema_from_string
        schema = parse_schema_from_string(SIMPLE_GROUP_XSD)
        t = schema.types["groups:ABSOLUTE-TOLERANCE"]
        self.assertEqual(t.doc, "Maximum allowable deviation")

    def test_group_member_has_doc(self):
        from schema_parser import parse_schema_from_string
        schema = parse_schema_from_string(SIMPLE_GROUP_XSD)
        t = schema.types["groups:ABSOLUTE-TOLERANCE"]
        self.assertEqual(t.members[0].doc, "Max deviation in seconds")

    def test_enum_value_docs(self):
        """Enum values should have doc extracted from xsd:documentation."""
        xsd = '''\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">
  <xsd:simpleType name="MY-STATUS--SIMPLE">
    <xsd:restriction base="xsd:string">
      <xsd:enumeration value="OK">
        <xsd:annotation>
          <xsd:documentation>All good</xsd:documentation>
          <xsd:appinfo source="tags">mmt.qualifiedName="MyStatus.ok"</xsd:appinfo>
        </xsd:annotation>
      </xsd:enumeration>
      <xsd:enumeration value="FAIL">
        <xsd:annotation>
          <xsd:documentation>Something broke</xsd:documentation>
          <xsd:appinfo source="tags">mmt.qualifiedName="MyStatus.fail"</xsd:appinfo>
        </xsd:annotation>
      </xsd:enumeration>
    </xsd:restriction>
  </xsd:simpleType>
</xsd:schema>'''
        from schema_parser import parse_schema_from_string
        from schema_model import InternalEnumeration
        schema = parse_schema_from_string(xsd)
        t = schema.types["MY-STATUS--SIMPLE"]
        self.assertIsInstance(t, InternalEnumeration)
        self.assertEqual(t.value_docs, ["All good", "Something broke"])
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_schema_parser.py::TestDocumentationExtraction -v`
Expected: FAIL — `get_documentation` not defined, `doc` attributes missing

**Step 3: Implement `get_documentation` in `schema_parser.py`**

Add after `get_appinfo` (around line 219):

```python
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
```

**Step 4: Wire doc extraction into `_get_member_from_appinfo`**

In `_get_member_from_appinfo` (line ~274), after creating the member, add:

```python
    member = InternalMember(name=name, doc=get_documentation(element))
```

**Step 5: Wire doc extraction into `_analyze_group_sequence`**

In `_analyze_group_sequence` (line ~670), after creating `res`, add:

```python
    res.doc = get_documentation(elem)
```

**Step 6: Wire doc extraction into `_analyze_group` for choice groups**

In `_analyze_group_choice` (line ~778), after `res = _analyze_mixed(...)`, if res is not None:

```python
    if res is not None:
        res.doc = get_documentation(elem)
        return res
```

**Step 7: Wire doc extraction into `_analyze_complex_type`**

In `_analyze_complex_type` (line ~911), after creating `ct`:

```python
    ct.doc = get_documentation(elem)
```

**Step 8: Wire doc extraction into enum parsing**

Modify `_get_enum_value` to also return doc, and `_get_enum_values` to return parallel docs list. Replace both functions:

```python
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
```

Update `_analyze_simple_type` where `_get_enum_values` is called (line ~426):

```python
        values, value_docs = _get_enum_values(restriction)
        if len(values) > 0:
            enumeration = InternalEnumeration(
                name=xml_to_pascal_case(xml_name),
                xml_name=xml_name,
                namespace=_ENUM_NS,
                values=values,
                value_docs=value_docs,
            )
```

Also extract type-level doc for the simpleType:

```python
            enumeration.doc = get_documentation(elem)
```

**Step 9: Run tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 10: Commit**

```bash
git add tools/autosar-converter/schema_parser.py tools/autosar-converter/tests/test_schema_parser.py
git commit -m "feat(autosar-converter): extract documentation from XSD annotations"
```

---

### Task 3: Carry docs through export layer

**Files:**
- Modify: `schema_parser.py:1232-1251` (`_export_member` — copy doc)
- Modify: `schema_parser.py:1268-1294` (`_export_composite` — copy doc)
- Modify: `schema_parser.py:1336-1341` (`_export_enum` / `_export_subtypes_enum` — copy doc)
- Test: `tests/test_schema_parser.py` (add export doc tests)

**Step 1: Write failing tests**

Add to `tests/test_schema_parser.py`:

```python
class TestExportDocumentation(unittest.TestCase):
    def test_exported_composite_has_doc(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(SIMPLE_GROUP_XSD)
        export = export_schema(schema)
        t = next((c for c in export.composites if c.name == "AbsoluteTolerance"), None)
        self.assertIsNotNone(t)
        self.assertEqual(t.doc, "Maximum allowable deviation")

    def test_exported_member_has_doc(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(SIMPLE_GROUP_XSD)
        export = export_schema(schema)
        t = next((c for c in export.composites if c.name == "AbsoluteTolerance"), None)
        m = next((m for m in t.members if m.name == "absolute"), None)
        self.assertIsNotNone(m)
        self.assertEqual(m.doc, "Max deviation in seconds")
```

**Step 2: Run to verify failure**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_schema_parser.py::TestExportDocumentation -v`
Expected: FAIL — doc is None on exported types

**Step 3: Wire doc through export functions**

In `_export_member` (line ~1243), add `doc=mem.doc` to ExportMember constructor:

```python
    return ExportMember(
        name=mem.name,
        types=type_names,
        is_reference=mem.is_reference,
        is_ordered=mem.is_ordered,
        min_occurs=mem.min_occurs,
        max_occurs=mem.max_occurs,
        is_identity=is_identity,
        doc=mem.doc,
    )
```

In `_export_composite` (line ~1286), add `doc=comp.doc`:

```python
    return ExportComposite(
        name=comp.name,
        members=members,
        identifiers=identifiers,
        is_ordered=is_ordered,
        has_unnamed_string_member=has_unnamed_string,
        is_abstract=comp.is_abstract,
        inherits_from=_resolve_inherits_from(comp, schema),
        doc=comp.doc,
    )
```

In `_export_enum` (line ~1336):

```python
def _export_enum(enum: InternalEnumeration) -> ExportEnum:
    return ExportEnum(
        name=enum.name,
        values=enum.values,
        is_subtypes_enum=False,
        doc=enum.doc,
        value_docs=enum.value_docs,
    )
```

**Step 4: Run all tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tools/autosar-converter/schema_parser.py tools/autosar-converter/tests/test_schema_parser.py
git commit -m "feat(autosar-converter): carry documentation through export layer"
```

---

### Task 4: Generate doc comments in Rupa output

**Files:**
- Modify: `rupa_generator.py:134-200` (`generate_primitive` — add doc comment)
- Modify: `rupa_generator.py:203-210` (`generate_enum` — multi-line with doc comments)
- Modify: `rupa_generator.py:213-257` (`generate_composite` — doc comments on types and members)
- Test: `tests/test_rupa_generator.py` (add doc comment tests)

**Step 1: Write failing tests**

Add to `tests/test_rupa_generator.py`:

```python
class TestDocComments(unittest.TestCase):
    def test_composite_doc_comment(self):
        from rupa_generator import generate_composite
        c = ExportComposite("AbsoluteTolerance",
                            members=[
                                ExportMember("absolute", ["TimeValue"],
                                             min_occurs=0, max_occurs=1,
                                             doc="Max deviation in seconds"),
                            ],
                            inherits_from=["TimeRangeTypeTolerance"],
                            doc="Maximum allowable deviation")
        text = generate_composite(c)
        self.assertIn("/// Maximum allowable deviation", text)
        self.assertIn("/// Max deviation in seconds", text)

    def test_composite_no_doc(self):
        from rupa_generator import generate_composite
        c = ExportComposite("EmptyType", doc=None)
        text = generate_composite(c)
        self.assertNotIn("///", text)

    def test_member_doc_before_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Foo", members=[
            ExportMember("bar", ["BarType"], min_occurs=1, max_occurs=1,
                         doc="The bar field"),
        ])
        text = generate_composite(c)
        lines = text.split("\n")
        doc_idx = next(i for i, l in enumerate(lines) if "/// The bar field" in l)
        member_idx = next(i for i, l in enumerate(lines) if ".bar" in l)
        self.assertLess(doc_idx, member_idx)

    def test_enum_multi_line_with_docs(self):
        from rupa_generator import generate_enum
        e = ExportEnum("StatusEnum", ["ok", "fail"],
                       doc="Status type",
                       value_docs=["All good", "Something broke"])
        text = generate_enum(e)
        self.assertIn("/// Status type", text)
        self.assertIn("/// All good", text)
        self.assertIn("/// Something broke", text)
        # Values on separate lines
        self.assertIn("\n    ok,", text)
        self.assertIn("\n    fail,", text)

    def test_enum_multi_line_no_docs(self):
        from rupa_generator import generate_enum
        e = ExportEnum("AlignEnum", ["center", "left", "right"])
        text = generate_enum(e)
        # Should still be multi-line, one per line
        self.assertIn("\n    center,", text)
        self.assertIn("\n    left,", text)
        self.assertIn("\n    right,", text)

    def test_enum_subtypes_quoted_multi_line(self):
        from rupa_generator import generate_enum
        e = ExportEnum("SubEnum",
                       ["ABSTRACT-ACCESS-POINT", "CALL-POINT"],
                       is_subtypes_enum=True)
        text = generate_enum(e)
        self.assertIn('\n    "ABSTRACT-ACCESS-POINT",', text)
        self.assertIn('\n    "CALL-POINT",', text)

    def test_primitive_doc_comment(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("CIdent", PrimitiveSupertype.STRING,
                            pattern="[a-zA-Z_]+",
                            doc="C identifier")
        text = generate_primitive(p)
        self.assertIn("/// C identifier", text)
```

**Step 2: Run to verify failure**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_rupa_generator.py::TestDocComments -v`
Expected: FAIL

**Step 3: Implement doc comments in `generate_primitive`**

At the start of `generate_primitive`, before annotations:

```python
def generate_primitive(p: ExportPrimitive) -> str:
    lines: list[str] = []

    if p.doc:
        lines.append("/// %s" % p.doc)

    # ... rest unchanged
```

**Step 4: Implement multi-line enum with doc comments in `generate_enum`**

Replace `generate_enum` entirely:

```python
def generate_enum(e: ExportEnum) -> str:
    """Generate a Rupa enum type definition (multi-line, one value per line)."""
    lines: list[str] = []

    if e.doc:
        lines.append("/// %s" % e.doc)

    needs_quoting = e.is_subtypes_enum or any(_needs_quoting(v) for v in e.values)
    value_docs = e.value_docs if e.value_docs else []

    lines.append("type %s = ::enum(" % e.name)
    for i, val in enumerate(e.values):
        doc = value_docs[i] if i < len(value_docs) else None
        if doc:
            lines.append("    /// %s" % doc)
        formatted_val = '"%s"' % val if needs_quoting else val
        lines.append("    %s," % formatted_val)
    lines.append(");")

    return "\n".join(lines)
```

**Step 5: Implement doc comments in `generate_composite`**

Add doc comment at the start (before `#[abstract]` etc.):

```python
def generate_composite(c: ExportComposite) -> str:
    lines: list[str] = []

    # Type-level doc comment
    if c.doc:
        lines.append("/// %s" % c.doc)

    # Type-level annotations
    if c.is_abstract:
        lines.append("#[abstract]")
    # ... rest of type-level annotations unchanged ...
```

For member doc comments, inside the member loop, add before annotations:

```python
        for m in c.members:
            member_lines: list[str] = []

            # Member-level doc comment
            if m.doc:
                member_lines.append("    /// %s" % m.doc)

            # Member-level annotations (existing code)
            if m.is_identity:
                member_lines.append("    #[id]")
            # ... rest unchanged
```

**Step 6: Update existing enum tests**

The existing `test_regular_enum` and `test_subtypes_enum_quoted` tests will now fail because the enum format changed from single-line to multi-line. Update them:

```python
    def test_regular_enum(self):
        from rupa_generator import generate_enum
        e = ExportEnum("AlignEnumSimple", ["center", "justify", "left", "right"])
        text = generate_enum(e)
        self.assertIn("type AlignEnumSimple = ::enum(", text)
        self.assertIn("\n    center,", text)
        self.assertIn("\n    justify,", text)
        self.assertIn("\n    left,", text)
        self.assertIn("\n    right,", text)
        self.assertIn("\n);", text)

    def test_subtypes_enum_quoted(self):
        from rupa_generator import generate_enum
        e = ExportEnum("SubtypesEnum",
                       ["ABSTRACT-ACCESS-POINT", "SOME-OTHER"],
                       is_subtypes_enum=True)
        text = generate_enum(e)
        self.assertIn('"ABSTRACT-ACCESS-POINT",', text)
        self.assertIn('"SOME-OTHER",', text)
```

**Step 7: Run all tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py tools/autosar-converter/tests/test_rupa_generator.py
git commit -m "feat(autosar-converter): generate doc comments and multi-line enums"
```

---

### Task 5: Multi-line variant comments above members

**Files:**
- Modify: `rupa_generator.py:107-128` (`_format_type_ref` — return alternatives list instead of inline comment)
- Modify: `rupa_generator.py:234-254` (member generation loop — emit multi-line comment above)
- Test: `tests/test_rupa_generator.py` (update variant tests)

**Step 1: Write failing tests**

Add to `tests/test_rupa_generator.py`:

```python
class TestMultiLineVariantComments(unittest.TestCase):
    def test_variant_above_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Foo", members=[
            ExportMember("bar", ["Primary", "Alt1", "Alt2"],
                         min_occurs=0, max_occurs=1),
        ])
        text = generate_composite(c)
        # Alternatives should be above the member as comments
        self.assertIn("// also:", text)
        self.assertIn("//   Alt1,", text)
        self.assertIn("//   Alt2", text)
        self.assertIn(".bar : Primary?;", text)
        # No trailing comment on member line
        lines = text.split("\n")
        member_line = next(l for l in lines if ".bar" in l)
        self.assertNotIn("// also", member_line)

    def test_no_variant_no_comment(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Foo", members=[
            ExportMember("bar", ["Only"], min_occurs=1, max_occurs=1),
        ])
        text = generate_composite(c)
        self.assertNotIn("// also", text)

    def test_many_variants_all_shown(self):
        from rupa_generator import generate_composite
        types = ["Primary"] + ["Type%d" % i for i in range(10)]
        c = ExportComposite("Foo", members=[
            ExportMember("bar", types, min_occurs=0, max_occurs=1),
        ])
        text = generate_composite(c)
        # ALL alternatives shown, no truncation
        for i in range(10):
            self.assertIn("Type%d" % i, text)
        self.assertNotIn("more)", text)
```

**Step 2: Run to verify failure**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_rupa_generator.py::TestMultiLineVariantComments -v`
Expected: FAIL

**Step 3: Refactor `_format_type_ref` to return alternatives list**

Replace `_format_type_ref`:

```python
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
```

Remove `_MAX_VARIANT_COMMENT_TYPES` constant.

**Step 4: Update member generation loop in `generate_composite`**

Replace the member generation section:

```python
        for m in c.members:
            member_lines: list[str] = []

            # Member-level doc comment
            if m.doc:
                member_lines.append("    /// %s" % m.doc)

            # Variant alternatives as multi-line comment above member
            type_text, alternatives = _format_type_ref(m.types, m.is_reference)
            if alternatives:
                member_lines.append("    // also:")
                for alt in alternatives:
                    member_lines.append("    //   %s," % alt)

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
```

**Step 5: Update old variant tests**

Update `TestVariantCommentTruncation` — rename and fix assertions:

```python
class TestVariantComments(unittest.TestCase):
    def test_short_variant(self):
        from rupa_generator import _format_type_ref
        types = ["A", "B", "C"]
        primary, alts = _format_type_ref(types, False)
        self.assertEqual(primary, "A")
        self.assertEqual(alts, ["B", "C"])

    def test_long_variant_not_truncated(self):
        from rupa_generator import _format_type_ref
        types = ["Primary"] + ["Type%d" % i for i in range(10)]
        primary, alts = _format_type_ref(types, False)
        self.assertEqual(primary, "Primary")
        self.assertEqual(len(alts), 10)
```

**Step 6: Run all tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py tools/autosar-converter/tests/test_rupa_generator.py
git commit -m "feat(autosar-converter): multi-line variant comments above members"
```

---

### Task 6: Fix integer-with-token fallback to string

**Files:**
- Modify: `schema_parser.py:148-197` (`analyze_pattern` — demote integer to string when tokens aren't numeric)
- Test: `tests/test_schema_parser.py` (add pattern analysis tests)

**Step 1: Write failing tests**

Add to `tests/test_schema_parser.py`:

```python
class TestIntegerTokenFallback(unittest.TestCase):
    def test_integer_with_non_numeric_tokens_becomes_string(self):
        """Integer pattern with tokens like UNSPECIFIED should fall back to string."""
        from schema_parser import analyze_pattern
        from schema_model import PrimitiveSupertype
        # Pattern like AlignmentTypeSimple: integers + UNSPECIFIED + BOOLEAN + PTR
        pattern = "(0[xX][0-9a-fA-F]+)|(0[0-7]+)|(0[bB][0-1]+)|([1-9][0-9]*)|0|UNSPECIFIED|UNKNOWN|BOOLEAN|PTR"
        supertype, cleaned, tokens = analyze_pattern(pattern, "AlignmentTypeSimple")
        self.assertEqual(supertype, PrimitiveSupertype.STRING)

    def test_float_with_inf_nan_stays_float(self):
        """Float special values (INF, -INF, NaN) should NOT trigger fallback."""
        from schema_parser import analyze_pattern
        from schema_model import PrimitiveSupertype
        pattern = r"([+\-]?[1-9][0-9]+(\.[0-9]+)?|[+\-]?[0-9](\.[0-9]+)?)([eE]([+\-]?)[0-9]+)?|INF|-INF|NaN"
        supertype, cleaned, tokens = analyze_pattern(pattern, "LimitValueSimple")
        self.assertEqual(supertype, PrimitiveSupertype.FLOAT)

    def test_integer_without_tokens_stays_integer(self):
        """Pure integer pattern without tokens stays integer."""
        from schema_parser import analyze_pattern
        from schema_model import PrimitiveSupertype
        pattern = "(0[xX][0-9a-fA-F]+)|(0[0-7]+)|(0[bB][0-1]+)|([1-9][0-9]*)|0"
        supertype, cleaned, tokens = analyze_pattern(pattern, "IntegerSimple")
        self.assertEqual(supertype, PrimitiveSupertype.INTEGER)

    def test_integer_with_any_token_becomes_string(self):
        """Even a single non-numeric token like 'ANY' forces string."""
        from schema_parser import analyze_pattern
        from schema_model import PrimitiveSupertype
        pattern = "[1-9][0-9]*|0|ANY"
        supertype, _, tokens = analyze_pattern(pattern, "AnyServiceInstanceIdSimple")
        self.assertEqual(supertype, PrimitiveSupertype.STRING)
```

**Step 2: Run to verify failure**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_schema_parser.py::TestIntegerTokenFallback -v`
Expected: FAIL — integers with tokens currently stay as INTEGER

**Step 3: Fix `analyze_pattern` to demote integer with non-numeric tokens**

In `analyze_pattern` (line ~184), after determining supertype, add a check before the return:

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

**Step 4: Run all tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tools/autosar-converter/schema_parser.py tools/autosar-converter/tests/test_schema_parser.py
git commit -m "fix(autosar-converter): demote integer types with non-numeric tokens to string"
```

---

### Task 7: Add instance-ref support to model and parser

**Files:**
- Modify: `schema_model.py` (add `is_instance_ref` to ExportComposite, `instance_ref_role` to ExportMember)
- Modify: `schema_parser.py` (detect `instanceRef` stereotype, classify member roles from XML names)
- Test: `tests/test_schema_parser.py`

**Step 1: Write failing tests**

Add XSD fixture and test class to `tests/test_schema_parser.py`:

```python
INSTANCE_REF_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">

  <xsd:group name="AR-OBJECT">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="ARObject"</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence/>
  </xsd:group>

  <xsd:attributeGroup name="AR-OBJECT">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="ARObject"</xsd:appinfo>
    </xsd:annotation>
  </xsd:attributeGroup>

  <xsd:group name="ATP-INSTANCE-REF">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="AtpInstanceRef"</xsd:appinfo>
      <xsd:appinfo source="stereotypes">atpObject</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence/>
  </xsd:group>

  <xsd:group name="P-PORT-IN-COMPOSITION-INSTANCE-REF">
    <xsd:annotation>
      <xsd:documentation>Reference to a p-port in context of a composition</xsd:documentation>
      <xsd:appinfo source="tags">mmt.qualifiedName="PPortInCompositionInstanceRef"</xsd:appinfo>
      <xsd:appinfo source="stereotypes">atpObject,instanceRef</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence>
      <xsd:element maxOccurs="unbounded" minOccurs="0" name="CONTEXT-COMPONENT-REF">
        <xsd:annotation>
          <xsd:documentation>Context component prototype</xsd:documentation>
          <xsd:appinfo source="tags">mmt.qualifiedName="PPortInCompositionInstanceRef.contextComponent";pureMM.maxOccurs="-1";pureMM.minOccurs="0"</xsd:appinfo>
        </xsd:annotation>
        <xsd:complexType>
          <xsd:simpleContent>
            <xsd:extension base="AR:REF">
              <xsd:attribute name="DEST" type="xsd:string" use="required"/>
            </xsd:extension>
          </xsd:simpleContent>
        </xsd:complexType>
      </xsd:element>
      <xsd:element maxOccurs="1" minOccurs="0" name="TARGET-P-PORT-REF">
        <xsd:annotation>
          <xsd:documentation>Target p-port prototype</xsd:documentation>
          <xsd:appinfo source="tags">mmt.qualifiedName="PPortInCompositionInstanceRef.targetPPort";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
        </xsd:annotation>
        <xsd:complexType>
          <xsd:simpleContent>
            <xsd:extension base="AR:REF">
              <xsd:attribute name="DEST" type="xsd:string" use="required"/>
            </xsd:extension>
          </xsd:simpleContent>
        </xsd:complexType>
      </xsd:element>
    </xsd:sequence>
  </xsd:group>

  <xsd:complexType name="P-PORT-IN-COMPOSITION-INSTANCE-REF">
    <xsd:annotation>
      <xsd:documentation>Reference to a p-port in context of a composition</xsd:documentation>
      <xsd:appinfo source="tags">mmt.qualifiedName="PPortInCompositionInstanceRef"</xsd:appinfo>
      <xsd:appinfo source="stereotypes">atpObject,instanceRef</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence>
      <xsd:group ref="AR:AR-OBJECT"/>
      <xsd:group ref="AR:ATP-INSTANCE-REF"/>
      <xsd:group ref="AR:P-PORT-IN-COMPOSITION-INSTANCE-REF"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="AR:AR-OBJECT"/>
  </xsd:complexType>
</xsd:schema>
"""


class TestInstanceRefDetection(unittest.TestCase):
    def test_instance_ref_stereotype_detected(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(INSTANCE_REF_XSD)
        export = export_schema(schema)
        t = next((c for c in export.composites
                  if c.name == "PPortInCompositionInstanceRef"), None)
        self.assertIsNotNone(t)
        self.assertTrue(t.is_instance_ref)

    def test_context_role_detected(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(INSTANCE_REF_XSD)
        export = export_schema(schema)
        t = next((c for c in export.composites
                  if c.name == "PPortInCompositionInstanceRef"), None)
        ctx = next((m for m in t.members if m.name == "contextComponent"), None)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.instance_ref_role, "context")

    def test_target_role_detected(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(INSTANCE_REF_XSD)
        export = export_schema(schema)
        t = next((c for c in export.composites
                  if c.name == "PPortInCompositionInstanceRef"), None)
        tgt = next((m for m in t.members if m.name == "targetPPort"), None)
        self.assertIsNotNone(tgt)
        self.assertEqual(tgt.instance_ref_role, "target")

    def test_non_instance_ref_has_no_role(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(SIMPLE_GROUP_XSD)
        export = export_schema(schema)
        t = next((c for c in export.composites
                  if c.name == "AbsoluteTolerance"), None)
        self.assertFalse(t.is_instance_ref)
        for m in t.members:
            self.assertIsNone(m.instance_ref_role)
```

**Step 2: Run to verify failure**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_schema_parser.py::TestInstanceRefDetection -v`
Expected: FAIL — `is_instance_ref` and `instance_ref_role` don't exist

**Step 3: Add model fields**

In `schema_model.py`:

Add to `ExportMember` (after `doc`):
```python
    instance_ref_role: str | None = None  # "context", "target", or None
```

Add to `ExportComposite` (after `doc`):
```python
    is_instance_ref: bool = False
```

Add to `InternalMember` (after `doc`):
```python
    xml_element_name: str | None = None  # Original XML element name for role detection
```

**Step 4: Capture XML element name in `_get_member_from_appinfo`**

The member's XML element name is needed for role classification. Currently `_get_member_from_appinfo` doesn't capture it. Modify to accept and store it. In `_get_member_from_appinfo`, the `element` parameter has an `attrib["name"]` — store it:

After creating the member:
```python
    member = InternalMember(name=name, doc=get_documentation(element))
    if "name" in element.attrib:
        member.xml_element_name = element.attrib["name"]
```

**Step 5: Detect instance ref in export**

In `_export_composite`, detect `instanceRef` stereotype and classify member roles:

```python
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
```

In `_export_composite`:

```python
    is_instance_ref = "instanceRef" in stereos

    # ... existing member export ...

    if is_instance_ref:
        for em, im in zip(members, comp.members):
            em.instance_ref_role = _classify_instance_ref_role(im.xml_element_name)

    return ExportComposite(
        # ... existing fields ...
        is_instance_ref=is_instance_ref,
    )
```

**Step 6: Run all tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add tools/autosar-converter/schema_model.py tools/autosar-converter/schema_parser.py tools/autosar-converter/tests/test_schema_parser.py
git commit -m "feat(autosar-converter): detect instance-ref types and context/target roles"
```

---

### Task 8: Generate instance-ref annotations in Rupa output

**Files:**
- Modify: `rupa_generator.py:213-257` (`generate_composite` — emit `#[instance_ref]`, `#[context]`, `#[target]`)
- Test: `tests/test_rupa_generator.py`

**Step 1: Write failing tests**

Add to `tests/test_rupa_generator.py`:

```python
class TestInstanceRefGeneration(unittest.TestCase):
    def test_instance_ref_annotation(self):
        from rupa_generator import generate_composite
        c = ExportComposite("PPortInstanceRef",
                            members=[
                                ExportMember("contextComponent", ["SwComponentPrototype"],
                                             is_reference=True,
                                             min_occurs=0, max_occurs=None,
                                             instance_ref_role="context"),
                                ExportMember("targetPPort", ["PPortPrototype"],
                                             is_reference=True,
                                             min_occurs=0, max_occurs=1,
                                             instance_ref_role="target"),
                            ],
                            inherits_from=["AtpInstanceRef"],
                            is_instance_ref=True)
        text = generate_composite(c)
        self.assertIn("#[instance_ref]", text)
        self.assertIn("#[context]", text)
        self.assertIn("#[target]", text)
        self.assertIn(".contextComponent", text)
        self.assertIn(".targetPPort", text)

    def test_no_instance_ref_annotation_on_regular(self):
        from rupa_generator import generate_composite
        c = ExportComposite("RegularType", members=[
            ExportMember("foo", ["Bar"], min_occurs=1, max_occurs=1),
        ])
        text = generate_composite(c)
        self.assertNotIn("#[instance_ref]", text)
        self.assertNotIn("#[context]", text)
        self.assertNotIn("#[target]", text)

    def test_context_before_target(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Ref",
                            members=[
                                ExportMember("ctx", ["A"], is_reference=True,
                                             min_occurs=0, max_occurs=None,
                                             instance_ref_role="context"),
                                ExportMember("tgt", ["B"], is_reference=True,
                                             min_occurs=0, max_occurs=1,
                                             instance_ref_role="target"),
                            ],
                            is_instance_ref=True)
        text = generate_composite(c)
        ctx_pos = text.index("#[context]")
        tgt_pos = text.index("#[target]")
        self.assertLess(ctx_pos, tgt_pos)
```

**Step 2: Run to verify failure**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_rupa_generator.py::TestInstanceRefGeneration -v`
Expected: FAIL

**Step 3: Implement instance-ref annotations in `generate_composite`**

In the type-level annotations section, after `#[ordered]`:

```python
    if c.is_instance_ref:
        lines.append("#[instance_ref]")
```

In the member loop, add role annotation after doc comment and before `#[id]`:

```python
            # Instance-ref role annotation
            if m.instance_ref_role == "context":
                member_lines.append("    #[context]")
            elif m.instance_ref_role == "target":
                member_lines.append("    #[target]")
```

**Step 4: Run all tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py tools/autosar-converter/tests/test_rupa_generator.py
git commit -m "feat(autosar-converter): generate instance_ref annotations in Rupa output"
```

---

### Task 9: Regenerate output and run integration tests

**Files:**
- Run: converter against real XSD
- Verify: `output/autosar-r23-11/*.rupa` regenerated with improvements
- Run: integration tests

**Step 1: Run the converter**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python tools/autosar-converter/converter.py /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd output/autosar-r23-11/`
Expected: Completes without error, prints statistics

**Step 2: Spot-check generated files**

Verify:
- `output/autosar-r23-11/enums.rupa` — multi-line format, doc comments present
- `output/autosar-r23-11/abstract-types.rupa` — doc comments on types and members
- `output/autosar-r23-11/composites-a-d.rupa` — multi-line variant comments, instance-ref annotations
- `output/autosar-r23-11/primitives.rupa` — integer types like AlignmentTypeSimple are now `::string`

**Step 3: Run integration tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/test_integration.py -v`
Expected: PASS (may need minor count adjustments if integer→string demotion changes primitive counts)

**Step 4: Run full test suite**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec/tools/autosar-converter && python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit regenerated output**

```bash
git add output/autosar-r23-11/
git commit -m "chore(autosar): regenerate output with doc comments, multi-line format, instance-ref annotations"
```

---

### Task 10: Final review and cleanup

**Step 1: Review the mapping report**

Read `output/autosar-r23-11/mapping-report.md` to check for new warnings/errors.

**Step 2: Verify instance-ref types in output**

Search generated output for `#[instance_ref]` — should find multiple instance-ref types with `#[context]` and `#[target]` annotations.

**Step 3: Verify integer fallback in output**

Check that types like `AlignmentTypeSimple`, `AnyServiceInstanceIdSimple`, `AxisIndexTypeSimple` are now `::string` instead of `::integer` (they all have non-numeric tokens).

**Step 4: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore(autosar-converter): final cleanup after converter improvements"
```
