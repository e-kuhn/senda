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

    def test_group_is_abstract(self):
        from schema_parser import parse_schema_from_string
        from schema_model import InternalComplexType
        schema = parse_schema_from_string(SIMPLE_GROUP_XSD)
        t = schema.types["groups:ABSOLUTE-TOLERANCE"]
        self.assertTrue(t.is_abstract)


# --- XSD fragments for export tests ---

INHERITANCE_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">

  <xsd:group name="BASE-GRP">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="BaseGrp"</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence>
      <xsd:element maxOccurs="1" minOccurs="0" name="X" type="xsd:string">
        <xsd:annotation>
          <xsd:appinfo source="tags">mmt.qualifiedName="BaseGrp.x";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
        </xsd:annotation>
      </xsd:element>
    </xsd:sequence>
  </xsd:group>

  <xsd:attributeGroup name="BASE-GRP">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="BaseGrp"</xsd:appinfo>
    </xsd:annotation>
    <xsd:attribute name="ATTR-A" type="xsd:string">
      <xsd:annotation>
        <xsd:appinfo source="tags">mmt.qualifiedName="BaseGrp.attrA";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
      </xsd:annotation>
    </xsd:attribute>
  </xsd:attributeGroup>

  <xsd:group name="CHILD-GRP">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="ChildGrp"</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence>
      <xsd:element maxOccurs="1" minOccurs="0" name="Y" type="xsd:string">
        <xsd:annotation>
          <xsd:appinfo source="tags">mmt.qualifiedName="ChildGrp.y";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
        </xsd:annotation>
      </xsd:element>
    </xsd:sequence>
  </xsd:group>

  <xsd:complexType name="CHILD-GRP">
    <xsd:sequence>
      <xsd:group ref="AR:BASE-GRP"/>
      <xsd:group ref="AR:CHILD-GRP"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="AR:BASE-GRP"/>
  </xsd:complexType>
</xsd:schema>
"""

SIMPLE_CONTENT_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">

  <xsd:group name="AR-OBJECT">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="ArObject"</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence/>
  </xsd:group>

  <xsd:attributeGroup name="AR-OBJECT">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="ArObject"</xsd:appinfo>
    </xsd:annotation>
    <xsd:attribute name="TIMESTAMP" type="xsd:string">
      <xsd:annotation>
        <xsd:appinfo source="tags">mmt.qualifiedName="ArObject.timestamp";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
      </xsd:annotation>
    </xsd:attribute>
  </xsd:attributeGroup>

  <xsd:simpleType name="MY-ENUM--SIMPLE">
    <xsd:restriction base="xsd:string">
      <xsd:enumeration value="A">
        <xsd:annotation>
          <xsd:appinfo source="tags">mmt.qualifiedName="MyEnum.a"</xsd:appinfo>
        </xsd:annotation>
      </xsd:enumeration>
    </xsd:restriction>
  </xsd:simpleType>

  <xsd:complexType name="MY-ENUM">
    <xsd:simpleContent>
      <xsd:extension base="AR:MY-ENUM--SIMPLE">
        <xsd:attributeGroup ref="AR:AR-OBJECT"/>
      </xsd:extension>
    </xsd:simpleContent>
  </xsd:complexType>
</xsd:schema>
"""

ALIAS_CHAIN_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">

  <xsd:simpleType name="NUMERICAL-VALUE--SIMPLE">
    <xsd:restriction base="xsd:double"/>
  </xsd:simpleType>

  <xsd:simpleType name="TIME-VALUE--SIMPLE">
    <xsd:restriction base="AR:NUMERICAL-VALUE--SIMPLE"/>
  </xsd:simpleType>

  <xsd:simpleType name="BOOLEAN--SIMPLE">
    <xsd:restriction base="xsd:boolean"/>
  </xsd:simpleType>

  <xsd:group name="KEEPER">
    <xsd:annotation>
      <xsd:appinfo source="tags">mmt.qualifiedName="Keeper"</xsd:appinfo>
    </xsd:annotation>
    <xsd:sequence>
      <xsd:element name="T" type="AR:TIME-VALUE--SIMPLE" minOccurs="0" maxOccurs="1">
        <xsd:annotation>
          <xsd:appinfo source="tags">mmt.qualifiedName="Keeper.t";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
        </xsd:annotation>
      </xsd:element>
      <xsd:element name="B" type="AR:BOOLEAN--SIMPLE" minOccurs="0" maxOccurs="1">
        <xsd:annotation>
          <xsd:appinfo source="tags">mmt.qualifiedName="Keeper.b";pureMM.maxOccurs="1";pureMM.minOccurs="0"</xsd:appinfo>
        </xsd:annotation>
      </xsd:element>
    </xsd:sequence>
  </xsd:group>

  <xsd:complexType name="KEEPER">
    <xsd:sequence>
      <xsd:group ref="AR:KEEPER"/>
    </xsd:sequence>
  </xsd:complexType>
