import re
from typing import List, Optional, Union, Dict, Any
from app.ingestion.corpus import corpus

def parse_para_spec(para_spec: Union[int, str]) -> int:
    """Normalizes paragraph identifier (e.g. 'P1', 'p2', 3) to 1-based index."""
    if isinstance(para_spec, int):
        return para_spec
    s = str(para_spec).strip().upper()
    m = re.match(r"^P?(\d+)$", s)
    if m:
        return int(m.group(1))
    return 1

def read_doc(
    id: str,
    paras: Optional[List[Union[int, str]]] = None
) -> Dict[str, Any]:
    """
    Fetches specific document paragraphs or full document text from Runemark corpus.
    
    Args:
        id: Permanent Document ID, e.g. 'ORV-0009', 'ORV-0013', 'ATL-0001'
        paras: Optional list of paragraph identifiers to retrieve, e.g. [1, 2] or ['P1', 'P5'].
               If None or empty, returns all paragraphs.
               
    Returns:
        Structured document dictionary with metadata and extracted paragraph texts.
    """
    corpus.load_corpus()
    clean_id = id.strip().upper()
    doc = corpus.get_document(clean_id)

    if not doc:
        return {
            "status": "NOT_FOUND",
            "doc_id": clean_id,
            "error": f"Document '{clean_id}' not found in Runemark manifest or document directory.",
            "paragraphs": []
        }

    meta = doc.metadata
    all_paras = doc.paragraphs

    if not paras:
        # Return all paragraphs
        formatted_paras = [
            {"para_id": f"P{i+1}", "index": i + 1, "text": p}
            for i, p in enumerate(all_paras)
        ]
        return {
            "status": "SUCCESS",
            "doc_id": meta.DOC_ID,
            "title": meta.TITLE,
            "source_name": meta.SOURCE_NAME,
            "source_type": meta.SOURCE_TYPE,
            "reliability_tier": meta.RELIABILITY,
            "pub_date": meta.PUB_DATE,
            "pub_time": meta.PUB_TIME,
            "country": meta.COUNTRY,
            "sector": meta.SECTOR,
            "format": meta.FORMAT,
            "is_retracted": doc.is_retracted,
            "total_paragraphs": len(all_paras),
            "paragraphs": formatted_paras,
            "full_content": doc.content
        }

    # Extract requested paragraphs
    selected_paras = []
    missing_indices = []

    for spec in paras:
        idx = parse_para_spec(spec)
        # 1-indexed to 0-indexed
        list_idx = idx - 1
        if 0 <= list_idx < len(all_paras):
            selected_paras.append({
                "para_id": f"P{idx}",
                "index": idx,
                "text": all_paras[list_idx]
            })
        else:
            missing_indices.append(f"P{idx}")

    return {
        "status": "SUCCESS",
        "doc_id": meta.DOC_ID,
        "title": meta.TITLE,
        "source_name": meta.SOURCE_NAME,
        "reliability_tier": meta.RELIABILITY,
        "pub_date": meta.PUB_DATE,
        "country": meta.COUNTRY,
        "sector": meta.SECTOR,
        "format": meta.FORMAT,
        "is_retracted": doc.is_retracted,
        "requested_paragraphs": len(paras),
        "retrieved_paragraphs": len(selected_paras),
        "missing_paragraphs": missing_indices,
        "paragraphs": selected_paras,
        "extracted_text": "\n\n".join([f"[{p['para_id']}] {p['text']}" for p in selected_paras])
    }
