# AUTOSAR XSD-to-Rupa Converter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python script that converts AUTOSAR XSD schema files into Rupa domain definition files, to validate Rupa's type system against a real-world 1000+ type metamodel.

**Architecture:** Three-module pipeline: `schema_parser.py` (XSD -> internal model using dataclasses), `rupa_generator.py` (internal model -> Rupa source files), `converter.py` (CLI orchestration). The existing `autosar-dsl/meta-model-generator/schema_analyzer.py` is the blueprint for parsing logic but will be cleanly rewritten.

**Tech Stack:** Python 3.14, `xml.etree.ElementTree` (stdlib), `dataclasses`, `unittest` for tests.

**CRITICAL:** Before writing `rupa_generator.py`, agents MUST read these files to understand the exact Rupa syntax:
- `/Users/ekuhn/CLionProjects/rupa-spec/spec/appendix-a-grammar.md` — PEG grammar (normative)
- `/Users/ekuhn/CLionProjects/rupa-spec/spec/04-declarations.md` — Type/role declaration syntax and annotations

**Blueprint reference:** `/Users/ekuhn/CLionProjects/autosar-dsl/meta-model-generator/schema_analyzer.py` (1118 lines) — read this before implementing the parser.

**XSD input file:** `/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd` (~10MB, R23-11)

---

## Task 1: Project Structure

**Files:**
- Create: `tools/autosar-converter/__init__.py`
- Create: `tools/autosar-converter/tests/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p tools/autosar-converter/tests
touch tools/autosar-converter/__init__.py
touch tools/autosar-converter/tests/__init__.py
```

**Step 2: Commit**

```bash
git add tools/autosar-converter/
git commit -m "chore: scaffold autosar-converter project structure"
```

---

## Task 2: Name Conversion Utilities

**Files:**
- Create: `tools/autosar-converter/name_converter.py`
- Create: `tools/autosar-converter/tests/test_name_converter.py`

### Context

AUTOSAR XSD uses three name conventions that must be converted:
- XML tag names: `ABSOLUTE-TOLERANCE` -> PascalCase `AbsoluteTolerance`
- `mmt.qualifiedName` type names: already PascalCase (e.g., `AbsoluteTolerance`)
- `mmt.qualifiedName` member names: `ClassName.memberName` -> extract `memberName`, lowercase first char unless ALL-CAPS

The blueprint handles this in `_get_name_from_xml_name` (line 31) and `_Member.__init__` (line 165).

**Step 1: Write failing tests**

```python
# tools/autosar-converter/tests/test_name_converter.py
import unittest


class TestXmlToPascalCase(unittest.TestCase):
    def test_simple(self):
        from name_converter import xml_to_pascal_case
        self.assertEqual(xml_to_pascal_case("ABSOLUTE-TOLERANCE"), "AbsoluteTolerance")

    def test_double_hyphen(self):
        from name_converter import xml_to_pascal_case
        self.assertEqual(xml_to_pascal_case("ALIGN-ENUM--SIMPLE"), "AlignEnumSimple")

    def test_single_word(self):
        from name_converter import xml_to_pascal_case
        self.assertEqual(xml_to_pascal_case("AUTOSAR"), "Autosar")


class TestExtractQualifiedName(unittest.TestCase):
    def test_type_name(self):
        from name_converter import extract_qualified_name
        self.assertEqual(
            extract_qualified_name('mmt.qualifiedName="AbsoluteTolerance"'),
            "AbsoluteTolerance",
        )

    def test_member_name(self):
        from name_converter import extract_qualified_name
        self.assertEqual(
            extract_qualified_name(
                'mmt.qualifiedName="AbsoluteTolerance.absolute";pureMM.maxOccurs="1"'
            ),
            "absolute",
        )

    def test_no_match(self):
        from name_converter import extract_qualified_name
        self.assertIsNone(extract_qualified_name("some other text"))

    def test_with_extra_prefix(self):
        from name_converter import extract_qualified_name
        self.assertEqual(
            extract_qualified_name(
                'mmt.RestrictToStandards="CP";mmt.qualifiedName="AbstractAccessPoint.returnValueProvision"'
            ),
            "returnValueProvision",
        )


class TestMemberNameNormalize(unittest.TestCase):
    def test_already_lower(self):
        from name_converter import normalize_member_name
        self.assertEqual(normalize_member_name("absolute"), "absolute")

    def test_upper_first(self):
        from name_converter import normalize_member_name
        self.assertEqual(normalize_member_name("ShortName"), "shortName")

    def test_all_caps_preserved(self):
        from name_converter import normalize_member_name
        self.assertEqual(normalize_member_name("URL"), "URL")

    def test_camel_case(self):
        from name_converter import normalize_member_name
        self.assertEqual(normalize_member_name("returnValueProvision"), "returnValueProvision")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tools/autosar-converter/tests/test_name_converter.py -v 2>/dev/null || python3 -m unittest tools/autosar-converter/tests/test_name_converter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'name_converter'`

