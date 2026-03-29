#!/usr/bin/env bash
set -euo pipefail

echo "Running backend compilation..."
python -m compileall backend

echo "Running backend unit tests..."
(cd backend && python -m unittest discover -v)

echo "Running frontend JavaScript syntax checks..."
while IFS= read -r -d '' file; do
  echo "CHECK $file"
  node --check "$file"
done < <(find frontend/js -type f -name '*.js' -print0)

echo "Validation completed successfully."
