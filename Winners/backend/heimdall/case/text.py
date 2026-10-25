"""Tokenising helpers shared by case understanding, retrieval and analysis."""

import re
import unicodedata
from typing import List, Set

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "also", "am", "an", "and", "any", "are", "as",
    "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "give", "had",
    "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "may", "me", "more", "most", "much", "must", "my", "no", "nor", "not", "now",
    "of", "off", "on", "once", "only", "or", "other", "our", "out", "over", "own", "per", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your", "said",
    "says", "say", "low", "high", "range", "exposed", "exposure", "as of",
}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = (t.replace("‘", "'").replace("’", "'").replace("“", '"')
          .replace("”", '"').replace("–", "-").replace("—", "-"))
    return re.sub(r"\s+", " ", t).strip().lower()


def stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ied", "es", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> List[str]:
    return [stem(w) for w in re.findall(r"[a-z][a-z0-9]+", norm(text)) if w not in STOPWORDS and w not in MONTHS]


def token_set(text: str) -> Set[str]:
    return set(tokens(text))


def contains_term(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term.lower())}s?\b", norm(text)) is not None
