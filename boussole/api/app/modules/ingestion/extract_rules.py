"""Étage 1 — extraction déterministe par règles FR/EN (07 §5.2).

Coût nul, reproductible, testé unitairement (D02/R7). Chaque fonction
retourne ``None`` quand rien n'est détecté OU quand des motifs
contradictoires coexistent (dans ce cas l'attribut passe à l'étage 2 LLM).

Confiances par famille (07 §5.2) : contrat 0,9 · salaire 0,8 ·
remote 0,85 · langues 0,8 · expérience 0,85 · séniorité 0,9 🟡.
La détection de langue de l'annonce est une heuristique par mots-outils
FR/EN sans dépendance lourde 🟡 (lingua-py prévu en intégration, 07 §5.4).
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import NamedTuple

CONTRACT_CONFIDENCE = 0.9
SALARY_CONFIDENCE = 0.8
REMOTE_CONFIDENCE = 0.85
LANGUAGE_CONFIDENCE = 0.8
EXPERIENCE_CONFIDENCE = 0.85
SENIORITY_CONFIDENCE = 0.9  # 🟡 hypothèse (07 §5.2 ne fixe pas cette famille)

# Bornes de vraisemblance d'un salaire annualisé (07 §5.2 🟡).
_SALARY_MIN_YEARLY = 10_000
_SALARY_MAX_YEARLY = 500_000
_DAYS_PER_YEAR = 218
_HOURS_PER_YEAR = 1_607


class RuleResult(NamedTuple):
    """Valeur extraite par règle + confiance associée."""

    value: str
    confidence: float


def _fold(text: str) -> str:
    """Casefold + unaccent (ponctuation conservée pour les motifs)."""
    text = unicodedata.normalize("NFKC", text).casefold()
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# ------------------------------------------------------------------ contrat
_CONTRACT_PATTERNS: dict[str, re.Pattern[str]] = {
    "permanent": re.compile(
        r"\bcdi\b|contrat\s+a\s+duree\s+indeterminee|permanent\s+(?:contract|position|role)"
    ),
    "fixed_term": re.compile(
        r"\bcdd\b|contrat\s+a\s+duree\s+determinee|fixed[\s-]term"
    ),
    "internship": re.compile(r"\bstage\b|\bstagiaire\b|\binternship\b|\bintern\b"),
    "apprenticeship": re.compile(
        r"\balternance\b|\bapprentissage\b|\bapprenticeship\b|contrat\s+pro\b"
    ),
    "freelance": re.compile(r"\bfree[\s-]?lance\b|\bindependant\b|\btjm\b|\bcontractor\b"),
    "other": re.compile(r"\binterim\b|\binterimaire\b|\btemp(?:orary)?\s+work\b"),
}


def extract_contract(text: str) -> RuleResult | None:
    """Type de contrat par dictionnaires FR/EN (07 §5.2).

    Confiance 0,9 si un seul type détecté ; plusieurs types contradictoires
    → ``None`` (étage 2).
    """
    folded = _fold(text)
    hits = {kind for kind, pattern in _CONTRACT_PATTERNS.items() if pattern.search(folded)}
    if len(hits) == 1:
        return RuleResult(hits.pop(), CONTRACT_CONFIDENCE)
    return None


# ------------------------------------------------------------------- remote
_FULL_REMOTE_RE = re.compile(
    r"\bfull[\s-]?remote\b|\bfully\s+remote\b|\bremote[\s-]first\b"
    r"|100\s*%\s*(?:remote|teletravail)"
    r"|teletravail\s+(?:total|complet|a\s+100\s*%)"
)
_HYBRID_RE = re.compile(r"\bhybride?\b|teletravail\s+partiel|partial(?:ly)?\s+remote")
_ONSITE_RE = re.compile(
    r"\bsur\s+site\b|\bpresentiel\b|\bon[\s-]?site\b"
    r"|pas\s+de\s+teletravail|aucun\s+teletravail|\bno\s+remote\b"
)
_REMOTE_DAYS_RES = (
    re.compile(r"teletravail[^\n.]{0,25}?(\d)\s*j(?:ours?|/)?"),
    re.compile(r"(\d)\s*j(?:ours?)?\s+de\s+teletravail"),
    re.compile(r"(\d)\s*days?\s+(?:of\s+)?(?:remote|home[\s-]?office|wfh)"),
    re.compile(r"remote[^\n.]{0,15}?(\d)\s*days?"),
)


@dataclass(frozen=True)
class RemoteRule:
    """Politique remote extraite + nombre de jours si détecté."""

    value: str  # onsite | hybrid | full_remote
    confidence: float
    days_per_week: int | None = None


def extract_remote(text: str) -> RemoteRule | None:
    """Politique de télétravail par dictionnaires (07 §5.2, confiance 0,85).

    « N jours de télétravail » → ``hybrid`` (``full_remote`` si N ≥ 5).
    Motifs contradictoires → ``None`` (étage 2).
    """
    folded = _fold(text)
    days: int | None = None
    for pattern in _REMOTE_DAYS_RES:
        match = pattern.search(folded)
        if match:
            days = int(match.group(1))
            break

    hits: set[str] = set()
    if _FULL_REMOTE_RE.search(folded):
        hits.add("full_remote")
    if _HYBRID_RE.search(folded) or (days is not None and days < 5):
        hits.add("hybrid")
    if days is not None and days >= 5:
        hits.add("full_remote")
    if _ONSITE_RE.search(folded) and days is None:
        hits.add("onsite")

    if len(hits) == 1:
        return RemoteRule(hits.pop(), REMOTE_CONFIDENCE, days)
    return None


# ------------------------------------------------------------------- salaire
_SEP = r"(?:\s*[-–—]\s*|\s+(?:a|et|to)\s+)"
_CUR = r"(?:€|eur(?:os?)?|\$|usd|£|gbp)"
_K_RANGE_RE = re.compile(
    rf"\b(\d{{2,3}})\s*k?\s*{_CUR}?{_SEP}(\d{{2,3}})\s*k\s*{_CUR}?", re.IGNORECASE
)
# Montant : « 45 000 », « 45000 », ou petit montant (TJM/horaire) « 500 ».
_NUM = "\\d{1,3}[   .,]?\\d{3}|\\d{4,6}|\\d{2,3}"
# Partie décimale optionnelle (« 42000.0 Euros » — libellés France Travail).
_DEC = r"(?:[.,]\d{1,2})?"
_FULL_RANGE_RE = re.compile(
    rf"\b({_NUM}){_DEC}\s*{_CUR}?{_SEP}({_NUM}){_DEC}\s*{_CUR}", re.IGNORECASE
)
_K_SINGLE_RE = re.compile(rf"\b(\d{{2,3}})\s*k\s*{_CUR}", re.IGNORECASE)
_FULL_SINGLE_RE = re.compile(rf"\b({_NUM}){_DEC}\s*{_CUR}", re.IGNORECASE)

_PERIOD_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("month", re.compile(r"/\s*mois|par\s+mois|mensuel|monthly|per\s+month|/\s*month")),
    ("day", re.compile(r"\btjm\b|/\s*jour|par\s+jour|per\s+day|daily\s+rate|/\s*day")),
    ("hour", re.compile(r"/\s*h\b|par\s+heure|per\s+hour|hourly|/\s*hour")),
    ("year", re.compile(r"/\s*an\b|par\s+an|annuel|brut\s+annuel|per\s+year|annual|yearly")),
)
_ANNUAL_FACTOR = {"year": 1, "month": 12, "day": _DAYS_PER_YEAR, "hour": _HOURS_PER_YEAR}


@dataclass(frozen=True)
class SalaryRule:
    """Fourchette salariale extraite par règles (07 §5.2, confiance 0,8)."""

    salary_min: int
    salary_max: int
    currency: str
    period: str  # year | month | day | hour
    confidence: float = SALARY_CONFIDENCE


def _parse_amount(raw: str) -> int:
    return int(re.sub("[ \u00a0\u202f.,]", "", raw))


def _window(folded: str, start: int, end: int, radius: int = 60) -> str:
    return folded[max(0, start - radius) : end + radius]


def _period_and_currency(window: str, is_k: bool) -> tuple[str, str]:
    del is_k
    # Sans contexte de période : lecture annuelle par convention (07 §5.2).
    period = next((p for p, rx in _PERIOD_RES if rx.search(window)), "year")
    if "$" in window or "usd" in window:
        currency = "USD"
    elif "£" in window or "gbp" in window:
        currency = "GBP"
    else:
        currency = "EUR"
    return period, currency


def _plausible(amount: int, period: str) -> bool:
    yearly = amount * _ANNUAL_FACTOR[period]
    return _SALARY_MIN_YEARLY <= yearly <= _SALARY_MAX_YEARLY


def extract_salary(text: str) -> SalaryRule | None:
    """Salaire par regex à fenêtres contextuelles (07 §5.2).

    Fourchettes ``45-55k€``, montants pleins ``45 000 €``, périodes /an,
    /mois, TJM. Montants aberrants (< 10 k€/an ou > 500 k€/an après
    annualisation 🟡) → rejet (étage 2).
    """
    folded = _fold(text)
    for pattern, is_k, is_range in (
        (_K_RANGE_RE, True, True),
        (_FULL_RANGE_RE, False, True),
        (_K_SINGLE_RE, True, False),
        (_FULL_SINGLE_RE, False, False),
    ):
        match = pattern.search(folded)
        if not match:
            continue
        low = _parse_amount(match.group(1)) * (1000 if is_k else 1)
        high = _parse_amount(match.group(2)) * (1000 if is_k else 1) if is_range else low
        if low > high:
            low, high = high, low
        period, currency = _period_and_currency(
            _window(folded, match.start(), match.end()), is_k
        )
        if not (_plausible(low, period) and _plausible(high, period)):
            return None  # aberrant → étage 2
        return SalaryRule(low, high, currency, period)
    return None


# --------------------------------------------------------------- expérience
_EXP_CONTEXT_RE = re.compile(r"experien|\bxp\b")
_EXP_RANGE_RE = re.compile(r"\b(\d{1,2})\s*(?:a|-|–|to)\s*(\d{1,2})\s*(?:ans?\b|years?\b)")
_EXP_PLUS_RE = re.compile(r"\b(\d{1,2})\s*\+\s*(?:ans?\b|years?\b)")
_EXP_MIN_RE = re.compile(
    r"(?:au\s+moins|minimum|min\.?|at\s+least)\s+(\d{1,2})\s*(?:ans?\b|years?\b)"
)
_EXP_SINGLE_RE = re.compile(r"\b(\d{1,2})\s*(?:ans?\b|years?\b)")


class ExperienceRule(NamedTuple):
    """Années d'expérience extraites (07 §5.2, confiance 0,85)."""

    minimum: float
    maximum: float | None
    confidence: float


