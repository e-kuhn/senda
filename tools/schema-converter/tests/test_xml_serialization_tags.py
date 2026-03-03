"""Tests for XML serialization tag extraction and inference."""

import os
import pytest
from schema_parser import _get_member_from_appinfo, parse_schema, export_schema
from cpp_generator import generate_domain_builder
from xml.etree import ElementTree as ET

XSD_NS = "http://www.w3.org/2001/XMLSchema"


def _make_element_with_appinfo(tag_text: str, element_name: str = "TEST-ELEM",
                                element_tag: str = "element") -> ET.Element:
    """Build an xsd:element with appinfo containing the given tag_text."""
    elem = ET.Element(f"{{{XSD_NS}}}{element_tag}")
    elem.set("name", element_name)
    annotation = ET.SubElement(elem, f"{{{XSD_NS}}}annotation")
    appinfo = ET.SubElement(annotation, f"{{{XSD_NS}}}appinfo")
    appinfo.set("source", "tags")
    appinfo.text = tag_text
    return elem


class TestXmlTagExtraction:
    """Test extraction of xml.* tags from appinfo text."""

    def test_all_tags_present(self):
        elem = _make_element_with_appinfo(
            'mmt.qualifiedName="AdminData.sdg";'
            'xml.roleElement="true";'
            'xml.roleWrapperElement="true";'
            'xml.sequenceOffset="60";'
            'xml.typeElement="false";'
            'xml.typeWrapperElement="false"'
        )
        member = _get_member_from_appinfo(elem)
        assert member is not None
        assert member.xml_role_element is True
        assert member.xml_role_wrapper_element is True
        assert member.xml_type_element is False
        assert member.xml_type_wrapper_element is False
        assert member.xml_sequence_offset == 60

    def test_role_element_only(self):
        elem = _make_element_with_appinfo(
            'mmt.qualifiedName="SwRecordLayout.swRecordLayoutGroup";'
            'xml.roleElement="true";'
            'xml.roleWrapperElement="false";'
            'xml.typeElement="false";'
            'xml.typeWrapperElement="false"'
        )
        member = _get_member_from_appinfo(elem)
        assert member is not None
        assert member.xml_role_element is True
        assert member.xml_role_wrapper_element is False
        assert member.xml_type_element is False
        assert member.xml_type_wrapper_element is False

    def test_attribute_tag(self):
        elem = _make_element_with_appinfo(
            'mmt.qualifiedName="ARObject.checksum";'
            'xml.attribute="true";'
            'xml.name="S"',
            element_tag="attribute"
        )
        member = _get_member_from_appinfo(elem)
        assert member is not None
        assert member.xml_attribute is True

    def test_type_element_true(self):
        elem = _make_element_with_appinfo(
            'mmt.qualifiedName="DelegationSwConnector.innerPort";'
            'xml.typeElement="true"'
        )
        member = _get_member_from_appinfo(elem)
        assert member is not None
        assert member.xml_type_element is True

    def test_negative_sequence_offset(self):
        elem = _make_element_with_appinfo(
            'mmt.qualifiedName="Referrable.shortName";'
            'xml.sequenceOffset="-100"'
        )
        member = _get_member_from_appinfo(elem)
        assert member is not None
        assert member.xml_sequence_offset == -100

    def test_no_explicit_xml_tags_inferred(self):
        """Tags not in appinfo — inferred as RoleOnly from element structure."""
        elem = _make_element_with_appinfo(
            'mmt.qualifiedName="SomeType.someField";'
            'pureMM.minOccurs="0";'
            'pureMM.maxOccurs="1"'
        )
        member = _get_member_from_appinfo(elem)
        assert member is not None
        # Inferred as RoleOnly (simple element, no complexType/choice)
        assert member.xml_role_element is True
        assert member.xml_role_wrapper_element is False
        assert member.xml_type_element is False
        assert member.xml_type_wrapper_element is False
        assert member.xml_attribute is None
        assert member.xml_sequence_offset is None


XSD_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "schema", "AUTOSAR_00051.xsd")


class TestXmlTagPropagation:
    """Test that XML tags propagate from XSD through to ExportMember."""

    def test_tags_in_export_member(self):
        """Parse the real R20-11 schema and verify AdminData.sdg has correct tags."""
        if not os.path.exists(XSD_PATH):
            pytest.skip("R20-11 schema not available")

        schema = export_schema(parse_schema(XSD_PATH))
        admin_data = next((c for c in schema.composites
                          if c.name == "AdminData"), None)
        assert admin_data is not None

        sdg_member = next((m for m in admin_data.members
                          if m.name == "sdg"), None)
        assert sdg_member is not None
        assert sdg_member.xml_role_element is True
        assert sdg_member.xml_role_wrapper_element is True
        assert sdg_member.xml_type_element is False
        assert sdg_member.xml_type_wrapper_element is False


class TestXmlTagInference:
    """Test inference of XML tags when not explicitly in appinfo."""

    def test_short_name_inferred_as_role_element(self):
        """SHORT-NAME has no xml.roleElement in appinfo — should be inferred."""
        if not os.path.exists(XSD_PATH):
            pytest.skip("R20-11 schema not available")

        schema = export_schema(parse_schema(XSD_PATH))
        referrable = next((c for c in schema.composites
                          if c.name == "Referrable"), None)
        assert referrable is not None

        short_name = next((m for m in referrable.members
                          if m.name == "shortName"), None)
        assert short_name is not None
        assert short_name.xml_role_element is True
        assert short_name.xml_role_wrapper_element in (False, None)
        assert short_name.xml_type_element in (False, None)

    def test_no_none_tags_after_inference(self):
        """After inference, no ExportMember should have all-None xml tags
        (at least xml_role_element or xml_attribute should be set)."""
        if not os.path.exists(XSD_PATH):
            pytest.skip("R20-11 schema not available")

        schema = export_schema(parse_schema(XSD_PATH))
        for c in schema.composites:
            for m in c.members:
                has_any_tag = any([
                    m.xml_role_element is not None,
                    m.xml_role_wrapper_element is not None,
                    m.xml_type_element is not None,
                    m.xml_type_wrapper_element is not None,
                    m.xml_attribute is not None,
                ])
                assert has_any_tag, (
                    f"{c.name}.{m.name} has no XML serialization tags after inference"
                )


class TestCppGeneration:
    """Test that generated C++ includes xml_tags bitfield."""

    def test_tag_role_desc_has_xml_tags(self):
        """Generated C++ should include xml_tags and sequence_offset fields."""
        if not os.path.exists(XSD_PATH):
            pytest.skip("R20-11 schema not available")

        schema = export_schema(parse_schema(XSD_PATH))
        code = generate_domain_builder(schema)

        # AdminData.sdg has rE=T, rWE=T → 0x03 (RoleElement|RoleWrapperElement)
        assert "0x03," in code
