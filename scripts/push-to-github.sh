#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

if ! gh auth status &>/dev/null; then
  echo "Logging into GitHub (browser will open)..."
  gh auth login -p https -w
fi
gh auth setup-git
git remote set-url origin https://github.com/primalBeast/local-issue-tracker.git
git push -u origin main
echo "Pushed successfully!"
