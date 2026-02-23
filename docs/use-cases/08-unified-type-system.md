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

### Step 3: Dissolution Transforms

A transformation file bridges the unified domain back to the concrete AUTOSAR
domain. Write-mode transforms create multiple target objects from each source
object, placing them into the appropriate ARPackages. Phase 2 wires
cross-references after all objects exist.

```rupa
// dissolve.rupa -- unified → concrete AUTOSAR dissolution
using domain autosar-2411;
using domain autosar-2411-unified as unified;

// ── Phase 1: Structural creation ─────────────────────────────────

// LinearQuantity → CompuMethod (LINEAR) + ADT + IDT
#[transform]
let dissolve_linear(src: unified::LinearQuantity) {
    /CompuMethods += CompuMethod (src.shortName + "_CM") {
        .category = "LINEAR";
        .compuInternalToPhys = CompuInternalToPhys {
            CompuScale {
                .compuRationalCoeffs = CompuRationalCoeffs {
                    .compuNumerator = [src.offset, src.factor];
                    .compuDenominator = [1.0];
                };
            };
        };
    };

    /ApplicationDataTypes += ApplicationPrimitiveDataType (src.shortName) {
        .category = "VALUE";
    };

    /ImplementationDataTypes += ImplementationDataType (src.shortName + "_Impl") {
        .category = "VALUE";
    };
}

// Enum → CompuMethod (TEXTTABLE) + ADT + IDT
#[transform]
let dissolve_enum(src: unified::GearPosition) {
    /CompuMethods += CompuMethod (src.shortName + "_CM") {
        .category = "TEXTTABLE";
        .compuInternalToPhys = CompuInternalToPhys {
            ::variants(src) | enumerate() | each((idx, name) => {
                CompuScale {
                    .lowerLimit = idx;
                    .upperLimit = idx;
                    .compuConst = CompuConst { .vt = name; };
                };
            });
        };
    };

    /ApplicationDataTypes += ApplicationPrimitiveDataType (src.shortName) {
        .category = "VALUE";
    };

    /ImplementationDataTypes += ImplementationDataType (src.shortName + "_Impl") {
        .category = "VALUE";
    };
}

// Composite → ApplicationRecordDataType + STRUCTURE IDT
#[transform]
let dissolve_composite(src: unified::VehicleData) {
    /ApplicationDataTypes += ApplicationRecordDataType (src.shortName) {
        .category = "STRUCTURE";
        ::transform(src.speed, .elements);
        ::transform(src.engineTemp, .elements);
        ::transform(src.gear, .elements);
    };

    /ImplementationDataTypes += ImplementationDataType (src.shortName + "_Impl") {
        .category = "STRUCTURE";
        ::transform(src.speed, .subElements);
        ::transform(src.engineTemp, .subElements);
        ::transform(src.gear, .subElements);
    };
}

// ── Phase 2: Cross-reference wiring ──────────────────────────────

// Wire CompuMethod references into ADTs, set base types on IDTs, create
// DataTypeMaps. By Phase 2 all objects exist; ::targets finds them.
#[transform(phase = 2)]
let link_linear(src: unified::LinearQuantity) {
    let targets = ::targets(src);
    let adt = targets | filter(x => x is ApplicationPrimitiveDataType) | first();
    let cm = targets | filter(x => x is CompuMethod) | first();
    let idt = targets | filter(x => x is ImplementationDataType) | first();

    // Wire CompuMethod into ADT
    adt.swDataDefProps = SwDataDefProps {
        SwDataDefPropsConditional {
            .compuMethodRef = cm;
        };
    };

    // Set implementation base type (infer smallest platform type)
    let range = (1.0 / src.factor) * (src.offset + src.factor * 65535.0);
    idt.swDataDefProps = SwDataDefProps {
        SwDataDefPropsConditional {
            .baseTypeRef = if range <= 255.0 then /PlatformTypes/uint8
                           else if range <= 65535.0 then /PlatformTypes/uint16
                           else /PlatformTypes/uint32;
        };
    };

    // Create the DataTypeMap
    /DataTypeMappingSets/DtMapping += DataTypeMap {
        .applicationDataType = adt;
        .implementationDataType = idt;
    };
}

#[transform(phase = 2)]
let link_enum(src: unified::GearPosition) {
    let targets = ::targets(src);
    let adt = targets | filter(x => x is ApplicationPrimitiveDataType) | first();
    let cm = targets | filter(x => x is CompuMethod) | first();
    let idt = targets | filter(x => x is ImplementationDataType) | first();

    adt.swDataDefProps = SwDataDefProps {
        SwDataDefPropsConditional {
            .compuMethodRef = cm;
        };
    };

    idt.swDataDefProps = SwDataDefProps {
        SwDataDefPropsConditional {
            .baseTypeRef = /PlatformTypes/uint8;
        };
    };

    /DataTypeMappingSets/DtMapping += DataTypeMap {
        .applicationDataType = adt;
        .implementationDataType = idt;
    };
}
```