</xsd:schema>
"""


class TestExportInheritance(unittest.TestCase):
    def test_group_exported_as_abstract(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(INHERITANCE_XSD)
        export = export_schema(schema)
        base = next((c for c in export.composites if c.name == "BaseGrp"), None)
        self.assertIsNotNone(base)
        self.assertTrue(base.is_abstract)

    def test_attrgroup_merged_into_group(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(INHERITANCE_XSD)
        export = export_schema(schema)
        base = next((c for c in export.composites if c.name == "BaseGrp"), None)
        member_names = [m.name for m in base.members]
        self.assertIn("x", member_names)
        self.assertIn("attrA", member_names)

    def test_concrete_type_inherits_from_group(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(INHERITANCE_XSD)
        export = export_schema(schema)
        child = next((c for c in export.composites if c.name == "ChildGrp"), None)
        self.assertIsNotNone(child)
        self.assertFalse(child.is_abstract)
        self.assertIn("BaseGrp", child.inherits_from)

    def test_concrete_type_has_own_members_only(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(INHERITANCE_XSD)
        export = export_schema(schema)
        child = next((c for c in export.composites if c.name == "ChildGrp"), None)
        member_names = [m.name for m in child.members]
        self.assertIn("y", member_names)
        self.assertNotIn("x", member_names)
        self.assertNotIn("attrA", member_names)


class TestSimpleContentUnnamedMember(unittest.TestCase):
    def test_primitive_wrapper_has_unnamed_member(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(SIMPLE_CONTENT_XSD)
        export = export_schema(schema)
        wrapper = next((c for c in export.composites if c.name == "MyEnum"), None)
        self.assertIsNotNone(wrapper)
        # Should inherit from ArObject but NOT from MyEnumSimple
        self.assertIn("ArObject", wrapper.inherits_from)
        self.assertNotIn("MyEnumSimple", wrapper.inherits_from)
        # Should have unnamed member carrying MyEnumSimple
        unnamed = [m for m in wrapper.members if m.name is None]
        self.assertEqual(len(unnamed), 1)
        self.assertIn("MyEnumSimple", unnamed[0].types)


class TestPrimitiveSupertypeDetection(unittest.TestCase):
    def test_boolean_supertype(self):
        from schema_parser import parse_schema_from_string, export_schema
        from schema_model import PrimitiveSupertype
        schema = parse_schema_from_string(ALIAS_CHAIN_XSD)
        export = export_schema(schema)
        bp = next((p for p in export.primitives if p.name == "BooleanSimple"), None)
        self.assertIsNotNone(bp)
        self.assertEqual(bp.supertype, PrimitiveSupertype.BOOLEAN)

    def test_float_chain(self):
        from schema_parser import parse_schema_from_string, export_schema
        from schema_model import PrimitiveSupertype
        schema = parse_schema_from_string(ALIAS_CHAIN_XSD)
        export = export_schema(schema)
        tv = next((p for p in export.primitives if p.name == "TimeValueSimple"), None)
        self.assertIsNotNone(tv)
        self.assertEqual(tv.supertype, PrimitiveSupertype.FLOAT)


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


class TestIntegerTokenUnion(unittest.TestCase):
    def test_integer_with_non_numeric_tokens_becomes_union(self):
        """Integer pattern with tokens like UNSPECIFIED should become INTEGER_ENUM_UNION."""
        from schema_parser import analyze_pattern
        from schema_model import PrimitiveSupertype
        # Pattern like AlignmentTypeSimple: integers + UNSPECIFIED + BOOLEAN + PTR
        pattern = "(0[xX][0-9a-fA-F]+)|(0[0-7]+)|(0[bB][0-1]+)|([1-9][0-9]*)|0|UNSPECIFIED|UNKNOWN|BOOLEAN|PTR"
        supertype, cleaned, tokens = analyze_pattern(pattern, "AlignmentTypeSimple")
        self.assertEqual(supertype, PrimitiveSupertype.INTEGER_ENUM_UNION)
        self.assertEqual(tokens, ["UNSPECIFIED", "UNKNOWN", "BOOLEAN", "PTR"])

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

    def test_integer_with_any_token_becomes_union(self):
        """Even a single non-numeric token like 'ANY' produces union."""
        from schema_parser import analyze_pattern
        from schema_model import PrimitiveSupertype
        pattern = "[1-9][0-9]*|0|ANY"
        supertype, _, tokens = analyze_pattern(pattern, "AnyServiceInstanceIdSimple")
        self.assertEqual(supertype, PrimitiveSupertype.INTEGER_ENUM_UNION)


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


IDENTIFIER_WRAPPER_XSD = """\
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

  <xsd:simpleType name="IDENTIFIER--SIMPLE">
    <xsd:restriction base="xsd:string">
      <xsd:pattern value="[a-zA-Z_][a-zA-Z0-9_]*"/>
    </xsd:restriction>
  </xsd:simpleType>

  <xsd:complexType name="IDENTIFIER">
    <xsd:simpleContent>
      <xsd:extension base="AR:IDENTIFIER--SIMPLE">
        <xsd:attributeGroup ref="AR:AR-OBJECT"/>
      </xsd:extension>
    </xsd:simpleContent>
  </xsd:complexType>

  <xsd:simpleType name="ALIGNMENT-TYPE--SIMPLE">
    <xsd:restriction base="xsd:string">
      <xsd:pattern value="[0-9]+"/>
    </xsd:restriction>
  </xsd:simpleType>

  <xsd:complexType name="ALIGNMENT-TYPE">
    <xsd:simpleContent>
      <xsd:extension base="AR:ALIGNMENT-TYPE--SIMPLE">
        <xsd:attributeGroup ref="AR:AR-OBJECT"/>
      </xsd:extension>
    </xsd:simpleContent>
  </xsd:complexType>
