# AUTOSAR Domain Modeling Research

**Generated**: 2026-01-28
**Purpose**: Comprehensive research on AUTOSAR domain requirements to inform Rupa DSL design

---

## Executive Summary

AUTOSAR (AUTomotive Open System ARchitecture) is a global standardized software architecture for automotive ECUs (Electronic Control Units). It uses ARXML (AUTOSAR XML) as its exchange format, which is notoriously verbose and complex. This research identifies what Rupa would need to effectively support AUTOSAR domain modeling, highlighting pain points that a well-designed DSL could address.

**Key Findings:**
1. ARXML's XML verbosity is a known pain point; a concise DSL could provide 5-10x reduction in file size
2. Reference paths (like `/Package/SubPackage/Element`) are fundamental - aligns with Rupa's existing path syntax
3. Hierarchical composition (compositions containing atomic components) maps naturally to nested structures
4. Strong typing with physical/implementation separation is essential
5. Validation constraints (OCL-based) are integral to the standard
6. Multi-file, multi-team collaboration is the norm - modularity is critical

---

## 1. AUTOSAR Model Structure

### 1.1 Architecture Overview

AUTOSAR defines a three-layer architecture:

```
┌─────────────────────────────────────────────┐
│            Application Layer                │  <- Software Components (SWCs)
├─────────────────────────────────────────────┤
│       Runtime Environment (RTE)             │  <- Generated communication layer
├─────────────────────────────────────────────┤
│          Basic Software (BSW)               │  <- Services, ECU Abstraction,
│                                             │     Microcontroller Abstraction
└─────────────────────────────────────────────┘
```

The **Virtual Functional Bus (VFB)** is a key abstraction - it allows application software to be developed independently of hardware, with the RTE handling actual communication once deployed.

### 1.2 Key Model Elements

#### Software Component Types

| Component Type | Description | Behavior |
|---------------|-------------|----------|
| `ApplicationSwComponentType` | Main application logic | Has internal behavior, ports |
| `CompositionSwComponentType` | Aggregates other components | No behavior, only structure |
| `ServiceSwComponentType` | BSW service wrappers | Interfaces with basic software |
| `EcuAbstractionSwComponentType` | Hardware abstraction | Accesses ECU peripherals |
| `SensorActuatorSwComponentType` | I/O handling | Interfaces with sensors/actuators |
| `ParameterSwComponentType` | Calibration data | Provides parameters to other SWCs |
| `NvBlockSwComponentType` | Non-volatile storage | Access to persistent memory |

**Rupa Implication:** Need robust type hierarchies with shared properties and specialized behavior.

#### Ports (Communication Points)

Software components communicate exclusively through ports:

| Port Type | ARXML Element | Direction | Purpose |
|-----------|---------------|-----------|---------|
| Provide (P-Port) | `P-PORT-PROTOTYPE` | Outward | Sends data, provides services |
| Require (R-Port) | `R-PORT-PROTOTYPE` | Inward | Receives data, calls services |
| PR-Port | `PR-PORT-PROTOTYPE` | Bidirectional | Combined (less common) |

Each port references a **PortInterface** that defines what data or operations flow through it.

#### Interfaces

| Interface Type | Purpose | Example Use |
|---------------|---------|-------------|
| `SenderReceiverInterface` | Signal/data exchange | Vehicle speed, temperature |
| `ClientServerInterface` | Operation calls with return values | Diagnostic requests |
| `ModeSwitchInterface` | Mode state transitions | STARTUP, RUN, SHUTDOWN |
| `ParameterInterface` | Calibration parameter access | Tuning constants |
| `NvDataInterface` | Non-volatile data access | Persistent settings |
| `TriggerInterface` | Event triggering | External trigger signals |

#### Runnables (Executable Units)

Runnables are the smallest schedulable code units within an SWC:

```
SWC Internal Behavior
├── RunnableEntity "Init"
│   └── triggered by: InitEvent
├── RunnableEntity "Periodic10ms"
│   └── triggered by: TimingEvent (period: 10ms)
├── RunnableEntity "OnDataReceived"
│   └── triggered by: DataReceivedEvent (port: VehicleSpeed)
└── RunnableEntity "OnModeChange"
    └── triggered by: ModeSwitchEvent
```

