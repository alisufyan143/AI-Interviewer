"""Resume parser using Gemini for intelligent extraction from any format."""

import logging
from pathlib import Path
from google import genai
from google.genai import types
from app.config import settings
from app.services.model_manager import model_manager

logger = logging.getLogger(__name__)

class ResumeParser:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = model_manager.get_model("parsing")

RESUME_PARSE_PROMPT = """You are a professional resume parser. Analyze the uploaded resume and extract the following information in a structured format.

Return a JSON object with these fields:
{
    "raw_text": "Full plain text content of the resume, preserving structure",
    "candidate_name": "Full name",
    "email": "Email address if found",
    "phone": "Phone number if found",
    "location": "City/Country if found",
    "summary": "Professional summary or objective (2-3 sentences)",
    "skills": ["skill1", "skill2", ...],
    "experience": [
        {
            "title": "Job Title",
            "company": "Company Name",
            "duration": "Start - End",
            "description": "Brief description of role"
        }
    ],
    "education": [
        {
            "degree": "Degree name",
            "institution": "University/School",
            "year": "Graduation year"
        }
    ],
    "certifications": ["cert1", "cert2"],
    "total_years_experience": 0
}

Be thorough. If a field is not found in the resume, use null or empty array.
Return ONLY the JSON object, no markdown formatting or code blocks."""


async def parse_resume(file_path: Path) -> dict:
    """Parse a resume file using Gemini's multimodal capabilities.
    
    Supports PDF, DOCX, PNG, JPG formats.
    Falls back to basic text extraction if Gemini fails.
    """
    import json

    suffix = file_path.suffix.lower()

    parser = ResumeParser()
    model_id = parser.model_id
    client = parser.client

    # For DOCX files, extract text first then send as text
    if suffix in [".docx", ".doc"]:
        text = _extract_docx_text(file_path)
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=[
                f"{RESUME_PARSE_PROMPT}\n\nResume content:\n{text}"
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
    elif suffix == ".pdf":
        # Try text extraction first, use Gemini for parsing
        text = _extract_pdf_text(file_path)
        if text and len(text.strip()) > 50:
            response = await client.aio.models.generate_content(
                model=model_id,
                contents=[
                    f"{RESUME_PARSE_PROMPT}\n\nResume content:\n{text}"
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
        else:
            # Scanned PDF — upload file directly for vision
            uploaded_file = await client.aio.files.upload(file=file_path)
            response = await client.aio.models.generate_content(
                model=model_id,
                contents=[RESUME_PARSE_PROMPT, uploaded_file],
            )
    elif suffix in [".png", ".jpg", ".jpeg"]:
        # Image resume — upload directly
        uploaded_file = await client.aio.files.upload(file=file_path)
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=[RESUME_PARSE_PROMPT, uploaded_file],
        )
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    # Parse the response
    response_text = response.text.strip()

    # Clean potential markdown code block wrapping
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        # If Gemini returns non-JSON, wrap it
        parsed = {"raw_text": response_text}

    # Ensure raw_text exists
    if "raw_text" not in parsed or not parsed["raw_text"]:
        if suffix in [".pdf"]:
            parsed["raw_text"] = _extract_pdf_text(file_path)
        elif suffix in [".docx", ".doc"]:
            parsed["raw_text"] = _extract_docx_text(file_path)
        else:
            parsed["raw_text"] = response_text

    return parsed


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(file_path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception:
        return ""


def _extract_docx_text(file_path: Path) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document

        doc = Document(str(file_path))
        text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        return text.strip()
    except Exception:
        return ""
