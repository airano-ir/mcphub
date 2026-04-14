#!/usr/bin/env bash
# Watch templates and rebuild Tailwind CSS on changes (dev mode).
# Stops with Ctrl+C. Requires bun (bunx).
set -e
cd "$(dirname "$0")/.."
echo "Watching core/templates/**/*.html for Tailwind changes..."
bunx tailwindcss@3 \
  -i core/templates/static/src/input.css \
  -o core/templates/static/tailwind.min.css \
  --minify \
  --watch
