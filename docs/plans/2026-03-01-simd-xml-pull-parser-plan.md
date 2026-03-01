# SIMD XML Pull Parser Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace libexpat with a custom SIMD-accelerated XML pull parser to maximize ARXML compilation throughput.

**Architecture:** A standalone `XmlPullParser` class provides a cursor-based pull API over mmap'd XML input, yielding events (StartElement, EndElement, Characters, Eof). SIMD kernels (Google Highway) accelerate the hot scanning loops. The ArxmlCompiler switches from expat push callbacks to a pull loop.

**Tech Stack:** C++26, Google Highway 1.2.0 (SIMD), CMake 3.28+, Google Test, Clang 21.1.8

**Design doc:** `docs/plans/2026-03-01-simd-xml-pull-parser-design.md`

---

## Batch 1: Standalone Pull Parser (Scalar)

Build the `XmlPullParser` with scalar code, tested independently against fixture files. This is the highest-risk batch — XML parsing correctness. No SIMD, no ArxmlCompiler changes.

### Task 1: Pull Parser Header

**Files:**
- Create: `src/compiler-arxml/xml_pull_parser.h`

**Step 1: Write the header**

```cpp
#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace senda {

enum class XmlEvent {
    StartElement,
    EndElement,
    Characters,
    Eof,
    Error,
};

class XmlPullParser {
public:
    explicit XmlPullParser(std::string_view input);

    /// Advance to the next event.
    XmlEvent next();

    /// Element tag name (valid after StartElement/EndElement).
    /// Namespace prefix is stripped (e.g. "AR:AUTOSAR" → "AUTOSAR").
    std::string_view tag() const { return tag_; }

    /// Text content (valid after Characters).
    /// Zero-copy view into input when no entities present.
    /// Entity-expanded into side buffer when '&' found.
    std::string_view text() const { return text_; }

    /// Advance to the next attribute (valid between StartElement and next next() call).
    /// Returns false when no more attributes.
    bool next_attr();

    /// Current attribute name (valid after next_attr() returns true).
    std::string_view attr_name() const { return attr_name_; }

    /// Current attribute value (valid after next_attr() returns true).
    std::string_view attr_value() const { return attr_value_; }

    /// Current line number (1-based).
    uint32_t line() const { return line_; }

    /// Error message (valid after Error event).
    const char* error_message() const { return error_msg_; }

    /// Skip the current element's entire subtree.
    /// Valid after StartElement — skips to the matching EndElement.
    /// The EndElement is consumed; next next() returns the event after it.
    void skip_subtree();

private:
    // Input buffer
    const char* data_;
    const char* end_;
    const char* pos_;

    // Current event data
    std::string_view tag_;
    std::string_view text_;
    std::string_view attr_name_;
    std::string_view attr_value_;

    // Entity expansion side buffer
    std::string entity_buf_;

    // Attribute scanning state
    const char* attr_pos_;     // position within tag for lazy attr scanning
    const char* attr_end_;     // end of opening tag (the '>' position)
    bool attrs_consumed_;      // true after all attrs scanned or next() called

    // Line tracking
    uint32_t line_ = 1;

    // Error state
    const char* error_msg_ = nullptr;

    // --- Internal scanning ---
    // These are scalar for now; Batch 2 replaces them with SIMD.
    uint32_t find_tag_or_amp(const char* p, uint32_t len) const;
    uint32_t skip_whitespace(const char* p, uint32_t len) const;
    uint32_t scan_name(const char* p, uint32_t len) const;
    uint32_t find_quote_end(const char* p, uint32_t len, char quote) const;

    // Entity expansion
    bool expand_entity(const char* p, uint32_t len, std::string& out, uint32_t& consumed);

    // Error helper
    XmlEvent error(const char* msg);

    // Line counting helper (count newlines in range)
    void count_lines(const char* from, const char* to);
};

}  // namespace senda
```

**Step 2: Commit**

```bash
git add src/compiler-arxml/xml_pull_parser.h
git commit -m "feat(arxml): add XmlPullParser header with pull API"
```

### Task 2: Pull Parser Implementation — Core

**Files:**
- Create: `src/compiler-arxml/xml_pull_parser.cpp`

**Step 1: Write the implementation**

Reference: `docs/plans/2026-03-01-simd-xml-pull-parser-design.md` for the state machine.

The implementation must handle:
- XML declaration: `<?xml ... ?>` — skip it
- Open tags: `<NAME ...>` — emit StartElement, park for lazy attr scanning
- Close tags: `</NAME>` — emit EndElement
- Self-closing tags: `<NAME ... />` — emit StartElement then EndElement on next call
- Text content: everything between `>` and `<` — emit Characters (skip whitespace-only)
- Entity expansion: `&lt;` `&gt;` `&amp;` `&quot;` `&apos;` — expand into side buffer
- Comments: `<!-- ... -->` — skip entirely
- Namespace prefix stripping: find `:` in tag name, return suffix
- Line tracking: count `\n` in scanned ranges

Key implementation details:
- `next()` drives the state machine. After StartElement, it parks at `attr_pos_` (the position after the tag name). On the next `next()` call, it skips past remaining attributes to find `>` or `/>`.
- `next_attr()` scans one attribute at a time from `attr_pos_`, advancing it.
- `skip_subtree()` uses depth counting to jump past the entire subtree without parsing text/attrs.
- `find_tag_or_amp()` is the hot inner loop — scan for `<` or `&` byte-by-byte (scalar for now).
- `text()` returns a view into the input buffer when no `&` found. When `&` found, copies to `entity_buf_` with expansion and returns a view into that.

