# XML Parse Phase Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce XML parse phase overhead by caching SIMD dispatch targets, adding a SIMD newline-counting kernel, and replacing scalar whitespace-only checks with SIMD.

**Architecture:** Three changes to the XML pull parser layer — all in `src/compiler-arxml/`. No changes to rupa, kore, or the ARXML compiler module. The parser's SIMD kernel dispatch is resolved once at construction instead of per-call. A new Highway `CountNewlines` kernel replaces the scalar `count_lines` loop. The scalar whitespace-only check in `next()` is replaced with the existing `SkipWhitespace` kernel.

**Tech Stack:** C++23, Google Highway (SIMD), GTest

**Design spec:** `docs/plans/2026-03-12-xml-parse-optimization-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/compiler-arxml/xml_simd_kernels.h` | Modify | Add `CountNewlines` declaration, `SimdKernels` struct, `resolve_simd_kernels()` |
| `src/compiler-arxml/xml_simd_kernels.cpp` | Modify | Add `CountNewlines` Highway kernel, export, resolver |
| `src/compiler-arxml/xml_pull_parser.h` | Modify | Store `SimdKernels` member, replace static SIMD wrappers with instance methods |
| `src/compiler-arxml/xml_pull_parser.cpp` | Modify | Constructor resolves kernels, SIMD `count_lines`, SIMD whitespace check |
| `test/compiler-arxml/xml-pull-parser-test.cpp` | Modify | Add line-counting correctness tests |

**Task dependencies:** All tasks are sequential (1→2→3→4→5→6). Each modifies files touched by the previous task.

---

### Task 1: Add `CountNewlines` SIMD Kernel

**Files:**
- Modify: `src/compiler-arxml/xml_simd_kernels.h:9-27`
- Modify: `src/compiler-arxml/xml_simd_kernels.cpp:152-181`

- [ ] **Step 1: Add `CountNewlines` declaration to header**

In `src/compiler-arxml/xml_simd_kernels.h`, add after line 25 (before the closing `}`):

```cpp
// Count newline ('\n') bytes in a range. Returns count.
uint32_t simd_count_newlines(const char* data, uint32_t len);
```

- [ ] **Step 2: Add `CountNewlines` Highway kernel implementation**

In `src/compiler-arxml/xml_simd_kernels.cpp`, add after the `FindQuoteOrAmp` function (after line 151, before the closing namespace brace on line 153):

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

- [ ] **Step 3: Add export and dispatch wrapper**

In `src/compiler-arxml/xml_simd_kernels.cpp`, in the `#if HWY_ONCE` section, add after `HWY_EXPORT(FindQuoteOrAmp);` (line 162):

```cpp
HWY_EXPORT(CountNewlines);
```

And add the dispatch wrapper after `simd_find_quote_or_amp` (after line 178):

```cpp
uint32_t simd_count_newlines(const char* data, uint32_t len) {
    return HWY_DYNAMIC_DISPATCH(CountNewlines)(data, len);
}
```

- [ ] **Step 4: Build and verify compilation**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
cmake --build --preset release 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 5: Run existing tests to verify no regression**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
./build-release/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: All 19 tests pass (kernel not yet wired in, so no behavioral change).

- [ ] **Step 6: Commit**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
git add src/compiler-arxml/xml_simd_kernels.h src/compiler-arxml/xml_simd_kernels.cpp
git commit -m "feat(xml): add CountNewlines SIMD kernel via Google Highway"
```

---

### Task 2: Add `SimdKernels` Struct and Resolver

**Files:**
- Modify: `src/compiler-arxml/xml_simd_kernels.h:9-27`
- Modify: `src/compiler-arxml/xml_simd_kernels.cpp:156-181`

- [ ] **Step 1: Add `SimdKernels` struct and resolver declaration to header**

In `src/compiler-arxml/xml_simd_kernels.h`, add after the `simd_count_newlines` declaration (before closing `}`):

```cpp
// Resolved SIMD kernel function pointers — call resolve_simd_kernels() once
// at startup, then use the pointers directly to avoid per-call dispatch overhead.
struct SimdKernels {
    uint32_t(*find_tag_or_amp)(const char*, uint32_t);
    uint32_t(*skip_whitespace)(const char*, uint32_t);
    uint32_t(*scan_name)(const char*, uint32_t);
    uint32_t(*find_quote_or_amp)(const char*, uint32_t, char);
    uint32_t(*count_newlines)(const char*, uint32_t);
};

