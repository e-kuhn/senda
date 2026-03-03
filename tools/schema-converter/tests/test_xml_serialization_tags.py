"""Tests for XML serialization tag extraction and inference."""

import pytest
from schema_parser import _get_member_from_appinfo
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

    def test_no_xml_tags(self):
        """Tags not present — fields should remain None."""
        elem = _make_element_with_appinfo(
            'mmt.qualifiedName="SomeType.someField";'
            'pureMM.minOccurs="0";'
            'pureMM.maxOccurs="1"'
        )
        member = _get_member_from_appinfo(elem)
        assert member is not None
        assert member.xml_role_element is None
        assert member.xml_role_wrapper_element is None
        assert member.xml_type_element is None
        assert member.xml_type_wrapper_element is None
        assert member.xml_attribute is None
        assert member.xml_sequence_offset is None
