# Use Case 05: ECU Extract with Overlays

An ECU extract is a view of the system description centered around a single
`EcuInstance` -- it contains only the communication clusters, signals, PDUs,
and frames that a specific ECU needs. In AUTOSAR methodology, the system
integrator produces the full system model and then extracts per-ECU slices for
each ECU integrator. Those slices often require ECU-specific modifications:
signal init values tuned for the target, vendor-specific metadata injected via
`AdminData`/`SDG`, and additional mappings not present in the system-wide model.

This use case exercises import, merge overlay (`|=`), targeted modification
operations, and vendor extensions through domain-derived `SDG` types.

---

## Scenario

A powertrain system contains two ECUs on a CAN bus -- **EngineECU** and
**TransmissionECU**. The system integrator maintains a shared system model with
the full signal stack (signals, I-signals, PDUs, frames) and topology
(communication cluster, ECU instances, controllers, connectors). The engine ECU
integrator needs to:

1. Import the system model as a base.
2. Overlay ECU-specific changes: adjust the `EngineStatus` PDU length and add a
   new signal mapping.
3. Attach vendor `AdminData` via SDG (Special Data Group) to record the
   integrator's tool version and internal part number.

---

## ARXML Baseline

### System-Level Model (shared)

The system description defines two ECUs on a CAN cluster with a frame carrying
engine signals.