def extract_experience(text: str) -> ExperienceRule | None:
    """« 5+ ans », « 3 à 5 ans », « 5 years of experience »…

    Le motif doit être adjacent au mot « expérience »/« experience »
    (fenêtre ±60 caractères) pour éviter les durées non pertinentes.
    """
    folded = _fold(text)

    def _in_context(start: int, end: int) -> bool:
        return bool(_EXP_CONTEXT_RE.search(_window(folded, start, end)))

    match = _EXP_RANGE_RE.search(folded)
    if match and _in_context(*match.span()):
        return ExperienceRule(float(match.group(1)), float(match.group(2)),
                              EXPERIENCE_CONFIDENCE)
    match = _EXP_PLUS_RE.search(folded)
    if match and _in_context(*match.span()):
        return ExperienceRule(float(match.group(1)), None, EXPERIENCE_CONFIDENCE)
    match = _EXP_MIN_RE.search(folded)
    if match and _in_context(*match.span()):
        return ExperienceRule(float(match.group(1)), None, EXPERIENCE_CONFIDENCE)
    match = _EXP_SINGLE_RE.search(folded)
    if match and _in_context(*match.span()):
        years = float(match.group(1))
        return ExperienceRule(years, years, EXPERIENCE_CONFIDENCE)
    return None


