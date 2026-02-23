# Pattern 12: Multilanguage Text

This pattern maps AUTOSAR's language-tagged text mechanisms to Rupa's
internationalization support. It covers the `MultilanguageLongName`,
`MultiLanguageOverviewParagraph`, and `DocumentationBlock` meta-classes; the
`L-4` and `L-2` XML wrapper elements; the `LanguageSpecific` base class with its
`L` attribute; and how each concept translates into Rupa's domain-level
localization roles, quoted identifiers, and UTF-8-native string handling.

---

## AUTOSAR Concept

### The Multilanguage Text Hierarchy

AUTOSAR provides several meta-classes for attaching human-readable text in
multiple languages to model elements. All language-tagged text shares a common
base class:

- **`LanguageSpecific`** -- abstract base providing the `L` attribute (type
  `LEnum`). The `L` attribute carries an ISO 639 language tag such as `EN`, `DE`,
  `JA`, `AA-STANDARD` (language-independent), or `FOR-ALL` (all languages).

- **`MultilanguageLongName`** -- aggregates one or more `L-4` children (typed
  `LLongName`). Each `L-4` is a "long name in one particular language." The spec
  states: *"This meta-class represents the ability to specify a long name which
  acts in the role of a headline. It is intended for human readers. Per language
  it should be around max 80 characters."* Aggregated by
  `MultilanguageReferrable.longName`, `GeneralAnnotation.label`,
  `AliasNameAssignment.label`, `Note.label`, `Prms.label`, and
  `ValueGroup.label`.

- **`LLongName`** (stereotype `atpMixedString`) -- a single language variant of a
  long name. Extends `LanguageSpecific` and `MixedContentForLongName`. Mixed
  content means it can contain both plain text and inline formatting elements
  (`<E>`, `<SUB>`, `<SUP>`, `<TT>`).

- **`MultiLanguageOverviewParagraph`** -- aggregates one or more `L-2` children
  (typed `LOverviewParagraph`). Used for brief descriptive text on `desc`
  attributes throughout the metamodel (e.g., `Identifiable.desc`,
  `SwRecordLayoutV.desc`, `SwRecordLayoutGroup.desc`).

- **`LOverviewParagraph`** (stereotype `atpMixedString`) -- a single language
  variant of an overview paragraph. Extends `LanguageSpecific`.

- **`DocumentationBlock`** -- a richer structure for multi-paragraph
  documentation. Used by `Identifiable.introduction` and
  `GeneralAnnotation.annotationText`. Contains `TraceableText` elements which
  themselves can carry multilanguage content.

### The L-4 and L-2 Wrapper Elements

In ARXML serialization, the meta-class names `LLongName` and
`LOverviewParagraph` do not appear directly. Instead, XML uses short role-based
element names:

| Meta-class | XML element | Parent | Purpose |
|------------|-------------|--------|---------|
| `LLongName` | `<L-4>` | `<LONG-NAME>` | Language-tagged long name |
| `LOverviewParagraph` | `<L-2>` | `<DESC>` | Language-tagged description |

The `L` attribute on each element carries the language tag:

```xml
<L-4 L="EN">Engine Control Unit</L-4>
<L-4 L="DE">Motorsteuergeraet</L-4>
```

The numbering (`L-4`, `L-2`) derives from AUTOSAR's internal XML schema
conventions -- `L-4` permits mixed content with inline formatting while `L-2` is
a simpler overview paragraph form.

### The Language Tag Vocabulary

AUTOSAR uses a constrained set of language identifiers (`LEnum`):

| Tag | Meaning |
|-----|---------|
| `AA-STANDARD` | Language-independent / standardized term |
| `FOR-ALL` | Applicable to all languages |
| `EN` | English |
| `DE` | German |
| `FR` | French |
| `JA` | Japanese |
| `ZH` | Chinese |
| (others) | Additional ISO 639-1 codes |

The `AA-STANDARD` tag is notable: it marks text that should not be translated
(e.g., standardized technical terms). `FOR-ALL` marks text that applies
regardless of locale.

