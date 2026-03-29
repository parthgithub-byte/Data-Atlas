#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
else
  echo ".env already exists; leaving it in place"
fi

echo "Installing backend dependencies..."
(cd backend && python -m pip install -r requirements.txt)

echo "Local setup complete."
echo "Start the app with:"
echo "  cd backend"
echo "  python app.py"
