# Pattern 08: AdminData and Special Data Groups (SDG)

This pattern maps AUTOSAR's `AdminData`/`Sdg`/`SdgContents`/`SD` extension data
mechanism to Rupa's domain derivation, typed annotations, and
`#[encode]`/`#[decode]` transformation pipeline. It covers how vendors attach
arbitrary extension data to any `Identifiable` element in ARXML, how AUTOSAR's
generic key-value SDG hierarchy works, and how Rupa replaces that untyped
tree with domain-typed extensions while preserving round-trip fidelity through
the encode/decode pipeline.

---

## AUTOSAR Concept

### AdminData: The Extension Point

Every `Identifiable` element in the AUTOSAR metamodel can carry an `AdminData`
aggregation. `AdminData` serves two roles:

1. **Document metadata** -- revision history (`DocRevision`), language settings,
   and used-language declarations.
2. **Special data** -- the `sdg` aggregation, which holds zero or more `Sdg`
   (SpecialDataGroup) instances containing arbitrary vendor-specific data.

The AUTOSAR specification describes `AdminData` as:

| Attribute | Type | Mult. | Kind | Note |
|-----------|------|-------|------|------|
| `docRevision` | `DocRevision` | `*` (ordered) | aggr | Revision history entries, sorted descending by date |
| `language` | `LEnum` | `0..1` | attr | Master language of the document fragment |
| `sdg` | `Sdg` | `*` | aggr | Special data not represented by the standard model |
| `usedLanguages` | `MultiLanguagePlainText` | `0..1` | aggr | Languages provided in the document |

`AdminData` is aggregated by `AUTOSAR.adminData`, `Describable.adminData`, and
`Identifiable.adminData` -- meaning virtually every named element in an AUTOSAR
model can carry extension data.

### Sdg: The Special Data Group

`Sdg` (SpecialDataGroup) is a recursive, key-value container for vendor-specific
information. The AUTOSAR spec explicitly states:

> *"Sdg is a generic model which can be used to keep arbitrary information which
> is not explicitly modeled in the meta-model. Special Data should only be used
> moderately since all elements should be defined in the meta-model. Thereby SDG
> should be considered as a temporary solution when no explicit model is
> available."*

Each `Sdg` has three parts:

| Attribute | Type | Mult. | Kind | Note |
|-----------|------|-------|------|------|
| `gid` | `NameToken` | `1` | attr | The "Generic Identifier" -- acts like an XML element name. Mandatory key. |
| `sdgCaption` | `SdgCaption` | `0..1` | aggr | Assigns `Identifiable` properties (`shortName`, `desc`, etc.) to the SDG |
| `sdgContentsType` | `SdgContents` | `0..1` | aggr | The actual content of the SDG |

The `GID` attribute (from the SGML/XML term "Generic Identifier") serves as the
primary discriminator. Tools use GID prefixes (e.g., `VDX-`, `DV-`, `ATP-`) as
vendor namespace conventions, though the AUTOSAR metamodel does not formalize
this convention.

### SdgContents: The Data Payload

`SdgContents` holds the actual data within an `Sdg`. It contains a mix of:

- **`SD`** elements -- simple string values with an optional `GID` attribute
  serving as a key. Each `SD` holds a text value.
- **Nested `Sdg`** elements -- recursive sub-groups, each with their own `GID`,
  `SdgCaption`, and `SdgContents`. This enables arbitrary nesting depth.
- **`SdxRef`** elements -- cross-references to other model elements, encoded
  as reference paths with a `GID` key.

The recursive `SdgContents.sdg` aggregation is what makes SDG hierarchies
arbitrarily deep. A single `AdminData` block can contain multiple top-level
`Sdg` groups, each containing nested `Sdg` sub-groups with `SD` leaf values
at any level.

### SdgCaption: Identity for SDGs

`SdgCaption` gives an `Sdg` the full properties of `Identifiable` -- most
importantly a `shortName` that can serve as a reference target. This is how
other parts of the model can reference a specific SDG group. The AUTOSAR
metamodel marks `sdgCaption` as an `atpIdentityContributor`, meaning it
participates in determining the identity of the containing `Sdg`. The
`AdminData.sdg` aggregation uses `sdg.sdgCaption.shortName` as its Splitkey,
enabling SDG groups to be merged across multiple ARXML files.

