# Multi-Compiler Architecture Design

**Date**: 2026-02-26
**Status**: Draft

---

## Overview

This design introduces a multi-compiler architecture where FIR is the universal compilation target. The current Rupa lexer/parser/sema pipeline becomes one compiler among many. Domain-specific compilers (e.g., ARXML for AUTOSAR) produce FIR directly, and a compilation driver orchestrates them based on file extension. Import statements in Rupa can trigger any registered compiler, enabling seamless cross-format imports.

The architecture is library-first: each layer is an independent library that can be used standalone, embedded in tools, or composed into a CLI.

---

## Architecture

### Layered Library Stack

```
Library              │ Depends on        │ Contains
─────────────────────┼───────────────────┼──────────────────────────────
fir                  │ kore              │ Fir, node types, serialization
                     │                   │
domain               │ fir               │ Domain, DomainView,
                     │                   │ DomainTransaction,
                     │                   │ DomainExtension
                     │                   │
compiler-api         │ fir, domain       │ Compiler (interface),
                     │                   │ CompileContext (interface),
                     │                   │ CompileResult, CompilerRegistry,
                     │                   │ Diagnostics
                     │                   │
fir-builder          │ fir               │ FirBuilder (construction API)
                     │                   │
compiler-rupa        │ compiler-api,     │ RupaCompiler
                     │ fir-builder,      │ (lexer + parser + sema)
                     │ domain            │
                     │                   │
driver               │ compiler-api,     │ CompilationDriver,
                     │ domain            │ DriverCompileContext,
                     │                   │ disk cache management
```

### Rupa / Senda Boundary

Rupa is domain-agnostic. It provides the infrastructure — FIR, Domain, Compiler interface, FirBuilder, Driver, and the Rupa compiler. It has no knowledge of AUTOSAR or any other specific domain.

Senda (and other domain-specific repos like Vena/medical, Brisa/aviation) add domain-specific compilers, pre-built domain FIRs, and a CLI that registers everything.

```
RUPA (domain-agnostic)          │  SENDA (AUTOSAR-specific)
────────────────────────────────┼─────────────────────────────
fir                             │
domain                          │
compiler-api                    │
fir-builder                     │
compiler-rupa                   │
driver                          │
                                │  compiler-arxml
                                │  autosar-domains (pre-built FIRs)
                                │  cli (registers rupa + arxml compilers)
```

The `Compiler` interface, `CompileContext`, and `CompilerRegistry` are designed for external implementation — they are the extension points that domain repos use to plug in.

---

## Core Types

### FIR as a Value Type

FIR is the universal compilation target. Every compiler produces a FIR. The `Fir` class is cheaply movable (arena pointer transfer + vector moves). No `unique_ptr<Fir>` in public APIs.

Public APIs expose behavior, not containers. Internal storage (`std::vector`, `VecArena`, etc.) is an implementation detail hidden behind accessor methods. This applies to `Fir`, `Diagnostics`, `DomainExtension`, and all other public types.

```cpp
struct CompileResult {
    fir::Fir fir;
    DomainExtensions extensions;
    Diagnostics diagnostics;
};
```

### Diagnostics

Opaque collection type with iteration and query support. Internal storage is hidden.

```cpp
class Diagnostics {
public:
    void add(Diagnostic d);
    size_t count() const;
    const Diagnostic& operator[](size_t i) const;
    auto begin() const;
    auto end() const;
    bool has_errors() const;
private:
    /* storage hidden */
};
```

---

## Domain System

Domains represent M2 meta-models (type systems). They are the mechanism through which compilers understand what types exist and how to create conformant M1 instances.

### Domain

The storage type. Owns M2 type FIRs. Immutable — accumulating extensions produces a new Domain.

```cpp
class Domain {
public:
    explicit Domain(std::string_view name, fir::Fir base_types);

    // Produce a new Domain with extensions incorporated (does not mutate self)
    Domain with_extensions(/* extensions */) const;

    // Create a read-only view for passing to compilers
    DomainView view() const;

    std::string_view name() const;
private:
    /* name, type FIRs, index structures for fast lookup */
};
```

### DomainView

