import logging

import anthropic
from fastapi import Depends, FastAPI, HTTPException, UploadFile

from app.config import settings
from app.dependencies import get_anthropic_client
from app.parser import parse_resume
from app.schemas import ErrorResponse, HealthResponse, ParsedResume

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Resume Parser",
    description="PDF resume → structured JSON via Claude",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.post(
    "/parse",
    response_model=ParsedResume,
    responses={413: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def parse(
    file: UploadFile,
    client: anthropic.Anthropic = Depends(get_anthropic_client),
) -> ParsedResume:
    """Parse a resume PDF and return structured JSON."""
    pdf_bytes = await file.read()

    if len(pdf_bytes) > settings.max_pdf_size_bytes:
        raise HTTPException(status_code=413, detail="PDF exceeds size limit")

    try:
        return await parse_resume(pdf_bytes, client)
    except ValueError as e:
        logger.error("parse_failed", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=502, detail="Upstream parsing service failed") from e
    except Exception as e:
        logger.error("parse_unexpected_error", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail="Internal server error") from e
