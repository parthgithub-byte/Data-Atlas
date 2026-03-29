$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists; leaving it in place"
}

Write-Host "Installing backend dependencies..."
Push-Location backend
python -m pip install -r requirements.txt
Pop-Location

Write-Host "Local setup complete."
Write-Host "Start the app with:"
Write-Host "  cd backend"
Write-Host "  python app.py"