Read-only query interface over a Domain. This is what compilers receive as an immutable snapshot. Handle-based — callers ask the view about opaque handles, never dereference them directly.

```cpp
struct TypeHandle { /* opaque */ };
struct RoleHandle { /* opaque */ };

class DomainView {
public:
    // Type lookup
    TypeHandle find_type(std::string_view name) const;
    bool has_type(std::string_view name) const;

    // Type introspection
    std::string_view type_name(TypeHandle t) const;
    M3Kind type_kind(TypeHandle t) const;
    bool is_abstract(TypeHandle t) const;
    TypeHandle supertype(TypeHandle t) const;

    // Roles
    size_t role_count(TypeHandle t) const;
    RoleHandle role_at(TypeHandle t, size_t index) const;
    RoleHandle find_role(TypeHandle t, std::string_view name) const;
    std::string_view role_name(RoleHandle r) const;
    TypeHandle role_target(RoleHandle r) const;
    Multiplicity role_multiplicity(RoleHandle r) const;
    bool role_is_containment(RoleHandle r) const;

    // Enum values
    size_t enum_value_count(TypeHandle t) const;
    std::string_view enum_value_at(TypeHandle t, size_t i) const;

    // Constraints (for primitives)
    bool has_constraint(TypeHandle t) const;
    ConstraintKind constraint_kind(TypeHandle t) const;
    // ... specific constraint accessors per kind

private:
    /* non-owning reference to Domain internals */
};
```

### DomainTransaction

Mutable overlay on an immutable DomainView. Used by compilers during compilation when they need to both add new types and query types they've just added.

Lookup strategy: check the base DomainView first (fast, indexed), then linear scan through pending additions (small list, effectively free).

```cpp
class DomainTransaction {
public:
    explicit DomainTransaction(const DomainView& base);

    // Write: add new types incrementally
    TypeHandle add_type(/* type def params */);
    RoleHandle add_role(TypeHandle type, /* role def params */);

    // Read: base lookup first, then linear scan of pending
    TypeHandle find_type(std::string_view name) const;

    // Same read API as DomainView for all accessors
    std::string_view type_name(TypeHandle t) const;
    M3Kind type_kind(TypeHandle t) const;
    // ... all DomainView accessors, dispatching to base or pending

    // Finalize: extract what was added as a DomainExtension
    DomainExtension into_extension() &&;

private:
    const DomainView& base_;
    /* pending additions — small, linear scan */
};
```

### DomainExtension

What compilers return as their contribution to a domain.

```cpp
class DomainExtension {
public:
    std::string_view domain_name() const;
    const fir::Fir& types() const;
private:
    /* domain name + type FIR */
};
```

### Domain Scoping Through the Import Chain

Domains flow through the import graph with lexical scoping and snapshot semantics:

- **Sibling isolation**: Imported modules do not see each other's domain extensions.
- **Upward bubbling**: Domain extensions flow back up to the importing parent.
- **Snapshot semantics**: Each module receives an immutable snapshot of the domain at import time.
- **Parent accumulation**: Only the parent combines extensions from all its children into a new Domain.

```
parent.rupa
  using domain autosar;           -- parent starts with base domain D
  import "signals.rupa";          -- signals sees D, adds types → ΔA
  import "devices.rupa";          -- devices sees D (NOT D+ΔA), adds types → ΔB
  -- parent now sees D + ΔA + ΔB + its own additions
```

This eliminates import-order-dependent behavior — sibling modules always see the same domain regardless of import order.

---

## Compiler Interface

### Compiler

Every compiler implements this interface. The Rupa compiler is one implementation; the ARXML compiler (in Senda) is another. Compilers declare their file extensions and produce FIR from source files.

```cpp
class Compiler {
public:
    virtual ~Compiler() = default;

    // File extensions this compiler handles (e.g., {".rupa"}, {".arxml"})
    virtual /* extension list */ extensions() const = 0;

    // Compile a file, producing a FIR
    virtual CompileResult compile(
        const std::filesystem::path& path,
        CompileContext& context) = 0;
};
```

### CompileContext

Provided by the driver to every compiler invocation. This is how compilers access the system without depending on the driver or other compilers directly.

