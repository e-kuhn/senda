# FIR Clean-Room Redesign

**Date**: 2026-03-04
**Status**: Approved
**Approach**: Clean-room rewrite (no backward compatibility constraints — internal prototype)
**Priority**: Sema lowering first, cross-FIR merging second

## Overview

Rewrite the FIR (Full Intermediate Representation) from scratch to be bullet-proof, stable, and extensible. The new FIR supports the full Rupa compilation pipeline: types, instances, constants, functions, validation rules, transformations, export tables, cross-FIR references, and N-way sequential merging.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| RTTI style | LLVM-style (`isa`/`cast`/`dyn_cast`) | Type-safe, no vtable overhead, standard for compiler IRs |
| Arena layout | Separate arenas per section | Independent serialization, prevents ID collisions |
| Handle types | Typed handles via `KORE_DEFINE_HANDLE` | Compile-time safety — can't mix TypeHandle with NodeHandle |
| Foreign refs | Top bit = foreign (same as today) | Simple, 2^31 local handles per section is sufficient |
| Expression scope | Full hierarchy (~35 semantic kinds) | Avoids rework when adding rules/transforms |
| Non-polymorphic storage | Direct `vector<T>` (no arena, no pointers) | Cache-friendly for uniform-size types (FirType, FirRole, FirProp) |
| Export/merge | Data structures designed now, implementation deferred | Avoids format version bump later |
| Identity model | No identity field on FirNode — identity derived from `is_identity` roles | General (compound identities), not AUTOSAR-specific |
| Value storage | ValueStore with typed ValueHandle (kind in top 4 bits) | Enables dedup of common values (0, 1, true, false) |
| Containment discriminator | 1 bit stolen from RoleHandle in FirProp | Roles will never exceed 2^31; gives full 32-bit NodeHandle/ValueHandle |

## Section 1: Foundations

### Typed Handles

```cpp
#include <kore/macros.hpp>
KORE_DEFINE_HANDLE(Type, 32);    // TypeHandle — indexes TypeTable
KORE_DEFINE_HANDLE(Role, 32);    // RoleHandle — indexes TypeTable roles
KORE_DEFINE_HANDLE(Node, 32);    // NodeHandle — indexes ModelGraph objects
KORE_DEFINE_HANDLE(Value, 32);   // ValueHandle — kind-tagged, indexes ValueStore
KORE_DEFINE_HANDLE(Expr, 32);    // ExprHandle — indexes ExpressionStore
KORE_DEFINE_HANDLE(Symbol, 32);  // SymbolHandle — indexes SymbolTable
```

Cross-section references are strongly typed: a FirNode references a `TypeHandle` for its type, a FirSymbol references an `ExprHandle` for its body.

Foreign references: top bit set = foreign. Lower 31 bits index the section's `foreign_refs_` table. Each `ForeignRef = (ModuleId, uint32_t local_id)`.

### LLVM-Style RTTI

```cpp
namespace fir::rtti {
    template <typename T, typename Base>
    bool isa(const Base* b) { return b && T::classof(b); }

    template <typename T, typename Base>
    T* cast(Base* b) { assert(isa<T>(b)); return static_cast<T*>(b); }

    template <typename T, typename Base>
    const T* dyn_cast(const Base* b) {
        return isa<T>(b) ? static_cast<const T*>(b) : nullptr;
    }
}
```

Each hierarchy has a `Kind` enum on the base class. Each subtype has `static bool classof(const Base*)`. Range-based classof allows many semantic kinds to share one structural subtype.

### Fir Container (top-level composition)

```cpp
struct Fir {
    kore::LiteralStore<64>  strings;        // shared across all sections

    TypeTable               types;          // M2: types + roles
    ModelGraph              model;          // M1: objects, properties, values
    ExpressionStore         expressions;    // compiled expression trees
    SymbolTable             symbols;        // name → definition mapping

    // Designed now, implemented later:
    ExportTable             exports;        // symbols this module exposes
    ExternalRefTable        external_refs;  // unresolved cross-module paths

    DomainMetadata          metadata;       // domain name, deps, content hash
    SourceMap               source_map;     // source spans (optional, fat IR only)
};
```

## Section 2: TypeTable — M2 Type Definitions

### M3Kind

