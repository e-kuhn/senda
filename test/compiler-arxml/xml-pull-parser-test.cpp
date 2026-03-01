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
    EXPECT_EQ(p.tag(), "AUTOSAR");  // AR:AUTOSAR -> AUTOSAR

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