```cpp
class CompileContext {
public:
    virtual ~CompileContext() = default;

    // Compile another file (triggers registry lookup, caching, cycle detection)
    virtual CompileResult compile_import(const std::filesystem::path& path) = 0;

    // Request a domain's meta-model by name
    // Returns nullptr if domain is not available
    virtual const DomainView* request_domain(std::string_view domain) = 0;

    // Get the domain transaction for the current compilation
    virtual DomainTransaction& domain_transaction() = 0;

    // Resolve a relative import path against the current file
    virtual std::filesystem::path resolve_path(
        const std::filesystem::path& relative) const = 0;
};
```

Compilers call other compilers indirectly through `compile_import`. This breaks the circular dependency: compilers depend on `CompileContext` (an interface), not on the registry or other compilers.

### Compiler Registry

Maps file extensions to compiler implementations. Populated at startup.

```cpp
class CompilerRegistry {
public:
    void register_compiler(Compiler& compiler);
    Compiler* find_compiler(std::string_view extension) const;
    size_t compiler_count() const;
private:
    /* extension -> compiler mapping */
};
```

---

## Compilation Driver

The driver orchestrates compilation. It owns the registry, manages domains, handles import resolution and cycle detection, and creates compile contexts.

```cpp
class CompilationDriver {
public:
    explicit CompilationDriver(CompilerRegistry& registry);

    // Pre-load domains before compilation starts
    void add_domain(Domain domain);

    // Compile a root file, recursively resolving all imports
    CompileResult compile(const std::filesystem::path& root);

private:
    CompilerRegistry& registry_;
    /* domain storage (name -> Domain) */
    /* file cache (canonical path -> status + result) */
};
```

### Import Resolution Flow

When a compiler calls `context.compile_import(path)`:

1. Resolve path relative to current file, canonicalize.
2. Check in-memory cache:
   - **Done** → return cached result.
   - **InProgress** → error: circular import detected.
   - **Not seen** → proceed.
3. Check disk cache: does a `.fir` file exist that is newer than the source?
   - **Yes** → deserialize FIR from disk, return.
   - **No** → continue to compilation.
4. Mark file as InProgress.
5. Look up file extension in registry → find compiler.
6. Snapshot current domain state → create DomainView.
7. Create DomainTransaction from view.
8. Create DriverCompileContext for the imported file.
9. Invoke `compiler.compile(path, child_context)`.
10. Mark as Done, cache result in memory.
11. Write FIR to disk in background (cache for next run).
12. Return result (FIR + extensions + diagnostics). Extensions are NOT applied to the caller's domain — only the parent accumulates them.

### Domain Request Flow

When a compiler calls `context.request_domain("autosar-r23-11")`:

1. Look up in driver's domain registry.
2. Return the DomainView if found, nullptr if not.
3. The ARXML compiler uses this to map its schema reference to a domain.
4. The Rupa compiler uses this when it encounters `using domain ...;`.

### Per-File FIRs and Caching

Each compiled module produces its own FIR. FIRs can be:
- **Kept in memory** if still needed by parent compilation.
- **Discarded** once the parent has consumed them.
- **Serialized to disk** as a cache artifact (`.fir` file alongside the source).
- **Loaded from cache** on next compilation if the source hasn't changed.

The existing FIR binary serialization format (v3) serves as the cache format. No new format needed.

---

## FIR Builder

A thin, compiler-friendly construction API on top of the Fir class. Simple enough to hand-code a domain programmatically.

```cpp
class FirBuilder {
public:
    explicit FirBuilder(fir::Fir& target);

    // Type construction
    TypeHandle begin_type(std::string_view name, M3Kind kind);
    void set_abstract(TypeHandle t, bool abstract);
    void set_supertype(TypeHandle t, TypeHandle super);
    RoleHandle add_role(TypeHandle t, std::string_view name, /* params */);
    void add_enum_value(TypeHandle t, std::string_view value);
    void set_constraint(TypeHandle t, /* constraint params */);

    // Instance construction
    ObjectHandle begin_object(std::string_view name, TypeHandle type);
    void add_property(ObjectHandle obj, RoleHandle role, /* value */);

    // Domain tagging
    void set_domain(TypeHandle t, std::string_view domain);

private:
    fir::Fir& target_;
};
```

