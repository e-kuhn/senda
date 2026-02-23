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

    def test_integer_type(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("PositiveIntegerSimple", PrimitiveSupertype.INTEGER)
        lines = generate_primitive(p)
        self.assertIn("type PositiveIntegerSimple = ::integer;", lines)


class TestEnumGeneration(unittest.TestCase):
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

    def test_subtypes_enum_pascal_case(self):
        from rupa_generator import generate_enum
        e = ExportEnum("SubtypesEnum",
                       ["ABSTRACT-ACCESS-POINT", "SOME-OTHER"],
                       is_subtypes_enum=True)
        text = generate_enum(e)
        self.assertIn("AbstractAccessPoint,", text)
        self.assertIn("SomeOther,", text)


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

    def test_abstract_annotation(self):
        from rupa_generator import generate_composite
        c = ExportComposite("ARObject", members=[
            ExportMember("checksum", ["StringSimple"], min_occurs=0, max_occurs=1),
        ], is_abstract=True)
        lines = generate_composite(c)
        self.assertIn("#[abstract]", lines)
        self.assertIn("type ARObject = {", lines)

    def test_inheritance_syntax(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Referrable", members=[
            ExportMember("shortName", ["Identifier"], min_occurs=1, max_occurs=1),
        ], is_abstract=True, inherits_from=["ARObject"])
        lines = generate_composite(c)
        self.assertIn("#[abstract]", lines)
        self.assertIn("type Referrable = ARObject {", lines)

    def test_multiple_inheritance(self):
        from rupa_generator import generate_composite
        c = ExportComposite("AccessControlEnum",
                            inherits_from=["ARObject", "AccessControlEnumSimple"])
        lines = generate_composite(c)
        self.assertIn("type AccessControlEnum = ARObject, AccessControlEnumSimple { };", lines)

    def test_empty_body_with_inheritance(self):
        from rupa_generator import generate_composite
        c = ExportComposite("CollectableElement",
                            is_abstract=True,
                            inherits_from=["Identifiable"])
        lines = generate_composite(c)
        self.assertIn("#[abstract]", lines)
        self.assertIn("type CollectableElement = Identifiable { };", lines)
        # Should not have a separate closing brace on its own line
        self.assertNotIn("\n};", lines)

    def test_empty_body_no_inheritance(self):
        from rupa_generator import generate_composite
        c = ExportComposite("EmptyType")
        lines = generate_composite(c)
        self.assertIn("type EmptyType = { };", lines)


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
        self.assertIn("/** Maximum allowable deviation */", text)
        self.assertIn("/** Max deviation in seconds */", text)

    def test_composite_no_doc(self):
        from rupa_generator import generate_composite
        c = ExportComposite("EmptyType", doc=None)
        text = generate_composite(c)
        self.assertNotIn("/**", text)

    def test_member_doc_before_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Foo", members=[
            ExportMember("bar", ["BarType"], min_occurs=1, max_occurs=1,
                         doc="The bar field"),
        ])
        text = generate_composite(c)
        lines = text.split("\n")
        doc_idx = next(i for i, l in enumerate(lines) if "/** The bar field */" in l)
        member_idx = next(i for i, l in enumerate(lines) if ".bar" in l)
        self.assertLess(doc_idx, member_idx)

    def test_enum_multi_line_with_docs(self):
        from rupa_generator import generate_enum
        e = ExportEnum("StatusEnum", ["ok", "fail"],
                       doc="Status type",
                       value_docs=["All good", "Something broke"])
        text = generate_enum(e)
        self.assertIn("/** Status type */", text)
        self.assertIn("/** All good */", text)
        self.assertIn("/** Something broke */", text)
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

    def test_enum_subtypes_pascal_case(self):
        from rupa_generator import generate_enum
        e = ExportEnum("SubEnum",
                       ["ABSTRACT-ACCESS-POINT", "CALL-POINT"],
                       is_subtypes_enum=True)
        text = generate_enum(e)
        self.assertIn("\n    AbstractAccessPoint,", text)
        self.assertIn("\n    CallPoint,", text)

    def test_primitive_doc_comment(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("CIdent", PrimitiveSupertype.STRING,
                            pattern="[a-zA-Z_]+",
                            doc="C identifier")
        text = generate_primitive(p)
        self.assertIn("/** C identifier */", text)


class TestMultiLineVariantComments(unittest.TestCase):
    def test_variant_above_member(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Foo", members=[
            ExportMember("bar", ["Primary", "Alt1", "Alt2"],
                         min_occurs=0, max_occurs=1),
        ])
        text = generate_composite(c, show_alternatives=True)
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
        text = generate_composite(c, show_alternatives=True)
        self.assertNotIn("// also", text)

    def test_many_variants_all_shown(self):
        from rupa_generator import generate_composite
        types = ["Primary"] + ["Type%d" % i for i in range(10)]
        c = ExportComposite("Foo", members=[
            ExportMember("bar", types, min_occurs=0, max_occurs=1),
        ])
        text = generate_composite(c, show_alternatives=True)
        # ALL alternatives shown, no truncation
        for i in range(10):
            self.assertIn("Type%d" % i, text)
        self.assertNotIn("more)", text)

    def test_variants_hidden_by_default(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Foo", members=[
            ExportMember("bar", ["Primary", "Alt1", "Alt2"],
                         min_occurs=0, max_occurs=1),
        ])
        text = generate_composite(c)
        self.assertNotIn("// also:", text)


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