**Step 3: Write implementation**

```python
# tools/autosar-converter/name_converter.py
"""Name conversion utilities for AUTOSAR XSD -> Rupa."""

import re

_QUALIFIED_NAME_RE = re.compile(r'mmt\.qualifiedName="(?:\w+\.)?(\w+)"')


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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python3 -m unittest tools/autosar-converter/tests/test_name_converter -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tools/autosar-converter/name_converter.py tools/autosar-converter/tests/test_name_converter.py
git commit -m "feat(autosar-converter): add name conversion utilities"
```

---

## Task 3: Internal Type Model (Dataclasses)

**Files:**
- Create: `tools/autosar-converter/schema_model.py`

### Context

This defines the intermediate representation between XSD parsing and Rupa generation. The blueprint uses ad-hoc classes (`_Type`, `_ComplexType`, `_Member`, etc.); we replace with typed dataclasses.

Two layers:
1. **Internal model** — mirrors XSD structure, used during parsing (includes XML references, namespace tags)
2. **Export model** — consumer-friendly, used by the Rupa generator (resolved types, clean names)

**Step 1: Write the model**

```python
# tools/autosar-converter/schema_model.py
"""Internal and export type models for AUTOSAR XSD schema."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto


# --- Export Model (consumer-facing, used by generators) ---


class PrimitiveSupertype(Enum):
    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()


@dataclass
class ExportMember:
    name: str | None
    types: list[str]
    is_reference: bool = False
    is_ordered: bool = False
    min_occurs: int | None = None  # None = optional (0)
    max_occurs: int | None = None  # None = unbounded
    is_identity: bool = False


@dataclass
class ExportPrimitive:
    name: str
    supertype: PrimitiveSupertype = PrimitiveSupertype.STRING
    pattern: str | None = None


@dataclass
class ExportEnum:
    name: str
    values: list[str]
    is_subtypes_enum: bool = False


@dataclass
class ExportComposite:
    name: str
    members: list[ExportMember] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)
    is_ordered: bool = False
    has_unnamed_string_member: bool = False


@dataclass
class ExportSchema:
    release_version: str = "R00-00"
    autosar_version: str = "0.0.0"
    primitives: list[ExportPrimitive] = field(default_factory=list)
    enums: list[ExportEnum] = field(default_factory=list)
    composites: list[ExportComposite] = field(default_factory=list)
    root_type: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# --- Internal Model (used during parsing, mirrors XSD structure) ---


@dataclass
class InternalMember:
    name: str | None
    xml_types: list[str] = field(default_factory=list)
    type_names: list[str] = field(default_factory=list)
    xml_sub_types: str | None = None
    is_ordered: bool = False
    is_reference: bool = False
    stereotypes: list[str] = field(default_factory=list)
    min_occurs: int | None = None
    max_occurs: int | None = None


@dataclass
class InternalType:
    name: str
    xml_name: str
    namespace: str
    is_abstract: bool = False
    stereotypes: list[str] = field(default_factory=list)


@dataclass
class InternalComplexType(InternalType):
    members: list[InternalMember] = field(default_factory=list)
    inherits_from: list[str] = field(default_factory=list)


@dataclass
class InternalPrimitiveType(InternalType):
    pass


@dataclass
class InternalAlias(InternalType):
    target: str | None = None
    pattern: str | None = None


@dataclass
class InternalEnumeration(InternalType):
    values: list[str] = field(default_factory=list)


@dataclass
class InternalSubTypesEnum(InternalType):
    types: list[str] = field(default_factory=list)


@dataclass
class InternalSchema:
    autosar_version: str = "0.0.0"
    release_version: str = "R00-00"
    types: dict[str, InternalType] = field(default_factory=dict)
    sub_types: dict[str, InternalSubTypesEnum] = field(default_factory=dict)
    root: InternalMember | None = None
```

