"""Extracts granular facts and trade intelligence from parsed documents.

Hallucination control runs in four layers:
  1. LLM extraction      - conservative prompt; every fact carries a paragraph index and verbatim quote.
  2. Citation validation - Python checks the paragraph exists and the quote really appears in it
                           (repairing the index when the quote is found in a different paragraph),
                           and that numbers and dates are actually stated in the source.
  3. Semantic validation - a second LLM pass checks the statement is supported by the cited paragraph
                           (modality, attribution, tense, values) and fixes the assertion status.
  4. Evidence status     - each fact ends VERIFIED, UNCERTAIN or REJECTED; only VERIFIED facts are
                           returned as accepted evidence, the rest are kept separately for review.
"""

import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Literal, Optional, Set, Tuple, Type, TypeVar

import openai
from pydantic import BaseModel, Field, field_validator

from agent_1.config import settings
from agent_1.models.document import DocumentParagraph, ParagraphRef, ParsedDocument
from agent_1.models.evidence import AssertionStatus, EvidenceStatus, ExtractedFact, FactCategory

T = TypeVar("T", bound=BaseModel)

# Minimum fraction of the quote's words that must appear, in order, in a source sentence
FUZZY_QUOTE_THRESHOLD = 0.90
# Facts per semantic-verification call
VERIFY_BATCH_SIZE = 25


class RawExtractedFact(BaseModel):
    """Schema for LLM structured fact extraction."""
    paragraph_index: int = Field(description="The ¶ number of the paragraph containing the quote (NOT the document's own [Pn] label)")
    category: FactCategory = Field(description="Fact classification")
    subject: str = Field(description="Key subject of the fact e.g. 'Orvan Grain Corridor', 'Midgard Wheat'")
    statement: str = Field(description="Self-contained factual assertion that preserves the source's attribution, modality and tense")
    assertion_status: AssertionStatus = Field(description="How the source frames the claim")
    date_mentioned: Optional[str] = Field(default=None, description="Date exactly as written in the quote, or null")
    numeric_value: Optional[float] = Field(default=None, description="Number explicitly written in the quote, or null; never calculated")
    unit: Optional[str] = Field(default=None, description="Unit exactly as written e.g. 'MT', 'tonnes', '%', 'gold marks'")
    verbatim_quote: str = Field(description="Exact contiguous text copied character-for-character from that one paragraph")

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, v):
        try:
            return FactCategory(str(v).strip().upper())
        except ValueError:
            return FactCategory.OTHER

    @field_validator("assertion_status", mode="before")
    @classmethod
    def _coerce_assertion(cls, v):
        try:
            return AssertionStatus(str(v).strip().upper())
        except ValueError:
            return AssertionStatus.REPORTED


class FactExtractionResponse(BaseModel):
    """Container for batch LLM fact extraction."""
    facts: List[RawExtractedFact] = Field(default_factory=list)


class FactVerdict(BaseModel):
    """Semantic verification verdict for one candidate fact."""
    fact_number: int = Field(description="The [n] number of the candidate being judged")
    verdict: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED"]
    assertion_status: AssertionStatus = Field(description="Correct framing of the claim according to the paragraph")
    issues: List[str] = Field(default_factory=list, description="Specific problems found; empty if fully supported")

    @field_validator("assertion_status", mode="before")
    @classmethod
    def _coerce_assertion(cls, v):
        try:
            return AssertionStatus(str(v).strip().upper())
        except ValueError:
            return AssertionStatus.REPORTED


class VerificationResponse(BaseModel):
    """Container for batch semantic verification."""
    verdicts: List[FactVerdict] = Field(default_factory=list)


class FactExtractionResult(BaseModel):
    """Validated extraction output, split by evidence status."""
    accepted: List[ExtractedFact] = Field(default_factory=list, description="VERIFIED facts only")
    flagged: List[ExtractedFact] = Field(default_factory=list, description="UNCERTAIN and REJECTED facts, kept for review")


