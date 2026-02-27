"""ARXML anonymizer using splice-based replacement.

Three-pass approach:
  1. SAX-collect all SHORT-NAME values, build replacement mapping.
  2. Scan the raw bytes for every occurrence of a mapped name, record
     (offset, length, replacement) tuples — the "replacement list".
  3. Serialize by copying original bytes between replacements and
     inserting the watermark.
"""

from __future__ import annotations

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


def _build_aho_corasick(mapping: dict[str, str]) -> tuple[dict, list[str]]:
    """Build an Aho-Corasick automaton from the mapping keys.

    Returns (goto_table, keywords) where goto_table maps
    (state, char) -> next_state, with output and failure links.
    """
    # Use a simple trie + failure links for multi-pattern matching
    goto: list[dict[str, int]] = [{}]  # state 0 = root
    output: list[list[str]] = [[]]      # output[state] = list of matched keywords
    fail: list[int] = [0]

    # Build trie
    for keyword in mapping:
        state = 0
        for ch in keyword:
            if ch not in goto[state]:
                goto[state][ch] = len(goto)
                goto.append({})
                output.append([])
                fail.append(0)
            state = goto[state][ch]
        output[state].append(keyword)

    # Build failure links (BFS)
    from collections import deque
    queue: deque[int] = deque()
    for ch, s in goto[0].items():
        fail[s] = 0
        queue.append(s)

    while queue:
        r = queue.popleft()
        for ch, s in goto[r].items():
            queue.append(s)
            state = fail[r]
            while state != 0 and ch not in goto[state]:
                state = fail[state]
            fail[s] = goto[state].get(ch, 0)
            if fail[s] == s:
                fail[s] = 0
            output[s] = output[s] + output[fail[s]]

    return goto, fail, output


def _build_text_regions(content: str) -> list[tuple[int, int]]:
    """Identify text-content regions (between > and <) in the XML.

    Returns sorted list of (start, end) pairs where replacements are safe.
    Excludes content inside tags, processing instructions, comments, and CDATA.
    """
    regions: list[tuple[int, int]] = []
    i = 0
    n = len(content)
    while i < n:
        if content[i] == '<':
            # Skip past this markup
            if content[i:i+4] == '<!--':
                # Comment body is replaceable (may contain path references)
                body_start = i + 4
                end = content.find('-->', body_start)
                if end >= 0:
                    if end > body_start:
                        regions.append((body_start, end))
                    i = end + 3
                else:
                    i = n
            elif content[i:i+9] == '<![CDATA[':
                # CDATA: skip to ]]>
                end = content.find(']]>', i + 9)
                i = end + 3 if end >= 0 else n
            elif content[i:i+2] == '<?':
                # Processing instruction: skip to ?>
                end = content.find('?>', i + 2)
                i = end + 2 if end >= 0 else n
            else:
                # Regular tag: skip to >
                end = content.find('>', i + 1)
                i = end + 1 if end >= 0 else n
        else:
            # Text content — find extent until next <
            start = i
            end = content.find('<', i)
            if end < 0:
                end = n
            if end > start:
                regions.append((start, end))
            i = end
    return regions


def _find_replacements(
    content: str,
    mapping: dict[str, str],
) -> list[tuple[int, int, str]]:
    """Scan content for all occurrences of mapped names using Aho-Corasick.

    Only replaces within XML text content (between > and <), never inside
    tags, attributes, processing instructions, or comments.

    Returns a sorted, non-overlapping list of (offset, length, replacement).
    Longer matches take priority; on ties, earlier position wins.
    """
    if not mapping:
        return []

    # Build set of safe text regions
    text_regions = _build_text_regions(content)

    goto, fail, output = _build_aho_corasick(mapping)

    # Scan
    raw_matches: list[tuple[int, int, str]] = []  # (start, length, replacement)
    state = 0
    for i, ch in enumerate(content):
        while state != 0 and ch not in goto[state]:
            state = fail[state]
        state = goto[state].get(ch, 0)
        for keyword in output[state]:
            start = i - len(keyword) + 1
            raw_matches.append((start, len(keyword), mapping[keyword]))

    if not raw_matches:
        return []

    # Filter to only matches fully inside text regions
    # Use a pointer into sorted regions for efficient filtering
    region_idx = 0
    filtered: list[tuple[int, int, str]] = []
    raw_matches.sort(key=lambda m: m[0])
    for start, length, replacement in raw_matches:
        end = start + length
        # Advance region pointer past regions that end before this match
        while region_idx < len(text_regions) and text_regions[region_idx][1] <= start:
            region_idx += 1
        # Check if match is fully contained in the current region
        if region_idx < len(text_regions):
            r_start, r_end = text_regions[region_idx]
            if start >= r_start and end <= r_end:
                filtered.append((start, length, replacement))

    if not filtered:
        return []

    # Sort by start position, then longest match first
    filtered.sort(key=lambda m: (m[0], -m[1]))

    # Remove overlaps: greedy left-to-right, prefer longer matches
    result: list[tuple[int, int, str]] = []
    prev_end = 0
    for start, length, replacement in filtered:
        if start >= prev_end:
            result.append((start, length, replacement))
            prev_end = start + length

    return result


def _serialize(
    content: str,
    replacements: list[tuple[int, int, str]],
    output_file,
) -> None:
    """Write content with replacements spliced in and watermark inserted."""
    # Find where to insert watermark (after XML declaration)
    watermark = f"<!-- {WATERMARK_COMMENT} -->\n"
    watermark_offset = -1
    xml_decl_end = content.find("?>")
    if xml_decl_end >= 0:
        # Skip past ?> and any following newline
        watermark_offset = xml_decl_end + 2
        if watermark_offset < len(content) and content[watermark_offset] == '\n':
            watermark_offset += 1

    pos = 0
    watermark_written = False
    for start, length, replacement in replacements:
        # Write watermark if we've passed the insertion point
        if not watermark_written and watermark_offset >= 0 and start >= watermark_offset:
            output_file.write(content[pos:watermark_offset])
            output_file.write(watermark)
            pos = watermark_offset
            watermark_written = True

        # Copy bytes before this replacement
        output_file.write(content[pos:start])
        # Write replacement
        output_file.write(replacement)
        pos = start + length

    # Write watermark if not yet written (no replacements after XML decl)
    if not watermark_written and watermark_offset >= 0:
        output_file.write(content[pos:watermark_offset])
        output_file.write(watermark)
        pos = watermark_offset

    # Write remaining content
    output_file.write(content[pos:])


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
    # Pass 1: SAX-collect SHORT-NAMEs
    collector = ShortNameCollector()
    xml.sax.parse(input_path, collector)

    # Build mapping
    mapping = _build_mapping(collector.short_names, seed)

    # Read entire file
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pass 2: find all replacement locations (Aho-Corasick scan)
    replacements = _find_replacements(content, mapping)

    # Pass 3: serialize with replacements spliced in
    with open(output_path, "w", encoding="utf-8") as out_file:
        _serialize(content, replacements, out_file)

    # Verify
    passed, leaked = _verify(output_path, collector.short_names)

    return AnonymizeResult(
        mapping_count=len(mapping),
        verification_passed=passed,
        leaked_names=leaked,
    )