SimdKernels resolve_simd_kernels();
```

- [ ] **Step 2: Implement `resolve_simd_kernels()`**

In `src/compiler-arxml/xml_simd_kernels.cpp`, add inside the `#if HWY_ONCE` section, after the dispatch wrappers (before the closing `}` of the namespace):

```cpp
SimdKernels resolve_simd_kernels() {
    // Trigger lazy dispatch resolution by calling each kernel once.
    // With len=0 the SIMD loops don't execute, but the dispatch target is resolved.
    static const char dummy = '\0';
    (void)simd_find_tag_or_amp(&dummy, 0);
    (void)simd_skip_whitespace(&dummy, 0);
    (void)simd_scan_name(&dummy, 0);
    (void)simd_find_quote_or_amp(&dummy, 0, '"');
    (void)simd_count_newlines(&dummy, 0);

    return {
        simd_find_tag_or_amp,
        simd_skip_whitespace,
        simd_scan_name,
        simd_find_quote_or_amp,
        simd_count_newlines,
    };
}
```

After `resolve_simd_kernels()`, the `HWY_DYNAMIC_DISPATCH` inside each `simd_*` wrapper has already resolved and cached its target. Subsequent calls through the stored pointers go through the wrapper, which performs a single cached pointer load — no more `GetChosenTarget()` per call.

- [ ] **Step 3: Build and verify**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
cmake --build --preset release 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
git add src/compiler-arxml/xml_simd_kernels.h src/compiler-arxml/xml_simd_kernels.cpp
git commit -m "feat(xml): add SimdKernels struct and resolver for cached dispatch"
```

---

### Task 3: Wire Cached Kernels into XmlPullParser

**Files:**
- Modify: `src/compiler-arxml/xml_pull_parser.h:56-104`
- Modify: `src/compiler-arxml/xml_pull_parser.cpp:6-35,42-46,110-294,296-355,357-475`

- [ ] **Step 1: Add `SimdKernels` member to `XmlPullParser`**

In `src/compiler-arxml/xml_pull_parser.h`, replace lines 82-94 (the static SIMD wrapper methods) with:

```cpp
    // --- SIMD-accelerated scanning (cached dispatch) ---
    xml::SimdKernels simd_;

    uint32_t find_tag_or_amp(const char* p, uint32_t len) const {
        return simd_.find_tag_or_amp(p, len);
    }
    uint32_t skip_whitespace(const char* p, uint32_t len) const {
        return simd_.skip_whitespace(p, len);
    }
    uint32_t scan_name(const char* p, uint32_t len) const {
        return simd_.scan_name(p, len);
    }
    uint32_t find_quote_end(const char* p, uint32_t len, char quote) const {
        return simd_.find_quote_or_amp(p, len, quote);
    }