```cpp
#include "xml_pull_parser.h"
#include <cstring>

namespace senda {

XmlPullParser::XmlPullParser(std::string_view input)
    : data_(input.data()),
      end_(input.data() + input.size()),
      pos_(input.data()),
      attr_pos_(nullptr),
      attr_end_(nullptr),
      attrs_consumed_(true)
{
    // Skip BOM if present
    if (input.size() >= 3 &&
        static_cast<uint8_t>(input[0]) == 0xEF &&
        static_cast<uint8_t>(input[1]) == 0xBB &&
        static_cast<uint8_t>(input[2]) == 0xBF) {
        pos_ += 3;
    }

    // Skip XML declaration: <?xml ... ?>
    auto ws = skip_whitespace(pos_, static_cast<uint32_t>(end_ - pos_));
    count_lines(pos_, pos_ + ws);
    pos_ += ws;

    if (end_ - pos_ >= 5 && std::memcmp(pos_, "<?xml", 5) == 0) {
        auto* q = pos_ + 5;
        while (q < end_ - 1) {
            if (*q == '\n') line_++;
            if (q[0] == '?' && q[1] == '>') { pos_ = q + 2; break; }
            q++;
        }
    }
}

XmlEvent XmlPullParser::error(const char* msg) {
    error_msg_ = msg;
    return XmlEvent::Error;
}

void XmlPullParser::count_lines(const char* from, const char* to) {
    for (auto* p = from; p < to; ++p) {
        if (*p == '\n') line_++;
    }
}

// --- Scalar scanning (replaced by SIMD in Batch 2) ---

uint32_t XmlPullParser::find_tag_or_amp(const char* p, uint32_t len) const {
    for (uint32_t i = 0; i < len; ++i) {
        if (p[i] == '<' || p[i] == '&') return i;
    }
    return len;
}

uint32_t XmlPullParser::skip_whitespace(const char* p, uint32_t len) const {
    uint32_t i = 0;
    while (i < len && (p[i] == ' ' || p[i] == '\t' || p[i] == '\n' || p[i] == '\r')) ++i;
    return i;
}

uint32_t XmlPullParser::scan_name(const char* p, uint32_t len) const {
    uint32_t i = 0;
    while (i < len) {
        auto c = static_cast<unsigned char>(p[i]);
        // XML NameChar: letters, digits, '.', '-', '_', ':', plus >0x7F for Unicode
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' ||
            c == '.' || c == ':' || c > 0x7F) {
            ++i;
        } else {
            break;
        }
    }
    return i;
}

uint32_t XmlPullParser::find_quote_end(const char* p, uint32_t len, char quote) const {
    for (uint32_t i = 0; i < len; ++i) {
        if (p[i] == quote) return i;
    }
    return len;
}

bool XmlPullParser::expand_entity(const char* p, uint32_t len,
                                   std::string& out, uint32_t& consumed) {
    // p points to character after '&'
    if (len >= 3 && p[0] == 'l' && p[1] == 't' && p[2] == ';') {
        out += '<'; consumed = 3; return true;
    }
    if (len >= 3 && p[0] == 'g' && p[1] == 't' && p[2] == ';') {
        out += '>'; consumed = 3; return true;
    }
    if (len >= 4 && p[0] == 'a' && p[1] == 'm' && p[2] == 'p' && p[3] == ';') {
        out += '&'; consumed = 4; return true;
    }
    if (len >= 5 && p[0] == 'q' && p[1] == 'u' && p[2] == 'o' && p[3] == 't' && p[4] == ';') {
        out += '"'; consumed = 5; return true;
    }
    if (len >= 5 && p[0] == 'a' && p[1] == 'p' && p[2] == 'o' && p[3] == 's' && p[4] == ';') {
        out += '\''; consumed = 5; return true;
    }
    // Numeric character reference: &#NNN; or &#xHHH;
    if (len >= 3 && p[0] == '#') {
        const char* start = p + 1;
        const char* end_p = p + len;
        bool hex = false;
        if (*start == 'x' || *start == 'X') { hex = true; start++; }
        uint32_t codepoint = 0;
        const char* s = start;
        while (s < end_p && *s != ';') {
            if (hex) {
                if (*s >= '0' && *s <= '9') codepoint = codepoint * 16 + (*s - '0');
                else if (*s >= 'a' && *s <= 'f') codepoint = codepoint * 16 + (*s - 'a' + 10);
                else if (*s >= 'A' && *s <= 'F') codepoint = codepoint * 16 + (*s - 'A' + 10);
                else return false;
            } else {
                if (*s >= '0' && *s <= '9') codepoint = codepoint * 10 + (*s - '0');
                else return false;
            }
            s++;
        }
        if (s < end_p && *s == ';') {
            // Encode as UTF-8
            if (codepoint <= 0x7F) {
                out += static_cast<char>(codepoint);
            } else if (codepoint <= 0x7FF) {
                out += static_cast<char>(0xC0 | (codepoint >> 6));
                out += static_cast<char>(0x80 | (codepoint & 0x3F));
            } else if (codepoint <= 0xFFFF) {
                out += static_cast<char>(0xE0 | (codepoint >> 12));
                out += static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F));
                out += static_cast<char>(0x80 | (codepoint & 0x3F));
            } else if (codepoint <= 0x10FFFF) {
                out += static_cast<char>(0xF0 | (codepoint >> 18));
                out += static_cast<char>(0x80 | ((codepoint >> 12) & 0x3F));
                out += static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F));
                out += static_cast<char>(0x80 | (codepoint & 0x3F));
            }
            consumed = static_cast<uint32_t>(s - p + 1);
            return true;
        }
    }
    return false;
}

XmlEvent XmlPullParser::next() {
    // If we were parked in an opening tag (attrs not consumed), skip to '>'
    if (!attrs_consumed_) {
        // Scan forward to find '>' or '/>'
        auto* p = attr_pos_;
        bool self_closing = false;
        while (p < end_) {
            if (*p == '"' || *p == '\'') {
                // Skip quoted attribute value
                char q = *p++;
                while (p < end_ && *p != q) {
                    if (*p == '\n') line_++;
                    p++;
                }
                if (p < end_) p++;  // skip closing quote
            } else {
                if (*p == '\n') line_++;
                if (*p == '/') { self_closing = true; p++; continue; }
                if (*p == '>') { p++; break; }
                p++;
            }
        }
        pos_ = p;
        attrs_consumed_ = true;

        // If self-closing, emit EndElement
        if (self_closing) {
            return XmlEvent::EndElement;
        }
    }

    // Main scanning loop
    while (pos_ < end_) {
        auto remaining = static_cast<uint32_t>(end_ - pos_);
        auto offset = find_tag_or_amp(pos_, remaining);

        // Text content before the structural character
        if (offset > 0) {
            auto* text_start = pos_;
            count_lines(pos_, pos_ + offset);
            pos_ += offset;

            // Check if text is whitespace-only
            bool all_ws = true;
            for (auto* c = text_start; c < pos_; ++c) {
                if (*c != ' ' && *c != '\t' && *c != '\n' && *c != '\r') {
                    all_ws = false;
                    break;
                }
            }
            if (!all_ws) {
                text_ = std::string_view(text_start, static_cast<size_t>(pos_ - text_start));
                return XmlEvent::Characters;
            }
            continue;
        }

        if (pos_ >= end_) break;

        if (*pos_ == '&') {
            // Entity in text content — need to collect text with expansion
            entity_buf_.clear();
            auto* text_start = pos_;
            while (pos_ < end_ && *pos_ != '<') {
                if (*pos_ == '&') {
                    pos_++;
                    uint32_t consumed = 0;
                    if (!expand_entity(pos_, static_cast<uint32_t>(end_ - pos_),
                                       entity_buf_, consumed)) {
                        return error("invalid entity reference");
                    }
                    pos_ += consumed;
                } else {
                    if (*pos_ == '\n') line_++;
                    entity_buf_ += *pos_++;
                }
            }
            if (!entity_buf_.empty()) {
                text_ = entity_buf_;
                return XmlEvent::Characters;
            }
            continue;
        }

        // *pos_ == '<'
        pos_++;
        if (pos_ >= end_) return error("unexpected end of input after '<'");

        if (*pos_ == '/') {
            // Close tag: </NAME>
            pos_++;
            auto name_len = scan_name(pos_, static_cast<uint32_t>(end_ - pos_));
            if (name_len == 0) return error("expected element name after '</'");
            auto* name_start = pos_;
            pos_ += name_len;

            // Strip namespace prefix
            std::string_view full_name(name_start, name_len);
            if (auto colon = full_name.find(':'); colon != std::string_view::npos) {
                tag_ = full_name.substr(colon + 1);
            } else {
                tag_ = full_name;
            }

            // Skip whitespace and '>'
            auto ws = skip_whitespace(pos_, static_cast<uint32_t>(end_ - pos_));
            count_lines(pos_, pos_ + ws);
            pos_ += ws;
            if (pos_ < end_ && *pos_ == '>') pos_++;
            else return error("expected '>' in close tag");

            return XmlEvent::EndElement;
        }

        if (*pos_ == '!') {
            // Comment: <!-- ... -->
            if (end_ - pos_ >= 3 && pos_[1] == '-' && pos_[2] == '-') {
                pos_ += 3;
                while (pos_ < end_ - 2) {
                    if (*pos_ == '\n') line_++;
                    if (pos_[0] == '-' && pos_[1] == '-' && pos_[2] == '>') {
                        pos_ += 3;
                        break;
                    }
                    pos_++;
                }
                continue;  // Skip comments, don't emit events
            }
            // Other <! constructs (DOCTYPE, CDATA) — skip to '>'
            while (pos_ < end_ && *pos_ != '>') {
                if (*pos_ == '\n') line_++;
                pos_++;
            }
            if (pos_ < end_) pos_++;
            continue;
        }

        if (*pos_ == '?') {
            // Processing instruction: <? ... ?>
            pos_++;
            while (pos_ < end_ - 1) {
                if (*pos_ == '\n') line_++;
                if (pos_[0] == '?' && pos_[1] == '>') { pos_ += 2; break; }
                pos_++;
            }
            continue;
        }

        // Open tag: <NAME ...>
        auto name_len = scan_name(pos_, static_cast<uint32_t>(end_ - pos_));
        if (name_len == 0) return error("expected element name after '<'");
        auto* name_start = pos_;
        pos_ += name_len;

        // Strip namespace prefix
        std::string_view full_name(name_start, name_len);
        if (auto colon = full_name.find(':'); colon != std::string_view::npos) {
            tag_ = full_name.substr(colon + 1);
        } else {
            tag_ = full_name;
        }

        // Park for lazy attribute scanning
        attr_pos_ = pos_;
        attrs_consumed_ = false;

        // Find the end of the opening tag to set attr_end_
        // (We need to scan ahead to know if it's self-closing)
        // But we defer this — attr_end_ is found lazily.
        attr_end_ = nullptr;

        return XmlEvent::StartElement;
    }

    return XmlEvent::Eof;
}

bool XmlPullParser::next_attr() {
    if (attrs_consumed_) return false;

    auto* p = attr_pos_;

    // Skip whitespace
    while (p < end_ && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')) {
        if (*p == '\n') line_++;
        p++;
    }

    // Check for end of tag
    if (p >= end_ || *p == '>' || *p == '/') {
        attr_pos_ = p;
        return false;
    }

    // Scan attribute name
    auto* name_start = p;
    auto name_len = scan_name(p, static_cast<uint32_t>(end_ - p));
    if (name_len == 0) {
        attr_pos_ = p;
        return false;
    }
    p += name_len;

    // Strip namespace prefix from attribute name
    std::string_view full_attr(name_start, name_len);
    if (auto colon = full_attr.find(':'); colon != std::string_view::npos) {
        attr_name_ = full_attr.substr(colon + 1);
    } else {
        attr_name_ = full_attr;
    }

    // Skip whitespace, '=', whitespace
    while (p < end_ && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')) {
        if (*p == '\n') line_++;
        p++;
    }
    if (p < end_ && *p == '=') p++;
    while (p < end_ && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')) {
        if (*p == '\n') line_++;
        p++;
    }

    // Scan quoted value
    if (p >= end_ || (*p != '"' && *p != '\'')) {
        attr_pos_ = p;
        return false;
    }
    char quote = *p++;
    auto* val_start = p;
    auto val_len = find_quote_end(p, static_cast<uint32_t>(end_ - p), quote);
    attr_value_ = std::string_view(val_start, val_len);
    p += val_len;
    if (p < end_) p++;  // skip closing quote

    attr_pos_ = p;
    return true;
}

void XmlPullParser::skip_subtree() {
    // Skip remaining attributes to get past the opening tag
    if (!attrs_consumed_) {
        auto* p = attr_pos_;
        while (p < end_) {
            if (*p == '"' || *p == '\'') {
                char q = *p++;
                while (p < end_ && *p != q) {
                    if (*p == '\n') line_++;
                    p++;
                }
                if (p < end_) p++;
            } else {
                if (*p == '\n') line_++;
                if (*p == '/' && p + 1 < end_ && p[1] == '>') {
                    // Self-closing — no subtree to skip
                    pos_ = p + 2;
                    attrs_consumed_ = true;
                    return;
                }
                if (*p == '>') { p++; break; }
                p++;
            }
        }
        pos_ = p;
        attrs_consumed_ = true;
    }

    // Now skip content by depth-counting '<' and '</':
    int depth = 1;
    while (pos_ < end_ && depth > 0) {
        // Fast scan for next '<'
        auto remaining = static_cast<uint32_t>(end_ - pos_);
        auto offset = find_tag_or_amp(pos_, remaining);
        count_lines(pos_, pos_ + offset);
        pos_ += offset;

        if (pos_ >= end_) break;
        if (*pos_ == '&') { pos_++; continue; }  // skip entities

        // *pos_ == '<'
        pos_++;
        if (pos_ >= end_) break;

        if (*pos_ == '/') {
            // Close tag
            depth--;
            if (depth == 0) {
                // Consume the close tag: </NAME>
                pos_++;
                auto name_len = scan_name(pos_, static_cast<uint32_t>(end_ - pos_));
                pos_ += name_len;
                auto ws = skip_whitespace(pos_, static_cast<uint32_t>(end_ - pos_));
                count_lines(pos_, pos_ + ws);
                pos_ += ws;
                if (pos_ < end_ && *pos_ == '>') pos_++;
                return;
            }
            // Skip past close tag
            while (pos_ < end_ && *pos_ != '>') {
                if (*pos_ == '\n') line_++;
                pos_++;
            }
            if (pos_ < end_) pos_++;
        } else if (*pos_ == '!') {
            // Comment — skip
            if (end_ - pos_ >= 3 && pos_[1] == '-' && pos_[2] == '-') {
                pos_ += 3;
                while (pos_ < end_ - 2) {
                    if (*pos_ == '\n') line_++;
                    if (pos_[0] == '-' && pos_[1] == '-' && pos_[2] == '>') {
                        pos_ += 3; break;
                    }
                    pos_++;
                }
            } else {
                while (pos_ < end_ && *pos_ != '>') {
                    if (*pos_ == '\n') line_++;
                    pos_++;
                }
                if (pos_ < end_) pos_++;
            }
        } else if (*pos_ == '?') {
            // PI — skip
            pos_++;
            while (pos_ < end_ - 1) {
                if (*pos_ == '\n') line_++;
                if (pos_[0] == '?' && pos_[1] == '>') { pos_ += 2; break; }
                pos_++;
            }
        } else {
            // Open tag — check for self-closing
            while (pos_ < end_) {
                if (*pos_ == '"' || *pos_ == '\'') {
                    char q = *pos_++;
                    while (pos_ < end_ && *pos_ != q) {
                        if (*pos_ == '\n') line_++;
                        pos_++;
                    }
                    if (pos_ < end_) pos_++;
                } else if (*pos_ == '/') {
                    if (pos_ + 1 < end_ && pos_[1] == '>') {
                        pos_ += 2;
                        // Self-closing doesn't change depth
                        break;
                    }
                    pos_++;
                } else if (*pos_ == '>') {
                    pos_++;
                    depth++;
                    break;
                } else {
                    if (*pos_ == '\n') line_++;
                    pos_++;
                }
            }
        }
    }
}

}  // namespace senda
```

