#!/usr/bin/env bash
# Wrapper to run gstack ./setup with Node + Bun on PATH, logging everything.
exec > "$HOME/Documents/miraheze-local/gstack-setup-output.log" 2>&1
export PATH="/c/Program Files/nodejs:/c/Users/danny/.bun/bin:$PATH"
echo "=== versions ==="
node --version
bun --version
git --version
echo "=== running ./setup --no-prefix ==="
cd "$HOME/.claude/skills/gstack" || { echo "cd into gstack failed"; exit 1; }
./setup --no-prefix
echo "=== SETUP EXIT=$? ==="
