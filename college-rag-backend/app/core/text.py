"""Text helpers shared by ingestion, retrieval, verification and the mock providers."""
from __future__ import annotations

import hashlib
import re
import unicodedata

# ----------------------------------------------------------------------------- tokens
try:  # optional, more accurate
    import tiktoken  # type: ignore

    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - depends on environment
    _ENC = None


def count_tokens(text: str) -> int:
    """Token estimate. Uses tiktoken when installed, otherwise a script-aware heuristic."""
    if not text:
        return 0
    if _ENC is not None:
        return len(_ENC.encode(text))
    words = len(text.split())
    non_ascii = sum(1 for c in text if ord(c) > 127)
    # Indic scripts tokenise to roughly 1 token per 1-2 chars; Latin ~4 chars/token.
    return max(int(words * 1.3), (len(text) - non_ascii) // 4 + non_ascii // 2)


# ----------------------------------------------------------------------------- sanitising
# Control chars (except \t \n \f \r), zero-width space, LRM/RLM and bidi overrides/isolates.
# ZWNJ/ZWJ (U+200C/U+200D) are deliberately kept: Indic scripts need them.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def strip_control(text: str) -> str:
    """Remove control / bidi-override characters, keeping newlines, tabs and ZWJ/ZWNJ."""
    return _CONTROL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))


_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|preceding)\s+(instructions|prompts|rules|messages)",
    r"disregard\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+",
    r"forget\s+(all\s+|your\s+)?(previous\s+)?instructions",
    r"\byou\s+are\s+now\b",
    r"\bact\s+as\s+(an?\s+)?(ai|assistant|system|developer)",
    r"\bsystem\s+(prompt|note|message|instruction)s?\s*:",
    r"\bnew\s+instructions?\s*:",
    r"\b(assistant|system|developer)\s*:\s",
    r"\breveal\s+(your|the)\s+(system\s+)?prompt",
    r"पिछले\s+(सभी\s+)?निर्देश(ों)?\s+(को\s+)?(अनदेखा|नज़रअंदाज़|भूल)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)
_TAG_RE = re.compile(r"</?\s*(source|context|question|system|instructions?|answer_language|english_question)\b[^>]*>", re.I)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))


def sanitize_untrusted(text: str) -> str:
    """Defence-in-depth for document text placed in prompts.

    1. strip control / bidi characters, 2. neutralise our own prompt delimiter tags,
    3. redact sentences that look like instructions aimed at the model.
    The system prompt additionally tells the model to treat context as data only.
    """
    text = strip_control(text)
    text = _TAG_RE.sub("", text)
    if not _INJECTION_RE.search(text):
        return text
    parts = re.split(r"(?<=[.!?।\n])\s+", text)
    return " ".join("[instruction-like text removed]" if _INJECTION_RE.search(p) else p for p in parts)


# ----------------------------------------------------------------------------- PII scrubbing
_PII_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[phone]"),  # Indian mobile
    (re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"), "[id-number]"),  # Aadhaar-like
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[id-number]"),  # PAN
]


def scrub_pii(text: str) -> str:
    for pat, repl in _PII_PATTERNS:
        text = pat.sub(repl, text)
    return text


# ----------------------------------------------------------------------------- numerals
def normalize_digits(text: str) -> str:
    """Map every Unicode decimal digit (Devanagari, Bengali, Tamil, Telugu, Kannada, ...) to ASCII."""
    out = []
    for ch in text:
        if ch.isdigit() and not ("0" <= ch <= "9"):
            try:
                out.append(str(unicodedata.digit(ch)))
                continue
            except (TypeError, ValueError):
                pass
        out.append(ch)
    return "".join(out)


# ----------------------------------------------------------------------------- terms
_WORD_RE = re.compile(r"[\w\u0900-\u0DFF]+(?:[.\-'][\w]+)*", re.UNICODE)

EN_STOPWORDS = frozenset(
    """a an the is are was were be been being am do does did of in on at to for from by with about as into
    and or but if then than so that this these those it its i me my we our you your he she they them their
    what which who whom whose when where why how can could should would will shall may might must
    there here any some all each every no not only also please tell know want need get give
    much many more most such very just there's what's whats per have has had having
    college university institute bennett""".split()
)