### ARXML Example

A typical vendor extension in ARXML uses AdminData with nested SDGs to attach
tool-specific configuration to an I-PDU:

```xml
<I-PDU-GROUP>
  <SHORT-NAME>EngineMessages</SHORT-NAME>
  <ADMIN-DATA>
    <SDGS>
      <SDG GID="DV-TOOL-CONFIG">
        <SDG-CAPTION>
          <SHORT-NAME>DvToolConfig</SHORT-NAME>
        </SDG-CAPTION>
        <SD GID="DV-VERSION">3.2.1</SD>
        <SD GID="DV-AUTHOR">jsmith</SD>
        <SDG GID="DV-CODEGEN">
          <SD GID="DV-TEMPLATE">CAN_Standard</SD>
          <SD GID="DV-OPTIMIZATION">SIZE</SD>
          <SDG GID="DV-OPTIONS">
            <SD GID="DV-INLINE-PACK">true</SD>
            <SD GID="DV-BYTE-ORDER">LITTLE_ENDIAN</SD>
          </SDG>
        </SDG>
        <SDG GID="DV-VALIDATION">
          <SD GID="DV-LAST-CHECK">2025-11-03T14:22:00</SD>
          <SD GID="DV-STATUS">PASSED</SD>
        </SDG>
      </SDG>
      <SDG GID="ATP-INTERNAL">
        <SD GID="ATP-HASH">a1b2c3d4e5f6</SD>
      </SDG>
    </SDGS>
  </ADMIN-DATA>
  <!-- ... standard I-PDU-GROUP content ... -->
</I-PDU-GROUP>
```

This example illustrates several real-world patterns:

- **Multiple top-level SDGs** with different GID prefixes (`DV-TOOL-CONFIG`
  from a design tool, `ATP-INTERNAL` from the AUTOSAR toolchain).
- **Three nesting levels** (`DV-TOOL-CONFIG` > `DV-CODEGEN` > `DV-OPTIONS`).
- **SdgCaption** on the top-level group for Splitkey merging.
- **Leaf SD elements** with GID keys and string values.
- **No type safety** -- `"true"`, `"SIZE"`, `"3.2.1"`, and
  `"2025-11-03T14:22:00"` are all plain strings.

---

## Rupa Mapping

### Strategy: Typed Extension via Domain Derivation

Rupa's approach to SDG data is to **replace untyped key-value trees with typed
domain extensions**. Rather than preserving the `Sdg`/`SD` nesting as-is, a
Rupa domain derivation defines proper types for vendor-specific data, and the
`#[encode]`/`#[decode]` pipeline handles serialization to and from the SDG
format when interchanging with ARXML.

This follows the pattern established in the Rupa design document
`extension-data-encoding.md`: custom M2 types are first-class in the derived
domain, and the encode pipeline serializes them into the base domain's
generic extension mechanism (here `AdminData`/`Sdg` instead of
`ExtensionData`/`ExtGroup`).

### Domain Definition: Typed Vendor Extensions

```rupa
// -- dv-autosar.rupa ----------------------------------------------------------
// Derive a domain that adds typed DV-tool extensions to AUTOSAR.

domain dv-autosar = autosar-r25-11;

// Code generation optimization strategy
type CodeGenOptimization = ::enum(SIZE, SPEED, BALANCED);

// Byte ordering for serialization
type ByteOrder = ::enum(LITTLE_ENDIAN, BIG_ENDIAN, OPAQUE);

// Code generation options
type CodeGenOptions = {
    .inlinePack : ::boolean;
    .byteOrder  : ByteOrder;
};

// Code generation configuration
type CodeGenConfig = {
    .template     : ::string;
    .optimization : CodeGenOptimization;
    .options      : CodeGenOptions;
};

// Validation status tracking
type ValidationStatus = ::enum(PASSED, FAILED, SKIPPED, UNKNOWN);

type ValidationRecord = {
    .lastCheck : ::string;       // ISO 8601 timestamp
    .status    : ValidationStatus;
};

// Top-level DV tool configuration, attachable to any Identifiable
type DvToolConfig = {
    #[id(1)]
    .name       : Name;
    .version    : ::string;
    .author     : ::string;
    .codeGen    : CodeGenConfig?;
    .validation : ValidationRecord?;
};

// Extend IPduGroup with optional DV tool configuration
type IPduGroup = IPduGroup {
    .dvConfig : DvToolConfig?;
};
```

