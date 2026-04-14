#!/usr/bin/env bash
# Build Tailwind CSS from templates (requires bun or npx)
set -e
cd "$(dirname "$0")/.."
bunx tailwindcss@3 \
  -i core/templates/static/src/input.css \
  -o core/templates/static/tailwind.min.css \
  --minify
echo "Built core/templates/static/tailwind.min.css"
