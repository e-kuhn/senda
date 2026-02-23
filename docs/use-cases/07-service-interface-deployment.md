# Use Case 07: Service Interface Deployment (Adaptive Platform)

Define an Adaptive Platform `ServiceInterface` with events, methods, and fields,
then deploy it to SOME/IP with concrete service and method IDs. Show the
corresponding `ProvidedServiceInstance` and `ConsumedServiceInstance`
configuration. This use case demonstrates that the same Rupa patterns used for
Classic Platform component architectures -- types, prototypes, references,
containment role inference -- apply directly to AP service-oriented
communication, and extends the coverage to deployment manifests.

---

## Scenario

A radar perception system exposes a **RadarService** `ServiceInterface`
containing:

- An **event** (`BrakeEvent`) for asynchronous notification of braking conditions.
- A **method** (`Calibrate`) for request/response calibration operations.
- A **field** (`UpdateRate`) with getter, setter, and notifier access.

The service is deployed over SOME/IP on an Ethernet-connected machine. The
deployment assigns numeric service, method, and event IDs. A
`ProvidedServiceInstance` advertises the service on a specific endpoint; a
`ConsumedServiceInstance` on a client ECU discovers and subscribes to it.

In the Adaptive Platform, `ServiceInterface` is a first-class meta-class that
directly aggregates events, methods, and fields. In the Classic Platform, the
same concept must be emulated through a `Collection` wrapping
`SenderReceiverInterface` and `ClientServerInterface` elements with
`SO_SERVICE_INTERFACE` semantics. This use case focuses on the native AP
representation.

---

## ARXML Baseline

Abbreviated ARXML for the `ServiceInterface`, its SOME/IP deployment, and
the provider/consumer service instances.