**RTE Events that trigger runnables:**
- `TimingEvent` - periodic execution
- `DataReceivedEvent` - data arrival on an R-port
- `DataSendCompletedEvent` - transmission confirmation
- `OperationInvokedEvent` - server operation called
- `ModeSwitchEvent` - mode state change
- `InitEvent` / `BackgroundEvent`

**Rupa Implication:** Event-driven execution model; need to express triggers and their relationships.

#### Inter-Runnable Variables (IRVs)

Variables shared between runnables within the same SWC (not visible externally).

### 1.3 Hierarchical Organization

AUTOSAR models are organized in packages:

```
/                                    <- Root
├── /DataTypes
│   ├── /ApplicationDataTypes
│   │   ├── Speed_kph                <- Application-level type
│   │   └── Temperature_degC
│   ├── /ImplementationDataTypes
│   │   ├── UInt16                   <- Implementation-level type
│   │   └── Float32
│   └── /BaseTypes
│       └── uint16                   <- Primitive base type
├── /PortInterfaces
│   ├── /SenderReceiver
│   │   └── VehicleSpeedInterface
│   └── /ClientServer
│       └── DiagnosticInterface
├── /SwComponentTypes
│   ├── /Composition
│   │   └── VehicleControlComposition
│   └── /Atomic
│       ├── SpeedSensor
│       └── EngineController
├── /Units
│   ├── kph
│   └── degC
└── /CompuMethods
    └── SpeedScaling
```

**Rupa Implication:** Path-based references (already in Rupa) map directly. Package structure is critical.

### 1.4 Relationships Between Elements

| Relationship Type | Description | Example |
|------------------|-------------|---------|
| **Reference** | One element points to another | Port references PortInterface |
| **Composition** | Parent contains children | Composition contains SWC prototypes |
| **Prototype Instance** | Type instantiation | SwComponentPrototype instantiates SwComponentType |
| **Inheritance** | Type specialization | Not heavily used, but supported |
| **Mapping** | Cross-concern linkage | DataTypeMapping links App to Impl types |
| **Connector** | Communication path | AssemblyConnector links ports |

**Critical:** AUTOSAR uses **reference paths** extensively. Example:
```xml
<PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE">
  /PortInterfaces/SenderReceiver/VehicleSpeedInterface
</PROVIDED-INTERFACE-TREF>
```

---

## 2. ARXML Format Analysis

### 2.1 Structure Overview

ARXML is standard XML with these characteristics:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR xmlns="http://autosar.org/schema/r4.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://autosar.org/schema/r4.0 AUTOSAR_4-2-2.xsd">
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>MyPackage</SHORT-NAME>
      <ELEMENTS>
        <!-- Package contents -->
      </ELEMENTS>
      <AR-PACKAGES>
        <!-- Sub-packages -->
      </AR-PACKAGES>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
