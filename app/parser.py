import asyncio
import io
import json
import logging

import google.generativeai as genai
import pypdf
import pypdf.errors

from app.schemas import ParsedResume

logger = logging.getLogger(__name__)

PARSE_SYSTEM_PROMPT = """
You are a resume parser. Extract structured information from the resume text.
Return ONLY valid JSON matching the provided schema. No markdown, no commentary.
If a field is not present in the resume, return null (or empty list for arrays).
Normalise dates to ISO format YYYY-MM. Use null for "Present" or "Current".
""".strip()

# JSON schema passed to Gemini so it knows what fields to extract
RESUME_JSON_SCHEMA = """
{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "summary": "string or null",
  "work_experience": [
    {
      "company": "string",
      "role": "string",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or null",
      "description": "string or null"
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string or null",
      "field_of_study": "string or null",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or null"
    }
  ],
  "skills": ["string"]
}
"""


async def parse_resume(
    pdf_bytes: bytes,
    model: genai.GenerativeModel,
) -> ParsedResume:
    """Extract structured data from a resume PDF using Gemini."""
    text = await asyncio.to_thread(_extract_text, pdf_bytes)
    if not text:
        raise ValueError("PDF contains no extractable text")
    return await _call_gemini(text, model)


def _extract_text(pdf_bytes: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except pypdf.errors.PdfReadError as e:
        logger.error("pdf_extract_failed", extra={"error_type": type(e).__name__})
        raise


async def _call_gemini(text: str, model: genai.GenerativeModel) -> ParsedResume:
    prompt = (
        f"{PARSE_SYSTEM_PROMPT}\n\n"
        f"Schema:\n{RESUME_JSON_SCHEMA}\n\n"
        f"Resume text:\n{text}"
    )

    response = await model.generate_content_async(prompt)

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        logger.error("gemini_empty_response")
        raise ValueError("Gemini returned empty response")

    finish_reason = getattr(candidates[0], "finish_reason", None)
    if finish_reason and str(finish_reason) not in {"STOP", "FinishReason.STOP", "1"}:
        logger.error("gemini_blocked", extra={"finish_reason": str(finish_reason)})
        raise ValueError(f"Gemini response not usable: {finish_reason}")

    try:
        raw = response.text
    except ValueError as e:
        logger.error("gemini_text_unavailable", extra={"error_type": type(e).__name__})
        raise

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("gemini_response_not_json", extra={"error_type": type(e).__name__})
        raise ValueError("Gemini returned non-JSON response") from e

    return ParsedResume.model_validate(data)