### Where Multilanguage Text Appears

Every `Identifiable` element in AUTOSAR inherits (via `MultilanguageReferrable`)
two multilanguage attachment points:

1. **`longName`** (`MultilanguageLongName`, optional) -- a headline-style display
   name, ~80 characters, intended for human consumption.
2. **`desc`** (`MultiLanguageOverviewParagraph`, optional) -- a brief description.
3. **`introduction`** (`DocumentationBlock`, optional) -- extended documentation.

Additionally, `GeneralAnnotation.label` carries a `MultilanguageLongName`, and
annotation text uses `DocumentationBlock`.

### ARXML Example

A software component with multilanguage long name and description:

```xml
<APPLICATION-SW-COMPONENT-TYPE>
  <SHORT-NAME>EngineCtrl</SHORT-NAME>
  <LONG-NAME>
    <L-4 L="EN">Engine Control Unit</L-4>
    <L-4 L="DE">Motorsteuergeraet</L-4>
    <L-4 L="JA">エンジン制御ユニット</L-4>
  </LONG-NAME>
  <DESC>
    <L-2 L="EN">Controls the engine based on sensor inputs and
      produces actuator commands.</L-2>
    <L-2 L="DE">Steuert den Motor basierend auf Sensoreingaben und
      erzeugt Aktuatorbefehle.</L-2>
  </DESC>
  <ADMIN-DATA>
    <SDGS>
      <SDG GID="AutosarStudio::AnnotationOrigin">
        <SD GID="originTool">Manual</SD>
      </SDG>
    </SDGS>
  </ADMIN-DATA>
</APPLICATION-SW-COMPONENT-TYPE>
```

Key observations:

1. `<SHORT-NAME>` is the machine identifier; `<LONG-NAME>` is the human-readable
   display name in potentially multiple languages.
2. `<LONG-NAME>` wraps multiple `<L-4>` elements; `<DESC>` wraps multiple `<L-2>`
   elements. Each carries an `L` attribute with the language tag.
3. The language tag is an XML attribute on the text element, not a separate child
   element -- a compact design that avoids extra nesting.
4. Mixed content in `<L-4>` allows inline markup: `<L-4 L="EN">Engine
   <E>Control</E> Unit</L-4>` (emphasis on "Control"). This is rare in practice
   but supported by the schema.

---

## Rupa Mapping

### Domain-Level Localization Roles

Rupa's design decision (9.4) is explicit: localization metadata belongs at the
metamodel level as regular model data, not as language-level annotations. The
AUTOSAR domain metamodel defines roles for multilanguage text, and instances
populate them using Rupa's standard role-assignment syntax.

The key mapping: AUTOSAR's `MultilanguageLongName` becomes a role typed as a
map-like structure keyed by language tag. Each language variant is a value
assignment on that role.

### String Literals and UTF-8

Rupa source files are UTF-8 only (9.1). All AUTOSAR language variants --
English, German, Japanese, Arabic -- are first-class string content without
encoding negotiation. String literal contents are NOT NFC-normalized (preserving
exact bytes for round-trip fidelity), which is essential for multilanguage text
where the source system may produce specific Unicode forms.

### Bare Tokens for All Scripts

Rupa's identifier rules (9.2) allow bare tokens in any Unicode script via
`XID_Start | digit` followed by `XID_Continue*`. This means AUTOSAR short names
in non-Latin scripts can be written without quoting:

```rupa
ApplicationSwComponentType エンジン制御 { }
```

However, `longName` and `desc` values are string literals (quoted) because they
contain spaces, punctuation, and mixed content that would not parse as bare
tokens.

### Parameterized Role Access

AUTOSAR's language tag on `L-4`/`L-2` maps to a parameterized role access
pattern in Rupa. The domain metamodel defines `longName` as accepting a language
key:

```rupa
.longName("EN") = "Engine Control Unit";
.longName("DE") = "Motorsteuergeraet";
```

This follows the pattern shown in the i18n design (9.4) where `.longName("de")`
is domain-level localization via ordinary role assignment. The parenthesized
language tag is a key selector on a map-typed role.