```

Key structural elements:
- `<AUTOSAR>` - root element
- `<AR-PACKAGES>` - container for packages (v4; `<TOP-LEVEL-PACKAGES>` in v3)
- `<AR-PACKAGE>` - namespace/grouping unit
- `<SHORT-NAME>` - identifier (used in reference paths)
- `<LONG-NAME>` - human-readable display name
- `<DESC>` - documentation/description

### 2.2 Example: Software Component with Ports

```xml
<APPLICATION-SW-COMPONENT-TYPE>
  <SHORT-NAME>SpeedSensor</SHORT-NAME>
  <LONG-NAME>
    <L-4 L="EN">Speed Sensor Component</L-4>
  </LONG-NAME>
  <DESC>
    <L-2 L="EN">Reads vehicle speed from wheel sensors and provides it to other components.</L-2>
  </DESC>
  <PORTS>
    <P-PORT-PROTOTYPE>
      <SHORT-NAME>VehicleSpeed</SHORT-NAME>
      <PROVIDED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE">
        /PortInterfaces/VehicleSpeedInterface
      </PROVIDED-INTERFACE-TREF>
    </P-PORT-PROTOTYPE>
    <R-PORT-PROTOTYPE>
      <SHORT-NAME>WheelPulseCount</SHORT-NAME>
      <REQUIRED-INTERFACE-TREF DEST="SENDER-RECEIVER-INTERFACE">
        /PortInterfaces/WheelPulseInterface
      </REQUIRED-INTERFACE-TREF>
    </R-PORT-PROTOTYPE>
  </PORTS>
  <INTERNAL-BEHAVIORS>
    <SWC-INTERNAL-BEHAVIOR>
      <SHORT-NAME>SpeedSensorBehavior</SHORT-NAME>
      <RUNNABLES>
        <RUNNABLE-ENTITY>
          <SHORT-NAME>CalculateSpeed</SHORT-NAME>
          <CAN-BE-INVOKED-CONCURRENTLY>false</CAN-BE-INVOKED-CONCURRENTLY>
          <DATA-READ-ACCESSS>
            <VARIABLE-ACCESS>
              <SHORT-NAME>ReadWheelPulse</SHORT-NAME>
              <ACCESSED-VARIABLE>
                <AUTOSAR-VARIABLE-IREF>
                  <PORT-PROTOTYPE-REF DEST="R-PORT-PROTOTYPE">
                    /SwComponentTypes/SpeedSensor/WheelPulseCount
                  </PORT-PROTOTYPE-REF>
                  <TARGET-DATA-PROTOTYPE-REF DEST="VARIABLE-DATA-PROTOTYPE">
                    /PortInterfaces/WheelPulseInterface/PulseCount
                  </TARGET-DATA-PROTOTYPE-REF>
                </AUTOSAR-VARIABLE-IREF>
              </ACCESSED-VARIABLE>
            </VARIABLE-ACCESS>
          </DATA-READ-ACCESSS>
          <DATA-WRITE-ACCESSS>
            <VARIABLE-ACCESS>
              <SHORT-NAME>WriteSpeed</SHORT-NAME>
              <ACCESSED-VARIABLE>
                <AUTOSAR-VARIABLE-IREF>
                  <PORT-PROTOTYPE-REF DEST="P-PORT-PROTOTYPE">
                    /SwComponentTypes/SpeedSensor/VehicleSpeed
                  </PORT-PROTOTYPE-REF>
                  <TARGET-DATA-PROTOTYPE-REF DEST="VARIABLE-DATA-PROTOTYPE">
                    /PortInterfaces/VehicleSpeedInterface/Speed
                  </TARGET-DATA-PROTOTYPE-REF>
                </AUTOSAR-VARIABLE-IREF>
              </ACCESSED-VARIABLE>
            </VARIABLE-ACCESS>
          </DATA-WRITE-ACCESSS>
        </RUNNABLE-ENTITY>
      </RUNNABLES>
      <EVENTS>
        <TIMING-EVENT>
          <SHORT-NAME>CalculateSpeedTrigger</SHORT-NAME>
          <START-ON-EVENT-REF DEST="RUNNABLE-ENTITY">
            /SwComponentTypes/SpeedSensor/SpeedSensorBehavior/CalculateSpeed
          </START-ON-EVENT-REF>
          <PERIOD>0.01</PERIOD>  <!-- 10ms -->
        </TIMING-EVENT>
      </EVENTS>
    </SWC-INTERNAL-BEHAVIOR>
  </INTERNAL-BEHAVIORS>
</APPLICATION-SW-COMPONENT-TYPE>
```

### 2.3 Pain Points with ARXML

| Pain Point | Description | Impact |
|------------|-------------|--------|
| **Extreme Verbosity** | Simple concepts require many XML elements | Files are 10-100x larger than necessary |
| **Deep Nesting** | 10+ levels of nesting common | Hard to read, navigate, edit |
| **Repetitive References** | Full paths repeated everywhere | Copy-paste errors, maintenance burden |
| **Schema Complexity** | Massive XSD with hundreds of types | Steep learning curve |
| **Version Fragmentation** | Many schema versions, breaking changes | Tool compatibility issues |
| **Hidden Semantics** | Important constraints not in schema | OCL constraints separate from structure |
| **Tag Name Verbosity** | `<VARIABLE-DATA-PROTOTYPE>` vs `var` | Noise obscures meaning |
| **Reference Syntax** | `<FOO-REF DEST="TYPE">path</FOO-REF>` | Verbose; type already in path |
| **Multi-language Text** | `<L-2 L="EN">text</L-2>` wrappers | Clutters simple descriptions |
| **Merge Conflicts** | XML structure causes git conflicts | Team collaboration friction |

### 2.4 What a Better DSL Could Provide

**Potential Rupa representation of the same component:**

```rupa
// Hypothetical Rupa syntax for AUTOSAR

