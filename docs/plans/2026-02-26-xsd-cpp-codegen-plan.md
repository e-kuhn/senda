# XSD-to-C++ Code Generator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a Python generator that takes an AUTOSAR XSD schema and produces C++ source files for the domain builder (with pre-resolved lookup tables) and a SAX-based ARXML parser.

**Architecture:** Extends the existing `tools/schema-converter/` pipeline. A new `cpp_generator.py` module takes the existing `ExportSchema` model and produces two C++ module files: `senda.domains.cppm` (domain registration + `kore::FrozenMap` lookup tables) and `senda.compiler-arxml.cppm` (expat SAX parser). The domain builder captures TypeHandle/RoleHandle IDs during construction and embeds them directly in the lookup tables — zero runtime string lookups.

**Tech Stack:** Python 3 (generator), C++26 modules (output), expat (SAX XML parser), kore::FrozenMap (lookup tables), existing Rupa Domain/FirBuilder APIs.

---

## Batch 1: Extend Export Model with XML Names

The existing ExportSchema model drops the original XML tag names during conversion. The C++ generator needs them to build tag→TypeHandle lookup tables.

### Task 1.1: Add xml_name fields to export model

**Files:**
- Modify: `tools/schema-converter/schema_model.py:20-71`

**Step 1: Write the failing test**

Create: `tools/schema-converter/tests/test_cpp_generator.py`

```python
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schema_model import ExportComposite, ExportMember, ExportEnum, ExportPrimitive


class TestExportModelXmlNames(unittest.TestCase):
    def test_composite_has_xml_name(self):
        c = ExportComposite("ISignal", xml_name="I-SIGNAL")
        self.assertEqual(c.xml_name, "I-SIGNAL")

    def test_composite_xml_name_default_none(self):
        c = ExportComposite("ISignal")
        self.assertIsNone(c.xml_name)

    def test_member_has_xml_element_name(self):
        m = ExportMember("shortName", ["StringSimple"], xml_element_name="SHORT-NAME")
        self.assertEqual(m.xml_element_name, "SHORT-NAME")

    def test_member_xml_element_name_default_none(self):
        m = ExportMember("shortName", ["StringSimple"])
        self.assertIsNone(m.xml_element_name)

    def test_enum_has_xml_name(self):
        e = ExportEnum("ISignalTypeEnum", ["PRIMITIVE"], xml_name="I-SIGNAL-TYPE-ENUM--SIMPLE")
        self.assertEqual(e.xml_name, "I-SIGNAL-TYPE-ENUM--SIMPLE")

    def test_primitive_has_xml_name(self):
        p = ExportPrimitive("StringSimple", xml_name="STRING--SIMPLE")
        self.assertEqual(p.xml_name, "STRING--SIMPLE")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestExportModelXmlNames -v`
Expected: FAIL — `ExportComposite.__init__() got an unexpected keyword argument 'xml_name'`

**Step 3: Add xml_name fields to export model classes**

In `tools/schema-converter/schema_model.py`, add to `ExportMember`:
```python
xml_element_name: str | None = None
```

Add to `ExportPrimitive`:
```python
xml_name: str | None = None
```

Add to `ExportEnum`:
```python
xml_name: str | None = None
```

Add to `ExportComposite`:
```python
xml_name: str | None = None
```

**Step 4: Run tests to verify they pass**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestExportModelXmlNames -v`
Expected: PASS

Run: `cd tools/schema-converter && python -m pytest tests/ -v`
Expected: ALL PASS (existing tests unaffected — new fields have defaults)

**Step 5: Commit**

```bash
git add tools/schema-converter/schema_model.py tools/schema-converter/tests/test_cpp_generator.py
git commit -m "feat: add xml_name fields to export model for C++ codegen"
```

### Task 1.2: Populate xml_name during export

**Files:**
- Modify: `tools/schema-converter/schema_parser.py:1289-1371` (export functions)

**Step 1: Write the failing test**

Append to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
class TestExportPopulatesXmlNames(unittest.TestCase):
    """Verify that export_schema populates xml_name fields."""

    def test_composite_xml_name_populated(self):
        from schema_parser import parse_schema_from_string, export_schema

        xsd = '''<?xml version="1.0" encoding="UTF-8"?>
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    targetNamespace="http://autosar.org/schema/r4.0"
                    xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:group name="ABSOLUTE-TOLERANCE">
            <xsd:sequence>
              <xsd:element name="ABSOLUTE" type="xsd:string" minOccurs="0"/>
            </xsd:sequence>
          </xsd:group>
          <xsd:complexType name="ABSOLUTE-TOLERANCE">
            <xsd:sequence>
              <xsd:group ref="AR:ABSOLUTE-TOLERANCE"/>
            </xsd:sequence>
          </xsd:complexType>
        </xsd:schema>'''

        internal = parse_schema_from_string(xsd)
        schema = export_schema(internal)

        composites_by_name = {c.name: c for c in schema.composites}
        self.assertIn("AbsoluteTolerance", composites_by_name)
        c = composites_by_name["AbsoluteTolerance"]
        self.assertEqual(c.xml_name, "ABSOLUTE-TOLERANCE")

    def test_member_xml_element_name_populated(self):
        from schema_parser import parse_schema_from_string, export_schema

        xsd = '''<?xml version="1.0" encoding="UTF-8"?>
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    targetNamespace="http://autosar.org/schema/r4.0"
                    xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:group name="ABSOLUTE-TOLERANCE">
            <xsd:sequence>
              <xsd:element name="ABSOLUTE" type="xsd:string" minOccurs="0"/>
            </xsd:sequence>
          </xsd:group>
          <xsd:complexType name="ABSOLUTE-TOLERANCE">
            <xsd:sequence>
              <xsd:group ref="AR:ABSOLUTE-TOLERANCE"/>
            </xsd:sequence>
          </xsd:complexType>
        </xsd:schema>'''

        internal = parse_schema_from_string(xsd)
        schema = export_schema(internal)

        c = next(c for c in schema.composites if c.name == "AbsoluteTolerance")
        absolute_member = next((m for m in c.members if m.name == "absolute"), None)
        self.assertIsNotNone(absolute_member)
        self.assertEqual(absolute_member.xml_element_name, "ABSOLUTE")

    def test_enum_xml_name_populated(self):
        from schema_parser import parse_schema_from_string, export_schema

        xsd = '''<?xml version="1.0" encoding="UTF-8"?>
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    targetNamespace="http://autosar.org/schema/r4.0"
                    xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:simpleType name="ACCESS-CONTROL-ENUM--SIMPLE">
            <xsd:restriction base="xsd:string">
              <xsd:enumeration value="custom"/>
              <xsd:enumeration value="modeled"/>
            </xsd:restriction>
          </xsd:simpleType>
        </xsd:schema>'''

        internal = parse_schema_from_string(xsd)
        schema = export_schema(internal)

        enums_by_name = {e.name: e for e in schema.enums}
        self.assertIn("AccessControlEnumSimple", enums_by_name)
        self.assertEqual(enums_by_name["AccessControlEnumSimple"].xml_name,
                         "ACCESS-CONTROL-ENUM--SIMPLE")
```

