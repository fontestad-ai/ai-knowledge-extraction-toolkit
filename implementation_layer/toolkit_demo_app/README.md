# Clinical Knowledge Extraction UI

Standalone frontend and API surface for the clinical guideline extraction workflow in this repository.

## Features

- Upload clinical guideline PDFs, Office files, or page images
- Load bundled example files from `/home/runner/work/ai-knowledge-extraction-toolkit/ai-knowledge-extraction-toolkit/uploads`
- Extract source-grounded hypertension knowledge with the existing clinical framework
- Review parsed source text, structured extraction output, and operationalized clinical units
- Optionally trigger validation when validator extras are available

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- Azure OpenAI or OpenAI credentials

### Setup

```bash
cd /home/runner/work/ai-knowledge-extraction-toolkit/ai-knowledge-extraction-toolkit/implementation_layer/toolkit_demo_app
npm install --no-package-lock
uv pip install -r api/requirements.txt
```

### Run both servers

```bash
# Terminal 1: frontend
npx next dev

# Terminal 2: API
cd /home/runner/work/ai-knowledge-extraction-toolkit/ai-knowledge-extraction-toolkit/implementation_layer/toolkit_demo_app/api
uvicorn main:app --reload
```

- Frontend: <http://localhost:3000>
- API Docs: <http://localhost:8000/docs>

## API Endpoints

| Prefix | Description |
| --- | --- |
| `/health` | Health check |
| `/clinical/extract` | Clinical guideline extraction |
| `/clinical/examples` | Bundled example asset listing |

## Notes

- Frontend authentication and authorization are intentionally disabled in this standalone branch.
- The UI is integrated into the existing frontend shell rather than a separate demo application.

## External service inventory

Removed from the current frontend shell:

- Supabase auth / access control
- Upstash Redis rate limiting
- PostHog analytics and remote widget bootstraps

Still external in the active clinical extraction path:

- Azure OpenAI or OpenAI via the current `gaik` clinical extraction pipeline

Local replacement target:

- SQLite for local persistence
- sqlite-vec (or equivalent SQLite vector extension) if vector search is added later
- LMCLI-backed extraction should be the next step if you want zero third-party model calls