package /SwComponentTypes/Atomic;

ApplicationSwComponent SpeedSensor {
    #[doc("Reads vehicle speed from wheel sensors")]

    provides VehicleSpeed: /PortInterfaces/VehicleSpeedInterface;
    requires WheelPulseCount: /PortInterfaces/WheelPulseInterface;

    behavior SpeedSensorBehavior {
        runnable CalculateSpeed {
            concurrent = false;
            reads WheelPulseCount.PulseCount;
            writes VehicleSpeed.Speed;
        }

        #[timing(period = 10ms)]
        event CalculateSpeedTrigger -> CalculateSpeed;
    }
}
```

**Reduction:** ~80 lines of XML to ~15 lines of DSL.

### 2.5 Metadata and Annotations

ARXML uses **ADMIN-DATA** with **Special Data Groups (SDG)** for extensions:

```xml
<ADMIN-DATA>
  <SDGS>
    <SDG GID="ToolVendor">
      <SD GID="ToolVendor::Version">2.5.3</SD>
      <SD GID="ToolVendor::GeneratedBy">DaVinci</SD>
    </SDG>
  </SDGS>
</ADMIN-DATA>
```

**Rupa Implication:** `#[...]` annotations map well to this pattern:
```rupa
#[tool_vendor(version = "2.5.3", generated_by = "DaVinci")]
```

---

## 3. Typing and Constraints

### 3.1 Data Type Hierarchy

AUTOSAR has a sophisticated three-layer type system:

```
BaseType (e.g., uint16)
    ↓
ImplementationDataType (e.g., UInt16_impl with endianness)
    ↓
ApplicationDataType (e.g., Speed_kph with units, scaling)
```

#### Base Types (Platform Types)

| Type | Bits | Description |
|------|------|-------------|
| `uint8/16/32/64` | 8-64 | Unsigned integers |
| `sint8/16/32/64` | 8-64 | Signed integers |
| `float32/64` | 32/64 | IEEE floating point |
| `boolean` | 1+ | Boolean value |

#### Implementation Data Types

Categories:
- **VALUE** - primitive value
- **TYPE_REFERENCE** - typedef (reference to another type)
- **ARRAY** - fixed-size array
- **STRUCTURE** - record/struct

#### Application Data Types

Categories:
- **ApplicationPrimitiveDataType** - scalar with physical semantics
- **ApplicationRecordDataType** - struct (fields with names)
- **ApplicationArrayDataType** - array of elements

### 3.2 Computation Methods (COMPU-METHOD)

Translate between internal (machine) values and physical (real-world) values:

| Category | Description | Example |
|----------|-------------|---------|
| **IDENTICAL** | No conversion | Enums, booleans |
| **LINEAR** | y = ax + b | Temperature scaling |
| **RATIONAL** | Polynomial ratio | Complex sensors |
| **TEXTTABLE** | Enumeration mapping | Mode states |
| **TAB-NOINTP** | Lookup table (discrete) | Calibration data |
| **SCALE-LINEAR** | Piecewise linear | Multi-range sensors |