</xsd:schema>
"""


class TestIdentifierUnnamedMemberWithId(unittest.TestCase):
    def test_identifier_wrapper_has_id_annotation(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(IDENTIFIER_WRAPPER_XSD)
        export = export_schema(schema)
        wrapper = next((c for c in export.composites if c.name == "Identifier"), None)
        self.assertIsNotNone(wrapper)
        unnamed = [m for m in wrapper.members if m.name is None]
        self.assertEqual(len(unnamed), 1)
        self.assertTrue(unnamed[0].is_identity)

    def test_non_identifier_wrapper_no_id(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(IDENTIFIER_WRAPPER_XSD)
        export = export_schema(schema)
        wrapper = next((c for c in export.composites if c.name == "AlignmentType"), None)
        self.assertIsNotNone(wrapper)
        unnamed = [m for m in wrapper.members if m.name is None]
        self.assertEqual(len(unnamed), 1)
        self.assertFalse(unnamed[0].is_identity)

    def test_identifier_wrapper_inherits_ar_object(self):
        from schema_parser import parse_schema_from_string, export_schema
        schema = parse_schema_from_string(IDENTIFIER_WRAPPER_XSD)
        export = export_schema(schema)
        wrapper = next((c for c in export.composites if c.name == "Identifier"), None)
        self.assertIn("ARObject", wrapper.inherits_from)
        # Should NOT inherit from IdentifierSimple
        self.assertNotIn("IdentifierSimple", wrapper.inherits_from)


INSTANCE_REF_XSD = """\
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:AR="http://autosar.org/schema/r4.0"
            targetNamespace="http://autosar.org/schema/r4.0">

  <xsd:simpleType name="REF">
    <xsd:restriction base="xsd:string"/>
  </xsd:simpleType>

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


if __name__ == "__main__":
    unittest.main()
