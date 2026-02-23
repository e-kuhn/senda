# Use Case 08: Unified Type System

AUTOSAR's type system splits every data type into three separate artifacts: an
ApplicationDataType describing physical meaning (units, ranges, computation
methods), an ImplementationDataType describing binary representation (base types,
byte ordering), and a DataTypeMap linking them inside a DataTypeMappingSet. This
triple-artifact design exists for good reasons -- portability across ECUs,
separation of physical and binary concerns -- but most projects don't exploit
this flexibility. Engineers just want one type.

Senda's unified type system collapses the split into single type declarations.
A set of dissolution transforms then regenerates the full AUTOSAR triple when
the model needs to enter the concrete AUTOSAR domain. The value proposition:
write 15 lines of Rupa, get the equivalent of 150+ lines of ARXML.

---

## ARXML Baseline

What a single VehicleSpeed type looks like in native AUTOSAR. Three separate
elements plus a CompuMethod, all cross-referenced by path:

```xml
<AR-PACKAGES>
  <AR-PACKAGE>
    <SHORT-NAME>CompuMethods</SHORT-NAME>
    <ELEMENTS>
      <COMPU-METHOD>
        <SHORT-NAME>CM_VehicleSpeed</SHORT-NAME>
        <CATEGORY>LINEAR</CATEGORY>
        <COMPU-INTERNAL-TO-PHYS>
          <COMPU-SCALES>
            <COMPU-SCALE>
              <LOWER-LIMIT INTERVAL-TYPE="CLOSED">0</LOWER-LIMIT>
              <UPPER-LIMIT INTERVAL-TYPE="CLOSED">65535</UPPER-LIMIT>
              <COMPU-RATIONAL-COEFFS>
                <COMPU-NUMERATOR><V>0</V><V>0.01</V></COMPU-NUMERATOR>
                <COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>
              </COMPU-RATIONAL-COEFFS>
            </COMPU-SCALE>
          </COMPU-SCALES>
        </COMPU-INTERNAL-TO-PHYS>
      </COMPU-METHOD>
      <COMPU-METHOD>
        <SHORT-NAME>CM_EngineTemp</SHORT-NAME>
        <CATEGORY>LINEAR</CATEGORY>
        <COMPU-INTERNAL-TO-PHYS>
          <COMPU-SCALES>
            <COMPU-SCALE>
              <LOWER-LIMIT INTERVAL-TYPE="CLOSED">0</LOWER-LIMIT>
              <UPPER-LIMIT INTERVAL-TYPE="CLOSED">255</UPPER-LIMIT>
              <COMPU-RATIONAL-COEFFS>
                <COMPU-NUMERATOR><V>-40</V><V>1</V></COMPU-NUMERATOR>
                <COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>
              </COMPU-RATIONAL-COEFFS>
            </COMPU-SCALE>
          </COMPU-SCALES>
        </COMPU-INTERNAL-TO-PHYS>
      </COMPU-METHOD>
      <COMPU-METHOD>
        <SHORT-NAME>CM_GearPosition</SHORT-NAME>
        <CATEGORY>TEXTTABLE</CATEGORY>
        <COMPU-INTERNAL-TO-PHYS>
          <COMPU-SCALES>
            <COMPU-SCALE>
              <LOWER-LIMIT>0</LOWER-LIMIT><UPPER-LIMIT>0</UPPER-LIMIT>
              <COMPU-CONST><VT>Park</VT></COMPU-CONST>
            </COMPU-SCALE>
            <COMPU-SCALE>
              <LOWER-LIMIT>1</LOWER-LIMIT><UPPER-LIMIT>1</UPPER-LIMIT>
              <COMPU-CONST><VT>Reverse</VT></COMPU-CONST>
            </COMPU-SCALE>
            <COMPU-SCALE>
              <LOWER-LIMIT>2</LOWER-LIMIT><UPPER-LIMIT>2</UPPER-LIMIT>
              <COMPU-CONST><VT>Neutral</VT></COMPU-CONST>
            </COMPU-SCALE>
            <COMPU-SCALE>
              <LOWER-LIMIT>3</LOWER-LIMIT><UPPER-LIMIT>3</UPPER-LIMIT>
              <COMPU-CONST><VT>Drive</VT></COMPU-CONST>
            </COMPU-SCALE>
          </COMPU-SCALES>
        </COMPU-INTERNAL-TO-PHYS>
      </COMPU-METHOD>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>ApplicationDataTypes</SHORT-NAME>
    <ELEMENTS>
      <APPLICATION-PRIMITIVE-DATA-TYPE>
        <SHORT-NAME>VehicleSpeed</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
        <SW-DATA-DEF-PROPS>
          <SW-DATA-DEF-PROPS-VARIANTS>
            <SW-DATA-DEF-PROPS-CONDITIONAL>
              <COMPU-METHOD-REF DEST="COMPU-METHOD">/CompuMethods/CM_VehicleSpeed</COMPU-METHOD-REF>
            </SW-DATA-DEF-PROPS-CONDITIONAL>
          </SW-DATA-DEF-PROPS-VARIANTS>
        </SW-DATA-DEF-PROPS>
      </APPLICATION-PRIMITIVE-DATA-TYPE>
      <APPLICATION-PRIMITIVE-DATA-TYPE>
        <SHORT-NAME>EngineTemp</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
        <SW-DATA-DEF-PROPS>
          <SW-DATA-DEF-PROPS-VARIANTS>
            <SW-DATA-DEF-PROPS-CONDITIONAL>
              <COMPU-METHOD-REF DEST="COMPU-METHOD">/CompuMethods/CM_EngineTemp</COMPU-METHOD-REF>
            </SW-DATA-DEF-PROPS-CONDITIONAL>
          </SW-DATA-DEF-PROPS-VARIANTS>
        </SW-DATA-DEF-PROPS>
      </APPLICATION-PRIMITIVE-DATA-TYPE>
      <APPLICATION-PRIMITIVE-DATA-TYPE>
        <SHORT-NAME>GearPosition</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
        <SW-DATA-DEF-PROPS>
          <SW-DATA-DEF-PROPS-VARIANTS>
            <SW-DATA-DEF-PROPS-CONDITIONAL>
              <COMPU-METHOD-REF DEST="COMPU-METHOD">/CompuMethods/CM_GearPosition</COMPU-METHOD-REF>
            </SW-DATA-DEF-PROPS-CONDITIONAL>
          </SW-DATA-DEF-PROPS-VARIANTS>
        </SW-DATA-DEF-PROPS>
      </APPLICATION-PRIMITIVE-DATA-TYPE>
      <APPLICATION-RECORD-DATA-TYPE>
        <SHORT-NAME>VehicleData</SHORT-NAME>
        <CATEGORY>STRUCTURE</CATEGORY>
        <ELEMENTS>
          <APPLICATION-RECORD-ELEMENT>
            <SHORT-NAME>speed</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/ApplicationDataTypes/VehicleSpeed</TYPE-TREF>
          </APPLICATION-RECORD-ELEMENT>
          <APPLICATION-RECORD-ELEMENT>
            <SHORT-NAME>engineTemp</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/ApplicationDataTypes/EngineTemp</TYPE-TREF>
          </APPLICATION-RECORD-ELEMENT>
          <APPLICATION-RECORD-ELEMENT>
            <SHORT-NAME>gear</SHORT-NAME>
            <TYPE-TREF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/ApplicationDataTypes/GearPosition</TYPE-TREF>
          </APPLICATION-RECORD-ELEMENT>
        </ELEMENTS>
      </APPLICATION-RECORD-DATA-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>ImplementationDataTypes</SHORT-NAME>
    <ELEMENTS>
      <IMPLEMENTATION-DATA-TYPE>
        <SHORT-NAME>VehicleSpeed_Impl</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
        <SW-DATA-DEF-PROPS>
          <SW-DATA-DEF-PROPS-VARIANTS>
            <SW-DATA-DEF-PROPS-CONDITIONAL>
              <BASE-TYPE-REF DEST="SW-BASE-TYPE">/PlatformTypes/uint16</BASE-TYPE-REF>
            </SW-DATA-DEF-PROPS-CONDITIONAL>
          </SW-DATA-DEF-PROPS-VARIANTS>
        </SW-DATA-DEF-PROPS>
      </IMPLEMENTATION-DATA-TYPE>
      <IMPLEMENTATION-DATA-TYPE>
        <SHORT-NAME>EngineTemp_Impl</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
        <SW-DATA-DEF-PROPS>
          <SW-DATA-DEF-PROPS-VARIANTS>
            <SW-DATA-DEF-PROPS-CONDITIONAL>
              <BASE-TYPE-REF DEST="SW-BASE-TYPE">/PlatformTypes/uint8</BASE-TYPE-REF>
            </SW-DATA-DEF-PROPS-CONDITIONAL>
          </SW-DATA-DEF-PROPS-VARIANTS>
        </SW-DATA-DEF-PROPS>
      </IMPLEMENTATION-DATA-TYPE>
      <IMPLEMENTATION-DATA-TYPE>
        <SHORT-NAME>GearPosition_Impl</SHORT-NAME>
        <CATEGORY>VALUE</CATEGORY>
        <SW-DATA-DEF-PROPS>
          <SW-DATA-DEF-PROPS-VARIANTS>
            <SW-DATA-DEF-PROPS-CONDITIONAL>
              <BASE-TYPE-REF DEST="SW-BASE-TYPE">/PlatformTypes/uint8</BASE-TYPE-REF>
            </SW-DATA-DEF-PROPS-CONDITIONAL>
          </SW-DATA-DEF-PROPS-VARIANTS>
        </SW-DATA-DEF-PROPS>
      </IMPLEMENTATION-DATA-TYPE>
      <IMPLEMENTATION-DATA-TYPE>
        <SHORT-NAME>VehicleData_Impl</SHORT-NAME>
        <CATEGORY>STRUCTURE</CATEGORY>
        <SUB-ELEMENTS>
          <IMPLEMENTATION-DATA-TYPE-ELEMENT>
            <SHORT-NAME>speed</SHORT-NAME>
            <SW-DATA-DEF-PROPS>
              <SW-DATA-DEF-PROPS-VARIANTS>
                <SW-DATA-DEF-PROPS-CONDITIONAL>
                  <IMPLEMENTATION-DATA-TYPE-REF DEST="IMPLEMENTATION-DATA-TYPE">/ImplementationDataTypes/VehicleSpeed_Impl</IMPLEMENTATION-DATA-TYPE-REF>
                </SW-DATA-DEF-PROPS-CONDITIONAL>
              </SW-DATA-DEF-PROPS-VARIANTS>
            </SW-DATA-DEF-PROPS>
          </IMPLEMENTATION-DATA-TYPE-ELEMENT>
          <IMPLEMENTATION-DATA-TYPE-ELEMENT>
            <SHORT-NAME>engineTemp</SHORT-NAME>
            <SW-DATA-DEF-PROPS>
              <SW-DATA-DEF-PROPS-VARIANTS>
                <SW-DATA-DEF-PROPS-CONDITIONAL>
                  <IMPLEMENTATION-DATA-TYPE-REF DEST="IMPLEMENTATION-DATA-TYPE">/ImplementationDataTypes/EngineTemp_Impl</IMPLEMENTATION-DATA-TYPE-REF>
                </SW-DATA-DEF-PROPS-CONDITIONAL>
              </SW-DATA-DEF-PROPS-VARIANTS>
            </SW-DATA-DEF-PROPS>
          </IMPLEMENTATION-DATA-TYPE-ELEMENT>
          <IMPLEMENTATION-DATA-TYPE-ELEMENT>
            <SHORT-NAME>gear</SHORT-NAME>
            <SW-DATA-DEF-PROPS>
              <SW-DATA-DEF-PROPS-VARIANTS>
                <SW-DATA-DEF-PROPS-CONDITIONAL>
                  <IMPLEMENTATION-DATA-TYPE-REF DEST="IMPLEMENTATION-DATA-TYPE">/ImplementationDataTypes/GearPosition_Impl</IMPLEMENTATION-DATA-TYPE-REF>
                </SW-DATA-DEF-PROPS-CONDITIONAL>
              </SW-DATA-DEF-PROPS-VARIANTS>
            </SW-DATA-DEF-PROPS>
          </IMPLEMENTATION-DATA-TYPE-ELEMENT>
        </SUB-ELEMENTS>
      </IMPLEMENTATION-DATA-TYPE>
    </ELEMENTS>
  </AR-PACKAGE>

  <AR-PACKAGE>
    <SHORT-NAME>DataTypeMappingSets</SHORT-NAME>
    <ELEMENTS>
      <DATA-TYPE-MAPPING-SET>
        <SHORT-NAME>DtMapping_VehicleV1</SHORT-NAME>
        <DATA-TYPE-MAPS>
          <DATA-TYPE-MAP>
            <APPLICATION-DATA-TYPE-REF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/ApplicationDataTypes/VehicleSpeed</APPLICATION-DATA-TYPE-REF>
            <IMPLEMENTATION-DATA-TYPE-REF DEST="IMPLEMENTATION-DATA-TYPE">/ImplementationDataTypes/VehicleSpeed_Impl</IMPLEMENTATION-DATA-TYPE-REF>
          </DATA-TYPE-MAP>
          <DATA-TYPE-MAP>
            <APPLICATION-DATA-TYPE-REF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/ApplicationDataTypes/EngineTemp</APPLICATION-DATA-TYPE-REF>
            <IMPLEMENTATION-DATA-TYPE-REF DEST="IMPLEMENTATION-DATA-TYPE">/ImplementationDataTypes/EngineTemp_Impl</IMPLEMENTATION-DATA-TYPE-REF>
          </DATA-TYPE-MAP>
          <DATA-TYPE-MAP>
            <APPLICATION-DATA-TYPE-REF DEST="APPLICATION-PRIMITIVE-DATA-TYPE">/ApplicationDataTypes/GearPosition</APPLICATION-DATA-TYPE-REF>
            <IMPLEMENTATION-DATA-TYPE-REF DEST="IMPLEMENTATION-DATA-TYPE">/ImplementationDataTypes/GearPosition_Impl</IMPLEMENTATION-DATA-TYPE-REF>
          </DATA-TYPE-MAP>
        </DATA-TYPE-MAPS>
      </DATA-TYPE-MAPPING-SET>
    </ELEMENTS>
  </AR-PACKAGE>
</AR-PACKAGES>
```