```

- [ ] **Step 2: Initialize `simd_` in constructor**

In `src/compiler-arxml/xml_pull_parser.cpp`, modify the constructor (line 6-13) to initialize `simd_`:

```cpp
XmlPullParser::XmlPullParser(std::string_view input)
    : data_(input.data()),
      end_(input.data() + input.size()),
      pos_(input.data()),
      attr_pos_(nullptr),
      attr_end_(nullptr),
      attrs_consumed_(true),
      simd_(xml::resolve_simd_kernels())
{
```

Note: `simd_` is initialized before the constructor body runs, so the `skip_whitespace` and `count_lines` calls in the body (lines 23-24) will use the cached pointers correctly since those are now instance methods calling through `simd_`.

- [ ] **Step 3: Build and run tests**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
cmake --build --preset release 2>&1 | tail -5
./build-release/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: Build succeeds, all 19 tests pass.

- [ ] **Step 4: Verify ARXML compile still works**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
./build-release/senda compile /Users/ekuhn/CLionProjects/senda/test/data/arxml/vehicle-comms-r20-11.arxml 2>&1
```

Expected: `176121 objects`, `73288 references resolved, 53 unresolved` — same as baseline.

- [ ] **Step 5: Commit**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
git add src/compiler-arxml/xml_pull_parser.h src/compiler-arxml/xml_pull_parser.cpp
git commit -m "perf(xml): cache SIMD dispatch targets in XmlPullParser constructor"
```

---

### Task 4: SIMD `count_lines` with Short-Run Heuristic

**Files:**
- Modify: `src/compiler-arxml/xml_pull_parser.cpp:42-46`
- Modify: `test/compiler-arxml/xml-pull-parser-test.cpp`

- [ ] **Step 1: Add line-counting test for multiline content**

In `test/compiler-arxml/xml-pull-parser-test.cpp`, add a test:

```cpp
TEST(XmlPullParserTest, LineCountingMultilineText) {
    // 5 lines of text content (4 newlines) inside an element
    std::string xml = "<root>\nline1\nline2\nline3\nline4\n</root>";
    senda::XmlPullParser p(xml);
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);
    EXPECT_EQ(p.line(), 1u);
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);
    // Text is "\nline1\nline2\nline3\nline4\n" — 5 newlines
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);
    EXPECT_EQ(p.line(), 6u);  // line 1 + 5 newlines
}
```

- [ ] **Step 2: Add line-counting test for long whitespace runs**

```cpp
TEST(XmlPullParserTest, LineCountingLongWhitespace) {
    // Inter-element whitespace with many newlines (>8 bytes to trigger SIMD path)
    std::string xml = "<a>\n\n\n\n\n\n\n\n\n\n<b>x</b></a>";  // 10 newlines
    senda::XmlPullParser p(xml);
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);  // <a>
    EXPECT_EQ(p.line(), 1u);
    EXPECT_EQ(p.next(), senda::XmlEvent::StartElement);  // <b>
    EXPECT_EQ(p.line(), 11u);  // 1 + 10 newlines
    EXPECT_EQ(p.next(), senda::XmlEvent::Characters);    // "x"
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);    // </b>
    EXPECT_EQ(p.next(), senda::XmlEvent::EndElement);    // </a>
}
```

- [ ] **Step 3: Run tests to verify they pass with current scalar implementation**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
cmake --build --preset release 2>&1 | tail -3
./build-release/test/compiler-arxml/senda.xml_pull_parser_test --gtest_filter="*LineCounting*"
```

Expected: Both new tests pass (verifying our expected line numbers are correct against the scalar implementation).

- [ ] **Step 4: Replace `count_lines` with SIMD + short-run heuristic**

In `src/compiler-arxml/xml_pull_parser.cpp`, replace lines 42-46:

```cpp
void XmlPullParser::count_lines(const char* from, const char* to) {
    for (auto* p = from; p < to; ++p) {
        if (*p == '\n') line_++;
    }
}
```

With:

```cpp
void XmlPullParser::count_lines(const char* from, const char* to) {
    auto len = static_cast<uint32_t>(to - from);
    if (len <= 8) {
        for (auto* p = from; p < to; ++p) {
            if (*p == '\n') line_++;
        }
    } else {
        line_ += simd_.count_newlines(from, len);
    }
}
```

- [ ] **Step 5: Build and run all tests**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
cmake --build --preset release 2>&1 | tail -3
./build-release/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: All tests pass (including 2 new line-counting tests).

- [ ] **Step 6: Verify ARXML compile correctness**

```bash
./build-release/senda compile /Users/ekuhn/CLionProjects/senda/test/data/arxml/vehicle-comms-r20-11.arxml 2>&1
```

Expected: Same output as baseline.

