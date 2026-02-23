# ECUC Transformation Showcase Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite pattern 09 (`autosar/patterns/09-ecuc-definition-value.md`) to showcase ECUC's "metamodel-as-data" architecture using Rupa's `#[decode]`/`#[encode]`/`#[transform]` pipeline.

**Architecture:** The document tells a pipeline story: ECUC definitions (ordinary `autosar-25-11` instances) are decoded into a typed domain via the M3 API, generic ECUC values are transformed into typed instances, and the encode pipeline proves round-trip fidelity. Materialized views show pipeline output as plain Rupa.

**Design doc:** `docs/plans/2026-02-17-ecuc-transformation-design.md`

**Key reference files:**
- Existing pattern to replace: `autosar/patterns/09-ecuc-definition-value.md`
- Pattern structure convention: see any sibling pattern (e.g., `08-admin-data-and-sdg.md`)
- Transformation language: `design/current/08-transformation/transformation-language.md`
- M3 API: `design/current/06-extensibility/m3-api-reference.md`
- Extension data encoding example: `design/current/examples/extension-data-encoding.md`
- Metamodel support: `design/current/06-extensibility/metamodel-support.md`

---

### Task 1: Write opening sections

**Files:**
- Modify: `autosar/patterns/09-ecuc-definition-value.md` (full rewrite)

**Step 1: Write the title, intro paragraph, and AUTOSAR Concept section**

Replace the entire file. The new document starts with:

- **Title**: `# Pattern 09: ECUC Definition-Value — Transformation Pipeline`
- **Intro paragraph**: One paragraph explaining that this pattern maps AUTOSAR's two-layer ECUC architecture onto Rupa's `#[decode]`/`#[encode]`/`#[transform]` pipeline, demonstrating how metamodel data living at the model level can be dynamically promoted into typed domains.
- **AUTOSAR Concept section**: Reuse/condense the two-layer architecture explanation from the old doc — definition layer (what can be configured) and value layer (actual configuration). Keep the ASCII hierarchy diagrams for both layers. Keep it concise — the reader needs the AUTOSAR context but the star of this pattern is the pipeline.

**Step 2: Write "The Insight" section**

New section after AUTOSAR Concept:

```markdown
## The Insight: Metamodel as Data

ECUC is unusual: the metamodel (definitions) and model (values) are both
expressed as data in the same format. An `EcucModuleDef` XML element is
structurally identical to any other ARXML element — it's not a schema file
or a separate metalanguage. The `DEFINITION-REF` on every value element
is a manual schema-conformance link because ARXML has no type system to
provide one automatically.

In Rupa, this pattern maps directly to the transformation pipeline:

1. ECUC definition types (`EcucModuleDef`, `EcucParamConfContainerDef`, etc.)
   are ordinary types in the `autosar-25-11` domain
2. An NvM definition file creates *instances* of these types — the metamodel
   is just M1 data
3. A `#[decode(domain)]` pipeline reads this data and dynamically produces
   a typed `ecuc-nvm` domain via the M3 API
4. A `#[transform]` pipeline maps generic ECUC values onto the generated types
5. A `#[encode(domain)]` pipeline serializes the types back to definition
   data, proving round-trip fidelity
```

**Step 3: Write "Pipeline Overview" section**

Include an ASCII pipeline diagram showing:
- `definition.rupa` → `#[decode(domain)]` → `ecuc-nvm` domain (with `decoded-domain.rupa` materialized view branching off)
- `values.rupa` → `#[transform]` → typed instances (with `decoded-values.rupa` materialized view branching off)
- `ecuc-nvm` domain → `#[encode(domain)]` → `EcucModuleDef` instances (round-trip)

Include a file table listing all seven files and their roles.

**Step 4: Commit**

```
git add autosar/patterns/09-ecuc-definition-value.md
git commit -m "refactor(pattern-09): rewrite opening with transformation pipeline framing"
```

---

### Task 2: Write `definition.rupa` and `decode.rupa` code sections

**Files:**
- Modify: `autosar/patterns/09-ecuc-definition-value.md`

**Step 1: Write the `definition.rupa` section**

Section header: `### Step 1: ECUC Definition as Data — `definition.rupa``