This is the API that every compiler uses internally. It's also the API a user would use to programmatically create a domain in C++ without any source file:

```cpp
fir::Fir type_fir;
FirBuilder builder(type_fir);

auto signal = builder.begin_type("Signal", M3Kind::Composite);
builder.add_role(signal, "name", /* target: string, multiplicity: 1..1 */);
builder.add_role(signal, "priority", /* target: integer, multiplicity: 0..1 */);
builder.set_domain(signal, "autosar");

Domain autosar("autosar", std::move(type_fir));
```

---

## Example: End-to-End ARXML Import

```rupa
// project.rupa
using domain autosar_r23_11;
import "ecu_config.arxml";

EcuInstance "MyECU" {
    .variant = "production";
}
```

Compilation flow:

```
1. CLI startup (in Senda):
     RupaCompiler rupa;
     ArxmlCompiler arxml;
     registry.register_compiler(rupa);    // ".rupa"
     registry.register_compiler(arxml);   // ".arxml"

     // Load pre-built AUTOSAR domain
     Domain autosar = load_autosar_r23_11_domain();
     driver.add_domain(std::move(autosar));

2. driver.compile("project.rupa"):
     extension ".rupa" → RupaCompiler
     create context with empty domain transaction

3. RupaCompiler parses "using domain autosar_r23_11;":
     calls context.request_domain("autosar_r23_11")
     driver returns DomainView over the pre-built AUTOSAR domain
     transaction now backed by this view

4. RupaCompiler parses `import "ecu_config.arxml";`:
     calls context.compile_import("ecu_config.arxml")

5. Driver handles the import:
     snapshot domain → DomainView (same AUTOSAR domain)
     extension ".arxml" → ArxmlCompiler
     create child context with DomainTransaction(view)

6. ArxmlCompiler:
     reads ecu_config.arxml
     finds schema reference → maps to "autosar_r23_11"
     calls context.request_domain("autosar_r23_11") to confirm
     uses domain_transaction() to look up types (EcuInstance, etc.)
     uses FirBuilder to create M1 FIR nodes
     returns CompileResult { fir: ecu_fir, extensions: {}, diagnostics: {} }

7. Back in RupaCompiler:
     receives ecu_fir from the import
     continues parsing own content (EcuInstance "MyECU" { ... })
     uses FirBuilder + domain_transaction() for own M1 nodes
     returns CompileResult { fir: project_fir, extensions: {}, diagnostics: {} }

8. Driver returns final result with per-file FIRs.
```

---

## Design Principles

1. **FIR is the universal language.** Every compiler targets FIR. No intermediate Rupa source generation required.
2. **Library-first.** Each layer is independently usable. A standalone tool can link just `fir` + `fir-builder` + `domain`.
3. **Public APIs expose behavior, not containers.** No `std::vector`, `std::span`, or `unique_ptr` in public interfaces. Internal storage is hidden behind accessor methods.
4. **Rupa is domain-agnostic.** All domain-specific code (ARXML compiler, AUTOSAR domains, etc.) lives in the domain repo (Senda, Vena, Brisa).
5. **Compilers are peers.** The Rupa compiler has no special status — it implements the same `Compiler` interface as any other compiler.
6. **Domains have lexical scoping.** Sibling imports see the same domain snapshot. Extensions bubble up, never sideways.
7. **Compilation results are cacheable.** Per-file FIRs are serialized to disk and reused when sources haven't changed.

---

## Dependencies

- **Existing**: FIR (data structure, serialization), lexer, parser, sema, CLI
- **New libraries**: domain, compiler-api, fir-builder, driver
- **Refactoring**: Current sema-driver becomes RupaCompiler implementing the Compiler interface; Fir gains move semantics (BumpArena/VecArena move constructors)

## Open Questions

- Exact cache invalidation strategy (timestamp vs. content hash).
- Whether DomainView should support inheritance-aware lookups (e.g., "find all subtypes of X") or keep it to direct queries only.
- FIR merge strategy when the caller needs a single consolidated FIR (e.g., for the explorer).
- Thread safety considerations if compiling independent imports in parallel.
