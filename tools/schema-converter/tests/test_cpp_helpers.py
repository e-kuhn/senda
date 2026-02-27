import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cpp_helpers import (
    multiplicity_str, safe_var, type_var, prim_var, role_var, domain_name,
    CPP_KEYWORDS,
)


class TestMultiplicity(unittest.TestCase):
    def test_one(self):
        self.assertEqual(multiplicity_str(1, 1), "fir::Multiplicity::One")

    def test_optional(self):
        self.assertEqual(multiplicity_str(0, 1), "fir::Multiplicity::Optional")

    def test_many(self):
        self.assertEqual(multiplicity_str(0, None), "fir::Multiplicity::Many")

    def test_one_or_more(self):
        self.assertEqual(multiplicity_str(1, None), "fir::Multiplicity::OneOrMore")


class TestNaming(unittest.TestCase):
    def test_safe_var_keyword(self):
        self.assertEqual(safe_var("class"), "class_")

    def test_safe_var_non_keyword(self):
        self.assertEqual(safe_var("signal"), "signal")

    def test_type_var(self):
        self.assertEqual(type_var("ISignal"), "i_signal")

    def test_prim_var(self):
        self.assertEqual(prim_var("StringSimple"), "string_simple_t")

    def test_role_var(self):
        self.assertEqual(role_var("i_signal", 0), "i_signal_r0")

    def test_domain_name(self):
        self.assertEqual(domain_name("R23-11"), "autosar-r23-11")


if __name__ == "__main__":
    unittest.main()