EXTRACTION_SYSTEM_PROMPT = (
    "You are a meticulous, conservative intelligence analyst extracting sourced facts with paragraph-level citations. "
    "You never infer, embellish or invent; if something is not explicitly written in the text, you do not extract it."
)

EXTRACTION_RULES = """Extraction rules (mandatory):
1. Extract only information explicitly stated in the supplied paragraphs. Never infer missing facts or invent dates, quantities, entities or events.
2. verbatim_quote must be a contiguous span copied character-for-character from ONE paragraph. Do not paraphrase, merge sentences, or fix grammar. If a claim cannot be supported by an exact quotation, do not extract it.
3. paragraph_index is the ¶ number shown before each paragraph. Some paragraphs also contain their own "[P1]", "[P2]"... labels; those are NOT the paragraph_index. Always use the ¶ number.
4. Preserve how the source frames the claim, both in the statement wording and in assertion_status:
   - CONFIRMED: stated as fact or officially confirmed
   - REPORTED: reported by or attributed to someone ("X said", "according to")
   - ALLEGED / DENIED / RUMOURED: claimed, denied, or unattributed speculation
   - PROJECTED: forecasts, expectations, plans, or announced future actions ("will", "would", "expects", "from 20 January")
   - PROPOSED: proposals or drafts not yet adopted
   - CORRECTED / RETRACTED: correction or retraction notices
5. Do not convert a prediction, plan, announcement or proposal into an event that already happened. "Shipments would be suspended from 20 January" is PROJECTED, not "shipments were suspended".
6. Keep attribution in the statement ("Vantro Trading says...", "Orvan authorities announced..."). Do not upgrade a party's claim into an established fact.
7. Do not treat a correction or retraction as confirmation of the original claim. Extract the correction itself, with category RETRACTION_NOTICE where applicable.
8. numeric_value must be a number explicitly written in the quote. Never calculate, convert, sum or estimate values. Leave null if absent.
9. date_mentioned must be copied as written in the quote. Never resolve relative dates ("yesterday", "next week") and never use the publication date as a substitute. Leave null if absent.
10. Ignore document metadata header lines (DOC_ID, EVENT_ID, SOURCE_NAME, RELIABILITY, PUB_DATE, etc.); they are not facts.
11. When unsure whether something qualifies, leave it out."""

VERIFIER_SYSTEM_PROMPT = (
    "You are a strict fact-checking auditor. You judge whether extracted statements are fully supported by their cited "
    "source paragraph. You give no benefit of the doubt."
)

VERIFIER_RULES = """For each candidate, compare the extracted fields against the SOURCE PARAGRAPH only (no outside knowledge).

verdict:
- SUPPORTED: every element (subject, statement, date, number, unit) is explicitly stated in the paragraph, and the statement keeps the paragraph's attribution, modality and tense.
- PARTIALLY_SUPPORTED: the core is in the paragraph but something is overstated, missing a qualifier, loses attribution, or adds detail not in the text.
- NOT_SUPPORTED: the paragraph does not say this, contradicts it, or the number/date is wrong.

Treat these as at most PARTIALLY_SUPPORTED, or NOT_SUPPORTED if the meaning changes:
- a plan, forecast, expectation or announced future action stated as something that already happened
- a party's claim, allegation or report stated as established fact
- a correction or retraction treated as confirming the original claim
- a numeric value or date that is not written in the paragraph, or was calculated
- hedges ("may", "about", "up to", "partial") dropped from the statement

assertion_status: give the correct framing according to the paragraph (CONFIRMED, REPORTED, ALLEGED, DENIED, RUMOURED, PROJECTED, PROPOSED, CORRECTED, RETRACTED).
issues: list each specific problem briefly. Return exactly one verdict per candidate."""


# ---------------------------------------------------------------------------
# Text helpers for citation validation
# ---------------------------------------------------------------------------

