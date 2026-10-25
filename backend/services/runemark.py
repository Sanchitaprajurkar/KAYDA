import json
import logging
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# ============================================================
# RUNEMARK PATHS & CONFIGURATION
# ============================================================

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEV_PACK_PATH = WORKSPACE_ROOT / "03_Ragnarok Trial of the Nine Realms" / "dev_pack_E5"
DOCS_DIR = DEV_PACK_PATH / "docs"
MANIFEST_PATH = DEV_PACK_PATH / "manifest.json"
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"

DEFAULT_AS_OF_DATE = "2027-01-25"

RELIABILITY_TIERS = {
    1: "Official (Canal and Government notices)",
    2: "Reputable Wire, Business Daily, and Trade Press",
    3: "Regional Paper and Analyst Firms",
    4: "Social Posts, Tabloids, and Blogs",
}

KNOWN_RETRACTIONS = {
    "WLD-0024": {
        "status": "RETRACTED",
        "reason": "Prior bulletin suggesting resumption of corridor talks withdrawn by editorial desk.",
    },
    "ORV-0043": {
        "status": "SUPERSEDED_BY_CORRECTION",
        "superseded_by": "ORV-0013",
        "reason": "Corrected by ORV-0013: corridor agreement was not renewed.",
    },
    "ORV-0015": {
        "status": "TAINTED_EVIDENCE",
        "depends_on": "ORV-0043",
        "retracted_by": "ORV-0013",
        "reason": "Tainted evidence: accepted unconfirmed early wire report subsequently retracted by ORV-0013.",
    },
}

# ============================================================
# MULTI-FORMAT DOCUMENT MODEL & PARSER
# ============================================================

class ParsedDocument(BaseModel):
    doc_id: str
    file_path: str
    format: str
    event_id: str = "NONE"
    title: str = ""
    source_name: str = ""
    source_type: str = "unknown"
    reliability: int = 4
    pub_date: str = "1970-01-01"
    pub_time: Optional[str] = None
    country: str = "general"
    sector: str = "general"
    resolved_sector: str = "general"
    has_sector_mismatch: bool = False
    mismatch_note: Optional[str] = None
    language: str = "en"
    header_raw: str = ""
    body_text: str = ""
    full_text: str = ""
    paragraphs: Dict[str, str] = Field(default_factory=dict)
    is_damaged: bool = False
    damage_reason: Optional[str] = None
    is_retracted: bool = False

