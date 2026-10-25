"""Extracts granular facts and trade intelligence from parsed documents."""

import json
from typing import List, Optional
from pydantic import BaseModel, Field

import openai
from heimdall.config import settings
from heimdall.models.document import ParsedDocument, ParagraphRef
from heimdall.models.evidence import ExtractedFact, FactCategory


class RawExtractedFact(BaseModel):
    """Schema for LLM structured fact extraction."""
    paragraph_index: int = Field(description="1-indexed paragraph where the fact appears")
    category: str = Field(description="One of: TRADE_VOLUME, TARIFF_OR_PRICE, ROUTE_STATUS, TREATY_OR_AGREEMENT, GEOPOLITICAL_EVENT, GRAIN_OR_INVENTORY, DISRUPTION_STATUS, RETRACTION_NOTICE, OTHER")
    subject: str = Field(description="Key subject of the fact e.g. 'Orvan Grain Corridor', 'Midgard Wheat'")
    statement: str = Field(description="Self-contained concise factual assertion")
    date_mentioned: Optional[str] = Field(default=None, description="Any explicit date mentioned in the assertion")
    numeric_value: Optional[float] = Field(default=None, description="Extracted numerical metric value if present")
    unit: Optional[str] = Field(default=None, description="Unit of measurement e.g. 'MT', 'tonnes', '%', 'gold marks'")
    verbatim_quote: str = Field(description="Verbatim sentence or phrase from the paragraph")


class FactExtractionResponse(BaseModel):
    """Container for batch LLM fact extraction."""
    facts: List[RawExtractedFact] = Field(default_factory=list)


class FactExtractor:
    """Extracts facts from parsed documents using OpenAI LLM with exact paragraph citations."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.OPENAI_MODEL
        self._client: Optional[openai.OpenAI] = None

    @property
    def client(self) -> openai.OpenAI:
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not configured.")
            self._client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def extract_from_document(
        self,
        doc: ParsedDocument,
        max_paragraphs: Optional[int] = None,
    ) -> List[ExtractedFact]:
        """Extract facts with paragraph citations from a ParsedDocument."""
        paragraphs_to_process = doc.paragraphs[:max_paragraphs] if max_paragraphs else doc.paragraphs
        if not paragraphs_to_process:
            return []

        # Prepare formatted prompt text with paragraph indices
        formatted_paras = []
        for p in paragraphs_to_process:
            page_info = f" [p.{p.page_number}]" if p.page_number else ""
            formatted_paras.append(f"¶{p.paragraph_index}{page_info}: {p.raw_text}")

        text_block = "\n\n".join(formatted_paras)

        prompt = f"""You are Heimdall, the rigorous evidence-intake intelligence agent for the Trial of the Nine Realms.
Document ID: {doc.doc_id}
Document Title: {doc.manifest_meta.title if doc.manifest_meta else doc.file_name}
Source: {doc.manifest_meta.source_name if doc.manifest_meta else 'Unknown'}
Published Date: {doc.manifest_meta.pub_date if doc.manifest_meta else 'Unknown'}

Document Paragraphs:
{text_block}

Task:
Extract all concrete, verifiable facts, trade metrics (wheat, maize, tonnages, prices, tariffs), corridor transit statuses, treaty terms, and disruption events.
Every fact MUST reference the exact 1-indexed paragraph_index (¶X) where it originates, and include the exact verbatim quote.
Classify the category into: TRADE_VOLUME, TARIFF_OR_PRICE, ROUTE_STATUS, TREATY_OR_AGREEMENT, GEOPOLITICAL_EVENT, GRAIN_OR_INVENTORY, DISRUPTION_STATUS, RETRACTION_NOTICE, OTHER.
"""

        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a meticulous intelligence analyst extracting sourced facts with paragraph-level citations."},
                    {"role": "user", "content": prompt},
                ],
                response_format=FactExtractionResponse,
                temperature=0.0,
            )
            raw_response = completion.choices[0].message.parsed
        except Exception:
            # Fallback to standard chat completion with JSON mode
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an intelligence analyst. Return valid JSON adhering to: {'facts': [{'paragraph_index': int, 'category': str, 'subject': str, 'statement': str, 'date_mentioned': str, 'numeric_value': float, 'unit': str, 'verbatim_quote': str}]}"},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            data = json.loads(response.choices[0].message.content or "{}")
            raw_response = FactExtractionResponse.model_validate(data)

        # Convert to ExtractedFact domain models with complete provenance
        reliability_tier = doc.manifest_meta.reliability_tier if doc.manifest_meta else 2
        is_as_of_valid = doc.manifest_meta.is_valid_as_of(settings.AS_OF_DATE) if doc.manifest_meta else True

        results: List[ExtractedFact] = []
        for raw in raw_response.facts:
            # Match paragraph reference
            p_obj = doc.get_paragraph(raw.paragraph_index)
            page_num = p_obj.page_number if p_obj else None

            source_ref = ParagraphRef(
                doc_id=doc.doc_id,
                file_name=doc.file_name,
                page_number=page_num,
                paragraph_index=raw.paragraph_index,
                text_snippet=raw.verbatim_quote,
            )

            # Map category
            cat_name = raw.category.upper()
            try:
                cat = FactCategory(cat_name)
            except ValueError:
                cat = FactCategory.OTHER

            results.append(
                ExtractedFact(
                    category=cat,
                    subject=raw.subject,
                    statement=raw.statement,
                    date_mentioned=raw.date_mentioned,
                    numeric_value=raw.numeric_value,
                    unit=raw.unit,
                    source_ref=source_ref,
                    reliability_tier=reliability_tier,
                    is_as_of_valid=is_as_of_valid,
                    confidence=0.95 if reliability_tier in [1, 2] else 0.75,
                )
            )

        return results
