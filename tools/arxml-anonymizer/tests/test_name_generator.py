import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from name_generator import detect_case_pattern, CasePattern, NameGenerator


class TestDetectCasePattern(unittest.TestCase):
    def test_camel_case(self):
        self.assertEqual(detect_case_pattern("BrakePedalPosition"), CasePattern.CAMEL)

    def test_upper_snake(self):
        self.assertEqual(detect_case_pattern("BRAKE_PEDAL_POS"), CasePattern.UPPER_SNAKE)

    def test_lower_snake(self):
        self.assertEqual(detect_case_pattern("brake_pedal_pos"), CasePattern.LOWER_SNAKE)

    def test_plain_lower(self):
        self.assertEqual(detect_case_pattern("signals"), CasePattern.PLAIN)

    def test_plain_upper(self):
        self.assertEqual(detect_case_pattern("AUTOSAR"), CasePattern.UPPER_SNAKE)

    def test_single_word_capitalized(self):
        self.assertEqual(detect_case_pattern("Signals"), CasePattern.CAMEL)


class TestNameGenerator(unittest.TestCase):
    def test_unique_names(self):
        gen = NameGenerator(seed=42)
        names = {gen.generate(CasePattern.CAMEL) for _ in range(100)}
        self.assertEqual(len(names), 100)

    def test_camel_case_output(self):
        gen = NameGenerator(seed=42)
        name = gen.generate(CasePattern.CAMEL)
        self.assertFalse("_" in name)
        self.assertTrue(name[0].isupper())

    def test_upper_snake_output(self):
        gen = NameGenerator(seed=42)
        name = gen.generate(CasePattern.UPPER_SNAKE)
        self.assertEqual(name, name.upper())
        self.assertIn("_", name)

    def test_lower_snake_output(self):
        gen = NameGenerator(seed=42)
        name = gen.generate(CasePattern.LOWER_SNAKE)
        self.assertEqual(name, name.lower())
        self.assertIn("_", name)

    def test_plain_output(self):
        gen = NameGenerator(seed=42)
        name = gen.generate(CasePattern.PLAIN)
        self.assertEqual(name, name.lower())
        self.assertFalse("_" in name)

    def test_deterministic_with_same_seed(self):
        gen1 = NameGenerator(seed=42)
        gen2 = NameGenerator(seed=42)
        for _ in range(10):
            self.assertEqual(
                gen1.generate(CasePattern.CAMEL),
                gen2.generate(CasePattern.CAMEL),
            )


if __name__ == "__main__":
    unittest.main()