```xml
<AR-PACKAGES>
  <AR-PACKAGE>
    <SHORT-NAME>Topology</SHORT-NAME>
    <ELEMENTS>
      <CAN-CLUSTER>
        <SHORT-NAME>PowertrainCAN</SHORT-NAME>
        <CAN-CLUSTER-VARIANTS>
          <CAN-CLUSTER-CONDITIONAL>
            <PHYSICAL-CHANNELS>
              <CAN-PHYSICAL-CHANNEL>
                <SHORT-NAME>Channel0</SHORT-NAME>
              </CAN-PHYSICAL-CHANNEL>
            </PHYSICAL-CHANNELS>
          </CAN-CLUSTER-CONDITIONAL>
        </CAN-CLUSTER-VARIANTS>
      </CAN-CLUSTER>

      <ECU-INSTANCE>
        <SHORT-NAME>EngineECU</SHORT-NAME>
        <COM-CONTROLLERS>
          <CAN-COMMUNICATION-CONTROLLER>
            <SHORT-NAME>CAN0</SHORT-NAME>
          </CAN-COMMUNICATION-CONTROLLER>
        </COM-CONTROLLERS>
      </ECU-INSTANCE>

      <ECU-INSTANCE>
        <SHORT-NAME>TransmissionECU</SHORT-NAME>
        <COM-CONTROLLERS>
          <CAN-COMMUNICATION-CONTROLLER>
            <SHORT-NAME>CAN0</SHORT-NAME>
          </CAN-COMMUNICATION-CONTROLLER>
        </COM-CONTROLLERS>
      </ECU-INSTANCE>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>Signals</SHORT-NAME>
    <ELEMENTS>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>EngineSpeed</SHORT-NAME>
        <LENGTH>16</LENGTH>
      </SYSTEM-SIGNAL>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>EngineTorque</SHORT-NAME>
        <LENGTH>12</LENGTH>
      </SYSTEM-SIGNAL>
      <SYSTEM-SIGNAL>
        <SHORT-NAME>OilTemperature</SHORT-NAME>
        <LENGTH>8</LENGTH>
      </SYSTEM-SIGNAL>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>Communication</SHORT-NAME>
    <ELEMENTS>
      <I-SIGNAL-I-PDU>
        <SHORT-NAME>EngineStatusPdu</SHORT-NAME>
        <LENGTH>32</LENGTH>
        <I-SIGNAL-TO-PDU-MAPPINGS>
          <I-SIGNAL-TO-I-PDU-MAPPING>
            <SHORT-NAME>EngineSpeed_Map</SHORT-NAME>
            <I-SIGNAL-REF DEST="I-SIGNAL">/Communication/EngineSpeed_I</I-SIGNAL-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>0</START-POSITION>
          </I-SIGNAL-TO-I-PDU-MAPPING>
          <I-SIGNAL-TO-I-PDU-MAPPING>
            <SHORT-NAME>EngineTorque_Map</SHORT-NAME>
            <I-SIGNAL-REF DEST="I-SIGNAL">/Communication/EngineTorque_I</I-SIGNAL-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>16</START-POSITION>
          </I-SIGNAL-TO-I-PDU-MAPPING>
        </I-SIGNAL-TO-PDU-MAPPINGS>
      </I-SIGNAL-I-PDU>

      <FRAME>
        <SHORT-NAME>EngineStatusFrame</SHORT-NAME>
        <FRAME-LENGTH>8</FRAME-LENGTH>
        <PDU-TO-FRAME-MAPPINGS>
          <PDU-TO-FRAME-MAPPING>
            <SHORT-NAME>EngineStatusPdu_Map</SHORT-NAME>
            <I-PDU-REF DEST="I-SIGNAL-I-PDU">/Communication/EngineStatusPdu</I-PDU-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>0</START-POSITION>
          </PDU-TO-FRAME-MAPPING>
        </PDU-TO-FRAME-MAPPINGS>
      </FRAME>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

### ECU-Specific Extract (ARXML overlay approach)

In traditional ARXML workflows, the ECU extract is a separate file that
duplicates relevant elements and modifies them. Adding a third signal mapping
and vendor metadata means copying the entire PDU element with modifications --
there is no merge primitive in ARXML itself. Tools perform the merge externally.

```xml
<!-- engine-ecu-extract.arxml (partial) -->
<AR-PACKAGES>
  <AR-PACKAGE>
    <SHORT-NAME>Communication</SHORT-NAME>
    <ELEMENTS>
      <I-SIGNAL-I-PDU>
        <SHORT-NAME>EngineStatusPdu</SHORT-NAME>
        <!-- Length changed from 32 to 40 to fit new signal -->
        <LENGTH>40</LENGTH>
        <I-SIGNAL-TO-PDU-MAPPINGS>
          <!-- Original mappings must be repeated in full -->
          <I-SIGNAL-TO-I-PDU-MAPPING>
            <SHORT-NAME>EngineSpeed_Map</SHORT-NAME>
            <I-SIGNAL-REF DEST="I-SIGNAL">/Communication/EngineSpeed_I</I-SIGNAL-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>0</START-POSITION>
          </I-SIGNAL-TO-I-PDU-MAPPING>
          <I-SIGNAL-TO-I-PDU-MAPPING>
            <SHORT-NAME>EngineTorque_Map</SHORT-NAME>
            <I-SIGNAL-REF DEST="I-SIGNAL">/Communication/EngineTorque_I</I-SIGNAL-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>16</START-POSITION>
          </I-SIGNAL-TO-I-PDU-MAPPING>
          <!-- New mapping added for the ECU extract -->
          <I-SIGNAL-TO-I-PDU-MAPPING>
            <SHORT-NAME>OilTemperature_Map</SHORT-NAME>
            <I-SIGNAL-REF DEST="I-SIGNAL">/Communication/OilTemperature_I</I-SIGNAL-REF>
            <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
            <START-POSITION>28</START-POSITION>
          </I-SIGNAL-TO-I-PDU-MAPPING>
        </I-SIGNAL-TO-PDU-MAPPINGS>
        <ADMIN-DATA>
          <SDGS>
            <SDG GID="VendorTool">
              <SD GID="ToolVersion">IntegrationSuite 4.2.1</SD>
              <SD GID="PartNumber">ENG-2025-0047</SD>
            </SDG>
          </SDGS>
        </ADMIN-DATA>
      </I-SIGNAL-I-PDU>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

The ARXML approach forces full duplication of unchanged mappings. Every existing
mapping must be copied verbatim into the extract file. Vendor metadata (`SDG`)
is embedded as a deep XML sub-tree inside `ADMIN-DATA`. If the base model
changes an existing mapping, the extract file silently diverges -- there is no
built-in mechanism to detect or reconcile the conflict.