```cpp
enum class M3Kind : uint8_t {
    Composite = 0,  // identity semantics, roles
    Primitive = 1,  // value semantics (string, integer, float, boolean)
    List      = 2,  // heterogeneous ordered collection
    Map       = 3,  // heterogeneous key-value collection
    Union     = 4,  // closed alternation of types
    Enum      = 5,  // named value set
    // 6..15 reserved for future kinds
};
```

List and Map are first-class M3Kinds. Containers are heterogeneous — no type parameters. Each contained element carries its own type.

### FirType (flat struct, 32 bytes)

```cpp
struct FirType {
    // Packed flags (32 bits):
    //   m3_kind:          4 bits  [0:3]
    //   is_abstract:      1 bit   [4]
    //   constraint_kind:  2 bits  [5:6]   none/int/float/string
    //   reserved:        25 bits  [7:31]
    uint32_t   flags;
    StringId   name;           // 8 bytes
    TypeHandle supertype;      // 4 bytes (kInvalidHandle = none)
    uint32_t   role_start;     // 4 bytes — offset into TypeTable::role_ids_
    uint16_t   role_count;     // 2 bytes
    uint16_t   aux_count;      // 2 bytes (enum_count / variant_count)
    uint32_t   aux_start;      // 4 bytes (enum_start / variant_start / constraint_id)
    DomainId   domain;         // 2 bytes
    uint16_t   reserved_;      // 2 bytes
    // Total: 32 bytes
};
```

The `aux_start`/`aux_count` fields are reinterpreted by m3_kind:
- **Enum**: `aux_start` = enum_start, `aux_count` = enum_count (offsets into `enum_values_`)
- **Union**: `aux_start` = variant_start, `aux_count` = variant_count (offsets into `variant_ids_`)
- **Primitive**: `aux_start` = constraint_id (index into constraint tables)
- **Composite/List/Map**: unused (0)

### FirRole (16 bytes, direct storage)

```cpp
struct FirRole {
    // Packed flags (32 bits):
    //   multiplicity:    2 bits  [0:1]   One/Optional/Many/OneOrMore
    //   is_containment:  1 bit   [2]
    //   is_identity:     1 bit   [3]
    //   reserved:       28 bits  [4:31]
    uint32_t   flags;
    StringId   name;           // 8 bytes
    TypeHandle target;         // 4 bytes
    // Total: 16 bytes
};
```

Non-polymorphic. Stored directly in `vector<FirRole>` — no arena, no pointers.

### M3 Builtins

Pre-registered as well-known TypeHandle constants:

```cpp
namespace fir::builtin {
    inline constexpr TypeHandle kInteger;   // ::integer
    inline constexpr TypeHandle kFloat;     // ::float
    inline constexpr TypeHandle kString;    // ::string
    inline constexpr TypeHandle kBoolean;   // ::boolean
    inline constexpr TypeHandle kList;      // ::list
    inline constexpr TypeHandle kMap;       // ::map
}
```

Seeded into the TypeTable at construction time with fixed handles. Available to both model layer and expression layer.

### TypeTable structure

```cpp
struct TypeTable {
    vector<FirType>    types;                // indexed by TypeHandle (direct storage)
    vector<FirRole>    roles;                // indexed by RoleHandle (direct storage)

    // Secondary tables:
    vector<RoleHandle> role_ids;             // contiguous role lists per type
    vector<StringId>   enum_values;          // contiguous enum member lists
    vector<TypeHandle> variant_ids;          // contiguous union variant lists

    // Constraints:
    vector<IntegerConstraint>  int_constraints;
    vector<FloatConstraint>    float_constraints;
    vector<StringConstraint>   string_constraints;

    // Domain/module:
    vector<DomainEntry>   domains;
    vector<ModuleEntry>   modules;
    vector<ForeignRef>    foreign_type_refs;  // for foreign TypeHandles
    vector<ForeignRef>    foreign_role_refs;  // for foreign RoleHandles

    vector<TypeHandle>    root_types;
};
```

## Section 3: ModelGraph — M1 Instances

### FirNode (model object, 24 bytes in vector)

```cpp
struct FirNode {
    // Packed flags (32 bits):
    //   provenance:  2 bits  [0:1]   Local/Imported/Materialized
    //   reserved:   30 bits  [2:31]
    uint32_t   flags;
    TypeHandle type;           // 4 bytes — M2 type this instantiates
    uint32_t   prop_start;     // 4 bytes — offset into ModelGraph::props_
    uint16_t   prop_count;     // 2 bytes
    uint16_t   reserved_;      // 2 bytes
    NodeHandle parent;         // 4 bytes — containment parent
    NodeHandle derived_from;   // 4 bytes — derivation source (from /Base)
    // Total: 24 bytes
};
```

