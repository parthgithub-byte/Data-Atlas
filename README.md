# DFAS - Digital Footprint Analysis System

A professional-grade OSINT web application that discovers, analyzes, and visualizes a person's digital footprint across the web.

## Features

- Identity normalization with username variants and search dorks
- Async discovery across major platforms
- SearxNG integration for privacy-respecting search
- Entity extraction for emails, phones, and handles
- Identity graph visualization
- Risk scoring and structured reporting
- Cookie-based authentication with stronger session security
- Docker-based local stack with Celery workers

## Local Development

### Quick start for a fresh GitHub clone

PowerShell:

```powershell
.\scripts\setup-local.ps1
cd backend
python app.py
```

Bash:

```bash
./scripts/setup-local.sh
cd backend
python app.py
```

This works without Google, DigiLocker, Redis, or SearxNG. Those integrations stay disabled until their credentials or services are configured.

### 1. Configure environment

Copy the example environment file and adjust secrets as needed.

```bash
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Rotate secrets any time with:

```bash
python scripts/generate-secrets.py
```

### 2. Install backend dependencies

```powershell
python -m pip install -r backend\requirements.txt
```

### 3. Run the backend directly

```powershell
cd c:\Data-Atlas-main\backend

# Optional: Set Google OAuth credentials if engaging Google Sign-In
# --- Google Cloud API Setup ---
# 1. Go to Google Cloud Console (console.cloud.google.com)
# 2. Create a new project and configure the OAuth consent screen
# 3. Navigate to Credentials -> Create Credentials -> OAuth client ID (Web application)
# 4. Add "http://localhost:5000/api/auth/google/callback" as an Authorized redirect URI
# 5. Copy the generated Client ID and Client Secret into the variables below
$env:GOOGLE_CLIENT_ID="your client id"
$env:GOOGLE_CLIENT_SECRET="your client secret"

python app.py
```

The app is available at `http://localhost:5000`.

Default local behavior from `.env.example`:

- SQLite runs in a local file
- task queue workers are disabled
- SearxNG is optional and disabled
- Google and DigiLocker login stay disabled until credentials are added

## Docker Compose Stack

Run the full local stack:

```bash
docker compose up --build
```

This starts:

- `dfas-web` on `http://localhost:5000`
- `dfas-worker` for Celery background jobs
- `redis` for the task queue
- `searxng` on `http://localhost:8888`

The compose setup now includes:

- persistent volumes for the SQLite database and archived evidence
- health checks for core services
- shared database storage between web and worker containers
- environment-driven configuration through `.env`

## Deployment Environments

- `.env` is tuned for local non-container development and uses a local SQLite file.
- `.env.staging` enables secure cookies and is prepared for staging rollout.
- `.env.production` enables secure cookies and stronger password policy defaults for production rollout.
- Before staging or production deployment, replace the placeholder public origins and OAuth values with your real environment values.

## Validation

### PowerShell

```powershell
.\scripts\validate.ps1
```

### Bash

```bash
./scripts/validate.sh
```

These checks run:

- backend Python compilation
- backend `unittest` suite
- frontend JavaScript syntax validation

## CI/CD

GitHub Actions workflows are included for:

- CI validation on pushes and pull requests
- container image publishing to GHCR on `main` and version tags

Files:

- `.github/workflows/ci.yml`
- `.github/workflows/publish-image.yml`

## Agile + DevOps

The repository now includes lightweight Agile delivery support:

- pull request template with Definition of Done
- issue templates for bugs and features
- shared working agreement in `docs/AGILE_DEVOPS.md`

Use the working agreement to keep changes tied to:

- sprint goals
- acceptance criteria
- verification steps
- security and rollback thinking

## Security Notes

- Authentication uses protected cookies instead of browser `localStorage` tokens
- Mutating API requests require CSRF headers
- Scan and evidence access are scoped to the owning user
- Internal server file paths are no longer returned by the API

## Updating Platform Data

The profile catalog lives in `backend/core/platform_catalog.json`.

- Admin or analyst users can manage it from the in-app Platform Catalog page
- The API returns a storage label instead of leaking host filesystem paths

## DigiLocker Authentication

To enable Aadhaar-based authentication:

1. Register at `https://partners.digilocker.gov.in`
2. Set:

```bash
set DIGILOCKER_CLIENT_ID=your_client_id
set DIGILOCKER_CLIENT_SECRET=your_client_secret
```

## Google Authentication

To enable Google sign-in:

1. Create a Google OAuth client with the redirect URI `http://localhost:5000/api/auth/google/callback`
2. Set:

```bash
set GOOGLE_CLIENT_ID=your_client_id
set GOOGLE_CLIENT_SECRET=your_client_secret
```

## Architecture

```text
Layer 1: Identity Normalization -> Variant & Dork Generation
Layer 2: Async Discovery Engine -> Username Enumeration + SearxNG
Layer 3: Investigation Engine   -> Page Scraping + Cleaning
Layer 4: Entity Extraction      -> Emails, Phones, Handles, Links
Layer 5: Identity Graph         -> NetworkX + Risk Scoring
Layer 6: Report Synthesis       -> Categorized Findings
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Flask + SQLAlchemy |
| Database | SQLite |
| Queue | Celery + Redis |
| Search | SearxNG |
| Graph | NetworkX + Cytoscape.js |
| Auth | JWT cookies + DigiLocker OAuth2 |
| Frontend | Vanilla JS SPA |
| CI/CD | GitHub Actions + GHCR |

## License

For educational and authorized security research purposes only.
