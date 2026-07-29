"""Nettoyage des textes de diagnostic — messages d'erreur, piles, journaux.

**Ce que ça corrige.** Le nettoyeur Sentry (``app/core/observability.py``)
retire explicitement ``request.query_string`` parce qu'une requête de
recherche d'emploi « peut révéler une santé ou une reconversion ». Trois
canaux la contournaient, ainsi que d'autres données, et ils ont été mesurés :

1. ``exception.values[].value`` — le **message** de l'exception, que la liste
   blanche laissait passer entier. ``SMTPRecipientsRefused`` porte le
   dictionnaire des destinataires : une adresse part à chaque rebond
   d'e-mail ::

       "{'camille.durand@exemple.fr': (550, b'5.1.1 User unknown')}"

2. le ``DETAIL:`` composé par PostgreSQL, et surtout le bloc
   ``[parameters: ...]`` ajouté par SQLAlchemy. Sur une inscription en
   collision, le message complet porte l'adresse ET les paramètres liés ::

       duplicate key value violates unique constraint "users_email_key"
       DETAIL:  Key (email)=(camille.durand@exemple.fr) already exists.

   Ce texte partait vers Sentry **et** s'écrivait dans ``exc_info`` du
   journal local, donc chez l'agrégateur de logs.

3. le journal d'accès d'uvicorn (voir ``configure_logging`` dans
   ``app/main.py``), qui écrit le chemin BRUT — donc le ``?q=`` de la
   recherche et la signature HMAC des liens de téléchargement d'export.

**La règle.** Le principe du nettoyeur est « garder la forme, jeter les
valeurs ». Une donnée personnelle apparaît dans un texte de diagnostic sous
trois formes seulement, et chacune se reconnaît par sa forme :

- une adresse e-mail ;
- un secret opaque (signature HMAC hexadécimale, jeton de session) — dont la
  fuite ne concerne pas la vie privée mais l'authentification : une signature
  d'export lue dans un journal permet de retélécharger l'archive complète
  d'une personne ;
- **tout ce que la base ou le pilote ajoute après le message** — ``DETAIL:``,
  ``HINT:``, ``[SQL:``, ``[parameters:``. Là, pas de reconnaissance de forme
  possible : ces sections contiennent la ligne concernée par construction.
  Elles sont coupées entièrement, pas filtrées.

**Ce que ça n'est pas.** Ce n'est pas une liste noire de champs — la course
perdue décrite dans ``observability.py``. C'est une normalisation appliquée à
UN type de contenu : du texte libre destiné à un humain. La liste blanche de
champs reste la barrière principale ; ceci traite le seul champ qu'on ne
pouvait pas supprimer sans rendre les rapports d'erreur inutilisables.

**Le compromis assumé.** ``ValueError: expected 3 got 5`` survit intact —
c'est ce qui rend un rapport d'erreur exploitable. On perd le nom de la
contrainte violée quand il vient après un saut de ligne, et la valeur exacte
d'un identifiant long. Le diagnostic se fait alors sur le type et la pile.
"""

import re

#: Sections ajoutées par PostgreSQL/SQLAlchemy APRÈS le message. Elles
#: contiennent la ligne en cause ou les paramètres liés — donc l'adresse, le
#: hachage du mot de passe, le texte d'un CV. Coupées, jamais filtrées.
_SECTIONS_DE_DONNEES = ("DETAIL:", "HINT:", "CONTEXT:", "[SQL:", "[parameters:")

#: Bornes de longueur. Un message qui embarque un CV est long par
#: construction ; le tronquer coûte un diagnostic moins riche, le laisser
#: passer transfère le document.
LIMITE_MESSAGE = 500
LIMITE_PILE = 20_000

_ADRESSE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

#: Hexadécimal long : empreinte HMAC-SHA256 (64), UUID sans tirets (32).
_HEXADECIMAL = re.compile(r"\b[0-9a-fA-F]{32,}\b")

#: Candidat de jeton ``secrets.token_urlsafe`` (43 caractères base64url).
#: Le motif seul attraperait aussi les identifiants Python longs — un nom de
#: test en snake_case dépasse volontiers 40 caractères. La casse mixte
#: tranche : un identifiant Python est en minuscules, un jeton de 43
#: caractères tirés au sort a les deux casses avec une certitude pratique
#: (probabilité d'y échapper ≈ 10⁻¹⁰).
_JETON_CANDIDAT = re.compile(r"[A-Za-z0-9_-]{40,}")


def _est_un_jeton(candidat: str) -> bool:
    return any(c.islower() for c in candidat) and any(c.isupper() for c in candidat)


def redact(texte: str) -> str:
    """Remplace adresses et secrets par un marqueur, sans toucher au reste.

    Le marqueur est visible exprès : un rapport d'erreur doit dire qu'il a
    été nettoyé, sinon on cherche pourquoi le message semble incomplet.
    """
    texte = _ADRESSE.sub("[adresse]", texte)
    texte = _HEXADECIMAL.sub("[secret]", texte)
    return _JETON_CANDIDAT.sub(
        lambda m: "[secret]" if _est_un_jeton(m.group()) else m.group(), texte
    )


def redact_message(texte: str | None) -> str | None:
    """Message d'erreur exportable : première ligne, nettoyée, bornée.

    La coupure à la première ligne n'est pas cosmétique : c'est elle qui
    supprime le ``DETAIL:`` de PostgreSQL et le bloc ``[parameters: ...]`` de
    SQLAlchemy, deux sections qui portent la ligne concernée en entier et
    qu'aucune reconnaissance de forme ne saurait filtrer.
    """
    if not texte:
        return texte
    message = texte.split("\n", 1)[0]
    for marqueur in _SECTIONS_DE_DONNEES:
        message = message.split(marqueur, 1)[0]
    message = redact(message).rstrip()
    if len(message) > LIMITE_MESSAGE:
        message = message[:LIMITE_MESSAGE] + "…[tronqué]"
    return message


def redact_traceback(texte: str) -> str:
    """Pile d'appels nettoyée — les cadres restent, les valeurs partent.

    Une pile est multiligne par nature : la couper à la première ligne la
    détruirait. On retire donc les lignes de section (``DETAIL:``,
    ``[parameters:``…) et on nettoie les autres.
    """
    lignes = [
        redact(ligne)
        for ligne in texte.splitlines()
        if not ligne.lstrip().startswith(_SECTIONS_DE_DONNEES)
    ]
    propre = "\n".join(lignes)
    if len(propre) > LIMITE_PILE:
        propre = propre[:LIMITE_PILE] + "\n…[tronqué]"
    return propre


def strip_query(url: str | None) -> str | None:
    """Chemin sans chaîne de requête.

    ``?q=`` porte la recherche d'emploi, ``?sig=`` la signature d'un lien de
    téléchargement d'export. Aucun des deux n'a sa place dans un journal.
    """
    if not url:
        return url
    return url.split("?", 1)[0]