**Step 2: Commit**

```bash
git add src/compiler-arxml/xml_pull_parser.cpp
git commit -m "feat(arxml): implement scalar XmlPullParser state machine"
```

### Task 3: Pull Parser Unit Tests

**Files:**
- Create: `test/compiler-arxml/xml-pull-parser-test.cpp`
- Modify: `test/compiler-arxml/CMakeLists.txt`
- Create: `test/compiler-arxml/fixtures/entities.arxml`
- Create: `test/compiler-arxml/fixtures/with-comments.arxml`
- Create: `test/compiler-arxml/fixtures/self-closing.arxml`
- Create: `test/compiler-arxml/fixtures/namespace-prefix.arxml`

**Step 1: Create test fixtures**

`test/compiler-arxml/fixtures/entities.arxml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Test</SHORT-NAME>
      <ELEMENTS>
        <I-SIGNAL>
          <SHORT-NAME>Sig1</SHORT-NAME>
          <DESC>Offset &gt; 0 &amp; Offset &lt; 100</DESC>
        </I-SIGNAL>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
```

`test/compiler-arxml/fixtures/with-comments.arxml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- This file has comments -->
<AUTOSAR>
  <AR-PACKAGES>
    <!-- A package -->
    <AR-PACKAGE>
      <SHORT-NAME>Pkg</SHORT-NAME>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
```

