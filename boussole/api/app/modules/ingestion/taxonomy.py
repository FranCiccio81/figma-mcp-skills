"""Taxonomie de compétences — normalisation label → ``skill_id`` (07 §5.5).

Chaîne partagée avec le module profil :

1. canonicalisation du libellé ;
2. alias exact (``skill_aliases``, citext → comparaison casefold) ;
3. libellé canonique (``skills.canonical_label``) ;
4. 🟡 rapprochement par embedding (cosinus ≥ 0,85, proposition d'alias en
   file de revue humaine) — NON implémenté au M2 (nécessite le modèle
   d'embeddings, 08 §8) ;
5. non rattaché → ``None`` (le ``label_raw`` est conservé dans
   ``job_skills``, le matching retombe sur les embeddings de libellés).
"""

import re
import unicodedata
import uuid
from collections.abc import Iterable, Mapping

_TERMINAL_PUNCT_RE = re.compile(r"[.,;:!?]+$")


def canonicalize(label: str) -> str:
    """Canonicalisation 07 §5.5 étape 1.

    lowercase (casefold), unaccent, trim, compactage des espaces,
    suppression de la ponctuation terminale.
    """
    label = unicodedata.normalize("NFKC", label).casefold()
    decomposed = unicodedata.normalize("NFD", label)
    label = "".join(c for c in decomposed if not unicodedata.combining(c))
    label = " ".join(label.split())
    return _TERMINAL_PUNCT_RE.sub("", label).strip()


class SkillResolver:
    """Résolution libellé brut → ``skill_id`` par lookup exact.

    Les deux tables de correspondance sont fournies déjà chargées
    (``skill_aliases`` et ``skills.canonical_label``) : aucune I/O ici,
    la classe est substituable et testable unitairement.
    """

    def __init__(
        self,
        aliases: Mapping[str, uuid.UUID] | Iterable[tuple[str, uuid.UUID]] = (),
        canonicals: Mapping[str, uuid.UUID] | Iterable[tuple[str, uuid.UUID]] = (),
    ) -> None:
        alias_items = aliases.items() if isinstance(aliases, Mapping) else aliases
        canon_items = canonicals.items() if isinstance(canonicals, Mapping) else canonicals
        self._aliases = {canonicalize(k): v for k, v in alias_items}
        self._canonicals = {canonicalize(k): v for k, v in canon_items}

    def resolve(self, label_raw: str) -> uuid.UUID | None:
        """Alias exact (casefold) puis ``canonical_label`` ; sinon ``None``."""
        key = canonicalize(label_raw)
        if not key:
            return None
        hit = self._aliases.get(key)
        if hit is not None:
            return hit
        return self._canonicals.get(key)