**Step 2: Commit**

```bash
git add tools/autosar-converter/schema_model.py
git commit -m "feat(autosar-converter): add internal and export type models"
```

---

## Task 4: XSD Schema Parser — Core Infrastructure

**Files:**
- Create: `tools/autosar-converter/schema_parser.py`
- Create: `tools/autosar-converter/tests/test_schema_parser.py`

### Context

Read the blueprint at `/Users/ekuhn/CLionProjects/autosar-dsl/meta-model-generator/schema_analyzer.py` before implementing. Key patterns to replicate:

- XSD namespace: `{"xsd": "http://www.w3.org/2001/XMLSchema"}`
- `AR:` prefix stripping from type refs (e.g., `AR:TIME-VALUE` -> `TIME-VALUE`)
- Appinfo extraction from `<xsd:annotation>/<xsd:appinfo source="tags">`
- Stereotype extraction from `<xsd:annotation>/<xsd:appinfo source="stereotypes">`
- Version info from XML comments in first 20 lines

The XSD file starts with patterns like (lines 9-11):
```
Part of AUTOSAR Release:        R23-11
Covered Standards:              4.9.0
```

**Step 1: Write test with small XSD fragment**

```python
# tools/autosar-converter/tests/test_schema_parser.py
import unittest
from xml.etree import ElementTree

# Minimal XSD fragments for testing
SIMPLE_GROUP_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">
  <xsd:group name="ABSOLUTE-TOLERANCE">
    <xsd:annotation>
      <xsd:documentation>Maximum allowable deviation</xsd:documentation>
      <xsd:appinfo source="tags">mmt.qualifiedName="AbsoluteTolerance"</xsd:appinfo>
      <xsd:appinfo source="stereotypes">atpObject</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence>
      <xsd:element maxOccurs="1" minOccurs="0" name="ABSOLUTE" type="AR:TIME-VALUE">
        <xsd:annotation>
          <xsd:documentation>Max deviation in seconds</xsd:documentation>
          <xsd:appinfo source="tags">mmt.qualifiedName="AbsoluteTolerance.absolute";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
        </xsd:annotation>
      </xsd:element>
    </xsd:sequence>
  </xsd:group>
</xsd:schema>
"""

SIMPLE_ENUM_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">
  <xsd:simpleType name="ACCESS-CONTROL-ENUM--SIMPLE">
    <xsd:restriction base="xsd:string">
      <xsd:enumeration value="CUSTOM">
        <xsd:annotation>
          <xsd:appinfo source="tags">atp.EnumerationLiteralIndex="1";mmt.qualifiedName="AccessControlEnum.custom"</xsd:appinfo>
        </xsd:annotation>
      </xsd:enumeration>
      <xsd:enumeration value="MODELED">
        <xsd:annotation>
          <xsd:appinfo source="tags">atp.EnumerationLiteralIndex="0";mmt.qualifiedName="AccessControlEnum.modeled"</xsd:appinfo>
        </xsd:annotation>
      </xsd:enumeration>
    </xsd:restriction>
  </xsd:simpleType>
</xsd:schema>
"""

SUBTYPES_ENUM_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">
  <xsd:simpleType name="ABSTRACT-ACCESS-POINT--SUBTYPES-ENUM">
    <xsd:restriction base="xsd:string">
      <xsd:enumeration value="ABSTRACT-ACCESS-POINT"/>
      <xsd:enumeration value="ASYNCHRONOUS-SERVER-CALL-POINT"/>
    </xsd:restriction>
  </xsd:simpleType>
</xsd:schema>
"""


class TestParserHelpers(unittest.TestCase):
    def test_get_appinfo_tags(self):
        from schema_parser import get_appinfo
        root = ElementTree.fromstring(SIMPLE_GROUP_XSD)
        ns = {"xsd": "http://www.w3.org/2001/XMLSchema"}
        group = root.find("xsd:group", ns)
        text = get_appinfo(group, "tags")
        self.assertIn("mmt.qualifiedName", text)

    def test_get_stereotypes(self):
        from schema_parser import get_stereotypes
        root = ElementTree.fromstring(SIMPLE_GROUP_XSD)
        ns = {"xsd": "http://www.w3.org/2001/XMLSchema"}
        group = root.find("xsd:group", ns)
        stereos = get_stereotypes(group)
        self.assertEqual(stereos, ["atpObject"])

    def test_drop_ar_prefix(self):
        from schema_parser import drop_ar_prefix
        self.assertEqual(drop_ar_prefix("AR:TIME-VALUE"), "TIME-VALUE")
        self.assertEqual(drop_ar_prefix("PLAIN-NAME"), "PLAIN-NAME")


class TestAnalyzeSimpleType(unittest.TestCase):
    def test_regular_enum(self):
        from schema_parser import parse_schema_from_string
        schema = parse_schema_from_string(SIMPLE_ENUM_XSD)
        key = "ACCESS-CONTROL-ENUM--SIMPLE"
        self.assertIn(key, schema.types)
        from schema_model import InternalEnumeration
        t = schema.types[key]
        self.assertIsInstance(t, InternalEnumeration)
        self.assertEqual(t.name, "AccessControlEnumSimple")
        self.assertEqual(sorted(t.values), ["custom", "modeled"])

    def test_subtypes_enum(self):
        from schema_parser import parse_schema_from_string
        schema = parse_schema_from_string(SUBTYPES_ENUM_XSD)
        key = "ABSTRACT-ACCESS-POINT--SUBTYPES-ENUM"
        self.assertIn(key, schema.types)
        from schema_model import InternalSubTypesEnum
        t = schema.types[key]
        self.assertIsInstance(t, InternalSubTypesEnum)
        self.assertIn("ABSTRACT-ACCESS-POINT", t.types)


class TestAnalyzeGroup(unittest.TestCase):
    def test_simple_group(self):
        from schema_parser import parse_schema_from_string
        from schema_model import InternalComplexType
        schema = parse_schema_from_string(SIMPLE_GROUP_XSD)
        key = "groups:ABSOLUTE-TOLERANCE"
        self.assertIn(key, schema.types)
        t = schema.types[key]
        self.assertIsInstance(t, InternalComplexType)
        self.assertEqual(t.name, "AbsoluteTolerance")
        self.assertEqual(len(t.members), 1)
        self.assertEqual(t.members[0].name, "absolute")
        self.assertEqual(t.members[0].xml_types, ["TIME-VALUE"])
        self.assertEqual(t.members[0].min_occurs, 0)
        self.assertEqual(t.members[0].max_occurs, 1)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python3 -m unittest tools/autosar-converter/tests/test_schema_parser -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write parser implementation**

Implement `schema_parser.py` following the blueprint's logic. The parser must handle:

1. **Helper functions**: `get_appinfo()`, `get_stereotypes()`, `drop_ar_prefix()`, `get_element_name()`, `get_member_from_appinfo()`
2. **Simple type analysis**: regular enums (values from `mmt.qualifiedName`), subtypes enums (values from XML `value` attr), aliases (with optional regex pattern), primitives
3. **Group analysis**: sequence groups with members (invariant, variant, wrapped-variant, reference elements), choice groups (mixed content)
4. **Attribute group analysis**: attribute members
5. **Complex type analysis**: sequence with group refs, simple content extension
6. **Root element detection**
7. **Inheritance flattening**: merge group/attributeGroup members into complex types
8. **Unused type truncation**
9. **Export**: convert internal model to ExportSchema

The blueprint file to reference is: `/Users/ekuhn/CLionProjects/autosar-dsl/meta-model-generator/schema_analyzer.py`

Key implementation notes:
- The `_PRIM_ALIAS` mapping converts XSD base types: `"string"` -> `"StringSimple"`, `"unsignedInt"` -> `"PositiveIntegerSimple"`, `"double"` -> `"NumericalValueSimple"`, `"INTEGER"` -> `"IntegerSimple"`
- Namespace prefixes for internal dict keys: `"groups:"`, `"attributes:"`, `"complex"`, `"alias"`, `"enumeration"`, `"primitive"`, `"subtypes"`
- Reference members are detected by `<xsd:extension base="AR:REF">` inside `<xsd:simpleContent>`
- Cardinality comes from `pureMM.minOccurs` and `pureMM.maxOccurs` in appinfo (NOT from XSD `minOccurs`/`maxOccurs` attributes)
- Identity comes from `atpIdentityContributor` stereotype on member elements
- Mixed/ordered types come from `atpMixed` or `atpMixedString` stereotypes
- `atpMixedString` types get an unnamed string member (name=None)

Provide `parse_schema_from_string(xml_string)` for testing and `parse_schema(filepath)` for production use. Both should return `InternalSchema`.

Also provide `export_schema(internal: InternalSchema) -> ExportSchema` that:
1. Flattens inheritance (merge group members into complex types)
2. Truncates unused types
3. Converts internal types to export types
4. Resolves member type names
5. Identifies composites with identity contributors
6. Detects ordered/mixed types

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python3 -m unittest tools/autosar-converter/tests/test_schema_parser -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tools/autosar-converter/schema_parser.py tools/autosar-converter/tests/test_schema_parser.py
git commit -m "feat(autosar-converter): implement XSD schema parser"
```

