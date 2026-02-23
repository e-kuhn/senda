# De-AUTOSAR Progress Tracker

Task: Remove all AUTOSAR-specific terminology and automotive-specific examples from `design/spec/`.
Replace with generic, domain-neutral examples.

## Status: COMPLETE

All AUTOSAR-specific terminology and automotive-specific examples have been removed from `design/spec/`.
Verified via comprehensive grep — zero matches for any AUTOSAR/automotive terms.

## What Was Done

### Prior session
- ~49 files edited, ~1700 lines changed
- `examples/autosar-admindata-sdg-encoding.md` deleted (replaced by `extension-data-encoding.md`)

### This session (2026-02-16)
All remaining files cleaned. Four parallel agents + manual fixups:

**Agent 1: instance-references-and-archetypes.md** (heaviest file)
- SwComponentType → CompositeModule, PPortPrototype → OutputPort, RPortPrototype → InputPort
- PortInterface → PortContract, DataElement → DataField, VehicleControl → ControlAssembly
- All instance-ref types updated (PPortInComponentRef → OutputPortRef, etc.)
- "automotive standards" → "component frameworks"

**Agent 2: 03-data-modeling (11 files)**
- variants-and-configurations: VehicleLine → ProductLine, Vehicle → Device
- references-and-paths: DataSignal → Signal
- identity-expression-syntax: DataSignal VehicleSpeed → Signal Temperature
- abstract-types: PackageableElement → Element, PortInterface → Connector
- root-types: ECU → device, VehicleSpeed → Temperature
- cross-role-identity-uniqueness: DataSignal → Signal
- collection-role-semantics: DataSignal → Signal
- collections: "automotive" → "industrial", FrameType "CAN" → Protocol "tcp"
- containment-role-inference: DataSignal → Signal
- object-node-structure: CAN → Main, EngineSpeed → Temperature
- enum-type: canFd → tcp, flexRay → udp, "some/ip" → "mqtt/ws"

**Agent 3: 01-foundational + 02-syntax + 06-extensibility (9 files)**
- relationship-to-existing-formats: removed ARXML references
- language-philosophy: CAN → Main, EngineSpeed → Temperature
- purpose-and-scope: "Automotive (vehicle architectures...)" → "Industrial (equipment models...)"
- grouping-strategy: CAN/Vehicle/Engine → Main/System/Controller
- keyword-disambiguation: VehicleLine → ProductLine
- keywords: "automotive domain" → "industrial domain"
- operator-precedence: config.can → config.network
- containment-chain-instantiation: DataSignal → Signal, PackageableElement → Element
- primitive-parsing-pipeline: "short-name conventions" → "naming conventions"

**Agent 4: 04-12 folders (15 files)**
- research-modularity-composition: automotive.signals → catalog.items
- imports-and-dependencies: EngineSpeed → MainSensor
- namespaces-and-scoping: CAN → Eth
- path-block-modification: BrakingIPdu → StatusMessage, Communication → Messaging
- composite-let-bindings: BrakingIPdu → StatusMessage
- path-mutation-and-distribution: BrakingIPdu → StatusMessage
- mutability-invariants: Communication → Messaging
- change-tracking: "automotive" → "industrial"
- expression-evaluation-and-name-resolution: config.can → config.network
- validation-language: Vehicle → Device/System, BrakeSystem → SafetyModule
- transformation-language: EngineSpeed → MainSensor
- i18n: "CAN-FD Bus" → "10G-Eth Hub"
- tooling: vehicle-model → sensor-model
- compatibility: "(automotive, healthcare)" → "(manufacturing, healthcare)"
- documentation: automotive-simplified → industrial-simplified

**Manual fixups:**
- diff-and-merge.md: Vehicle → Device
- dsl-vs-library-rationale.md: vehicle.rupa → model.rupa

## Verification
Final grep for all AUTOSAR/automotive terms: **zero matches** across entire `design/spec/`.
