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


if __name__ == "__main__":
    unittest.main()