**No identity field.** Identity is derived from the node's properties whose roles have `is_identity = true`. Identity comparison for merging walks these roles and compares their values (like OML's `SemaIdentityComparer`).

### FirProp (property assignment, 12 bytes)

```cpp
struct FirProp {
    // role_flags (32 bits):
    //   is_node: 1 bit  [31]     0 = value property, 1 = containment (child object)
    //   role:   31 bits [0:30]   role index (2B max — AUTOSAR has ~30K)
    uint32_t   role_flags;
    TypeHandle value_type;     // 4 bytes — M2 type of value (or M3 builtin)
    uint32_t   ref;            // 4 bytes — ValueHandle (if is_node=0) or NodeHandle (if is_node=1)
    // Total: 12 bytes
};
```

The `value_type` field carries the M2 type of the assigned value. This is essential for:
- Union-typed roles where the actual type varies per instance
- Primitive values where multiple M2 types map to the same M3 builtin (e.g., SpeedKph vs TemperatureC both wrapping `::integer`)
- Expression layer needing to reference M3 builtins directly

### ValueStore

Values are typeless in the store — the M2 type context lives on FirProp, not the value. This preserves value dedup: a `42` is a `42` regardless of its M2 type.

```
ValueHandle (32 bits):
  [31:28] kind   (4 bits — up to 16 ValueKinds)
  [27:0]  index  (28 bits — up to 268M values per kind)
```

```cpp
enum class ValueKind : uint8_t {
    Integer   = 0,
    Float     = 1,
    String    = 2,
    Boolean   = 3,  // index: 0=false, 1=true (no storage needed)
    Null      = 4,  // index: always 0 (no storage needed)
    Reference = 5,
    EnumValue = 6,
    // 7..15 reserved
};

struct RefValue {
    uint32_t   segment_start;  // offset into ValueStore::path_segments_
    uint16_t   segment_count;
    uint16_t   reserved_;
    NodeHandle target;         // resolved target (kInvalidHandle = unresolved)
    // 12 bytes
};

struct EnumEntry {
    TypeHandle enum_type;      // which enum type
    StringId   member_name;    // which member
    // 12 bytes
};

struct ValueStore {
    // Per-kind storage:
    vector<int64_t>     integers;
    vector<double>      floats;
    vector<StringId>    strings;
    vector<RefValue>    references;
    vector<EnumEntry>   enum_values;
    vector<PathSegment> path_segments;

    // Well-known constants (no storage lookup needed):
    static constexpr ValueHandle kNull  = /* kind=Null,    index=0 */;
    static constexpr ValueHandle kTrue  = /* kind=Boolean, index=1 */;
    static constexpr ValueHandle kFalse = /* kind=Boolean, index=0 */;

    // API:
    ValueHandle add_integer(int64_t v);
    ValueHandle add_float(double v);
    ValueHandle add_string(StringId s);
    ValueHandle add_boolean(bool v);
    ValueHandle add_null();
    ValueHandle add_reference(std::span<PathSegment> segments);
    ValueHandle add_enum(TypeHandle type, StringId member);

    ValueKind   kind(ValueHandle h) const;
    int64_t     get_integer(ValueHandle h) const;
    double      get_float(ValueHandle h) const;
    StringId    get_string(ValueHandle h) const;
    bool        get_boolean(ValueHandle h) const;
    const RefValue& get_reference(ValueHandle h) const;
    const EnumEntry& get_enum(ValueHandle h) const;
};
```

### ModelGraph structure

```cpp
struct ModelGraph {
    vector<FirNode>    nodes;       // indexed by NodeHandle (direct storage)
    vector<FirProp>    props;       // secondary table (indexed by prop_start/prop_count)
    ValueStore         values;

    NodeHandle         root_object; // kInvalidHandle = none
};
```

## Section 4: ExpressionStore — Full Expression Hierarchy

### Kind Enum (35+ semantic kinds)

