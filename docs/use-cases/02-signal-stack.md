# Use Case 02: Signal Stack

Define the complete AUTOSAR signal chain -- from `SystemSignal` through `ISignal`
and `ISignalIPdu` to `Frame` -- including validation rules for bit-level overlap
detection and length consistency. This is the bread-and-butter of communication
design in AUTOSAR: getting signals packed into PDUs and PDUs packed into frames,
with all the constraints that make the physical layer work.

---

## ARXML Baseline

A minimal signal stack in ARXML for a CAN frame carrying two signals. Abbreviated
for readability -- a real file would include XML namespaces, `ADMIN-DATA`, `DESC`,
and `CATEGORY` on every element.

```xml
<AR-PACKAGES>
  <AR-PACKAGE>
    <SHORT-NAME>Signals</SHORT-NAME>
    <ELEMENTS>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>EngineSpeed</SHORT-NAME>
        <DYNAMIC-LENGTH>false</DYNAMIC-LENGTH>
        <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
        <INIT-VALUE>
          <NUMERICAL-VALUE-SPECIFICATION>
            <VALUE>0</VALUE>
          </NUMERICAL-VALUE-SPECIFICATION>
        </INIT-VALUE>
        <LENGTH>16</LENGTH>
      </SYSTEM-SIGNAL>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>ThrottlePosition</SHORT-NAME>
        <DYNAMIC-LENGTH>false</DYNAMIC-LENGTH>
        <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
        <INIT-VALUE>
          <NUMERICAL-VALUE-SPECIFICATION>
            <VALUE>0</VALUE>
          </NUMERICAL-VALUE-SPECIFICATION>
        </INIT-VALUE>
        <LENGTH>12</LENGTH>
      </SYSTEM-SIGNAL>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>Communication</SHORT-NAME>
    <ELEMENTS>
      <I-SIGNAL>
        <SHORT-NAME>EngineSpeed_I</SHORT-NAME>
        <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
        <LENGTH>16</LENGTH>
        <SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Signals/EngineSpeed</SYSTEM-SIGNAL-REF>
      </I-SIGNAL>
      <I-SIGNAL>
        <SHORT-NAME>ThrottlePosition_I</SHORT-NAME>
        <I-SIGNAL-TYPE>PRIMITIVE</I-SIGNAL-TYPE>
        <LENGTH>12</LENGTH>
        <SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Signals/ThrottlePosition</SYSTEM-SIGNAL-REF>
      </I-SIGNAL>

      <I-SIGNAL-I-PDU>
        <SHORT-NAME>EngineDataIPdu</SHORT-NAME>
        <LENGTH>4</LENGTH>
        <I-SIGNAL-TO-PDU-MAPPINGS>
          <I-SIGNAL-TO-I-PDU-MAPPING>
            <SHORT-NAME>EngineSpeed_Mapping</SHORT-NAME>
            <I-SIGNAL-REF DEST="I-SIGNAL">/Communication/EngineSpeed_I</I-SIGNAL-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>0</START-POSITION>
          </I-SIGNAL-TO-I-PDU-MAPPING>
          <I-SIGNAL-TO-I-PDU-MAPPING>
            <SHORT-NAME>ThrottlePos_Mapping</SHORT-NAME>
            <I-SIGNAL-REF DEST="I-SIGNAL">/Communication/ThrottlePosition_I</I-SIGNAL-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>16</START-POSITION>
          </I-SIGNAL-TO-I-PDU-MAPPING>
        </I-SIGNAL-TO-PDU-MAPPINGS>
      </I-SIGNAL-I-PDU>

      <FRAME>
        <SHORT-NAME>EngineDataFrame</SHORT-NAME>
        <FRAME-LENGTH>8</FRAME-LENGTH>
        <PDU-TO-FRAME-MAPPINGS>
          <PDU-TO-FRAME-MAPPING>
            <SHORT-NAME>EngineDataIPdu_Mapping</SHORT-NAME>
            <I-PDU-REF DEST="I-SIGNAL-I-PDU">/Communication/EngineDataIPdu</I-PDU-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>0</START-POSITION>
          </PDU-TO-FRAME-MAPPING>
        </PDU-TO-FRAME-MAPPINGS>
      </FRAME>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

That is roughly 70 lines of XML for two signals, one PDU, and one frame. The
nesting is four levels deep in places. The `DEST` attribute on every `REF` element
is a redundant type hint that the toolchain must validate anyway. The `LENGTH` on
the `I-SIGNAL-I-PDU` is in bytes while the signal lengths and start positions are
in bits -- a unit mismatch that lives entirely in the engineer's head.

---

## Rupa Solution

### Instance Model

```rupa
// engine-signals.rupa
using domain autosar-r25;