Example:
```xml
<COMPU-METHOD>
  <SHORT-NAME>SpeedScaling</SHORT-NAME>
  <CATEGORY>LINEAR</CATEGORY>
  <UNIT-REF DEST="UNIT">/Units/kph</UNIT-REF>
  <COMPU-INTERNAL-TO-PHYS>
    <COMPU-SCALES>
      <COMPU-SCALE>
        <COMPU-RATIONAL-COEFFS>
          <COMPU-NUMERATOR>
            <V>0</V>   <!-- offset -->
            <V>0.1</V> <!-- factor -->
          </COMPU-NUMERATOR>
          <COMPU-DENOMINATOR>
            <V>1</V>
          </COMPU-DENOMINATOR>
        </COMPU-RATIONAL-COEFFS>
      </COMPU-SCALE>
    </COMPU-SCALES>
  </COMPU-INTERNAL-TO-PHYS>
</COMPU-METHOD>
```

**Rupa Implication:** Need to express unit conversions and scaling. Could leverage functional expressions:
```rupa
CompuMethod SpeedScaling {
    unit = /Units/kph;
    internal_to_phys = |x| x * 0.1;  // or explicit coefficients
}
```

### 3.3 Physical Dimensions and Units

AUTOSAR defines physical dimensions based on SI units:

```xml
<PHYSICAL-DIMENSION>
  <SHORT-NAME>Velocity</SHORT-NAME>
  <LENGTH-EXP>1</LENGTH-EXP>
  <TIME-EXP>-1</TIME-EXP>
</PHYSICAL-DIMENSION>

<UNIT>
  <SHORT-NAME>kph</SHORT-NAME>
  <LONG-NAME><L-4 L="EN">kilometers per hour</L-4></LONG-NAME>
  <DISPLAY-NAME>km/h</DISPLAY-NAME>
  <PHYSICAL-DIMENSION-REF>Velocity</PHYSICAL-DIMENSION-REF>
  <FACTOR-SI-TO-UNIT>3.6</FACTOR-SI-TO-UNIT>  <!-- 1 m/s = 3.6 km/h -->
</UNIT>
```

### 3.4 Data Constraints

Two constraint types for range validation:

| Constraint Type | Purpose | Example |
|-----------------|---------|---------|
| **PhysicalConstraint** | Real-world limits | 0 to 300 km/h |
| **InternalConstraint** | Machine representation limits | 0 to 65535 |

```xml
<DATA-CONSTR>
  <SHORT-NAME>SpeedConstraint</SHORT-NAME>
  <DATA-CONSTR-RULES>
    <DATA-CONSTR-RULE>
      <PHYS-CONSTRS>
        <LOWER-LIMIT INTERVAL-TYPE="CLOSED">0</LOWER-LIMIT>
        <UPPER-LIMIT INTERVAL-TYPE="CLOSED">300</UPPER-LIMIT>
        <UNIT-REF DEST="UNIT">/Units/kph</UNIT-REF>
      </PHYS-CONSTRS>
    </DATA-CONSTR-RULE>
  </DATA-CONSTR-RULES>
</DATA-CONSTR>
```

**Rupa Implication:** Range constraints should be expressible inline or via validation:
```rupa
ApplicationPrimitiveDataType Speed_kph {
    #[range(0..300, unit = kph)]
    #[internal_range(0..65535)]
}
```

### 3.5 Semantic Constraints (OCL)

AUTOSAR uses OCL (Object Constraint Language) for semantic validation beyond structural schema:

Example constraints:
- "Every port prototype must reference a valid port interface"
- "Data element names within an interface must be unique"
- "A composition cannot contain itself (no circular composition)"
- "Init values must be within the defined data constraints"

**Rupa Implication:** Validation rules (topic 7) are essential for AUTOSAR modeling.

---

## 4. Modularity Requirements

### 4.1 File Organization

AUTOSAR models are typically split across many files:

```
project/
├── DataTypes/
│   ├── ApplicationTypes.arxml
│   ├── ImplementationTypes.arxml
│   └── BaseTypes.arxml
├── PortInterfaces/
│   ├── SenderReceiver.arxml
│   └── ClientServer.arxml
├── SwComponents/
│   ├── Sensors/
│   │   └── SpeedSensor.arxml
│   ├── Controllers/
│   │   └── EngineController.arxml
│   └── Compositions/
│       └── VehicleControl.arxml
├── System/
│   ├── Topology.arxml
│   ├── Mapping.arxml
│   └── Communication.arxml
└── ECU/
    ├── ECU1_Extract.arxml
    └── ECU1_Config.arxml
```