`test/compiler-arxml/fixtures/self-closing.arxml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Pkg</SHORT-NAME>
      <ELEMENTS>
        <I-SIGNAL>
          <SHORT-NAME>Sig1</SHORT-NAME>
          <EMPTY-PROP/>
        </I-SIGNAL>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
```

`test/compiler-arxml/fixtures/namespace-prefix.arxml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<AR:AUTOSAR xmlns:AR="http://autosar.org/schema/r4.0"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://autosar.org/schema/r4.0 AUTOSAR_00052.xsd">
  <AR:AR-PACKAGES>
    <AR:AR-PACKAGE>
      <AR:SHORT-NAME>Pkg</AR:SHORT-NAME>
    </AR:AR-PACKAGE>
  </AR:AR-PACKAGES>
</AR:AUTOSAR>
```

**Step 2: Write the test file**

`test/compiler-arxml/xml-pull-parser-test.cpp`:
```cpp
#include <gtest/gtest.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include "xml_pull_parser.h"

namespace fs = std::filesystem;

static std::string read_file(const fs::path& path) {
    std::ifstream f(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}

static fs::path fixture_path(const char* name) {
    return fs::path(SENDA_TEST_FIXTURES_DIR) / name;
}

// --- Basic event sequence tests ---

TEST(XmlPullParserTest, EmptyInput) {
    senda::XmlPullParser p("");
    EXPECT_EQ(p.next(), senda::XmlEvent::Eof);
}

TEST(XmlPullParserTest, MinimalDocument) {
    senda::XmlPullParser p("<root></root>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "root");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "root");
    EXPECT_EQ(p.next(), senda::XmlEvent::Eof);
}

TEST(XmlPullParserTest, TextContent) {
    senda::XmlPullParser p("<a>hello</a>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "hello");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "a");
}

TEST(XmlPullParserTest, NestedElements) {
    senda::XmlPullParser p("<a><b><c>text</c></b></a>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "b");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "c");
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "text");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "c");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "b");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::Eof);
}

TEST(XmlPullParserTest, SelfClosingTag) {
    senda::XmlPullParser p("<a><b/></a>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "b");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "b");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::Eof);
}

// --- Attribute tests ---

TEST(XmlPullParserTest, Attributes) {
    senda::XmlPullParser p(R"(<a x="1" y="hello">text</a>)");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");

    EXPECT_TRUE(p.next_attr());
    EXPECT_EQ(p.attr_name(), "x");
    EXPECT_EQ(p.attr_value(), "1");

    EXPECT_TRUE(p.next_attr());
    EXPECT_EQ(p.attr_name(), "y");
    EXPECT_EQ(p.attr_value(), "hello");

    EXPECT_FALSE(p.next_attr());

    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "text");
}

TEST(XmlPullParserTest, SkippedAttributes) {
    // Don't call next_attr() — attributes should be skipped on next next() call
    senda::XmlPullParser p(R"(<a x="1" y="2">text</a>)");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    // Skip attributes, go directly to content
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "text");
}

TEST(XmlPullParserTest, SelfClosingWithAttributes) {
    senda::XmlPullParser p(R"(<a x="1"/>)");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_TRUE(p.next_attr());
    EXPECT_EQ(p.attr_name(), "x");
    EXPECT_EQ(p.attr_value(), "1");
    EXPECT_FALSE(p.next_attr());
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::Eof);
}

// --- Entity expansion tests ---

TEST(XmlPullParserTest, EntityExpansion) {
    senda::XmlPullParser p("<a>&lt;&gt;&amp;&quot;&apos;</a>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "<>&\"'");
}

TEST(XmlPullParserTest, MixedTextAndEntities) {
    senda::XmlPullParser p("<a>Offset &gt; 0 &amp; Offset &lt; 100</a>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "Offset > 0 & Offset < 100");
}

// --- Namespace prefix stripping ---

TEST(XmlPullParserTest, NamespacePrefixStripped) {
    senda::XmlPullParser p("<AR:AUTOSAR><AR:SHORT-NAME>x</AR:SHORT-NAME></AR:AUTOSAR>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "AUTOSAR");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "SHORT-NAME");
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "x");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "SHORT-NAME");
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.tag(), "AUTOSAR");
}

// --- Comment handling ---

TEST(XmlPullParserTest, CommentsSkipped) {
    senda::XmlPullParser p("<!-- comment --><a>text</a>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "text");
}

// --- XML declaration ---

TEST(XmlPullParserTest, XmlDeclarationSkipped) {
    senda::XmlPullParser p("<?xml version=\"1.0\" encoding=\"UTF-8\"?><a/>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
}

// --- skip_subtree ---

TEST(XmlPullParserTest, SkipSubtree) {
    senda::XmlPullParser p("<a><b><c>deep</c><d/></b><e>after</e></a>");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "b");
    p.skip_subtree();  // skip everything inside <b>
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "e");
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    EXPECT_EQ(p.text(), "after");
}

TEST(XmlPullParserTest, SkipSelfClosing) {
    senda::XmlPullParser p(R"(<a><b x="1"/><c>text</c></a>)");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "a");
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "b");
    p.skip_subtree();  // self-closing — skip is immediate
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "c");
}

// --- Line tracking ---

TEST(XmlPullParserTest, LineTracking) {
    senda::XmlPullParser p("<a>\n  <b>\n    text\n  </b>\n</a>");
    EXPECT_EQ(p.line(), 1u);
    p.next();  // StartElement a
    EXPECT_EQ(p.line(), 1u);
    p.next();  // StartElement b
    EXPECT_GE(p.line(), 2u);
}

// --- Fixture file tests ---

TEST(XmlPullParserTest, SimpleSignalFixture) {
    auto content = read_file(fixture_path("simple-signal.arxml"));
    senda::XmlPullParser p(content);

    // Count events
    int start_count = 0, end_count = 0, text_count = 0;
    while (true) {
        auto e = p.next();
        if (e == senda::XmlEvent::Eof) break;
        if (e == senda::XmlEvent::Error) { FAIL() << p.error_message(); break; }
        if (e == senda::XmlEvent::StartElement) start_count++;
        if (e == senda::XmlEvent::EndElement) end_count++;
        if (e == senda::XmlEvent::Characters) text_count++;
    }
    EXPECT_EQ(start_count, end_count);  // balanced
    EXPECT_GT(start_count, 0);
    EXPECT_GT(text_count, 0);
}

TEST(XmlPullParserTest, EntitiesFixture) {
    auto content = read_file(fixture_path("entities.arxml"));
    senda::XmlPullParser p(content);

    // Walk to the DESC element's text
    bool found_desc = false;
    while (true) {
        auto e = p.next();
        if (e == senda::XmlEvent::Eof) break;
        if (e == senda::XmlEvent::Error) { FAIL() << p.error_message(); break; }
        if (e == senda::XmlEvent::StartElement && p.tag() == "DESC") {
            // Next should be Characters with expanded entities
            e = p.next();
            EXPECT_EQ(e, senda::XmlEvent::Characters);
            EXPECT_EQ(p.text(), "Offset > 0 & Offset < 100");
            found_desc = true;
            break;
        }
    }
    EXPECT_TRUE(found_desc);
}

TEST(XmlPullParserTest, NamespacePrefixFixture) {
    auto content = read_file(fixture_path("namespace-prefix.arxml"));
    senda::XmlPullParser p(content);

    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.tag(), "AUTOSAR");  // AR:AUTOSAR → AUTOSAR

    // Can read attributes (schemaLocation etc.)
    bool found_schema = false;
    while (p.next_attr()) {
        if (p.attr_name() == "schemaLocation") {
            found_schema = true;
            EXPECT_NE(p.attr_value().find("AUTOSAR_00052.xsd"), std::string_view::npos);
        }
    }
    EXPECT_TRUE(found_schema);
}
```

