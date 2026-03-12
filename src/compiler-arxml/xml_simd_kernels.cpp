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
    // Strategy: a byte is NOT a name char if it's in the ASCII range (<=0x7F)
    // and doesn't match any of the name character sets.
    // We test the complement: stop at space, <, >, /, =, ", ', !, ?, tab, nl, cr
    // which covers all realistic XML delimiters.
    //
    // This is simpler and faster than range-checking each name char class.
    const hn::ScalableTag<uint8_t> d;
    const size_t N = hn::Lanes(d);
    uint32_t pos = 0;

    const auto v_space = hn::Set(d, ' ');
    const auto v_tab   = hn::Set(d, '\t');
    const auto v_lf    = hn::Set(d, '\n');
    const auto v_cr    = hn::Set(d, '\r');
    const auto v_lt    = hn::Set(d, '<');
    const auto v_gt    = hn::Set(d, '>');
    const auto v_slash = hn::Set(d, '/');
    const auto v_eq    = hn::Set(d, '=');
    const auto v_dquot = hn::Set(d, '"');
    const auto v_squot = hn::Set(d, '\'');

    while (pos + N <= len) {
        const auto v = hn::LoadU(d, reinterpret_cast<const uint8_t*>(data + pos));

        // Check for delimiter characters that end a name
        const auto is_delim = hn::Or(
            hn::Or(hn::Or(hn::Eq(v, v_space), hn::Eq(v, v_tab)),
                   hn::Or(hn::Eq(v, v_lf), hn::Eq(v, v_cr))),
            hn::Or(hn::Or(hn::Eq(v, v_lt), hn::Eq(v, v_gt)),
                   hn::Or(hn::Or(hn::Eq(v, v_slash), hn::Eq(v, v_eq)),
                          hn::Or(hn::Eq(v, v_dquot), hn::Eq(v, v_squot)))));

        if (hn::AllFalse(d, is_delim)) {
            pos += static_cast<uint32_t>(N);
        } else {
            auto idx = hn::FindFirstTrue(d, is_delim);
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

uint32_t CountNewlines(const char* data, uint32_t len) {
    const hn::ScalableTag<uint8_t> d;
    const size_t N = hn::Lanes(d);
    uint32_t count = 0;
    uint32_t pos = 0;
    const auto v_nl = hn::Set(d, '\n');

    while (pos + N <= len) {
        const auto v = hn::LoadU(d, reinterpret_cast<const uint8_t*>(data + pos));
        count += static_cast<uint32_t>(hn::CountTrue(d, hn::Eq(v, v_nl)));
        pos += static_cast<uint32_t>(N);
    }

    // Scalar tail
    while (pos < len) {
        if (data[pos] == '\n') count++;
        pos++;
    }
    return count;
}

}  // namespace senda::xml::HWY_NAMESPACE
HWY_AFTER_NAMESPACE();

#if HWY_ONCE
namespace senda::xml {

HWY_EXPORT(FindTagOrAmp);
HWY_EXPORT(SkipWhitespace);
HWY_EXPORT(ScanName);
HWY_EXPORT(FindQuoteOrAmp);
HWY_EXPORT(CountNewlines);

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

uint32_t simd_count_newlines(const char* data, uint32_t len) {
    return HWY_DYNAMIC_DISPATCH(CountNewlines)(data, len);
}

}  // namespace senda::xml
#endif