**What this does**: The `domain dv-autosar = autosar-r25-11;` derivation
creates a new domain that inherits all AUTOSAR R25-11 types. The
`type IPduGroup = IPduGroup { ... };` self-reference reopens `IPduGroup`
to add a `.dvConfig` role. The base domain's `AdminData`, `Sdg`, `SdgContents`,
and `SD` types are inherited unchanged -- they still exist in the domain for
round-trip support, but authors working in the derived domain use the typed
`DvToolConfig` instead.

### Source Model: Using Typed Extensions

```rupa
// -- engine-pdus.rupa ---------------------------------------------------------
using domain dv-autosar;

Catalog {
    IPduGroup IPduGroups/EngineMessages {
        .name = "EngineMessages";

        .dvConfig = DvToolConfig {
            .version = "3.2.1";
            .author  = "jsmith";

            .codeGen = CodeGenConfig {
                .template     = "CAN_Standard";
                .optimization = SIZE;
                .options = CodeGenOptions {
                    .inlinePack = true;
                    .byteOrder  = LITTLE_ENDIAN;
                };
            };

            .validation = ValidationRecord {
                .lastCheck = "2025-11-03T14:22:00";
                .status    = PASSED;
            };
        };

        // ... standard IPduGroup content ...
    };
}
```

Compare this with the ARXML version above: the same information is expressed
with full type safety, IDE completion, and validation. `SIZE` is an enum
literal instead of a string. `.inlinePack` is a boolean instead of `"true"`.
Nesting is structural rather than GID-keyed.

### Encode Pipeline: Typed Extensions to AdminData/SDG

```rupa
// -- dv-to-autosar.rupa -------------------------------------------------------
// Pipeline: dv-autosar -> autosar-r25-11
// Encodes typed DV extensions as AdminData/Sdg in the base AUTOSAR domain.

using domain autosar-r25-11;                // target domain
using domain dv-autosar as dv;              // source domain

// Key convention: all DV tool SDGs use the "DV-" GID prefix.

// Helper: wrap a value as an SD element with a GID key
let make_sd(gid: ::string, value: ::string) = SD {
    .gid   = gid;
    .value = value;
};

// Helper: encode CodeGenOptions as a nested Sdg
let encode_codegen_options(opts: dv::CodeGenOptions) = Sdg {
    .gid = "DV-OPTIONS";
    .sdgContentsType = SdgContents {
        .sd += make_sd("DV-INLINE-PACK", to_string(opts.inlinePack));
        .sd += make_sd("DV-BYTE-ORDER", to_string(opts.byteOrder));
    };
};

// Helper: encode CodeGenConfig as a nested Sdg
let encode_codegen(cfg: dv::CodeGenConfig) = Sdg {
    .gid = "DV-CODEGEN";
    .sdgContentsType = SdgContents {
        .sd  += make_sd("DV-TEMPLATE", cfg.template);
        .sd  += make_sd("DV-OPTIMIZATION", to_string(cfg.optimization));
        .sdg += encode_codegen_options(cfg.options);
    };
};

// Helper: encode ValidationRecord as a nested Sdg
let encode_validation(val: dv::ValidationRecord) = Sdg {
    .gid = "DV-VALIDATION";
    .sdgContentsType = SdgContents {
        .sd += make_sd("DV-LAST-CHECK", val.lastCheck);
        .sd += make_sd("DV-STATUS", to_string(val.status));
    };
};

// Main transform: IPduGroup with DV config
#[transform]
let transform_ipdu_group(group: dv::IPduGroup) = IPduGroup {
    .name = group.name;

    // Delegate standard children
    ::transform(group.iPdus, .iPdus);

    // Preserve any existing adminData from the source
    ::transform(group.adminData, .adminData);

    // Encode DV config into AdminData/Sdg
    if group.dvConfig? then {
        .adminData |= AdminData {
            .sdg += Sdg {
                .gid = "DV-TOOL-CONFIG";

                // SdgCaption for Splitkey identity
                .sdgCaption = SdgCaption {
                    .shortName = "DvToolConfig";
                };

                .sdgContentsType = SdgContents {
                    .sd += make_sd("DV-VERSION", group.dvConfig.version);
                    .sd += make_sd("DV-AUTHOR", group.dvConfig.author);

                    if group.dvConfig.codeGen? then {
                        .sdg += encode_codegen(group.dvConfig.codeGen);
                    };
                    if group.dvConfig.validation? then {
                        .sdg += encode_validation(group.dvConfig.validation);
                    };
                };
            };
        };
    };
};

// DvToolConfig instances are consumed by transform_ipdu_group above.
#[transform]
let drop_dv_config(c: dv::DvToolConfig) {};
#[transform]
let drop_codegen(c: dv::CodeGenConfig) {};
#[transform]
let drop_codegen_opts(c: dv::CodeGenOptions) {};
#[transform]
let drop_validation(c: dv::ValidationRecord) {};
```

