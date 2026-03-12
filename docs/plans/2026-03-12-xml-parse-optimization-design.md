# XML Parse Phase Optimization — Design

**Date**: 2026-03-12
**Scope**: senda (compiler-arxml: xml_pull_parser, xml_simd_kernels)

## Problem

Profiling the ARXML compile pipeline on R4.3.1 (227MB, 987K objects, 388K refs) with `sample` tool shows the XML parse phase dominates at ~58% of wall time (342 samples). Within the parse phase, three sources of overhead are addressable:

1. **`hwy::GetChosenTarget()` dispatch** — 9 samples (3%). Called on every SIMD kernel invocation to resolve the dynamic dispatch target. The target never changes at runtime.
2. **Scalar `count_lines`** — byte-by-byte newline scan called on every text run and whitespace skip. Hidden inside the 131 samples attributed to `XmlPullParser::next()`.
3. **Scalar whitespace-only check** — byte-by-byte loop in `next()` (lines 160-165) testing whether inter-element text is all whitespace. Runs for every text run between elements.

## Timing Baseline (release, Apple M4 Pro, warm cache, no instrumentation)

| File | Size | Objects | Refs | Compile |
|------|------|---------|------|---------|
| R20-11 | 49MB | 176K | 73K | 110ms |
| R4.3.1 | 227MB | 987K | 388K | 530ms |

## Profile Breakdown (R4.3.1, 342 samples)

| Category | Samples | % |
|----------|---------|---|
| XML parse (XmlPullParser::next, SIMD kernels, memchr) | ~198 | 58% |
| handle_end_element | ~50 | 15% |
| handle_start_element | ~42 | 12% |
| capture_xml_attributes | ~13 | 4% |
| Characters | ~6 | 2% |
| resolve_references | 4 | 1% |
| Other | ~29 | 8% |

## Fix 1: Cache SIMD Function Pointers

### Current

Each SIMD kernel call goes through `HWY_DYNAMIC_DISPATCH` which calls `hwy::GetChosenTarget()` to resolve the target on every invocation:

```cpp
// xml_pull_parser.h — static wrappers
static uint32_t find_tag_or_amp(const char* p, uint32_t len) {
    return senda::xml::simd_find_tag_or_amp(p, len);  // -> HWY_DYNAMIC_DISPATCH
}
```

### Change

Resolve the 4 Highway dispatch targets once in the `XmlPullParser` constructor. Store as member function pointers. The static wrapper methods become instance methods calling through cached pointers.

```cpp
// xml_pull_parser.h — new members
using FindTagOrAmpFn = uint32_t(*)(const char*, uint32_t);
using SkipWhitespaceFn = uint32_t(*)(const char*, uint32_t);
using ScanNameFn = uint32_t(*)(const char*, uint32_t);
using FindQuoteOrAmpFn = uint32_t(*)(const char*, uint32_t, char);
using CountNewlinesFn = uint32_t(*)(const char*, uint32_t);

FindTagOrAmpFn find_tag_or_amp_;
SkipWhitespaceFn skip_whitespace_;
ScanNameFn scan_name_;
FindQuoteOrAmpFn find_quote_end_;
CountNewlinesFn count_newlines_;
```

A new function in `xml_simd_kernels.h` resolves all pointers at once:

```cpp
struct SimdKernels {
    uint32_t(*find_tag_or_amp)(const char*, uint32_t);
    uint32_t(*skip_whitespace)(const char*, uint32_t);
    uint32_t(*scan_name)(const char*, uint32_t);
    uint32_t(*find_quote_or_amp)(const char*, uint32_t, char);
    uint32_t(*count_newlines)(const char*, uint32_t);
};

SimdKernels resolve_simd_kernels();
```

The constructor calls `resolve_simd_kernels()` once and stores the pointers. All call sites use the cached pointers.

## Fix 2: SIMD CountNewlines Kernel

### Current

```cpp
void XmlPullParser::count_lines(const char* from, const char* to) {
    for (auto* p = from; p < to; ++p) {
        if (*p == '\n') line_++;
    }
}
```

Scalar byte-by-byte scan called on every text run and whitespace skip.

### Change

Add a 5th Highway SIMD kernel `CountNewlines(data, len)` that counts `'\n'` bytes using `hn::Eq` + `hn::CountTrue`. Same Highway pattern as the existing kernels.

```cpp
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
```

Short-run heuristic: for ranges <= 8 bytes, use scalar loop (avoids function call overhead for the common case of short inter-element whitespace). `count_lines` becomes:

```cpp
void XmlPullParser::count_lines(const char* from, const char* to) {
    auto len = static_cast<uint32_t>(to - from);
    if (len <= 8) {
        for (auto* p = from; p < to; ++p) {
            if (*p == '\n') line_++;
        }
    } else {
        line_ += count_newlines_(from, len);
    }
}
```

## Fix 3: Reuse SkipWhitespace for Whitespace-Only Check

### Current

```cpp
// In next(), after FindTagOrAmp returns text content:
bool all_ws = true;
for (auto* c = text_start; c < pos_; ++c) {
    if (*c != ' ' && *c != '\t' && *c != '\n' && *c != '\r') {
        all_ws = false;
        break;
    }
}
```

Scalar byte-by-byte whitespace check on every inter-element text run.

### Change

Replace with cached `skip_whitespace_` call:

```cpp
auto text_len = static_cast<uint32_t>(pos_ - text_start);
if (text_len <= 8) {
    // Scalar for short runs
    bool all_ws = true;
    for (auto* c = text_start; c < pos_; ++c) {
        if (*c != ' ' && *c != '\t' && *c != '\n' && *c != '\r') {
            all_ws = false;
            break;
        }
    }
    if (all_ws) { /* count lines and continue */ }
} else {
    if (skip_whitespace_(text_start, text_len) == text_len) {
        count_lines(text_start, pos_);
        continue;
    }
}
```

## Changes by file

### xml_simd_kernels.h
- Add `CountNewlines` declaration
- Add `SimdKernels` struct and `resolve_simd_kernels()` function

### xml_simd_kernels.cpp
- Add `CountNewlines` Highway kernel implementation
- Add `HWY_EXPORT(CountNewlines)` and `simd_count_newlines` dispatch wrapper
- Add `resolve_simd_kernels()` that returns all 5 function pointers

### xml_pull_parser.h
- Add `SimdKernels kernels_` member (or individual pointers)
- Change static SIMD wrapper methods to instance methods using cached pointers
- Keep `count_lines` as instance method with scalar/SIMD threshold

### xml_pull_parser.cpp
- Constructor: call `resolve_simd_kernels()` to populate cached pointers
- `count_lines`: use threshold (<=8 scalar, >8 SIMD CountNewlines)
- `next()`: replace scalar whitespace-only check with `skip_whitespace_` + threshold

## Not in scope

- Frame struct restructuring (3% but poor effort/payoff ratio)
- `text_buf` management (3%, inherent data movement cost)
- `attrs_consumed_` skip-ahead SIMD (complexity not worth marginal gain)
- `roles.find()` / `tag_to_type.find()` (already `absl::flat_hash_map`, 2-3%)
- `LiteralStore::Add` (already optimized with rapidhash)

## Expected Impact

Conservative estimate: 5-8% wall-time improvement. The XML parse phase is 58% of total time; these changes target dispatch overhead (~3%), scalar newline counting, and scalar whitespace checking within that phase.

| File | Baseline | Expected |
|------|----------|----------|
| R20-11 (49MB) | 110ms | ~103ms |
| R4.3.1 (227MB) | 530ms | ~495ms |