class DocumentParser:
    """
    Robust multi-format parser for Runemark corpus (TXT, PDF, DOCX).
    Handles mixed encodings, BOM markers, damaged files, and corrupted headers gracefully.
    """

    @classmethod
    def parse_file(cls, file_path: Path) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            return ParsedDocument(
                doc_id=path.stem,
                file_path=str(path),
                format="UNKNOWN",
                is_damaged=True,
                damage_reason=f"File does not exist: {path.name}",
            )

        file_size = path.stat().st_size
        doc_id = path.stem.split(".")[0]
        ext = path.suffix.lower()

        # Handle 0-byte or empty damaged files
        if file_size == 0:
            return ParsedDocument(
                doc_id=doc_id,
                file_path=str(path),
                format=ext.replace(".", "").upper(),
                is_damaged=True,
                damage_reason="File is completely empty (0 bytes)",
            )

        try:
            if ext == ".txt":
                raw_text = cls._read_txt_tolerant(path)
            elif ext == ".docx":
                raw_text = cls._read_docx(path)
            elif ext == ".pdf":
                raw_text = cls._read_pdf(path)
            else:
                raw_text = cls._read_txt_tolerant(path)
        except Exception as e:
            return ParsedDocument(
                doc_id=doc_id,
                file_path=str(path),
                format=ext.replace(".", "").upper(),
                is_damaged=True,
                damage_reason=f"Failed to read file contents: {str(e)}",
            )

        if not raw_text or len(raw_text.strip()) == 0:
            return ParsedDocument(
                doc_id=doc_id,
                file_path=str(path),
                format=ext.replace(".", "").upper(),
                is_damaged=True,
                damage_reason="Document contains no readable text",
            )

        return cls._parse_text_content(doc_id, str(path), ext.replace(".", "").upper(), raw_text)

    @classmethod
    def _read_txt_tolerant(cls, path: Path) -> str:
        with open(path, "rb") as f:
            b = f.read()

        # Check for mixed encoding with split at '---' or UTF-16 BOM
        if b"---" in b:
            parts = b.split(b"---", 1)
            header_bytes = parts[0]
            body_bytes = parts[1]

            header_text = header_bytes.decode("utf-8", errors="ignore")
            if body_bytes.startswith(b"\n\xff\xfe") or body_bytes.startswith(b"\r\n\xff\xfe"):
                bom_idx = body_bytes.find(b"\xff\xfe")
                body_text = body_bytes[bom_idx + 2:].decode("utf-16-le", errors="ignore")
            elif body_bytes.startswith(b"\xff\xfe"):
                body_text = body_bytes[2:].decode("utf-16-le", errors="ignore")
            elif b"\x00" in body_bytes:
                try:
                    body_text = body_bytes.decode("utf-16-le", errors="ignore")
                except Exception:
                    body_text = body_bytes.replace(b"\x00", b"").decode("utf-8", errors="ignore")
            else:
                body_text = body_bytes.decode("utf-8", errors="ignore")

            return f"{header_text}\n---\n{body_text}"

        # Standard file decoding fallback chain
        for enc in ["utf-8", "utf-16", "utf-16-le", "latin-1", "cp1252"]:
            try:
                text = b.decode(enc)
                if "\x00" in text:
                    text = text.replace("\x00", "")
                return text
            except Exception:
                continue

        return b.decode("utf-8", errors="ignore").replace("\x00", "")

    @classmethod
    def _read_docx(cls, path: Path) -> str:
        with zipfile.ZipFile(path) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            texts = []
            for node in tree.iter():
                if node.tag.endswith("t"):
                    if node.text:
                        texts.append(node.text)
                elif node.tag.endswith("p"):
                    texts.append("\n")
            return "".join(texts)

    @classmethod
    def _read_pdf(cls, path: Path) -> str:
        try:
            import pymupdf
            doc = pymupdf.open(path)
            pages_text = [page.get_text() for page in doc]
            return "\n".join(pages_text)
        except ImportError:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages_text)

    @classmethod
    def _parse_text_content(cls, doc_id: str, file_path: str, fmt: str, text: str) -> ParsedDocument:
        header_text = ""
        body_text = text

        if "---" in text:
            parts = text.split("---", 1)
            header_text = parts[0].strip()
            body_text = parts[1].strip()

        meta = cls._extract_metadata(header_text or text, doc_id)

        # Extract structured paragraphs [P1], [P2], etc.
        paragraphs: Dict[str, str] = {}
        p_matches = list(re.finditer(r"\[(P\d+)\]\s*(.*?)(?=\[(?:P\d+)\]|\Z)", body_text, re.DOTALL))
        for m in p_matches:
            pid = m.group(1)
            ptext = re.sub(r"\s+", " ", m.group(2)).strip()
            paragraphs[pid] = ptext

        is_retracted = "RETRACTED" in text.upper() or "RETRACTION" in text.upper()
        meta_sector = meta.get("SECTOR", "general")
        title = meta.get("TITLE", "")
        resolved_sector = meta_sector
        has_sector_mismatch = False
        mismatch_note = None

        # Check for sector mismatch between header metadata and actual title/body (e.g. ORV-0029 & ORV-0030)
        t_low = title.lower()
        b_low = body_text[:250].lower()
        if "maize" in t_low or "maize" in b_low:
            if meta_sector.lower() != "maize":
                has_sector_mismatch = True
                resolved_sector = "Maize"
                mismatch_note = f"Metadata labels sector as {meta_sector}, but title/body specifies Maize."
        elif "wheat" in t_low or "wheat" in b_low:
            if meta_sector.lower() != "wheat" and meta_sector.lower() != "general":
                has_sector_mismatch = True
                resolved_sector = "Wheat"
                mismatch_note = f"Metadata labels sector as {meta_sector}, but title/body specifies Wheat."

        return ParsedDocument(
            doc_id=meta.get("DOC_ID", doc_id),
            file_path=file_path,
            format=fmt,
            event_id=meta.get("EVENT_ID", "NONE"),
            title=title,
            source_name=meta.get("SOURCE_NAME", ""),
            source_type=meta.get("SOURCE_TYPE", "unknown").lower(),
            reliability=int(meta.get("RELIABILITY", 4)),
            pub_date=meta.get("PUB_DATE", "1970-01-01"),
            pub_time=meta.get("PUB_TIME"),
            country=meta.get("COUNTRY", "general"),
            sector=meta_sector,
            resolved_sector=resolved_sector,
            has_sector_mismatch=has_sector_mismatch,
            mismatch_note=mismatch_note,
            language=meta.get("LANGUAGE", "en"),
            header_raw=header_text,
            body_text=body_text,
            full_text=text,
            paragraphs=paragraphs,
            is_damaged=False,
            is_retracted=is_retracted,
        )

    @classmethod
    def _extract_metadata(cls, text: str, fallback_doc_id: str) -> Dict[str, str]:
        meta = {"DOC_ID": fallback_doc_id, "RELIABILITY": "4"}
        patterns = {
            "DOC_ID": r"DOC_ID:\s*([^\r\n]+)",
            "EVENT_ID": r"EVENT_ID:\s*([^\r\n]+)",
            "TITLE": r"TITLE:\s*([^\r\n]+)",
            "SOURCE_NAME": r"SOURCE_NAME:\s*([^\r\n]+)",
            "SOURCE_TYPE": r"SOURCE_TYPE:\s*([^\r\n]+)",
            "RELIABILITY": r"RELIABILITY:\s*([1-4])",
            "PUB_DATE": r"PUB_DATE:\s*(\d{4}-\d{2}-\d{2})",
            "PUB_TIME": r"PUB_TIME:\s*([^\r\n]+)",
            "COUNTRY": r"COUNTRY:\s*([^\r\n]+)",
            "SECTOR": r"SECTOR:\s*([^\r\n]+)",
            "LANGUAGE": r"LANGUAGE:\s*([^\r\n]+)",
        }
        for key, pat in patterns.items():
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                meta[key] = m.group(1).strip()
        return meta