### 4.2 Package References

AUTOSAR packages are "open sets" - content can be split across files:

```xml
<!-- File 1: DataTypes/Base.arxml -->
<AR-PACKAGE>
  <SHORT-NAME>DataTypes</SHORT-NAME>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>BaseTypes</SHORT-NAME>
      <ELEMENTS>
        <SW-BASE-TYPE>...</SW-BASE-TYPE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AR-PACKAGE>

<!-- File 2: DataTypes/Application.arxml -->
<AR-PACKAGE>
  <SHORT-NAME>DataTypes</SHORT-NAME>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>ApplicationTypes</SHORT-NAME>
      <ELEMENTS>
        <APPLICATION-PRIMITIVE-DATA-TYPE>...</APPLICATION-PRIMITIVE-DATA-TYPE>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AR-PACKAGE>
```

Both files contribute to the same `/DataTypes` package.

**Rupa Implication:** Need to support:
1. Package declarations that can span files
2. Imports/references across files
3. Conflict detection when same element defined twice

### 4.3 Reference Bases (Relative References)

AUTOSAR supports reference bases for shorter paths:

```xml
<AR-PACKAGE>
  <SHORT-NAME>MyComponent</SHORT-NAME>
  <REFERENCE-BASES>
    <REFERENCE-BASE>
      <SHORT-LABEL>InterfaceBase</SHORT-LABEL>
      <IS-DEFAULT>true</IS-DEFAULT>
      <PACKAGE-REF DEST="AR-PACKAGE">/PortInterfaces</PACKAGE-REF>
    </REFERENCE-BASE>
  </REFERENCE-BASES>
  <!-- Now can use relative refs within this package -->
</AR-PACKAGE>
```

**Rupa Implication:** Import aliases serve similar purpose:
```rupa
import /PortInterfaces as iface;
// then use: iface/VehicleSpeedInterface
```

### 4.4 Team Collaboration Patterns

| Pattern | Description | Challenge |
|---------|-------------|-----------|
| **Responsibility Split** | Different teams own different packages | Reference coordination |
| **Library Components** | Shared reusable components | Versioning, updates |
| **OEM/Supplier Split** | OEM defines interfaces, supplier implements | Partial visibility |
| **ECU Extract** | OEM provides only relevant subset to supplier | Derived artifacts |

### 4.5 Merge and Conflict Handling

ARXML merging is notoriously difficult:
- XML structure causes many git conflicts
- Element order matters for some tools
- UUIDs can conflict on parallel additions
- Deep nesting makes diffs hard to read

**Rupa Implication:** Design for merge-friendliness:
- Line-based syntax (not deeply nested)
- Stable element ordering
- Explicit identity (SHORT-NAME) rather than position-based

---

## 5. Versioning and Evolution

### 5.1 AUTOSAR Release History

| Release | Year | Key Changes |
|---------|------|-------------|
| R19-11 (4.5.0) | 2019 | Unified versioning with Adaptive Platform |
| R20-11 (4.6.0) | 2020 | Enhanced Ethernet, security features |
| R21-11 (4.7.0) | 2021 | Improved service-oriented communication |
| R22-11 (4.8.0) | 2022 | Minor release, refinements |
| R23-11 (4.9.0) | 2023 | Minor release |
| R24-11 (4.10.0) | 2024 | Latest release |

### 5.2 Schema Evolution

AUTOSAR schemas aim for backward compatibility:
- New elements are optional
- Deprecated elements remain for several releases
- Breaking changes are rare but happen

**Version declaration in ARXML:**
```xml
<AUTOSAR xmlns="http://autosar.org/schema/r4.0"
         xsi:schemaLocation="http://autosar.org/schema/r4.0 AUTOSAR_00051.xsd">
```

The `AUTOSAR_00051` corresponds to internal version number.

### 5.3 Migration Challenges

| Challenge | Description |
|-----------|-------------|
| **Schema Version Mismatch** | Different tools use different schema versions |
| **Deprecated Elements** | Old models use deprecated constructs |
| **New Required Elements** | New versions may require previously optional elements |
| **Multi-ECU Systems** | Different ECUs may use different AUTOSAR versions |
| **Tool Lock-in** | Tools may require specific versions |

