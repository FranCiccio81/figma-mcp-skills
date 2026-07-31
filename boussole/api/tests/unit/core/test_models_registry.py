"""Les métadonnées SQLAlchemy doivent être COMPLÈTES dans tout processus.

Deux pannes graves, même cause, trouvées le même jour par deux revues
indépendantes — et c'est ce qui rend ce contrôle nécessaire : l'oubli ne se
manifeste jamais là où on l'a commis.

**1. Alembic** — sur la commande qu'on tape pour écrire la migration suivante :

    $ alembic revision --autogenerate -m "..."
    INFO  [alembic.autogenerate.compare.tables] Detected removed table 'job_postings'
    INFO  [alembic.autogenerate.compare.tables] Detected removed table 'profiles'
    ...
    upgrade() : drop_table = 33   create_table = 0

``alembic/env.py`` n'importait qu'UN module sur dix : ``Base.metadata``
connaissait 3 tables sur 37, les 34 autres passaient pour « supprimées du
code ». Dont ``ai_calls`` (treize mois de conservation obligatoire) et
``audit_log`` (la preuve des purges RGPD).

**2. Celery** — le processus worker n'importait que les modules touchés par
ses tâches. ``applications`` n'en faisait pas partie, alors que
``generated_documents.application_id`` porte une clé étrangère vers cette
table :

    NoReferencedTableError: Foreign key associated with column
    'generated_documents.application_id' could not find table 'applications'

Tout flush ORM d'un document généré échouait — donc e-mail, lettre de
motivation, CV adapté et optimisation de CV étaient **intégralement
inopérants**. Silencieusement : l'API répondait 202 (elle importe les modèles
via ses routeurs), le document restait ``pending`` pour toujours, et
l'utilisateur lisait « Rédaction en cours… » sans limite de temps.

D'où ``app/models_registry.py`` : un seul endroit qui connaisse la liste, et
ce test qui la compare au contenu réel de ``app/modules/*/models.py``.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.migration_policy import include_object

API = Path(__file__).resolve().parents[3]
ENV = API / "alembic" / "env.py"
REGISTRE = API / "app" / "models_registry.py"
CELERY = API / "app" / "workers" / "celery_app.py"
MODULES = API / "app" / "modules"


def _modules_avec_modeles() -> set[str]:
    """Modules qui déclarent des tables — la source de vérité, pas une liste.

    ``rglob`` et chemin POINTÉ, pas ``glob`` et nom court. Le motif d'origine
    (``*/models.py`` + ``p.parent.name``) ratait ``profiles/cv/models.py`` deux
    fois : le glob ne descend pas d'un niveau, et même corrigé il aurait rendu
    ``cv`` là où le registre importe ``profiles.cv``. Deux tables manquaient à
    ``Base.metadata`` sans que la garde ne bronche.
    """
    return {
        ".".join(chemin.parent.relative_to(MODULES).parts)
        for chemin in MODULES.rglob("models.py")
    }


def _modules_du_registre() -> set[str]:
    """``from app.modules.X import models`` présents dans le registre."""
    arbre = ast.parse(REGISTRE.read_text(encoding="utf-8"))
    importes: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom) and noeud.module:
            parties = noeud.module.split(".")
            if parties[:2] == ["app", "modules"] and any(
                alias.name == "models" for alias in noeud.names
            ):
                importes.add(".".join(parties[2:]))
    return importes


class TestLeRegistreEstComplet:
    def test_le_perimetre_du_controle_nest_pas_vide(self) -> None:
        assert len(_modules_avec_modeles()) >= 8

    def test_aucun_module_de_modeles_noublie(self) -> None:
        manquants = _modules_avec_modeles() - _modules_du_registre()
        assert not manquants, (
            f"app/models_registry.py n'importe pas {sorted(manquants)} : leurs "
            "tables seront absentes de Base.metadata, donc --autogenerate "
            "proposera de les SUPPRIMER et les clés étrangères qui les "
            "traversent ne se résoudront pas dans le worker."
        )

    def test_toutes_les_cles_etrangeres_se_resolvent(self) -> None:
        """LE contrôle qui aurait attrapé la panne de génération.

        ``sorted_tables`` force la résolution de toutes les FK : c'est
        exactement l'opération que faisait échouer l'absence
        d'``applications``, et elle échouait dans le worker uniquement.
        """
        import app.models_registry  # noqa: F401
        from app.core.db import Base

        # L'appel EST le test : il lève NoReferencedTableError si une FK
        # pointe vers une table absente de la métadonnée.
        assert Base.metadata.sorted_tables

    @pytest.mark.parametrize("fichier", [ENV, CELERY], ids=["alembic", "celery"])
    def test_les_deux_processus_chargent_le_registre(self, fichier) -> None:
        """Un processus qui manipule l'ORM sans le registre est le défaut."""
        assert "models_registry" in fichier.read_text(encoding="utf-8"), (
            f"{fichier.name} doit importer app.models_registry — sinon ses "
            "métadonnées sont incomplètes, et ça ne se voit pas chez lui"
        )