# ============================================================
# STRUCTURED JSON OBSERVERS & LOGGERS
# ============================================================

class StructuredThorLogger:
    """
    Structured JSON logger for Thor providing complete judicial observability (NFR4).
    Logs all events into backend/logs/thor.jsonl.
    """

    def __init__(self, log_dir: Optional[Path] = None, logger_name: str = "ThorLogger"):
        self.log_dir = log_dir or LOGS_DIR
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        self.in_memory_records: List[Dict[str, Any]] = []

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self.log_dir / "thor.jsonl"
            handler = logging.FileHandler(str(log_file), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def log_event(self, event_type: str, payload: Dict[str, Any]):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "THOR",
            "event_type": event_type,
            "data": payload,
        }
        self.in_memory_records.append(record)
        msg = json.dumps(record, ensure_ascii=False)
        self.logger.info(msg)

    def log_case_ingested(self, case_id: str, question: str, as_of_date: str, countries: List[str], sectors: List[str], gaps: List[str]):
        self.log_event("CASE_FILE_INGESTED", {
            "case_id": case_id,
            "investigation_question": question,
            "as_of_date": as_of_date,
            "countries": countries,
            "sectors": sectors,
            "coverage_gaps_count": len(gaps),
            "coverage_gaps": gaps,
        })

    def log_search(self, query: str, filters: Dict[str, Any], retrieved_docs: List[str]):
        self.log_event("SEARCH_EXECUTED", {
            "query": query,
            "filters": filters,
            "result_count": len(retrieved_docs),
            "retrieved_doc_ids": retrieved_docs,
        })

    def log_trade_calculation(self, country: str, sector: str, result: Dict[str, Any]):
        self.log_event("TRADE_CALCULATION_EXECUTED", {
            "country": country,
            "sector": sector,
            "baseline_value_usd_m": result.get("baseline_value_usd_m"),
            "disrupted_value_usd_m": result.get("disrupted_value_usd_m"),
            "gross_loss_usd_m": result.get("gross_value_loss_usd_m"),
            "net_loss_usd_m": result.get("net_value_loss_usd_m"),
            "high_bound_usd_m": result.get("high_exposure_bound_usd_m"),
            "low_bound_usd_m": result.get("low_exposure_bound_usd_m"),
            "source_row_ids": result.get("source_row_ids"),
            "damaged_rows_reported": result.get("damaged_rows_reported"),
        })

    def log_claim(self, claim_id: str, country: str, sector: str, statement: str, bounds: str, classification: str, citations: List[str]):
        self.log_event("CLAIM_GENERATED", {
            "claim_id": claim_id,
            "country": country,
            "sector": sector,
            "statement": statement,
            "bounds": bounds,
            "classification": classification,
            "citations": citations,
        })

    def log_evidence_gap(self, country: str, sector: str, reason: str):
        self.log_event("EVIDENCE_GAP_RECORDED", {
            "country": country,
            "sector": sector,
            "status": "EVIDENCE_GAP",
            "gap_reason": reason,
            "action": "Range fabrication strictly prohibited; gap returned explicitly.",
        })

    def log_attack(self, attack_id: str, target_claim_id: str, reason: str, argument: str, counter_evidence: List[str]):
        self.log_event("CROSS_EXAM_ATTACK_LAUNCHED", {
            "attack_id": attack_id,
            "target_claim_id": target_claim_id,
            "reason": reason,
            "argument": argument,
            "counter_evidence": counter_evidence,
        })

    def log_response(self, response_id: str, attack_id: str, claim_id: str, decision: str, justification: str, defence_evidence: List[str]):
        self.log_event("CROSS_EXAM_RESPONSE_DELIVERED", {
            "response_id": response_id,
            "attack_id": attack_id,
            "claim_id": claim_id,
            "decision": decision,
            "justification": justification,
            "defence_evidence": defence_evidence,
        })

    def log_memory(self, action: str, key: str, decision_influence: str):
        self.log_event("MEMORY_INTERACTION", {
            "action": action,
            "key": key,
            "decision_influence": decision_influence,
        })

    def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if not event_type:
            return self.in_memory_records
        return [r for r in self.in_memory_records if r["event_type"] == event_type]
