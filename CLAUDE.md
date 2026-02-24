# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Senda ("path" in Spanish) is an automotive DSL built on the [Rupa](https://github.com/e-kuhn/rupa) language — providing AUTOSAR tooling, pattern mappings, and schema conversion. It is part of a naming family for domain-specific Rupa implementations (Senda/Automotive, Vena/Medical, Brisa/Aviation).

## Key References

- **Rupa (language implementation)**: `external/rupa/` — the C++23 Rupa language implementation (submodule). Provides lexer, parser, and kore libraries.
- **Specification**: `external/rupa/external/rupa-spec/` — the canonical Rupa language spec (871 requirements across 15 categories). Design docs in `design/current/` (folders `01-*` through `12-*`).
- **OML (reference implementation)**: `../oml/` — a previous DSL implementation with the same architecture. **Always consult OML for patterns, structure, and conventions before implementing new components.**
- **Pattern docs**: `docs/patterns/` — AUTOSAR → Rupa pattern mappings (13 patterns).
- **AUTOSAR schemas**: `schema/` — AUTOSAR XSD schemas (R4.3.1 through R23-11, files `AUTOSAR_00048.xsd` to `AUTOSAR_00052.xsd`). Used by the schema converter to generate Rupa type definitions.
- **Schema converter**: `tools/schema-converter/` — Python tool that translates AUTOSAR XSD schemas into Rupa type definitions.

## Build & Test

```bash
# C++ build (requires CMake 3.28+, Ninja, Homebrew LLVM)
cmake --preset debug
cmake --build --preset debug
./build-debug/senda

# Schema converter tests (Python)
python -m venv .venv && source .venv/bin/activate
pip install lxml pytest
python -m pytest tools/schema-converter/tests/ -v
```

## Working in Inner Repositories

Changes from Senda may touch the inner submodules. All paths below are relative to Senda's root.

### Rupa (Language Implementation) — `external/rupa/`

Rupa is a C++23 implementation of the Rupa language — a domain-specific language for working with structured data models across diverse formats (AUTOSAR/automotive, healthcare, configuration management, etc.).

**Sibling references (from Rupa's perspective):**
- **Specification**: `external/rupa/external/rupa-spec/` — the canonical Rupa language spec (871 requirements across 15 categories). Formal spec in `external/rupa/external/rupa-spec/spec/`.
- **OML (reference implementation)**: `../oml/` (relative to Senda root's parent) — a previous DSL implementation with the same architecture. **Always consult OML for patterns, structure, and conventions before implementing new components.**

**Optimization workflow** (within Rupa):
- Campaign folders: `external/rupa/docs/optimization/<campaign-name>/`
- Knowledge base: `external/rupa/docs/research/optimization/`
- Invoke: `/optimize <campaign>` or describe optimization goals in natural language

### Rupa-Spec (Language Design) — `external/rupa/external/rupa-spec/`

**Current status: Design complete. Ready for specification writing.** All design topics (1-12), parking lot items (1-30), and pre-spec triage items (31-42) are resolved.

**Key documents:**
- **Canonical Design**: `external/rupa/external/rupa-spec/design/current/` — authoritative design decisions (folders `01-*` through `12-*`, plus `examples/`)
- **Transient Material**: `external/rupa/external/rupa-spec/design/transient/` — intermediate/historical artifacts (research, review, suggestions, progress log)
- **Formal Spec**: `external/rupa/external/rupa-spec/spec/`
- **All builtins**: `external/rupa/external/rupa-spec/design/current/06-extensibility/expression-builtins-reference.md`
- **M3 API**: `external/rupa/external/rupa-spec/design/current/06-extensibility/m3-api-reference.md`

**Design review mindset** (when working on Rupa-spec):
- Assume every decision is wrong until it proves otherwise
- Construct adversarial examples — write concrete Rupa code that breaks, confuses, or exploits a decision
- Steel-man before you attack — understand the strongest version of why a decision was made
- Draw on real-world failures from other languages (ODL/OML, JSON, YAML, XML, etc.)
- Focus on feature interactions, edge cases at boundaries, and emergent complexity
- Treat "deferred" as a red flag — push on whether deferrals hide unresolved contradictions
- Render explicit verdicts: "This holds up", "This has a fixable problem", or "This needs to be revisited"

**Review protocol** (when reviewing a design decision):
1. Read the decision document and its context
2. Attack the rationale — are there unstated assumptions?
3. Construct adversarial examples in concrete Rupa code
4. Check cross-cutting interactions across at least 3 other design areas
5. Compare with prior art — successes and failures from other languages
6. Assess deferred items — could resolving them differently force a redesign?
7. Render a verdict — be explicit, no hedging

**Saving design decisions** to `external/rupa/external/rupa-spec/design/current/`:
```
01-foundational/  02-syntax/  03-data-modeling/  ...  12-documentation/  examples/
```
Each decision document should include: Topic, Decision, Rationale, Alternatives Considered, Dependencies, Open Questions.

**Design principles:**
- Consistency over cleverness — predictable behavior trumps elegant shortcuts
- Explicit over implicit — when in doubt, make the user state their intent
- Tooling-first design — error recovery for LSP; quality error messages
- Evolution is inevitable — design for future extension without breaking changes
- Domain experts are the users — not every user is a programmer

### Submodule Commit Workflow

When changes touch inner repos, commit from the inside out:
1. Commit changes inside `external/rupa/external/rupa-spec/` first (if applicable)
2. Commit the updated submodule pointer in `external/rupa/`
3. Commit the updated submodule pointer in Senda's root

## Workflow: Mandatory Rules

### 0. Update Submodules First

**Before starting any new task**, run the update script to ensure all submodule pointers are at the latest remote `main`:

```bash
./scripts/update-submodules.sh
```

This recursively fetches and checks out the latest commit on each submodule's default branch, then stages the updated pointers. If anything changed, commit the update as part of your first commit on the new branch.

### 1. Never Work on Main

**All changes happen in a git worktree.** Never modify files directly on the main branch.

```bash
# Create a worktree for a feature
git worktree add .worktrees/<branch-name> -b <branch-name>

# All edits happen inside .worktrees/<branch-name>/
# The main working directory stays clean on main
```

### 2. Brainstorm Before Implementing

Before tackling any task, **always use the brainstorm skill** to explore requirements, design, and approach. No exceptions.

### 3. Plan in Small Batches

Implementation plans must be broken into **small, independently completable batches**. This allows stopping at any checkpoint and resuming in a new session. Plans go in `docs/plans/`.

### 4. Parallel Execution

Once a plan is approved, spawn multiple workers in a new session using the subagent-driven-development or dispatching-parallel-agents skills.

### 5. Context Health Monitoring

**Stop if context health drops to 30% or below.** When stopping mid-plan:
- Save current progress (update task status, note which batch is complete)
- Provide a **continuation prompt** for the next session that includes:
  - Path to the plan file (e.g., `docs/plans/<plan-name>.md`)
  - Path to the worktree (e.g., `.worktrees/<branch-name>/`)
  - Which tasks/batches are complete and which remain
  - Any relevant state or decisions made during execution

### 6. Completion: PR, Merge, Cleanup

When a plan is fully implemented:
1. Create a PR: `gh pr create`
2. Merge: `gh pr merge`
3. Switch to main, delete the feature branch, remove the worktree