class TestLeFiltreDeSuretteEstEnPlace:
    """Le second filet : ce qui n'est pas déclaré n'est pas géré.

    Quatre tables (``ai_calls``, ``cv_documents``, ``extraction_runs``,
    ``prompt_versions``) et quinze index/contraintes existent en base sans
    contrepartie dans les modèles — index partiels, GIN trigram, HNSW
    vectoriel, que SQLAlchemy ne sait pas déclarer. Sans filtre, l'autogenerate
    les proposait tous à la suppression, dont ``idx_jobs_embedding`` (la
    recherche sémantique) et ``idx_jobs_tsv`` (la recherche plein texte).
    """

    def test_include_object_est_cable_sur_les_deux_modes(self) -> None:
        source = ENV.read_text(encoding="utf-8")
        assert source.count("include_object=include_object") == 2, (
            "le filtre doit être passé à context.configure() en mode online "
            "ET offline — un mode non filtré suffit à générer les drops"
        )

    @pytest.mark.parametrize(
        "type_,nom,attendu",
        [
            ("table", "ai_calls", False),
            ("table", "users", True),
            ("index", "idx_jobs_embedding", False),
            ("unique_constraint", "job_sources_source_id_external_ref_key", False),
            ("foreign_key_constraint", "profiles_source_cv_id_fkey", False),
            ("column", "email", True),
        ],
    )
    def test_ce_qui_nest_pas_declare_est_ignore(
        self, type_: str, nom: str, attendu: bool
    ) -> None:
        """Cas « présent en base, absent des modèles » = proposé à la suppression."""
        assert (
            include_object(None, nom, type_, True, None) is attendu
        ), f"{type_} {nom!r} : le filtre doit rendre {attendu}"

    def test_un_objet_venant_des_modeles_reste_gere(self) -> None:
        """Le filtre ne doit pas rendre l'autogenerate inutile : un index
        DÉCLARÉ dans un modèle (donc avec une contrepartie) passe."""
        assert include_object(None, "idx_quelconque", "index", False, None) is True
        assert include_object(None, "idx_quelconque", "index", True, object()) is True


class TestLaMigrationNeAttendPasUnVerrouIndefiniment:
    def test_un_lock_timeout_est_pose(self) -> None:
        """Une requête de lecture de 60 s sur ``ai_calls`` — un pg_dump, une
        requête analytique — suffisait à transformer une migration de 4 s en
        58 s d'écritures bloquées : ce n'est pas le lecteur qui bloque
        l'écrivain, c'est la file d'attente derrière l'ACCESS EXCLUSIVE que la
        migration réclame. Sans borne, l'attente est illimitée."""
        assert "SET lock_timeout" in ENV.read_text(encoding="utf-8")


class TestLaMetadonneeEstReellementComplete:
    """La garde qui ne peut pas être contournée par un motif de fichier.

    Les vérifications ci-dessus comparent des LISTES : celle des modules sur
    le disque et celle du registre. Elles reposent donc sur un motif de
    chemin, et c'est précisément un motif de chemin qui a laissé passer
    ``profiles/cv/models.py`` — ``app/modules/*/models.py`` ne descend pas
    d'un niveau, et ``Base.metadata`` connaissait 32 tables au lieu de 34.

    Celle-ci mesure la PROPRIÉTÉ : importer le registre doit suffire.

    **En SOUS-PROCESSUS, et c'est le point.** Écrite dans le processus de
    test, elle passait au vert sans rien prouver : les imports Python sont
    globaux, et un test exécuté plus tôt avait déjà chargé les modules
    manquants. Elle mesurait donc l'état accumulé de la suite, pas ce que
    voit un worker Celery qui démarre. Deux interpréteurs neufs, un par
    scénario, sont la seule façon de poser la vraie question.
    """

    @staticmethod
    def _tables(imports: str) -> set[str]:
        code = (
            f"{imports}\n"
            "from app.core.db import Base\n"
            "print(' '.join(sorted(Base.metadata.tables)))"
        )
        resultat = subprocess.run(
            [sys.executable, "-c", code],
            cwd=API,
            capture_output=True,
            text=True,
            check=True,
        )
        return set(resultat.stdout.split())

    def test_importer_le_registre_suffit(self) -> None:
        modules = sorted(
            ".".join(chemin.relative_to(API).with_suffix("").parts)
            for chemin in API.joinpath("app").rglob("models.py")
        )
        registre = self._tables("import app.models_registry")
        tout = self._tables(
            "import app.models_registry\n"
            + "\n".join(f"import {module}" for module in modules)
        )

        assert tout - registre == set(), (
            f"tables absentes de Base.metadata quand on n'importe QUE le "
            f"registre : {sorted(tout - registre)} — tout processus qui s'y "
            f"fie travaille avec une métadonnée incomplète"
        )