Two phases cleanly separate structural creation from cross-reference wiring.
Phase 1 creates all AUTOSAR artifacts and places them in the correct ARPackages.
Phase 2 uses `::targets` to find the objects created from each source, then
wires the `CompuMethod` references, infers the platform base type from the
scaling parameters, and creates the `DataTypeMap` entries.

### Step 4: Dissolved Output

After running the dissolution transforms, the target model in the `autosar-2411`
domain contains the full AUTOSAR artifact set. Shown here in Rupa format for
readability -- this is what `rupa inspect` would produce.

```rupa
// dissolved-output.rupa -- generated AUTOSAR model (target domain)
using domain autosar-2411;

ARPackage CompuMethods {
    CompuMethod CM_VehicleSpeed {
        .category = "LINEAR";
        .compuInternalToPhys = CompuInternalToPhys {
            CompuScale {
                .compuRationalCoeffs = CompuRationalCoeffs {
                    .compuNumerator = [0.0, 0.01];
                    .compuDenominator = [1.0];
                };
            };
        };
    }

    CompuMethod CM_EngineTemp {
        .category = "LINEAR";
        .compuInternalToPhys = CompuInternalToPhys {
            CompuScale {
                .compuRationalCoeffs = CompuRationalCoeffs {
                    .compuNumerator = [-40.0, 1.0];
                    .compuDenominator = [1.0];
                };
            };
        };
    }

    CompuMethod CM_GearPosition {
        .category = "TEXTTABLE";
        .compuInternalToPhys = CompuInternalToPhys {
            CompuScale { .lowerLimit = 0; .upperLimit = 0;
                .compuConst = CompuConst { .vt = "Park"; }; }
            CompuScale { .lowerLimit = 1; .upperLimit = 1;
                .compuConst = CompuConst { .vt = "Reverse"; }; }
            CompuScale { .lowerLimit = 2; .upperLimit = 2;
                .compuConst = CompuConst { .vt = "Neutral"; }; }
            CompuScale { .lowerLimit = 3; .upperLimit = 3;
                .compuConst = CompuConst { .vt = "Drive"; }; }
        };
    }
}

ARPackage ApplicationDataTypes {
    ApplicationPrimitiveDataType VehicleSpeed {
        .category = "VALUE";
        .swDataDefProps = SwDataDefProps {
            SwDataDefPropsConditional {
                .compuMethodRef = /CompuMethods/CM_VehicleSpeed;
            };
        };
    }

    ApplicationPrimitiveDataType EngineTemp {
        .category = "VALUE";
        .swDataDefProps = SwDataDefProps {
            SwDataDefPropsConditional {
                .compuMethodRef = /CompuMethods/CM_EngineTemp;
            };
        };
    }

    ApplicationPrimitiveDataType GearPosition {
        .category = "VALUE";
        .swDataDefProps = SwDataDefProps {
            SwDataDefPropsConditional {
                .compuMethodRef = /CompuMethods/CM_GearPosition;
            };
        };
    }

    ApplicationRecordDataType VehicleData {
        .category = "STRUCTURE";
        ApplicationRecordElement speed {
            .typeRef = /ApplicationDataTypes/VehicleSpeed;
        }
        ApplicationRecordElement engineTemp {
            .typeRef = /ApplicationDataTypes/EngineTemp;
        }
        ApplicationRecordElement gear {
            .typeRef = /ApplicationDataTypes/GearPosition;
        }
    }
}

ARPackage ImplementationDataTypes {
    ImplementationDataType VehicleSpeed_Impl {
        .category = "VALUE";
        .swDataDefProps = SwDataDefProps {
            SwDataDefPropsConditional {
                .baseTypeRef = /PlatformTypes/uint16;
            };
        };
    }

    ImplementationDataType EngineTemp_Impl {
        .category = "VALUE";
        .swDataDefProps = SwDataDefProps {
            SwDataDefPropsConditional {
                .baseTypeRef = /PlatformTypes/uint8;
            };
        };
    }

    ImplementationDataType GearPosition_Impl {
        .category = "VALUE";
        .swDataDefProps = SwDataDefProps {
            SwDataDefPropsConditional {
                .baseTypeRef = /PlatformTypes/uint8;
            };
        };
    }

    ImplementationDataType VehicleData_Impl {
        .category = "STRUCTURE";
        ImplementationDataTypeElement speed {
            .swDataDefProps = SwDataDefProps {
                SwDataDefPropsConditional {
                    .implementationDataTypeRef = /ImplementationDataTypes/VehicleSpeed_Impl;
                };
            };
        }
        ImplementationDataTypeElement engineTemp {
            .swDataDefProps = SwDataDefProps {
                SwDataDefPropsConditional {
                    .implementationDataTypeRef = /ImplementationDataTypes/EngineTemp_Impl;
                };
            };
        }
        ImplementationDataTypeElement gear {
            .swDataDefProps = SwDataDefProps {
                SwDataDefPropsConditional {
                    .implementationDataTypeRef = /ImplementationDataTypes/GearPosition_Impl;
                };
            };
        }
    }
}

ARPackage DataTypeMappingSets {
    DataTypeMappingSet DtMapping {
        DataTypeMap {
            .applicationDataType = /ApplicationDataTypes/VehicleSpeed;
            .implementationDataType = /ImplementationDataTypes/VehicleSpeed_Impl;
        }
        DataTypeMap {
            .applicationDataType = /ApplicationDataTypes/EngineTemp;
            .implementationDataType = /ImplementationDataTypes/EngineTemp_Impl;
        }
        DataTypeMap {
            .applicationDataType = /ApplicationDataTypes/GearPosition;
            .implementationDataType = /ImplementationDataTypes/GearPosition_Impl;
        }
    }
}
```

