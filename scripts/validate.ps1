$ErrorActionPreference = "Stop"

Write-Host "Running backend compilation..."
python -m compileall backend

Write-Host "Running backend unit tests..."
Push-Location backend
python -m unittest discover -v
Pop-Location

Write-Host "Running frontend JavaScript syntax checks..."
Get-ChildItem -Path frontend\js -Recurse -Filter *.js | ForEach-Object {
    Write-Host "CHECK $($_.FullName)"
    node --check $_.FullName
}

Write-Host "Validation completed successfully."