---

## Rupa Solution

### System Model (base file)

```rupa
// system-model.rupa
using domain autosar-r22;

ARPackage Topology {
    CanCluster PowertrainCAN {
        CanPhysicalChannel Channel0 {}
    }

    EcuInstance EngineECU {
        CanCommunicationController CAN0 {}
    }

    EcuInstance TransmissionECU {
        CanCommunicationController CAN0 {}
    }
}

ARPackage Signals {
    SystemSignal EngineSpeed    { .length = 16; }
    SystemSignal EngineTorque   { .length = 12; }
    SystemSignal OilTemperature { .length = 8; }
}

ARPackage Communication {
    ISignal EngineSpeed_I {
        .length = 16;
        .systemSignalRef = /Signals/EngineSpeed;
    }

    ISignal EngineTorque_I {
        .length = 12;
        .systemSignalRef = /Signals/EngineTorque;
    }

    ISignal OilTemperature_I {
        .length = 8;
        .systemSignalRef = /Signals/OilTemperature;
    }

    ISignalIPdu EngineStatusPdu {
        .length = 32;

        ISignalToPduMapping EngineSpeed_Map {
            .iSignalRef = /Communication/EngineSpeed_I;
            .startPosition = 0;
            .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
        }

        ISignalToPduMapping EngineTorque_Map {
            .iSignalRef = /Communication/EngineTorque_I;
            .startPosition = 16;
            .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
        }
    }

    Frame EngineStatusFrame {
        .frameLength = 8;

        PduToFrameMapping EngineStatusPdu_Map {
            .iPduRef = /Communication/EngineStatusPdu;
            .startPosition = 0;
            .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
        }
    }
}
```

### Vendor Extension Types (domain derivation)

Before writing the overlay, the integrator's toolchain defines SDG types as a
domain extension. This is a one-time setup that the overlay file imports.

```rupa
// vendor-sdg-types.rupa -- extend base domain with SDG support
domain vendor-engine-ext = autosar-r22;

// SDG key-value pair
type SdgEntry = Identifiable {
    .value: ::string;
};

// Special Data Group: a named bag of key-value pairs
type Sdg = Identifiable {
    .entries: SdgEntry*;
};

// AdminData: container for SDG groups, attachable to any Identifiable
type AdminData = {
    .sdgs: Sdg*;
};

// Reopen ISignalIPdu to accept adminData
type ISignalIPdu = ISignalIPdu {
    .adminData: AdminData?;
};
```

### ECU Extract Overlay

```rupa
// engine-ecu-extract.rupa
using domain vendor-engine-ext;
import base from "system-model.rupa";

// Step 1: Merge the full system model as our starting point
|= base;

// Step 2: Modify the PDU for this ECU -- grow length, add a mapping
/Communication/EngineStatusPdu |= {
    .length = 40;

    ISignalToPduMapping OilTemperature_Map {
        .iSignalRef = /Communication/OilTemperature_I;
        .startPosition = 28;
        .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
    }
};

// Step 3: Attach vendor AdminData via SDG
/Communication/EngineStatusPdu |= {
    .adminData = AdminData {
        Sdg VendorTool {
            SdgEntry ToolVersion { .value = "IntegrationSuite 4.2.1"; }
            SdgEntry PartNumber  { .value = "ENG-2025-0047"; }
        }
    };
};
```

**What happened:**

- `|= base` merges the entire system model into this file's model root. Every
  package, signal, PDU, and ECU from the base is now present.

- The first `|=` on `EngineStatusPdu` performs a structural merge: `.length` is
  replaced with `40` (single-valued role -- merge overwrites), while
  `OilTemperature_Map` is added to the `.iSignalToPduMappings` collection
  (multi-valued role -- merge adds by identity). The two existing mappings
  (`EngineSpeed_Map`, `EngineTorque_Map`) are untouched because the merge block
  does not mention them.

- The second `|=` attaches `.adminData` to the PDU. Because `AdminData` is
  optional and not yet present, the merge creates it. The `Sdg` and `SdgEntry`
  instances are contained children.