---

## Task 5: Integration Test — Parse Full AUTOSAR XSD

**Files:**
- Create: `tools/autosar-converter/tests/test_integration.py`

### Context

Verify the parser handles the full 10MB AUTOSAR R23-11 schema without errors. The JSON output for R23-11 has roughly 1400+ composites and 500+ primitives/enums. Use these as sanity checks.

**Step 1: Write integration test**

```python
# tools/autosar-converter/tests/test_integration.py
import unittest
import os
import sys

SCHEMA_PATH = "/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd"


@unittest.skipUnless(os.path.exists(SCHEMA_PATH), "AUTOSAR schema not available")
class TestFullSchemaParsing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from schema_parser import parse_schema, export_schema
        cls.internal = parse_schema(SCHEMA_PATH)
        cls.schema = export_schema(cls.internal)

    def test_version_info(self):
        self.assertEqual(self.schema.release_version, "R23-11")
        self.assertIn("4.9", self.schema.autosar_version)

    def test_has_primitives(self):
        self.assertGreater(len(self.schema.primitives), 10)

    def test_has_enums(self):
        self.assertGreater(len(self.schema.enums), 50)

    def test_has_composites(self):
        self.assertGreater(len(self.schema.composites), 500)

    def test_has_root_type(self):
        self.assertIsNotNone(self.schema.root_type)

    def test_known_type_exists(self):
        names = {c.name for c in self.schema.composites}
        self.assertIn("ArPackage", names)

    def test_known_primitive_exists(self):
        names = {p.name for p in self.schema.primitives}
        self.assertIn("CIdentifierSimple", names)

    def test_known_enum_exists(self):
        names = {e.name for e in self.schema.enums}
        # Regular enum
        self.assertIn("AccessControlEnumSimple", names)

    def test_ar_package_has_identity(self):
        pkg = next(c for c in self.schema.composites if c.name == "ArPackage")
        self.assertGreater(len(pkg.identifiers), 0)

    def test_no_critical_errors(self):
        # Warnings are OK, errors should be few
        self.assertLess(len(self.schema.errors), 50,
                        f"Too many errors: {self.schema.errors[:5]}...")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run integration test**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python3 -m unittest tools/autosar-converter/tests/test_integration -v`