**Step 3: Update test CMakeLists.txt**

Add to `test/compiler-arxml/CMakeLists.txt`:

```cmake
# XmlPullParser unit tests
add_executable(senda.xml_pull_parser_test xml-pull-parser-test.cpp)
target_link_libraries(senda.xml_pull_parser_test PRIVATE
    senda.compiler.arxml
    GTest::gtest_main
)
target_include_directories(senda.xml_pull_parser_test PRIVATE
    ${CMAKE_SOURCE_DIR}/src/compiler-arxml
)
target_compile_definitions(senda.xml_pull_parser_test PRIVATE
    SENDA_TEST_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
)
target_compile_features(senda.xml_pull_parser_test PUBLIC cxx_std_26)
senda_target_settings(senda.xml_pull_parser_test)
add_test(NAME senda.xml_pull_parser_test COMMAND senda.xml_pull_parser_test)
```

**Step 4: Update compiler-arxml CMakeLists.txt to include new sources**

The `xml_pull_parser.cpp` needs to be compiled as part of the library. Since it's a plain `.cpp` file (not a module), add it as a PRIVATE source. Also add the include directory so the header is findable.

Modify `src/compiler-arxml/CMakeLists.txt` to:

```cmake
add_library(senda.compiler.arxml)
target_sources(senda.compiler.arxml
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.compiler-arxml.cppm
    PRIVATE
        xml_pull_parser.cpp
)
target_include_directories(senda.compiler.arxml PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(senda.compiler.arxml
    PUBLIC rupa.compiler rupa.fir.builder rupa.domain rupa.fir kore senda.domains rupa.diagnostics
    PRIVATE expat
)
target_compile_features(senda.compiler.arxml PUBLIC cxx_std_26)
senda_target_settings(senda.compiler.arxml)
```

Note: expat stays for now — the ArxmlCompiler still uses it. We remove it in Batch 3.

**Step 5: Build and run tests**

```bash
cmake --build --preset debug 2>&1 | tail -20
./build-debug/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: All tests pass.

**Step 6: Run existing ARXML compiler tests to verify no regression**

```bash
./build-debug/test/compiler-arxml/senda.arxml_compiler_test
```

Expected: All existing tests still pass.

**Step 7: Commit**

```bash
git add test/compiler-arxml/xml-pull-parser-test.cpp \
        test/compiler-arxml/CMakeLists.txt \
        test/compiler-arxml/fixtures/entities.arxml \
        test/compiler-arxml/fixtures/with-comments.arxml \
        test/compiler-arxml/fixtures/self-closing.arxml \
        test/compiler-arxml/fixtures/namespace-prefix.arxml \
        src/compiler-arxml/CMakeLists.txt
git commit -m "test(arxml): add XmlPullParser unit tests with fixture files"
```

---

## Batch 2: SIMD Kernels

Add Highway SIMD kernels and integrate them into the pull parser, replacing scalar scanning functions.

### Task 4: SIMD Kernel Implementation

**Files:**
- Create: `src/compiler-arxml/xml_simd_kernels.h`
- Create: `src/compiler-arxml/xml_simd_kernels.cpp`

**Step 1: Write the kernel header**

`src/compiler-arxml/xml_simd_kernels.h` — follows exact same pattern as `external/rupa/src/lexer/simd_kernels.h`:

```cpp
// xml_simd_kernels — SIMD-accelerated XML scanning kernels via Google Highway.
//
// Separate translation unit because Highway's dynamic dispatch macros
// are incompatible with C++ module semantics.
#pragma once

#include <cstdint>

namespace senda::xml {

// Find first '<' or '&' byte. Returns offset from data[0], or len if not found.
uint32_t simd_find_tag_or_amp(const char* data, uint32_t len);

// Count leading whitespace bytes (space, \t, \n, \r).
// Returns number of whitespace bytes.
uint32_t simd_skip_whitespace(const char* data, uint32_t len);

// Scan XML name characters [a-zA-Z0-9_:.\-] plus >0x7F for Unicode.
// Returns length of the name (number of consecutive name characters).
uint32_t simd_scan_name(const char* data, uint32_t len);

// Find first occurrence of quote_char ('"' or '\'') or '&'.
// Returns offset from data[0], or len if not found.
// When the returned position holds '&', caller knows entity expansion is needed.
uint32_t simd_find_quote_or_amp(const char* data, uint32_t len, char quote_char);

}  // namespace senda::xml
```

**Step 2: Write the kernel implementation**

`src/compiler-arxml/xml_simd_kernels.cpp`:

```cpp
#include "xml_simd_kernels.h"

#undef HWY_TARGET_INCLUDE
#define HWY_TARGET_INCLUDE "xml_simd_kernels.cpp"
#include <hwy/foreach_target.h>
#include <hwy/highway.h>

