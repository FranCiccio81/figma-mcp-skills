"""Provider d'embeddings LOCAL et DÉTERMINISTE (défaut dev/test/CI).

Principe — *hashing trick* signé sur des n-grammes :

1. le texte est replié (NFKD, désaccentué, casefold) puis découpé en
   jetons : mots + n-grammes de caractères (``ngram=3`` par défaut, avec
   marqueurs de bord ``^``/``$``) — le mélange mots/n-grammes rapproche
   les variantes orthographiques (« back-end » ≈ « backend ») et les
   flexions, ce qui est exactement ce que demandent les usages FR/EN de
   06 §2.1 et §2.3. Les symboles qui font partie du NOM d'une technologie
   (``C++``, ``C#``, ``.NET``) sont CONSERVÉS dans le jeton — voir
   :data:`_WORD_RE` ;
2. chaque jeton est projeté par ``blake2b`` sur un indice de la dimension
   configurée, avec un signe tiré du même condensat (projection signée :
   les collisions s'annulent en espérance au lieu de s'additionner) ;
3. le vecteur accumulé est normalisé L2.

**Déterminisme** : ``blake2b`` et non ``hash()`` — le hachage natif de
Python est randomisé par processus (``PYTHONHASHSEED``), ce qui
produirait des vecteurs différents entre l'API et un worker Celery, donc
des cosinus faux et une base incohérente. Le condensat est stable entre
processus, machines et versions de Python.

**Ce que ce provider n'est pas** : un modèle sémantique. Il capture de la
similarité LEXICALE (morphologie, ordre des caractères), pas du sens :
« développeur backend » et « ingénieur serveur » restent éloignés. Il
permet de livrer, tester et calibrer toute la chaîne sans réseau ni clé,
mais les seuils produit (0,75 / 0,80–0,55 / 0,92) devront être
recalibrés 🟡 avec le modèle réellement retenu (**Q11 non tranchée**,
**Q12** — 08 §8 impose un re-embedding complet à tout changement).
"""

import hashlib
import math
import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

__all__ = ["HASHING_MODEL_VERSION", "HashingEmbeddingProvider"]

#: Version du « modèle » local — journalisée comme ``embedding_model_version``
#: (08 §8). Tout changement d'algorithme DOIT l'incrémenter : les vecteurs
#: déjà en base ne seraient plus comparables.
HASHING_MODEL_VERSION = "hashing-ngram-v2"

#: Jeton = mot alphanumérique, AVEC le point de tête et les suffixes ``+``/``#``
#: qui font partie du NOM de la technologie. Sans eux, ``C``, ``C++`` et ``C#``
#: (comme ``.NET`` et ``NET``) produisent des jetons IDENTIQUES, donc un cosinus
#: de 1,0 : une offre exigeant C++ créditerait « proche » (06 §2.1, seuil 0,75)
#: un candidat ne connaissant que C.
#:
#: Le point n'est capturé qu'en TÊTE : un point final de phrase (« … en
#: Python. ») reste hors du jeton, sinon toute la ponctuation ferait diverger
#: les vecteurs de textes par ailleurs identiques.
_WORD_RE = re.compile(r"\.?[0-9a-z]+[+#]*")


def fold(text: str) -> str:
    """Repli insensible à la casse et aux accents (NFKD + suppression des diacritiques)."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokens(text: str, ngram: int) -> Iterator[str]:
    """Mots + n-grammes de caractères bornés, sur le texte replié."""
    for word in _WORD_RE.findall(fold(text)):
        yield word
        padded = f"^{word}$"
        if len(padded) <= ngram:
            continue
        for start in range(len(padded) - ngram + 1):
            yield padded[start : start + ngram]


def _project(token: str, dimension: int) -> tuple[int, float]:
    """Indice + signe du jeton (condensat stable inter-processus)."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
    index = int.from_bytes(digest[:8], "big") % dimension
    sign = 1.0 if digest[8] & 1 else -1.0
    return index, sign


@dataclass(frozen=True)
class HashingEmbeddingProvider:
    """Implémentation locale du :class:`~app.ai.embeddings.base.EmbeddingProvider`.

    Aucun réseau, aucune clé, aucun état : deux appels avec le même texte
    rendent le MÊME vecteur, dans n'importe quel processus.
    """

    dimension: int
    ngram: int = 3
    model: str = HASHING_MODEL_VERSION

    def __post_init__(self) -> None:
        if self.dimension < 1:
            raise ValueError(f"dimension d'embedding invalide : {self.dimension}")
        if self.ngram < 2:
            raise ValueError(f"taille de n-gramme invalide : {self.ngram}")

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode chaque texte en vecteur normalisé L2 (vecteur nul si vide)."""
        return [self.embed(text) for text in texts]

    def embed(self, text: str) -> list[float]:
        """Encode UN texte — vecteur nul si le texte ne produit aucun jeton."""
        vector = [0.0] * self.dimension
        for token in _tokens(text, self.ngram):
            index, sign = _project(token, self.dimension)
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            # Texte vide ou sans caractère alphanumérique : vecteur nul,
            # jamais persisté (un vecteur nul rendrait tout cosinus nul et
            # ferait diverger l'index HNSW cosinus).
            return vector
        return [value / norm for value in vector]
