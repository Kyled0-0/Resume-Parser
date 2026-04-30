import io
import json
import logging

import anthropic
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

# JSON schema passed to Claude so it knows what fields to extract
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
    client: anthropic.Anthropic,
) -> ParsedResume:
    """Extract structured data from a resume PDF using Claude."""
    text = _extract_text(pdf_bytes)
    return await _call_claude(text, client)


def _extract_text(pdf_bytes: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except pypdf.errors.PdfReadError as e:
        logger.error("pdf_extract_failed", extra={"error_type": type(e).__name__})
        raise


async def _call_claude(text: str, client: anthropic.Anthropic) -> ParsedResume:
    user_message = (
        f"Extract the resume data from the following text.\n\n"
        f"Schema:\n{RESUME_JSON_SCHEMA}\n\n"
        f"Resume text:\n{text}"
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=PARSE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("claude_response_not_json", extra={"error_type": type(e).__name__})
        raise ValueError("Claude returned non-JSON response") from e

    return ParsedResume.model_validate(data)