```xml
<AR-PACKAGES>
  <!-- Data types -->
  <AR-PACKAGE>
    <SHORT-NAME>DataTypes</SHORT-NAME>
    <ELEMENTS>
      <STD-CPP-IMPLEMENTATION-DATA-TYPE>
        <SHORT-NAME>RadarStructure_T</SHORT-NAME>
        <CATEGORY>STRUCTURE</CATEGORY>
      </STD-CPP-IMPLEMENTATION-DATA-TYPE>
      <STD-CPP-IMPLEMENTATION-DATA-TYPE>
        <SHORT-NAME>CalibResult_T</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
      </STD-CPP-IMPLEMENTATION-DATA-TYPE>
      <STD-CPP-IMPLEMENTATION-DATA-TYPE>
        <SHORT-NAME>UInt16_T</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
      </STD-CPP-IMPLEMENTATION-DATA-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- Service interface -->
  <AR-PACKAGE>
    <SHORT-NAME>ServiceInterfaces</SHORT-NAME>
    <ELEMENTS>
      <SERVICE-INTERFACE>
        <SHORT-NAME>RadarService</SHORT-NAME>
        <NAMESPACES>
          <SYMBOL-PROPS>
            <SHORT-NAME>radar</SHORT-NAME>
            <SYMBOL>radar</SYMBOL>
          </SYMBOL-PROPS>
        </NAMESPACES>
        <EVENTS>
          <VARIABLE-DATA-PROTOTYPE>
            <SHORT-NAME>BrakeEvent</SHORT-NAME>
            <TYPE-TREF DEST="STD-CPP-IMPLEMENTATION-DATA-TYPE"
              >/DataTypes/RadarStructure_T</TYPE-TREF>
          </VARIABLE-DATA-PROTOTYPE>
        </EVENTS>
        <METHODS>
          <CLIENT-SERVER-OPERATION>
            <SHORT-NAME>Calibrate</SHORT-NAME>
            <ARGUMENTS>
              <ARGUMENT-DATA-PROTOTYPE>
                <SHORT-NAME>config</SHORT-NAME>
                <TYPE-TREF DEST="STD-CPP-IMPLEMENTATION-DATA-TYPE"
                  >/DataTypes/RadarStructure_T</TYPE-TREF>
                <DIRECTION>IN</DIRECTION>
              </ARGUMENT-DATA-PROTOTYPE>
              <ARGUMENT-DATA-PROTOTYPE>
                <SHORT-NAME>result</SHORT-NAME>
                <TYPE-TREF DEST="STD-CPP-IMPLEMENTATION-DATA-TYPE"
                  >/DataTypes/CalibResult_T</TYPE-TREF>
                <DIRECTION>OUT</DIRECTION>
              </ARGUMENT-DATA-PROTOTYPE>
            </ARGUMENTS>
          </CLIENT-SERVER-OPERATION>
        </METHODS>
        <FIELDS>
          <FIELD>
            <SHORT-NAME>UpdateRate</SHORT-NAME>
            <TYPE-TREF DEST="STD-CPP-IMPLEMENTATION-DATA-TYPE"
              >/DataTypes/UInt16_T</TYPE-TREF>
            <HAS-GETTER>true</HAS-GETTER>
            <HAS-SETTER>true</HAS-SETTER>
            <HAS-NOTIFIER>true</HAS-NOTIFIER>
          </FIELD>
        </FIELDS>
      </SERVICE-INTERFACE>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- SOME/IP service interface deployment -->
  <AR-PACKAGE>
    <SHORT-NAME>Deployment</SHORT-NAME>
    <ELEMENTS>
      <SOMEIP-SERVICE-INTERFACE-DEPLOYMENT>
        <SHORT-NAME>RadarService_SomeIp</SHORT-NAME>
        <SERVICE-INTERFACE-REF DEST="SERVICE-INTERFACE"
          >/ServiceInterfaces/RadarService</SERVICE-INTERFACE-REF>
        <SERVICE-INTERFACE-ID>4711</SERVICE-INTERFACE-ID>
        <SERVICE-INTERFACE-VERSION>
          <MAJOR-VERSION>1</MAJOR-VERSION>
          <MINOR-VERSION>0</MINOR-VERSION>
        </SERVICE-INTERFACE-VERSION>
        <EVENT-DEPLOYMENTS>
          <SOMEIP-EVENT-DEPLOYMENT>
            <SHORT-NAME>BrakeEvent_Depl</SHORT-NAME>
            <EVENT-REF DEST="VARIABLE-DATA-PROTOTYPE"
              >/ServiceInterfaces/RadarService/BrakeEvent</EVENT-REF>
            <EVENT-ID>32769</EVENT-ID>
            <TRANSPORT-PROTOCOL>UDP</TRANSPORT-PROTOCOL>
          </SOMEIP-EVENT-DEPLOYMENT>
        </EVENT-DEPLOYMENTS>
        <METHOD-DEPLOYMENTS>
          <SOMEIP-METHOD-DEPLOYMENT>
            <SHORT-NAME>Calibrate_Depl</SHORT-NAME>
            <METHOD-REF DEST="CLIENT-SERVER-OPERATION"
              >/ServiceInterfaces/RadarService/Calibrate</METHOD-REF>
            <METHOD-ID>1</METHOD-ID>
            <TRANSPORT-PROTOCOL>TCP</TRANSPORT-PROTOCOL>
          </SOMEIP-METHOD-DEPLOYMENT>
        </METHOD-DEPLOYMENTS>
        <FIELD-DEPLOYMENTS>
          <SOMEIP-FIELD-DEPLOYMENT>
            <SHORT-NAME>UpdateRate_Depl</SHORT-NAME>
            <FIELD-REF DEST="FIELD"
              >/ServiceInterfaces/RadarService/UpdateRate</FIELD-REF>
            <GETTER>
              <METHOD-ID>2</METHOD-ID>
            </GETTER>
            <SETTER>
              <METHOD-ID>3</METHOD-ID>
            </SETTER>
            <NOTIFIER>
              <EVENT-ID>32770</EVENT-ID>
            </NOTIFIER>
          </SOMEIP-FIELD-DEPLOYMENT>
        </FIELD-DEPLOYMENTS>
      </SOMEIP-SERVICE-INTERFACE-DEPLOYMENT>
    </ELEMENTS>
  </AR-PACKAGE>

  <!-- Service instances -->
  <AR-PACKAGE>
    <SHORT-NAME>ServiceInstances</SHORT-NAME>
    <ELEMENTS>
      <PROVIDED-SERVICE-INSTANCE>
        <SHORT-NAME>RadarService_Provided</SHORT-NAME>
        <SERVICE-IDENTIFIER>4711</SERVICE-IDENTIFIER>
        <INSTANCE-IDENTIFIER>1</INSTANCE-IDENTIFIER>
        <MAJOR-VERSION>1</MAJOR-VERSION>
        <MINOR-VERSION>0</MINOR-VERSION>
        <LOCAL-UNICAST-ADDRESSES>
          <APPLICATION-ENDPOINT-REF DEST="APPLICATION-ENDPOINT"
            >/Network/RadarECU_Endpoint</APPLICATION-ENDPOINT-REF>
        </LOCAL-UNICAST-ADDRESSES>
        <EVENT-HANDLERS>
          <EVENT-HANDLER>
            <SHORT-NAME>BrakeEventGroup</SHORT-NAME>
            <EVENT-GROUP-IDENTIFIER>1</EVENT-GROUP-IDENTIFIER>
          </EVENT-HANDLER>
        </EVENT-HANDLERS>
      </PROVIDED-SERVICE-INSTANCE>

      <CONSUMED-SERVICE-INSTANCE>
        <SHORT-NAME>RadarService_Consumed</SHORT-NAME>
        <SERVICE-IDENTIFIER>4711</SERVICE-IDENTIFIER>
        <REQUIRED-SERVICE-INSTANCE-ID>1</REQUIRED-SERVICE-INSTANCE-ID>
        <MAJOR-VERSION>1</MAJOR-VERSION>
        <LOCAL-UNICAST-ADDRESSES>
          <APPLICATION-ENDPOINT-REF DEST="APPLICATION-ENDPOINT"
            >/Network/FusionECU_Endpoint</APPLICATION-ENDPOINT-REF>
        </LOCAL-UNICAST-ADDRESSES>
        <CONSUMED-EVENT-GROUPS>
          <CONSUMED-EVENT-GROUP>
            <SHORT-NAME>BrakeEventGroup_Sub</SHORT-NAME>
            <EVENT-GROUP-IDENTIFIER>1</EVENT-GROUP-IDENTIFIER>
          </CONSUMED-EVENT-GROUP>
        </CONSUMED-EVENT-GROUPS>
      </CONSUMED-SERVICE-INSTANCE>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

The ARXML totals approximately 160 lines. Notable structural costs:

- The `ServiceInterface` nests events, methods, and fields under separate
  wrapper elements (`<EVENTS>`, `<METHODS>`, `<FIELDS>`) that mirror the AP
  metamodel aggregation roles.
- The SOME/IP deployment cross-references each event, method, and field by
  path in `DEST`-attributed `REF` elements. Each deployment element requires
  its own wrapper collection (`<EVENT-DEPLOYMENTS>`, `<METHOD-DEPLOYMENTS>`,
  `<FIELD-DEPLOYMENTS>`).
- Field deployment nests three sub-structures (`GETTER`, `SETTER`, `NOTIFIER`)
  each containing their own method/event IDs.
- Service instance configuration repeats the service ID and version from the
  deployment, with no structural mechanism to enforce consistency.

---

## Rupa Solution

The equivalent Rupa model. M2 metamodel types for the Adaptive Platform are
assumed to be defined in a domain library; this is M1 instance authoring only.

```rupa
// radar-service.rupa
using domain autosar_ap;