ARPackage Signals {
    SystemSignal EngineSpeed {
        .length = 16;
        .initValue = 0;
    }

    SystemSignal ThrottlePosition {
        .length = 12;
        .initValue = 0;
    }
}

ARPackage Communication {
    ISignal EngineSpeed_I {
        .length = 16;
        .systemSignalRef = /Signals/EngineSpeed;
    }

    ISignal ThrottlePosition_I {
        .length = 12;
        .systemSignalRef = /Signals/ThrottlePosition;
    }

    ISignalIPdu EngineDataIPdu {
        .length = 4;                // bytes (PDU payload size)

        ISignalToPduMapping EngineSpeed_Mapping {
            .iSignalRef = /Communication/EngineSpeed_I;
            .startPosition = 0;     // bit offset within PDU
            .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
        }

        ISignalToPduMapping ThrottlePos_Mapping {
            .iSignalRef = /Communication/ThrottlePosition_I;
            .startPosition = 16;    // bit offset within PDU
            .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
        }
    }

    Frame EngineDataFrame {
        .frameLength = 8;           // bytes (CAN frame size)

        PduToFrameMapping EngineDataIPdu_Mapping {
            .iPduRef = /Communication/EngineDataIPdu;
            .startPosition = 0;     // bit offset within frame
            .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
        }
    }
}
```

The same model in 40 lines. Every containment relationship is expressed by
nesting: `ISignalToPduMapping` instances live inside their `ISignalIPdu`, just as
they do in the AUTOSAR metamodel. References use absolute paths instead of
`<REF DEST="...">` elements -- the type is inferred from the declared role type
(`&ISignal`, `&ISignalIPdu`).

### Validation Rules

```rupa
// signal-stack-rules.rupa
using domain autosar-r25;

// --- Signal-level rules ---

// ISignal length must match its referenced SystemSignal
#[rule(autosar::signal::length_consistent)]
let signal_length_consistent() =
    (. is ISignal) -> .length == .systemSignalRef.length;

// Every ISignal must be referenced by at least one PDU mapping
#[rule(autosar::signal::must_be_mapped)]
let signal_must_be_mapped() =
    (. is ISignal) ->
        ::referrers(.) | any(r => r is ISignalToPduMapping);

// --- PDU-level rules ---

// No two signal mappings within a PDU may occupy overlapping bit ranges.
// For little-endian (MOST-SIGNIFICANT-BYTE-LAST), startPosition is the
// least significant bit. The occupied range is [start, start + length).
#[rule(autosar::pdu::no_signal_overlap)]
let pdu_no_signal_overlap() =
    (. is ISignalIPdu) ->
        .iSignalToPduMappings | combinations(2) | all((m1, m2) =>
            m1.startPosition + m1.iSignalRef.length <= m2.startPosition
            || m2.startPosition + m2.iSignalRef.length <= m1.startPosition
        );

// Signal mappings must not exceed the PDU length (in bits)
#[rule(autosar::pdu::signals_within_bounds)]
let pdu_signals_within_bounds() =
    (. is ISignalIPdu) ->
        .iSignalToPduMappings | all(m =>
            m.startPosition + m.iSignalRef.length <= .length * 8
        );

// PDU must contain at least one signal mapping
#[rule(autosar::pdu::has_mappings)]
let pdu_has_mappings() =
    (. is ISignalIPdu) ->
        .iSignalToPduMappings | count() >= 1;

// --- Frame-level rules ---

