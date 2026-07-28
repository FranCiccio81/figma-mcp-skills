"""Construction des textes source à embarquer (06 §2.3, 07 §5.5/§5.6).

Un embedding ne vaut que par le texte qu'on lui donne : ces fonctions
fixent, en UN seul endroit, ce qui entre dans chaque vecteur. Toute
modification ici change la sémantique des vecteurs déjà en base et impose
un re-embedding complet (08 §8) — au même titre qu'un changement de
modèle.

| Colonne | Texte source |
|---|---|
| ``job_postings.embedding`` | intitulé + 1er paragraphe de l'annonce (06 §2.3) |
| ``profiles.embedding`` | intitulés cibles + intitulés occupés |
| ``preference_titles.embedding`` | l'intitulé cible seul (06 §2.3 : max des cosinus) |
| ``skills.embedding`` | libellé canonique de la compétence (07 §5.5) |

**Minimisation (D09)** : aucun de ces textes ne contient de donnée
nominative — ni nom, ni e-mail, ni téléphone, ni adresse. Le vecteur de
profil est construit à partir d'INTITULÉS de poste uniquement, jamais du
résumé ni des descriptions d'expérience (qui peuvent contenir des
coordonnées ou des attributs sensibles issus du CV).
"""

import hashlib
import re
from collections.abc import Iterable, Sequence

__all__ = [
    "MAX_PARAGRAPH_CHARS",
    "MAX_TITLE_CHARS",
    "first_paragraph",
    "job_embedding_text",
    "profile_embedding_text",
    "skill_embedding_text",
    "source_text_hash",
]

#: Bornes de troncature 🟡 : un vecteur dilué par 20 000 caractères de
#: « avantages » et de boilerplate RH ne discrimine plus rien, et le coût
#: d'un provider managé est proportionnel aux tokens (R7).
MAX_PARAGRAPH_CHARS = 1000
MAX_TITLE_CHARS = 200

#: Séparateur entre intitulés d'un même vecteur — neutre pour le repli
#: alphanumérique du provider local (il ne produit aucun jeton).
_JOIN = " · "

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"\s+")


def _squeeze(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def first_paragraph(description: str, *, max_chars: int = MAX_PARAGRAPH_CHARS) -> str:
    """Premier paragraphe non vide de la description, compacté et borné.

    Le texte reçu est déjà du texte brut (l'étage 0 de 07 §5.2 a retiré le
    HTML) : les paragraphes sont donc séparés par des lignes vides. Sans
    ligne vide, tout le texte est considéré comme un seul paragraphe et
    c'est la troncature qui joue.
    """
    for block in _PARAGRAPH_SPLIT_RE.split(description or ""):
        squeezed = _squeeze(block)
        if squeezed:
            return squeezed[:max_chars]
    return ""


def job_embedding_text(title: str, description: str) -> str:
    """Texte source d'une offre : « intitulé + 1er paragraphe » (06 §2.3)."""
    parts = [_squeeze(title or "")[:MAX_TITLE_CHARS], first_paragraph(description or "")]
    return _JOIN.join(part for part in parts if part)


def _dedupe_titles(titles: Iterable[str]) -> list[str]:
    """Déduplique en préservant l'ordre (insensible à la casse)."""
    seen: set[str] = set()
    kept: list[str] = []
    for title in titles:
        squeezed = _squeeze(title or "")[:MAX_TITLE_CHARS]
        key = squeezed.casefold()
        if squeezed and key not in seen:
            seen.add(key)
            kept.append(squeezed)
    return kept


def profile_embedding_text(
    target_titles: Sequence[str], held_titles: Sequence[str] = (), *, max_held: int = 2
) -> str:
    """Texte source d'un profil : intitulés cibles + ``max_held`` intitulés occupés.

    06 §2.3 définit la dimension comme le **max des cosinus** entre chaque
    intitulé du candidat et l'offre. Le schéma n'offre qu'UN vecteur par
    profil : ce texte agrégé en est l'approximation 🟡 (un centroïde
    lexical), utilisable dès qu'il existe. La forme exacte de 06 §2.3
    reste disponible et prioritaire via ``preference_titles.embedding``
    (un vecteur par intitulé), passés à
    ``candidate_input_from(title_embeddings=…)``.

    ``held_titles`` doit être fourni du plus récent au plus ancien.
    """
    titles = _dedupe_titles([*target_titles, *list(held_titles)[:max_held]])
    return _JOIN.join(titles)


def skill_embedding_text(label: str) -> str:
    """Texte source d'une compétence : son libellé canonique (07 §5.5)."""
    return _squeeze(label or "")[:MAX_TITLE_CHARS]


def source_text_hash(text: str) -> str:
    """Condensat stable du texte source (idempotence du backfill).

    ``blake2b`` tronqué à 16 hex — stable entre processus, contrairement à
    ``hash()``. 🟡 **Aucune colonne du schéma ne stocke ce condensat**
    (``job_postings``, ``profiles``, ``preference_titles`` et ``skills``
    n'ont que ``embedding``) : il sert aujourd'hui à la journalisation et
    à l'idempotence EN MÉMOIRE d'un lot. La détection « le texte source a
    changé depuis le calcul » est donc portée par le POINT D'ÉCRITURE
    (l'ingestion recalcule l'embedding quand elle modifie l'intitulé ou la
    description), pas par le batch — voir
    :mod:`app.ai.embeddings.backfill`. Une colonne
    ``embedding_source_hash`` (+ ``embedding_model_version``, 08 §8)
    rendrait le rattrapage exact : migration à prévoir avec Q11.
    """
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
