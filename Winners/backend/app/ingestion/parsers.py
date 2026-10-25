import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple, List
import pypdf

from app.models.document import DocumentMetadata, ParsedDocument

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(your|all|previous)\s+rules", re.IGNORECASE),
    re.compile(r"disregard\s+(the|all|previous)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a\s+different\s+agent", re.IGNORECASE),
    re.compile(r"system\s*:\s*override", re.IGNORECASE),
]

def parse_header_block(raw_text: str) -> Tuple[dict, str]:
    """
    Extracts the standard Runemark key-value header block up to the '---' line.
    """
    meta_dict = {}
    lines = raw_text.splitlines()
    body_start_idx = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "---":
            body_start_idx = i + 1
            break
        if ":" in stripped:
            parts = stripped.split(":", 1)
            key = parts[0].strip().upper()
            val = parts[1].strip()
            meta_dict[key] = val
            
    body_text = "\n".join(lines[body_start_idx:]).strip()
    return meta_dict, body_text

def parse_txt_file(file_path: Path) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def parse_pdf_file(file_path: Path) -> str:
    try:
        reader = pypdf.PdfReader(str(file_path))
        text_parts = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_parts.append(extracted)
        return "\n".join(text_parts)
    except Exception as e:
        return f"ERROR_DAMAGED_PDF: Could not read {file_path.name}: {str(e)}"

def parse_docx_file(file_path: Path) -> str:
    try:
        with zipfile.ZipFile(str(file_path)) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            
            # Namespace for WordprocessingML
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            
            for p in tree.iter(f"{{{ns['w']}}}p"):
                texts = [node.text for node in p.iter(f"{{{ns['w']}}}t") if node.text]
                if texts:
                    paragraphs.append("".join(texts))
            return "\n".join(paragraphs)
    except Exception as e:
        return f"ERROR_DAMAGED_DOCX: Could not read {file_path.name}: {str(e)}"

def check_for_prompt_injection(text: str) -> Tuple[bool, Optional[str]]:
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, f"Found injection phrase: '{match.group(0)}'"
    return False, None

def parse_document(file_path: Path, manifest_entry: Optional[dict] = None) -> ParsedDocument:
    """
    Parses any Runemark document (.txt, .pdf, .docx), enforces metadata validation,
    extracts paragraphs [P1], [P2], etc., and sanitizes against prompt injections.
    """
    ext = file_path.suffix.lower()
    if ext == ".txt":
        raw_text = parse_txt_file(file_path)
    elif ext == ".pdf":
        raw_text = parse_pdf_file(file_path)
    elif ext == ".docx":
        raw_text = parse_docx_file(file_path)
    else:
        raw_text = parse_txt_file(file_path)
        
    extracted_meta, body = parse_header_block(raw_text)
    
    # Merge with manifest entry if available (manifest provides verified defaults)
    merged = {}
    if manifest_entry:
        merged.update(manifest_entry)
    merged.update(extracted_meta)
    
    # Fallback doc_id from filename if not in header
    doc_id = merged.get("DOC_ID", file_path.stem)
    title = merged.get("TITLE", file_path.stem)
    source_name = merged.get("SOURCE_NAME", "Unknown Outlet")
    source_type = merged.get("SOURCE_TYPE", "news")
    
    reliability = 2
    try:
        reliability = int(merged.get("RELIABILITY", 2))
    except (ValueError, TypeError):
        reliability = 2
        
    pub_date = merged.get("PUB_DATE", "2024-01-01")
    pub_time = merged.get("PUB_TIME", "00:00")
    country = merged.get("COUNTRY", "general")
    sector = merged.get("SECTOR", "general")
    language = merged.get("LANGUAGE", "en")
    fmt = merged.get("FORMAT", ext.replace(".", "").upper())
    
    metadata = DocumentMetadata(
        DOC_ID=doc_id,
        EVENT_ID=merged.get("EVENT_ID", "NONE"),
        TITLE=title,
        SOURCE_NAME=source_name,
        SOURCE_TYPE=source_type,
        RELIABILITY=reliability,
        PUB_DATE=pub_date,
        PUB_TIME=pub_time,
        COUNTRY=country,
        SECTOR=sector,
        LANGUAGE=language,
        FORMAT=fmt,
        file=file_path.name
    )
    
    # Check for prompt injection
    has_inj, inj_details = check_for_prompt_injection(body)
    
    # Extract paragraph blocks ([P1], [P2] etc)
    paragraphs = []
    p_splits = re.split(r"\[P\d+\]", body)
    for p in p_splits:
        p_clean = p.strip()
        if p_clean:
            paragraphs.append(p_clean)
            
    if not paragraphs and body.strip():
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        
    words = len(body.split())
    
    return ParsedDocument(
        metadata=metadata,
        content=body if body else raw_text,
        paragraphs=paragraphs,
        word_count=words,
        has_injection_attempt=has_inj,
        injection_details=inj_details
    )