**Step 2: Run test to verify it fails**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestExportPopulatesXmlNames -v`
Expected: FAIL — xml_name is None

**Step 3: Populate xml_name in export functions**

In `schema_parser.py`, modify `_export_member()` (~line 1300):
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
    xml_element_name=mem.xml_element_name,
)
```

Modify `_export_composite()` (~line 1361):
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
    is_instance_ref=is_instance_ref,
    xml_name=comp.xml_name,
)
```

Modify `_export_enum()` (~line 1414):
```python
def _export_enum(enum: InternalEnumeration) -> ExportEnum:
    return ExportEnum(
        name=enum.name, values=enum.values, is_subtypes_enum=False,
        doc=enum.doc, value_docs=enum.value_docs,
        xml_name=enum.xml_name,
    )
```

Modify `_export_subtypes_enum()` (~line 1421):
```python
def _export_subtypes_enum(st: InternalSubTypesEnum) -> ExportEnum:
    return ExportEnum(name=st.name, values=st.types, is_subtypes_enum=True,
                      doc=st.doc, xml_name=st.xml_name)
```

Modify `_export_primitive()` (~line 1384):
```python
def _export_primitive(
    prim: InternalPrimitiveType, aliases_by_name: dict[str, InternalAlias],
    xml_to_name: dict[str, str],
) -> ExportPrimitive:
    supertype = _SUPERTYPE_BY_NAME.get(prim.name, PrimitiveSupertype.STRING)
    return ExportPrimitive(name=prim.name, supertype=supertype, doc=prim.doc,
                           xml_name=prim.xml_name)
```

Modify `_export_alias()` (~line 1392) — both return paths:
```python
def _export_alias(
    alias: InternalAlias, aliases_map: dict[str, str],
    aliases_by_name: dict[str, InternalAlias],
    xml_to_name: dict[str, str],
) -> ExportPrimitive:
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
        target_name = xml_to_name.get(alias.target, alias.target)
        aliases_map[alias.name] = target_name
    return ExportPrimitive(name=alias.name, doc=alias.doc, xml_name=alias.xml_name)
```

**Step 4: Run tests**

Run: `cd tools/schema-converter && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tools/schema-converter/schema_parser.py tools/schema-converter/tests/test_cpp_generator.py
git commit -m "feat: populate xml_name fields during schema export"
```

---

## Batch 2: C++ Domain Builder Generator

### Task 2.1: Name conversion utilities for C++ codegen

**Files:**
- Modify: `tools/schema-converter/name_converter.py`

**Step 1: Write failing test**

Add to `tools/schema-converter/tests/test_name_converter.py`:

```python
class TestPascalToSnake(unittest.TestCase):
    def test_simple(self):
        from name_converter import pascal_to_snake
        self.assertEqual(pascal_to_snake("ISignal"), "i_signal")

    def test_all_upper_prefix(self):
        from name_converter import pascal_to_snake
        self.assertEqual(pascal_to_snake("ARObject"), "ar_object")

    def test_single_word(self):
        from name_converter import pascal_to_snake
        self.assertEqual(pascal_to_snake("Identifiable"), "identifiable")

    def test_multiple_words(self):
        from name_converter import pascal_to_snake
        self.assertEqual(pascal_to_snake("EcuInstance"), "ecu_instance")

    def test_consecutive_caps(self):
        from name_converter import pascal_to_snake
        self.assertEqual(pascal_to_snake("ISignalIPdu"), "i_signal_i_pdu")

    def test_enum_suffix(self):
        from name_converter import pascal_to_snake
        self.assertEqual(pascal_to_snake("ISignalTypeEnum"), "i_signal_type_enum")