### Alternative: Single Merge Block

The two modifications can be combined into one merge for conciseness:

```rupa
/Communication/EngineStatusPdu |= {
    .length = 40;

    ISignalToPduMapping OilTemperature_Map {
        .iSignalRef = /Communication/OilTemperature_I;
        .startPosition = 28;
        .packingByteOrder = "MOST-SIGNIFICANT-BYTE-LAST";
    }

    .adminData = AdminData {
        Sdg VendorTool {
            SdgEntry ToolVersion { .value = "IntegrationSuite 4.2.1"; }
            SdgEntry PartNumber  { .value = "ENG-2025-0047"; }
        }
    };
};
```

### Scoped Modification with `with`

When the overlay needs to touch multiple elements under the same package, the
`with` block avoids repeating the path prefix:

```rupa
with /Signals {
    // Set init values specific to this ECU's calibration
    SystemSignal EngineSpeed    |= { .initValue = 800.0; };
    SystemSignal EngineTorque   |= { .initValue = 0.0; };
    SystemSignal OilTemperature |= { .initValue = 25.0; };
}
```

### CLI

```sh
# Build the overlay -- base is resolved via the import declaration
rupa build engine-ecu-extract.rupa -o engine-ecu.rupac

# Export back to ARXML for downstream AUTOSAR tools
rupa export engine-ecu.rupac --format arxml -o engine-ecu-extract.arxml

# Validate overlay consistency against base
rupa check engine-ecu-extract.rupa
```

---

## Key Features Demonstrated

| Feature | How it appears |
|---------|---------------|
| **Import** | `import base from "system-model.rupa"` loads the system model as a value |
| **Root merge** | `\|= base` merges the imported model into the current file's root |
| **Path-targeted merge** | `/Communication/EngineStatusPdu \|= { ... }` modifies a specific object |
| **Single-valued overwrite** | `.length = 40` inside merge replaces the existing value |
| **Collection append** | `ISignalToPduMapping OilTemperature_Map { ... }` adds to the collection |
| **Unchanged elements preserved** | Existing mappings survive the merge untouched |
| **Domain derivation** | `domain vendor-engine-ext = autosar-r22` extends the base domain |
| **Type reopening** | `type ISignalIPdu = ISignalIPdu { ... }` adds `.adminData` to an existing type |
| **Vendor SDG extension** | `AdminData`, `Sdg`, `SdgEntry` model AUTOSAR's special data groups |
| **`with` block** | `with /Signals { ... }` scopes multiple modifications under one path |
| **`=` vs `\|=`** | `=` replaces unconditionally; `\|=` merges structurally |

---

## Comparison

| Concern | ARXML file-based overlay | Rupa explicit merge |
|---------|--------------------------|---------------------|
| **Expressing a delta** | Full element duplication required. Every unchanged child must be copied into the extract file. | Only the changed and added elements appear. Merge semantics handle the rest. |
| **Conflict detection** | None built-in. If the base model changes an existing mapping, the extract silently diverges. External diff tooling required. | The compiler resolves `\|= base` at build time. If a merge conflict arises (e.g., both base and overlay set `.length`), the last-writer-wins rule applies and is visible in the source. |
| **Vendor metadata** | Deep XML nesting: `ADMIN-DATA > SDGS > SDG > SD`. Interleaved with model content. | Domain extension adds typed `.adminData` role. SDG entries are first-class objects with identity and validation. |
| **Traceability** | Requires external tooling to determine which elements differ from the base. | The overlay file is the delta -- every statement in the overlay is an intentional modification. `rupa check` validates consistency. |
| **Multi-ECU extracts** | Separate ARXML files per ECU, each duplicating shared content. | Separate `.rupa` overlay files per ECU, each importing the same base. Shared content is defined once. |
| **Composability** | ARXML files are merged by external tools with proprietary merge logic. | `\|= base` is a language-level operation with defined semantics. Multiple overlays compose predictably: `\|= base; \|= safety_overlay; \|= vendor_overlay;`. |