Expected: All tests PASS (may take a few seconds for the 10MB parse)

**Step 3: Fix any issues found by integration test, re-run until passing**

**Step 4: Commit**

```bash
git add tools/autosar-converter/tests/test_integration.py
git commit -m "test(autosar-converter): add integration test against full R23-11 schema"
```

---

## Task 6: Rupa Code Generator

**Files:**
- Create: `tools/autosar-converter/rupa_generator.py`
- Create: `tools/autosar-converter/tests/test_rupa_generator.py`

### Context

**CRITICAL**: Before implementing, read these files to understand the exact Rupa syntax:
- `/Users/ekuhn/CLionProjects/rupa-spec/spec/appendix-a-grammar.md` — The normative PEG grammar
- `/Users/ekuhn/CLionProjects/rupa-spec/spec/04-declarations.md` — Type/role declaration syntax

Key syntax rules from the grammar:

```peg
statement        = annotation* statement_body SEMI?
type_definition  = 'type' identifier '=' type_body
composite_body   = base_list? '{' role_declaration* '}'
primitive_body   = type_ref
enum_body        = '::enum' '(' enum_values ')'
role_declaration = annotation* role_name ':' '&'? type_ref multiplicity? SEMI?
role_name        = '.' identifier / '..'
multiplicity     = '?' / '*' / '+' / '{' integer ',' integer? '}'
annotation       = '#[' annotation_body ']'
```