Brief narrative lead-in: this is the "aha" moment — the NvM definition isn't types, it's instances of `autosar-25-11::EcucModuleDef`. In ARXML this is `AUTOSAR_MOD_ECUConfigurationParameters.arxml`.

Code block: `EcucModuleDef NvM { ... }` with `NvMBlockDescriptor` container containing `NvMNvramBlockIdentifier`, `NvMNvBlockLength`, `NvMBlockUseCrc`, `NvMBlockManagementType` parameter definitions. Use content from design doc section 4a.

After the code block, one paragraph noting: all parameter constraints (min/max, enum literals, multiplicity) are expressed as role values on definition instances. The metamodel is data.

**Step 2: Write the `decode.rupa` section**

Section header: `### Step 2: Definitions Become Types — `decode.rupa``

Brief narrative lead-in: the decode pipeline reads definition data and builds a typed domain via the M3 API. Phase 1 creates type and enum shells; Phase 2 adds roles with proper types and constraints.

Code block: Full decode pipeline with:
- Phase 1: `create_container_types` — walks `EcucParamConfContainerDef` instances, calls `::create_type`, `::set_tag`, `::register_type`
- Phase 1: `create_enum_types` — walks `EcucEnumerationParamDef` instances, calls `::create_enum`, `::add_enum_value`
- Phase 2: `add_parameter_roles` — for each container def, creates typed roles from parameter defs using `match` on definition type (integer → `::create_primitive` + `::set_range`, boolean → `::boolean`, etc.)
- Phase 2: `create_module_type` — creates the top-level module type with container roles

Use content from design doc section 4b.

After the code block, one paragraph noting: the M3 API calls mirror the ECUC definition structure exactly — each `EcucIntegerParamDef` with min/max becomes `::set_range`, each enumeration becomes `::add_enum_value`. The definition data drives the type construction.

**Step 3: Commit**

```
git add autosar/patterns/09-ecuc-definition-value.md
git commit -m "feat(pattern-09): add definition data and decode pipeline sections"
```

---

### Task 3: Write materialized domain, values, and transform sections

**Files:**
- Modify: `autosar/patterns/09-ecuc-definition-value.md`

**Step 1: Write the `decoded-domain.rupa` section**

Section header: `### Step 3: The Generated Domain — `decoded-domain.rupa``

Brief narrative lead-in: this materialized view shows what the decode pipeline produced, expressed as hand-written Rupa. This file is not pipeline input — it's documentation.

Code block: The `ecuc-nvm` domain with `NvMNvramBlockIdentifier` (`#[range(2, 65535)]`), `NvMNvBlockLength` (`#[range(1, 65535)]`), `NvMBlockManagementType` enum, `NvMBlockDescriptor` composite, and `NvM` module type. Use content from design doc section 4c.

After the code block, note that role names match ECUC parameter names directly (`.NvMNvramBlockIdentifier`) — the decode pipeline uses the definition's name as both type name and role name, faithful to ECUC conventions.

**Step 2: Write the `values.rupa` section**

Section header: `### Step 4: Configuration Values as Generic Data — `values.rupa``

Brief narrative lead-in: the integrator's NvM configuration, expressed as generic ECUC data. All parameter values are strings; the `definitionRef` is the only thing that gives them meaning.

Code block: `EcucModuleConfigurationValues NvM { ... }` with two container values (`NvMBlock_AppData`, `NvMBlock_Calibration`), each containing `EcucNumericalParamValue` and `EcucTextualParamValue` instances with `definitionRef` and string `value`. Use content from design doc section 4d.

**Step 3: Write the `transform.rupa` section**

Section header: `### Step 5: Values Become Typed Instances — `transform.rupa``

Brief narrative lead-in: the transform reads generic ECUC values, uses `definitionRef` to resolve which generated type and role to target, and parses string values into proper typed values.

Code block: Full transform pipeline with:
- `param` helper function
- `transform_module` — dispatches containers by definition name
- `transform_container` — matches on definition type to convert string values (`to_integer`, `to_boolean`, `to_float`, or passthrough for enums)
- Drop functions for consumed generic types

Use content from design doc section 4e.

