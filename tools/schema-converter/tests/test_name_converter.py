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

    def test_name_with_slash(self):
        from name_converter import extract_qualified_name
        self.assertEqual(
            extract_qualified_name(
                'atp.EnumerationLiteralIndex="1";atp.Status="removed";mmt.qualifiedName="RemotingTechnologyEnum.some/ip"'
            ),
            "some/ip",
        )

    def test_name_with_hyphen_and_digits(self):
        from name_converter import extract_qualified_name
        self.assertEqual(
            extract_qualified_name(
                'atp.EnumerationLiteralIndex="6";mmt.qualifiedName="EthernetPhysicalLayerTypeEnum.1000BASE-T"'
            ),
            "1000BASE-T",
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