Key syntax patterns:

```rupa
// Primitive with pattern annotation (annotation ABOVE the type keyword)
#[pattern("[a-zA-Z_][a-zA-Z0-9_]*")]
type CIdentifierSimple = ::string;

// Primitive with range
#[range(>=0)]
type PositiveIntegerSimple = ::integer;

// Enum with bare tokens
type AlignEnumSimple = ::enum(center, justify, left, right);

// Enum with quoted strings (for values containing hyphens)
type SubtypesEnum = ::enum("ABSTRACT-ACCESS-POINT", "SOME-OTHER");

// Abstract composite
#[abstract]
type ArObject = {
    .checksum : StringSimple?;
    .timestamp : DateSimple?;
};

// Composite with identity
type ArPackage = {
    #[id]
    .shortName : IdentifierSimple;
    .element : ArElement*;
};

// Composite with reference member
type SomeType = {
    .target : &OtherType?;
};

// Ordered type with unnamed role
#[ordered]
type MixedContent = {
    .. : StringSimple*;
    .child : ChildType*;
};

// Cardinality: Type? Type* Type+ Type{2,5}

// Domain declaration
domain autosar-r23-11;
```

**Step 1: Write tests for Rupa output formatting**

```python
# tools/autosar-converter/tests/test_rupa_generator.py
import unittest
from schema_model import (
    ExportSchema, ExportPrimitive, ExportEnum, ExportComposite,
    ExportMember, PrimitiveSupertype,
)


class TestPrimitiveGeneration(unittest.TestCase):
    def test_string_with_pattern(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("CIdentifierSimple", PrimitiveSupertype.STRING,
                            pattern="[a-zA-Z_][a-zA-Z0-9_]*")
        lines = generate_primitive(p)
        self.assertIn('#[pattern("[a-zA-Z_][a-zA-Z0-9_]*")]', lines)
        self.assertIn("type CIdentifierSimple = ::string;", lines)

    def test_plain_string(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("StringSimple", PrimitiveSupertype.STRING)
        lines = generate_primitive(p)
        self.assertIn("type StringSimple = ::string;", lines)
        self.assertNotIn("#[pattern", lines)

    def test_float(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("NumericalValueSimple", PrimitiveSupertype.FLOAT)
        lines = generate_primitive(p)
        self.assertIn("type NumericalValueSimple = ::float;", lines)

    def test_integer_with_range(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("PositiveIntegerSimple", PrimitiveSupertype.INTEGER)
        lines = generate_primitive(p)
        self.assertIn("#[range(>=0)]", lines)
        self.assertIn("type PositiveIntegerSimple = ::integer;", lines)


class TestEnumGeneration(unittest.TestCase):
    def test_regular_enum(self):
        from rupa_generator import generate_enum
        e = ExportEnum("AlignEnumSimple", ["center", "justify", "left", "right"])
        lines = generate_enum(e)
        self.assertIn("type AlignEnumSimple = ::enum(center, justify, left, right);", lines)

    def test_subtypes_enum_quoted(self):
        from rupa_generator import generate_enum
        e = ExportEnum("SubtypesEnum",
                       ["ABSTRACT-ACCESS-POINT", "SOME-OTHER"],
                       is_subtypes_enum=True)
        lines = generate_enum(e)
        self.assertIn('"ABSTRACT-ACCESS-POINT"', lines)
        self.assertIn('"SOME-OTHER"', lines)


class TestCompositeGeneration(unittest.TestCase):
    def test_simple_composite(self):
        from rupa_generator import generate_composite
        c = ExportComposite("AbsoluteTolerance", members=[
            ExportMember("checksum", ["StringSimple"], min_occurs=0, max_occurs=1),
            ExportMember("absolute", ["TimeValue"], min_occurs=0, max_occurs=1),
        ])
        lines = generate_composite(c)
        self.assertIn("type AbsoluteTolerance = {", lines)
        self.assertIn("    .checksum : StringSimple?;", lines)
        self.assertIn("    .absolute : TimeValue?;", lines)
        self.assertIn("};", lines)

    def test_reference_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("AccessCount", members=[
            ExportMember("target", ["SomeType"], is_reference=True,
                         min_occurs=0, max_occurs=1),
        ])
        lines = generate_composite(c)
        self.assertIn("    .target : &SomeType?;", lines)

    def test_identity_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("ArPackage",
                            members=[
                                ExportMember("shortName", ["IdentifierSimple"],
                                             min_occurs=1, max_occurs=1,
                                             is_identity=True),
                            ],
                            identifiers=["shortName"])
        lines = generate_composite(c)
        self.assertIn("    #[id]", lines)
        self.assertIn("    .shortName : IdentifierSimple;", lines)

    def test_unbounded_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Package", members=[
            ExportMember("element", ["Element"], min_occurs=0, max_occurs=None),
        ])
        lines = generate_composite(c)
        self.assertIn("    .element : Element*;", lines)

    def test_one_or_more_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Container", members=[
            ExportMember("items", ["Item"], min_occurs=1, max_occurs=None),
        ])
        lines = generate_composite(c)
        self.assertIn("    .items : Item+;", lines)

    def test_ordered_with_unnamed(self):
        from rupa_generator import generate_composite
        c = ExportComposite("MixedContent",
                            members=[
                                ExportMember(None, ["StringSimple"],
                                             min_occurs=0, max_occurs=None,
                                             is_ordered=True),
                                ExportMember("child", ["ChildType"],
                                             min_occurs=0, max_occurs=None,
                                             is_ordered=True),
                            ],
                            is_ordered=True,
                            has_unnamed_string_member=True)
        lines = generate_composite(c)
        self.assertIn("#[ordered]", lines)
        self.assertIn("    .. : StringSimple*;", lines)

    def test_multiplicity_required(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Foo", members=[
            ExportMember("bar", ["BarType"], min_occurs=1, max_occurs=1),
        ])
        lines = generate_composite(c)
        self.assertIn("    .bar : BarType;", lines)
        # No ?, *, + suffix for required single-valued


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python3 -m unittest tools/autosar-converter/tests/test_rupa_generator -v`
Expected: FAIL