// --- Data Types ---

StdCppImplementationDataType RadarStructure_T {
    .category = "STRUCTURE";
}

StdCppImplementationDataType CalibResult_T {
    .category = "VALUE";
}

StdCppImplementationDataType UInt16_T {
    .category = "VALUE";
}

// --- Service Interface ---
//
// In the AP metamodel, ServiceInterface directly aggregates events,
// methods, and fields.  Rupa's containment role inference assigns each
// child to the correct aggregation role based on its M2 type:
//   VariableDataPrototype  -> .events
//   ClientServerOperation  -> .methods
//   Field                  -> .fields

ServiceInterface RadarService {
    .namespace = "radar";

    // Event: asynchronous notification
    VariableDataPrototype BrakeEvent {
        .type = /DataTypes/RadarStructure_T;
    }

    // Method: request/response operation
    ClientServerOperation Calibrate {
        ArgumentDataPrototype config {
            .type      = /DataTypes/RadarStructure_T;
            .direction = IN;
        }
        ArgumentDataPrototype result {
            .type      = /DataTypes/CalibResult_T;
            .direction = OUT;
        }
    }

    // Field: get/set/notify property
    Field UpdateRate {
        .type        = /DataTypes/UInt16_T;
        .hasGetter   = true;
        .hasSetter   = true;
        .hasNotifier = true;
    }
}
```

```rupa
// radar-deployment.rupa
using domain autosar_ap;

