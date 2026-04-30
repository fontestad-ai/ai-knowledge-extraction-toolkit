"""Standalone clinical knowledge extraction API."""

import logging
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

env_path = Path(__file__).parent.parent / ".env.local"
load_dotenv(env_path, override=True)

from fastapi import FastAPI, Request  # noqa: E402, I001
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from gaik import __version__ as gaik_version  # noqa: E402, F401

try:
    from routers import clinical
except ImportError:
    from api.routers import clinical


app = FastAPI(
    title="Clinical Knowledge Extraction API",
    description="REST API for the standalone clinical guideline extraction workflow",
    version=gaik_version,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(clinical.router, prefix="/clinical", tags=["Clinical Extraction"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "clinical-knowledge-extraction-api"}


@app.get("/")
async def root():
    return {
        "name": "Clinical Knowledge Extraction API",
        "version": gaik_version,
        "docs": "/docs",
        "endpoints": {
            "clinical": (
                "/clinical/extract - Extract traceable clinical knowledge "
                "from uploaded guideline files"
            ),
            "examples": "/clinical/examples - List bundled guideline example assets",
        },
    }
