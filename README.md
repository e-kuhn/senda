# Senda

Automotive DSL built on the [Rupa](https://github.com/e-kuhn/rupa) language — AUTOSAR tooling, patterns, and schema conversion.

**Senda** (Spanish for "path") is part of a naming family for domain-specific Rupa implementations:
- **Senda** — Automotive (AUTOSAR)
- **Vena** — Medical (Latin for "vein")
- **Brisa** — Aviation (Spanish for "breeze")

## Building

Requires CMake 3.28+, Ninja, and Homebrew LLVM (for C++ modules support).

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/e-kuhn/senda.git
cd senda

# Build
cmake --preset debug
cmake --build --preset debug

# Run
./build-debug/senda
```

## Directory Layout

```
senda/
├── external/rupa/           # Rupa language implementation (submodule)
├── src/                     # C++ CLI source
├── test/                    # Tests
├── tools/
│   └── schema-converter/    # AUTOSAR XSD → Rupa schema converter (Python)
├── docs/
│   ├── patterns/            # AUTOSAR → Rupa pattern mappings
│   ├── use-cases/           # End-to-end AUTOSAR workflows
│   ├── research/            # Domain research
│   └── plans/               # Design & implementation plans
├── CMakeLists.txt
└── CMakePresets.json
```

## Schema Converter

The Python-based schema converter translates AUTOSAR XSD schemas into Rupa type definitions.

```bash
python -m venv .venv && source .venv/bin/activate
pip install lxml pytest

# Run tests
python -m pytest tools/schema-converter/tests/ -v
```