HWY_BEFORE_NAMESPACE();
namespace senda::xml::HWY_NAMESPACE {

namespace hn = hwy::HWY_NAMESPACE;

uint32_t FindTagOrAmp(const char* data, uint32_t len) {
    const hn::ScalableTag<uint8_t> d;
    const size_t N = hn::Lanes(d);
    uint32_t pos = 0;

    const auto v_lt  = hn::Set(d, '<');
    const auto v_amp = hn::Set(d, '&');

    while (pos + N <= len) {
        const auto v = hn::LoadU(d, reinterpret_cast<const uint8_t*>(data + pos));
        const auto hit = hn::Or(hn::Eq(v, v_lt), hn::Eq(v, v_amp));
        if (!hn::AllFalse(d, hit)) {
            auto idx = hn::FindFirstTrue(d, hit);
            return pos + static_cast<uint32_t>(idx);
        }
        pos += static_cast<uint32_t>(N);
    }

    // Scalar tail
    while (pos < len) {
        if (data[pos] == '<' || data[pos] == '&') return pos;
        pos++;
    }
    return len;
}

uint32_t SkipWhitespace(const char* data, uint32_t len) {
    const hn::ScalableTag<uint8_t> d;
    const size_t N = hn::Lanes(d);
    uint32_t pos = 0;

    const auto v_space = hn::Set(d, ' ');
    const auto v_tab   = hn::Set(d, '\t');
    const auto v_lf    = hn::Set(d, '\n');
    const auto v_cr    = hn::Set(d, '\r');

    while (pos + N <= len) {
        const auto v = hn::LoadU(d, reinterpret_cast<const uint8_t*>(data + pos));
        const auto is_ws = hn::Or(hn::Or(hn::Eq(v, v_space), hn::Eq(v, v_tab)),
                                  hn::Or(hn::Eq(v, v_lf), hn::Eq(v, v_cr)));
        if (hn::AllTrue(d, is_ws)) {
            pos += static_cast<uint32_t>(N);
        } else {
            const auto not_ws = hn::Not(is_ws);
            auto idx = hn::FindFirstTrue(d, not_ws);
            return pos + static_cast<uint32_t>(idx);
        }
    }

    // Scalar tail
    while (pos < len) {
        auto c = static_cast<unsigned char>(data[pos]);
        if (c != ' ' && c != '\t' && c != '\n' && c != '\r') break;
        pos++;
    }
    return pos;
}

uint32_t ScanName(const char* data, uint32_t len) {
    // XML NameChar: [a-zA-Z0-9_:.\-] plus bytes > 0x7F for Unicode.
    // We use a range-check approach: a byte is a name char if it's in one
    // of these ranges or is > 0x7F.
    //
    // Strategy: check (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
    //           (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' ||
    //           c == ':' || c > 0x7F
    //
    // With SIMD we do: name_char = (c in ranges) OR (c > 0x7F)
    // Non-name stops the scan.

    const hn::ScalableTag<uint8_t> d;
    const size_t N = hn::Lanes(d);
    uint32_t pos = 0;

    const auto v_a   = hn::Set(d, 'a');
    const auto v_z   = hn::Set(d, 'z');
    const auto v_A   = hn::Set(d, 'A');
    const auto v_Z   = hn::Set(d, 'Z');
    const auto v_0   = hn::Set(d, '0');
    const auto v_9   = hn::Set(d, '9');
    const auto v_hyp = hn::Set(d, '-');
    const auto v_und = hn::Set(d, '_');
    const auto v_dot = hn::Set(d, '.');
    const auto v_col = hn::Set(d, ':');
    const auto v_7f  = hn::Set(d, 0x7F);

    while (pos + N <= len) {
        const auto v = hn::LoadU(d, reinterpret_cast<const uint8_t*>(data + pos));

        // Range checks: c >= low && c <= high  ↔  (c - low) <= (high - low) for unsigned
        const auto in_az = hn::And(hn::Ge(v, v_a), hn::Le(v, v_z));
        const auto in_AZ = hn::And(hn::Ge(v, v_A), hn::Le(v, v_Z));
        const auto in_09 = hn::And(hn::Ge(v, v_0), hn::Le(v, v_9));

        const auto is_special = hn::Or(
            hn::Or(hn::Eq(v, v_hyp), hn::Eq(v, v_und)),
            hn::Or(hn::Eq(v, v_dot), hn::Eq(v, v_col)));

        const auto is_unicode = hn::Gt(v, v_7f);

        const auto is_name = hn::Or(
            hn::Or(hn::Or(in_az, in_AZ), hn::Or(in_09, is_special)),
            is_unicode);

        if (hn::AllTrue(d, is_name)) {
            pos += static_cast<uint32_t>(N);
        } else {
            const auto not_name = hn::Not(is_name);
            auto idx = hn::FindFirstTrue(d, not_name);
            return pos + static_cast<uint32_t>(idx);
        }
    }

    // Scalar tail
    while (pos < len) {
        auto c = static_cast<unsigned char>(data[pos]);
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' ||
            c == '.' || c == ':' || c > 0x7F) {
            pos++;
        } else {
            break;
        }
    }
    return pos;
}

uint32_t FindQuoteOrAmp(const char* data, uint32_t len, char quote_char) {
    const hn::ScalableTag<uint8_t> d;
    const size_t N = hn::Lanes(d);
    uint32_t pos = 0;

    const auto v_quote = hn::Set(d, static_cast<uint8_t>(quote_char));
    const auto v_amp   = hn::Set(d, '&');

    while (pos + N <= len) {
        const auto v = hn::LoadU(d, reinterpret_cast<const uint8_t*>(data + pos));
        const auto hit = hn::Or(hn::Eq(v, v_quote), hn::Eq(v, v_amp));
        if (!hn::AllFalse(d, hit)) {
            auto idx = hn::FindFirstTrue(d, hit);
            return pos + static_cast<uint32_t>(idx);
        }
        pos += static_cast<uint32_t>(N);
    }

    // Scalar tail
    while (pos < len) {
        if (data[pos] == quote_char || data[pos] == '&') return pos;
        pos++;
    }
    return len;
}

}  // namespace senda::xml::HWY_NAMESPACE
HWY_AFTER_NAMESPACE();