After the code block, note the key move: `definitionRef` at transform time does what `DEFINITION-REF` does at ARXML validation time — it bridges the two layers.

**Step 4: Commit**

```
git add autosar/patterns/09-ecuc-definition-value.md
git commit -m "feat(pattern-09): add generated domain, values, and transform sections"
```

---

### Task 4: Write decoded values, encode, comparison, and design reference

**Files:**
- Modify: `autosar/patterns/09-ecuc-definition-value.md`

**Step 1: Write the `decoded-values.rupa` section**

Section header: `### Step 6: The Typed Result — `decoded-values.rupa``

Brief narrative lead-in: materialized view of the transform output. Compare this to `values.rupa` — no `definitionRef` indirection, no string-encoded values, no redundant type annotations.

Code block: Typed NvM instances using `ecuc-nvm` domain types. Use content from design doc section 4f.

**Step 2: Write the `encode.rupa` section**

Section header: `### Step 7: Types Become Definitions Again — `encode.rupa``

Brief narrative lead-in: the reverse direction — `#[encode(domain)]` reads the dynamically-created types via `::type` reflection and serializes them back as `EcucModuleDef` instances. The output should match `definition.rupa` structurally, proving round-trip fidelity.

Code block: Encode pipeline with `encode_module` and `encode_container_def` helper. Use content from design doc section 4g.

**Step 3: Write Structural Comparison section**

Section header: `## Structural Comparison`

A table comparing the ARXML approach vs the Rupa transformation pipeline:

| Concern | ARXML | Rupa Pipeline |
|---------|-------|---------------|
| Schema representation | `EcucModuleDef` XML data + manual `DEFINITION-REF` | Same data decoded into typed domain via M3 API |
| Parameter type safety | String values validated by external tooling | Typed roles with `#[range]` enforced at M2 |
| Schema-data link | Explicit `DEFINITION-REF` on every value element | Implicit — instances are typed by the generated domain |
| Enumeration safety | String matching against `ECUC-ENUMERATION-LITERAL-DEF` | `enum` types with compile-time checking |
| Round-trip fidelity | N/A (definitions and values are always separate XML) | `#[encode]` reconstructs definitions from types |
| Schema evolution | Edit XML definition files, re-validate all values | Modify definition instances, re-run decode pipeline |

**Step 4: Write Design Reference section**

Section header: `## Design Reference`

Bullet list linking to:
- Transformation language (`design/current/08-transformation/transformation-language.md`): `#[decode]`/`#[encode]`/`#[transform]` pipeline, phase ordering, return vs write mode
- M3 API (`design/current/06-extensibility/m3-api-reference.md`): `::create_type`, `::create_role`, `::set_range`, `::add_enum_value`, `::type`/`::role` reflection properties
- Metamodel support (`design/current/06-extensibility/metamodel-support.md`): M2 type definitions, primitive types, composite types, multiplicity
- Extension data encoding example (`design/current/examples/extension-data-encoding.md`): precedent for `#[encode]`/`#[decode]` round-trip with the same pipeline structure
- AUTOSAR specification (`AUTOSAR_CP_TPS_ECUConfiguration`, R25-11): Section 2.3 (definition metamodel), Section 2.4 (value metamodel)

**Step 5: Commit**

```
git add autosar/patterns/09-ecuc-definition-value.md
git commit -m "feat(pattern-09): complete ECUC transformation showcase with encode round-trip"
```

---

### Task 5: Review and finalize

**Step 1: Read the complete document end-to-end**

Read `autosar/patterns/09-ecuc-definition-value.md` from top to bottom. Check for:
- Narrative flow: does each section follow logically from the previous?
- Code consistency: do type names, role names, and identifiers match across all seven code blocks?
- Pipeline coherence: does `decoded-domain.rupa` actually reflect what `decode.rupa` would produce? Does `decoded-values.rupa` reflect what `transform.rupa` would produce?
- Cross-references: do the design reference links point to real files?

**Step 2: Fix any inconsistencies found**

**Step 3: Final commit if changes were made**

```
git add autosar/patterns/09-ecuc-definition-value.md
git commit -m "fix(pattern-09): address review feedback"
```