_SOFT_QUERY_STOPWORDS = frozenset(
    """detail details information info available offer offered offering offers provide provided provides
    list name names named explain describe summary overview regarding related under between through
    visit visiting come coming take taken make made total number count different various major main
    top best key kind kinds type types option options""".split()
)

_SYNONYM_CLUSTERS: tuple[frozenset[str], ...] = (
    frozenset({"program", "programme", "cours", "degre", "branch", "stream", "curriculum"}),
    frozenset({"ai", "artificial", "intelligenc"}),
    frozenset({"cse", "computer"}),
    frozenset({"ece", "electronic", "vlsi"}),
    frozenset({"recruiter", "placement", "compani", "employer", "job", "hiring", "career", "packag"}),
    frozenset({"hangout", "cafeteria", "food", "canteen", "cafe", "dining", "mess", "eat", "outlet", "restaurant"}),
    frozenset({"found", "founder", "establish", "start", "launch", "creator", "owner"}),
    frozenset({"contact", "phon", "mobil", "helplin", "call", "whatsapp", "email", "mail", "toll", "18001038484"}),
    frozenset({"noida", "locat", "addres", "situat", "city", "state"}),
    frozenset({"capacit", "accommodat", "seat", "intak", "strength"}),
    frozenset({"acr", "siz", "area", "sprawling", "big", "spread"}),
    frozenset({"fest", "festival", "event", "cultural", "uphoria", "zenevia", "bluemoon", "sportikon", "converg"}),
    frozenset({"vc", "vice", "chancellor"}),
    frozenset({"dean", "head", "hod", "leadership", "expert"}),
    frozenset({"hostel", "dorm", "residenc", "residential", "boarding", "room"}),
    frozenset({"sport", "game", "athletic", "court", "ground", "arena", "gym", "fitnes"}),
    frozenset({"librari", "book", "koha", "opac", "reading"}),
    frozenset({"startup", "hatcheri", "incubat", "entrepreneur", "entrepreneurship", "ventur", "seed"}),
    frozenset({"accredit", "accreditation", "naac", "ugc", "approv", "recognis", "recognition", "iso", "ranking"}),
    frozenset({"global", "international", "abroad", "foreign", "oversea", "exchange", "mobility", "pathway"}),
)

_SYNONYM_MAP: dict[str, frozenset[str]] = {}
for _cluster in _SYNONYM_CLUSTERS:
    for _term in _cluster:
        _SYNONYM_MAP[_term] = _SYNONYM_MAP.get(_term, frozenset()) | _cluster


def stem(word: str) -> str:
    w = word.lower()
    if not w.isascii() or len(w) <= 3:
        return w
    for suf, rep in (("ings", ""), ("ing", ""), ("ies", "y"), ("es", ""), ("s", ""), ("ed", ""), ("e", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + rep
    return w


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(normalize_digits(text))]


def content_terms(text: str, stopwords: frozenset[str] = EN_STOPWORDS) -> list[str]:
    """Lower-cased, stemmed, stop-word-free terms (order preserved, de-duplicated)."""
    seen: dict[str, None] = {}
    soft: dict[str, None] = {}
    for tok in tokenize(text):
        if tok in stopwords or (len(tok) < 2 and not tok.isdigit()):
            continue
        st = stem(tok)
        if tok in _SOFT_QUERY_STOPWORDS or st in _SOFT_QUERY_STOPWORDS:
            soft.setdefault(st, None)
        else:
            seen.setdefault(st, None)
    return list(seen) if seen else list(soft)


def expand_synonyms(terms: set[str] | list[str]) -> set[str]:
    out = set(terms)
    for t in list(out):
        if t in _SYNONYM_MAP:
            out.update(_SYNONYM_MAP[t])
    return out


def term_coverage(query: str, passage: str) -> float:
    """Fraction of the query's content terms that occur in the passage (0..1), with domain synonym awareness."""
    q = content_terms(query)
    if not q:
        return 0.0
    p = expand_synonyms(content_terms(passage))
    return sum(1 for t in q if t in p) / len(q)


def normalize_query(text: str) -> str:
    text = normalize_digits(unicodedata.normalize("NFKC", text)).lower()
    text = re.sub(r"[^\w\s\u0900-\u0DFF₹%]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
