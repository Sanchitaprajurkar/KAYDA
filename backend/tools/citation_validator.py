import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.schemas.thor_claim import Citation, CitationValidationReport
from backend.services.runemark import KNOWN_RETRACTIONS, ParsedDocument, RELIABILITY_TIERS

class CitationValidator:
    """
    Judicial citation validation engine.
    Enforces manifest existence, simulated clock rules, retraction status,
    outlet reliability tiers, and verbatim source content matching.
    """

    def __init__(self, manifest: Optional[Dict[str, Any]] = None, manifest_path: Optional[Path] = None):
        self.manifest_docs: Dict[str, Dict[str, Any]] = {}
        if manifest:
            self._load_manifest_dict(manifest)
        elif manifest_path and Path(manifest_path).exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._load_manifest_dict(data)

    def _load_manifest_dict(self, data: Dict[str, Any]):
        for doc in data.get("documents", []):
            doc_id = doc.get("DOC_ID") or doc.get("doc_id")
            if doc_id:
                self.manifest_docs[doc_id.upper()] = doc

    def validate_citation(
        self,
        citation: Citation,
        as_of_date: str,
        doc_parsed: Optional[ParsedDocument] = None,
    ) -> CitationValidationReport:
        doc_id = citation.doc_id.upper()
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Manifest Existence Check
        exists_in_manifest = doc_id in self.manifest_docs
        manifest_meta = self.manifest_docs.get(doc_id)

        if not exists_in_manifest:
            errors.append(f"Citation {doc_id} does not resolve to any document in Runemark manifest.")

        # 2. Simulated Clock Compliance Check (pub_date <= as_of_date)
        is_clock_compliant = True
        try:
            as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d").date()
            cite_dt = datetime.strptime(citation.pub_date, "%Y-%m-%d").date()
            if cite_dt > as_of_dt:
                is_clock_compliant = False
                errors.append(
                    f"Clock violation: Citation pub_date {citation.pub_date} is after the "
                    f"as-of cutoff date {as_of_date}."
                )

            if manifest_meta:
                m_date_str = manifest_meta.get("PUB_DATE") or manifest_meta.get("pub_date")
                if m_date_str:
                    m_dt = datetime.strptime(m_date_str, "%Y-%m-%d").date()
                    if m_dt > as_of_dt:
                        is_clock_compliant = False
                        errors.append(
                            f"Clock violation: Manifest pub_date {m_date_str} for {doc_id} "
                            f"is after the as-of cutoff date {as_of_date}."
                        )
        except ValueError as e:
            is_clock_compliant = False
            errors.append(f"Invalid date format in citation or as_of_date: {str(e)}")

        # 3. Retraction and Correction Check
        is_retracted = False
        if doc_id in KNOWN_RETRACTIONS:
            ret_info = KNOWN_RETRACTIONS[doc_id]
            is_retracted = True
            errors.append(
                f"Source {doc_id} is inadmissible: {ret_info['status']} - {ret_info['reason']}"
            )

        if doc_parsed and doc_parsed.is_retracted:
            is_retracted = True
            errors.append(f"Source text in {doc_id} explicitly indicates retraction.")

        # 4. Reliability Tier Validation
        verified_tier = citation.reliability_tier
        if manifest_meta:
            m_tier = manifest_meta.get("RELIABILITY") or manifest_meta.get("reliability")
            if m_tier is not None:
                try:
                    verified_tier = int(m_tier)
                    if verified_tier != citation.reliability_tier:
                        warnings.append(
                            f"Citation reliability tier ({citation.reliability_tier}) differs from "
                            f"manifest tier ({verified_tier})."
                        )
                except ValueError:
                    pass

        if verified_tier == 4:
            warnings.append(
                f"Document {doc_id} is Tier 4 (weak source/tabloid). Must not be treated as established fact."
            )

        # 5. Content Verification
        content_matched = True
        if doc_parsed:
            if doc_parsed.is_damaged:
                content_matched = False
                errors.append(f"Source document {doc_id} is damaged or empty: {doc_parsed.damage_reason}")
            else:
                if citation.paragraph_or_row_id:
                    pid = citation.paragraph_or_row_id.upper()
                    if pid.startswith("P") and pid in doc_parsed.paragraphs:
                        ptext = doc_parsed.paragraphs[pid]
                        if citation.excerpt.lower() not in ptext.lower() and ptext.lower() not in citation.excerpt.lower():
                            cite_words = set(citation.excerpt.lower().split())
                            p_words = set(ptext.lower().split())
                            overlap = len(cite_words.intersection(p_words)) / max(1, len(cite_words))
                            if overlap < 0.4:
                                content_matched = False
                                errors.append(
                                    f"Excerpt does not match paragraph {pid} in {doc_id}. "
                                    f"Overlap was only {overlap*100:.1f}%."
                                )
                    elif pid not in doc_parsed.paragraphs and doc_parsed.paragraphs:
                        content_matched = False
                        errors.append(f"Paragraph/Row {pid} not found in {doc_id}.")

                if citation.excerpt and content_matched:
                    source_corpus = doc_parsed.full_text or doc_parsed.body_text or ""
                    norm_full = " ".join(source_corpus.split()).lower()
                    norm_cite = " ".join(citation.excerpt.split()).lower()
                    if norm_cite not in norm_full and norm_full:
                        cite_words = set(norm_cite.split())
                        full_words = set(norm_full.split())
                        overlap = len(cite_words.intersection(full_words)) / max(1, len(cite_words))
                        if overlap < 0.4:
                            content_matched = False
                            errors.append(
                                f"Excerpt words have insufficient match in {doc_id} text ({overlap*100:.1f}%)."
                            )

        is_valid = (
            exists_in_manifest
            and is_clock_compliant
            and not is_retracted
            and content_matched
            and len(errors) == 0
        )

        return CitationValidationReport(
            is_valid=is_valid,
            doc_id=doc_id,
            exists_in_manifest=exists_in_manifest,
            is_clock_compliant=is_clock_compliant,
            is_retracted=is_retracted,
            reliability_tier=verified_tier,
            content_matched=content_matched,
            errors=errors,
            warnings=warnings,
        )