class TestUnionPrimitive(unittest.TestCase):
    def test_integer_enum_union(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("AlignmentTypeSimple",
                            PrimitiveSupertype.INTEGER_ENUM_UNION,
                            values=["UNSPECIFIED", "UNKNOWN", "BOOLEAN", "PTR"])
        text = generate_primitive(p)
        self.assertIn("type AlignmentTypeSimple = ::integer | ::enum(UNSPECIFIED, UNKNOWN, BOOLEAN, PTR);", text)

    def test_union_with_doc(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("AlignmentTypeSimple",
                            PrimitiveSupertype.INTEGER_ENUM_UNION,
                            values=["ANY"],
                            doc="Alignment type")
        text = generate_primitive(p)
        self.assertIn("/** Alignment type */", text)
        self.assertIn("::integer | ::enum(ANY);", text)


class TestUnnamedMemberWithId(unittest.TestCase):
    def test_unnamed_member_with_id(self):
        from rupa_generator import generate_composite
        c = ExportComposite("Identifier",
                            members=[
                                ExportMember(None, ["IdentifierSimple"],
                                             min_occurs=1, max_occurs=1,
                                             is_identity=True),
                            ],
                            inherits_from=["ARObject"])
        text = generate_composite(c)
        self.assertIn("#[id]", text)
        self.assertIn(".. : IdentifierSimple;", text)
        self.assertIn("type Identifier = ARObject {", text)

    def test_unnamed_member_without_id(self):
        from rupa_generator import generate_composite
        c = ExportComposite("AlignmentType",
                            members=[
                                ExportMember(None, ["AlignmentTypeSimple"],
                                             min_occurs=1, max_occurs=1),
                            ],
                            inherits_from=["ARObject"])
        text = generate_composite(c)
        self.assertNotIn("#[id]", text)
        self.assertIn(".. : AlignmentTypeSimple;", text)


class TestBooleanPrimitive(unittest.TestCase):
    def test_boolean_with_values(self):
        from rupa_generator import generate_primitive
        p = ExportPrimitive("BooleanSimple", PrimitiveSupertype.BOOLEAN,
                            values=["0", "1"])
        lines = generate_primitive(p)
        self.assertIn("type BooleanSimple = ::boolean;", lines)
        self.assertIn('#[values("0" = false, "1" = true)]', lines)
        self.assertNotIn("#[pattern", lines)


if __name__ == "__main__":
    unittest.main()