# ------------------------------------------------------------------ langues
_LANG_WORDS: dict[str, str] = {
    "anglais": "en", "english": "en",
    "francais": "fr", "french": "fr",
    "allemand": "de", "german": "de", "deutsch": "de",
    "espagnol": "es", "spanish": "es",
    "italien": "it", "italian": "it",
}
# Mapping courant→B2 🟡, bilingue/natif→C2 (07 §5.2).
_LEVEL_WORDS: tuple[tuple[str, str], ...] = (
    ("bilingue", "C2"), ("bilingual", "C2"), ("natif", "C2"), ("native", "C2"),
    ("langue maternelle", "C2"), ("courant", "B2"), ("courante", "B2"),
    ("fluent", "B2"), ("professionnel", "B2"), ("professional", "B2"),
    ("intermediaire", "B1"), ("intermediate", "B1"),
    ("notions", "A2"), ("basique", "A2"), ("basic", "A2"), ("beginner", "A2"),
)
_CEFR_RE = re.compile(r"\b([abc][12])\b")


class LanguageRule(NamedTuple):
    """Exigence de langue extraite (07 §5.2, confiance 0,8)."""

    lang_code: str
    min_level: str  # CECRL
    confidence: float


def extract_languages(text: str) -> list[LanguageRule]:
    """Langues requises : « anglais courant » → en B2 🟡, CECRL explicite…

    La langue de rédaction de l'annonce n'est JAMAIS convertie en exigence
    (06 §2 dim. 9) : seuls les motifs explicites langue+niveau sont émis.
    """
    folded = _fold(text)
    results: dict[str, LanguageRule] = {}
    for word, code in _LANG_WORDS.items():
        for match in re.finditer(rf"\b{word}\b", folded):
            window = _window(folded, match.start(), match.end(), radius=30)
            level: str | None = None
            cefr = _CEFR_RE.search(window)
            if cefr:
                level = cefr.group(1).upper()
            else:
                for level_word, cefr_level in _LEVEL_WORDS:
                    if level_word in window:
                        level = cefr_level
                        break
            if level is not None and code not in results:
                results[code] = LanguageRule(code, level, LANGUAGE_CONFIDENCE)
    return list(results.values())


