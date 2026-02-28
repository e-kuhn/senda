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


class TestExportPopulatesXmlNames(unittest.TestCase):
    """Verify that export_schema populates xml_name fields."""

    def test_composite_xml_name_populated(self):
        from schema_parser import parse_schema_from_string, export_schema

        xsd = '''\
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    targetNamespace="http://autosar.org/schema/r4.0"
                    xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:group name="ABSOLUTE-TOLERANCE">
            <xsd:annotation>
              <xsd:appinfo source="tags">mmt.qualifiedName="AbsoluteTolerance"</xsd:appinfo>
            </xsd:annotation>
            <xsd:sequence>
              <xsd:element maxOccurs="1" minOccurs="0" name="ABSOLUTE" type="AR:TIME-VALUE">
                <xsd:annotation>
                  <xsd:appinfo source="tags">mmt.qualifiedName="AbsoluteTolerance.absolute";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
                </xsd:annotation>
              </xsd:element>
            </xsd:sequence>
          </xsd:group>
        </xsd:schema>'''

        internal = parse_schema_from_string(xsd)
        schema = export_schema(internal)

        composites_by_name = {c.name: c for c in schema.composites}
        self.assertIn("AbsoluteTolerance", composites_by_name)
        c = composites_by_name["AbsoluteTolerance"]
        self.assertEqual(c.xml_name, "ABSOLUTE-TOLERANCE")

    def test_member_xml_element_name_populated(self):
        from schema_parser import parse_schema_from_string, export_schema

        xsd = '''\
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    targetNamespace="http://autosar.org/schema/r4.0"
                    xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:group name="ABSOLUTE-TOLERANCE">
            <xsd:annotation>
              <xsd:appinfo source="tags">mmt.qualifiedName="AbsoluteTolerance"</xsd:appinfo>
            </xsd:annotation>
            <xsd:sequence>
              <xsd:element maxOccurs="1" minOccurs="0" name="ABSOLUTE" type="AR:TIME-VALUE">
                <xsd:annotation>
                  <xsd:appinfo source="tags">mmt.qualifiedName="AbsoluteTolerance.absolute";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
                </xsd:annotation>
              </xsd:element>
            </xsd:sequence>
          </xsd:group>
        </xsd:schema>'''

        internal = parse_schema_from_string(xsd)
        schema = export_schema(internal)

        c = next(c for c in schema.composites if c.name == "AbsoluteTolerance")
        absolute_member = next((m for m in c.members if m.name == "absolute"), None)
        self.assertIsNotNone(absolute_member)
        self.assertEqual(absolute_member.xml_element_name, "ABSOLUTE")

    def test_enum_xml_name_populated(self):
        from schema_parser import parse_schema_from_string, export_schema

        # Enum must be referenced by a composite to survive truncation
        xsd = '''\
        <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    targetNamespace="http://autosar.org/schema/r4.0"
                    xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:simpleType name="ACCESS-CONTROL-ENUM--SIMPLE">
            <xsd:restriction base="xsd:string">
              <xsd:enumeration value="CUSTOM">
                <xsd:annotation>
                  <xsd:appinfo source="tags">mmt.qualifiedName="AccessControlEnum.custom"</xsd:appinfo>
                </xsd:annotation>
              </xsd:enumeration>
              <xsd:enumeration value="MODELED">
                <xsd:annotation>
                  <xsd:appinfo source="tags">mmt.qualifiedName="AccessControlEnum.modeled"</xsd:appinfo>
                </xsd:annotation>
              </xsd:enumeration>
            </xsd:restriction>
          </xsd:simpleType>
          <xsd:group name="HOLDER">
            <xsd:annotation>
              <xsd:appinfo source="tags">mmt.qualifiedName="Holder"</xsd:appinfo>
            </xsd:annotation>
            <xsd:sequence>
              <xsd:element name="MODE" type="AR:ACCESS-CONTROL-ENUM--SIMPLE" minOccurs="0">
                <xsd:annotation>
                  <xsd:appinfo source="tags">mmt.qualifiedName="Holder.mode"</xsd:appinfo>
                </xsd:annotation>
              </xsd:element>
            </xsd:sequence>
          </xsd:group>
        </xsd:schema>'''

        internal = parse_schema_from_string(xsd)
        schema = export_schema(internal)

        enums_by_name = {e.name: e for e in schema.enums}
        self.assertIn("AccessControlEnumSimple", enums_by_name)
        self.assertEqual(enums_by_name["AccessControlEnumSimple"].xml_name,
                         "ACCESS-CONTROL-ENUM--SIMPLE")


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


