#pragma once

#include <cstdint>
#include <string>
#include <string_view>

#include "xml_simd_kernels.h"

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
    /// Namespace prefix is stripped (e.g. "AR:AUTOSAR" -> "AUTOSAR").
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

    // --- SIMD-accelerated scanning (delegates to xml_simd_kernels) ---
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

    // Entity expansion
    bool expand_entity(const char* p, uint32_t len, std::string& out, uint32_t& consumed);

    // Error helper
    XmlEvent error(const char* msg);

    // Line counting helper (count newlines in range)
    void count_lines(const char* from, const char* to);
};

}  // namespace senda
