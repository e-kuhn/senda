import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schema_model import ExportComposite, ExportMember, ExportEnum, ExportPrimitive, PrimitiveSupertype


class TestExportModelXmlNames(unittest.TestCase):
    """These tests don't depend on code generation output format."""
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


# ── Helpers for parsing data-driven output ──

def _extract_array_entries(code, array_name):
    """Extract entries from a static constexpr array in generated code.

    Returns list of raw entry strings (everything between { and })
    for each row in the array.
    """
    entries = []
    lines = code.split("\n")
    in_array = False
    for line in lines:
        stripped = line.strip()
        if not in_array:
            if "constexpr" in stripped and array_name in stripped:
                in_array = True
            continue
        if stripped == "};":
            break
        if stripped.startswith("{") and stripped.endswith("},"):
            entries.append(stripped[1:-2])  # strip { and },
    return entries


def _find_tag_roles(code, xml_tag):
    """Find all TagRoleDesc entries for a given XML tag.

    Returns list of (xml_element_name, role_index, target_type, is_reference) strings.
    """
    tags = _extract_array_entries(code, "kTags[]")
    tag_roles = _extract_array_entries(code, "kTagRoles[]")

    for entry in tags:
        parts = [p.strip().strip('"') for p in entry.split(",")]
        if parts[0] == xml_tag:
            start = int(parts[2])
            count = int(parts[3])
            result = []
            for i in range(start, start + count):
                tr_parts = [p.strip().strip('"') for p in tag_roles[i].split(",")]
                result.append(tr_parts)  # [xml_elem, role_idx, target_type, is_ref]
            return result
    return []


def _tag_role_xml_names(code, xml_tag):
    """Get the set of XML element names in the tag-role entries for a given tag."""
    roles = _find_tag_roles(code, xml_tag)
    return {r[0] for r in roles}