```cpp
struct FirExpr {
    enum class Kind : uint8_t {
        // Leaf (no operands)
        SelfRef = 0, RootPath,

        // Value leaf
        Literal, ResolvedValue,

        // Symbol reference
        VarRef,

        // Unary (1 ExprHandle operand)
        Negate, Not, Flatten, Count, Collect,

        // Binary (2 ExprHandle operands)
        Add, Sub, Mul, Div, Mod,
        Equal, NotEqual, LessThan, LessEqual, GreaterThan, GreaterEqual,
        And, Or, Implication,
        Concat,
        Map, Filter, Select, Exists, ForAll,

        // Ternary (3 ExprHandle operands)
        IfThenElse, Fold,

        // Path navigation
        RoleAccess, IdentityNav,

        // Type operations
        TypeCheck, TypeCast,

        // Variable-arity
        FnCall, FfiCall, PipeChain, Match,

        // Sentinel
        Unresolved,
    };

    Kind       kind;
    uint8_t    reserved_[3];
    TypeHandle result_type;     // what type this evaluates to
    // Total base: 8 bytes

    static bool classof(const FirExpr*) { return true; }
};
```

### Structural Subtypes (10 structs)

| Struct | Size | Kinds |
|--------|------|-------|
| `FirLeafExpr` | 8 | SelfRef, RootPath, Unresolved |
| `FirValueExpr` | 12 | Literal, ResolvedValue |
| `FirSymRefExpr` | 12 | VarRef |
| `FirUnaryExpr` | 12 | Negate, Not, Flatten, Count, Collect |
| `FirBinaryExpr` | 16 | Add, Sub, Mul, Div, Mod, Equal, NotEqual, LessThan, LessEqual, GreaterThan, GreaterEqual, And, Or, Implication, Concat, Map, Filter, Select, Exists, ForAll |
| `FirTernaryExpr` | 20 | IfThenElse, Fold |
| `FirRoleAccessExpr` | 16 | RoleAccess |
| `FirIdentityNavExpr` | 20 | IdentityNav |
| `FirTypeOpExpr` | 16 | TypeCheck, TypeCast |
| `FirCallExpr` | 20 | FnCall, FfiCall |
| `FirPipeExpr` | 20 | PipeChain |
| `FirMatchExpr` | 20 | Match |

```cpp
// --- Leaf (0 operands) ---
struct FirLeafExpr : FirExpr {
    static bool classof(const FirExpr* e) {
        return e->kind == Kind::SelfRef || e->kind == Kind::RootPath
            || e->kind == Kind::Unresolved;
    }
};

// --- Value leaf ---
struct FirValueExpr : FirExpr {
    ValueHandle value;
    static bool classof(const FirExpr* e) {
        return e->kind == Kind::Literal || e->kind == Kind::ResolvedValue;
    }
};

// --- Symbol reference ---
struct FirSymRefExpr : FirExpr {
    SymbolHandle symbol;
    static bool classof(const FirExpr* e) { return e->kind == Kind::VarRef; }
};

// --- Unary ---
struct FirUnaryExpr : FirExpr {
    ExprHandle operand;
    static bool classof(const FirExpr* e) {
        return e->kind >= Kind::Negate && e->kind <= Kind::Collect;
    }
};

// --- Binary ---
struct FirBinaryExpr : FirExpr {
    ExprHandle lhs;
    ExprHandle rhs;
    static bool classof(const FirExpr* e) {
        return e->kind >= Kind::Add && e->kind <= Kind::ForAll;
    }
};

// --- Ternary ---
struct FirTernaryExpr : FirExpr {
    ExprHandle first;   // condition (IfThenElse) / collection (Fold)
    ExprHandle second;  // then_expr / initial_value
    ExprHandle third;   // else_expr / lambda
    static bool classof(const FirExpr* e) {
        return e->kind == Kind::IfThenElse || e->kind == Kind::Fold;
    }
};

// --- Path: RoleAccess ---
struct FirRoleAccessExpr : FirExpr {
    ExprHandle base;
    RoleHandle role;
    static bool classof(const FirExpr* e) { return e->kind == Kind::RoleAccess; }
};

// --- Path: IdentityNav ---
struct FirIdentityNavExpr : FirExpr {
    ExprHandle base;
    StringId   identity;     // 8 bytes
    static bool classof(const FirExpr* e) { return e->kind == Kind::IdentityNav; }
};

// --- Type operations ---
struct FirTypeOpExpr : FirExpr {
    ExprHandle operand;
    TypeHandle target_type;
    static bool classof(const FirExpr* e) {
        return e->kind == Kind::TypeCheck || e->kind == Kind::TypeCast;
    }
};

// --- Function/FFI calls ---
struct FirCallExpr : FirExpr {
    SymbolHandle function;
    uint32_t     arg_start;
    uint16_t     arg_count;
    uint16_t     reserved_;
    static bool classof(const FirExpr* e) {
        return e->kind == Kind::FnCall || e->kind == Kind::FfiCall;
    }
};

// --- Pipe chain ---
struct FirPipeExpr : FirExpr {
    ExprHandle input;
    uint32_t   step_start;
    uint16_t   step_count;
    uint16_t   reserved_;
    static bool classof(const FirExpr* e) { return e->kind == Kind::PipeChain; }
};

// --- Match ---
struct FirMatchExpr : FirExpr {
    ExprHandle scrutinee;
    uint32_t   arm_start;
    uint16_t   arm_count;
    uint16_t   reserved_;
    static bool classof(const FirExpr* e) { return e->kind == Kind::Match; }
};

// --- Match arm (secondary table, not a FirExpr) ---
struct MatchArm {
    ExprHandle pattern;
    ExprHandle body;
};
```