**Rupa Implication:**
- Edition system (topic 11) aligns with AUTOSAR versioning needs
- Need migration tools for model evolution
- Consider version annotations on elements

---

## 6. Tooling Ecosystem

### 6.1 Major AUTOSAR Tools

| Tool | Vendor | Purpose |
|------|--------|---------|
| **DaVinci Developer** | Vector | SWC design, architecture |
| **DaVinci Configurator** | Vector | BSW configuration |
| **EB tresos Studio** | Elektrobit | BSW configuration, code gen |
| **SystemDesk** | dSPACE | System architecture |
| **TargetLink** | dSPACE | Production code generation |
| **AUTOSAR Builder** | Dassault | Architecture modeling |
| **Rhapsody** | IBM | UML/SysML with AUTOSAR |
| **Enterprise Architect** | Sparx | UML with AUTOSAR profile |
| **MATLAB/Simulink** | MathWorks | Model-based design |

### 6.2 Common Workflows

```
System Design           Component Design         ECU Integration
─────────────────      ─────────────────        ─────────────────
SystemDesk             DaVinci Developer        EB tresos Studio
     │                      │                        │
     ▼                      ▼                        ▼
System Description → SW-C Descriptions → ECU Configuration
     (ARXML)              (ARXML)              (ARXML)
                              │                        │
                              ▼                        ▼
                         TargetLink              Code Generation
                              │                        │
                              ▼                        ▼
                          App Code              BSW + RTE Code
                              │                        │
                              └──────────┬─────────────┘
                                         ▼
                                   Compiled ECU
```

### 6.3 Common Transformations

| Transformation | Description |
|----------------|-------------|
| **System → ECU Extract** | Reduce system description to single-ECU scope |
| **Flatten Composition** | Expand compositions to atomic components |
| **RTE Generation** | Generate C code for runtime environment |
| **BSW Configuration** | Configure basic software modules |
| **Signal Mapping** | Map SW-C signals to bus signals |
| **Type Mapping** | Map application types to implementation types |

### 6.4 Typical Queries/Views

| Query Type | Example |
|------------|---------|
| **Dependency** | "What components use this interface?" |
| **Impact Analysis** | "What changes if I modify this data type?" |
| **Consistency** | "Are all referenced elements defined?" |
| **Completeness** | "What's missing for RTE generation?" |
| **Traceability** | "Link requirements to implementing runnables" |

### 6.5 Python Libraries

**cogu/autosar** - Python AUTOSAR library:
- Create/read/modify ARXML
- Follows AUTOSAR schema structure
- Targets R22-11, validates against multiple versions
- Used for automation and scripting

**autosarfactory** - Alternative Python package:
- Similar create/read/modify capabilities
- Metamodel-based approach

**Rupa Implication:**
- Need API/SDK for programmatic manipulation
- Consider Python bindings for adoption
- Support common query patterns natively

---

## 7. Implications for Rupa Design

### 7.1 Must-Have Features

| Feature | AUTOSAR Requirement | Rupa Alignment |
|---------|---------------------|----------------|
| **Reference Paths** | `/Package/Element` syntax | Already designed |
| **Nested Structures** | Deep hierarchies | Already supported |
| **Type References** | Strong typing with indirection | Metamodel-driven |
| **Annotations** | Metadata (ADMIN-DATA, SDG) | `#[...]` syntax |
| **Multi-file** | Large model splitting | Import system (topic 4) |
| **Validation** | OCL constraints | Validation language (topic 7) |
| **Transformations** | Code gen, extraction | Transformation language (topic 8) |

### 7.2 Specific Syntax Needs

1. **Port Direction:** Need `provides`/`requires` or similar keywords
2. **Reference Typing:** References should indicate target type
3. **Enums with Metadata:** Mode declarations need associated data
4. **Units and Scaling:** First-class support or library pattern
5. **Trigger/Event Binding:** Event-to-runnable associations

### 7.3 Metamodel Requirements