**Key patterns**:

- **`|=` merge** on `.adminData` preserves any existing `AdminData` content
  (doc revisions, other vendor SDGs) while adding the DV-specific `Sdg` group.
  This is critical: an element can have multiple vendor SDGs from different
  tools, and encoding one vendor's data must not destroy another's.

- **`SdgCaption` with `shortName`** enables Splitkey-based merging. When the
  encoded ARXML is later split across files, the `DvToolConfig` SDG can be
  reconstituted by matching on `sdg.sdgCaption.shortName`.

- **Explicit drops** for consumed types (`DvToolConfig`, `CodeGenConfig`, etc.)
  prevent "unmapped type" errors. These types exist only in the source domain
  and are serialized inline into `Sdg` trees.

### Decode Pipeline: AdminData/SDG to Typed Extensions

```rupa
// -- autosar-to-dv.rupa -------------------------------------------------------
// Reverse pipeline: autosar-r25-11 -> dv-autosar
// Decodes DV-prefixed SDGs back into typed domain extensions.

using domain dv-autosar;                    // target domain
using domain autosar-r25-11 as ar;          // source domain

// Helper: find an SD by GID within an SdgContents
let find_sd(contents: ar::SdgContents, gid: ::string) =
    contents.sd | find(s => s.gid == gid);

// Helper: find a nested Sdg by GID within an SdgContents
let find_sdg(contents: ar::SdgContents, gid: ::string) =
    contents.sdg | find(s => s.gid == gid);

#[transform]
let import_ipdu_group(group: ar::IPduGroup) = IPduGroup {
    .name = group.name;
    ::transform(group.iPdus, .iPdus);

    // Look for the DV-TOOL-CONFIG SDG in AdminData
    let dv_sdg = group.adminData?.sdg
        | find(s => s.gid == "DV-TOOL-CONFIG");

    if dv_sdg? then {
        let contents = dv_sdg.sdgContentsType;

        .dvConfig = DvToolConfig {
            .version = find_sd(contents, "DV-VERSION").value;
            .author  = find_sd(contents, "DV-AUTHOR").value;

            // Decode CodeGen sub-group
            let cg_sdg = find_sdg(contents, "DV-CODEGEN");
            if cg_sdg? then {
                let cg_contents = cg_sdg.sdgContentsType;
                .codeGen = CodeGenConfig {
                    .template     = find_sd(cg_contents, "DV-TEMPLATE").value;
                    .optimization = find_sd(cg_contents, "DV-OPTIMIZATION").value;

                    let opts_sdg = find_sdg(cg_contents, "DV-OPTIONS");
                    if opts_sdg? then {
                        let opts_contents = opts_sdg.sdgContentsType;
                        .options = CodeGenOptions {
                            .inlinePack = find_sd(opts_contents, "DV-INLINE-PACK").value;
                            .byteOrder  = find_sd(opts_contents, "DV-BYTE-ORDER").value;
                        };
                    };
                };
            };

            // Decode Validation sub-group
            let val_sdg = find_sdg(contents, "DV-VALIDATION");
            if val_sdg? then {
                let val_contents = val_sdg.sdgContentsType;
                .validation = ValidationRecord {
                    .lastCheck = find_sd(val_contents, "DV-LAST-CHECK").value;
                    .status    = find_sd(val_contents, "DV-STATUS").value;
                };
            };
        };
    };

    // Copy adminData minus the DV-TOOL-CONFIG SDG
    if group.adminData? then {
        .adminData = AdminData {
            ::transform(group.adminData.docRevision, .docRevision);
            group.adminData.sdg
                | filter(s => s.gid != "DV-TOOL-CONFIG")
                | each(s => { ::transform(s, .sdg); });
        };
    };
};
```

