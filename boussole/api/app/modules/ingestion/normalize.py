"""Normalisation déterministe pour la déduplication (07 §6.1, D13).

Contient la fonction ``norm()`` — définition EXACTE des 6 étapes de
07 §6.1 —, la construction de ``norm_location`` et le calcul du
``dedup_hash`` (sha256, séparateur ``\\x1f``). Également l'étage 0 de
sanitisation HTML → texte (07 §5.2) : le HTML brut n'atteint jamais un
prompt ni les règles d'extraction.
"""

import hashlib
import html as _html
import re
import unicodedata

# Ponctuation/séparateurs listés explicitement en 07 §6.1 étape 4.
_EXPLICIT_PUNCT = set("/\\-_,.()[]&+'\"")

# Étape 6 (company uniquement) : suffixes juridiques terminaux et
# mentions « groupe »/« group » en tête. 🟡 (liste 07 §6.1).
_LEGAL_SUFFIXES = frozenset({"sas", "sasu", "sarl", "sa", "gmbh", "inc", "ltd", "llc", "bv"})
_GROUP_PREFIXES = frozenset({"groupe", "group"})


def _strip_accents(s: str) -> str:
    """Étape 3 — suppression des diacritiques (équivalent unaccent)."""
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def norm(s: str) -> str:
    """Normalise une chaîne selon les 6 étapes de 07 §6.1 (étapes 1–5).

    1. Unicode NFKC ; 2. casefold ; 3. unaccent ; 4. ponctuation et
    séparateurs remplacés par une espace ; 5. compactage des espaces + trim.
    L'étape 6 (spécifique aux raisons sociales) est dans :func:`norm_company`.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.casefold()
    s = _strip_accents(s)
    chars: list[str] = []
    for ch in s:
        category = unicodedata.category(ch)
        if ch in _EXPLICIT_PUNCT or category.startswith(("P", "Z")) or ch.isspace():
            chars.append(" ")
        else:
            chars.append(ch)
    return " ".join("".join(chars).split())


def norm_company(s: str) -> str:
    """``norm()`` + étape 6 : suffixes juridiques et « groupe » en tête."""
    tokens = norm(s).split()
    while len(tokens) > 1 and tokens[0] in _GROUP_PREFIXES:
        tokens = tokens[1:]
    while len(tokens) > 1 and tokens[-1] in _LEGAL_SUFFIXES:
        tokens = tokens[:-1]
    return " ".join(tokens)


def norm_location(
    *,
    city: str | None = None,
    country_code: str | None = None,
    raw_label: str | None = None,
    full_remote: bool = False,
) -> str:
    """Composante localisation de la clé de dédup (07 §6.1).

    - ville géocodée : ``country_code + ":" + norm(ville)`` ;
    - full-remote sans ville : ``"remote:" + country_code`` (ou ``"remote:"``) ;
    - sinon : ``norm(raw_label)`` ; à défaut chaîne vide.

    Les codes pays sont mis en minuscules pour la stabilité du hash.
    """
    cc = (country_code or "").strip().lower()
    if full_remote and not city:
        return f"remote:{cc}"
    if city:
        return f"{cc}:{norm(city)}"
    if raw_label:
        return norm(raw_label)
    return ""


def compute_dedup_hash(
    company: str,
    title: str,
    location_norm: str,
    employer_ref: str | None = "",
) -> str:
    """Clé exacte de l'étage 1 (07 §6.1, D13).

    ``sha256(norm(company) \\x1f norm(title) \\x1f norm_location \\x1f norm_ref)``.
    ``employer_ref`` = référence EMPLOYEUR si la source l'expose, chaîne vide
    sinon (résolution D13 du 2026-07-23 — jamais l'``external_ref`` de la
    source). ``location_norm`` est passée déjà normalisée
    (:func:`norm_location`).
    """
    parts = [
        norm_company(company),
        norm(title),
        location_norm,
        norm(employer_ref) if employer_ref else "",
    ]
    payload = "\x1f".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------- étage 0
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BLOCK_TAG_RE = re.compile(r"</?(?:p|div|li|ul|ol|h[1-6]|tr|table|section)\b[^>]*>|<br\s*/?>",
                           re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_HAS_HTML_RE = re.compile(r"<[a-zA-Z!/]")


def strip_html(s: str) -> str:
    """Étage 0 de 07 §5.2 : HTML → texte brut.

    Scripts/styles supprimés, balises bloc → sauts de ligne, autres balises
    retirées, entités décodées, NFKC, espaces compactés. Idempotent sur du
    texte sans balisage.
    """
    if _HAS_HTML_RE.search(s):
        s = _SCRIPT_STYLE_RE.sub(" ", s)
        s = _BLOCK_TAG_RE.sub("\n", s)
        s = _TAG_RE.sub(" ", s)
        s = _html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    lines = [" ".join(line.split()) for line in s.splitlines()]
    return "\n".join(line for line in lines if line).strip()
