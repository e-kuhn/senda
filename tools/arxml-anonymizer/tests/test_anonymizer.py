import unittest
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anonymizer import anonymize_arxml, WATERMARK_COMMENT

SIMPLE_ARXML = """\
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Signals</SHORT-NAME>
      <ELEMENTS>
        <I-SIGNAL>
          <SHORT-NAME>BrakePedalPosition</SHORT-NAME>
          <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
        </I-SIGNAL>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
"""

ARXML_WITH_REFS = """\
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Signals</SHORT-NAME>
      <ELEMENTS>
        <I-SIGNAL>
          <SHORT-NAME>BrakePedalPosition</SHORT-NAME>
          <INIT-VALUE>/Signals/BrakePedalPosition</INIT-VALUE>
        </I-SIGNAL>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
"""


class TestAnonymizeArxml(unittest.TestCase):
    def _anonymize(self, input_xml: str) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".arxml", delete=False
        ) as inp:
            inp.write(input_xml)
            inp_path = inp.name
        out_path = inp_path + ".anon.arxml"
        try:
            result = anonymize_arxml(inp_path, out_path, seed=42)
            with open(out_path, "r") as f:
                return f.read()
        finally:
            os.unlink(inp_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_short_names_replaced(self):
        output = self._anonymize(SIMPLE_ARXML)
        self.assertNotIn("Signals", output)
        self.assertNotIn("BrakePedalPosition", output)

    def test_xml_structure_preserved(self):
        output = self._anonymize(SIMPLE_ARXML)
        self.assertIn("<SHORT-NAME>", output)
        self.assertIn("<AR-PACKAGE>", output)
        self.assertIn("<I-SIGNAL>", output)

    def test_watermark_present(self):
        output = self._anonymize(SIMPLE_ARXML)
        self.assertIn(WATERMARK_COMMENT, output)

    def test_watermark_in_first_5_lines(self):
        output = self._anonymize(SIMPLE_ARXML)
        first_lines = output.split("\n")[:5]
        found = any(WATERMARK_COMMENT in line for line in first_lines)
        self.assertTrue(found, "Watermark not in first 5 lines")

    def test_reference_paths_updated(self):
        output = self._anonymize(ARXML_WITH_REFS)
        self.assertNotIn("Signals", output)
        self.assertNotIn("BrakePedalPosition", output)
        # The reference path should still have slashes
        self.assertIn("/", output)

    def test_reference_path_consistency(self):
        """SHORT-NAME and reference path use the same replacement."""
        output = self._anonymize(ARXML_WITH_REFS)
        import re
        short_names = re.findall(r"<SHORT-NAME>([^<]+)</SHORT-NAME>", output)
        init_values = re.findall(r"<INIT-VALUE>([^<]+)</INIT-VALUE>", output)
        self.assertEqual(len(init_values), 1)
        path_segments = [s for s in init_values[0].split("/") if s]
        for seg in path_segments:
            self.assertIn(seg, short_names)

    def test_non_short_name_text_preserved(self):
        output = self._anonymize(SIMPLE_ARXML)
        self.assertIn("PRIMITIVE", output)


class TestVerification(unittest.TestCase):
    def test_verification_passes_on_clean_anonymization(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".arxml", delete=False
        ) as inp:
            inp.write(SIMPLE_ARXML)
            inp_path = inp.name
        out_path = inp_path + ".anon.arxml"
        try:
            result = anonymize_arxml(inp_path, out_path, seed=42)
            self.assertTrue(result.verification_passed)
            self.assertEqual(len(result.leaked_names), 0)
        finally:
            os.unlink(inp_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