### Mapping Table

| AUTOSAR concept | ARXML form | Rupa equivalent |
|-----------------|------------|-----------------|
| `MultilanguageLongName` | `<LONG-NAME>` wrapper | Map-typed `.longName` role |
| `LLongName` | `<L-4 L="EN">text</L-4>` | `.longName("EN") = "text";` |
| `MultiLanguageOverviewParagraph` | `<DESC>` wrapper | Map-typed `.desc` role |
| `LOverviewParagraph` | `<L-2 L="EN">text</L-2>` | `.desc("EN") = "text";` |
| `L` attribute (language tag) | `L="EN"` XML attribute | Map key `("EN")` |
| `AA-STANDARD` tag | `L="AA-STANDARD"` | Key `"AA-STANDARD"` |
| `FOR-ALL` tag | `L="FOR-ALL"` | Key `"FOR-ALL"` |
| `DocumentationBlock` | `<INTRODUCTION>` wrapper | Structured `.introduction` role |
| Mixed content (`<E>`, `<SUB>`) | Inline XML elements | Domain-specific markup strings |

---

## Worked Example

### M2: Type Definitions (Metamodel)

```rupa
domain autosar;

#[pattern("[a-zA-Z_][a-zA-Z0-9_]*")]
type ShortName = ::string;

// Language tag enumeration matching AUTOSAR LEnum
type LEnum = enum {
    AA_STANDARD;
    FOR_ALL;
    EN; DE; FR; JA; ZH; KO; ES; IT; PT; SV;
};

// A single language-tagged text entry
type LLongName = {
    #[id(0)]
    .lang: LEnum;
    .value: ::string;
};

// A single language-tagged overview paragraph
type LOverviewParagraph = {
    #[id(0)]
    .lang: LEnum;
    .value: ::string;
};

// Multilanguage long name: a collection keyed by language
type MultilanguageLongName = {
    .variants: LLongName*;
};

// Multilanguage overview paragraph: a collection keyed by language
type MultiLanguageOverviewParagraph = {
    .variants: LOverviewParagraph*;
};

// Base class providing multilanguage long name
type MultilanguageReferrable = Referrable {
    .longName: MultilanguageLongName?;
};

type Identifiable = MultilanguageReferrable {
    .category: ShortName?;
    .desc: MultiLanguageOverviewParagraph?;
    .adminData: AdminData?;
};

#[abstract]
type ARElement = Identifiable { };

type ApplicationSwComponentType = ARElement {
    .ports: PortPrototype*;
    .internalBehaviors: SwcInternalBehavior*;
};
```

### M1: Model Instance (Verbose Metamodel-Faithful Form)

```rupa
using domain autosar;

ARPackage AUTOSAR {
    ARPackage Components {
        ApplicationSwComponentType EngineCtrl {
            .longName = MultilanguageLongName {
                LLongName EN {
                    .value = "Engine Control Unit";
                }
                LLongName DE {
                    .value = "Motorsteuergeraet";
                }
                LLongName JA {
                    .value = "エンジン制御ユニット";
                }
            };

            .desc = MultiLanguageOverviewParagraph {
                LOverviewParagraph EN {
                    .value = "Controls the engine based on sensor inputs "
                           + "and produces actuator commands.";
                }
                LOverviewParagraph DE {
                    .value = "Steuert den Motor basierend auf Sensoreingaben "
                           + "und erzeugt Aktuatorbefehle.";
                }
            };
        }
    }
}
```

### M1: Model Instance (Sugared Domain-Convenience Form)

If the domain metamodel provides a map-keyed accessor pattern for
multilanguage roles (as suggested in the i18n design 9.4), the same
model becomes more concise:

```rupa
using domain autosar;

ARPackage AUTOSAR {
    ARPackage Components {
        ApplicationSwComponentType EngineCtrl {
            .longName("EN") = "Engine Control Unit";
            .longName("DE") = "Motorsteuergeraet";
            .longName("JA") = "エンジン制御ユニット";

            .desc("EN") = "Controls the engine based on sensor inputs "
                        + "and produces actuator commands.";
            .desc("DE") = "Steuert den Motor basierend auf Sensoreingaben "
                        + "und erzeugt Aktuatorbefehle.";
        }
    }
}
```