That is approximately 180 lines of XML for four data types (three primitives and
one record). Each type requires coordinating elements across four separate
ARPackages with cross-references by path. Adding a single new type means editing
four locations.

---

## Rupa Solution

### Step 1: Unified Domain Definition

The unified domain derives from the full AUTOSAR R24-11 domain, copying its
entire type system. It then adds simplified base types that carry conversion
parameters as roles. Engineers derive their types from these base types instead
of manually coordinating ADTs, IDTs, and DataTypeMaps.

```rupa
// unified-types.rupa -- simplified base types for the unified domain
domain autosar-2411-unified = autosar-2411;

// M2 aliases: M3 primitives cannot appear directly in M2 composite roles
type Factor = ::float;
type Offset = ::float;

// Base type for linear-converted quantities (dissolves to LINEAR CompuMethod)
type LinearQuantity = ARElement {
    .factor: Factor;
    .offset: Offset;
};

// Base type for pass-through quantities (dissolves to IDENTICAL CompuMethod)
type IdenticalQuantity = ARElement {};
```

Two base types cover the most common AUTOSAR conversion categories. Enums
(`::enum(...)`) dissolve to TEXTTABLE CompuMethods using ordinal position --
no special base type needed. Both base types inherit from `ARElement` (available
from the copied `autosar-2411` domain) so they carry a `.shortName` for identity.

