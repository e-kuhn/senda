# AUTOSAR Examples & Use Cases Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the top-level `autosar/` folder with 13 pattern docs, 7 use-case docs, and an index README — mapping Rupa language features to concrete AUTOSAR M3/M2 patterns.

**Architecture:** Each pattern doc follows the template: AUTOSAR Concept (with ARXML) → Rupa Mapping (M2 + M1) → Worked Example → Edge Cases → Design Reference. Each use-case doc follows: Scenario → ARXML Baseline → Rupa Solution → Key Features → Comparison. The README is the master index linking everything together.

**Tech Stack:** Markdown documentation. Real AUTOSAR type names (SwComponentType, PPortPrototype, etc.). Rupa syntax from canonical design docs. ARXML snippets from AUTOSAR R25-11 specs (via MCP server `search_autosar`).

---

## Key Resources

Before writing any document, the author must be familiar with:

- **Design doc (this plan's source)**: `docs/plans/2026-02-17-autosar-examples-design.md`
- **Existing PoC** (reference, being superseded): `design/transient/poc-autosar-use-cases.md`
- **Existing research**: `design/transient/research/autosar-domain-research.md`
- **Canonical design docs**: `design/current/` (the authoritative Rupa design decisions)
- **AUTOSAR MCP server**: Use `search_autosar` tool to fetch real ARXML snippets and class tables
- **Pattern doc template** and **use-case doc template**: defined in the design doc above

## Conventions

- Use **real AUTOSAR names** in all examples (SwComponentType, not CompositeModule)
- All Rupa code must be **consistent with canonical design docs** — check `design/current/` for the feature being exercised
- ARXML snippets should be **abbreviated but structurally correct** — enough to show the pattern, not a full 200-line element
- Each doc is **self-contained** but links to related pattern/use-case docs
- **Commit after each batch** (not after each file)

---

### Task 1: Scaffold folder structure

**Files:**
- Create: `autosar/patterns/` (directory)
- Create: `autosar/use-cases/` (directory)

**Step 1: Create directories**

```bash
mkdir -p /Users/ekuhn/CLionProjects/rupa-spec/autosar/patterns
mkdir -p /Users/ekuhn/CLionProjects/rupa-spec/autosar/use-cases
```

**Step 2: Create placeholder .gitkeep files**

```bash
touch /Users/ekuhn/CLionProjects/rupa-spec/autosar/patterns/.gitkeep
touch /Users/ekuhn/CLionProjects/rupa-spec/autosar/use-cases/.gitkeep
```

**Step 3: Commit scaffold**

```bash
git add autosar/
git commit -m "chore: scaffold autosar/ folder structure"
```

---

### Task 2: Write pattern 01 — Identifiable and Paths

**Files:**
- Create: `autosar/patterns/01-identifiable-and-paths.md`
- Read: `design/current/03-data-modeling/references-and-paths.md`
- Read: `design/current/03-data-modeling/cross-role-identity-uniqueness.md`

**Step 1: Read the canonical design docs**

Read the two design docs listed above. Extract the Rupa path syntax, anchors, identity navigation rules.

**Step 2: Fetch AUTOSAR ARXML examples via MCP**

Query `search_autosar` for:
- "Identifiable shortName Referrable SHORT-NAME-PATH" to get the base class structure
- "reference SHORT-NAME-PATH DEST attribute" to get reference XML examples

**Step 3: Write the pattern doc**

Follow the pattern template. Cover:
- **AUTOSAR Concept**: `Referrable.shortName`, `Identifiable` (adds longName, desc, adminData), SHORT-NAME-PATH resolution, DEST attribute on references. Show ARXML for an ARPackage with nested elements and a reference using SHORT-NAME-PATH.
- **Rupa Mapping**: `#[id(N)]` annotation = shortName. `/` path anchor = SHORT-NAME-PATH. Cross-role identity uniqueness = AUTOSAR shortName uniqueness within parent. Non-identifiable objects are path-transparent. `DEST` is unnecessary (type known from metamodel).
- **Worked Example**: Define `ARPackage` and `SystemSignal` types with `#[id]`. Instantiate a package hierarchy. Show path resolution. Show ARXML side-by-side.
- **Edge Cases**: AUTOSAR allows shortName to be absent on non-Identifiable elements; Rupa requires `#[id]` to be explicit. AUTOSAR's DEST attribute provides type information redundant with the metamodel.
- **Design Reference**: Link to `design/current/03-data-modeling/references-and-paths.md` and `cross-role-identity-uniqueness.md`.

**Step 4: Verify consistency**

Check that all Rupa syntax in the doc matches the canonical design docs. Specifically verify:
- Path anchor syntax (`/`, `.`, `^`, `*`)
- `#[id]` annotation syntax
- Cross-role identity uniqueness rule

---

### Task 3: Write pattern 02 — Type-Prototype-Archetype

**Files:**
- Create: `autosar/patterns/02-type-prototype-archetype.md`
- Read: `design/current/03-data-modeling/instance-references-and-archetypes.md`

**Step 1: Read the canonical design doc**

Read the instance-references-and-archetypes doc. Extract `#[archetype]` semantics, `/>` operator, constraints.

**Step 2: Fetch AUTOSAR examples via MCP**

Query `search_autosar` for:
- "SwComponentType SwComponentPrototype AtpType AtpPrototype" for the type-prototype pattern
- "CompositionSwComponentType component aggregation" for the composition example

**Step 3: Write the pattern doc**

Cover:
- **AUTOSAR Concept**: `AtpType`/`AtpPrototype` M3 pattern. `SwComponentType` defines ports/behavior; `SwComponentPrototype` instantiates it within a `CompositionSwComponentType`. Prototype doesn't contain ports — references its type. Show ARXML for a composition with component prototypes.
- **Rupa Mapping**: `#[archetype]` on a reference role = AtpType/AtpPrototype link. `/>` operator = navigating from prototype into type structure. One `#[archetype]` per type. Must be required single-valued reference.
- **Worked Example**: Define `SwComponentType` with ports, `SwComponentPrototype` with `#[archetype] .type`, `CompositionSwComponentType` containing prototypes. Show `/>` navigation.
- **Edge Cases**: Circular archetype chains = compile error. Multiple archetypes not supported (one per type). `::children` on a prototype returns prototype's own children, not archetype's.
- **Design Reference**: Link to `design/current/03-data-modeling/instance-references-and-archetypes.md`.

---

### Task 4: Write pattern 03 — Instance References

**Files:**
- Create: `autosar/patterns/03-instance-references.md`
- Read: `design/current/03-data-modeling/instance-references-and-archetypes.md`

**Step 1: Read canonical design doc (same as task 3, deeper focus on instance refs)**

Focus on `#[instance_ref]`, `#[context]`, `#[target]`, `::instance_ref` M3 type, narrowing rules.

**Step 2: Fetch AUTOSAR examples via MCP**

Query `search_autosar` for:
- "PPortInCompositionInstanceRef contextComponent targetPPort" for concrete InstanceRef classes
- "AtpInstanceRef atpContextElement atpTarget" for the abstract pattern
- "VariableDataPrototypeInSystemInstanceRef" for a multi-context example

**Step 3: Write the pattern doc**

Cover:
- **AUTOSAR Concept**: `AtpInstanceRef` abstract class with `atpContextElement` (ordered) and `atpTarget`. Concrete subclasses: `PPortInCompositionInstanceRef`, `RPortInCompositionInstanceRef`, `VariableInAtomicSWCTypeInstanceRef`, `ComponentInCompositionInstanceRef`. Each has specific context and target types. Show ARXML for an assembly connector using PPortInCompositionInstanceRef.
- **Rupa Mapping**: `#[instance_ref]` type = AtpInstanceRef subclass. `#[context]` roles = ordered context chain. `#[target]` role = target prototype. `/>` operator constructs the chain. `::instance_ref` M3 type narrows to M2 at assignment. Non-annotated roles (blueprintRef, extensionData) are excluded from chain.
- **Worked Example**: Define `PPortInCompositionInstanceRef` and `RPortInCompositionInstanceRef` as `#[instance_ref]` types. Use them in `AssemblySwConnector`. Show `/>` path construction and narrowing.
- **Edge Cases**: Multi-valued `#[context]` for variable-depth chains. Multiple M2 types with same context chain but different target types. Inherited non-lookup roles from base types.
- **Design Reference**: Link to `design/current/03-data-modeling/instance-references-and-archetypes.md`.

---

### Task 5: Write patterns 04-06 (parallel batch)

These three patterns are independent of each other and can be written in parallel.

**Files:**
- Create: `autosar/patterns/04-atp-mixed-ordering.md`
- Create: `autosar/patterns/05-blueprints-and-derivation.md`
- Create: `autosar/patterns/06-splitable-and-multi-file.md`

#### 04 — atpMixed Ordering

- Read: `design/current/03-data-modeling/cross-role-ordering-and-unnamed-roles.md`
- Fetch AUTOSAR: "atpMixed Desc Introduction mixed content ordering"
- Cover: `atpMixed` stereotype, cross-role ordering, `#[ordered]` on types, unnamed role `..`, sequence concatenation, `|=` error on ordered types. Show ARXML for a `Desc` element with interleaved text and structured children.

#### 05 — Blueprints and Derivation

- Read: `design/current/06-extensibility/domain-specific-extensions.md`, `design/current/04-modularity/model-composition.md`
- Fetch AUTOSAR: "AtpBlueprint AtpBlueprintable namePattern BlueprintMapping derivation"
- Cover: Blueprint mechanism, `namePattern`, `BlueprintMapping` tracking, CATEGORY=BLUEPRINT packages. Map to domain derivation, type reopening, validation rules for conformance.

#### 06 — atpSplitable and Multi-File

- Read: `design/current/04-modularity/file-organization.md`, `design/current/04-modularity/model-composition.md`, `design/current/05-operations/modification-operations.md`
- Fetch AUTOSAR: "atpSplitable Splitkey ARPackage open set multiple files"
- Cover: `atpSplitable` stereotype, `Splitkey` attributes, open packages. Map to multi-file composition, `|=` merge, import system. Show two ARXML files contributing to same package, then Rupa equivalent.

**Commit after all three are written:**

```bash
git add autosar/patterns/04-atp-mixed-ordering.md autosar/patterns/05-blueprints-and-derivation.md autosar/patterns/06-splitable-and-multi-file.md
git commit -m "docs(autosar): add patterns 04-06 — ordering, blueprints, multi-file"
```

---

### Task 6: Write patterns 07-09 (parallel batch)

**Files:**
- Create: `autosar/patterns/07-variation-points.md`
- Create: `autosar/patterns/08-admin-data-and-sdg.md`
- Create: `autosar/patterns/09-ecuc-definition-value.md`

#### 07 — Variation Points

- Read: `design/current/03-data-modeling/variants-and-configurations.md`
- Fetch AUTOSAR: "atpVariation VariationPoint SwSystemconst binding time postBuild preCompile"
- Cover: `atpVariation` stereotype, `VariationPoint`, `SwSystemconst`, binding times. Map to `variant` declarations, `#[variant()]` annotations, `--variant` CLI flag. Show ARXML with conditional component existence.

#### 08 — AdminData and SDG

- Read: `design/current/examples/extension-data-encoding.md`, `design/current/06-extensibility/domain-specific-extensions.md`
- Fetch AUTOSAR: "AdminData SDG SdgContents Sdg GID special data group"
- Cover: `AdminData` structure, `SDG`/`SD` nesting, `GID` keys, `SdgCaption`. Map to annotations, `#[decode]`/`#[encode]` for SDG transformation, domain derivation for vendor extensions. Show ARXML AdminData with nested SDGs, then Rupa equivalent.

#### 09 — ECUC Definition-Value

- Read: `design/current/06-extensibility/metamodel-support.md`, `design/current/07-validation/validation-language.md`
- Fetch AUTOSAR: "EcucModuleDef EcucContainerDef EcucParameterDef EcucContainerValue parameter definition value"
- Cover: Two-layer ECUC architecture (definition = schema, value = data). Map to M2 types (domain contribution) and M1 instances (domain consumption). Show ARXML for a simple module definition + values, then Rupa equivalent.

**Commit after all three:**

```bash
git add autosar/patterns/07-variation-points.md autosar/patterns/08-admin-data-and-sdg.md autosar/patterns/09-ecuc-definition-value.md
git commit -m "docs(autosar): add patterns 07-09 — variants, SDG, ECUC"
```

---

### Task 7: Write patterns 10-13 (parallel batch)

**Files:**
- Create: `autosar/patterns/10-references-and-ref-bases.md`
- Create: `autosar/patterns/11-flat-map.md`
- Create: `autosar/patterns/12-multilanguage-text.md`
- Create: `autosar/patterns/13-data-type-mapping.md`

#### 10 — References and Reference Bases

- Read: `design/current/03-data-modeling/references-and-paths.md`, `design/current/04-modularity/imports-and-dependencies.md`
- Fetch AUTOSAR: "reference REF TREF IREF ReferenceBase BASE relative path DEST"
- Cover: Three AUTOSAR reference kinds (REF, TREF, IREF), DEST attribute, ReferenceBase mechanism. Map to `&Type`, typed paths, `import as`, `*` search.

#### 11 — FlatMap

- Read: `design/current/03-data-modeling/references-and-paths.md` (tree builtins), `design/current/08-transformation/transformation-language.md`
- Fetch AUTOSAR: "FlatMap FlatInstanceDescriptor flat representation unique name MCD"
- Cover: FlatMap purpose (MCD tools, calibration). Map to `.**` descendant navigation, `::descendants`, transform functions for flattening.

#### 12 — Multilanguage Text

- Read: `design/current/09-i18n/internationalization-and-character-set.md`
- Fetch AUTOSAR: "MultilanguageLongName L-4 L-2 MultiLanguageOverviewParagraph desc longName"
- Cover: AUTOSAR's language-tagged text wrapping. Map to Rupa i18n support.

#### 13 — Data Type Mapping

- Read: `design/current/08-transformation/transformation-language.md`, `design/current/06-extensibility/expression-builtins-reference.md`
- Fetch AUTOSAR: "DataTypeMappingSet ApplicationDataType ImplementationDataType CompuMethod LINEAR TEXTTABLE"
- Cover: DataTypeMappingSet, CompuMethod categories. Map to `#[transform]`, expression functions, domain derivation.

**Commit after all four:**

```bash
git add autosar/patterns/10-references-and-ref-bases.md autosar/patterns/11-flat-map.md autosar/patterns/12-multilanguage-text.md autosar/patterns/13-data-type-mapping.md
git commit -m "docs(autosar): add patterns 10-13 — references, flatmap, i18n, type mapping"
```

---

### Task 8: Write use case 01 — Component Architecture

**Files:**
- Create: `autosar/use-cases/01-component-architecture.md`
- Read: Pattern docs 01, 02, 03
- Read: `design/transient/poc-autosar-use-cases.md` sections 2-3 (reuse and improve)

**Step 1: Fetch AUTOSAR examples via MCP**

Query for complete composition example: SwComponentType with ports, SwComponentPrototype, AssemblySwConnector, DelegationSwConnector.

**Step 2: Write the use-case doc**

Follow the use-case template. Scenario: define a braking system with sensor and controller components, connected via assembly connectors.

**Step 3: Verify Rupa code consistency**

Check all Rupa syntax against design docs. Especially verify `#[archetype]`, `/>`, `#[instance_ref]` usage.

---

### Task 9: Write use case 02 — Signal Stack

**Files:**
- Create: `autosar/use-cases/02-signal-stack.md`
- Read: `design/transient/poc-autosar-use-cases.md` sections 3-4 (reuse and improve)

Scenario: Define complete signal chain (SystemSignal -> ISignal -> ISignalIPdu -> Frame) with validation rules for overlap detection and length consistency.

---

### Task 10: Write use cases 03-05 (parallel batch)

**Files:**
- Create: `autosar/use-cases/03-ecuc-configuration.md`
- Create: `autosar/use-cases/04-version-migration.md`
- Create: `autosar/use-cases/05-ecu-extract-overlay.md`

#### 03 — ECUC Configuration
Scenario: Configure an NvM (Non-Volatile Memory Manager) module. Define EcucModuleDef types, then fill in values. Show M2/M1 separation.

#### 04 — Version Migration
Scenario: Migrate a signal model from AUTOSAR R22 to R25. Use two domains, transform functions, cross-version type mapping.
Reference: `design/transient/poc-autosar-use-cases.md` sections 5, 8.

#### 05 — ECU Extract with Overlays
Scenario: Import a system model, create ECU-specific overlay. Modify signal properties, add vendor SDG extensions.
Reference: `design/transient/poc-autosar-use-cases.md` section 6.

**Commit after all three:**

```bash
git add autosar/use-cases/03-ecuc-configuration.md autosar/use-cases/04-version-migration.md autosar/use-cases/05-ecu-extract-overlay.md
git commit -m "docs(autosar): add use cases 03-05 — ECUC, migration, overlays"
```

---

### Task 11: Write use cases 06-07 (parallel batch)

**Files:**
- Create: `autosar/use-cases/06-validation-constraints.md`
- Create: `autosar/use-cases/07-service-interface-deployment.md`

#### 06 — Validation Constraints
Scenario: Express real AUTOSAR OCL constraints as Rupa validation rules. Cover port consistency, PDU overlap, naming conventions, reverse reference checks.
Reference: `design/transient/poc-autosar-use-cases.md` section 4.

#### 07 — Service Interface Deployment (AP)
Scenario: Define an AP ServiceInterface with events/methods/fields. Define Machine and execution manifest. Show same Rupa patterns with AP-specific types.

**Commit after both:**

```bash
git add autosar/use-cases/06-validation-constraints.md autosar/use-cases/07-service-interface-deployment.md
git commit -m "docs(autosar): add use cases 06-07 — validation, AP service interfaces"
```

---

### Task 12: Write README.md (index)

**Files:**
- Create: `autosar/README.md`

**Step 1: Write the README**

Include:
- Purpose statement
- Audience guide ("engineers start with patterns/, stakeholders start with use-cases/")
- AUTOSAR version scope (R25-11, CP + AP Foundation)
- Master mapping table: all 20 patterns/concepts with AUTOSAR name → Rupa feature → pattern doc link → design doc link
- Use case summary table: scenario → features demonstrated → doc link
- Scope boundaries (what's in, what's out)
- Relationship to other project artifacts

**Step 2: Verify all links**

Check every internal link in the README points to an existing file.

**Step 3: Commit**

```bash
git add autosar/README.md
git commit -m "docs(autosar): add README with master index and mapping tables"
```

---

### Task 13: Remove .gitkeep files and final cleanup

**Step 1: Remove placeholder files**

```bash
rm autosar/patterns/.gitkeep autosar/use-cases/.gitkeep
```

**Step 2: Mark PoC as superseded**

Add a note at the top of `design/transient/poc-autosar-use-cases.md`:

```markdown
> **Status: Superseded** by `autosar/use-cases/`. This file is retained for historical reference.
```

**Step 3: Final commit**

```bash
git add -A autosar/ design/transient/poc-autosar-use-cases.md
git commit -m "docs(autosar): finalize folder, mark PoC as superseded"
```

---

## Task Dependency Graph

```
Task 1 (scaffold)
  ├── Task 2 (pattern 01) ─┐
  ├── Task 3 (pattern 02) ─┤
  ├── Task 4 (pattern 03) ─┤── commit patterns 01-03
  │                         │
  ├── Task 5 (patterns 04-06, parallel) ── commit
  ├── Task 6 (patterns 07-09, parallel) ── commit
  ├── Task 7 (patterns 10-13, parallel) ── commit
  │                         │
  ├── Task 8 (use case 01) ─┤ (depends on patterns 01-03)
  ├── Task 9 (use case 02) ─┤
  ├── Task 10 (use cases 03-05, parallel) ── commit
  ├── Task 11 (use cases 06-07, parallel) ── commit
  │                         │
  └── Task 12 (README) ────── commit (depends on all pattern + use case docs)
      └── Task 13 (cleanup) ── final commit
```

## Estimated Scope

- **13 pattern docs** (~200-400 lines each)
- **7 use-case docs** (~150-300 lines each)
- **1 README** (~100-150 lines)
- **Total**: ~21 documents, ~5000-8000 lines of documentation