#if HWY_ONCE
namespace senda::xml {

HWY_EXPORT(FindTagOrAmp);
HWY_EXPORT(SkipWhitespace);
HWY_EXPORT(ScanName);
HWY_EXPORT(FindQuoteOrAmp);

uint32_t simd_find_tag_or_amp(const char* data, uint32_t len) {
    return HWY_DYNAMIC_DISPATCH(FindTagOrAmp)(data, len);
}

uint32_t simd_skip_whitespace(const char* data, uint32_t len) {
    return HWY_DYNAMIC_DISPATCH(SkipWhitespace)(data, len);
}

uint32_t simd_scan_name(const char* data, uint32_t len) {
    return HWY_DYNAMIC_DISPATCH(ScanName)(data, len);
}

uint32_t simd_find_quote_or_amp(const char* data, uint32_t len, char quote_char) {
    return HWY_DYNAMIC_DISPATCH(FindQuoteOrAmp)(data, len, quote_char);
}

}  // namespace senda::xml
#endif
```

**Step 3: Update compiler-arxml CMakeLists.txt**

Add the SIMD kernel source and link Highway:

```cmake
add_library(senda.compiler.arxml)
target_sources(senda.compiler.arxml
    PUBLIC FILE_SET CXX_MODULES FILES
        senda.compiler-arxml.cppm
    PRIVATE
        xml_pull_parser.cpp
        xml_simd_kernels.cpp
)
target_include_directories(senda.compiler.arxml PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(senda.compiler.arxml
    PUBLIC rupa.compiler rupa.fir.builder rupa.domain rupa.fir kore senda.domains rupa.diagnostics
    PRIVATE expat hwy
)
target_compile_features(senda.compiler.arxml PUBLIC cxx_std_26)
senda_target_settings(senda.compiler.arxml)
```

**Step 4: Build and verify**

```bash
cmake --build --preset debug 2>&1 | tail -20
```

Expected: Compiles without errors. SIMD kernels aren't called yet — just compiled.

**Step 5: Commit**

```bash
git add src/compiler-arxml/xml_simd_kernels.h \
        src/compiler-arxml/xml_simd_kernels.cpp \
        src/compiler-arxml/CMakeLists.txt
git commit -m "feat(arxml): add Highway SIMD kernels for XML scanning"
```

### Task 5: Wire SIMD Kernels into Pull Parser

**Files:**
- Modify: `src/compiler-arxml/xml_pull_parser.h`
- Modify: `src/compiler-arxml/xml_pull_parser.cpp`

**Step 1: Replace scalar methods with SIMD calls**

In `xml_pull_parser.h`, add the include and change the private scanning methods to call the SIMD kernels:

Replace the four private method declarations:
```cpp
    uint32_t find_tag_or_amp(const char* p, uint32_t len) const;
    uint32_t skip_whitespace(const char* p, uint32_t len) const;
    uint32_t scan_name(const char* p, uint32_t len) const;
    uint32_t find_quote_end(const char* p, uint32_t len, char quote) const;
```

With inline wrappers that delegate to the SIMD kernels:

```cpp
#include "xml_simd_kernels.h"

// In private section:
    static uint32_t find_tag_or_amp(const char* p, uint32_t len) {
        return senda::xml::simd_find_tag_or_amp(p, len);
    }
    static uint32_t skip_whitespace(const char* p, uint32_t len) {
        return senda::xml::simd_skip_whitespace(p, len);
    }
    static uint32_t scan_name(const char* p, uint32_t len) {
        return senda::xml::simd_scan_name(p, len);
    }
    static uint32_t find_quote_end(const char* p, uint32_t len, char quote) {
        return senda::xml::simd_find_quote_or_amp(p, len, quote);
    }
```

In `xml_pull_parser.cpp`, remove the four scalar method implementations (they're now inline in the header).

**Step 2: Build and run tests**

```bash
cmake --build --preset debug 2>&1 | tail -20
./build-debug/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: All pull parser tests still pass — SIMD kernels produce identical results to scalar.

**Step 3: Commit**

```bash
git add src/compiler-arxml/xml_pull_parser.h src/compiler-arxml/xml_pull_parser.cpp
git commit -m "feat(arxml): wire SIMD kernels into XmlPullParser"
```

---

## Batch 3: ArxmlCompiler Integration

Replace expat push callbacks with the pull parser loop. This is the critical integration step.

### Task 6: Rewrite ArxmlCompiler::compile() to Use Pull Parser

**Files:**
- Modify: `src/compiler-arxml/senda.compiler-arxml.cppm`

**Step 1: Add include and rewrite compile()**

At the top of the module fragment (after `#include <expat.h>` — which we'll remove in Task 7), add:

```cpp
#include "xml_pull_parser.h"
```

Replace the body of `ArxmlCompiler::compile()`. The key changes:
1. Replace `XML_Parser` creation + callbacks + `XML_Parse()` with `XmlPullParser` + pull loop
2. `on_start_element` logic moves inline into the `StartElement` case
3. `on_end_element` logic moves inline into the `EndElement` case
4. `on_characters` logic moves inline into the `Characters` case
5. The `static` callbacks and `XMLCALL` signatures are removed
6. For the AUTOSAR root element, use `xml.next_attr()` to lazily scan for `xsi:schemaLocation`
7. For Skip frames, call `xml.skip_subtree()` instead of incrementing depth

The `ParseState` struct, `Frame`, `FrameKind`, `PathKey` all stay the same.

Rewrite the `compile()` method body:

```cpp
rupa::compiler::CompileResult compile(
    const std::filesystem::path& path,
    rupa::compiler::CompileContext& context) override
{
    rupa::compiler::Diagnostics diags;

    if (!std::filesystem::exists(path)) {
        diags.add({rupa::compiler::Severity::Error,
                   "cannot open file: " + path.string(),
                   {path.string(), 0, 0}});
        return rupa::compiler::CompileResult(
            fir::Fir{}, rupa::compiler::DomainExtensions{}, std::move(diags));
    }
    rupa::diagnostics::SourceFile source(path);
    auto content = source.view();

    fir::Fir fir;
    rupa::fir_builder::FirBuilder builder(fir);

    ParseState state{
        .registry = registry_,
        .default_domain = default_domain_,
        .builder = builder,
        .diags = diags,
        .file_path = path.string(),
        .stack = {},
        .context = &context,
        .max_skip_warnings = max_skip_warnings_,
        .current_path_key = {},
        .current_path_ids = {},
        .path_index = {},
        .text_buf = {},
    };

    XmlPullParser xml(content);

    while (true) {
        auto event = xml.next();
        if (event == XmlEvent::Eof) break;
        if (event == XmlEvent::Error) {
            diags.add({rupa::compiler::Severity::Error,
                       std::string("XML parse error: ") + xml.error_message()
                           + " at line " + std::to_string(xml.line()),
                       {path.string(), xml.line(), 0}});
            break;
        }
        if (state.abort_parse) break;

        switch (event) {
        case XmlEvent::StartElement:
            handle_start_element(state, xml);
            break;
        case XmlEvent::EndElement:
            handle_end_element(state);
            break;
        case XmlEvent::Characters:
            handle_characters(state, xml.text());
            break;
        default:
            break;
        }
    }

    resolve_references(state, fir);

    if (state.skip_total_count > state.skip_warning_emitted) {
        int remaining = state.skip_total_count - state.skip_warning_emitted;
        diags.add({rupa::compiler::Severity::Warning,
            std::to_string(remaining) + " additional elements skipped",
            {path.string(), 0, 0}});
    }

    return rupa::compiler::CompileResult(
        std::move(fir), rupa::compiler::DomainExtensions{}, std::move(diags));
}
```

The three handler methods replace the three `static XMLCALL` callbacks. They contain the same logic but take a `XmlPullParser&` instead of raw `const XML_Char*` pointers:

```cpp
static void handle_start_element(ParseState& state, XmlPullParser& xml) {
    auto tag = xml.tag();

    // On AUTOSAR root element, resolve domain from schema
    if (tag == "AUTOSAR" && !state.domain_resolved) {
        state.domain_resolved = true;

        // Lazy attr scan for xsi:schemaLocation
        std::string_view schema_location;
        while (xml.next_attr()) {
            auto name = xml.attr_name();
            if (name == "schemaLocation") {
                schema_location = xml.attr_value();
                break;
            }
        }

        // ... rest of domain resolution logic (same as current on_start_element) ...
    }

    // Skip frame handling
    if (!state.stack.empty() && state.stack.back().kind == FrameKind::Skip) {
        state.stack.back().skip_depth++;
        return;
    }

    // Type lookup, role lookup, etc. — same logic as current on_start_element
    // but using 'tag' instead of extracting from raw XML_Char*
    // ...
}

static void handle_end_element(ParseState& state) {
    // Same logic as current on_end_element but without XML_Char* parameter
    // (tag is already available on the stack frame or from xml.tag())
    // ...
}

static void handle_characters(ParseState& state, std::string_view text) {
    if (state.stack.empty()) return;
    auto& frame = state.stack.back();
    if (frame.kind == FrameKind::Property) {
        if (frame.text_len == 0) {
            frame.text_start = static_cast<uint32_t>(state.text_buf.size());
        }
        state.text_buf.append(text.data(), text.size());
        frame.text_len += static_cast<uint32_t>(text.size());
    }
}
```

Important: The `handle_start_element` and `handle_end_element` methods should preserve the exact same logic as the existing `on_start_element` and `on_end_element` callbacks. The only changes are:
- `std::string_view tag` is obtained from `xml.tag()` instead of parsing `const XML_Char* name`
- Namespace prefix stripping is handled by the pull parser (already done)
- Attribute access uses `xml.next_attr()` instead of `const XML_Char** attrs` array
- Skip frames can use `xml.skip_subtree()` for better performance (optional optimization — can be done as a follow-up)

**Step 2: Build and run ALL tests**

```bash
cmake --build --preset debug 2>&1 | tail -20
./build-debug/test/compiler-arxml/senda.arxml_compiler_test
./build-debug/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: All tests pass. The ARXML compiler tests are the critical regression check.

**Step 3: Test with real ARXML files**

```bash
cmake --preset release && cmake --build --preset release
./build-release/senda test/data/arxml/vehicle-comms-r20-11.arxml 2>&1
./build-release/senda --domain autosar-r20-11 test/data/arxml/vehicle-platform-r4-3-1.arxml 2>&1
```

Expected: Same object counts, reference counts, and diagnostic messages as the expat-based version. Verify output matches the known baselines:
- R20-11: 46k objects, 34,162 refs resolved, 0 skips
- R4.3.1 (R20-11 domain): 249k objects, 194,854 refs resolved, 3 skips

**Step 4: Commit**

```bash
git add src/compiler-arxml/senda.compiler-arxml.cppm
git commit -m "feat(arxml): replace expat callbacks with XmlPullParser pull loop"
```

### Task 7: Remove Expat Dependency

**Files:**
- Modify: `src/compiler-arxml/senda.compiler-arxml.cppm` — remove `#include <expat.h>`
- Modify: `src/compiler-arxml/CMakeLists.txt` — remove `expat` from link libraries
- Modify: `CMakeLists.txt` — remove expat FetchContent block

**Step 1: Remove expat include from compiler module**

In `src/compiler-arxml/senda.compiler-arxml.cppm`, remove:
```cpp
#include <expat.h>
```

Also remove any remaining `XML_*` type references, `XMLCALL` declarations, and the static callback functions (`on_start_element`, `on_end_element`, `on_characters`).

**Step 2: Remove expat from compiler-arxml CMakeLists.txt**

Change `PRIVATE expat hwy` to `PRIVATE hwy`:

```cmake
target_link_libraries(senda.compiler.arxml
    PUBLIC rupa.compiler rupa.fir.builder rupa.domain rupa.fir kore senda.domains rupa.diagnostics
    PRIVATE hwy
)
```

**Step 3: Remove expat FetchContent from root CMakeLists.txt**

Remove lines 30-44 (the entire expat block):
```cmake
# expat (SAX XML parser for ARXML compiler — replaces pugixml)
FetchContent_Declare(
    expat
    ...
)
...
FetchContent_MakeAvailable(expat)
```

**Step 4: Build and run tests**

```bash
cmake --preset debug && cmake --build --preset debug 2>&1 | tail -20
./build-debug/test/compiler-arxml/senda.arxml_compiler_test
./build-debug/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: Clean build with no expat references. All tests pass.

**Step 5: Commit**

```bash
git add src/compiler-arxml/senda.compiler-arxml.cppm \
        src/compiler-arxml/CMakeLists.txt \
        CMakeLists.txt
git commit -m "refactor(arxml): remove libexpat dependency"
```

---

## Batch 4: Benchmark & Validation

### Task 8: Benchmark Against Baseline

**Step 1: Build release and time both test files**

```bash
cmake --preset release && cmake --build --preset release

# R20-11 (baseline: 280ms)
time ./build-release/senda test/data/arxml/vehicle-comms-r20-11.arxml

# R4.3.1 (baseline: 1.40s)
time ./build-release/senda --domain autosar-r20-11 test/data/arxml/vehicle-platform-r4-3-1.arxml
```

**Step 2: Validate output correctness**

Compare object counts, reference counts, skip counts, and diagnostic messages against known baselines.

**Step 3: Record results**

Document benchmark results in the commit message and update the design doc with actual performance numbers.

**Step 4: Commit**

```bash
git add docs/plans/2026-03-01-simd-xml-pull-parser-design.md
git commit -m "perf(arxml): benchmark SIMD pull parser — record results"
```

### Task 9: Set Up Optimization Campaign (Optional)

If further tuning is desired, set up an optimization campaign using the evolutionary-optimization infrastructure:

**Step 1: Create campaign directory**

```bash
mkdir -p docs/optimization/arxml-simd-parser
```

**Step 2: Create config.json**

```json
{
    "name": "arxml-simd-parser",
    "description": "SIMD XML pull parser performance for ARXML compilation",
    "source_paths": [
        "src/compiler-arxml/xml_pull_parser.cpp",
        "src/compiler-arxml/xml_simd_kernels.cpp",
        "src/compiler-arxml/senda.compiler-arxml.cppm"
    ],
    "test_command": "cmake --build --preset debug && ./build-debug/test/compiler-arxml/senda.arxml_compiler_test && ./build-debug/test/compiler-arxml/senda.xml_pull_parser_test",
    "benchmark_command": "cmake --build --preset release && time ./build-release/senda test/data/arxml/vehicle-comms-r20-11.arxml 2>&1",
    "baseline_file": "test/data/arxml/vehicle-comms-r20-11.arxml"
}
```

**Step 3: Commit**

```bash
git add docs/optimization/arxml-simd-parser/
git commit -m "chore(arxml): set up SIMD parser optimization campaign"
```

---

## Summary

| Batch | Tasks | Risk | Description |
|-------|-------|------|-------------|
| 1 | 1-3 | High | Standalone pull parser (scalar) with full test suite |
| 2 | 4-5 | Medium | SIMD kernels + wire into parser |
| 3 | 6-7 | High | ArxmlCompiler integration + expat removal |
| 4 | 8-9 | Low | Benchmark + optional campaign setup |

Each batch is independently completable and committable. The riskiest work (XML parsing correctness) is isolated in Batch 1 with its own test suite before touching the ARXML compiler.
