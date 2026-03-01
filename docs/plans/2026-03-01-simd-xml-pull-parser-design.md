# SIMD XML Pull Parser for ARXML Compiler

**Date:** 2026-03-01
**Status:** Implemented
**Goal:** Replace libexpat with a custom SIMD-accelerated XML pull parser to maximize ARXML compilation throughput, approaching memory bandwidth limits.

## Results

| File | Size | Expat Baseline | SIMD Pull Parser | Speedup |
|------|------|---------------|------------------|---------|
| R20-11 | 49MB | 280ms | 105ms | **2.7x** |
| R4.3.1 | 240MB | 1.40s | 510ms | **2.7x** |

Throughput: ~470 MB/s (R4.3.1, 240MB in 510ms). Benchmarked on Apple M4 Pro, release build.

## Context

The ARXML compiler (`src/compiler-arxml/senda.compiler-arxml.cppm`) currently uses libexpat as a SAX push parser. File content is mmap'd and fed to expat in a single call. Post-optimization baseline (PR #29): 280ms for 49MB R20-11, 1.40s for 240MB R4.3.1 (release build, Apple M4 Pro).

Expat's limitations:
- Push model: callback overhead, no ability to skip subtrees
- Internal buffering despite mmap'd input (copies data internally)
- Byte-at-a-time state machine (~100-200 MB/s throughput ceiling)
- No SIMD acceleration

## Design

### Pull Parser API

```cpp
enum class XmlEvent { StartElement, EndElement, Characters, Eof, Error };

class XmlPullParser {
public:
    explicit XmlPullParser(std::string_view input);

    XmlEvent next();                     // advance to next event

    std::string_view tag() const;        // element name (ns prefix stripped)
    std::string_view text() const;       // text content (entity-expanded when needed)

    bool next_attr();                    // advance to next attribute (lazy)
    std::string_view attr_name() const;
    std::string_view attr_value() const;

    uint32_t line() const;
    const char* error_message() const;
};
```

Key API choices:
- `tag()` returns a view into the mmap'd buffer. Namespace prefix stripped by advancing past `:`.
- `text()` returns a view into the buffer when no entities present (common case). When `&` found, expands into a side buffer.
- Attribute iteration is lazy — parser doesn't scan attributes until `next_attr()` is called. Unread attributes are skipped for free on the next `next()` call.
- No allocation. The parser is a cursor over the mmap'd buffer.

### SIMD Kernels

File: `src/compiler-arxml/xml_simd_kernels.h/cpp`
Pattern: identical to `external/rupa/src/lexer/simd_kernels.h/cpp` (Highway dynamic dispatch, scalar tails)

**Kernel 1: `simd_find_tag_or_amp(data, len)` — THE hot path**

Scans text content for `<` (0x3C) or `&` (0x26). Most bytes in ARXML are text between tags. Uses Lemire's 64-byte block technique: four 16-byte loads, `cmpeq` for both targets, OR, combine masks into 64-bit word. If zero, advance 64 bytes. Otherwise `ctz` gives position.

Expected: ~10-30 GB/s (memory-bandwidth bound on M4 Pro with 128-bit NEON).

**Kernel 2: `simd_skip_whitespace(data, len)`**

Count leading whitespace (space, tab, newline, carriage return). Same pattern as Rupa's `simd_count_leading_whitespace`.

**Kernel 3: `simd_scan_name(data, len)`**

Scan XML name characters `[a-zA-Z0-9_:.-]`. Returns length of name. Uses `vpshufb` dual-nibble classification: two 16-byte lookup tables, AND result. Non-zero = name character. Scan blocks until non-name byte found.

**Kernel 4: `simd_find_quote_end(data, len, quote_char)`**

Scan attribute values for closing quote (`"` or `'`). Also detects `&` for entity expansion within attribute values.

**Kernel 5: `simd_find_colon(data, len)`**

Namespace prefix detection. Single-character scan for `:` within element names.

### Parser State Machine

```
INIT → skip XML declaration, skip leading whitespace

SCAN_CONTENT (main loop):
  simd_find_tag_or_amp()
  → '<': TAG_OPEN
  → '&': expand entity, emit Characters
  → EOF: emit Eof

TAG_OPEN:
  → '</': scan close tag name, emit EndElement → SCAN_CONTENT
  → '<!': scan comment (scalar, rare) → SCAN_CONTENT
  → else: scan open tag name, emit StartElement → ATTR_SCAN

ATTR_SCAN (parked state between StartElement events):
  On next_attr(): simd_skip_ws, scan attr name, skip '=', scan quoted value
  On next(): skip remaining attrs, find '>' or '/>' → SCAN_CONTENT
  '/>': also emit EndElement
```

### Entity Expansion