// PDU mappings must not exceed the frame length (in bits)
#[rule(autosar::frame::pdu_within_bounds)]
let frame_pdu_within_bounds() =
    (. is Frame) ->
        .pduToFrameMappings | all(m =>
            m.startPosition + m.iPduRef.length * 8 <= .frameLength * 8
        );

// CAN classic frames: length must be 0..8 bytes
#[rule(autosar::frame::can_classic_length)]
let can_classic_frame_length() =
    (. is Frame && has(.frameLength)) ->
        .frameLength >= 0 && .frameLength <= 8;
```

### Activating Rules

```rupa
// project-validation.rupa
using domain autosar-r25;
import "signal-stack-rules.rupa";

// Activate all signal-stack rules by prefix
#[validate(autosar::signal)]
#[validate(autosar::pdu)]
#[validate(autosar::frame)]
```

Or activate at the type level in the metamodel so that every instance is checked
automatically, with no per-project import needed:

```rupa
// In the metamodel definition
#[validate(autosar::pdu::no_signal_overlap)]
#[validate(autosar::pdu::signals_within_bounds)]
type ISignalIPdu = ARElement {
    .length: PositiveInteger;
    .iSignalToPduMappings: ISignalToPduMapping*;
};
```

### Suppression

When a legacy signal intentionally violates a rule, suppress it with a reason:

```rupa
#[suppress(autosar::signal::length_consistent,
           reason = "Legacy signal retained for backward compatibility")]
ISignal LegacyBrake_I {
    .length = 8;
    .systemSignalRef = /Signals/BrakePedalPosition;  // length = 12
}
```

---

## Key Features Demonstrated

| Feature | Where it appears |
|---------|-----------------|
| **Full signal chain modeling** | `SystemSignal` -> `ISignal` -> `ISignalIPdu` -> `Frame` with correct AUTOSAR type names |
| **Containment by nesting** | `ISignalToPduMapping` inside `ISignalIPdu`; `PduToFrameMapping` inside `Frame` |
| **Typed references** | `.systemSignalRef`, `.iSignalRef`, `.iPduRef` -- type inferred from role declaration |
| **Validation rules (`#[rule]`)** | Six rules covering overlap detection, bounds checking, length consistency |
| **Self-guarding (`->`)** | Every rule uses `(. is Type) ->` to scope itself to relevant instances |
| **Reverse navigation** | `::referrers(.)` to check that every `ISignal` is actually used |
| **Combinatorial checking** | `combinations(2)` for pairwise overlap detection |
| **Pipe-based expressions** | `\| all(...)`, `\| any(...)`, `\| count()` for collection operations |
| **Hierarchical rule IDs** | `autosar::pdu::no_signal_overlap` enables prefix-based activation |
| **Selective suppression** | `#[suppress]` with mandatory reason on individual instances |

---

## Comparison

| Aspect | ARXML | Rupa |
|--------|-------|------|
| **Lines for this example** | ~70 (abbreviated) | ~40 (model) + ~45 (rules) |
| **Signal overlap detection** | External script or tool-specific check | First-class `#[rule]` with `combinations(2)` |
| **Bounds checking** | Implicit in tools, not in the model file | Explicit rule: `startPosition + length <= pdu.length * 8` |
| **Length consistency** | Manual review across files | `signal_length_consistent` rule auto-checked |
| **Reference syntax** | `<REF DEST="TYPE">/path</REF>` (redundant `DEST`) | `/path` (type inferred from role) |
| **Containment** | Nested XML elements with wrapper tags (`<I-SIGNAL-TO-PDU-MAPPINGS>`) | Direct nesting, no wrapper |
| **Unit confusion (bits vs bytes)** | Lives in documentation, not enforced | Rules can encode `length * 8` conversion explicitly |
| **Unused signal detection** | Requires external tooling | `::referrers(.)` in a one-line rule |
| **Rule activation** | N/A | Prefix-based (`autosar::pdu`) or per-type (`#[validate]` on `ISignalIPdu`) |

The validation rules are the differentiator. ARXML captures the structure but
leaves the constraints to external tools. Rupa lets the constraints live next to
the data they govern -- same language, same toolchain, same error reporting.
