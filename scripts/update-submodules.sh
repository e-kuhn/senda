#!/usr/bin/env bash
# Update all git submodules (recursively) to the latest commit on their
# remote main branch, then stage the updated pointers.
#
# Usage: ./scripts/update-submodules.sh
#
# Run this from the repository root before starting work on a new task.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "Initialising submodules..."
git submodule update --init --recursive

echo "Updating submodules to latest origin/main..."
git submodule foreach --recursive '
  git fetch origin
  DEFAULT=$(git remote show origin | sed -n "s/.*HEAD branch: //p")
  echo "  -> checking out origin/$DEFAULT"
  git checkout "origin/$DEFAULT"
'

echo ""
echo "Staging updated submodule pointers..."
git submodule foreach --quiet 'echo $sm_path' | while read -r sm; do
  git add "$sm"
done

echo ""
echo "Done. Submodule status:"
git submodule status --recursive
