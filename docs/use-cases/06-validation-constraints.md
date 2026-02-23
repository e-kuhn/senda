# Use Case 06: Validation Constraints

Translate real AUTOSAR validation constraints -- the kind expressed as OCL
invariants or `[constr_NNNN]` rules in the AUTOSAR TPS specifications -- into
Rupa `#[rule]` functions. This use case goes beyond the signal-stack rules in
Use Case 02 by covering port-interface consistency, PDU-to-frame overlap,
naming conventions, and reverse-reference checks that span the entire model
graph. It also demonstrates rule activation at both M1 and M2 levels, selective
suppression with mandatory justification, and hierarchical rule composition.

---

## Scenario

A system integrator maintains an AUTOSAR model with software components,
ports, interfaces, signals, PDUs, and frames. The AUTOSAR specification
imposes dozens of structural constraints that tool vendors typically implement
as hardcoded checks. The integrator wants to:

1. Express those constraints as Rupa validation rules so they are visible,
   versionable, and extensible.
2. Activate them by category (e.g., all `autosar::port` rules) at the project
   level.
3. Suppress specific rules on legacy elements with auditable justification.
4. Attach constraints to type definitions (M2) so every instance is validated
   automatically without per-project opt-in.

The constraints below are modeled after real AUTOSAR specification items:
`[constr_3009]` (overlapping ISignals), `[constr_3010]` (IPdu length exceeded),
`[constr_3012]` (overlapping PDUs in frames), `[constr_3013]` (frame length
exceeded), `[constr_3514]` (no duplicate ISignal references), and the naming
and port-consistency rules from TPS_SoftwareComponentTemplate.

---

## ARXML Baseline

AUTOSAR constraints are documented as prose with OCL-like invariants. A
representative sample (abbreviated):

```
[constr_3009] Overlapping of ISignals is prohibited
  context: ISignalIPdu
  The bit ranges of ISignalToIPduMappings within the same ISignalIPdu
  shall not overlap.

[constr_3010] ISignalIPdu shall not be exceeded
  context: ISignalIPdu
  For each ISignalToIPduMapping, startPosition + iSignal.length
  shall not exceed the ISignalIPdu.length (in bits).

[constr_3012] Overlapping of PDUs is prohibited
  context: Frame
  The bit ranges of PduToFrameMappings within the same Frame shall not
  overlap.

[constr_3514] No two ISignalToIPduMappings shall reference the identical
              ISignal in the scope of one System.
  context: System

[constr_1202] Supported connections by AssemblySwConnector
  context: AssemblySwConnector
  Provider and requester ports connected by an AssemblySwConnector shall
  be typed by compatible PortInterfaces.

Naming convention (EXP_AIChassis 2.2.1.4):
  ShortNames of AUTOSAR elements shall start with an uppercase letter
  followed by alphanumeric characters or underscores.
```

These constraints live in PDF documents, not in the ARXML schema. Tooling
enforces them inconsistently -- some tools check overlap, others silently
accept it. There is no way for a project to add, customize, or suppress
individual constraints.

---

## Rupa Solution

### Rule Definitions