### ExpressionStore structure

```cpp
struct ExpressionStore {
    VecArena          arena;          // allocation for heterogeneous FirExpr nodes
    vector<FirExpr*>  exprs;          // indexed by ExprHandle (pointer table)

    // Secondary tables:
    vector<ExprHandle> call_args;     // contiguous arg lists for FnCall/FfiCall
    vector<ExprHandle> pipe_steps;    // contiguous step lists for PipeChain
    vector<MatchArm>   match_arms;    // contiguous arm lists for Match
};
```

## Section 5: SymbolTable

### Symbol hierarchy

```cpp
struct FirSymbol {
    enum class Kind : uint8_t {
        Type, Value, Function, Rule, Transform, Imported,
    };

    Kind     kind;
    uint8_t  reserved_[3];
    StringId name;             // 8 bytes
    // Total base: 12 bytes

    static bool classof(const FirSymbol*) { return true; }
};

struct FirTypeSym : FirSymbol {
    TypeHandle type;
    static bool classof(const FirSymbol* s) { return s->kind == Kind::Type; }
    // Total: 16 bytes
};

struct FirValueSym : FirSymbol {
    ValueHandle value;
    TypeHandle  value_type;
    static bool classof(const FirSymbol* s) { return s->kind == Kind::Value; }
    // Total: 20 bytes
};

struct FirFnSym : FirSymbol {
    ExprHandle body;
    TypeHandle return_type;
    uint32_t   param_start;
    uint16_t   param_count;
    uint16_t   reserved_;
    static bool classof(const FirSymbol* s) { return s->kind == Kind::Function; }
    // Total: 24 bytes
};

struct FirRuleSym : FirSymbol {
    ExprHandle predicate;
    TypeHandle target_type;
    uint8_t    severity;       // error / warning / info
    uint8_t    reserved_[3];
    static bool classof(const FirSymbol* s) { return s->kind == Kind::Rule; }
    // Total: 24 bytes
};

struct FirTransformSym : FirSymbol {
    ExprHandle body;
    TypeHandle source_type;
    TypeHandle target_type;
    static bool classof(const FirSymbol* s) { return s->kind == Kind::Transform; }
    // Total: 24 bytes
};

struct FirImportedSym : FirSymbol {
    ModuleId     source_module;
    SymbolHandle original;
    static bool classof(const FirSymbol* s) { return s->kind == Kind::Imported; }
    // Total: 18 bytes
};

struct ParamDef {
    StringId   name;           // 8 bytes
    TypeHandle type;           // 4 bytes
    // Total: 12 bytes
};
```

### SymbolTable structure

```cpp
struct SymbolTable {
    VecArena           arena;
    vector<FirSymbol*> symbols;          // indexed by SymbolHandle

    vector<ParamDef>   params;           // contiguous param lists for functions

    // Lookup (built after lowering):
    flat_hash_map<StringId, SymbolHandle> name_index;
};
```

## Section 6: ExportTable + ExternalRefTable (designed, deferred)

### ExportTable

