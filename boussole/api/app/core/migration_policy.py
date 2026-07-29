"""Ce qu'``alembic --autogenerate`` a le droit de proposer.

Extrait d'``alembic/env.py`` pour une raison précise : ``env.py`` lit
``context.config`` dès son import et n'est donc exécutable que sous Alembic.
Une règle de sûreté qu'on ne peut pas tester en CI n'est pas une règle.

**Ce que ça corrige.** Revue avant déploiement, sur la commande qu'on tape
pour écrire la migration suivante :

    $ alembic revision --autogenerate -m "..."
    upgrade() : drop_table = 33   create_table = 0

``env.py`` n'importait qu'un module de modèles sur dix : ``Base.metadata``
connaissait 3 tables sur 37, et les 34 autres passaient pour « supprimées du
code ». Parmi elles ``ai_calls`` (treize mois de conservation obligatoire) et
``audit_log`` (la preuve des purges RGPD).

Les imports manquants sont rétablis dans ``env.py``. Il restait quinze index
et contraintes proposés à la suppression — ceux que SQLAlchemy ne sait pas
déclarer : index partiels, GIN trigram, HNSW vectoriel. Dont
``idx_jobs_embedding`` (la recherche sémantique) et ``idx_jobs_tsv`` (la
recherche plein texte). D'où le filtre ci-dessous.

**Le parti pris.** Une chose présente en base et absente des modèles n'est pas
« à supprimer » : c'est une chose qu'Alembic ne sait pas décrire. Le pire cas
devient « la migration générée oublie quelque chose » — visible à la
relecture — au lieu de « la migration générée détruit quelque chose », qui ne
se voit qu'après.
"""

#: Tables réelles SANS modèle ORM : créées et modifiées par du SQL écrit à la
#: main dans les migrations, lues par des requêtes ``text()``. Leur donner un
#: modèle que personne n'utiliserait serait inventer une abstraction pour
#: satisfaire un outil.
TABLES_SANS_MODELE = frozenset(
    {"ai_calls", "cv_documents", "extraction_runs", "prompt_versions"}
)

#: Objets dont l'existence en base ne se déduit pas des modèles.
TYPES_NON_DECLARABLES = frozenset(
    {"index", "unique_constraint", "foreign_key_constraint"}
)


def include_object(
    objet: object,
    nom: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Signature ``include_object`` d'Alembic — ``False`` = objet ignoré.

    Contrepartie assumée : un index réellement retiré d'un modèle ne sera pas
    détecté, il faudra écrire sa suppression à la main. C'est le bon sens de
    l'échec.
    """
    if type_ == "table" and nom in TABLES_SANS_MODELE:
        return False
    # Présent en base (``reflected``) et sans contrepartie dans les modèles
    # (``compare_to is None``) : exactement le cas « proposé à la suppression ».
    return not (type_ in TYPES_NON_DECLARABLES and reflected and compare_to is None)
