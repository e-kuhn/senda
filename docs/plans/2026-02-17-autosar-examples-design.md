# Design: AUTOSAR Examples & Use Cases Folder

**Date**: 2026-02-17
**Status**: Approved
**Purpose**: Create a top-level `autosar/` folder mapping Rupa language features to concrete AUTOSAR M3/M2 patterns

---

## Motivation

Rupa's design docs (`design/current/`) are deliberately domain-neutral after the de-AUTOSAR pass (2026-02-16). However, AUTOSAR is the primary driving domain for the language. We need a dedicated place that:

1. **Validates** that every major AUTOSAR M3/M2 pattern has a clean Rupa mapping
2. **Communicates** to AUTOSAR engineers and stakeholders how Rupa serves their concrete needs
3. **Uses real AUTOSAR names** (SwComponentType, PPortPrototype, AtpInstanceRef, etc.) — this folder speaks AUTOSAR

## Audience

- **Engineers**: pattern docs for precise mapping lookup
- **Stakeholders**: use-case docs for end-to-end workflow understanding

## Location

Top-level `autosar/` folder (peer to `design/`, `spec/`).

## Folder Structure

```
autosar/
├── README.md                              # Index, master mapping table, how to read
├── patterns/                              # Pattern-centric (for engineers)
│   ├── 01-identifiable-and-paths.md
│   ├── 02-type-prototype-archetype.md
│   ├── 03-instance-references.md
│   ├── 04-atp-mixed-ordering.md
│   ├── 05-blueprints-and-derivation.md
│   ├── 06-splitable-and-multi-file.md
│   ├── 07-variation-points.md
│   ├── 08-admin-data-and-sdg.md
│   ├── 09-ecuc-definition-value.md
│   ├── 10-references-and-ref-bases.md
│   ├── 11-flat-map.md
│   ├── 12-multilanguage-text.md
│   └── 13-data-type-mapping.md
└── use-cases/                             # Use-case-centric (for stakeholders)
    ├── 01-component-architecture.md
    ├── 02-signal-stack.md
    ├── 03-ecuc-configuration.md
    ├── 04-version-migration.md
    ├── 05-ecu-extract-overlay.md
    ├── 06-validation-constraints.md
    └── 07-service-interface-deployment.md
```

## Pattern Inventory (M3 + M2)

### M3-Level (Foundation / Generic Structure Template)

| # | AUTOSAR Pattern | Rupa Feature | Pattern Doc |
|---|----------------|-------------|-------------|
| 1 | Identifiable / SHORT-NAME / SHORT-NAME-PATH | `#[id]`, `/` paths, cross-role identity uniqueness | 01 |
| 2 | AtpType / AtpPrototype / AtpClassifier | Types, instances, `#[archetype]` | 02 |
| 3 | AtpInstanceRef (context/target) | `#[instance_ref]`, `#[context]`, `#[target]`, `/>` | 03 |
| 4 | atpMixed (cross-role ordering) | `#[ordered]` on types, unnamed role `..` | 04 |
| 5 | AtpBlueprint / AtpBlueprintable / namePattern | Domain derivation, type reopening | 05 |
| 6 | atpSplitable / Splitkey / open packages | Multi-file composition, `|=` merge | 06 |
| 7 | atpVariation / VariationPoint / binding times | `variant` declarations, `#[variant()]` | 07 |
| 8 | AdminData / SDG / SdgContents | Annotations `#[...]`, `#[decode]`/`#[encode]` | 08 |
| 9 | ECUC ParamDef/Value duality | M2/M1 separation, definition-as-schema | 09 |
| 10 | References (REF, TREF, BASE), reference bases | `&Type`, `import as`, `*` search | 10 |
| 11 | FlatMap / FlatInstanceDescriptor | `.**`, tree builtins, transforms | 11 |
| 12 | MultilanguageLongName / Desc (L-2, L-4) | i18n support | 12 |
| 13 | DataTypeMappingSet / CompuMethod | `#[transform]`, expression functions | 13 |

### M2-Level (exercised via use cases)