```

**Step 2: Run test to verify it fails**

Run: `cd tools/schema-converter && python -m pytest tests/test_name_converter.py::TestPascalToSnake -v`
Expected: FAIL — `cannot import name 'pascal_to_snake'`

**Step 3: Implement pascal_to_snake**

Add to `tools/schema-converter/name_converter.py`:

```python
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
```

**Step 4: Run tests**

Run: `cd tools/schema-converter && python -m pytest tests/test_name_converter.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tools/schema-converter/name_converter.py tools/schema-converter/tests/test_name_converter.py
git commit -m "feat: add pascal_to_snake name converter for C++ codegen"
```

### Task 2.2: Domain builder generator — primitives and enums

**Files:**
- Create: `tools/schema-converter/cpp_generator.py`

**Step 1: Write failing test**

Add to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
class TestDomainBuilderPrimitives(unittest.TestCase):
    def test_generates_primitive_types(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema, ExportPrimitive, PrimitiveSupertype

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
                ExportPrimitive("integer", PrimitiveSupertype.INTEGER, xml_name="integer"),
            ],
        )

        code = generate_domain_builder(schema)
        self.assertIn('b.begin_type("string", fir::M3Kind::Primitive)', code)
        self.assertIn('b.begin_type("integer", fir::M3Kind::Primitive)', code)

    def test_generates_enum_types(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema, ExportEnum

        schema = ExportSchema(
            release_version="R23-11",
            enums=[
                ExportEnum("ISignalTypeEnum", ["PRIMITIVE", "STRUCTURE"],
                           xml_name="I-SIGNAL-TYPE-ENUM--SIMPLE"),
            ],
        )

        code = generate_domain_builder(schema)
        self.assertIn('b.begin_type("ISignalTypeEnum", fir::M3Kind::Enum)', code)
        self.assertIn('b.add_enum_value(i_signal_type_enum, "PRIMITIVE")', code)
        self.assertIn('b.add_enum_value(i_signal_type_enum, "STRUCTURE")', code)


class TestDomainBuilderComposites(unittest.TestCase):
    def test_generates_composite_types(self):
        from cpp_generator import generate_domain_builder
        from schema_model import (
            ExportSchema, ExportPrimitive, ExportComposite, ExportMember,
            PrimitiveSupertype,
        )

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
            composites=[
                ExportComposite("Identifiable", is_abstract=True,
                                xml_name="IDENTIFIABLE",
                                members=[
                                    ExportMember("shortName", ["string"],
                                                 min_occurs=1, max_occurs=1,
                                                 xml_element_name="SHORT-NAME"),
                                ]),
                ExportComposite("ISignal", inherits_from=["Identifiable"],
                                xml_name="I-SIGNAL",
                                members=[
                                    ExportMember("shortName", ["string"],
                                                 min_occurs=1, max_occurs=1,
                                                 xml_element_name="SHORT-NAME"),
                                    ExportMember("length", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="LENGTH"),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)

        # Phase 1: Type declarations
        self.assertIn('b.begin_type("Identifiable", fir::M3Kind::Composite)', code)
        self.assertIn('b.begin_type("ISignal", fir::M3Kind::Composite)', code)

        # Phase 2: Supertypes
        self.assertIn('b.set_supertype(i_signal, identifiable)', code)

        # Phase 3: Abstract
        self.assertIn('b.set_abstract(identifiable, true)', code)

        # Phase 4: Roles
        self.assertIn('b.add_role(identifiable, "shortName", string_t', code)
        self.assertIn('b.add_role(i_signal, "shortName", string_t', code)
        self.assertIn('b.add_role(i_signal, "length", string_t', code)

    def test_generates_lookup_tables(self):
        from cpp_generator import generate_domain_builder
        from schema_model import (
            ExportSchema, ExportPrimitive, ExportComposite, ExportMember,
            PrimitiveSupertype,
        )

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
            composites=[
                ExportComposite("ISignal", xml_name="I-SIGNAL",
                                members=[
                                    ExportMember("shortName", ["string"],
                                                 min_occurs=1, max_occurs=1,
                                                 xml_element_name="SHORT-NAME"),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)

        # Tag-to-type lookup
        self.assertIn('tag_to_type.add("I-SIGNAL"', code)
        # Per-type role lookup
        self.assertIn('"SHORT-NAME"', code)
        self.assertIn('tag_to_type.freeze()', code)

    def test_multiplicity_mapping(self):
        from cpp_generator import generate_domain_builder
        from schema_model import (
            ExportSchema, ExportPrimitive, ExportComposite, ExportMember,
            PrimitiveSupertype,
        )

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
            composites=[
                ExportComposite("TestType", xml_name="TEST-TYPE",
                                members=[
                                    ExportMember("required", ["string"],
                                                 min_occurs=1, max_occurs=1,
                                                 xml_element_name="REQUIRED"),
                                    ExportMember("optional", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="OPTIONAL"),
                                    ExportMember("many", ["string"],
                                                 min_occurs=0, max_occurs=None,
                                                 xml_element_name="MANY"),
                                    ExportMember("oneOrMore", ["string"],
                                                 min_occurs=1, max_occurs=None,
                                                 xml_element_name="ONE-OR-MORE"),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        self.assertIn("fir::Multiplicity::One", code)
        self.assertIn("fir::Multiplicity::Optional", code)
        self.assertIn("fir::Multiplicity::Many", code)
        self.assertIn("fir::Multiplicity::OneOrMore", code)
```

**Step 2: Run test to verify it fails**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestDomainBuilderPrimitives -v`
Expected: FAIL — `cannot import name 'generate_domain_builder'`

**Step 3: Implement generate_domain_builder**

Create `tools/schema-converter/cpp_generator.py`:

```python
"""Generate C++ source files from the AUTOSAR export model.

Produces:
  - senda.domains.cppm: Domain builder with FirBuilder API calls + FrozenMap lookup tables
  - senda.compiler-arxml.cppm: SAX-based ARXML parser using expat
"""

