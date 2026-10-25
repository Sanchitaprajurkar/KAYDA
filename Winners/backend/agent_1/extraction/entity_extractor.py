"""Extracts and resolves Runemark entities linked to paragraph citations."""

import json
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

import openai
from agent_1.config import settings
from agent_1.models.document import ParsedDocument, ParagraphRef
from agent_1.models.evidence import ExtractedEntity, EntityType


class RawExtractedEntity(BaseModel):
    name: str = Field(description="Canonical entity name e.g. 'Midgard', 'Wheat'")
    type: str = Field(description="One of: NATION, PORT, COMMODITY, AGREEMENT, CORRIDOR, ORGANIZATION, PERSON, INFRASTRUCTURE")
    aliases: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    paragraph_indices: List[int] = Field(default_factory=list)


class EntityExtractionResponse(BaseModel):
    entities: List[RawExtractedEntity] = Field(default_factory=list)


class EntityExtractor:
    """Extracts domain entities from documents with citation links."""

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
    ) -> List[ExtractedEntity]:
        paragraphs_to_process = doc.paragraphs[:max_paragraphs] if max_paragraphs else doc.paragraphs
        if not paragraphs_to_process:
            return []

        formatted_paras = [f"¶{p.paragraph_index}: {p.raw_text}" for p in paragraphs_to_process]
        text_block = "\n\n".join(formatted_paras)

        prompt = f"""You are Heimdall, extracting domain entities for the Runemark intelligence trial.
Document ID: {doc.doc_id}

Text:
{text_block}

Task:
Extract key entities (NATIONS, PORTS, COMMODITIES, AGREEMENTS, CORRIDORS, INFRASTRUCTURE, ORGANIZATIONS).
For each entity, list all 1-indexed paragraph numbers where it is mentioned.
"""

        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an entity extraction system returning structured Runemark domain entities."},
                    {"role": "user", "content": prompt},
                ],
                response_format=EntityExtractionResponse,
                temperature=0.0,
            )
            raw_response = completion.choices[0].message.parsed
        except Exception:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON adhering to {'entities': [{'name': str, 'type': str, 'aliases': [str], 'description': str, 'paragraph_indices': [int]}]}"},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            data = json.loads(response.choices[0].message.content or "{}")
            raw_response = EntityExtractionResponse.model_validate(data)

        results: List[ExtractedEntity] = []
        for raw in raw_response.entities:
            # Resolve entity type
            type_str = raw.type.upper()
            try:
                etype = EntityType(type_str)
            except ValueError:
                etype = EntityType.ORGANIZATION

            # Build source refs
            refs: List[ParagraphRef] = []
            for p_idx in raw.paragraph_indices:
                p_obj = doc.get_paragraph(p_idx)
                page = p_obj.page_number if p_obj else None
                snippet = (p_obj.raw_text[:120] + "...") if p_obj else None
                refs.append(
                    ParagraphRef(
                        doc_id=doc.doc_id,
                        file_name=doc.file_name,
                        page_number=page,
                        paragraph_index=p_idx,
                        text_snippet=snippet,
                    )
                )

            results.append(
                ExtractedEntity(
                    name=raw.name,
                    type=etype,
                    aliases=raw.aliases,
                    description=raw.description,
                    mentions_count=max(len(raw.paragraph_indices), 1),
                    source_refs=refs,
                )
            )

        return results
