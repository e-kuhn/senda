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

            // If next char is '&', coalesce text + entity expansion into one event
            if (pos_ < end_ && *pos_ == '&') {
                entity_buf_.clear();
                entity_buf_.append(text_start, static_cast<size_t>(pos_ - text_start));
                // Fall through to entity collection below
            } else {
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
        }

        if (pos_ >= end_) break;

        if (*pos_ == '&') {
            // Entity in text content — collect text with expansion
            if (entity_buf_.empty()) {
                // No preceding text was collected above
                entity_buf_.clear();
            }
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