```cpp
struct ExportEntry {
    StringId     name;         // exported name (may differ via `as`)
    SymbolHandle symbol;       // the symbol being exported
    // 12 bytes
};

struct ExportTable {
    vector<ExportEntry> entries;
    // Model root is always implicitly exported.
};
```

### ExternalRefTable

Cross-module references unresolved at compile time. Resolved by linker.

```cpp
struct ExternalRef {
    uint32_t   segment_start;  // path expression segments
    uint16_t   segment_count;
    uint16_t   reserved_;
    NodeHandle source_node;    // FirNode containing the unresolved ref
    RoleHandle source_role;    // which role
    NodeHandle target;         // filled by linker (kInvalidHandle until then)
    // 20 bytes
};

struct ExternalRefTable {
    vector<ExternalRef> refs;
    vector<PathSegment> path_segments;
};
```

### DomainMetadata

```cpp
struct DomainMetadata {
    StringId            domain_name;
    vector<StringId>    dependencies;
    uint64_t            content_hash;
};
```

## Section 7: Binary Format v6

### Header (220 bytes)

```
Offset  Size  Field
──────  ────  ─────
0       4     Magic: "FIR\0"
4       2     Format version (6)
6       2     Section mask (which sections are present)
8       8     Content hash

Section directory (offset + size/count per section):
16      8     String table
24      8     Type table
32      8     Role table
40      8     Model graph (nodes)
48      8     Value store
56      8     Expression store
64      8     Symbol table
72      8     Export table
80      8     External ref table

Secondary table directory:
88      8     Role IDs
96      8     Enum values
104     8     Variant IDs
112     8     Properties
120     8     Path segments (values)
128     8     Call args
136     8     Match arms
144     8     Pipe steps
152     8     Params
160     8     Constraints

Module/domain/foreign tables:
168     8     Domain table
176     8     Module table
184     8     Foreign type refs
192     8     Foreign role refs

Root markers:
200     4     Root object (NodeHandle)
204     4     Root type count
208     4     Root types offset

Metadata:
212     8     Domain metadata
// Total: 220 bytes
```

### Section mask bits

```
Bit 0:  String table (always present)
Bit 1:  Type table
Bit 2:  Model graph
Bit 3:  Expression store
Bit 4:  Symbol table
Bit 5:  Export table
Bit 6:  External ref table
Bit 7:  Source map (optional, fat IR only)
Bits 8-15: reserved
```

Enables RUPA-TLG-020: model-only, rule-only, and transform-only artifacts built separately.

### Serialization approach

Same proven approach as v5:
- Compact sequential index remapping (sparse → dense)
- String dedup via `flat_hash_map<uint64_t, uint32_t>`
- Node type determined by first byte (Kind)
- Little-endian throughout

## Section 8: Builder API