| # | AUTOSAR Concept | Use Case Doc |
|---|----------------|-------------|
| 14 | SwComponentType / Prototype / Port / Connector | 01 |
| 15 | SystemSignal / ISignal / ISignalIPdu / Frame | 02 |
| 16 | EcucModuleDef / EcucContainerDef / EcucParameterValue | 03 |
| 17 | Cross-version migration (R22 -> R25) | 04 |
| 18 | ECU Extract, overlays, vendor SDG extensions | 05 |
| 19 | OCL constraints / semantic validation | 06 |
| 20 | ServiceInterface / Machine / Manifest (AP) | 07 |

## Document Templates

### Pattern Doc Template

```markdown
# Pattern: [Name]

## AUTOSAR Concept

What this is in AUTOSAR. M3 or M2 level. ARXML snippet showing
the real XML structure. Reference to AUTOSAR spec document (TPS).

## Rupa Mapping

How Rupa represents this. Show:
- Metamodel definition (M2) in Rupa syntax
- Instance (M1) usage
- Key annotations and operators

## Worked Example

Complete Rupa code using real AUTOSAR type names.
Side-by-side ARXML <-> Rupa where illuminating.

## Edge Cases & Limitations

Where the mapping is imperfect. What AUTOSAR features Rupa
handles differently or defers.

## Design Reference

Link to canonical design doc in design/current/.
```

### Use Case Doc Template

```markdown
# Use Case: [Name]

## Scenario

What the AUTOSAR engineer is trying to accomplish.
Real-world context.

## ARXML Baseline

Abbreviated but structurally complete ARXML showing the scenario.

## Rupa Solution

Step-by-step: metamodel (M2), model (M1), validation, transforms.
Complete Rupa code.

## Key Features Demonstrated

Which Rupa features are exercised, with links to pattern docs.

## Comparison

Line count, nesting depth, readability comparison vs ARXML.
```

## Pattern Details

### 01 — Identifiable and Paths

**AUTOSAR**: Every model element inherits from `Identifiable` via `Referrable.shortName`. References use SHORT-NAME-PATHs like `/AUTOSAR/Signals/BrakePedalPosition`. The `DEST` attribute on references provides type information.

**Rupa mapping**:
- `#[id]` annotation marks identity roles (= shortName)
- `/` root anchor + identity navigation = SHORT-NAME-PATH
- Cross-role identity uniqueness = AUTOSAR's rule that shortNames are unique within a parent ARPackage
- Non-identifiable objects are path-transparent (like the AUTOSAR root element)
- `DEST` attribute → Rupa's typed reference `&Type` makes this unnecessary (type is in the metamodel)

**Design refs**: `03-data-modeling/references-and-paths.md`, `03-data-modeling/cross-role-identity-uniqueness.md`

### 02 — Type-Prototype-Archetype

**AUTOSAR**: The type-prototype pattern is fundamental. `SwComponentType` defines structure (ports, behavior). `SwComponentPrototype` is an instance referencing its type. The prototype doesn't contain ports — it delegates to its type.

**Rupa mapping**:
- `#[archetype]` on a reference role marks structural delegation
- `/>` operator navigates through the archetype boundary
- Type definitions = Rupa types; Prototypes = Rupa instances with `#[archetype]` reference

**Design refs**: `03-data-modeling/instance-references-and-archetypes.md`

### 03 — Instance References

**AUTOSAR**: `AtpInstanceRef` is a structured reference with `atpContextElement` (ordered context chain) and `atpTarget`. Concrete subclasses like `PPortInCompositionInstanceRef` define the specific context and target types. Serialized with `xml.sequenceOffset` for ordering.

**Rupa mapping**:
- `#[instance_ref]` on a type = AtpInstanceRef subclass
- `#[context]` roles = atpContextElement (declaration order = traversal order)
- `#[target]` role = atpTarget
- `/>` operator constructs the chain: `./SensorSlot/>SpeedOutput`
- `::instance_ref` M3 type narrows to specific M2 type at assignment

**Design refs**: `03-data-modeling/instance-references-and-archetypes.md`

### 04 — atpMixed Ordering

**AUTOSAR**: `atpMixed` stereotype means assignments across different roles form a single global sequence. Used in Desc, Introduction, and other rich-text-like types where text interleaves with structured children.

**Rupa mapping**:
- `#[ordered]` on a type = atpMixed semantics
- Unnamed role `..` = text content interleaved with structured children
- Formatter preserves statement order for `#[ordered]` types
- `|=` merge is an error on `#[ordered]` types (no sensible interleaving default)