```rupa
// autosar-constraints.rupa -- validation rules for AUTOSAR structural constraints
using domain autosar-r25;

// ============================================================
// PDU-level constraints (constr_3009, constr_3010)
// ============================================================

// [constr_3009] No overlapping ISignal bit ranges within a PDU.
// Uses combinations(2) to generate all unordered pairs, then checks
// that no two mappings occupy the same bit positions.
#[rule(autosar::pdu::no_signal_overlap)]
#[message(format(
    "ISignal overlap in PDU {}: mappings at bit {} and bit {} collide",
    .shortName,
    m1.startPosition,
    m2.startPosition
))]
let pdu_no_signal_overlap() =
    (. is ISignalIPdu) ->
        .iSignalToPduMappings | combinations(2) | all((m1, m2) =>
            m1.startPosition + m1.iSignalRef.length <= m2.startPosition
            || m2.startPosition + m2.iSignalRef.length <= m1.startPosition
        );

// [constr_3010] Signal mappings must fit within the PDU length.
// PDU .length is in bytes; startPosition and signal .length are in bits.
#[rule(autosar::pdu::signals_within_bounds)]
let pdu_signals_within_bounds() =
    (. is ISignalIPdu) ->
        .iSignalToPduMappings | all(m =>
            m.startPosition + m.iSignalRef.length <= .length * 8
        );

// [constr_3514] No two ISignalToIPduMappings in the system reference the
// same ISignal. This is a global uniqueness check -- uses recursive descent
// from the model root.
#[rule(autosar::pdu::unique_signal_refs)]
let unique_signal_refs() =
    (. is ARPackage && . == ::root(.)) ->
        .**<ISignalToPduMapping>
        | map(m => m.iSignalRef)
        | is_unique();

// ============================================================
// Frame-level constraints (constr_3012, constr_3013)
// ============================================================

// [constr_3012] No overlapping PDU bit ranges within a Frame.
#[rule(autosar::frame::no_pdu_overlap)]
let frame_no_pdu_overlap() =
    (. is Frame) ->
        .pduToFrameMappings | combinations(2) | all((m1, m2) =>
            m1.startPosition + m1.iPduRef.length * 8 <= m2.startPosition
            || m2.startPosition + m2.iPduRef.length * 8 <= m1.startPosition
        );

// [constr_3013] PDU mappings must fit within the frame length.
#[rule(autosar::frame::pdu_within_bounds)]
let frame_pdu_within_bounds() =
    (. is Frame) ->
        .pduToFrameMappings | all(m =>
            m.startPosition + m.iPduRef.length * 8 <= .frameLength * 8
        );

// ============================================================
// Reverse-reference constraints
// ============================================================

// Every ISignal must be referenced by at least one ISignalToPduMapping.
// Uses ::referrers to navigate backward from the signal to its users.
#[rule(autosar::signal::must_be_mapped)]
#[severity(warning)]
#[message(format("ISignal {} is not mapped in any PDU", .shortName))]
let signal_must_be_mapped() =
    (. is ISignal) ->
        ::referrers(.) | any(r => r is ISignalToPduMapping);

// Every ISignalIPdu must be referenced by at least one PduToFrameMapping.
#[rule(autosar::pdu::must_be_framed)]
#[severity(warning)]
#[message(format("PDU {} is not mapped in any Frame", .shortName))]
let pdu_must_be_framed() =
    (. is ISignalIPdu) ->
        ::referrers(.) | any(r => r is PduToFrameMapping);

// ISignal length must match its SystemSignal's length.
#[rule(autosar::signal::length_consistent)]
let signal_length_consistent() =
    (. is ISignal) ->
        .length == .systemSignalRef.length;

// ============================================================
// Port and connector consistency
// ============================================================

// [constr_1202] An AssemblySwConnector must connect ports typed by
// compatible PortInterfaces. At minimum, the provider and requester
// must reference the same PortInterface (or a mapped one).
#[rule(autosar::port::connector_interface_match)]
#[message(format(
    "Connector {} links incompatible interfaces: provider has {}, requester has {}",
    .shortName,
    .provider.portInterface.shortName,
    .requester.portInterface.shortName
))]
let connector_interface_match() =
    (. is AssemblySwConnector) ->
        .provider.portInterface == .requester.portInterface
        || . has .portInterfaceMapping;

// Every required port in a composition must be connected by at least
// one AssemblySwConnector or DelegationSwConnector. Unconnected required
// ports are likely integration errors.
#[rule(autosar::port::required_port_connected)]
#[severity(warning)]
#[message(format("Required port {} is not connected", .shortName))]
let required_port_connected() =
    (. is AbstractRequiredPortPrototype) ->
        ::referrers(.) | any(r =>
            r is AssemblySwConnector || r is DelegationSwConnector
        );

// ============================================================
// Naming conventions (EXP_AIChassis 2.2.1.4)
// ============================================================

// ShortNames must start with an uppercase letter.
#[rule(autosar::naming::pascal_case)]
#[severity(warning)]
#[message(format("ShortName '{}' should start with uppercase", .shortName))]
let pascal_case_shortname() =
    (. is Identifiable) ->
        .shortName | matches("[A-Z][a-zA-Z0-9_]*");

// ShortNames must not contain consecutive underscores.
#[rule(autosar::naming::no_double_underscore)]
#[severity(warning)]
let no_double_underscore() =
    (. is Identifiable) ->
        !(.shortName | matches(".*__.*"));

// Package names should use PascalCase without underscores.
#[rule(autosar::naming::package_style)]
#[severity(hint)]
let package_naming() =
    (. is ARPackage) ->
        .shortName | matches("[A-Z][a-zA-Z0-9]*");
```

### M2-Level Activation

Attach rules directly to type definitions so every instance is validated
automatically. No per-project import or `#[validate]` statement needed.

```rupa
// autosar-types-validated.rupa -- type definitions with built-in validation
using domain autosar-r25;
import "autosar-constraints.rupa";

#[validate(autosar::pdu::no_signal_overlap)]
#[validate(autosar::pdu::signals_within_bounds)]
type ISignalIPdu = ARElement {
    #![validate(autosar::pdu::has_mappings)]
    .length: PositiveInteger;
    .iSignalToPduMappings: ISignalToPduMapping*;
};

#[validate(autosar::frame::no_pdu_overlap)]
#[validate(autosar::frame::pdu_within_bounds)]
type Frame = ARElement {
    .frameLength: PositiveInteger;
    .pduToFrameMappings: PduToFrameMapping*;
};

#[validate(autosar::signal::length_consistent)]
type ISignal = ARElement {
    .length: PositiveInteger;
    .systemSignalRef: &SystemSignal;
};
```

### Project-Level Activation and Suppression

```rupa
// project-validation.rupa -- project-specific activation
using domain autosar-r25;
import "autosar-constraints.rupa";
import "system-model.rupa";

// Activate entire rule categories by prefix
#![validate(autosar::pdu)]
#![validate(autosar::frame)]
#![validate(autosar::signal)]
#![validate(autosar::naming)]

// Activate port rules only for the safety-critical composition
#[validate(autosar::port)]
/**<CompositionSwComponentType>[.shortName | matches("Safety.*")];
```

