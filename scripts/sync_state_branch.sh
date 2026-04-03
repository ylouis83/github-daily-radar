#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(git rev-parse --show-toplevel)"
STATE_DIR="$(mktemp -d)"
git fetch origin state || true

if git show-ref --verify --quiet refs/remotes/origin/state; then
  git worktree add "$STATE_DIR" origin/state
else
  git worktree add --detach "$STATE_DIR"
  (
    cd "$STATE_DIR"
    git checkout --orphan state
    git rm -rf . >/dev/null 2>&1 || true
  )
fi

(
  cd "$STATE_DIR"
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  mkdir -p artifacts
  if [ -d "$SOURCE_DIR/artifacts" ]; then
    cp -R "$SOURCE_DIR/artifacts/." artifacts/
  fi
  git add artifacts
  if git diff --cached --quiet; then
    echo "No state changes to commit."
  else
    git commit -m "chore(state): update daily artifacts"
    git push origin HEAD:state
  fi
)
