import unittest
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schema_model import (
    ExportSchema, ExportPrimitive, ExportEnum, ExportComposite,
    ExportMember, PrimitiveSupertype,
)
from cpp_emitter_generator import generate_arxml_emitter_module


MINIMAL_SCHEMA = ExportSchema(
    release_version="R23-11",
    autosar_version="00052",
    primitives=[
        ExportPrimitive(name="StringSimple", supertype=PrimitiveSupertype.STRING,
                        pattern=None, xml_name=None),
    ],
    enums=[],
    composites=[
        ExportComposite(
            name="ArPackage", members=[
                ExportMember(name=None, types=["StringSimple"], is_reference=False,
                             is_ordered=False, min_occurs=1, max_occurs=1,
                             is_identity=True, doc=None, instance_ref_role=None,
                             xml_element_name="SHORT-NAME"),
            ],
            identifiers=["shortName"], is_ordered=False,
            has_unnamed_string_member=False, is_abstract=False,
            inherits_from=[], xml_name="AR-PACKAGE",
        ),
        ExportComposite(
            name="ISignal", members=[
                ExportMember(name=None, types=["StringSimple"], is_reference=False,
                             is_ordered=False, min_occurs=1, max_occurs=1,
                             is_identity=True, doc=None, instance_ref_role=None,
                             xml_element_name="SHORT-NAME"),
                ExportMember(name="iSignalType", types=["StringSimple"],
                             is_reference=False, is_ordered=False,
                             min_occurs=0, max_occurs=1, is_identity=False,
                             doc=None, instance_ref_role=None,
                             xml_element_name="I-SIGNAL-TYPE"),
            ],
            identifiers=["shortName"], is_ordered=False,
            has_unnamed_string_member=False, is_abstract=False,
            inherits_from=[], xml_name="I-SIGNAL",
        ),
    ],
    root_type=None, warnings=[], errors=[],
)


class TestEmitterModuleGeneration(unittest.TestCase):
    def test_contains_module_declaration(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn("export module senda.emitter.arxml;", code)

    def test_contains_emitter_class(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn("class ArxmlEmitter", code)

    def test_contains_reverse_type_lookup(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn("type_to_tag", code)

    def test_contains_reverse_role_lookup(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn("role_to_xml", code)

    def test_contains_emit_method(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn("emit(", code)

    def test_imports_fir_module(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn("import rupa.fir;", code)

    def test_contains_xml_tag_names(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn('"AR-PACKAGE"', code)
        self.assertIn('"I-SIGNAL"', code)
        self.assertIn('"SHORT-NAME"', code)

    def test_contains_indentation_logic(self):
        code = generate_arxml_emitter_module(MINIMAL_SCHEMA)
        self.assertIn("indent", code)


if __name__ == "__main__":
    unittest.main()
