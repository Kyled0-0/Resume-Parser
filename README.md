# Resume Parser

A containerised resume parsing API. PDF in, structured JSON out.
Built as the SIT323 capstone deliverable; designed to extend into a Chrome extension that auto-fills job application forms.

## Architecture

```
Client (browser / curl / future extension)
  │
  │  POST /parse  (multipart, PDF upload)
  ▼
Kubernetes LoadBalancer Service (port 80)
  │
  ▼
FastAPI pod (port 8000)
  │
  ├─ pypdf extracts raw text from the PDF
  │
  ├─ Gemini API call with extracted text + JSON schema
  │   (system prompt: "extract resume into schema, return only JSON")
  │
  └─ Validates response against Pydantic schema
       │
       ▼
       Returns 200 with parsed JSON
```

The same pod also serves a static single-page UI from `/` for browser-based demo use.

## Tech Stack

- **Python 3.12** + FastAPI + Pydantic v2 + pydantic-settings
- **Gemini API** (`google-generativeai`) for resume parsing — model configurable via `GEMINI_MODEL`
- **pypdf** for PDF text extraction
- **uvicorn** ASGI server, async throughout
- **Docker** multi-stage image (~458 MB), runs as non-root `app` user
- **GKE Autopilot** for Kubernetes deployment
- **Artifact Registry** for image storage
- **Cloud Build** for CI/CD on push to `main`

## Local Development

Requires Python 3.12+ and a Gemini API key from [`aistudio.google.com/app/apikey`](https://aistudio.google.com/app/apikey) (free tier).

**1. Clone and set up the environment**

Windows (PowerShell):
```powershell
git clone https://github.com/Kyled0-0/Resume-Parser.git
cd Resume-Parser
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env    # set GEMINI_API_KEY=...
```

macOS / Linux:
```bash
git clone https://github.com/Kyled0-0/Resume-Parser.git
cd Resume-Parser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
$EDITOR .env    # set GEMINI_API_KEY=...
```

**2. Run the server**

```bash
uvicorn app.main:app --reload --port 8000
```

**3. Open in a browser**

- `http://localhost:8000/` — drop-in resume parser UI
- `http://localhost:8000/docs` — OpenAPI Swagger UI

## Run via Docker

```bash
docker build -t resume-parser:local .
docker run -p 8000:8000 --env-file .env resume-parser:local
```

The image is multi-stage, runs as a non-root user (`uid=1000`), and includes a `HEALTHCHECK` that hits `/health` every 30s.

## Deployment

See [`DEPLOY.md`](DEPLOY.md) for the full GCP Console steps:
1. Create Artifact Registry repository
2. Provision GKE Autopilot cluster
3. Apply the `GEMINI_API_KEY` Secret
4. Deploy via Workloads page (paste `k8s/deployment.yaml` into the YAML editor)
5. Expose via Services & Ingress (`k8s/service.yaml`)
6. Connect GitHub repo to Cloud Build with `cloudbuild.yaml` — pushes to `main` build, push to Artifact Registry, and roll out to the cluster automatically.

## Project Structure

```
.
├── app/                    # FastAPI service code
│   ├── main.py             # Routes, app instance, logging setup
│   ├── config.py           # pydantic-settings env loader
│   ├── dependencies.py     # Cached Gemini client provider
│   ├── parser.py           # PDF extraction + Gemini call
│   └── schemas.py          # Pydantic request/response models
├── static/
│   └── index.html          # Single-file browser UI
├── k8s/
│   ├── deployment.yaml     # Pod spec, env, probes, resources
│   ├── service.yaml        # LoadBalancer
│   └── secret.template.yaml  # Placeholder — real secret applied separately
├── Dockerfile              # Multi-stage build (Python 3.12-slim)
├── .dockerignore
├── cloudbuild.yaml         # CI/CD pipeline
├── requirements.txt
├── .env.example
├── DEPLOY.md               # GCP Console deployment walkthrough
└── README.md
```

## Environment Variables

| Name | Required | Default | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | yes | — | From `aistudio.google.com` |
| `GEMINI_MODEL`   | no  | `models/gemini-2.0-flash` | Swap to a different model if quota is exhausted |
| `LOG_LEVEL`      | no  | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MAX_PDF_SIZE_BYTES` | no | `10485760` | 10 MB upload cap |

## API

### `POST /parse`

Accepts a single PDF file in a multipart form field named `file`. Returns the parsed resume as JSON.

```bash
curl -X POST -F "file=@resume.pdf" http://localhost:8000/parse
```

Response shape (`ParsedResume`):

```json
{
  "name": "...",
  "email": "...",
  "phone": "...",
  "location": "...",
  "summary": "...",
  "work_experience": [
    { "company": "...", "role": "...", "start_date": "YYYY-MM",
      "end_date": "YYYY-MM or null (Present)", "description": "..." }
  ],
  "education": [
    { "institution": "...", "degree": "...", "field_of_study": "...",
      "start_date": "...", "end_date": "..." }
  ],
  "skills": ["..."]
}
```

### `GET /health`

Liveness probe. Returns `{"status": "ok"}`.

## Limitations

- **Single replica, no autoscaling** — capstone scope. HPA is post-submission work.
- **No authentication on `/parse`** — relies on network-level controls; intended for limited demo use, not public production.
- **English resumes only** — the Gemini prompt is English-tuned.
- **Free-tier Gemini quota** — `GEMINI_MODEL` is configurable to swap models when a daily quota is exhausted.
- **Image-only / scanned PDFs** are rejected with 422 (no OCR step).

## License

Capstone project — not licensed for redistribution.