**The decode mirrors the encode**: it navigates the `Sdg` tree by GID keys,
extracts `SD` values, and constructs typed instances. The remaining
non-DV SDGs are preserved in the target `AdminData` via filtered transform.

---

## Edge Cases

### Deeply Nested SDG Hierarchies

The AUTOSAR SDG mechanism permits unlimited nesting depth. The ARXML example
above shows three levels (`DV-TOOL-CONFIG` > `DV-CODEGEN` > `DV-OPTIONS`).
Real-world tool data can go deeper -- some authoring tools nest SDGs to
five or more levels for complex configuration trees.

In the Rupa approach, each nesting level maps to a distinct typed composition
in the derived domain. This is manageable for known vendor schemas but becomes
impractical for deeply dynamic or schema-free data. For truly arbitrary SDG
trees that resist typing, the base domain's `Sdg`/`SdgContents` types remain
available in the derived domain and can be used directly:

```rupa
using domain dv-autosar;

// Fallback: use the inherited Sdg type directly for unknown vendor data
IPduGroup IPduGroups/Legacy {
    .name = "Legacy";
    .adminData = AdminData {
        .sdg += Sdg {
            .gid = "UNKNOWN-VENDOR-X";
            .sdgContentsType = SdgContents {
                .sd += SD { .gid = "X-KEY-1"; .value = "some-value"; };
                .sdg += Sdg {
                    .gid = "X-NESTED";
                    .sdgContentsType = SdgContents {
                        .sd += SD { .gid = "X-DEEP"; .value = "deep-value"; };
                    };
                };
            };
        };
    };
};
```

This is verbose but correct -- it mirrors the ARXML structure exactly. The
typed extension pattern is preferred when the SDG schema is known.

### Vendor-Specific vs Standard SDGs

A single `AdminData` block can contain SDGs from multiple vendors. The GID
prefix convention (`DV-`, `ATP-`, `VDX-`, etc.) acts as an informal namespace.
The encode pipeline must preserve SDGs it does not own:

```rupa
// In the encode pipeline, the |= merge on .adminData is critical:
.adminData |= AdminData {
    .sdg += Sdg { .gid = "DV-TOOL-CONFIG"; /* ... */ };
};
```

The `|=` operator ensures that if the source element already has `AdminData`
with an `ATP-INTERNAL` SDG, the `DV-TOOL-CONFIG` SDG is added alongside it
rather than replacing the entire `AdminData`. Without `|=`, existing vendor
SDGs would be silently destroyed.

Similarly, the decode pipeline must filter selectively:

```rupa
// Only extract DV-prefixed SDGs; leave others intact
group.adminData.sdg
    | filter(s => s.gid != "DV-TOOL-CONFIG")
    | each(s => { ::transform(s, .sdg); });
```

This ensures that decoding the DV vendor's data does not consume or discard
another vendor's SDGs. Each vendor's encode/decode pipeline operates on its
own GID prefix and passes through everything else.

### Round-Trip Fidelity

The encode/decode cycle must satisfy: for any `DvToolConfig` instance in the
source domain, encoding to `Sdg` and decoding back must produce a
semantically identical `DvToolConfig`. The key risks are:

1. **String serialization of non-string types**. `to_string(SIZE)` produces
   `"SIZE"`, which must parse back to the `SIZE` enum literal. Rupa's type
   narrowing at model insertion handles this -- the string `"SIZE"` assigned
   to a role of type `CodeGenOptimization` narrows to the enum value.

