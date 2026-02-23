# AUTOSAR Examples & Use Cases

This folder demonstrates how Rupa maps to real AUTOSAR metamodel patterns and workflows. Every example uses real AUTOSAR type names from the R25-11 specification and Rupa syntax consistent with the canonical design in `design/current/`.

## Audience

- **Engineers** familiar with AUTOSAR: start with [patterns/](patterns/) to see how M3/M2 concepts translate to Rupa
- **Stakeholders** evaluating Rupa: start with [use-cases/](use-cases/) to see end-to-end workflows
- **Language designers**: cross-reference the Design Doc links to verify design coverage

## AUTOSAR Version Scope

- **AUTOSAR R25-11** (Classic Platform + Adaptive Platform Foundation)
- ARXML snippets are abbreviated but structurally correct
- Type names match the AUTOSAR metamodel (e.g., `SwComponentType`, not `CompositeModule`)

## Pattern Index

Each pattern doc maps one AUTOSAR M3/M2 concept to its Rupa equivalent with ARXML side-by-side comparisons.

| # | Pattern | AUTOSAR Concept | Key Rupa Features | Doc |
|---|---------|-----------------|-------------------|-----|
| 01 | Identifiable and Paths | `Referrable.shortName`, `Identifiable`, SHORT-NAME-PATH | `#[id]`, `/` path anchor, cross-role identity | [patterns/01-identifiable-and-paths.md](patterns/01-identifiable-and-paths.md) |
| 02 | Type-Prototype-Archetype | `AtpType`/`AtpPrototype`, `SwComponentPrototype` | `#[archetype]`, `/>` operator | [patterns/02-type-prototype-archetype.md](patterns/02-type-prototype-archetype.md) |
| 03 | Instance References | `AtpInstanceRef`, `PPortInCompositionInstanceRef` | `#[instance_ref]`, `#[context]`, `#[target]`, `/>` | [patterns/03-instance-references.md](patterns/03-instance-references.md) |
| 04 | atpMixed Ordering | `atpMixed` stereotype, `DocumentationBlock` | `#[ordered]`, unnamed role `..`, sequence ops | [patterns/04-atp-mixed-ordering.md](patterns/04-atp-mixed-ordering.md) |
| 05 | Blueprints and Derivation | `AtpBlueprint`, `namePattern`, `BlueprintMapping` | `from` derivation, domain extension, validation | [patterns/05-blueprints-and-derivation.md](patterns/05-blueprints-and-derivation.md) |
| 06 | atpSplitable and Multi-File | `atpSplitable`, `Splitkey`, open packages | `\|=` merge, multi-file composition, imports | [patterns/06-splitable-and-multi-file.md](patterns/06-splitable-and-multi-file.md) |
| 07 | Variation Points | `atpVariation`, `VariationPoint`, `SwSystemconst` | `variant` declarations, `#[variant()]`, `--variant` | [patterns/07-variation-points.md](patterns/07-variation-points.md) |
| 08 | AdminData and SDG | `AdminData`, `SDG`/`SD`, `GID` keys | Annotations, `#[decode]`/`#[encode]`, domain ext. | [patterns/08-admin-data-and-sdg.md](patterns/08-admin-data-and-sdg.md) |
| 09 | ECUC Definition-Value | `EcucModuleDef`, `EcucContainerValue` | M2/M1 separation, domain contribution/consumption | [patterns/09-ecuc-definition-value.md](patterns/09-ecuc-definition-value.md) |
| 10 | References and Ref Bases | REF, TREF, IREF, `REFERENCE-BASE` | `&Type`, typed paths, `import as`, `*` search | [patterns/10-references-and-ref-bases.md](patterns/10-references-and-ref-bases.md) |
| 11 | FlatMap | `FlatMap`, `FlatInstanceDescriptor` | `.**`, `::descendants`, `#[transform]` | [patterns/11-flat-map.md](patterns/11-flat-map.md) |
| 12 | Multilanguage Text | `MultilanguageLongName`, `L-4`/`L-2` | i18n roles, language-keyed access | [patterns/12-multilanguage-text.md](patterns/12-multilanguage-text.md) |
| 13 | Data Type Mapping | `DataTypeMappingSet`, `CompuMethod` | `#[transform]`, expression functions | [patterns/13-data-type-mapping.md](patterns/13-data-type-mapping.md) |

## Use Case Index

Each use case demonstrates an end-to-end workflow with a realistic scenario.

| # | Use Case | Scenario | Features Demonstrated | Doc |
|---|----------|----------|-----------------------|-----|
| 01 | Component Architecture | Braking system with sensor + controller | `#[archetype]`, `/>`, `#[instance_ref]`, connectors | [use-cases/01-component-architecture.md](use-cases/01-component-architecture.md) |
| 02 | Signal Stack | SystemSignal -> ISignal -> IPdu -> Frame | Validation rules, overlap detection, `#[rule]` | [use-cases/02-signal-stack.md](use-cases/02-signal-stack.md) |
| 03 | ECUC Configuration | NvM module definition + values | M2/M1 separation, `#[range]`, cross-param rules | [use-cases/03-ecuc-configuration.md](use-cases/03-ecuc-configuration.md) |
| 04 | Version Migration | R22 to R25 signal model migration | Multi-domain, `#[transform]`, schema evolution | [use-cases/04-version-migration.md](use-cases/04-version-migration.md) |
| 05 | ECU Extract with Overlays | System model + ECU-specific overlay | `\|=` merge, modification ops, vendor SDG | [use-cases/05-ecu-extract-overlay.md](use-cases/05-ecu-extract-overlay.md) |
| 06 | Validation Constraints | AUTOSAR OCL constraints as Rupa rules | `#[rule]`, `::referrers`, activation/suppression | [use-cases/06-validation-constraints.md](use-cases/06-validation-constraints.md) |
| 07 | Service Interface (AP) | Adaptive Platform SOME/IP deployment | AP types, manifests, CP/AP pattern reuse | [use-cases/07-service-interface-deployment.md](use-cases/07-service-interface-deployment.md) |

## Scope

**In scope:**
- Classic Platform (CP) and Adaptive Platform (AP) Foundation metamodel patterns
- M3 stereotypes (`atpType`, `atpPrototype`, `atpVariation`, `atpSplitable`, `atpMixed`, `atpBlueprint`)
- Common workflows: component modeling, signal stacks, ECUC, validation, migration, overlays
- ARXML import/export round-trip considerations

**Out of scope:**
- Full metamodel coverage (thousands of classes) -- these examples cover the ~20 most important patterns
- Runtime behavior modeling (timing, scheduling)
- Specific tool vendor integrations
- AUTOSAR Adaptive Platform services beyond Foundation

## Relationship to Other Artifacts

- **Canonical design**: `design/current/` -- the authoritative Rupa language design. Pattern docs link to specific design decisions.
- **Specification**: `spec/` -- the formal language specification (when available)
- **Historical PoC**: `design/transient/poc-autosar-use-cases.md` -- superseded by this folder
