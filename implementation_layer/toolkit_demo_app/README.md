# Clinical Knowledge Extraction UI

Standalone frontend and API surface for the clinical guideline extraction workflow in this repository.

## Features

- Upload clinical guideline PDFs, Office files, or page images
- Load bundled example files from `/home/runner/work/ai-knowledge-extraction-toolkit/ai-knowledge-extraction-toolkit/uploads`
- Extract source-grounded hypertension knowledge with an LMCLI-first local framework
- Review parsed source text, structured extraction output, and operationalized clinical units
- Persist extraction runs, clinical units, RAG text, and graph projections in local SQLite
- Optionally trigger validation when validator extras are available

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- Optional local LMCLI command configured by `CLINICAL_LMCLI_COMMAND`

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
| `/clinical/runs` | Locally persisted SQLite extraction run listing |

## Notes

- Frontend authentication and authorization are intentionally disabled in this standalone branch.
- The UI is integrated into the existing frontend shell rather than a separate demo application.

## External service inventory

Removed from the current frontend shell:

- Supabase auth / access control
- Upstash Redis rate limiting
- PostHog analytics and remote widget bootstraps

Still present in broader toolkit dependencies, but not called by the active clinical path:

- OpenAI/Azure SDK dependencies remain in the reusable `gaik` toolkit package
- OpenAI/Azure-capable parsers are disabled in the standalone clinical UI/API defaults

Local replacement implemented for the active clinical path:

- LMCLI-first extraction via `CLINICAL_LMCLI_COMMAND`
- Conservative deterministic local extraction fallback when LMCLI is absent
- SQLite for local persistence
- sqlite-vec-ready RAG rows with local embedding slots for future vector search
