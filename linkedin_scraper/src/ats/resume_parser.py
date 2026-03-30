"""
Resume parser for PDF and DOCX files.
Extracts raw text and parses into structured ParsedResume data.
"""

import re
import uuid
from typing import List, Optional, Dict

from .models import ParsedResume, ContactInfo, WorkExperience, Education


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file using pdfplumber (preferred) or PyPDF2 fallback."""
    text = ""
    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception:
        try:
            import PyPDF2
            import io
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {e}")

    if not text.strip():
        raise ValueError("No text could be extracted from the PDF. It may be image-based.")
    return text.strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        import docx
        import io
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
    except Exception as e:
        raise ValueError(f"Failed to extract text from DOCX: {e}")

    if not text.strip():
        raise ValueError("No text could be extracted from the DOCX file.")
    return text.strip()


# ---------------------------------------------------------------------------
# Section Detection
# ---------------------------------------------------------------------------

# Common resume section headers (case-insensitive)
SECTION_PATTERNS = {
    "summary": r"(?i)^(?:summary|professional\s+summary|profile|about\s+me|objective|career\s+objective|career\s+summary)\s*:?\s*$",
    "experience": r"(?i)^(?:experience|work\s+experience|professional\s+experience|employment|employment\s+history|work\s+history)\s*:?\s*$",
    "education": r"(?i)^(?:education|academic|academics|educational\s+background|academic\s+background)\s*:?\s*$",
    "skills": r"(?i)^(?:skills|technical\s+skills|core\s+skills|competencies|core\s+competencies|technologies|tech\s+stack|areas\s+of\s+expertise)\s*:?\s*$",
    "certifications": r"(?i)^(?:certifications?|licenses?\s*(?:&|and)?\s*certifications?|professional\s+certifications?|credentials)\s*:?\s*$",
    "projects": r"(?i)^(?:projects|key\s+projects|selected\s+projects|personal\s+projects)\s*:?\s*$",
}


def extract_sections(raw_text: str) -> Dict[str, str]:
    """Split resume text into labeled sections based on header detection."""
    lines = raw_text.split("\n")
    sections: Dict[str, str] = {}
    current_section = "header"
    current_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_lines.append("")
            continue

        matched = False
        for section_name, pattern in SECTION_PATTERNS.items():
            if re.match(pattern, stripped):
                # Save previous section
                if current_lines:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = section_name
                current_lines = []
                matched = True
                break

        if not matched:
            current_lines.append(line)

    # Save last section
    if current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


# ---------------------------------------------------------------------------
# Field Extraction
# ---------------------------------------------------------------------------

def extract_contact_info(text: str) -> ContactInfo:
    """Extract contact information from resume text (typically the header)."""
    email_match = re.search(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b", text)
    phone_match = re.search(
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
    )
    linkedin_match = re.search(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?", text
    )

    # Name is usually the first non-empty line
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    name = None
    if lines:
        first_line = lines[0]
        # Heuristic: name is a short line without @ or common non-name patterns
        if len(first_line) < 60 and "@" not in first_line and not re.match(r"^\d", first_line):
            name = first_line

    # Location heuristic: look for city, state patterns
    location_match = re.search(
        r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2}(?:\s+\d{5})?)\b", text
    )

    return ContactInfo(
        name=name,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0) if phone_match else None,
        linkedin_url=linkedin_match.group(0) if linkedin_match else None,
        location=location_match.group(1) if location_match else None,
    )


def extract_work_experience(section_text: str) -> List[WorkExperience]:
    """Parse work experience section into structured entries."""
    experiences = []
    if not section_text:
        return experiences

    # Split into entries by looking for patterns like "Title at Company" or "Company - Title"
    # or lines that look like date ranges
    entries = re.split(
        r"\n(?=(?:[A-Z][^\n]*(?:\d{4}|present|current)))",
        section_text,
        flags=re.IGNORECASE,
    )

    for entry in entries:
        entry = entry.strip()
        if not entry or len(entry) < 10:
            continue

        lines = [l.strip() for l in entry.split("\n") if l.strip()]
        if not lines:
            continue

        # First line is typically title/company
        title_line = lines[0]
        company = ""
        title = title_line

        # Try to split "Title at Company" or "Title | Company" or "Title - Company"
        for sep in [" at ", " | ", " - ", " — ", ", "]:
            if sep in title_line:
                parts = title_line.split(sep, 1)
                title = parts[0].strip()
                company = parts[1].strip()
                break

        # If company wasn't found and there's a second line, it might be the company
        if not company and len(lines) > 1:
            second = lines[1]
            # If second line is short and doesn't look like a bullet point
            if len(second) < 80 and not second.startswith(("•", "-", "●", "*")):
                company = second

        # Extract date range
        date_pattern = r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\w.]*\s+\d{4}|(?:\d{1,2}/\d{4})|(?:\d{4}))"
        dates = re.findall(date_pattern, entry, re.IGNORECASE)
        start_date = dates[0] if dates else None
        end_date = dates[1] if len(dates) > 1 else None

        # Check for "Present" or "Current"
        if re.search(r"\b(?:present|current|now)\b", entry, re.IGNORECASE):
            if not end_date:
                end_date = "Present"

        # Remaining lines are description
        desc_lines = []
        for line in lines[1:]:
            if line.startswith(("•", "-", "●", "*", "–")):
                desc_lines.append(line)
            elif len(line) > 30:  # likely a description line
                desc_lines.append(line)

        experiences.append(
            WorkExperience(
                title=title,
                company=company or "Unknown",
                start_date=start_date,
                end_date=end_date,
                description="\n".join(desc_lines) if desc_lines else None,
                skills_used=[],
            )
        )

    return experiences


def extract_education(section_text: str) -> List[Education]:
    """Parse education section into structured entries."""
    education_list = []
    if not section_text:
        return education_list

    # Split on lines that look like institution names (often contain University, College, etc.)
    entries = re.split(
        r"\n(?=.*(?:University|College|Institute|School|Academy|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|Ph\.?D|MBA|Bachelor|Master|Doctor))",
        section_text,
        flags=re.IGNORECASE,
    )

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        lines = [l.strip() for l in entry.split("\n") if l.strip()]
        if not lines:
            continue

        institution = lines[0]
        degree = None
        field = None
        grad_date = None
        gpa = None

        for line in lines:
            # Degree detection
            degree_match = re.search(
                r"(Bachelor|Master|Doctor|Ph\.?D|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|MBA|Associate)[\w\s.]*(?:of|in)?\s*([\w\s,&]+)?",
                line,
                re.IGNORECASE,
            )
            if degree_match:
                degree = degree_match.group(1).strip()
                if degree_match.group(2):
                    field = degree_match.group(2).strip().rstrip(",.")

            # Date detection
            date_match = re.search(r"(\d{4})", line)
            if date_match:
                grad_date = date_match.group(1)

            # GPA detection
            gpa_match = re.search(r"(?:GPA|gpa)[:\s]*(\d+\.?\d*)\s*/?\s*(\d+\.?\d*)?", line)
            if gpa_match:
                gpa = gpa_match.group(1)
                if gpa_match.group(2):
                    gpa = f"{gpa}/{gpa_match.group(2)}"

        education_list.append(
            Education(
                degree=degree,
                field_of_study=field,
                institution=institution,
                graduation_date=grad_date,
                gpa=gpa,
            )
        )

    return education_list


def extract_certifications(section_text: str) -> List[str]:
    """Extract certification names from the certifications section."""
    if not section_text:
        return []

    certs = []
    for line in section_text.split("\n"):
        line = line.strip().lstrip("•-●*–  ")
        if line and len(line) > 3:
            certs.append(line)
    return certs


# ---------------------------------------------------------------------------
# Main Parse Function
# ---------------------------------------------------------------------------

async def parse_resume(filename: str, file_bytes: bytes) -> ParsedResume:
    """Parse an uploaded resume file into structured data."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        raw_text = extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        raw_text = extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Please upload a PDF or DOCX file.")

    # Extract sections
    sections = extract_sections(raw_text)

    # Parse each section
    header_text = sections.get("header", raw_text[:500])
    contact_info = extract_contact_info(header_text)

    summary = sections.get("summary")

    work_experience = extract_work_experience(sections.get("experience", ""))

    education = extract_education(sections.get("education", ""))

    certifications = extract_certifications(sections.get("certifications", ""))

    # Skills are extracted separately by skill_extractor module
    # Here we just grab raw skill lines if a skills section exists
    raw_skills = []
    skills_text = sections.get("skills", "")
    if skills_text:
        for line in skills_text.split("\n"):
            line = line.strip().lstrip("•-●*–  ")
            if line:
                # Split on common delimiters
                for skill in re.split(r"[,;|•·]", line):
                    skill = skill.strip()
                    if skill and len(skill) > 1:
                        raw_skills.append(skill)

    resume_id = str(uuid.uuid4())

    return ParsedResume(
        resume_id=resume_id,
        filename=filename,
        contact_info=contact_info,
        summary=summary,
        skills=raw_skills,
        work_experience=work_experience,
        education=education,
        certifications=certifications,
        raw_text=raw_text,
        parse_method="rule_based",
    )
