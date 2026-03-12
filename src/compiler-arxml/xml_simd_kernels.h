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

// Count newline ('\n') bytes in a range. Returns count.
uint32_t simd_count_newlines(const char* data, uint32_t len);

}  // namespace senda::xml