### Side-by-Side Comparison

**ARXML (24 lines for long name + description):**

```xml
<APPLICATION-SW-COMPONENT-TYPE>
  <SHORT-NAME>EngineCtrl</SHORT-NAME>
  <LONG-NAME>
    <L-4 L="EN">Engine Control Unit</L-4>
    <L-4 L="DE">Motorsteuergeraet</L-4>
    <L-4 L="JA">エンジン制御ユニット</L-4>
  </LONG-NAME>
  <DESC>
    <L-2 L="EN">Controls the engine based on sensor inputs
      and produces actuator commands.</L-2>
    <L-2 L="DE">Steuert den Motor basierend auf Sensoreingaben
      und erzeugt Aktuatorbefehle.</L-2>
  </DESC>
</APPLICATION-SW-COMPONENT-TYPE>
```

**Rupa sugared form (8 lines for the same content):**

```rupa
ApplicationSwComponentType EngineCtrl {
    .longName("EN") = "Engine Control Unit";
    .longName("DE") = "Motorsteuergeraet";
    .longName("JA") = "エンジン制御ユニット";
    .desc("EN") = "Controls the engine based on sensor inputs "
                + "and produces actuator commands.";
    .desc("DE") = "Steuert den Motor basierend auf Sensoreingaben "
                + "und erzeugt Aktuatorbefehle.";
}
```

| Aspect | ARXML | Rupa (sugared) |
|--------|-------|----------------|
| Wrapper nesting | `<LONG-NAME>` wraps `<L-4>` elements | Flat `.longName(key)` assignments |
| Language tag | XML attribute `L="EN"` | String key `"EN"` |
| Text content | XML text node (mixed content) | String literal |
| Closing tags | Every element needs `</...>` | Semicolons terminate assignments |
| Lines per 3-language longName | 5 | 3 |
| Lines per 2-language desc | 5 | 4 |

---

## Edge Cases

### 1. AA-STANDARD and FOR-ALL: Non-Language Tags

AUTOSAR's `AA-STANDARD` and `FOR-ALL` are not ISO language codes but special
markers. In Rupa, they are simply additional enum values in `LEnum` and
additional keys in the map:

```rupa
.longName("AA-STANDARD") = "ECU";
.longName("FOR-ALL") = "Electronic Control Unit";
```

The domain metamodel can enforce constraints such as "if `AA-STANDARD` is
present, no other language variants are needed" via validation rules. Rupa's
language does not special-case these -- they are domain data.

### 2. Mixed Content in L-4 (Inline Formatting)

AUTOSAR's `LLongName` is an `atpMixedString`, meaning `<L-4>` can contain inline
XML elements like `<E>` (emphasis), `<SUB>` (subscript), `<SUP>` (superscript),
and `<TT>` (teletype). In practice this is rare, but it exists in the schema.

In Rupa, string literals are plain text. Inline formatting would need a
domain-specific convention, such as a lightweight markup within the string or a
structured value type:

```rupa
// Option A: domain convention for inline markup in plain strings
.longName("EN") = "Engine {emph}Control{/emph} Unit";

// Option B: structured value with explicit formatting spans
.longName("EN") = FormattedText {
    .segments = [
        TextSegment { .text = "Engine "; },
        TextSegment { .text = "Control"; .emphasis = true; },
        TextSegment { .text = " Unit"; },
    ];
};
```

The ARXML importer must handle mixed content; the Rupa model can choose the
representation that best fits its usage. For the vast majority of real AUTOSAR
files, long names are plain text with no inline formatting.

### 3. Duplicate Language Tags

AUTOSAR requires at most one `L-4` per language within a `<LONG-NAME>`. In
Rupa's metamodel-faithful form, this is enforced by `#[id(0)]` on `.lang` in
`LLongName` -- the language tag IS the identity, so duplicates are a compile
error:

```
error[E0042]: duplicate identity "EN" within parent MultilanguageLongName
  --> model.rupa:5:17
   |
 5 |                 LLongName EN { .value = "Engine Control"; }
   |                           -- first defined here
 8 |                 LLongName EN { .value = "Motor Control"; }
   |                           ^^ duplicate identity
```

In the sugared form, duplicate key assignment (`.longName("EN")` twice) is
handled by Rupa's standard duplicate-assignment semantics for the role.

### 4. Empty or Missing Language Variants

An element with no `<LONG-NAME>` is common in AUTOSAR -- long names are optional
(multiplicity 0..1). In Rupa, the `.longName` role is typed as optional (`?`),
so omission is natural:

```rupa
// No long name, no desc -- just the shortName identity
SystemSignal BrakePedalPos {
    .length = 12;
}
```

A `<LONG-NAME>` with zero `<L-4>` children is technically invalid (the schema
requires 1..* for the `l4` role). The Rupa metamodel mirrors this:
`.variants: LLongName*` could be constrained to `LLongName+` (one or more) if
the domain enforces the same rule.

### 5. Bidirectional Text in Long Names

AUTOSAR models used in Middle Eastern or North African contexts may have Arabic
or Hebrew long names:

```rupa
.longName("AR") = "وحدة التحكم في المحرك";
```

Rupa's bidi rules (9.3) apply: the string literal content can contain any
Unicode text. Bidi control characters are allowed in strings (modern isolates
with balanced pairs), but for simple RTL text the Unicode Bidirectional Algorithm
handles rendering without explicit control characters. The LSP highlights any
bidi control characters visually even where they are allowed.

### 6. NFC Normalization and Round-Trip Fidelity

String literal contents are NOT NFC-normalized in Rupa (9.1). This is critical
for multilanguage text round-tripping: if an AUTOSAR tool produces a Japanese
long name with specific Unicode codepoint sequences, Rupa preserves them exactly.
The ARXML exporter writes back the same bytes. NFC normalization only applies to
bare tokens (identifiers), not to string data.

### 7. Annotation Labels

AUTOSAR `GeneralAnnotation` also uses `MultilanguageLongName` for its `.label`
role. The same pattern applies:

```rupa
GeneralAnnotation {
    .label("EN") = "Safety Requirement";
    .label("DE") = "Sicherheitsanforderung";
    .annotationText = DocumentationBlock {
        // structured documentation content
    };
}
```

---

## Design Reference

| Feature | Design document |
|---------|----------------|
| UTF-8 encoding, string literal byte preservation | `design/current/09-i18n/internationalization-and-character-set.md` (9.1) |
| Bare token rules, XID_Start, NFC normalization | `design/current/09-i18n/internationalization-and-character-set.md` (9.2) |
| Bidirectional text safety in strings | `design/current/09-i18n/internationalization-and-character-set.md` (9.3) |
| Domain-level localization, `.longName("de")` pattern | `design/current/09-i18n/internationalization-and-character-set.md` (9.4) |
| `#[id(N)]` annotation, identity mechanism | `design/current/03-data-modeling/object-node-structure.md` |
| String literal rules, quoted identifiers | `design/current/02-syntax/` |
| Map-typed roles, parameterized access | `design/current/03-data-modeling/type-system.md` |
| Annotations are language-only (`#[...]`) | `design/current/06-extensibility/` (6.4) |
| Metamodel-mediated literal interpretation | `design/current/02-syntax/` (2.5), `design/current/06-extensibility/` (6.1) |

### Related Patterns

- **Pattern 01**: Identifiable, Short Names, and Path Navigation -- covers the
  `shortName` / `Referrable` / `Identifiable` hierarchy that multilanguage text
  decorates.
- **Pattern 08**: Admin Data and SDG -- covers the `AdminData` and structured
  metadata that often accompanies multilanguage descriptive elements.
- **Pattern 05**: Blueprints and Derivation -- `LLongName.blueprintValue`
  interacts with the blueprint pattern for defining how long names are derived.