The dissolved Rupa model is readable and inspectable. Every AUTOSAR artifact is
present -- ApplicationPrimitiveDataTypes, ImplementationDataTypes, CompuMethods,
DataTypeMappingSet -- all generated from the 15 lines of unified input.

### Step 5: Build and Dissolve

```sh
# Compile the unified model
rupa build vehicle-types.rupa vehicle-model.rupa -o vehicle-unified.rupac

# Dissolve to concrete AUTOSAR domain -- compiler applies transforms
rupa build --domain autosar-2411 \
    dissolve.rupa \
    vehicle-unified.rupac \
    -o vehicle-autosar.rupac

# Inspect the dissolved model
rupa inspect vehicle-autosar.rupac

# Export to ARXML
rupa emit --format arxml vehicle-autosar.rupac -o vehicle.arxml
```

---

## Key Features Demonstrated

| Feature | Where it appears |
|---------|-----------------|
| **Domain derivation** | `domain autosar-2411-unified = autosar-2411;` -- copy full AUTOSAR type system, extend with simplified base types |
| **M2 base types with roles** | `LinearQuantity` carries `.factor` and `.offset` as roles -- conversion parameters are structural, not annotations |
| **M1 scaling templates** | `let speed_scaling = LinearQuantity { .factor = 0.01; ... };` -- reusable value templates |
| **`from` derivation** | `VehicleSpeed VehicleSpeed from speed_scaling {}` -- copy scaling parameters into instances |
| **Write-mode transforms** | `dissolve_linear` creates CompuMethod + ADT + IDT in one function, placing each in the correct ARPackage |
| **One-to-many dissolution** | Each unified type produces three AUTOSAR artifacts (ADT + IDT + CompuMethod) plus a DataTypeMap entry |
| **Multi-phase transforms** | Phase 1 creates structure; Phase 2 wires cross-references (`CompuMethodRef`, `baseTypeRef`, DataTypeMaps) |
| **`::targets` lookup** | Phase 2 finds objects created from each source to wire references |
| **Convention-based inference** | Implementation base type (uint8/uint16/uint32) inferred from scaling factor and range |
| **Subtype dispatch** | `dissolve_linear`, `dissolve_enum`, `dissolve_composite` -- overloaded by source type |

---

## Comparison

| Aspect | Manual AUTOSAR (ARXML) | Unified Type System (Rupa) |
|--------|----------------------|---------------------------|
| **Lines per type** | ~40 lines across 4 ARPackages | ~4 lines (type def + scaling template) |
| **Artifacts to coordinate** | 4 per primitive (ADT + IDT + CompuMethod + DataTypeMap) | 1 type declaration, 1 scaling template |
| **Adding a new type** | Edit 4 locations, maintain cross-references by path | Add type definition + scaling template, dissolution handles the rest |
| **Changing a conversion factor** | Find CompuMethod, update coefficients, verify consistency | Change `.factor` on the scaling template |
| **Type safety** | XML validation catches schema violations, not semantic errors | Compiler type-checks dissolution transforms against both domains |
| **Readability** | Verbose XML with deeply nested elements | Concise Rupa with clear intent |
| **Platform variants** | Duplicate all IDTs and mappings per ECU | Derive a new domain, override scaling templates |
| **Consistency** | Manual maintenance of ADT-IDT-CompuMethod consistency | Structural consistency guaranteed by dissolution transforms |

The fundamental difference: the unified type system eliminates the conceptual
overhead of AUTOSAR's three-artifact split. Engineers think in physical types
with conversion parameters. The tooling generates the AUTOSAR artifacts.