# ---------------------------------------------------------------- séniorité
_SENIORITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "intern": re.compile(r"\bstagiaire\b|\bintern\b(?!al)"),
    "junior": re.compile(r"\bjunior\b|\bdebutant(?:e)?\b|entry[\s-]level|\bgraduate\b"),
    "mid": re.compile(r"\bconfirme(?:e)?\b|mid[\s-]level"),
    "senior": re.compile(r"\bsenior\b|\bexperimente(?:e)?\b"),
    "lead": re.compile(r"\blead\b|\bteam\s+lead\b|\btech\s+lead\b"),
    "principal": re.compile(r"\bprincipal\b|\bstaff\s+engineer\b"),
    "executive": re.compile(
        r"\bdirecteur\b|\bdirectrice\b|\bdirector\b|\bhead\s+of\b|\bvp\b|\bchief\b"
    ),
}


def extract_seniority(text: str) -> RuleResult | None:
    """Séniorité par mots-clés (confiance 0,9 🟡).

    Un seul niveau détecté → résultat ; plusieurs niveaux contradictoires
    → ``None`` (étage 2).
    """
    folded = _fold(text)
    hits = {level for level, pattern in _SENIORITY_PATTERNS.items() if pattern.search(folded)}
    if len(hits) == 1:
        return RuleResult(hits.pop(), SENIORITY_CONFIDENCE)
    return None


# ------------------------------------------------- langue de rédaction 🟡
_FR_STOPWORDS = frozenset([
    "le", "la", "les", "des", "une", "un", "et", "ou", "nous", "vous", "pour",
    "avec", "dans", "sur", "est", "sont", "notre", "vos", "du", "de", "au",
    "aux", "ce", "cette", "qui", "que", "plus", "pas", "chez", "poste",
    "equipe", "entreprise", "missions", "profil", "recherche", "annees",
])
_EN_STOPWORDS = frozenset([
    "the", "and", "of", "to", "in", "for", "with", "you", "we", "our", "is",
    "are", "will", "on", "at", "as", "this", "that", "be", "or", "from",
    "have", "work", "team", "role", "about", "your", "join", "years",
    "skills", "experience",
])


def detect_language(text: str) -> tuple[str, float]:
    """Heuristique FR/EN par mots-outils (07 §5.4 🟡, sans dépendance lourde).

    Retourne ``(code ISO 639-1, confiance)``. Confiance < 0,7 → l'appelant
    applique le défaut par source (fr pour France Travail, en sinon).
    """
    words = re.findall(r"[a-z']+", _fold(text))
    fr_hits = sum(1 for w in words if w in _FR_STOPWORDS)
    en_hits = sum(1 for w in words if w in _EN_STOPWORDS)
    total = fr_hits + en_hits
    if total < 5:
        return ("fr", 0.5)
    if fr_hits >= en_hits:
        return ("fr", fr_hits / total)
    return ("en", en_hits / total)