### Suppression

```rupa
// legacy-signals.rupa -- legacy elements that intentionally violate rules
using domain autosar-r25;
import "autosar-constraints.rupa";

// Legacy signal has mismatched length -- accepted for backward compatibility
#[suppress(autosar::signal::length_consistent,
           reason = "Retained for R19 backward compatibility; mismatch is intentional")]
ISignal LegacyBrake_I {
    .length = 8;
    .systemSignalRef = /AUTOSAR/Signals/BrakePedalPosition;  // length = 12
}

// Legacy package uses snake_case naming
#[suppress(autosar::naming, reason = "Pre-R22 naming convention; migration deferred")]
ARPackage legacy_signals {
    SystemSignal engine_speed { .length = 16; }
    SystemSignal throttle_pos { .length = 12; }
}
```

### Diagnostic Output

```
error[E0147]: validation rule `autosar::pdu::no_signal_overlap` failed
  --> comm.rupa:18:5
   |
18 |         ISignalToPduMapping Speed_Map {
   |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   = note: ISignal overlap in PDU EngineIPdu: mappings at bit 0 and bit 12 collide
   = note: Speed_Map occupies bits [0, 16), Throttle_Map occupies bits [12, 24)
   = help: adjust startPosition of Throttle_Map to 16 or higher

warning[W0032]: validation rule `autosar::signal::must_be_mapped` failed
  --> signals.rupa:8:5
   |
 8 |     SystemSignal SteeringAngle {
   |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^
   = note: ISignal SteeringAngle is not mapped in any PDU
   = help: add an ISignalToPduMapping referencing this signal, or remove it
```

---

## Key Features Demonstrated

| Feature | Where it appears |
|---------|-----------------|
| **`#[rule]` with hierarchical IDs** | `autosar::pdu::no_signal_overlap`, `autosar::naming::pascal_case` -- enables prefix-based activation |
| **Self-guarding (`->`)** | Every rule uses `(. is Type) ->` to scope itself; vacuously true for non-matching objects |
| **Reverse navigation (`::referrers`)** | `signal_must_be_mapped` and `required_port_connected` -- navigate incoming references without tree walks |
| **Collection predicates** | `\| all(...)`, `\| any(...)`, `\| combinations(2)`, `\| is_unique()` for pairwise and aggregate checks |
| **Pipe expressions** | `\| map(m => m.iSignalRef) \| is_unique()` chains operations fluently |
| **Recursive descent (`.**`)** | `.**<ISignalToPduMapping>` for system-wide uniqueness check |
| **Structural guards (`has`)** | `\|\| . has .portInterfaceMapping` for optional role checking |
| **`#[message]` with `format`** | Custom diagnostics with interpolated context values |
| **`#[severity]` ladder** | `error` (default), `warning` for unused signals, `hint` for style rules |
| **M2-level `#[validate]`** | Rules attached to `ISignalIPdu` and `Frame` type definitions |
| **Inner annotations (`#![validate]`)** | File-level activation in project-validation.rupa, inner form in type body |
| **`#[suppress]` with `reason`** | Per-instance exemption with mandatory justification |
| **Prefix-based activation** | `#[validate(autosar::pdu)]` activates all `autosar::pdu::*` rules |
| **Path/filter activation** | `#[validate] /**<Type>[pred]` activates rules on filtered objects |

---

## Comparison

| Aspect | AUTOSAR OCL/TPS constraints | Rupa validation |
|--------|----------------------------|-----------------|
| **Where constraints live** | PDF documents, not machine-readable | `#[rule]` functions in `.rupa` files, versioned alongside the model |
| **Enforcement** | Tool-vendor-specific; inconsistent across tools | Uniform engine; same rules in LSP and batch build |
| **Customizability** | None -- vendor decides which checks to run | Hierarchical activation: activate by prefix, suppress by path |
| **Extensibility** | Cannot add project-specific constraints | Any `#[rule]` function is a first-class rule; no special hooks needed |
| **Reverse references** | OCL `allInstances()` -- expensive, global | `::referrers(.)` -- index-backed, scoped to visible model |
| **Suppression** | Not possible; workaround is to disable the entire tool check | `#[suppress(path, reason = "...")]` per instance, auditable |
| **Diagnostics** | Tool-dependent error messages | `#[message(format(...))]` with interpolated values; auto-generated traces when omitted |
| **M2 vs M1 activation** | All constraints are implicit in the spec | Explicit choice: M2 `#[validate]` on types for definitional invariants, M1 for project-specific rules |
| **Combinatorial checks** | Manual OCL with `forAll` and nested iterators | `combinations(2) \| all(...)` -- declarative pairwise checks |
| **Global uniqueness** | `allInstances()->isUnique()` | `.**<Type> \| map(...) \| is_unique()` -- bounded by containment scope |

The fundamental shift is that validation moves from opaque tool behavior into
the model language itself. Constraints become first-class artifacts that can be
read, reviewed, versioned, tested, and selectively applied -- the same workflow
as the model data they govern.
