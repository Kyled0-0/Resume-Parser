import logging

import google.generativeai as genai
import pydantic
import pypdf.errors
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from google.api_core.exceptions import GoogleAPICallError
from pythonjsonlogger import jsonlogger

from app.config import settings
from app.dependencies import get_gemini_model
from app.parser import parse_resume
from app.schemas import ErrorResponse, HealthResponse, ParsedResume


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
    ))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(settings.log_level)


_configure_logging()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Resume Parser",
    description="PDF resume → structured JSON via Gemini",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.post(
    "/parse",
    response_model=ParsedResume,
    responses={
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def parse(
    file: UploadFile,
    model: genai.GenerativeModel = Depends(get_gemini_model),
) -> ParsedResume:
    """Parse a resume PDF and return structured JSON."""
    pdf_bytes = await file.read()

    if len(pdf_bytes) > settings.max_pdf_size_bytes:
        raise HTTPException(status_code=413, detail="PDF exceeds size limit")

    try:
        return await parse_resume(pdf_bytes, model)
    except pypdf.errors.PdfReadError as e:
        logger.error("pdf_read_error", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=422, detail="Could not read PDF") from e
    except pydantic.ValidationError as e:
        logger.error("response_validation_error", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=502, detail="Upstream parsing service returned invalid data") from e
    except GoogleAPICallError as e:
        logger.error(
            "gemini_api_error",
            extra={
                "error_type": type(e).__name__,
                "error_code": getattr(e, "code", None),
                "error_details": str(getattr(e, "details", "")),
            },
        )
        raise HTTPException(status_code=502, detail="Upstream parsing service failed") from e
    except ValueError as e:
        logger.error("parse_value_error", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("parse_unexpected_error", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail="Internal server error") from e
