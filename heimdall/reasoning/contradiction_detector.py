"""Contradiction, correction, retraction, and missing information detection engine."""

import json
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

import openai
from heimdall.config import settings
from heimdall.models.document import ParsedDocument
from heimdall.models.evidence import (
    ExtractedFact,
    FactCategory,
    ContradictionItem,
    ConflictType,
    MissingInformation,
)


class RawContradictionItem(BaseModel):
    conflict_type: str = Field(description="One of: DIRECT_CONTRADICTION, CORRECTION, RETRACTION, TEMPORAL_UPDATE, NUMERICAL_DISCREPANCY, CREDIBILITY_CONFLICT")
    description: str
    fact_a_statement: Optional[str] = None
    fact_b_statement: Optional[str] = None
    resolution_rationale: str
    favored_side: Optional[str] = Field(default=None, description="'A', 'B', or 'NEITHER'")


class RawMissingInfoItem(BaseModel):
    topic: str
    expected_scope: str
    impact_on_assessment: str


class ContradictionAnalysisResponse(BaseModel):
    contradictions: List[RawContradictionItem] = Field(default_factory=list)
    missing_information: List[RawMissingInfoItem] = Field(default_factory=list)


class ContradictionDetector:
    """Compares independent documents to uncover contradictions, retractions, and intelligence gaps."""

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

    def compare_documents(
        self,
        doc_a: ParsedDocument,
        doc_b: ParsedDocument,
        facts_a: Optional[List[ExtractedFact]] = None,
        facts_b: Optional[List[ExtractedFact]] = None,
    ) -> Tuple[List[ContradictionItem], List[MissingInformation]]:
        """Perform cross-examination analysis between two separate documents."""
        # Meta info
        meta_a = doc_a.manifest_meta
        meta_b = doc_b.manifest_meta

        tier_a = meta_a.reliability_tier if meta_a else 2
        tier_b = meta_b.reliability_tier if meta_b else 2
        date_a = meta_a.pub_date if meta_a else "Unknown"
        date_b = meta_b.pub_date if meta_b else "Unknown"

        # Prepare text summaries or facts
        summary_a = "\n".join([f"¶{p.paragraph_index}: {p.raw_text}" for p in doc_a.paragraphs[:15]])
        summary_b = "\n".join([f"¶{p.paragraph_index}: {p.raw_text}" for p in doc_b.paragraphs[:15]])

        prompt = f"""You are Heimdall, conducting adversarial cross-document analysis for Trial of the Nine Realms.

Document A:
- ID: {doc_a.doc_id}
- Title: {meta_a.title if meta_a else doc_a.file_name}
- Source: {meta_a.source_name if meta_a else 'Unknown'} (Credibility Tier: {tier_a})
- Published: {date_a}
- Excerpt:
{summary_a}

Document B:
- ID: {doc_b.doc_id}
- Title: {meta_b.title if meta_b else doc_b.file_name}
- Source: {meta_b.source_name if meta_b else 'Unknown'} (Credibility Tier: {tier_b})
- Published: {date_b}
- Excerpt:
{summary_b}

Rules for Analysis:
1. Identify any DIRECT_CONTRADICTIONS (e.g. one claims corridor closed, another says operational).
2. Identify CORRECTIONS (e.g. later document rectifies earlier incorrect figures).
3. Identify RETRACTIONS (e.g. formal cancellation or retraction of previous article).
4. Identify TEMPORAL_UPDATES (e.g. an earlier agreement was valid until a later expiration event).
5. Identify NUMERICAL_DISCREPANCIES (e.g. differing tonnages for wheat/maize imports).
6. Note that Tier 1 (Official treaties/filings) strictly supersedes Tier 4 (Tabloid rumours).
7. Identify critical MISSING_INFORMATION required to judge commercial exposure of Midgard and Tolan.
"""

        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior judicial intelligence analyst detecting contradictions, retractions, and missing data."},
                    {"role": "user", "content": prompt},
                ],
                response_format=ContradictionAnalysisResponse,
                temperature=0.0,
            )
            raw_analysis = completion.choices[0].message.parsed
        except Exception:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return JSON adhering to ContradictionAnalysisResponse schema."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            data = json.loads(response.choices[0].message.content or "{}")
            raw_analysis = ContradictionAnalysisResponse.model_validate(data)

        # Convert to ContradictionItem objects
        contradictions: List[ContradictionItem] = []
        for raw in raw_analysis.contradictions:
            try:
                ctype = ConflictType(raw.conflict_type.upper())
            except ValueError:
                ctype = ConflictType.DIRECT_CONTRADICTION

            # Find matching facts if available
            f_a = next((f for f in (facts_a or []) if f.statement in (raw.fact_a_statement or "")), None)
            f_b = next((f for f in (facts_b or []) if f.statement in (raw.fact_b_statement or "")), None)

            # If no exact match, create synthetic fact proxies
            if not f_a and raw.fact_a_statement:
                f_a = ExtractedFact(
                    category=FactCategory.OTHER,
                    subject=doc_a.doc_id,
                    statement=raw.fact_a_statement,
                    source_ref=doc_a.make_citation(1),
                    reliability_tier=tier_a,
                )
            if not f_b and raw.fact_b_statement:
                f_b = ExtractedFact(
                    category=FactCategory.OTHER,
                    subject=doc_b.doc_id,
                    statement=raw.fact_b_statement,
                    source_ref=doc_b.make_citation(1),
                    reliability_tier=tier_b,
                )

            favored_id = None
            if raw.favored_side == "A" and f_a:
                favored_id = f_a.fact_id
            elif raw.favored_side == "B" and f_b:
                favored_id = f_b.fact_id

            contradictions.append(
                ContradictionItem(
                    conflict_type=ctype,
                    description=raw.description,
                    fact_a=f_a,
                    fact_b=f_b,
                    resolution_rationale=raw.resolution_rationale,
                    favored_fact_id=favored_id,
                )
            )

        missing_info: List[MissingInformation] = [
            MissingInformation(
                topic=m.topic,
                expected_scope=m.expected_scope,
                impact_on_assessment=m.impact_on_assessment,
            )
            for m in raw_analysis.missing_information
        ]

        return contradictions, missing_info
