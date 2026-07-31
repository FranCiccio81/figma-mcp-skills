"""Index manquants sur les chemins chauds — mesurés, pas supposés.

Revision ID: 0007
Revises: 0006

Trois coûts constatés en revue avant déploiement, contre un PostgreSQL réel
peuplé. Aucun n'est visible aujourd'hui : le corpus de démonstration fait
douze offres et un compte. Tous croissent avec l'usage réel.

1. **Rétention d'``ai_calls`` : 20 scans complets par jour.**
   Le prédicat est ``WHERE created_at < cutoff``, et le seul index existant
   est ``idx_ai_calls_task_time (task, created_at)`` — ``task`` en tête le
   rend inutilisable pour ce filtre. Mesuré sur 15 M lignes :

       Parallel Seq Scan on ai_calls
         Buffers: shared hit=11880 read=176382     (1,47 Go lus)
       Execution Time: 749 ms                       pour 5 000 lignes

   et le ``ORDER BY id`` force un tri, donc **chaque lot re-scanne toute la
   table** : 21,8 s et ~30 Go d'E/S pour un passage quotidien qui supprime
   la moitié de son arriéré. Ironie relevée en revue : la migration 0006 a
   déployé les grands moyens pour indexer la purge RGPD (occasionnelle) et a
   laissé sans index la rétention (quotidienne).

   ⚠️ **Nuance mesurée en posant l'index, et qui mérite d'être écrite** : le
   gain dépend de la distribution. Sur un arriéré massif (la quasi-totalité
   des lignes éligibles, cas du premier passage), le planificateur balaie
   ``ai_calls_pkey`` et l'index sur ``created_at`` ne sert à rien. C'est en
   **régime permanent** — peu de lignes éligibles parmi beaucoup de récentes,
   l'état de tous les jours suivants — qu'il mord. Mesuré sur 200 000 lignes
   dont 5 000 éligibles :

       avec l'index   : Index Scan,          1,7 ms,    18 blocs
       sans           : Parallel Seq Scan,  20,2 ms,  1907 blocs
                        (97 500 lignes écartées par le filtre)

   Douze fois plus rapide et cent fois moins d'E/S, sur une table qui est la
   plus volumineuse du système et une tâche qui tourne chaque nuit.

2. **Purge d'un compte : coût linéaire au volume TOTAL, pas au sien.**
   Vingt-quatre clés étrangères sans index de support. Les deux qui se
   paient à chaque purge, mesurées sur 300 000 comptes / 900 000
   expériences :

       DELETE FROM cv_documents WHERE user_id = ?
         -> Seq Scan on cv_documents          69,7 ms
       DELETE FROM profiles WHERE user_id = ?
         Trigger profile_experiences_profile_id_fkey: 91,7 ms

   130 ms par compte à 300 k comptes, sur un chemin déjà surveillé pour son
   retard (D20). À 3 M comptes, la purge quotidienne se compte en secondes
   par compte.

3. **Tri par compatibilité sur la liste d'offres.**
   ``idx_match_by_score`` est PARTIEL (``WHERE blocking_criteria = '[]'``) :
   il ne couvre pas le cas par défaut du contrat, où les offres bloquées
   restent visibles et badgées. L'index complet sert la jointure et le tri
   de la requête la plus chaude du produit.

MIGRATION SANS INTERRUPTION
---------------------------
Tout est en ``CONCURRENTLY``, donc hors transaction (``autocommit_block``).
Deux pièges que la revue a reproduits sur 0006 et qu'on évite ici :

- ``CREATE INDEX CONCURRENTLY`` interrompu laisse un index **INVALIDE** ;
  ``IF NOT EXISTS`` compare le NOM et considère alors le travail fait. La
  migration se déclarait « appliquée » avec un index inutilisable, et
  ``alembic upgrade head`` étant déjà à head, elle ne repassait jamais. On
  supprime donc explicitement tout index invalide de même nom avant de créer.
- L'``autocommit_block`` casse l'atomicité : un échec en cours laisse une
  partie du travail commitée. Chaque étape est donc **rejouable** telle
  quelle.
- ``env.py`` pose ``lock_timeout = 5s`` sur la connexion de migration. Cette
  borne est **juste pour les migrations transactionnelles et fausse ici** :
  voir :func:`_sans_lock_timeout`.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

#: (nom, table, définition). Ordre : le plus coûteux d'abord — si la
#: migration est interrompue, c'est celui-là qu'on veut avoir gagné.
INDEXES: tuple[tuple[str, str, str], ...] = (
    (
        "ix_ai_calls_created_at",
        "ai_calls",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ai_calls_created_at "
        "ON ai_calls (created_at)",
    ),
    (
        "ix_cv_documents_user_id",
        "cv_documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cv_documents_user_id "
        "ON cv_documents (user_id)",
    ),
    (
        "ix_profile_experiences_profile_id",
        "profile_experiences",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_profile_experiences_profile_id "
        "ON profile_experiences (profile_id)",
    ),
    (
        "ix_profile_skills_profile_id",
        "profile_skills",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_profile_skills_profile_id "
        "ON profile_skills (profile_id)",
    ),
    (
        "ix_profile_educations_profile_id",
        "profile_educations",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_profile_educations_profile_id "
        "ON profile_educations (profile_id)",
    ),
    (
        "ix_profile_languages_profile_id",
        "profile_languages",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_profile_languages_profile_id "
        "ON profile_languages (profile_id)",
    ),
    (
        "ix_generated_documents_user_id",
        "generated_documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_generated_documents_user_id "
        "ON generated_documents (user_id)",
    ),
    (
        "ix_applications_user_id",
        "applications",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_applications_user_id "
        "ON applications (user_id)",
    ),
    (
        "ix_saved_jobs_user_id",
        "saved_jobs",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_saved_jobs_user_id "
        "ON saved_jobs (user_id)",
    ),
    (
        "ix_audit_log_user_id",
        "audit_log",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_audit_log_user_id "
        "ON audit_log (user_id)",
    ),
    (
        "ix_match_results_profile_score",
        "match_results",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_match_results_profile_score "
        "ON match_results (profile_id, score DESC)",
    ),
)


def _drop_if_invalid(nom: str) -> None:
    """Supprime l'index s'il existe mais est INVALIDE.

    C'est le correctif du piège de 0006 : un ``CREATE INDEX CONCURRENTLY``
    interrompu (pod tué, timeout, deadlock) laisse une relation du bon nom
    que ``IF NOT EXISTS`` considère comme faite. L'index n'est jamais utilisé
    par le planificateur, et rien ne le signale.

    Le contrôle est fait ICI et non dans un ``DO $$`` : PostgreSQL refuse
    ``DROP INDEX CONCURRENTLY`` à l'intérieur d'un bloc de fonction comme
    d'une transaction. Première version écrite ainsi, et elle échouait
    exactement sur le cas qu'elle existe pour traiter.
    """
    # Nom littéral : il vient de ``INDEXES`` ci-dessus, jamais d'une entrée
    # externe. asyncpg n'accepte de toute façon pas les paramètres nommés.
    invalide = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT 1 FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid "
            f"WHERE c.relname = '{nom}' AND NOT i.indisvalid"
        )
        .first()
    )
    if invalide is not None:
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {nom}")


def _sans_lock_timeout() -> None:
    """Lève le ``lock_timeout`` de 5 s pour la durée de ce bloc.

    **Mesuré en revue avant déploiement, contre un PostgreSQL réel.** Un
    simple ``SELECT`` **en lecture seule** sur ``users`` — une table sans
    aucun rapport — tenu trois secondes suffisait à faire échouer cette
    migration dès son PREMIER index ::

        asyncpg.exceptions.LockNotAvailableError:
          canceling statement due to lock timeout
        [SQL: CREATE INDEX CONCURRENTLY ... ON ai_calls (created_at)]

    La raison : ``CREATE INDEX CONCURRENTLY`` attend la fin des transactions
    en cours au moment où il démarre, et cette attente est soumise au
    ``lock_timeout``. Sur une base en production — un ``pg_dump``, une
    requête analytique, un ``idle in transaction`` oublié — la condition est
    permanente. Onze index à passer, chacun devant franchir la même porte.

    **Et cette borne ne protégeait rien ici.** Le commentaire d'``env.py``
    justifie les 5 s par « un lecteur long transforme une migration de 4 s en
    58 s d'écritures bloquées ». C'est vrai d'un ``ALTER TABLE``, qui prend un
    ``ACCESS EXCLUSIVE``. ``CREATE INDEX CONCURRENTLY`` ne prend qu'un
    ``SHARE UPDATE EXCLUSIVE`` et **ne bloque aucune écriture** — c'est son
    unique raison d'être. La borne n'évitait donc aucune indisponibilité et
    ne coûtait que l'échec de la migration.

    Le ``lock_timeout`` reste en vigueur partout ailleurs : c'est la portée
    qui était fausse, pas le principe. ``statement_timeout`` n'est pas touché
    non plus — s'il est posé côté serveur, il s'applique toujours.
    """
    op.execute("SET lock_timeout = 0")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        _sans_lock_timeout()
        for nom, _table, sql in INDEXES:
            _drop_if_invalid(nom)
            op.execute(sql)


def downgrade() -> None:
    """Retire les index. Aucune donnée n'est perdue — ils sont dérivés.

    Contrairement au downgrade de 0004, celui-ci est réellement sans risque :
    un index ne porte pas d'information qui n'existe pas ailleurs.
    """
    with op.get_context().autocommit_block():
        _sans_lock_timeout()  # même attente, même raison qu'à l'aller
        for nom, _table, _sql in INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {nom}")