// --- SOME/IP Deployment ---
//
// The deployment references the service interface and assigns numeric
// IDs to each service element.  References into the ServiceInterface
// use standard typed paths -- no DEST attributes needed.

SomeipServiceInterfaceDeployment RadarService_SomeIp {
    .serviceInterface = /ServiceInterfaces/RadarService;
    .serviceInterfaceId = 4711;
    .majorVersion = 1;
    .minorVersion = 0;

    // Event deployment: references the event inside the interface
    SomeipEventDeployment BrakeEvent_Depl {
        .event             = /ServiceInterfaces/RadarService/BrakeEvent;
        .eventId           = 0x8001;
        .transportProtocol = UDP;
    }

    // Method deployment: references the operation inside the interface
    SomeipMethodDeployment Calibrate_Depl {
        .method            = /ServiceInterfaces/RadarService/Calibrate;
        .methodId          = 1;
        .transportProtocol = TCP;
    }

    // Field deployment: getter/setter are methods, notifier is an event
    SomeipFieldDeployment UpdateRate_Depl {
        .field      = /ServiceInterfaces/RadarService/UpdateRate;
        .getterId   = 2;
        .setterId   = 3;
        .notifierId = 0x8002;
    }
}
```

```rupa
// radar-instances.rupa
using domain autosar_ap;

// --- Service Instance Configuration ---
//
// ProvidedServiceInstance and ConsumedServiceInstance define the
// runtime service discovery parameters.  The service ID and version
// can be validated against the deployment via rules (see below).

ProvidedServiceInstance RadarService_Provided {
    .serviceIdentifier  = 4711;
    .instanceIdentifier = 1;
    .majorVersion       = 1;
    .minorVersion       = 0;
    .localUnicastAddress = /Network/RadarECU_Endpoint;

    EventHandler BrakeEventGroup {
        .eventGroupIdentifier = 1;
    }
}

ConsumedServiceInstance RadarService_Consumed {
    .serviceIdentifier        = 4711;
    .requiredServiceInstanceId = 1;
    .majorVersion              = 1;
    .localUnicastAddress       = /Network/FusionECU_Endpoint;

    ConsumedEventGroup BrakeEventGroup_Sub {
        .eventGroupIdentifier = 1;
    }
}
```

### Validation Rule: Service ID Consistency

In ARXML, the service ID is repeated across the deployment and every service
instance with no structural link enforcing consistency. In Rupa, a domain rule
can verify this:

```rupa
#[rule("service-id-consistent")]
let service_id_match(psi: ProvidedServiceInstance) =
    ::referrers(psi) | filter(r => r is SomeipServiceInterfaceDeployment)
    | all(depl => depl.serviceInterfaceId == psi.serviceIdentifier);