class TestDomainBuilderPrimitives(unittest.TestCase):
    def test_generates_primitive_types(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
                ExportPrimitive("integer", PrimitiveSupertype.INTEGER, xml_name="integer"),
            ],
        )

        code = generate_domain_builder(schema)
        entries = _extract_array_entries(code, "kTypes[]")
        # Primitives have kind=1
        self.assertTrue(any('"string", 1,' in e for e in entries))
        self.assertTrue(any('"integer", 1,' in e for e in entries))

    def test_generates_enum_types(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

        schema = ExportSchema(
            release_version="R23-11",
            enums=[
                ExportEnum("ISignalTypeEnum", ["PRIMITIVE", "STRUCTURE"],
                           xml_name="I-SIGNAL-TYPE-ENUM--SIMPLE"),
            ],
        )

        code = generate_domain_builder(schema)
        # Enum kind = 4
        type_entries = _extract_array_entries(code, "kTypes[]")
        self.assertTrue(any('"ISignalTypeEnum", 4,' in e for e in type_entries))
        # Enum values present
        ev_entries = _extract_array_entries(code, "kEnumValues[]")
        values = [e.strip().strip('"') for e in ev_entries]
        self.assertIn("PRIMITIVE", values)
        self.assertIn("STRUCTURE", values)


class TestDomainBuilderComposites(unittest.TestCase):
    def test_generates_composite_types(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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

        # Composite kind = 0
        type_entries = _extract_array_entries(code, "kTypes[]")
        self.assertTrue(any('"Identifiable", 0,' in e for e in type_entries))
        self.assertTrue(any('"ISignal", 0,' in e for e in type_entries))

        # Abstract flag
        identifiable_entry = next(e for e in type_entries if '"Identifiable"' in e)
        self.assertIn("true", identifiable_entry)

        # Supertype: ISignal -> Identifiable (index 1 since string is index 0)
        isignal_entry = next(e for e in type_entries if '"ISignal"' in e)
        self.assertIn(", 1,", isignal_entry)  # supertype index = 1

        # Roles
        role_entries = _extract_array_entries(code, "kRoles[]")
        role_names = [e.split(",")[0].strip().strip('"') for e in role_entries]
        self.assertIn("shortName", role_names)
        self.assertIn("length", role_names)

    def test_generates_lookup_tables(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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

        tag_entries = _extract_array_entries(code, "kTags[]")
        self.assertTrue(any('"I-SIGNAL"' in e for e in tag_entries))

        xml_names = _tag_role_xml_names(code, "I-SIGNAL")
        self.assertIn("SHORT-NAME", xml_names)

    def test_multiplicity_mapping(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
        role_entries = _extract_array_entries(code, "kRoles[]")

        # One=0, Optional=1, Many=2, OneOrMore=3
        required_role = next(e for e in role_entries if '"required"' in e)
        self.assertTrue(required_role.strip().endswith("0"))
        optional_role = next(e for e in role_entries if '"optional"' in e)
        self.assertTrue(optional_role.strip().endswith("1"))
        many_role = next(e for e in role_entries if '"many"' in e)
        self.assertTrue(many_role.strip().endswith("2"))
        one_or_more_role = next(e for e in role_entries if '"oneOrMore"' in e)
        self.assertTrue(one_or_more_role.strip().endswith("3"))


class TestLookupTableInheritedRoles(unittest.TestCase):
    def test_child_lookup_includes_parent_roles(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
        xml_names = _tag_role_xml_names(code, "I-SIGNAL")

        self.assertIn("LONG-NAME", xml_names,
                      "I-SIGNAL lookup must include inherited LONG-NAME role")
        self.assertIn("LENGTH", xml_names,
                      "I-SIGNAL lookup must include own LENGTH role")

    def test_child_role_overrides_parent_role(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
        roles = _find_tag_roles(code, "CHILD")

        name_roles = [r for r in roles if r[0] == "NAME"]
        self.assertEqual(len(name_roles), 1,
                         "Child should have exactly one NAME role (child overrides parent)")

    def test_deep_inheritance_chain(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
        xml_names = _tag_role_xml_names(code, "LEAF")

        self.assertIn("GP-FIELD", xml_names)
        self.assertIn("P-FIELD", xml_names)
        self.assertIn("OWN-FIELD", xml_names)


class TestDomainModuleGeneration(unittest.TestCase):
    def test_generates_domain_module_file(self):
        import tempfile
        from cpp_generator import generate_domain_module
        from schema_model import ExportSchema

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
            self.assertIn("TypeDesc", content)


class TestDomainBuilderUnnamedRoles(unittest.TestCase):
    def test_unnamed_role_uses_dotdot(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
        role_entries = _extract_array_entries(code, "kRoles[]")
        self.assertTrue(any('".."' in e for e in role_entries))


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
        from schema_model import ExportSchema

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
    def test_simple_composition_hoisting(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

        schema = ExportSchema(
            release_version="R23-11",
            primitives=[
                ExportPrimitive("string", PrimitiveSupertype.STRING, xml_name="string"),
            ],
            composites=[
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
                ExportComposite("SwBaseType", xml_name="SW-BASE-TYPE",
                                members=[
                                    ExportMember("shortName", ["string"],
                                                 min_occurs=1, max_occurs=1,
                                                 xml_element_name="SHORT-NAME"),
                                    ExportMember("baseTypeDirectDefinition",
                                                 ["BaseTypeDirectDefinition"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        xml_names = _tag_role_xml_names(code, "SW-BASE-TYPE")

        self.assertIn("SHORT-NAME", xml_names)
        self.assertIn("BASE-TYPE-SIZE", xml_names)
        self.assertIn("BASE-TYPE-ENCODING", xml_names)

    def test_transitive_hoisting(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
                                    ExportMember("inner", ["Inner"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
                ExportComposite("Outer", xml_name="OUTER",
                                members=[
                                    ExportMember("ownField", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="OWN-FIELD"),
                                    ExportMember("middle", ["Middle"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        xml_names = _tag_role_xml_names(code, "OUTER")

        self.assertIn("OWN-FIELD", xml_names)
        self.assertIn("MID-FIELD", xml_names)
        self.assertIn("DEEP-FIELD", xml_names)

    def test_cycle_detection(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
                                    ExportMember("note", ["Note"],
                                                 min_occurs=0, max_occurs=None,
                                                 xml_element_name=None),
                                ]),
                ExportComposite("Note", xml_name="NOTE",
                                members=[
                                    ExportMember("text", ["string"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name="TEXT"),
                                    ExportMember("docBlock", ["DocBlock"],
                                                 min_occurs=0, max_occurs=1,
                                                 xml_element_name=None),
                                ]),
            ],
        )

        code = generate_domain_builder(schema)
        xml_names = _tag_role_xml_names(code, "DOCUMENTATION-BLOCK")

        self.assertIn("TITLE", xml_names)
        self.assertIn("TEXT", xml_names)


class TestCLIIntegration(unittest.TestCase):
    def test_cpp_flag_recognized(self):
        import subprocess
        result = subprocess.run(
            ["python", "converter.py", "--help"],
            capture_output=True, text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertIn("--cpp", result.stdout)


class TestInnerRefRoleInjection(unittest.TestCase):
    def test_inner_ref_tag_injected_into_target_type(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

        schema = ExportSchema(
            release_version="R23-11",
            composites=[
                ExportComposite(
                    name="ISignalTriggering", xml_name="I-SIGNAL-TRIGGERING",
                    members=[ExportMember(
                        name="iSignalPort", types=["ISignalPort"],
                        xml_element_name="I-SIGNAL-PORT-REFS",
                        is_reference=True,
                        inner_ref_tag="I-SIGNAL-PORT-REF",
                    )],
                ),
                ExportComposite(
                    name="ISignalPort", xml_name="I-SIGNAL-PORT",
                    members=[],
                ),
            ],
            primitives=[], enums=[],
        )
        code = generate_domain_builder(schema)

        triggering_names = _tag_role_xml_names(code, "I-SIGNAL-TRIGGERING")
        self.assertIn("I-SIGNAL-PORT-REFS", triggering_names)

        port_names = _tag_role_xml_names(code, "I-SIGNAL-PORT")
        self.assertIn("I-SIGNAL-PORT-REF", port_names,
                      "Inner REF tag must be injected into target type's lookup")


class TestRoleInfoIsReference(unittest.TestCase):
    def test_non_reference_role_emits_false(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
        roles = _find_tag_roles(code, "MY-TYPE")
        child_role = next(r for r in roles if r[0] == "CHILD")
        self.assertEqual(child_role[3].strip(), "false")

    def test_reference_role_emits_true(self):
        from cpp_generator import generate_domain_builder
        from schema_model import ExportSchema

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
        roles = _find_tag_roles(code, "MY-TYPE")
        ref_role = next(r for r in roles if r[0] == "TARGET-REF")
        self.assertEqual(ref_role[3].strip(), "true")


if __name__ == "__main__":
    unittest.main()