2. **Optional field handling**. An `IPduGroup` with no `.codeGen` produces no
   `DV-CODEGEN` SDG in the encoded output. The decode must handle the absence
   gracefully via `if cg_sdg? then { ... }`.

3. **Ordering**. AUTOSAR `SdgContents.sdg` is an unordered aggregation.
   Encoded SDGs may appear in any order in the ARXML output. The decode
   pipeline uses `find()` by GID rather than positional access, making it
   order-independent.

4. **Unknown SD keys**. If a newer version of the DV tool adds an
   `SD GID="DV-NEW-FEATURE"` that the current decode pipeline does not
   handle, that SD element is silently dropped during decode. This is a
   known limitation of schema-typed decoding. Mitigation: the decode
   pipeline can capture unrecognized SD entries into a catch-all role
   (e.g., `.extraData : [SD]*;`) on the typed extension.

### Multiple AdminData Sources in Splitable Models

When an AUTOSAR model is split across files, the same `Identifiable` element
can appear in multiple ARXML files, each contributing to its `AdminData`.
The `atpSplitable` stereotype on `AdminData.sdg` with Splitkey
`sdg.sdgCaption.shortName` enables this: two ARXML files contributing
SDGs to the same element are merged by matching `SdgCaption.shortName`.

In Rupa, this maps to the `|=` merge operator combined with multi-file
composition (see Pattern 06). The derived domain's typed extension is
defined once, and each contributing file sets its portion:

```rupa
// File 1: base IPduGroup definition
IPduGroup IPduGroups/EngineMessages {
    .name = "EngineMessages";
    .dvConfig = DvToolConfig {
        .version = "3.2.1";
        .author  = "jsmith";
    };
};

// File 2: adds code generation config via merge
IPduGroup IPduGroups/EngineMessages |= {
    .dvConfig |= {
        .codeGen = CodeGenConfig {
            .template     = "CAN_Standard";
            .optimization = SIZE;
            .options = CodeGenOptions {
                .inlinePack = true;
                .byteOrder  = LITTLE_ENDIAN;
            };
        };
    };
};
```

---

## Design Reference

| Topic | Document | Relevance |
|-------|----------|-----------|
| Extension data encoding pattern | `design/current/examples/extension-data-encoding.md` | The canonical example of encoding custom M2 extensions as generic extension data. AdminData/SDG follows the same `#[encode]`/`#[decode]` + `\|=` merge pattern used for `ExtensionData`/`ExtGroup`. |
| Domain-specific extensions | `design/current/06-extensibility/domain-specific-extensions.md` | Domain derivation syntax (`domain X = Y;`), type reopening, `#[transform]`/`#[encode]`/`#[decode]` pipeline ordering, and the principle that domain metadata uses model elements rather than custom annotations. |
| Merge operator semantics | `design/current/05-operations/merge-semantics.md` (section 5.3) | The `\|=` create-and-merge operator that enables non-destructive AdminData augmentation. |
| Splitable and multi-file | `autosar/patterns/06-splitable-and-multi-file.md` | How `atpSplitable` and Splitkey map to Rupa's multi-file merge -- directly relevant since `AdminData.sdg` uses Splitkey `sdg.sdgCaption.shortName`. |

### AUTOSAR Source References

- **AdminData class**: TPS_SoftwareComponentTemplate, TPS_SystemTemplate,
  TPS_ECUConfiguration -- `AdminData` class tables. Aggregated by
  `AUTOSAR.adminData`, `Describable.adminData`, `Identifiable.adminData`.
- **Sdg class**: All TPS documents, SWS_RTE Appendix D. `Sdg.gid` (NameToken,
  mandatory), `Sdg.sdgCaption` (SdgCaption, 0..1), `Sdg.sdgContentsType`
  (SdgContents, 0..1).
- **SdgContents class**: Contains `SD` elements (string values with GID keys),
  nested `Sdg` elements, and `SdxRef` cross-references.
- **Splitkey on AdminData.sdg**: Tagged value
  `atp.Splitkey=sdg.sdgCaption.shortName` -- the merge identity for SDGs
  across split ARXML files.