### Step 2: User Type Definitions and Scaling Templates

Engineers work entirely in a domain derived from `autosar-2411-unified`. Type
definitions are M2 (structure); scaling parameters are M1 (values on instances).
The `from` keyword copies scaling templates into new instances.

```rupa
// vehicle-types.rupa -- type definitions (M2)
domain vehicle-v1 = autosar-2411-unified;

type VehicleSpeed = LinearQuantity;
type EngineTemp = LinearQuantity;
type GearPosition = ::enum(Park, Reverse, Neutral, Drive);

type VehicleData = {
    .speed: VehicleSpeed;
    .engineTemp: EngineTemp;
    .gear: GearPosition;
};
```

```rupa
// vehicle-model.rupa -- scaling templates and instances (M1)
using domain vehicle-v1;

// Scaling templates: set the conversion parameters once
let speed_scaling = LinearQuantity {
    .factor = 0.01;
    .offset = 0.0;
};

let temp_scaling = LinearQuantity {
    .factor = 1.0;
    .offset = -40.0;
};

// Instances copy scaling via `from`
VehicleSpeed VehicleSpeed from speed_scaling {}
EngineTemp EngineTemp from temp_scaling {}

VehicleData VehicleData {
    .speed = /VehicleSpeed;
    .engineTemp = /EngineTemp;
    .gear = Park;
}
```

Fifteen lines of Rupa define four types and their conversion parameters. No
CompuMethods, no ImplementationDataTypes, no DataTypeMaps. The dissolution
transforms generate all of that.