class TestLookupTableInheritedRoles(unittest.TestCase):
    @staticmethod
    def _extract_lookup_block(code, xml_tag):
        """Extract the lookup table block for a given XML tag name."""
        lines = code.split("\n")
        block_lines = []
        capturing = False
        brace_depth = 0
        for line in lines:
            if not capturing and line.strip() == "{":
                capturing = True
                brace_depth = 1
                block_lines = [line]
                continue
            if capturing:
                block_lines.append(line)
                brace_depth += line.count("{") - line.count("}")
                if brace_depth == 0:
                    block = "\n".join(block_lines)
                    if ('tag_to_type.add("%s"' % xml_tag) in block:
                        return block
                    capturing = False
                    block_lines = []
        return ""

    def test_child_lookup_includes_parent_roles(self):
        """Roles from parent groups must appear in child lookup tables."""
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
                ExportComposite("MultilanguageReferrable", is_abstract=True,
                                xml_name=None,
                                members=[
                                    ExportMember("longName", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="LONG-NAME"),
                                ]),
                ExportComposite("ISignal",
                                inherits_from=["MultilanguageReferrable"],
                                xml_name="I-SIGNAL",
                                members=[
                                    ExportMember("length", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="LENGTH"),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        block = self._extract_lookup_block(code, "I-SIGNAL")

        self.assertIn('"LONG-NAME"', block,
                      "I-SIGNAL lookup must include inherited LONG-NAME role")
        self.assertIn('"LENGTH"', block,
                      "I-SIGNAL lookup must include own LENGTH role")

    def test_child_role_overrides_parent_role(self):
        """When child defines same xml_element_name as parent, child wins."""
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
                ExportComposite("BaseGroup", is_abstract=True, xml_name=None,
                                members=[
                                    ExportMember("name", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="NAME"),
                                ]),
                ExportComposite("Child",
                                inherits_from=["BaseGroup"],
                                xml_name="CHILD",
                                members=[
                                    ExportMember("name", ["string"],
                                                 min_occurs=1, max_occurs=1,
                                                 xml_element_name="NAME"),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        block = self._extract_lookup_block(code, "CHILD")

        name_count = block.count('"NAME"')
        self.assertEqual(name_count, 1,
                         "Child should have exactly one NAME role (child overrides parent)")
        # Verify it uses the child's role handle, not the parent's
        self.assertIn("child_r0", block)
        self.assertNotIn("base_group_r0", block)

    def test_deep_inheritance_chain(self):
        """Roles propagate through multi-level inheritance."""
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
                ExportComposite("GrandParent", is_abstract=True, xml_name=None,
                                members=[
                                    ExportMember("gp", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="GP-FIELD"),
                                ]),
                ExportComposite("Parent", is_abstract=True, xml_name=None,
                                inherits_from=["GrandParent"],
                                members=[
                                    ExportMember("p", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="P-FIELD"),
                                ]),
                ExportComposite("Leaf",
                                inherits_from=["Parent"],
                                xml_name="LEAF",
                                members=[
                                    ExportMember("own", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="OWN-FIELD"),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        block = self._extract_lookup_block(code, "LEAF")

        self.assertIn('"GP-FIELD"', block,
                      "LEAF lookup must include grandparent's GP-FIELD")
        self.assertIn('"P-FIELD"', block,
                      "LEAF lookup must include parent's P-FIELD")
        self.assertIn('"OWN-FIELD"', block,
                      "LEAF lookup must include own OWN-FIELD")


class TestDomainModuleGeneration(unittest.TestCase):
    def test_generates_domain_module_file(self):
        import tempfile
        from cpp_generator import generate_domain_module
        from schema_model import ExportSchema, ExportPrimitive, PrimitiveSupertype

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generate_domain_module(schema, tmpdir)
            path = os.path.join(tmpdir, "domains", "senda.domains.r23-11.cppm")
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("export module senda.domains.r23_11", content)
            self.assertIn("AutosarSchema", content)
            self.assertIn("TypeInfo", content)


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


class TestVersionedDomainModule(unittest.TestCase):
    def test_domain_module_uses_release_in_filename(self):
        import tempfile
        from cpp_generator import generate_cpp_files
        from schema_model import ExportSchema

        schema = ExportSchema(
            release_version="R23-11",
            autosar_version="00052",
            primitives=[], enums=[], composites=[],
            root_type=None, warnings=[], errors=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_cpp_files(schema, tmpdir)
            expected_path = os.path.join(tmpdir, "domains", "senda.domains.r23-11.cppm")
            self.assertTrue(os.path.exists(expected_path), f"Expected {expected_path}")

    def test_domain_module_name_contains_version(self):
        import tempfile
        from cpp_generator import generate_cpp_files
        from schema_model import ExportSchema

        schema = ExportSchema(
            release_version="R23-11",
            autosar_version="00052",
            primitives=[], enums=[], composites=[],
            root_type=None, warnings=[], errors=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_cpp_files(schema, tmpdir)
            path = os.path.join(tmpdir, "domains", "senda.domains.r23-11.cppm")
            with open(path) as f:
                content = f.read()
            self.assertIn("export module senda.domains.r23_11;", content)


class TestFileGeneration(unittest.TestCase):
    def test_generate_cpp_files_creates_domain_module(self):
        import tempfile
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

            domain_path = os.path.join(tmpdir, "domains", "senda.domains.r23-11.cppm")
            self.assertTrue(os.path.exists(domain_path))

            with open(domain_path) as f:
                content = f.read()
            self.assertIn("export module senda.domains.r23_11", content)
            self.assertIn("AutosarSchema", content)

class TestCompositionRoleHoisting(unittest.TestCase):
    """RC1: Composition members without xml_element_name should have their
    target type's roles hoisted into the parent's lookup table."""

    @staticmethod
    def _extract_lookup_block(code, xml_tag):
        """Extract the lookup table block for a given XML tag name."""
        lines = code.split("\n")
        block_lines = []
        capturing = False
        brace_depth = 0
        for line in lines:
            if not capturing and line.strip() == "{":
                capturing = True
                brace_depth = 1
                block_lines = [line]
                continue
            if capturing:
                block_lines.append(line)
                brace_depth += line.count("{") - line.count("}")
                if brace_depth == 0:
                    block = "\n".join(block_lines)
                    if ('tag_to_type.add("%s"' % xml_tag) in block:
                        return block
                    capturing = False
                    block_lines = []
        return ""

    def test_simple_composition_hoisting(self):
        """A composition member without xml_element_name should hoist target roles."""
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
                # Target type: has roles with xml_element_name
                ExportComposite("BaseTypeDirectDefinition", is_abstract=True,
                                xml_name=None,
                                members=[
                                    ExportMember("baseTypeSize", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="BASE-TYPE-SIZE"),
                                    ExportMember("baseTypeEncoding", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="BASE-TYPE-ENCODING"),
                                ]),
                # Parent type: has composition member without xml_element_name
                ExportComposite("SwBaseType", xml_name="SW-BASE-TYPE",
                                members=[
                                    ExportMember("shortName", ["string"],
                                                 min_occurs=1, max_occurs=1,
                                                 xml_element_name="SHORT-NAME"),
                                    # Composition member — no xml_element_name
                                    ExportMember("baseTypeDirectDefinition",
                                                 ["BaseTypeDirectDefinition"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        block = self._extract_lookup_block(code, "SW-BASE-TYPE")

        self.assertIn('"SHORT-NAME"', block,
                      "Own role SHORT-NAME must be present")
        self.assertIn('"BASE-TYPE-SIZE"', block,
                      "Hoisted role BASE-TYPE-SIZE must be present")
        self.assertIn('"BASE-TYPE-ENCODING"', block,
                      "Hoisted role BASE-TYPE-ENCODING must be present")

    def test_transitive_hoisting(self):
        """Composition chains should hoist transitively (A -> B -> C)."""
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
                ExportComposite("Inner", is_abstract=True, xml_name=None,
                                members=[
                                    ExportMember("deepField", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="DEEP-FIELD"),
                                ]),
                ExportComposite("Middle", is_abstract=True, xml_name=None,
                                members=[
                                    ExportMember("midField", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="MID-FIELD"),
                                    # Composition to Inner
                                    ExportMember("inner", ["Inner"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
                ExportComposite("Outer", xml_name="OUTER",
                                members=[
                                    ExportMember("ownField", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="OWN-FIELD"),
                                    # Composition to Middle
                                    ExportMember("middle", ["Middle"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        block = self._extract_lookup_block(code, "OUTER")

        self.assertIn('"OWN-FIELD"', block)
        self.assertIn('"MID-FIELD"', block,
                      "One-level hoisted MID-FIELD must be present")
        self.assertIn('"DEEP-FIELD"', block,
                      "Two-level hoisted DEEP-FIELD must be present")

    def test_cycle_detection(self):
        """Circular composition references should not cause infinite recursion."""
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
                ExportComposite("DocBlock", xml_name="DOCUMENTATION-BLOCK",
                                members=[
                                    ExportMember("title", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="TITLE"),
                                    # Composition to Note (which references back)
                                    ExportMember("note", ["Note"],
                                                 min_occurs=0, max_occurs=None,
                                                 xml_element_name=None),
                                ]),
                ExportComposite("Note", xml_name="NOTE",
                                members=[
                                    ExportMember("text", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="TEXT"),
                                    # Circular: back to DocBlock
                                    ExportMember("docBlock", ["DocBlock"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
            ],
        )

        # Should not raise RecursionError
        code = generate_domain_builder(schema)
        block = self._extract_lookup_block(code, "DOCUMENTATION-BLOCK")

        self.assertIn('"TITLE"', block, "Own role TITLE must be present")
        self.assertIn('"TEXT"', block,
                      "Hoisted role TEXT from Note must be present")


class TestCLIIntegration(unittest.TestCase):
    def test_cpp_flag_recognized(self):
        import subprocess
        result = subprocess.run(
            ["python", "converter.py", "--help"],
            capture_output=True, text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertIn("--cpp", result.stdout)


class TestRoleInfoIsReference(unittest.TestCase):
    """Test that is_reference flag is emitted in RoleInfo."""

    def test_non_reference_role_emits_false(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema, ExportPrimitive, PrimitiveSupertype

        schema = ExportSchema(
            release_version="R23-11",
            composites=[ExportComposite(
                name="MyType", xml_name="MY-TYPE",
                members=[ExportMember(
                    name="child", types=["ChildType"],
                    xml_element_name="CHILD", is_reference=False,
                )],
            )],
            primitives=[ExportPrimitive(name="ChildType", xml_name="CHILD-TYPE")],
        )
        code = generate_domain_builder(schema)
        self.assertIn(", false}", code)

    def test_reference_role_emits_true(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema, ExportPrimitive, PrimitiveSupertype

        schema = ExportSchema(
            release_version="R23-11",
            composites=[ExportComposite(
                name="MyType", xml_name="MY-TYPE",
                members=[ExportMember(
                    name="targetRef", types=["TargetType"],
                    xml_element_name="TARGET-REF", is_reference=True,
                )],
            )],
            primitives=[ExportPrimitive(name="TargetType", xml_name="TARGET-TYPE")],
        )
        code = generate_domain_builder(schema)
        self.assertIn(", true}", code)


if __name__ == "__main__":
    unittest.main()