_PARA_LABEL_RE = re.compile(r"^\s*\[P\d+\]\s*")
_NUM_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?:st|nd|rd|th)?"
    r"\s*(per cent|percent|%|thousand|million|billion|bn|mn|k|m)?(?![A-Za-z])",
    re.IGNORECASE,
)
_SCALES = {"thousand": 1e3, "k": 1e3, "million": 1e6, "mn": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9}
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "hundred": 100, "dozen": 12, "half": 0.5,
}
_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _normalize(text: str) -> str:
    """Normalize unicode, quotes, dashes and whitespace for tolerant comparison."""
    text = unicodedata.normalize("NFKC", text or "")
    text = (text.replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))
    return re.sub(r"\s+", " ", text).strip().lower()


def _clean_quote(quote: str) -> str:
    """Normalize a quote and strip wrapping quote marks, ellipses and trailing punctuation."""
    q = _normalize(quote)
    q = q.strip("\"' ")
    q = re.sub(r"^(\.\.\.|…)\s*|\s*(\.\.\.|…)$", "", q)
    return q.rstrip(".,;: ").strip("\"' ")


def _strip_label(text: str) -> str:
    return _PARA_LABEL_RE.sub("", text or "")


def _sentences(text: str) -> List[str]:
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    # Include adjacent pairs so quotes spanning a sentence boundary can still match
    return parts + [f"{a} {b}" for a, b in zip(parts, parts[1:])]


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+(?:[.,'][a-z0-9]+)*", text)


def _coverage(quote_words: List[str], candidate_words: List[str]) -> float:
    """Fraction of the quote's words found in order within the candidate."""
    if not quote_words:
        return 0.0
    blocks = SequenceMatcher(None, quote_words, candidate_words, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks) / len(quote_words)


def _best_fuzzy(quote_norm: str, paragraph_text: str) -> Tuple[float, Optional[str]]:
    """Best fuzzy match of a quote against the sentences of a paragraph."""
    best_score, best_span = 0.0, None
    quote_words = _words(quote_norm)
    for sent in _sentences(_strip_label(paragraph_text)):
        sent_words = _words(_normalize(sent))
        # Penalize candidates shorter than the quote (quote padded with words the source doesn't have)
        length_ratio = min(1.0, len(sent_words) / max(1, len(quote_words)))
        score = _coverage(quote_words, sent_words) * (0.5 + 0.5 * length_ratio)
        if score > best_score:
            best_score, best_span = score, sent
    return best_score, best_span


def _numbers_in(text: str) -> Set[float]:
    """All numeric values written in a text, including scaled forms ('1.2 million' -> 1.2 and 1200000)."""
    values: Set[float] = set()
    for m in _NUM_RE.finditer(_strip_label(text)):
        base = float(m.group(1).replace(",", "") + (f".{m.group(2)}" if m.group(2) else ""))
        values.add(base)
        scale = (m.group(3) or "").lower()
        if scale in _SCALES:
            values.add(base * _SCALES[scale])
    for word in re.findall(r"[a-z]+", _normalize(text)):
        if word in _NUMBER_WORDS:
            values.add(float(_NUMBER_WORDS[word]))
    return values


def _value_in(value: float, values: Set[float]) -> bool:
    return any(math.isclose(value, v, rel_tol=1e-6, abs_tol=1e-9) for v in values)


def _date_support(date_str: str, paragraph_text: str) -> Tuple[int, int]:
    """Return (tokens found, tokens checked) for the month/weekday/number tokens of a date."""
    para_norm = _normalize(_strip_label(paragraph_text))
    para_numbers = _numbers_in(paragraph_text)
    checks: List[bool] = []

    iso = re.fullmatch(r"\s*(\d{4})-(\d{1,2})(?:-(\d{1,2}))?\s*", date_str)
    if iso:
        year, month, day = iso.groups()
        checks.append(_value_in(float(year), para_numbers))
        if 1 <= int(month) <= 12:
            name = _MONTHS[int(month) - 1]
            checks.append(name in para_norm or name[:3] in para_norm or _value_in(float(month), para_numbers))
        if day:
            checks.append(_value_in(float(day), para_numbers))
        return sum(checks), len(checks)

    for token in re.findall(r"[A-Za-z]+|\d+", date_str):
        tok = token.lower()
        if tok.isdigit():
            checks.append(_value_in(float(tok), para_numbers))
        elif any(tok == m or (len(tok) >= 3 and m.startswith(tok)) for m in _MONTHS + _WEEKDAYS):
            full = next(m for m in _MONTHS + _WEEKDAYS if tok == m or m.startswith(tok))
            checks.append(full in para_norm or full[:3] in para_norm)
    return sum(checks), len(checks)


class _Candidate:
    """Working state for one fact as it moves through the validation layers."""

    def __init__(self, raw: RawExtractedFact):
        self.raw = raw
        self.paragraph: Optional[DocumentParagraph] = None
        self.snippet: str = raw.verbatim_quote
        self.assertion_status: AssertionStatus = raw.assertion_status
        self.confidence: float = 1.0
        self.reject: List[str] = []
        self.uncertain: List[str] = []
        self.notes: List[str] = []

    @property
    def status(self) -> EvidenceStatus:
        if self.reject:
            return EvidenceStatus.REJECTED
        if self.uncertain:
            return EvidenceStatus.UNCERTAIN
        return EvidenceStatus.VERIFIED


class FactExtractor:
    """Extracts facts from parsed documents using OpenAI LLM with validated paragraph citations."""

    def __init__(self, model_name: Optional[str] = None, verify_semantics: bool = True):
        self.model_name = model_name or settings.OPENAI_MODEL
        self.verify_semantics = verify_semantics
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
        """Extract facts and return only those that passed every validation layer (VERIFIED)."""
        return self.extract_with_review(doc, max_paragraphs).accepted

    def extract_with_review(
        self,
        doc: ParsedDocument,
        max_paragraphs: Optional[int] = None,
    ) -> FactExtractionResult:
        """Extract facts and return them split into accepted (VERIFIED) and flagged (UNCERTAIN/REJECTED)."""
        paragraphs = doc.paragraphs[:max_paragraphs] if max_paragraphs else doc.paragraphs
        if not paragraphs:
            return FactExtractionResult()

        # Layer 1: LLM extraction
        raw_facts = self._llm_extract(doc, paragraphs)
        candidates = self._dedupe([_Candidate(raw) for raw in raw_facts])

        # Layer 2: citation, numeric and date validation (deterministic)
        for cand in candidates:
            self._validate_citation(cand, paragraphs)
            if not cand.reject:
                self._validate_values(cand)

        # Layer 3: semantic verification of facts that survived citation checks
        to_verify = [c for c in candidates if not c.reject]
        if self.verify_semantics:
            for i in range(0, len(to_verify), VERIFY_BATCH_SIZE):
                self._verify_semantics(to_verify[i:i + VERIFY_BATCH_SIZE])
        else:
            for cand in to_verify:
                cand.uncertain.append("Semantic verification disabled; statement not checked against paragraph meaning")

        # Layer 4: evidence status assignment
        reliability_tier = doc.manifest_meta.reliability_tier if doc.manifest_meta else 2
        is_as_of_valid = doc.manifest_meta.is_valid_as_of(settings.AS_OF_DATE) if doc.manifest_meta else True

        result = FactExtractionResult()
        for cand in candidates:
            fact = self._to_fact(cand, doc, reliability_tier, is_as_of_valid)
            (result.accepted if fact.evidence_status == EvidenceStatus.VERIFIED else result.flagged).append(fact)
        return result

    # -- Layer 1 -------------------------------------------------------------

    def _llm_extract(self, doc: ParsedDocument, paragraphs: List[DocumentParagraph]) -> List[RawExtractedFact]:
        formatted_paras = []
        for p in paragraphs:
            page_info = f" [page {p.page_number}]" if p.page_number else ""
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
Extract concrete, verifiable facts: trade metrics (wheat, maize, tonnages, prices, tariffs), corridor transit statuses, treaty terms, and disruption events.
Every fact MUST reference the ¶ paragraph_index where it originates and include the exact verbatim quote.
Classify the category into: TRADE_VOLUME, TARIFF_OR_PRICE, ROUTE_STATUS, TREATY_OR_AGREEMENT, GEOPOLITICAL_EVENT, GRAIN_OR_INVENTORY, DISRUPTION_STATUS, RETRACTION_NOTICE, OTHER.

{EXTRACTION_RULES}
"""
        response = self._parse(EXTRACTION_SYSTEM_PROMPT, prompt, FactExtractionResponse)
        return response.facts

    @staticmethod
    def _dedupe(candidates: List[_Candidate]) -> List[_Candidate]:
        seen = set()
        unique = []
        for c in candidates:
            key = (_normalize(c.raw.statement), _clean_quote(c.raw.verbatim_quote))
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    # -- Layer 2 -------------------------------------------------------------

    def _validate_citation(self, cand: _Candidate, paragraphs: List[DocumentParagraph]) -> None:
        """Check the cited paragraph exists and contains the quote; repair the index if the quote is elsewhere."""
        quote_norm = _clean_quote(cand.raw.verbatim_quote)
        by_index = {p.paragraph_index: p for p in paragraphs}
        cited = by_index.get(cand.raw.paragraph_index)

        if not quote_norm:
            cand.reject.append("Empty verbatim quote")
            cand.paragraph = cited
            return
        if cited is None:
            cand.notes.append(f"Cited ¶{cand.raw.paragraph_index} does not exist in document")

        # Exact (normalized) match: cited paragraph first, then nearest other paragraph
        if cited is not None and quote_norm in _normalize(cited.raw_text):
            cand.paragraph = cited
            return
        exact_hits = [p for p in paragraphs if quote_norm in _normalize(p.raw_text)]
        if exact_hits:
            hit = min(exact_hits, key=lambda p: abs(p.paragraph_index - cand.raw.paragraph_index))
            cand.paragraph = hit
            cand.confidence *= 0.95
            cand.notes.append(f"Citation repaired: quote found in ¶{hit.paragraph_index}, not cited ¶{cand.raw.paragraph_index}")
            if len(exact_hits) > 1:
                cand.notes.append(f"Quote appears in {len(exact_hits)} paragraphs; nearest chosen")
            return

        # Fuzzy match at sentence level: cited paragraph first, then best elsewhere
        best_p, best_score, best_span = None, 0.0, None
        if cited is not None:
            best_score, best_span = _best_fuzzy(quote_norm, cited.raw_text)
            best_p = cited
        if best_score < FUZZY_QUOTE_THRESHOLD:
            for p in paragraphs:
                score, span = _best_fuzzy(quote_norm, p.raw_text)
                if score > best_score:
                    best_p, best_score, best_span = p, score, span

        if best_p is not None and best_score >= FUZZY_QUOTE_THRESHOLD:
            cand.paragraph = best_p
            cand.snippet = best_span or cand.snippet
            cand.confidence *= 0.85 * best_score
            cand.notes.append(f"Quote not verbatim ({best_score:.0%} match); replaced with source text from ¶{best_p.paragraph_index}")
            if best_p.paragraph_index != cand.raw.paragraph_index:
                cand.notes.append(f"Citation repaired: ¶{cand.raw.paragraph_index} -> ¶{best_p.paragraph_index}")
            return

        cand.paragraph = cited
        cand.reject.append(
            f"Quote not found in cited ¶{cand.raw.paragraph_index} or anywhere in the document (best match {best_score:.0%})"
        )

    def _validate_values(self, cand: _Candidate) -> None:
        """Check numeric values and dates are actually written in the quote / paragraph."""
        para_text = cand.paragraph.raw_text if cand.paragraph else ""

        if cand.raw.numeric_value is not None:
            value = cand.raw.numeric_value
            if _value_in(value, _numbers_in(cand.snippet)):
                pass
            elif _value_in(value, _numbers_in(para_text)):
                cand.uncertain.append(f"Numeric value {value:g} is in the paragraph but not in the quoted text")
                cand.confidence *= 0.7
            else:
                cand.reject.append(f"Numeric value {value:g} is not stated in the source paragraph (calculated or invented)")

        if cand.raw.date_mentioned:
            found, checked = _date_support(cand.raw.date_mentioned, para_text)
            if checked and found == 0:
                cand.reject.append(f"Date '{cand.raw.date_mentioned}' does not appear in the source paragraph")
            elif found < checked:
                cand.uncertain.append(f"Date '{cand.raw.date_mentioned}' only partially matches the source paragraph")
                cand.confidence *= 0.7

    # -- Layer 3 -------------------------------------------------------------

    def _verify_semantics(self, batch: List[_Candidate]) -> None:
        """Second LLM pass: judge each statement against its cited paragraph."""
        blocks = []
        for n, cand in enumerate(batch, start=1):
            r = cand.raw
            blocks.append(
                f"[{n}]\n"
                f"SOURCE PARAGRAPH: {cand.paragraph.raw_text if cand.paragraph else ''}\n"
                f"Subject: {r.subject}\n"
                f"Statement: {r.statement}\n"
                f"Claimed assertion_status: {r.assertion_status.value}\n"
                f"Date: {r.date_mentioned}\n"
                f"Numeric value: {r.numeric_value} {r.unit or ''}".rstrip()
            )
        prompt = f"{VERIFIER_RULES}\n\nCandidates:\n\n" + "\n\n".join(blocks)
        response = self._parse(VERIFIER_SYSTEM_PROMPT, prompt, VerificationResponse)

        verdicts = {v.fact_number: v for v in response.verdicts}
        for n, cand in enumerate(batch, start=1):
            v = verdicts.get(n)
            if v is None:
                cand.uncertain.append("No semantic verdict returned by verifier")
                cand.confidence *= 0.5
                continue
            issues = "; ".join(v.issues) if v.issues else ""
            if v.verdict == "NOT_SUPPORTED":
                cand.reject.append(f"Verifier: statement not supported by cited paragraph. {issues}".strip())
                cand.confidence *= 0.2
            elif v.verdict == "PARTIALLY_SUPPORTED":
                cand.uncertain.append(f"Verifier: statement only partially supported. {issues}".strip())
                cand.confidence *= 0.6
            elif issues:
                cand.notes.append(f"Verifier notes: {issues}")
            if v.assertion_status != cand.assertion_status:
                cand.notes.append(f"Assertion status corrected {cand.assertion_status.value} -> {v.assertion_status.value}")
                cand.assertion_status = v.assertion_status
                cand.confidence *= 0.9

    # -- Layer 4 -------------------------------------------------------------

    @staticmethod
    def _to_fact(cand: _Candidate, doc: ParsedDocument, reliability_tier: int, is_as_of_valid: bool) -> ExtractedFact:
        r = cand.raw
        para = cand.paragraph
        source_ref = ParagraphRef(
            doc_id=doc.doc_id,
            file_name=doc.file_name,
            page_number=para.page_number if para else None,
            paragraph_index=para.paragraph_index if para else r.paragraph_index,
            text_snippet=cand.snippet,
        )
        return ExtractedFact(
            category=r.category,
            subject=r.subject,
            statement=r.statement,
            date_mentioned=r.date_mentioned,
            numeric_value=r.numeric_value,
            unit=r.unit,
            source_ref=source_ref,
            reliability_tier=reliability_tier,
            is_as_of_valid=is_as_of_valid,
            confidence=0.0 if cand.reject else round(max(0.0, min(1.0, cand.confidence)), 2),
            assertion_status=cand.assertion_status,
            evidence_status=cand.status,
            validation_notes=cand.reject + cand.uncertain + cand.notes,
        )

    # -- LLM plumbing --------------------------------------------------------

    def _parse(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        """Structured-output call, falling back to JSON mode if the parse endpoint fails."""
        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=schema,
                temperature=0.0,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError(completion.choices[0].message.refusal or "Empty structured response")
            return parsed
        except Exception:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": f"{system_prompt}\nReturn only valid JSON matching this JSON schema:\n{json.dumps(schema.model_json_schema())}"},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            data = json.loads(response.choices[0].message.content or "{}")
            return schema.model_validate(data)