**Step 3: Implement generator**

The `rupa_generator.py` module must provide:

- `generate_primitive(p: ExportPrimitive) -> str` — single type definition
- `generate_enum(e: ExportEnum) -> str` — single enum definition
- `generate_composite(c: ExportComposite) -> str` — single composite definition
- `generate_rupa_files(schema: ExportSchema, output_dir: str)` — writes all files

File splitting logic:
- `domain.rupa` — domain declaration + imports
- `primitives.rupa` — all ExportPrimitive types
- `enums.rupa` — all ExportEnum types
- `base-types.rupa` — composites where is_ordered=True or has_unnamed_string_member=True (mixed types are effectively base/abstract patterns)
- Remaining composites split alphabetically into chunks of ~500 types each
- `mapping-report.md` — statistics, warnings, errors

Multiplicity formatting:
- min=1, max=1 -> bare (no suffix)
- min=0, max=1 -> `?`
- min=0, max=None -> `*`
- min=1, max=None -> `+`
- min=N, max=M (other) -> `{N,M}`
- min=N, max=None (other) -> `{N,}`

For variant members (types list has >1 entry): use the first type and add a comment noting the alternatives. Log a warning. If types share a name prefix suggesting a common base, note it.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python3 -m unittest tools/autosar-converter/tests/test_rupa_generator -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tools/autosar-converter/rupa_generator.py tools/autosar-converter/tests/test_rupa_generator.py
git commit -m "feat(autosar-converter): implement Rupa code generator"
```

---

## Task 7: Main Converter Script

**Files:**
- Create: `tools/autosar-converter/converter.py`

### Context

CLI entry point that orchestrates parsing and generation.

**Step 1: Implement converter**

```python
# tools/autosar-converter/converter.py
"""AUTOSAR XSD Schema to Rupa Domain Converter.

Usage:
    python tools/autosar-converter/converter.py <schema.xsd> <output-dir>
"""

import sys
import os