- Side buffer (`std::string entity_buf_`) used only when `&` encountered in text
- Common case (no `&`): `text()` returns zero-copy view into mmap'd buffer
- When `&` found: copy content to `entity_buf_`, expanding entities inline
- 5 XML entities only: `&lt;` → `<`, `&gt;` → `>`, `&amp;` → `&`, `&quot;` → `"`, `&apos;` → `'`
- Numeric character references (`&#NNN;`, `&#xHHH;`) not needed for ARXML (not observed in test data)

### SIMD Subtree Skipping

When the ARXML compiler encounters an unknown element, it currently pushes a Skip frame and tracks depth through expat callbacks — expat still fully parses all content, attributes, and text inside the skipped subtree.

With the pull parser, `skip_subtree()`:
1. Set depth = 1
2. Use `simd_find_tag_or_amp()` to jump to each `<`
3. If `</`: depth-- (if 0, consume close tag, done)
4. If `<X` (not `<!`, not `<?`): check for self-closing `/>`, else depth++
5. All text, attributes, entities between tags are skipped entirely

This is a major win for files with many unknown elements (R4.3.1 with R20-11 domain previously had 1,030 skips before PR #28).

### Integration with ArxmlCompiler

Replace expat push callbacks with pull loop:

```cpp
// Current (expat push):
XML_SetElementHandler(parser, on_start_element, on_end_element);
XML_SetCharacterDataHandler(parser, on_characters);
XML_Parse(parser, content.data(), content.size(), XML_TRUE);

// New (pull parser):
XmlPullParser xml(content);
while (true) {
    auto event = xml.next();
    switch (event) {
    case XmlEvent::StartElement:
        handle_start(state, xml.tag(), xml);  // xml passed for lazy attr access
        break;
    case XmlEvent::EndElement:
        handle_end(state, xml.tag());
        break;
    case XmlEvent::Characters:
        handle_text(state, xml.text());
        break;
    case XmlEvent::Eof: goto done;
    case XmlEvent::Error:
        diags.add(/* error from xml.error_message() */);
        goto done;
    }
}
```

The existing `on_start_element` / `on_end_element` / `on_characters` logic is reorganized from static callbacks into the switch body. `ParseState` struct stays the same.

## ARXML XML Feature Audit

Verified against 49MB R20-11 and 240MB R4.3.1 test files:

| Feature | Used? | Count | Notes |
|---------|-------|-------|-------|
| Entity refs (`&lt;` `&gt;` `&amp;`) | Yes | ~240 | Must expand |
| `&quot;` `&apos;` | No | 0 | Support anyway |
| Numeric char refs (`&#NNN;`) | No | 0 | Not needed |
| CDATA sections | No | 0 | Not needed |
| Processing instructions | No | 0 | Not needed |
| DTD / DOCTYPE | No | 0 | Not needed |
| Comments | Rare | 1 | Scalar handling |
| Namespaces (default + xsi) | Yes | 2 | Strip prefix |
| Mixed content (schema) | Yes | 35 types | `mixed="true"` in XSD |
| Attributes | Heavy | 193k+ | DEST, L, GID, UUID, T |
| UTF-8 with non-ASCII | Yes | — | German umlauts in docs |
| Long lines | Yes | up to 2,789 chars | — |

## Files

| File | Purpose |
|------|---------|
| `src/compiler-arxml/xml_pull_parser.h` | XmlPullParser class |
| `src/compiler-arxml/xml_pull_parser.cpp` | Parser state machine implementation |
| `src/compiler-arxml/xml_simd_kernels.h` | SIMD kernel declarations |
| `src/compiler-arxml/xml_simd_kernels.cpp` | Highway SIMD kernel implementations |
| `src/compiler-arxml/senda.compiler-arxml.cppm` | Modified: pull loop replaces expat callbacks |
| `src/compiler-arxml/CMakeLists.txt` | Modified: remove expat, add Highway, add new sources |
| `CMakeLists.txt` | Modified: remove expat FetchContent, add Highway |

## Testing Strategy

- Validate both test files produce identical FIR output (object count, reference count, diagnostic messages)
- Existing `test/compiler-arxml/arxml-compiler-test.cpp` as regression suite
- Compare `senda` CLI output before/after for both files
- Benchmark: `time ./build-release/senda <file>` for both files, compare to 280ms/1.40s baseline

## Prior Art

- **simdjson**: structural indexing via vpshufb dual-nibble classification — technique applies to XML character classification
- **Parabix (Cameron et al.)**: parallel bit stream transposition for XML, ~1 cycle/byte lexical scanning
- **pugixml**: table-driven in-situ parsing, ~300-500 MB/s
- **RapidXML**: null-terminating in-situ, ~500-800 MB/s
- **Lemire (2024)**: SIMD HTML scanning at 33 GB/s on M2 via 64-byte block scan
- **TurboXml (.NET)**: SAX + SIMD, 10-30% gains
- **Rupa lexer**: existing Highway SIMD kernels — direct pattern to follow