```cpp
class FirBuilder {
    Fir& fir_;

public:
    explicit FirBuilder(Fir& fir);

    // ── Type construction ──
    TypeHandle add_type(std::string_view name, M3Kind kind);
    void set_abstract(TypeHandle t, bool abstract);
    void set_supertype(TypeHandle derived, TypeHandle base);
    void set_domain(TypeHandle t, std::string_view domain);
    RoleHandle add_role(TypeHandle t, std::string_view name, TypeHandle target,
                        Multiplicity mult, bool containment);
    void set_identity(RoleHandle r, bool is_identity);
    void add_enum_value(TypeHandle t, std::string_view value);
    void add_union_variant(TypeHandle t, TypeHandle variant);
    void add_root_type(TypeHandle t);

    // ── Values ──
    ValueHandle add_integer(int64_t v);
    ValueHandle add_float(double v);
    ValueHandle add_string(std::string_view s);
    ValueHandle add_boolean(bool v);
    ValueHandle add_null();
    ValueHandle add_reference(std::span<std::string_view> segments);
    ValueHandle add_enum(TypeHandle type, std::string_view member);

    // ── Model construction ──
    NodeHandle begin_object(TypeHandle type);
    void set_parent(NodeHandle child, NodeHandle parent);
    void add_property(NodeHandle obj, RoleHandle role, TypeHandle type, ValueHandle value);
    void add_containment(NodeHandle parent, RoleHandle role, TypeHandle type, NodeHandle child);
    void flush_properties(NodeHandle obj, std::span<FirProp> props);
    void set_root_object(NodeHandle obj);

    // ── Expression construction ──
    ExprHandle add_literal(ValueHandle value, TypeHandle result_type);
    ExprHandle add_var_ref(SymbolHandle sym, TypeHandle result_type);
    ExprHandle add_self_ref(TypeHandle result_type);
    ExprHandle add_root_path(TypeHandle result_type);
    ExprHandle add_unary(FirExpr::Kind kind, ExprHandle operand, TypeHandle result_type);
    ExprHandle add_binary(FirExpr::Kind kind, ExprHandle lhs, ExprHandle rhs,
                          TypeHandle result_type);
    ExprHandle add_ternary(FirExpr::Kind kind, ExprHandle a, ExprHandle b, ExprHandle c,
                           TypeHandle result_type);
    ExprHandle add_role_access(ExprHandle base, RoleHandle role, TypeHandle result_type);
    ExprHandle add_identity_nav(ExprHandle base, std::string_view identity,
                                TypeHandle result_type);
    ExprHandle add_type_op(FirExpr::Kind kind, ExprHandle operand, TypeHandle target,
                           TypeHandle result_type);
    ExprHandle add_fn_call(SymbolHandle fn, std::span<ExprHandle> args,
                           TypeHandle result_type);
    ExprHandle add_pipe(ExprHandle input, std::span<ExprHandle> steps,
                        TypeHandle result_type);
    ExprHandle add_match(ExprHandle scrutinee, std::span<MatchArm> arms,
                         TypeHandle result_type);

    // ── Symbol construction ──
    SymbolHandle add_type_symbol(std::string_view name, TypeHandle type);
    SymbolHandle add_value_symbol(std::string_view name, ValueHandle value, TypeHandle type);
    SymbolHandle add_function(std::string_view name, ExprHandle body, TypeHandle return_type,
                              std::span<ParamDef> params);
    SymbolHandle add_rule(std::string_view name, ExprHandle predicate, TypeHandle target,
                          uint8_t severity);
    SymbolHandle add_transform(std::string_view name, ExprHandle body,
                               TypeHandle source, TypeHandle target);
    SymbolHandle add_imported(std::string_view name, ModuleId module, SymbolHandle original);

    // ── Module/foreign refs ──
    ModuleId add_module(std::string_view name);
    TypeHandle add_foreign_type(ModuleId module, uint32_t local_id);
    RoleHandle add_foreign_role(ModuleId module, uint32_t local_id);
};
```

## Impact on Existing Code

Everything breaks and gets rewritten:

| Component | Changes |
|-----------|---------|
| `rupa.fir-node.cppm` | Replace `Id`/`Node`/`NodeKind` with typed handles + RTTI |
| `rupa.fir-types.cppm` | Replace `TypeDef`/`RoleDef` with `FirType`/`FirRole` (flat, bitfield-packed) |
| `rupa.fir-instances.cppm` | Replace `ObjectDef`/`PropertyVal`/`ValueDef` with `FirNode`/`FirProp`/`ValueStore` |
| `rupa.fir.cppm` | Replace monolithic `Fir` with section-composed `Fir` |
| `rupa.fir-serial.cppm` | Complete rewrite for format v6 |
| `rupa.fir-builder.cppm` | New API surface with typed handles |
| `rupa.emitter.cppm` | Adapt to new handle types and ValueStore |
| `senda.compiler-arxml.cppm` | Adapt to new FirBuilder API |
| `rupa.sema-*.cppm` | Adapt to new handle types |
| `rupa.cli-emit.cppm` | Minimal — handle type changes |

New files:
- `rupa.fir-expr.cppm` — ExpressionStore + FirExpr hierarchy
- `rupa.fir-symbol.cppm` — SymbolTable + FirSymbol hierarchy
- `rupa.fir-value.cppm` — ValueStore
- `rupa.fir-rtti.cppm` — isa/cast/dyn_cast utilities

## Memory Budget (4GB ARXML stress test)

Extrapolating from R20-11 (49MB → 176K objects, ~700K props):

| Component | Per-item | 4GB estimate | Total |
|-----------|----------|-------------|-------|
| FirNode | 24 bytes | ~14M objects | 336 MB |
| FirProp | 12 bytes | ~56M props | 672 MB |
| Values (int/float/string) | 8 bytes avg | ~56M values | 448 MB |
| Strings (interned) | variable | ~2M unique | ~200 MB |
| **Total** | | | **~1.6 GB** |

Comfortable for a 4GB input on modern hardware.
