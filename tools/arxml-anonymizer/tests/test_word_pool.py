# tools/arxml-anonymizer/tests/test_word_pool.py
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from word_pool import ANIMALS, TREES, RIVERS, MINERALS, ALL_WORDS


class TestWordPool(unittest.TestCase):
    def test_pool_has_at_least_200_words(self):
        self.assertGreaterEqual(len(ALL_WORDS), 200)

    def test_no_duplicates(self):
        self.assertEqual(len(ALL_WORDS), len(set(ALL_WORDS)))

    def test_all_words_are_lowercase_alpha(self):
        for w in ALL_WORDS:
            self.assertTrue(w.isalpha(), f"'{w}' is not purely alphabetic")
            self.assertTrue(w.islower(), f"'{w}' is not lowercase")

    def test_categories_non_empty(self):
        for cat in (ANIMALS, TREES, RIVERS, MINERALS):
            self.assertGreater(len(cat), 10)


if __name__ == "__main__":
    unittest.main()