**Design refs**: `03-data-modeling/cross-role-ordering-and-unnamed-roles.md`

### 05 — Blueprints and Derivation

**AUTOSAR**: `AtpBlueprint`/`AtpBlueprintable` enable standardized elements that can be derived (copied and refined) into project-specific elements. `BlueprintMapping` tracks the relationship. `namePattern` allows flexible naming of derived elements.

**Rupa mapping**:
- Domain derivation (`domain mycompany-ext = autosar-r22`) = creating a derived domain from a blueprint base
- Type reopening = adding roles to existing types in a derived domain
- Blueprint validation = checking derived elements conform to blueprint → validation rules

**Design refs**: `06-extensibility/domain-specific-extensions.md`, `04-modularity/model-composition.md`

### 06 — atpSplitable and Multi-File

**AUTOSAR**: `atpSplitable` marks aggregations that can be split across files. `Splitkey` defines which attribute is used for identity-based merging. ARPackages are "open sets" — content from multiple files merges into one package.

**Rupa mapping**:
- Multi-file composition: multiple `.rupa` files contribute to the same namespace
- `|=` merge operator = identity-based merging (same as Splitkey-based merge)
- `import` + `|= base` = importing and merging model content

**Design refs**: `04-modularity/file-organization.md`, `04-modularity/model-composition.md`, `05-operations/modification-operations.md`

### 07 — Variation Points

**AUTOSAR**: `atpVariation` marks roles subject to variability. `VariationPoint` contains binding conditions referencing `SwSystemconst` values. Binding times: blueprintDerivationTime, systemDesignTime, codeGenerationTime, preCompileTime, linkTime, postBuild.

**Rupa mapping**:
- `variant VehicleLine = [Standard, Premium, Sport]` = SwSystemconst
- `#[variant(VehicleLine == Premium)]` on statements = VariationPoint binding
- `--variant "VehicleLine=Premium"` CLI flag = build-time resolution
- No exhaustiveness requirement matches AUTOSAR's partial-existence semantics

**Design refs**: `03-data-modeling/variants-and-configurations.md`

### 08 — AdminData and SDG

**AUTOSAR**: `AdminData` holds `DocRevision` (version info) and `Sdg` (Special Data Groups) for vendor extensions. SDGs use GID-based keys with nested `SD`/`SDG` values.

**Rupa mapping**:
- Annotations `#[...]` = structured metadata (like SDG GIDs)
- `#[decode(domain)]`/`#[encode(domain)]` = transforming AdminData/SDG to/from Rupa's typed model
- Domain derivation + type reopening = vendor-specific extensions without modifying base domain

**Design refs**: `design/current/examples/extension-data-encoding.md`, `06-extensibility/domain-specific-extensions.md`

### 09 — ECUC Definition-Value Duality

**AUTOSAR**: ECU Configuration has two layers: `EcucModuleDef`/`EcucParamConfContainerDef`/`EcucParameterDef` define the schema (M2-like); `EcucModuleConfigurationValues`/`EcucContainerValue`/`EcucParameterValue` hold actual values (M1-like). The value layer references the definition layer.

**Rupa mapping**:
- Definition types = Rupa M2 types (contributed to a domain)
- Value instances = Rupa M1 instances (using the domain)
- `configClass`/`configVariant` = variant binding times + validation rules
- Container nesting = containment hierarchy with identity

**Design refs**: `06-extensibility/metamodel-support.md`, `07-validation/validation-language.md`

### 10 — References and Reference Bases

**AUTOSAR**: Three reference forms: `REF` (reference by SHORT-NAME-PATH), `TREF` (type reference with DEST), `IREF` (instance reference). `ReferenceBase` provides shorthand for frequently-used package paths. Relative paths (not starting with `/`) resolve via reference bases.

