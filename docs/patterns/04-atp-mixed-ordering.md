# Pattern 04: atpMixed Ordering

This pattern maps AUTOSAR's `atpMixed` and `atpMixedString` stereotypes --
which model cross-role ordered "mixed content" in XML -- to Rupa's `#[ordered]`
type annotation, the unnamed role `..`, and the operator semantics that preserve
interleaving order across roles. It is the canonical example of why Rupa needs
cross-role ordering as a first-class concept.

---

## AUTOSAR Concept

### Mixed Content in XML and AUTOSAR

XML "mixed content" allows a single element to contain both character data and
child elements, interleaved in any order. The classic HTML example is a paragraph
with inline bold and link tags:

```xml
<P>Click <B>here</B> for <A HREF="...">details</A>.</P>
```

The order of text fragments and child elements is semantically significant: "Click"
precedes `<B>`, which precedes "for", and so on.

AUTOSAR uses two UML stereotypes to model this pattern in its metamodel:

| Stereotype | Meaning | Examples |
|------------|---------|----------|
| `atpMixed` | Mixed content: child elements from different roles interleave in a single ordered sequence. Serialized as XML mixed content. | `DocumentationBlock`, `LOverviewParagraph` |
| `atpMixedString` | Like `atpMixed`, but the "text" component is the string value of the element itself. Child elements are embedded inline within the text. | `LLongName`, `ConditionByFormula`, `EcucConditionFormula` |

Both stereotypes signal to code generators and schema tools that the **cross-role
ordering** of children in the XML serialization is significant.

### DocumentationBlock -- the Primary atpMixed Type

`DocumentationBlock` is the most widely used `atpMixed` class in AUTOSAR. It is
aggregated by over 30 meta-classes (every `Identifiable.introduction`, every
`GeneralAnnotation.annotationText`, `AUTOSAR.introduction`, etc.) and its children
span multiple roles:

| Role | Type | Mult. | xml.sequenceOffset |
|------|------|-------|--------------------|
| `p` | `MultiLanguageParagraph` | 0..1 | 10 |
| `verbatim` | `MultiLanguageVerbatim` | 0..1 | 20 |
| `defList` | `DefList` | 0..1 | 40 |
| `figure` | `MlFigure` | 0..1 | 70 |
| `formula` | `MlFormula` | 0..1 | 60 |
| `note` | `Note` | 0..1 | 80 |
| `trace` | `TraceableText` | 0..1 | 90 |
| `structuredReq` | `StructuredReq` | 0..1 | 100 |
| `list` | `List` | 0..1 | 50 |
| `labeledList` | `LabeledList` | 0..1 | 30 |

Because `DocumentationBlock` is `atpMixed`, multiple instances of these children
can appear interleaved. The `xml.sequenceOffset` tags define the default sort order
*within a generation pass* but the actual ordering in a document is the order in
the XML stream.

### atpMixedString -- Inline Structured Content

`LLongName` (stereotype `atpMixedString`, base `MixedContentForLongName`) is the
long-name text in a single language. Its string value is the text itself, and it
can contain inline structured sub-elements (subscript, superscript, emphasis).

`ConditionByFormula` is another `atpMixedString` class: its string value is the
formula text, with `SwSystemconst` references embedded inline at the positions
where system constants appear in the expression.

### ARXML Example: DocumentationBlock with Interleaved Content

```xml
<INTRODUCTION>
  <P>
    <L-1 L="EN">This module provides the brake-by-wire interface.</L-1>
  </P>
  <NOTE>
    <LABEL><L-4 L="EN">Safety Notice</L-4></LABEL>
    <NOTE-TEXT>
      <P>
        <L-1 L="EN">ASIL-D requirements apply to all public APIs.</L-1>
      </P>
    </NOTE-TEXT>
  </NOTE>
  <P>
    <L-1 L="EN">See the integration manual for calibration procedures.</L-1>
  </P>
</INTRODUCTION>
```

Here the `INTRODUCTION` element is a `DocumentationBlock`. The children appear
in the order: paragraph, note, paragraph. That order is the cross-role interleaving
sequence. An XML parser that discards this order and groups by element type would
lose information -- the note is *between* the two paragraphs.

### atpMixedString Example: ConditionByFormula