from __future__ import annotations

import os
from schema_model import (
    ExportSchema, ExportPrimitive, ExportEnum, ExportComposite,
    ExportMember, PrimitiveSupertype,
)
from name_converter import pascal_to_snake


def _multiplicity(min_occurs: int | None, max_occurs: int | None) -> str:
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
    # For explicit ranges, use Many (closest approximation)
    if mn == 0:
        return "fir::Multiplicity::Many"
    return "fir::Multiplicity::OneOrMore"


def _type_var(name: str) -> str:
    """Generate a C++ variable name for a type.

    Primitives get a _t suffix, everything else uses snake_case.
    """
    return pascal_to_snake(name)


def _prim_var(name: str) -> str:
    """Variable name for a primitive type."""
    return pascal_to_snake(name) + "_t"


def _role_var(type_var: str, index: int) -> str:
    """Variable name for a role handle."""
    return f"{type_var}_r{index}"


def _domain_name(release_version: str) -> str:
    """Convert release version to domain name: R23-11 -> autosar-r23-11."""
    return "autosar-" + release_version.lower()


def generate_domain_builder(schema: ExportSchema) -> str:
    """Generate the C++ domain builder function body."""
    lines: list[str] = []
    w = lines.append

    release = schema.release_version
    domain = _domain_name(release)

    # --- Build name→variable mappings ---
    # We need to map type names to C++ variable names for cross-references
    type_vars: dict[str, str] = {}  # PascalCase name → C++ variable name

    for p in schema.primitives:
        var = _prim_var(p.name)
        type_vars[p.name] = var

    for e in schema.enums:
        var = _type_var(e.name)
        type_vars[e.name] = var

    for c in schema.composites:
        var = _type_var(c.name)
        type_vars[c.name] = var

    # --- Emit function ---
    w("AutosarSchema build_%s() {" % pascal_to_snake(_domain_name(release).replace("-", "_")))
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
    if schema.composites:
        w("    // ── Composites Phase 1: Declare types (%d) ──" % len(schema.composites))
        for c in schema.composites:
            var = type_vars[c.name]
            w('    auto %s = b.begin_type("%s", fir::M3Kind::Composite);' % (var, c.name))
        w("")

        # --- Phase 2: Set supertypes ---
        supertypes = [(c, parent) for c in schema.composites
                      for parent in c.inherits_from if parent in type_vars]
        if supertypes:
            w("    // ── Composites Phase 2: Supertypes ──")
            for c, parent in supertypes:
                w("    b.set_supertype(%s, %s);" % (type_vars[c.name], type_vars[parent]))
            w("")

        # --- Phase 3: Abstract flags ---
        abstracts = [c for c in schema.composites if c.is_abstract]
        if abstracts:
            w("    // ── Composites Phase 3: Abstract flags ──")
            for c in abstracts:
                w("    b.set_abstract(%s, true);" % type_vars[c.name])
            w("")

        # --- Phase 4: Roles ---
        w("    // ── Composites Phase 4: Roles ──")

        # Track role handles per type for lookup table generation
        role_handles: dict[str, list[tuple[str, str, str]]] = {}
        # type_name -> [(role_var, member_xml_element_name, role_name)]

        for c in schema.composites:
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

                w("    auto %s = b.add_role(%s, \"%s\", %s, %s);"
                  % (rvar, cvar, role_name, target_type, mult))

                xml_elem = m.xml_element_name
                if xml_elem:
                    role_handles[c.name].append((rvar, xml_elem, role_name))
            if c.members:
                w("")

    # --- Lookup tables ---
    w("    // ── Lookup Tables ──")
    w("    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type(%d);"
      % len(schema.composites))
    w("")

    for c in schema.composites:
        if not c.xml_name:
            continue
        cvar = type_vars[c.name]
        roles = role_handles.get(c.name, [])

        w("    {")
        w("        TypeInfo info{%s, kore::FrozenMap<std::string_view, rupa::domain::RoleHandle>(%d)};"
          % (cvar, len(roles)))
        for rvar, xml_elem, _role_name in roles:
            w('        info.roles.add("%s", %s);' % (xml_elem, rvar))
        w("        info.roles.freeze();")
        w('        tag_to_type.add("%s", std::move(info));' % c.xml_name)
        w("    }")

    w("    tag_to_type.freeze();")
    w("")
    w('    return AutosarSchema{rupa::domain::Domain("%s", std::move(type_fir)), std::move(tag_to_type)};'
      % domain)
    w("}")

    return "\n".join(lines)


def generate_domain_module(schema: ExportSchema, output_dir: str) -> None:
    """Generate the complete senda.domains.cppm module file."""
    release = schema.release_version
    domain = _domain_name(release)

    header = '''module;

#include <string_view>
#include <utility>

export module senda.domains;

import kore.containers.frozen_map;
import rupa.fir;
import rupa.fir.builder;
import rupa.domain;

export namespace senda::domains
{

struct TypeInfo {
    rupa::domain::TypeHandle handle;
    kore::FrozenMap<std::string_view, rupa::domain::RoleHandle> roles;
};

struct AutosarSchema {
    rupa::domain::Domain domain;
    kore::FrozenMap<std::string_view, TypeInfo> tag_to_type;
};

'''

    body = generate_domain_builder(schema)

    footer = '''
}  // namespace senda::domains
'''

    path = os.path.join(output_dir, "domains", "senda.domains.cppm")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(body)
        f.write(footer)
```

**Step 4: Run tests**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tools/schema-converter/cpp_generator.py tools/schema-converter/tests/test_cpp_generator.py
git commit -m "feat: implement C++ domain builder generator"
```