An AUTOSAR metamodel for Rupa would need:
- ~100+ element types (simplified from AUTOSAR's 500+)
- Rich reference relationships
- Containment hierarchies
- Constraint definitions

### 7.4 DSL vs. Format Translation

Two possible approaches:

**Option A: Native AUTOSAR DSL**
- Define Rupa syntax that maps to AUTOSAR concepts
- Import/export ARXML
- Lose some ARXML details, gain readability

**Option B: General DSL with AUTOSAR Profile**
- Generic Rupa structures
- AUTOSAR-specific annotations
- Full ARXML fidelity possible

**Recommendation:** Option A with lossless round-trip for common elements. Accept that some exotic ARXML features may require fallback to raw format.

---

## 8. References and Sources

### AUTOSAR Official
- [AUTOSAR Classic Platform](https://www.autosar.org/standards/classic-platform)
- [AUTOSAR Adaptive Platform](https://www.autosar.org/standards/adaptive-platform)

### Technical Specifications
- [ARXML Serialization Rules (R20-11)](https://www.autosar.org/fileadmin/standards/R20-11/FO/AUTOSAR_TPS_ARXMLSerializationRules.pdf)
- [Software Component Template (R21-11)](https://www.autosar.org/fileadmin/standards/R21-11/CP/AUTOSAR_TPS_SoftwareComponentTemplate.pdf)
- [ECU Configuration (R21-11)](https://www.autosar.org/fileadmin/standards/R21-11/CP/AUTOSAR_TPS_ECUConfiguration.pdf)
- [Mode Management Guide (R22-11)](https://www.autosar.org/fileadmin/standards/R22-11/CP/AUTOSAR_EXP_ModeManagementGuide.pdf)

### Tools and Libraries
- [cogu/autosar Python Library](https://github.com/cogu/autosar)
- [AUTOSAR Python Documentation](https://autosar.readthedocs.io/)
- [EB tresos Studio](https://www.elektrobit.com/products/ecu/eb-tresos/studio/)
- [Vector DaVinci](https://www.mathworks.com/products/connections/product_detail/davinci-developer-and-davinci-configurator-pro.html)
- [dSPACE SystemDesk](https://www.dspace.com/en/inc/home/products/systems/system_architecture/sd_casestudy_ar-validation.cfm)

### Tutorials and Guides
- [AUTOSAR for Dummies - Methodology](https://www.vtronics.in/2019/09/autosar-for-dummies-part-4-autosar.html)
- [Embitel AUTOSAR Guide](https://www.embitel.com/product-engineering-2/automotive/autosar)
- [Automotive Wiki](https://automotive.wiki/index.php/AutosarDataType)
- [AUTOSAR Today](https://www.autosartoday.com/)

### Academic and Technical Analysis
- [The AUTOSAR XML Schema and Its Relevance for AUTOSAR Tools (ResearchGate)](https://www.researchgate.net/publication/224506602_The_Autosar_XML_Schema_and_Its_Relevance_for_Autosar_Tools)
- [Understanding AUTOSAR ARXML for Communication Networks (Intrepid)](https://www.intrepidcs.net.cn/wp-content/uploads/2019/05/202._Understanding_ARXML_EEA_COM_TD_USA_2019.pdf)
- [HPI AUTOSAR Methodology (PDF)](https://hpi.de/fileadmin/user_upload/fachgebiete/giese/Ausarbeitungen_AUTOSAR0809/Methodology_hebig.pdf)

---

## 9. Open Questions for Rupa Design

1. **Fidelity Level:** Should Rupa target 100% ARXML fidelity or accept some limitations for cleaner syntax?

2. **Metamodel Packaging:** Should AUTOSAR metamodel be built-in or loadable as a domain package?

3. **Version Mapping:** How to handle mapping between Rupa editions and AUTOSAR releases?

4. **Tooling Integration:** Priority of integration with existing AUTOSAR tools vs. standalone workflow?

5. **Constraint Language:** Can Rupa's validation language fully replace OCL for AUTOSAR semantics?

6. **Code Generation:** Should Rupa include RTE/BSW code generation or leave to external tools?