```xml
<CONDITION-BY-FORMULA>
  <BINDING-TIME>PRE-COMPILE-TIME</BINDING-TIME>
  ( <SYSC-REF DEST="SW-SYSTEMCONST">/AUTOSAR/Defs/EnableFeatureA</SYSC-REF>
    == 1 ) AND
  ( <SYSC-REF DEST="SW-SYSTEMCONST">/AUTOSAR/Defs/VariantId</SYSC-REF>
    != 3 )
</CONDITION-BY-FORMULA>
```

The text content `( ... == 1 ) AND ( ... != 3 )` is the formula string. The
`SYSC-REF` elements are embedded at the positions where the system constant
values are referenced. The relative position of text and references is the formula
structure.

---

## Rupa Mapping

### `#[ordered]` on Types -- Cross-Role Ordering

Rupa's `#[ordered]` annotation on a type declares that all containment operations
across all roles participate in a single global sequence:

```rupa
#[ordered]
type DocumentationBlock = {
    .p: MultiLanguageParagraph*;
    .verbatim: MultiLanguageVerbatim*;
    .labeledList: LabeledList*;
    .defList: DefList*;
    .list: List*;
    .formula: MlFormula*;
    .figure: MlFigure*;
    .note: Note*;
    .trace: TraceableText*;
    .structuredReq: StructuredReq*;
};
```

The `#[ordered]` annotation implies `#[ordered]` on every multi-valued containment
role. The model stores a single tagged sequence; per-role accessors (`.p`, `.note`,
etc.) return filtered views preserving relative order.

### Unnamed Role `..` -- atpMixedString

The `atpMixedString` pattern maps to a type with an explicit unnamed role (`..`).
The unnamed role holds the string content; named roles hold the inline structured
elements:

```rupa
#[ordered]
type ConditionByFormula = {
    ..: string*;                    // formula text fragments
    .syscRef: &SwSystemconst*;     // inline system constant references
    .bindingTime: BindingTimeEnum;
};
```

The `..` (double-dot) declares the unnamed role. In an `#[ordered]` type, text
fragments and structured children interleave in the global sequence.

### Operator Semantics on Ordered Types

| Operator | Behavior |
|----------|----------|
| `+=` on a role | Appends to the global sequence at the current tail position |
| `+=` between objects | Concatenates the two global sequences |
| `=` on a role | Replaces element(s) in place within the sequence |
| `\|=` (merge) | **Error.** Two independent interleaving sequences cannot be merged without ambiguity |

### Write Forwarding to Unnamed Role

For `atpMixedString` types, writing a bare string value to the object forwards to
the unnamed role. Both forms are equivalent:

```rupa
ConditionByFormula cond {
    . += "( ";                    // forwarding: appends to unnamed role (..)
    .syscRef += /AUTOSAR/Defs/EnableFeatureA;
    .. += " == 1 ) AND ( ";      // explicit unnamed role
    .syscRef += /AUTOSAR/Defs/VariantId;
    . += " != 3 )";
}
```

Reads always require explicit `..`:

```rupa
let fragments = /cond..;          // read the unnamed text fragments
let allChildren = /cond.*;        // all children in sequence order
```

### Sequence Concatenation

Two `#[ordered]` objects of the same type can be concatenated with `+=`:

```rupa
DocumentationBlock intro {
    .p += MultiLanguageParagraph p1 { };
}

DocumentationBlock more {
    .note += Note n1 { };
    .p += MultiLanguageParagraph p2 { };
}

// intro += more;
// Result sequence: [p:p1, note:n1, p:p2]
```

---

## Worked Example

### M2: Type Definitions

```rupa
domain autosar;

type LanguageEnum = ::string;

type LParagraph = {
    .l: LanguageEnum;
    ..: string;
};

type MultiLanguageParagraph = {
    .l1: LParagraph+;
};

type MultilanguageLongName = {
    .l4: LLongName+;
};

#[ordered]
type LLongName = {
    ..: string*;             // text content (atpMixedString)
    .l: LanguageEnum;
    .sub: Subscript*;
    .sup: Superscript*;
    .e: Emphasis*;
};

type Note = Identifiable {
    .noteText: DocumentationBlock;
};

#[ordered]
type DocumentationBlock = {
    .p: MultiLanguageParagraph*;
    .verbatim: MultiLanguageVerbatim*;
    .labeledList: LabeledList*;
    .defList: DefList*;
    .list: List*;
    .formula: MlFormula*;
    .figure: MlFigure*;
    .note: Note*;
    .trace: TraceableText*;
    .structuredReq: StructuredReq*;
};
```