- [ ] **Step 7: Commit**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
git add src/compiler-arxml/xml_pull_parser.cpp test/compiler-arxml/xml-pull-parser-test.cpp
git commit -m "perf(xml): SIMD count_lines with <=8 byte scalar heuristic"
```

---

### Task 5: SIMD Whitespace-Only Check with Short-Run Heuristic

**Files:**
- Modify: `src/compiler-arxml/xml_pull_parser.cpp:158-170`

- [ ] **Step 1: Replace scalar whitespace-only check**

In `src/compiler-arxml/xml_pull_parser.cpp`, in the `next()` method, replace the whitespace-only check block (the section starting with `// Check if text is whitespace-only`). The current code is:

```cpp
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
```

Replace with:

```cpp
                // Check if text is whitespace-only
                auto text_len = static_cast<uint32_t>(pos_ - text_start);
                bool all_ws;
                if (text_len <= 8) {
                    all_ws = true;
                    for (auto* c = text_start; c < pos_; ++c) {
                        if (*c != ' ' && *c != '\t' && *c != '\n' && *c != '\r') {
                            all_ws = false;
                            break;
                        }
                    }
                } else {
                    all_ws = (skip_whitespace(text_start, text_len) == text_len);
                }
                if (!all_ws) {
                    text_ = std::string_view(text_start, static_cast<size_t>(pos_ - text_start));
                    return XmlEvent::Characters;
                }
                continue;
```

- [ ] **Step 2: Build and run all tests**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
cmake --build --preset release 2>&1 | tail -3
./build-release/test/compiler-arxml/senda.xml_pull_parser_test
```

Expected: All tests pass.

- [ ] **Step 3: Verify ARXML compile correctness**

```bash
./build-release/senda compile /Users/ekuhn/CLionProjects/senda/test/data/arxml/vehicle-comms-r20-11.arxml 2>&1
```

Expected: Same output as baseline.

- [ ] **Step 4: Commit**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
git add src/compiler-arxml/xml_pull_parser.cpp
git commit -m "perf(xml): SIMD whitespace-only check with <=8 byte scalar heuristic"
```

---

### Task 6: Performance Validation and Cleanup

**Files:**
- Modify: `src/compiler-arxml/senda.compiler-arxml.cppm:1-12` (remove profiling includes)

- [ ] **Step 1: Remove profiling includes**

In `src/compiler-arxml/senda.compiler-arxml.cppm`, remove the `#include <chrono>` and `#include <iostream>` that were added for profiling (lines 1-2 of the includes). The file should start with:

```cpp
module;

#include <cstring>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <absl/container/flat_hash_map.h>
#include <utility>
#include <vector>
```

- [ ] **Step 2: Build release and run full test suite**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
cmake --build --preset release 2>&1 | tail -5
./build-release/test/compiler-arxml/senda.xml_pull_parser_test
./build-release/test/compiler-arxml/senda.compiler_arxml_test
```

Expected: All tests pass.

- [ ] **Step 3: Run performance benchmarks**

R20-11 (3 runs, warm cache):
```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
for i in 1 2 3; do /usr/bin/time -l ./build-release/senda compile /Users/ekuhn/CLionProjects/senda/test/data/arxml/vehicle-comms-r20-11.arxml 2>&1 | grep -E "real|maximum"; done
```

R4.3.1 (3 runs, warm cache):
```bash
for i in 1 2 3; do /usr/bin/time -l ./build-release/senda --domain autosar-r20-11 compile /Users/ekuhn/CLionProjects/senda/test/data/arxml/vehicle-platform-r4-3-1.arxml 2>&1 | grep -E "real|maximum"; done
```

Expected: Improvement over baseline (R20-11: <110ms, R4.3.1: <530ms).

Baselines for comparison:
- R20-11: 110ms
- R4.3.1: 530ms

- [ ] **Step 4: Commit cleanup**

```bash
cd /Users/ekuhn/CLionProjects/senda/.worktrees/xml-parse-optimization
git add src/compiler-arxml/senda.compiler-arxml.cppm
git commit -m "chore: remove profiling includes from ARXML compiler"
```
