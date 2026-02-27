"""SAX-based ARXML anonymizer.

Two-pass approach:
  1. Collect all SHORT-NAME values, build replacement mapping.
  2. Rewrite the ARXML, replacing SHORT-NAME text and reference paths.
"""

from __future__ import annotations

import re
import xml.sax
import xml.sax.handler
from dataclasses import dataclass, field

from name_generator import NameGenerator, detect_case_pattern


WATERMARK_COMMENT = "ANONYMIZED: This file has been anonymized by senda-arxml-anonymizer"


@dataclass
class AnonymizeResult:
    """Result of anonymization including verification."""
    mapping_count: int
    verification_passed: bool
    leaked_names: list[str] = field(default_factory=list)


class ShortNameCollector(xml.sax.handler.ContentHandler):
    """First pass: collect all SHORT-NAME text values."""

    def __init__(self):
        super().__init__()
        self.short_names: set[str] = set()
        self._in_short_name = False
        self._current_text = ""

    def startElement(self, name, attrs):
        if name == "SHORT-NAME":
            self._in_short_name = True
            self._current_text = ""

    def characters(self, content):
        if self._in_short_name:
            self._current_text += content

    def endElement(self, name):
        if name == "SHORT-NAME" and self._in_short_name:
            self._in_short_name = False
            text = self._current_text.strip()
            if text:
                self.short_names.add(text)


class AnonymizingRewriter(xml.sax.handler.ContentHandler):
    """Second pass: rewrite SHORT-NAME values and reference paths."""

    def __init__(self, mapping: dict[str, str], output_file):
        super().__init__()
        self._mapping = mapping
        self._out = output_file
        self._in_short_name = False
        self._in_element = False
        self._current_text = ""
        self._element_name = ""
        self._wrote_watermark = False

    def _write(self, text: str):
        self._out.write(text)

    def _escape(self, text: str) -> str:
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    def _replace_path_segments(self, text: str) -> str:
        """Replace SHORT-NAME segments inside /-delimited reference paths."""
        if "/" not in text:
            return text
        parts = text.split("/")
        replaced = [self._mapping.get(p, p) for p in parts]
        return "/".join(replaced)

    def startDocument(self):
        self._write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self._write(f"<!-- {WATERMARK_COMMENT} -->\n")
        self._wrote_watermark = True

    def startElement(self, name, attrs):
        self._flush_text()
        attr_str = ""
        for aname in attrs.getNames():
            attr_str += f' {aname}="{self._escape(attrs[aname])}"'
        self._write(f"<{name}{attr_str}>")

        if name == "SHORT-NAME":
            self._in_short_name = True
            self._current_text = ""
        else:
            self._in_element = True
            self._element_name = name
            self._current_text = ""

    def characters(self, content):
        self._current_text += content

    def endElement(self, name):
        if name == "SHORT-NAME" and self._in_short_name:
            self._in_short_name = False
            text = self._current_text.strip()
            replaced = self._mapping.get(text, text)
            self._write(self._escape(replaced))
            self._current_text = ""
        else:
            self._flush_text()
        self._in_element = False
        self._write(f"</{name}>")

    def _flush_text(self):
        if self._current_text:
            text = self._current_text
            text = self._replace_path_segments(text)
            self._write(self._escape(text))
            self._current_text = ""

    def ignorableWhitespace(self, content):
        self._write(content)

    def processingInstruction(self, target, data):
        pass  # We emit our own XML declaration in startDocument


def _build_mapping(short_names: set[str], seed: int | None) -> dict[str, str]:
    """Build original->anonymized name mapping."""
    gen = NameGenerator(seed=seed)
    mapping = {}
    for name in sorted(short_names):  # Sort for determinism
        pattern = detect_case_pattern(name)
        mapping[name] = gen.generate(pattern)
    return mapping


def _verify(output_path: str, original_names: set[str], sample_size: int = 50) -> tuple[bool, list[str]]:
    """Spot-check that original names don't appear in the output."""
    import random
    names = sorted(original_names)
    sample = names[:sample_size] if len(names) <= sample_size else random.Random(0).sample(names, sample_size)

    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()

    leaked = [name for name in sample if name in content]
    return len(leaked) == 0, leaked


def anonymize_arxml(
    input_path: str,
    output_path: str,
    seed: int | None = None,
) -> AnonymizeResult:
    """Anonymize an ARXML file."""
    # Pass 1: collect SHORT-NAMEs
    collector = ShortNameCollector()
    xml.sax.parse(input_path, collector)

    # Build mapping
    mapping = _build_mapping(collector.short_names, seed)

    # Pass 2: rewrite
    with open(output_path, "w", encoding="utf-8") as out_file:
        rewriter = AnonymizingRewriter(mapping, out_file)
        xml.sax.parse(input_path, rewriter)

    # Verify
    passed, leaked = _verify(output_path, collector.short_names)

    return AnonymizeResult(
        mapping_count=len(mapping),
        verification_passed=passed,
        leaked_names=leaked,
    )