### M1: Instance with Interleaved Content

```rupa
using domain autosar;

DocumentationBlock moduleIntro {
    // First paragraph -- position 0 in global sequence
    .p += MultiLanguageParagraph {
        .l1 += LParagraph {
            .l = "EN";
            . = "This module provides the brake-by-wire interface.";
        };
    };

    // Note -- position 1 in global sequence
    .note += Note SafetyNotice {
        .noteText = DocumentationBlock {
            .p += MultiLanguageParagraph {
                .l1 += LParagraph {
                    .l = "EN";
                    . = "ASIL-D requirements apply to all public APIs.";
                };
            };
        };
    };

    // Second paragraph -- position 2 in global sequence
    .p += MultiLanguageParagraph {
        .l1 += LParagraph {
            .l = "EN";
            . = "See the integration manual for calibration procedures.";
        };
    };
}
```

### Global Sequence

The model stores:

```
Position 0: role=.p       MultiLanguageParagraph (brake-by-wire)
Position 1: role=.note    Note "SafetyNotice"
Position 2: role=.p       MultiLanguageParagraph (integration manual)
```

Per-role views:

- `.p` returns `[pos0, pos2]` -- the two paragraphs in sequence order
- `.note` returns `[pos1]` -- the single note
- `.*` returns `[pos0, pos1, pos2]` -- all children in interleaved order

### atpMixedString Instance

```rupa
LLongName brakeLabel {
    .l = "EN";
    . += "Brake ";
    .e += Emphasis { . = "Pedal"; };
    . += " Position Sensor";
}
```

Global sequence: `[text:"Brake ", emphasis:"Pedal", text:" Position Sensor"]`.
Concatenated text view: `"Brake Pedal Position Sensor"`.

### Side-by-Side: ARXML vs Rupa

**ARXML (DocumentationBlock with interleaving):**
```xml
<INTRODUCTION>
  <P>
    <L-1 L="EN">Brake-by-wire interface.</L-1>
  </P>
  <NOTE>
    <SHORT-NAME>SafetyNotice</SHORT-NAME>
    <NOTE-TEXT>
      <P><L-1 L="EN">ASIL-D requirements.</L-1></P>
    </NOTE-TEXT>
  </NOTE>
  <P>
    <L-1 L="EN">See integration manual.</L-1>
  </P>
</INTRODUCTION>
```

**Rupa:**
```rupa
DocumentationBlock moduleIntro {
    .p += MultiLanguageParagraph { /* ... */ };
    .note += Note SafetyNotice { /* ... */ };
    .p += MultiLanguageParagraph { /* ... */ };
}
```

| Aspect | ARXML | Rupa |
|--------|-------|------|
| Mixed content signal | `atpMixed` stereotype (invisible in XML) | `#[ordered]` annotation (visible in type def) |
| Ordering | Implicit in XML element order | Explicit in statement order |
| Text interleaving | XML mixed content model | Unnamed role `..` with `#[ordered]` |
| Merge safety | Not addressed | `\|=` is a compile error on `#[ordered]` types |
| Role access | XPath with position predicates | Filtered views: `.p`, `.note`, `.*` |

---

## Edge Cases

### 1. Ordered Type + Merge (`|=`) Conflict

Merging two independently ordered sequences is inherently ambiguous. Rupa
rejects it at compile time:

```rupa
DocumentationBlock a {
    .p += MultiLanguageParagraph { /* "First" */ };
    .note += Note { /* "A-note" */ };
}

DocumentationBlock b {
    .note += Note { /* "B-note" */ };
    .p += MultiLanguageParagraph { /* "Second" */ };
}

// a |= b;
// ERROR: merge (|=) is not permitted on #[ordered] type DocumentationBlock
// Rationale: no deterministic interleaving of [p, note] and [note, p]
```

The error message should suggest `+=` (concatenation) as the alternative, since
concatenation has well-defined semantics: append b's sequence after a's.

### 2. Unnamed Roles in Non-Ordered Types

A type can have `..` without `#[ordered]`. This is the standard primitive-promotion
pattern -- the unnamed role holds the "value" of the object but ordering relative
to named roles is not tracked:

```rupa
type TaggedString = string {
    ..: string;            // single-valued unnamed role (from string supertype)
    .tag: ShortName;
};

TaggedString greeting {
    . = "Hello";           // forwards to unnamed role
    .tag = "informal";
}
```