**Rupa mapping**:
- `&Type` = typed reference (DEST is implicit from metamodel)
- `/AUTOSAR/Signals/Brake` = absolute SHORT-NAME-PATH
- `import /PortInterfaces as iface` + `iface/VehicleSpeedInterface` = reference base
- `*` search anchor = unqualified lookup (like AUTOSAR's resolution of short references)

**Design refs**: `03-data-modeling/references-and-paths.md`, `04-modularity/imports-and-dependencies.md`

### 11 — FlatMap

**AUTOSAR**: `FlatMap` contains `FlatInstanceDescriptor`s — a flat list of all instances in the system with unique shortNames, resolving the nested instance-ref structure into a linear list. Used for MCD tools, calibration, measurement.

**Rupa mapping**:
- `.**` (descendant navigation) = traverse entire instance tree
- `::descendants(root)` = get all instances
- `#[transform]` = generate flat representation from nested model
- Pipe chains = filter, name, and project flat descriptors

**Design refs**: `03-data-modeling/references-and-paths.md` (tree builtins), `08-transformation/transformation-language.md`

### 12 — Multilanguage Text

**AUTOSAR**: `MultilanguageLongName` (L-4), `MultiLanguageOverviewParagraph` (L-2) wrap text in language-tagged elements. Every `Identifiable` has optional `longName` and `desc`.

**Rupa mapping**:
- Rupa's i18n support handles language-tagged values
- The unnamed role `..` with language tags maps to the content model

**Design refs**: `09-i18n/internationalization-and-character-set.md`

### 13 — Data Type Mapping

**AUTOSAR**: `DataTypeMappingSet` maps `ApplicationDataType` to `ImplementationDataType`. `CompuMethod` defines conversions (LINEAR, TEXTTABLE, etc.) between internal and physical values.

**Rupa mapping**:
- `#[transform]` functions = type mapping
- Expression functions (`let`) = CompuMethod conversion logic
- Domain derivation = separating application-level and implementation-level type sets

**Design refs**: `08-transformation/transformation-language.md`, `06-extensibility/expression-builtins-reference.md`

## Use Case Details

### 01 — Component Architecture
Full composition example: define `SensorModuleType` with ports, instantiate as `SwComponentPrototype` in a `CompositionSwComponentType`, wire with `AssemblySwConnector` using instance refs. Demonstrates types, archetypes, `/>`, instance refs, paths.

### 02 — Signal Stack
Define the complete signal chain: `SystemSignal` -> `ISignal` -> `ISignalIPdu` (with `ISignalToPduMapping`) -> `Frame`. Validation rules for overlap detection, length consistency. Demonstrates references, validation, pipe chains.

### 03 — ECUC Configuration
Define a BSW module configuration: `EcucModuleDef` with containers and parameters as Rupa types, then `EcucContainerValue` instances. Demonstrates M2/M1 separation, validation, definition-as-schema.

### 04 — Version Migration
Migrate a model from AUTOSAR R22 to R25. Two domains, `using domain ... as`, transform functions bridging structural changes. Demonstrates `#[transform]`, domain derivation, cross-version references.

### 05 — ECU Extract with Overlays
Import a system model, apply ECU-specific overlay (modify signal lengths, add vendor SDG extensions). Demonstrates `|=` merge, path-block modification, `#[decode]`/`#[encode]`, vendor domain derivation.

### 06 — Validation Constraints
Express real AUTOSAR OCL constraints as Rupa validation rules. Port consistency, PDU overlap detection, naming conventions, reverse reference checks. Demonstrates `#[rule]`, `->`, `::referrers`, hierarchical rule IDs.

### 07 — Service Interface Deployment (AP)
Define AP `ServiceInterface` with events/methods/fields, `Machine`, execution manifest. Same Rupa patterns (types, archetypes, instance refs) applied to AP-specific types. Demonstrates platform-neutrality of Rupa features.

## Relationship to Existing Material

| Artifact | Status |
|----------|--------|
| `design/transient/poc-autosar-use-cases.md` | **Superseded** by `autosar/use-cases/`. Remove or mark as historical. |
| `design/transient/research/autosar-domain-research.md` | **Remains** as background research. Not duplicated. |
| `design/current/` (canonical design docs) | **Stays domain-neutral**. `autosar/` links to them, never the reverse. |

## Scope Boundaries

**In scope**: All 13 M3/M2 patterns. 7 use cases (6 CP + 1 AP). AUTOSAR R25-11 as reference version.

**Out of scope**:
- Full AUTOSAR M2 metamodel definition in Rupa (implementation work)
- RTE code generation (external tool)
- BSW module C code (not Rupa's domain)
- Complete AP coverage (one use case for pattern demonstration; more can be added later)

## AUTOSAR Version

All examples reference AUTOSAR Classic Platform R25-11 (the version in our MCP specification server). AP use case references Foundation/Adaptive R25-11 concepts.
