"""Minimisation déterministe des données transmises au LLM (D09, RM-T-7).

La minimisation ne peut pas reposer sur la seule bonne volonté du modèle
(consigne « n'extrais pas les coordonnées ») ni sur ``extra='forbid'`` : un
schéma fermé interdit des CLÉS hors schéma, il n'empêche EN RIEN une adresse
e-mail, un numéro de téléphone ou une date de naissance de voyager dans un
champ TEXTE légitime (``headline``, ``summary``, ``description``,
``evidence.quote``). Ce module apporte le filet déterministe :

- :func:`scrub_pii` — retire d'un texte les coordonnées et attributs
  personnels détectables par expression régulière (e-mail, téléphone
  FR/international, IBAN, date de naissance, adresse postale simple 🟡,
  situation familiale 🟡) et retourne la liste des CATÉGORIES retirées
  (jamais les valeurs — les journaux ne doivent pas recopier la donnée) ;
- :func:`scrub_payload` — applique :func:`scrub_pii` à toutes les chaînes
  d'un payload structuré (profil transmis aux prompts).

Le filtrage est volontairement CONSERVATEUR côté vie privée : un faux
positif (fragment retiré à tort) coûte une reformulation, un faux négatif
expose une donnée personnelle à un tiers (le fournisseur LLM).
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

#: Marqueur inséré à la place d'un fragment retiré (visible en relecture).
REDACTED = "[RETIRÉ]"

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Téléphone : international (+33…, 0033…) ou national FR (0X …), séparateurs
# espace/point/tiret uniquement. Les dates « 01/09/2020 » et les millésimes
# (« 2020 », « 2015-2019 ») ne sont PAS des numéros : préfixe 0/+ obligatoire
# et 8 chiffres minimum.
_PHONE = re.compile(r"(?<![\w+])(?:(?:\+|00)\d{1,3}[\s.\-]?|0)\d(?:[\s.\-]?\d){7,12}(?!\d)")

_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b")

# Date de naissance : mention explicite, ou date complète JJ/MM/AAAA (un CV
# date ses expériences en MM/AAAA ou AAAA — une date complète est un
# marqueur d'état civil).
_BIRTH_DATE = re.compile(
    r"(?:n[ée]e?\s+le\s*:?\s*[^\n,;.]{0,40})"
    r"|(?:date\s+de\s+naissance\s*:?\s*[^\n,;.]{0,40})"
    r"|(?:\b\d{1,2}[/.\-]\d{1,2}[/.\-](?:19|20)\d{2}\b)",
    re.IGNORECASE,
)

# Adresse postale simple 🟡 : numéro + voie, ou code postal + commune.
_ADDRESS = re.compile(
    r"(?:\b\d{1,4}\s*(?:bis|ter|quater)?[,]?\s+"
    r"(?:rue|avenue|av\.|boulevard|bd|impasse|chemin|all[ée]e|place|route|quai|voie|cours)"
    r"\b[^\n;.]{0,60})"
    r"|(?:\b\d{5}\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+(?:[ \-][A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+)?\b)",
    re.IGNORECASE,
)

# Situation familiale / enfants (attribut interdit R8, jamais utile au prompt).
_MARITAL = re.compile(
    r"\b(?:c[ée]libataire|mari[ée]e?|divorc[ée]e?|veuf|veuve|pacs[ée]e?|concubinage)\b"
    r"|(?:situation\s+familiale\s*:?\s*[^\n;.]{0,30})"
    r"|(?:\b\d+\s+enfants?\b)",
    re.IGNORECASE,
)

#: (catégorie, motif) — ordre significatif : l'e-mail et l'IBAN d'abord (leurs
#: chiffres ne doivent pas être mangés par le motif téléphone).
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", _EMAIL),
    ("iban", _IBAN),
    ("birth_date", _BIRTH_DATE),
    ("phone", _PHONE),
    ("postal_address", _ADDRESS),
    ("marital_status", _MARITAL),
)


#: Les identifiants techniques (UUID des références d'ancrage
#: ``experience:<uuid>``…) sont MASQUÉS avant filtrage : une suite de
#: chiffres d'UUID ne doit jamais être prise pour un numéro de téléphone —
#: un ref mutilé casserait le contrôle d'ancrage.
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
#: Sentinelles de masquage (zone à usage privé Unicode : aucun motif
#: ci-dessus ne peut les traverser, aucun texte réel ne les contient).
_MASK_OPEN = "\ue000"
_MASK_CLOSE = "\ue001"


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """``(texte nettoyé, catégories retirées)`` — filet déterministe D09.

    Chaque fragment reconnu est remplacé par :data:`REDACTED` ; la valeur
    d'origine n'est jamais retournée ni journalisée. Idempotent : le
    marqueur ne correspond à aucun motif. Les UUID (références d'ancrage)
    sont préservés à l'identique.
    """
    if not text:
        return text, []

    masked: list[str] = []

    def _mask(match: re.Match[str]) -> str:
        masked.append(match.group(0))
        return f"{_MASK_OPEN}{len(masked) - 1}{_MASK_CLOSE}"

    cleaned = _UUID.sub(_mask, text)
    removed: list[str] = []
    for category, pattern in _PATTERNS:
        cleaned, count = pattern.subn(REDACTED, cleaned)
        if count:
            removed.append(category)
    for index, value in enumerate(masked):
        cleaned = cleaned.replace(f"{_MASK_OPEN}{index}{_MASK_CLOSE}", value)
    return cleaned, removed


def scrub_payload(payload: Any) -> tuple[Any, list[str]]:
    """Applique :func:`scrub_pii` à TOUTES les chaînes d'un payload structuré.

    Parcours récursif des mappings et séquences (les clés ne sont pas
    modifiées : elles viennent du code, pas de l'utilisateur). Retourne le
    payload nettoyé et les catégories retirées (dédupliquées, ordre stable).
    """
    removed: list[str] = []

    def _walk(node: Any) -> Any:
        if isinstance(node, str):
            cleaned, found = scrub_pii(node)
            for category in found:
                if category not in removed:
                    removed.append(category)
            return cleaned
        if isinstance(node, Mapping):
            return {key: _walk(value) for key, value in node.items()}
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
            return [_walk(item) for item in node]
        return node

    return _walk(payload), removed


def scrub_warning(removed: Sequence[str]) -> str:
    """Avertissement lisible (français) listant les CATÉGORIES retirées."""
    labels = {
        "email": "adresse e-mail",
        "phone": "numéro de téléphone",
        "iban": "IBAN",
        "birth_date": "date de naissance",
        "postal_address": "adresse postale",
        "marital_status": "situation familiale",
    }
    listed = ", ".join(labels.get(item, item) for item in removed)
    return (
        f"Minimisation (D09) : donnée(s) personnelle(s) retirée(s) — {listed}. "
        "Ces informations ne sont jamais transmises au modèle."
    )