Here `.tag` and `..` have no relative ordering. The object is *not* `#[ordered]`
and both `|=` and `+=` work as normal.

### 3. Mixing Ordered and Unordered Children

Within an `#[ordered]` type, non-containment roles (attributes, references) do not
participate in the global sequence. Only containment (`aggr`) roles interleave:

```rupa
#[ordered]
type ConditionByFormula = {
    ..: string*;                    // containment, participates in sequence
    .syscRef: &SwSystemconst*;     // REFERENCE, does NOT participate in sequence
    .bindingTime: BindingTimeEnum;  // attribute, does NOT participate
};
```

Wait -- this creates a problem for the `atpMixedString` pattern. In the ARXML,
`SYSC-REF` elements are interleaved with the formula text and their position
*is* significant. But `&SwSystemconst` is a reference, not a containment role.

Resolution: The AUTOSAR-to-Rupa domain definition must model inline references
that participate in ordering as *containment* wrappers rather than bare references.
This matches how AUTOSAR actually works: the `SYSC-REF` is an inline element
within mixed content, not a standalone reference:

```rupa
type SyscRefInline = {
    .target: &SwSystemconst;
};

#[ordered]
type ConditionByFormula = {
    ..: string*;                    // text fragments -- containment, in sequence
    .syscRef: SyscRefInline*;      // wrapper -- containment, in sequence
    .bindingTime: BindingTimeEnum;  // attribute -- not in sequence
};
```

This preserves the interleaving semantics while keeping references typed.

### 4. Formatter Behavior

The formatter must preserve statement order for `#[ordered]` types. Without the
annotation, the formatter is free to sort or group role assignments. With it, the
formatter treats the block as a sequence and preserves user-authored order:

```rupa
// Formatter MUST NOT reorder these statements:
DocumentationBlock intro {
    .p += MultiLanguageParagraph { /* first */ };    // position 0
    .note += Note { /* middle */ };                  // position 1
    .p += MultiLanguageParagraph { /* last */ };     // position 2
}

// Formatter MAY reorder these (not #[ordered]):
SystemSignal sig {
    .length = 12;
    .initValue = 0.0;        // could be moved above .length
}
```

### 5. `from` (Derivation) Preserves Sequence

When deriving a new object from an `#[ordered]` source, the global sequence is
copied:

```rupa
DocumentationBlock extended from moduleIntro {
    // Inherits: [p(brake-by-wire), note(SafetyNotice), p(integration)]
    .p += MultiLanguageParagraph { /* appended at position 3 */ };
}
```

The derived object's sequence is `[pos0, pos1, pos2, pos3]`.

### 6. Replace Within Sequence

When `=` replaces a role value in an `#[ordered]` type, the replacement occupies
the same position in the global sequence:

```rupa
/moduleIntro.note = Note RevisedNotice {
    .noteText = DocumentationBlock { /* updated */ };
};
// Sequence: [p(brake-by-wire), note(RevisedNotice), p(integration)]
// Position 1 is preserved; only the value changes.
```

---

## Design Reference

| Feature | Design document |
|---------|----------------|
| `#[ordered]` on types, cross-role ordering | `design/current/03-data-modeling/cross-role-ordering-and-unnamed-roles.md` |
| Unnamed role `..`, operator forwarding | `design/current/03-data-modeling/cross-role-ordering-and-unnamed-roles.md` |
| `.` vs `..` disambiguation | `design/current/02-syntax/self-reference-vs-unnamed-role.md` |
| `\|=` error on ordered types | `design/current/03-data-modeling/cross-role-ordering-and-unnamed-roles.md` |
| Sequence concatenation (`+=`) | `design/current/03-data-modeling/cross-role-ordering-and-unnamed-roles.md` |
| Statement ordering semantics | `design/current/03-data-modeling/statement-ordering.md` |
| Collection role semantics | `design/current/03-data-modeling/collection-role-semantics.md` |
| Formatter interaction | `design/current/10-formatting/formatting.md` |
| `from` derivation | `design/current/05-operations/object-derivation.md` |

### Related Patterns

- **Pattern 01**: Identifiable and paths -- the identity mechanism that `#[ordered]`
  types still participate in.
- **Pattern 02**: Type/prototype/archetype -- how `DocumentationBlock` is typed
  and instantiated.
- **Pattern 03**: Instance references -- relevant where `atpMixedString` types
  embed references inline.