### Task 2.3: Domain builder — unnamed roles and containment

**Files:**
- Modify: `tools/schema-converter/cpp_generator.py`

**Step 1: Write failing test**

Add to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
class TestDomainBuilderUnnamedRoles(unittest.TestCase):
    def test_unnamed_role_uses_dotdot(self):
        from cpp_generator import generate_domain_builder
        from schema_model import (
            ExportSchema, ExportPrimitive, ExportComposite, ExportMember,
            PrimitiveSupertype,
        )

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
            composites=[
                ExportComposite("MixedContent", xml_name="MIXED-CONTENT",
                                is_ordered=True,
                                has_unnamed_string_member=True,
                                members=[
                                    ExportMember(None, ["string"],
                                                 min_occurs=0, max_occurs=None),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        self.assertIn('".."', code)
```

**Step 2: Run test to verify it passes (already handled by `".." if m.name is None`)**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestDomainBuilderUnnamedRoles -v`
Expected: PASS (already implemented in Task 2.2)

If it fails, fix the `generate_domain_builder` function accordingly.

**Step 3: Commit if any changes were needed**

---

## Batch 3: SAX ARXML Parser Generator

### Task 3.1: Generate the ARXML parser module

**Files:**
- Modify: `tools/schema-converter/cpp_generator.py`

**Step 1: Write failing test**

Add to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
class TestArxmlParserGeneration(unittest.TestCase):
    def test_generates_parser_module(self):
        from cpp_generator import generate_arxml_module
        from schema_model import ExportSchema

        schema = ExportSchema(release_version="R23-11")
        code = generate_arxml_module(schema)

        # Module declaration
        self.assertIn("export module senda.compiler.arxml", code)
        # Expat include
        self.assertIn("expat.h", code)
        # Compiler interface
        self.assertIn("class ArxmlCompiler", code)
        self.assertIn("rupa::compiler::Compiler", code)
        # SAX callbacks
        self.assertIn("XML_SetElementHandler", code)
        self.assertIn("XML_SetCharacterDataHandler", code)
        # Extensions
        self.assertIn(".arxml", code)
        # Domain name
        self.assertIn("autosar-r23-11", code)

    def test_parser_uses_autosar_schema(self):
        from cpp_generator import generate_arxml_module
        from schema_model import ExportSchema

        schema = ExportSchema(release_version="R23-11")
        code = generate_arxml_module(schema)

        self.assertIn("AutosarSchema", code)
        self.assertIn("tag_to_type", code)
```

**Step 2: Run test to verify it fails**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestArxmlParserGeneration -v`
Expected: FAIL — `cannot import name 'generate_arxml_module'`

**Step 3: Implement generate_arxml_module**

Add to `tools/schema-converter/cpp_generator.py`:

```python
def generate_arxml_module(schema: ExportSchema) -> str:
    """Generate the complete senda.compiler-arxml.cppm SAX parser module."""
    release = schema.release_version
    domain = _domain_name(release)

    return '''module;

#include <cstring>
#include <filesystem>
#include <fstream>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
#include <expat.h>

export module senda.compiler.arxml;

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;
import senda.domains;

export namespace senda
{{

class ArxmlCompiler : public rupa::compiler::Compiler {{
public:
    explicit ArxmlCompiler(const senda::domains::AutosarSchema& schema)
        : schema_(schema) {{}}

    std::span<const std::string_view> extensions() const override {{
        return exts_;
    }}

    rupa::compiler::CompileResult compile(
        const std::filesystem::path& path,
        rupa::compiler::CompileContext& context) override
    {{
        rupa::compiler::Diagnostics diags;

        // Read file content
        std::ifstream file(path, std::ios::binary | std::ios::ate);
        if (!file) {{
            diags.add({{rupa::compiler::Severity::Error,
                       "cannot open file: " + path.string(),
                       {{path.string(), 0, 0}}}});
            return rupa::compiler::CompileResult(
                fir::Fir{{}}, rupa::compiler::DomainExtensions{{}}, std::move(diags));
        }}
        auto size = file.tellg();
        file.seekg(0);
        std::string content(static_cast<size_t>(size), '\\0');
        file.read(content.data(), size);

        // Create expat parser
        XML_Parser parser = XML_ParserCreate(nullptr);
        if (!parser) {{
            diags.add({{rupa::compiler::Severity::Error,
                       "failed to create XML parser",
                       {{path.string(), 0, 0}}}});
            return rupa::compiler::CompileResult(
                fir::Fir{{}}, rupa::compiler::DomainExtensions{{}}, std::move(diags));
        }}

        // Set up parse state
        fir::Fir fir;
        rupa::fir_builder::FirBuilder builder(fir);

        ParseState state{{
            .schema = schema_,
            .builder = builder,
            .diags = diags,
            .file_path = path.string(),
        }};

        XML_SetUserData(parser, &state);
        XML_SetElementHandler(parser, on_start_element, on_end_element);
        XML_SetCharacterDataHandler(parser, on_characters);

        // Parse
        if (XML_Parse(parser, content.data(), static_cast<int>(content.size()), XML_TRUE)
            == XML_STATUS_ERROR) {{
            diags.add({{rupa::compiler::Severity::Error,
                       std::string("XML parse error: ")
                           + XML_ErrorString(XML_GetErrorCode(parser))
                           + " at line "
                           + std::to_string(XML_GetCurrentLineNumber(parser)),
                       {{path.string(),
                         static_cast<uint32_t>(XML_GetCurrentLineNumber(parser)), 0}}}});
        }}

        XML_ParserFree(parser);

        return rupa::compiler::CompileResult(
            std::move(fir), rupa::compiler::DomainExtensions{{}}, std::move(diags));
    }}

private:
    static constexpr std::string_view exts_arr_[] = {{".arxml"}};
    std::span<const std::string_view> exts_{{exts_arr_}};
    const senda::domains::AutosarSchema& schema_;

    // --- SAX state machine ---

    enum class FrameKind {{ Object, Property, Skip }};

    struct Frame {{
        FrameKind kind;
        // Object frame
        rupa::fir_builder::ObjectHandle obj{{}};
        const senda::domains::TypeInfo* type_info = nullptr;
        // Property frame
        rupa::domain::RoleHandle role{{}};
        rupa::fir_builder::ObjectHandle parent_obj{{}};
        std::string text;
        // Skip frame
        int skip_depth = 0;
    }};

    struct ParseState {{
        const senda::domains::AutosarSchema& schema;
        rupa::fir_builder::FirBuilder& builder;
        rupa::compiler::Diagnostics& diags;
        std::string file_path;
        std::vector<Frame> stack;
    }};

    static void XMLCALL on_start_element(void* user_data, const XML_Char* name,
                                          const XML_Char** /*attrs*/) {{
        auto& state = *static_cast<ParseState*>(user_data);
        std::string_view tag(name);

        // Strip namespace prefix if present (e.g., "AR:AUTOSAR" -> "AUTOSAR")
        if (auto pos = tag.find(':'); pos != std::string_view::npos) {{
            tag = tag.substr(pos + 1);
        }}

        // If top of stack is Skip, increment depth
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Skip) {{
            state.stack.back().skip_depth++;
            return;
        }}

        // Try type lookup
        auto* type_info = state.schema.tag_to_type.find(tag);
        if (type_info) {{
            // Known type element — create object
            Frame frame{{}};
            frame.kind = FrameKind::Object;
            frame.type_info = type_info;
            // Identity will be set when we see SHORT-NAME
            frame.obj = {{}};  // deferred
            state.stack.push_back(std::move(frame));
            return;
        }}

        // If we're inside an Object frame, try role lookup
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Object) {{
            auto& parent = state.stack.back();
            if (parent.type_info) {{
                auto* role = parent.type_info->roles.find(tag);
                if (role) {{
                    Frame frame{{}};
                    frame.kind = FrameKind::Property;
                    frame.role = *role;
                    frame.parent_obj = parent.obj;
                    state.stack.push_back(std::move(frame));
                    return;
                }}
            }}
        }}

        // If we're inside a Property frame, try type lookup (contained object)
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Property) {{
            auto* nested_type_info = state.schema.tag_to_type.find(tag);
            if (nested_type_info) {{
                Frame frame{{}};
                frame.kind = FrameKind::Object;
                frame.type_info = nested_type_info;
                frame.obj = {{}};
                state.stack.push_back(std::move(frame));
                return;
            }}
        }}

        // Unknown element — skip
        Frame frame{{}};
        frame.kind = FrameKind::Skip;
        frame.skip_depth = 1;
        state.stack.push_back(std::move(frame));
    }}

    static void XMLCALL on_end_element(void* user_data, const XML_Char* /*name*/) {{
        auto& state = *static_cast<ParseState*>(user_data);

        if (state.stack.empty()) return;

        auto& frame = state.stack.back();

        switch (frame.kind) {{
        case FrameKind::Skip:
            if (--frame.skip_depth > 0) return;
            break;

        case FrameKind::Property:
            // If we captured text and have a valid parent object, add the property
            if (!frame.text.empty() && frame.parent_obj.valid()) {{
                state.builder.add_property(
                    frame.parent_obj, rupa::fir_builder::RoleHandle{{frame.role.id}},
                    std::string_view(frame.text));
            }}
            break;

        case FrameKind::Object:
            // Object finalization is implicit (FirBuilder tracks current object)
            break;
        }}

        state.stack.pop_back();
    }}

    static void XMLCALL on_characters(void* user_data, const XML_Char* s, int len) {{
        auto& state = *static_cast<ParseState*>(user_data);

        if (state.stack.empty()) return;

        auto& frame = state.stack.back();
        if (frame.kind == FrameKind::Property) {{
            frame.text.append(s, static_cast<size_t>(len));
        }}
    }}
}};

}}  // namespace senda
'''.format(domain=domain)
```

Note: The `generate_arxml_module` function returns a complete C++ module file as a string. The actual file writing is handled by a separate function.

**Step 4: Run tests**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tools/schema-converter/cpp_generator.py tools/schema-converter/tests/test_cpp_generator.py
git commit -m "feat: implement C++ SAX ARXML parser generator"
```

### Task 3.2: File-writing functions

**Files:**
- Modify: `tools/schema-converter/cpp_generator.py`

**Step 1: Write failing test**

Add to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
import tempfile

class TestFileGeneration(unittest.TestCase):
    def test_generate_cpp_files_creates_domain_module(self):
        from cpp_generator import generate_cpp_files
        from schema_model import ExportSchema, ExportPrimitive, PrimitiveSupertype

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generate_cpp_files(schema, tmpdir)

            domain_path = os.path.join(tmpdir, "domains", "senda.domains.cppm")
            self.assertTrue(os.path.exists(domain_path))

            with open(domain_path) as f:
                content = f.read()
            self.assertIn("export module senda.domains", content)
            self.assertIn("AutosarSchema", content)

    def test_generate_cpp_files_creates_parser_module(self):
        from cpp_generator import generate_cpp_files
        from schema_model import ExportSchema, ExportPrimitive, PrimitiveSupertype

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generate_cpp_files(schema, tmpdir)

            parser_path = os.path.join(tmpdir, "compiler-arxml", "senda.compiler-arxml.cppm")
            self.assertTrue(os.path.exists(parser_path))

            with open(parser_path) as f:
                content = f.read()
            self.assertIn("export module senda.compiler.arxml", content)
```

**Step 2: Run test to verify it fails**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestFileGeneration -v`
Expected: FAIL — `cannot import name 'generate_cpp_files'`

**Step 3: Implement generate_cpp_files**

Add to `tools/schema-converter/cpp_generator.py`:

```python
def generate_cpp_files(schema: ExportSchema, output_dir: str) -> None:
    """Generate all C++ files from the schema.

    Args:
        schema: The exported schema model.
        output_dir: Base output directory (e.g., 'src/'). Files are written to:
            - <output_dir>/domains/senda.domains.cppm
            - <output_dir>/compiler-arxml/senda.compiler-arxml.cppm
    """
    generate_domain_module(schema, output_dir)

    # Write parser module
    parser_code = generate_arxml_module(schema)
    parser_dir = os.path.join(output_dir, "compiler-arxml")
    os.makedirs(parser_dir, exist_ok=True)
    parser_path = os.path.join(parser_dir, "senda.compiler-arxml.cppm")
    with open(parser_path, "w", encoding="utf-8") as f:
        f.write(parser_code)
```

**Step 4: Run tests**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tools/schema-converter/cpp_generator.py tools/schema-converter/tests/test_cpp_generator.py
git commit -m "feat: add file-writing functions for C++ codegen"
```

---

## Batch 4: CLI Integration

### Task 4.1: Add --cpp flag to converter.py

**Files:**
- Modify: `tools/schema-converter/converter.py`

**Step 1: Write the failing test**

Add to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
import subprocess

class TestCLIIntegration(unittest.TestCase):
    def test_cpp_flag_recognized(self):
        result = subprocess.run(
            ["python", "converter.py", "--help"],
            capture_output=True, text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertIn("--cpp", result.stdout)
```

**Step 2: Run test to verify it fails**

Run: `cd tools/schema-converter && python -m pytest tests/test_cpp_generator.py::TestCLIIntegration -v`
Expected: FAIL — `--cpp` not in help output

**Step 3: Add --cpp flag**

Modify `tools/schema-converter/converter.py`:

```python
"""AUTOSAR XSD Schema to Rupa Domain Converter.

Usage:
    python tools/autosar-converter/converter.py <schema.xsd> <output-dir>
    python tools/autosar-converter/converter.py <schema.xsd> <output-dir> --cpp
"""

import argparse
import sys
import os

# Add the converter directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schema_parser import parse_schema, export_schema
from rupa_generator import generate_rupa_files


def main():
    parser = argparse.ArgumentParser(
        description="Convert AUTOSAR XSD schema to Rupa domain files."
    )
    parser.add_argument("schema", help="Path to AUTOSAR XSD schema file")
    parser.add_argument("output_dir", help="Output directory for generated files")
    parser.add_argument(
        "--alternatives", action="store_true", default=False,
        help="Generate variant alternative comments (// also:) on members",
    )
    parser.add_argument(
        "--cpp", action="store_true", default=False,
        help="Generate C++ domain builder and ARXML parser instead of Rupa files",
    )
    args = parser.parse_args()

    if not os.path.exists(args.schema):
        print(f"Error: Schema file not found: {args.schema}")
        sys.exit(1)

    print(f"Parsing {args.schema}...")
    internal = parse_schema(args.schema)

    print("Exporting schema model...")
    schema = export_schema(internal)

    if args.cpp:
        from cpp_generator import generate_cpp_files

        print(f"Generating C++ files in {args.output_dir}/...")
        generate_cpp_files(schema, args.output_dir)
    else:
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


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

Run: `cd tools/schema-converter && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tools/schema-converter/converter.py
git commit -m "feat: add --cpp flag to converter CLI"
```

---

## Batch 5: CMake and C++ Build Integration

### Task 5.1: Add expat dependency to CMakeLists.txt

**Files:**
- Modify: `CMakeLists.txt` (root)

**Step 1: Add expat FetchContent declaration**

Replace the pugixml dependency with expat in the root `CMakeLists.txt`:

```cmake
# expat (SAX XML parser for ARXML compiler — replaces pugixml)
FetchContent_Declare(
    expat
    SYSTEM
    GIT_REPOSITORY https://github.com/libexpat/libexpat.git
    GIT_TAG R_2_6_4
    SOURCE_SUBDIR expat
    EXCLUDE_FROM_ALL
)
set(EXPAT_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(EXPAT_SHARED_LIBS OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(expat)
```

Remove the pugixml FetchContent block.

**Step 2: Update compiler-arxml CMakeLists.txt**

Modify `src/compiler-arxml/CMakeLists.txt`:

```cmake
add_library(senda.compiler.arxml)
target_sources(senda.compiler.arxml
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.compiler-arxml.cppm
)
target_link_libraries(senda.compiler.arxml
    PUBLIC rupa.compiler rupa.fir.builder rupa.domain rupa.fir kore senda.domains
    PRIVATE expat
)
target_compile_features(senda.compiler.arxml PUBLIC cxx_std_26)
senda_target_settings(senda.compiler.arxml)
```

Note: `senda.domains` is now a PUBLIC dependency (for the `AutosarSchema` struct), and `expat` replaces `pugixml::pugixml`.

**Step 3: Update domains CMakeLists.txt**

Modify `src/domains/CMakeLists.txt` to add kore.containers.frozen_map:

```cmake
add_library(senda.domains)
target_sources(senda.domains
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.domains.cppm
)
target_link_libraries(senda.domains
    PUBLIC rupa.domain rupa.fir rupa.fir.builder kore
)
target_compile_features(senda.domains PUBLIC cxx_std_26)
senda_target_settings(senda.domains)
```

**Step 4: Commit**

```bash
git add CMakeLists.txt src/compiler-arxml/CMakeLists.txt src/domains/CMakeLists.txt
git commit -m "build: replace pugixml with expat, add kore frozen_map deps"
```

### Task 5.2: Update main.cpp for AutosarSchema

**Files:**
- Modify: `src/main.cpp`

**Step 1: Update main.cpp to use AutosarSchema**

```cpp
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>

import rupa.compiler;
import rupa.driver;
import rupa.fir;
import rupa.sema;
import senda.compiler.arxml;
import senda.domains;

namespace fs = std::filesystem;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::puts("senda 0.1.0 — Automotive DSL built on Rupa");
        std::puts("Usage: senda <file.rupa|file.arxml>");
        return 0;
    }

    fs::path input_path(argv[1]);

    // Build AUTOSAR schema (domain + lookup tables)
    auto schema = senda::domains::build_autosar_r23_11();

    // Create compilers
    rupa::sema::RupaCompiler rupa_compiler;
    senda::ArxmlCompiler arxml_compiler(schema);

    // Register compilers
    rupa::compiler::CompilerRegistry registry;
    registry.register_compiler(rupa_compiler);
    registry.register_compiler(arxml_compiler);

    // Create driver
    rupa::driver::CompilationDriver driver(registry);

    // Load domain from schema
    // Note: We need to extract the domain from AutosarSchema
    // The driver needs a Domain, not an AutosarSchema
    driver.add_domain(std::move(schema.domain));

    // Compile
    auto result = driver.compile(input_path);

    // Report diagnostics
    for (const auto& diag : result.diagnostics()) {
        const char* severity = "note";
        if (diag.severity == rupa::compiler::Severity::Error) severity = "error";
        else if (diag.severity == rupa::compiler::Severity::Warning) severity = "warning";

        std::fprintf(stderr, "%s:%u:%u: %s: %s\n",
            diag.location.file.c_str(),
            diag.location.line,
            diag.location.column,
            severity,
            diag.message.c_str());
    }

    if (result.has_errors()) {
        return 1;
    }

    // Report success
    size_t obj_count = 0;
    result.fir().forEachNode([&](fir::Id, const fir::Node& node) {
        if (node.kind == fir::NodeKind::ObjectDef) ++obj_count;
    });
    std::printf("Compiled %s: %zu objects\n", input_path.c_str(), obj_count);

    return 0;
}
```

**Step 2: Commit**

```bash
git add src/main.cpp
git commit -m "refactor: update main.cpp to use AutosarSchema"
```

### Task 5.3: Update C++ tests for new API

**Files:**
- Modify: `test/compiler-arxml/arxml-compiler-test.cpp`
- Modify: `test/integration/e2e-arxml-import-test.cpp`

**Step 1: Update unit tests**

The tests need to adapt to ArxmlCompiler now taking an `AutosarSchema&` instead of looking up the domain via context. Update `MockArxmlContext` and test code to use the new API.

Key changes:
- `ArxmlCompiler` now takes `AutosarSchema&` in constructor
- `build_autosar_r23_11()` returns `AutosarSchema` instead of `Domain`
- Extract domain from schema for `MockArxmlContext`

**Step 2: Update integration tests**

Same API changes. `driver.add_domain(std::move(schema.domain))` instead of `driver.add_domain(build_autosar_r23_11())`.

**Step 3: Build and run tests**

Run:
```bash
cmake --preset debug
cmake --build --preset debug
ctest --preset debug
```
Expected: ALL PASS

**Step 4: Commit**

```bash
git add test/compiler-arxml/arxml-compiler-test.cpp test/integration/e2e-arxml-import-test.cpp
git commit -m "test: update C++ tests for AutosarSchema API"
```

---

## Batch 6: Full Generation and Verification

### Task 6.1: Generate C++ files from AUTOSAR_00052.xsd

**Step 1: Run the generator**

```bash
cd tools/schema-converter
python converter.py ../../schema/AUTOSAR_00052.xsd ../../src --cpp
```

**Step 2: Verify generated files exist**

```bash
ls -la ../../src/domains/senda.domains.cppm
ls -la ../../src/compiler-arxml/senda.compiler-arxml.cppm
```

**Step 3: Inspect generated output**

Check that generated files contain expected content (primitives, enums, ~2700 composites, lookup tables).

**Step 4: Build**

```bash
cd ../..
cmake --build --preset debug
```

Expected: BUILD SUCCESS

**Step 5: Run tests**

```bash
ctest --preset debug
```

Expected: ALL PASS

**Step 6: Commit generated files**

```bash
git add src/domains/senda.domains.cppm src/compiler-arxml/senda.compiler-arxml.cppm
git commit -m "feat: generate full AUTOSAR R23-11 domain and SAX parser from XSD"
```

### Task 6.2: Test with real ARXML file

**Step 1: Create a comprehensive test ARXML fixture**

Create a fixture that exercises multiple type categories from the full schema (not just the 6 hand-coded types).

**Step 2: Run senda on it**

```bash
./build-debug/senda test/compiler-arxml/fixtures/simple-signal.arxml
```

Expected: Objects compiled successfully.

**Step 3: Final commit and cleanup**

```bash
git add -A
git commit -m "chore: final verification of XSD-to-C++ codegen pipeline"
```