# Add the converter directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schema_parser import parse_schema, export_schema
from rupa_generator import generate_rupa_files


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <schema.xsd> <output-dir>")
        sys.exit(1)

    schema_file = sys.argv[1]
    output_dir = sys.argv[2]

    if not os.path.exists(schema_file):
        print(f"Error: Schema file not found: {schema_file}")
        sys.exit(1)

    print(f"Parsing {schema_file}...")
    internal = parse_schema(schema_file)

    print("Exporting schema model...")
    schema = export_schema(internal)

    print(f"Generating Rupa files in {output_dir}/...")
    os.makedirs(output_dir, exist_ok=True)
    generate_rupa_files(schema, output_dir)

    print(f"Done. {len(schema.primitives)} primitives, "
          f"{len(schema.enums)} enums, "
          f"{len(schema.composites)} composites.")
    if schema.warnings:
        print(f"  {len(schema.warnings)} warnings (see mapping-report.md)")
    if schema.errors:
        print(f"  {len(schema.errors)} ERRORS (see mapping-report.md)")


if __name__ == "__main__":
    main()
```

**Step 2: Run end-to-end test**

```bash
cd /Users/ekuhn/CLionProjects/rupa-spec
python3 tools/autosar-converter/converter.py \
    /Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd \
    output/autosar-r23-11/
```

Expected output: files created in `output/autosar-r23-11/`:
- `domain.rupa`
- `primitives.rupa`
- `enums.rupa`
- `base-types.rupa`
- `composites-*.rupa` (one or more)
- `mapping-report.md`

**Step 3: Verify output**

Manually inspect a few generated types:
```bash
head -30 output/autosar-r23-11/primitives.rupa
head -30 output/autosar-r23-11/enums.rupa
head -50 output/autosar-r23-11/composites-a-e.rupa
cat output/autosar-r23-11/mapping-report.md
```

**Step 4: Add output directory to .gitignore**

```bash
echo "output/" >> .gitignore
```

**Step 5: Commit**

```bash
git add tools/autosar-converter/converter.py .gitignore
git commit -m "feat(autosar-converter): add main converter script"
```

---

## Task 8: End-to-End Validation and Polish

**Files:**
- Modify: `tools/autosar-converter/tests/test_integration.py` (add output validation tests)
- Possibly modify: any files with issues found

**Step 1: Add output validation to integration tests**

Add tests to `test_integration.py` that:
1. Run the full conversion pipeline
2. Verify all expected output files exist
3. Spot-check that specific known types appear correctly in the output
4. Verify the mapping report has expected sections

```python
@unittest.skipUnless(os.path.exists(SCHEMA_PATH), "AUTOSAR schema not available")
class TestFullConversion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        from schema_parser import parse_schema, export_schema
        from rupa_generator import generate_rupa_files
        cls.output_dir = tempfile.mkdtemp()
        internal = parse_schema(SCHEMA_PATH)
        cls.schema = export_schema(internal)
        generate_rupa_files(cls.schema, cls.output_dir)

    def test_domain_file_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "domain.rupa")))

    def test_primitives_file_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "primitives.rupa")))

    def test_enums_file_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "enums.rupa")))

    def test_mapping_report_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "mapping-report.md")))

    def test_primitives_contain_known_type(self):
        with open(os.path.join(self.output_dir, "primitives.rupa")) as f:
            content = f.read()
        self.assertIn("type CIdentifierSimple = ::string;", content)

    def test_domain_declaration(self):
        with open(os.path.join(self.output_dir, "domain.rupa")) as f:
            content = f.read()
        self.assertIn("domain autosar-r23-11;", content)

    def test_report_has_statistics(self):
        with open(os.path.join(self.output_dir, "mapping-report.md")) as f:
            content = f.read()
        self.assertIn("Primitive types:", content)
        self.assertIn("Composite types:", content)
```

**Step 2: Run all tests**

Run: `cd /Users/ekuhn/CLionProjects/rupa-spec && python3 -m unittest discover -s tools/autosar-converter/tests -v`
Expected: All tests PASS

**Step 3: Fix any issues, re-run until clean**

**Step 4: Final commit**

```bash
git add tools/autosar-converter/
git commit -m "feat(autosar-converter): complete end-to-end AUTOSAR XSD to Rupa converter"
```
