import unittest
import os

SCHEMA_PATH = "/Users/ekuhn/CLionProjects/autosar-dsl/schema/AUTOSAR_00052.xsd"


@unittest.skipUnless(os.path.exists(SCHEMA_PATH), "AUTOSAR schema not available")
class TestFullSchemaParsing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from schema_parser import parse_schema, export_schema
        cls.internal = parse_schema(SCHEMA_PATH)
        cls.schema = export_schema(cls.internal)

    def test_version_info(self):
        self.assertEqual(self.schema.release_version, "R23-11")
        self.assertIn("4.9", self.schema.autosar_version)

    def test_has_primitives(self):
        self.assertGreater(len(self.schema.primitives), 10)

    def test_has_enums(self):
        self.assertGreater(len(self.schema.enums), 50)

    def test_has_composites(self):
        self.assertGreater(len(self.schema.composites), 500)

    def test_has_root_type(self):
        self.assertIsNotNone(self.schema.root_type)

    def test_known_type_exists(self):
        names = {c.name for c in self.schema.composites}
        self.assertIn("ARPackage", names)

    def test_known_primitive_exists(self):
        names = {p.name for p in self.schema.primitives}
        self.assertIn("CIdentifierSimple", names)

    def test_known_enum_exists(self):
        names = {e.name for e in self.schema.enums}
        self.assertIn("AccessControlEnumSimple", names)

    def test_ar_package_has_identity(self):
        pkg = next(c for c in self.schema.composites if c.name == "ARPackage")
        self.assertGreater(len(pkg.identifiers), 0)

    def test_no_critical_errors(self):
        self.assertLess(len(self.schema.errors), 50,
                        f"Too many errors: {self.schema.errors[:5]}...")

    def test_has_abstract_composites(self):
        abstract = [c for c in self.schema.composites if c.is_abstract]
        self.assertGreater(len(abstract), 100)

    def test_concrete_types_have_inherits_from(self):
        concrete_with_parents = [
            c for c in self.schema.composites
            if not c.is_abstract and c.inherits_from
        ]
        self.assertGreater(len(concrete_with_parents), 500)

    def test_no_massive_member_duplication(self):
        """Concrete types should have only their own members, not inherited ones."""
        for c in self.schema.composites:
            if not c.is_abstract and c.inherits_from:
                self.assertLess(len(c.members), 35,
                                f"{c.name} has {len(c.members)} members — "
                                f"possible flattened inheritance")

    def test_ar_object_is_abstract(self):
        ar_obj = next(c for c in self.schema.composites if c.name == "ARObject")
        self.assertTrue(ar_obj.is_abstract)
        self.assertEqual(len(ar_obj.inherits_from), 0)

    def test_identifiable_hierarchy(self):
        identifiable = next(
            c for c in self.schema.composites if c.name == "Identifiable"
        )
        self.assertTrue(identifiable.is_abstract)
        self.assertEqual(len(identifiable.inherits_from), 1)

    def test_no_self_inheritance(self):
        for c in self.schema.composites:
            self.assertNotIn(c.name, c.inherits_from,
                             f"{c.name} inherits from itself")


