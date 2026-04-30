"""Clinical knowledge extraction router."""

from __future__ import annotations

import mimetypes
import shutil
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import fitz
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from utils import get_api_config, validate_file_size
except ImportError:
    from api.utils import get_api_config, validate_file_size

from gaik.software_modules.clinical_guidelines_to_structured_data import (
    DEFAULT_HYPERTENSION_EXTRACTION_REQUIREMENTS,
    ClinicalGuidelineKnowledgeExtractor,
)

router = APIRouter()

SUPPORTED_FILE_SUFFIXES = {
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
}
SUPPORTED_PARSER_CHOICES = {
    "auto",
    "multimodal",
    "vision_plus",
    "vision_parser",
    "docling",
    "pymupdf",
    "docx",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
MAX_VALIDATION_PAGES = 10
UPLOADS_DIR = Path(__file__).resolve().parents[4] / "uploads"


class ClinicalExampleAsset(BaseModel):
    name: str
    url: str
    media_type: str


class ClinicalExamplesResponse(BaseModel):
    examples: list[ClinicalExampleAsset]


def _ensure_supported_file(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_FILE_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_FILE_SUFFIXES))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix or 'unknown'}'. Supported types: {supported}",
        )
    return suffix


def _list_example_assets() -> list[ClinicalExampleAsset]:
    if not UPLOADS_DIR.exists():
        return []

    examples: list[ClinicalExampleAsset] = []
    for path in sorted(UPLOADS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_FILE_SUFFIXES:
            continue
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        examples.append(
            ClinicalExampleAsset(
                name=path.name,
                url=f"/api/clinical/examples/{quote(path.name)}",
                media_type=media_type,
            )
        )
    return examples


def _resolve_example_path(filename: str) -> Path:
    uploads_dir = UPLOADS_DIR.resolve()
    candidate = (uploads_dir / filename).resolve()
    try:
        candidate.relative_to(uploads_dir)
    except ValueError as exc:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Example asset not found") from exc

    if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_FILE_SUFFIXES:
        raise HTTPException(status_code=404, detail="Example asset not found")
    return candidate


def _render_source_pages(file_suffix: str, content: bytes) -> list[bytes] | None:
    if file_suffix in IMAGE_SUFFIXES:
        return [content]

    if file_suffix != ".pdf":
        return None

    pages: list[bytes] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        for page_index in range(min(document.page_count, MAX_VALIDATION_PAGES)):
            pixmap = document.load_page(page_index).get_pixmap(dpi=150, alpha=False)
            pages.append(pixmap.tobytes("png"))
    return pages or None


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    return value


@router.get("/examples", response_model=ClinicalExamplesResponse)
async def list_examples() -> ClinicalExamplesResponse:
    """List bundled example assets from the repository uploads folder."""
    return ClinicalExamplesResponse(examples=_list_example_assets())


@router.get("/examples/{filename:path}")
async def get_example_file(filename: str) -> FileResponse:
    """Serve a bundled example asset."""
    file_path = _resolve_example_path(filename)
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)


@router.post("/extract")
async def extract_clinical_guideline(
    file: UploadFile = File(...),
    user_requirements: str = Form(DEFAULT_HYPERTENSION_EXTRACTION_REQUIREMENTS),
    parser_choice: str = Form("auto"),
    operationalize: bool = Form(True),
    validate_extraction: bool = Form(False),
) -> dict[str, Any]:
    """Extract traceable clinical knowledge from an uploaded guideline file."""
    if parser_choice not in SUPPORTED_PARSER_CHOICES:
        allowed = ", ".join(sorted(SUPPORTED_PARSER_CHOICES))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported parser choice. Allowed: {allowed}",
        )

    suffix = _ensure_supported_file(file.filename)
    content = await validate_file_size(file)
    temp_dir = Path(tempfile.mkdtemp(prefix="clinical-guideline-"))
    temp_path = temp_dir / Path(file.filename or f"clinical_upload{suffix}").name

    try:
        temp_path.write_bytes(content)
        source_pages = _render_source_pages(suffix, content) if validate_extraction else None
        if validate_extraction and not source_pages:
            raise HTTPException(
                status_code=400,
                detail="Validation is currently available for PDF and image uploads only.",
            )

        extractor = ClinicalGuidelineKnowledgeExtractor(api_config=get_api_config())
        result = extractor.run(
            file_path=temp_path,
            parser_choice=parser_choice,
            operationalize=operationalize,
            validate=validate_extraction,
            source_pages=source_pages,
            source_document_id=temp_path.name,
        )

        return {
            "source_file": temp_path.name,
            "parser_choice": result.parser_choice,
            "route": _to_jsonable(result.route),
            "parsed_documents": result.parsed_documents,
            "extracted_knowledge": result.extracted_knowledge,
            "operationalized_knowledge": _to_jsonable(result.operationalized_knowledge),
            "validation": _to_jsonable(result.validation),
        }
    except HTTPException:
        raise
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
