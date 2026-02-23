# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Senda ("path" in Spanish) is an automotive DSL built on the [Rupa](https://github.com/e-kuhn/rupa) language — providing AUTOSAR tooling, pattern mappings, and schema conversion. It is part of a naming family for domain-specific Rupa implementations (Senda/Automotive, Vena/Medical, Brisa/Aviation).

## Key References

- **Rupa (language implementation)**: `external/rupa/` — the C++23 Rupa language implementation (submodule). Provides lexer, parser, and kore libraries.
- **Specification**: `external/rupa/external/rupa-spec/` — the canonical Rupa language spec (871 requirements across 15 categories). Design docs in `design/current/` (folders `01-*` through `12-*`).
- **OML (reference implementation)**: `../oml/` — a previous DSL implementation with the same architecture. **Always consult OML for patterns, structure, and conventions before implementing new components.**
- **Pattern docs**: `docs/patterns/` — AUTOSAR → Rupa pattern mappings (13 patterns).
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

## Workflow: Mandatory Rules

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