```

This rule queries the model for any `SomeipServiceInterfaceDeployment` that
references the same service and validates the numeric ID matches. The same
pattern applies to version consistency.

---

## Key Features Demonstrated

- **AP-native service modeling**: `ServiceInterface` directly aggregates
  events, methods, and fields as first-class children. Rupa's containment
  role inference assigns `VariableDataPrototype` to `.events`,
  `ClientServerOperation` to `.methods`, and `Field` to `.fields` -- the user
  never writes wrapper collections.

- **Typed cross-file references**: The deployment file references elements
  inside the service interface using absolute paths
  (`/ServiceInterfaces/RadarService/BrakeEvent`). These are typed references
  (`&VariableDataPrototype`, `&ClientServerOperation`, `&Field`) validated at
  compile time. No `DEST` attribute is needed.

- **Same patterns, different domain**: The Rupa patterns used for CP component
  architecture (Use Case 01) -- types, identity paths, typed references,
  containment role inference -- apply without modification to AP service
  interfaces. No new language constructs are needed.

- **Deployment as containment**: SOME/IP deployment elements
  (`SomeipEventDeployment`, `SomeipMethodDeployment`,
  `SomeipFieldDeployment`) are children of the deployment container. Their
  references back into the service interface are standard typed paths.

- **Validation across manifests**: Rupa rules can express cross-cutting
  constraints (service ID consistency between deployment and instance
  configuration) that ARXML cannot structurally enforce. The rule uses
  `::referrers` to navigate from the instance back to the deployment.

- **Multi-file organization**: The service interface definition, SOME/IP
  deployment, and instance configuration are naturally split across files.
  Rupa's cross-file reference resolution handles this transparently -- paths
  resolve across the merged model.

---

## Comparison

| Aspect | ARXML | Rupa |
|--------|-------|------|
| **ServiceInterface** | ~35 lines (wrappers, DEST refs) | ~20 lines |
| **SOME/IP deployment** | ~45 lines (3 wrapper collections) | ~20 lines |
| **Service instances** | ~40 lines each | ~12 lines each |
| **Total** | ~160 lines | ~65 lines |
| **Reference typing** | `DEST` attribute per reference | Metamodel-typed (`&T`) |
| **Wrapper elements** | 8 distinct wrappers | None |
| **ID consistency** | Manual (no enforcement) | Rule-based validation |
| **Field deployment** | Nested GETTER/SETTER/NOTIFIER sub-elements | Flat role assignment |
| **Cross-file references** | Full path in `DEST`-attributed REF | Standard identity paths |

The Rupa representation is roughly 60% shorter. The reduction comes from
eliminating XML wrapper collections, collapsing `DEST`-attributed references
into typed paths, and flattening nested deployment structures. The more
significant gain is structural: Rupa rules can enforce consistency constraints
that ARXML leaves to external tooling.

---

## CP vs. AP: Pattern Reuse

A key goal of Rupa is that the same language mechanisms serve both the Classic
and Adaptive Platforms. The following table traces the core patterns across
the two platforms:

| Pattern | Classic Platform (UC01) | Adaptive Platform (UC07) |
|---------|----------------------|------------------------|
| **Type / instance** | `SwComponentType` / `SwComponentPrototype` | `ServiceInterface` / `ProvidedServiceInstance` |
| **Containment role inference** | `PPortPrototype` -> `.ports` | `VariableDataPrototype` -> `.events` |
| **Typed references** | `.interface = /Interfaces/BrakePressureSRI` | `.event = /ServiceInterfaces/RadarService/BrakeEvent` |
| **Identity paths** | `/SwComponents/BrakeSensor` | `/ServiceInterfaces/RadarService/Calibrate` |
| **Deployment binding** | COM stack mapping (UC02) | `SomeipServiceInterfaceDeployment` |
| **Cross-cutting rules** | Bit overlap detection (UC02) | Service ID consistency |

No Rupa language extensions are required for AP modeling. The M2 metamodel
changes (different types and roles for AP concepts), but the M1 authoring
experience and language mechanisms are identical. A domain expert switching
between CP and AP projects encounters the same syntax, the same path system,
the same validation framework.

---

## Related Patterns

- **[Pattern 01: Identifiable and Paths](../patterns/01-identifiable-and-paths.md)** --
  identity-based paths resolve into `ServiceInterface` children the same way
  they resolve into `SwComponentType` children
- **[Pattern 02: Type / Prototype / Archetype](../patterns/02-type-prototype-archetype.md)** --
  the deployment-to-interface reference is a standard typed reference, not an
  archetype; AP does not use `/>` for service element access because events,
  methods, and fields are direct containment children of `ServiceInterface`
- **[Pattern 10: References and Ref-Bases](../patterns/10-references-and-ref-bases.md)** --
  cross-file references between deployment and interface use the same
  resolution as any other typed reference path