@unittest.skipUnless(os.path.exists(SCHEMA_PATH), "AUTOSAR schema not available")
class TestFullConversion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        from schema_parser import parse_schema, export_schema
        from rupa_generator import generate_rupa_files
        cls.output_dir = tempfile.mkdtemp()
        internal = parse_schema(SCHEMA_PATH)
        cls.schema = export_schema(internal)
        generate_rupa_files(cls.schema, cls.output_dir)

    def test_domain_file_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "domain.rupa")))

    def test_primitives_file_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "primitives.rupa")))

    def test_enums_file_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "enums.rupa")))

    def test_mapping_report_exists(self):
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "mapping-report.md")))

    def test_primitives_contain_known_type(self):
        with open(os.path.join(self.output_dir, "primitives.rupa")) as f:
            content = f.read()
        self.assertIn("type CIdentifierSimple = ::string;", content)

    def test_domain_declaration(self):
        with open(os.path.join(self.output_dir, "domain.rupa")) as f:
            content = f.read()
        self.assertIn("domain autosar_r23_11;", content)

    def test_report_has_statistics(self):
        with open(os.path.join(self.output_dir, "mapping-report.md")) as f:
            content = f.read()
        self.assertIn("Primitives:", content)
        self.assertIn("Composites:", content)
        self.assertIn("Abstract:", content)

    def test_abstract_types_file_exists(self):
        self.assertTrue(os.path.exists(
            os.path.join(self.output_dir, "abstract-types.rupa")))

    def test_abstract_types_file_content(self):
        with open(os.path.join(self.output_dir, "abstract-types.rupa")) as f:
            content = f.read()
        self.assertIn("#[abstract]", content)
        self.assertIn("type ARObject = {", content)

    def test_concrete_types_show_inheritance(self):
        """The composites file should have inheritance syntax."""
        composites_path = os.path.join(self.output_dir, "composites.rupa")
        self.assertTrue(os.path.exists(composites_path))
        with open(composites_path) as f:
            content = f.read()
        import re
        self.assertTrue(
            re.search(r'type \w+ = \w+', content),
            "No concrete type with inheritance syntax found in composites.rupa"
        )

    def test_wrapper_types_have_unnamed_role(self):
        """Primitive/enum wrapper types should use '..' unnamed member pattern."""
        composites_path = os.path.join(self.output_dir, "composites.rupa")
        self.assertTrue(os.path.exists(composites_path))
        with open(composites_path) as f:
            content = f.read()
        self.assertIn(".. :", content, "No unnamed member '..' found in composites.rupa")

    def test_identifier_has_id_annotation(self):
        """Identifier wrapper type should have #[id] on unnamed member."""
        # Check both composites.rupa and base-types.rupa (these are base types)
        for fname in ["composites.rupa", "base-types.rupa"]:
            fpath = os.path.join(self.output_dir, fname)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    content = f.read()
                if "type Identifier = " in content or "type CIdentifier = " in content:
                    self.assertIn("#[id]", content)
                    return
        self.fail("No Identifier or CIdentifier type found in generated files")


    # --- Task 7.1: Single composites file ---

    def test_single_composites_file(self):
        """Regular composites should be in a single composites.rupa file."""
        composites_path = os.path.join(self.output_dir, "composites.rupa")
        self.assertTrue(os.path.exists(composites_path))
        # Old split files should NOT exist
        import glob
        splits = glob.glob(os.path.join(self.output_dir, "composites-*-*.rupa"))
        self.assertEqual(len(splits), 0, "Should not have alphabetically split composite files")

    # --- Task 7.2: Import statements ---

    def test_primitives_no_imports(self):
        """primitives.rupa should have no import statements (leaf file)."""
        with open(os.path.join(self.output_dir, "primitives.rupa")) as f:
            content = f.read()
        self.assertNotIn('import "', content)

    def test_enums_no_imports(self):
        """enums.rupa should have no import statements (leaf file)."""
        with open(os.path.join(self.output_dir, "enums.rupa")) as f:
            content = f.read()
        self.assertNotIn('import "', content)

    def test_abstract_types_imports(self):
        """abstract-types.rupa should import primitives and enums."""
        with open(os.path.join(self.output_dir, "abstract-types.rupa")) as f:
            content = f.read()
        self.assertIn('import "primitives.rupa";', content)
        self.assertIn('import "enums.rupa";', content)

    def test_base_types_imports(self):
        """base-types.rupa should import primitives, enums, and abstract-types."""
        with open(os.path.join(self.output_dir, "base-types.rupa")) as f:
            content = f.read()
        self.assertIn('import "primitives.rupa";', content)
        self.assertIn('import "enums.rupa";', content)
        self.assertIn('import "abstract-types.rupa";', content)

    def test_composites_imports(self):
        """composites.rupa should import primitives, enums, abstract-types, base-types."""
        with open(os.path.join(self.output_dir, "composites.rupa")) as f:
            content = f.read()
        self.assertIn('import "primitives.rupa";', content)
        self.assertIn('import "enums.rupa";', content)
        self.assertIn('import "abstract-types.rupa";', content)
        self.assertIn('import "base-types.rupa";', content)

    # --- Task 7.3: Root index.rupa ---

    def test_index_file_exists(self):
        """index.rupa should exist as the compilation entry point."""
        index_path = os.path.join(self.output_dir, "index.rupa")
        self.assertTrue(os.path.exists(index_path))

    def test_index_has_domain(self):
        """index.rupa should have a domain declaration."""
        with open(os.path.join(self.output_dir, "index.rupa")) as f:
            content = f.read()
        self.assertIn("domain autosar_r23_11;", content)

    def test_index_imports_all_sub_files(self):
        """index.rupa should import all generated sub-files."""
        with open(os.path.join(self.output_dir, "index.rupa")) as f:
            content = f.read()
        self.assertIn('import "primitives.rupa";', content)
        self.assertIn('import "enums.rupa";', content)
        self.assertIn('import "abstract-types.rupa";', content)
        self.assertIn('import "base-types.rupa";', content)
        self.assertIn('import "composites.rupa";', content)

    def test_domain_uses_underscores(self):
        """Domain names must use underscores, not hyphens, for lexer compatibility."""
        with open(os.path.join(self.output_dir, "domain.rupa")) as f:
            content = f.read()
        self.assertIn("domain autosar_r23_11;", content)
        self.assertNotIn("domain autosar-r23-11;", content)


if __name__ == "__main__":
    unittest.main()
