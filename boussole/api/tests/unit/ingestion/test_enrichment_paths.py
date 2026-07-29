"""Ce que l'ingestion FAIT d'une offre déjà connue.

Quatre défauts d'une même famille, tous trouvés en revue en rejouant deux
cycles d'ingestion contre PostgreSQL : le pipeline savait CRÉER une offre
complète, mais pas l'enrichir. Chacun est silencieux — aucune erreur, aucune
ligne de journal, juste une donnée qui reste fausse ou absente pour toujours.

- le code secteur n'était écrit qu'à la création ;
- le drapeau « indispensable / souhaitée » ne bougeait plus jamais ;
- un secteur hors référentiel faisait perdre l'offre ENTIÈRE (clé étrangère
  violée, savepoint par item, ``errors += 1``) ;
- un libellé cité dans les deux listes créait deux lignes à la création, une
  seule à la fusion.

Le corpus de démonstration ne pouvait rien montrer de tout ça : ses douze
offres naissent complètes, avec leur secteur, sans recouvrement entre exigé
et souhaité, et ne sont jamais republiées enrichies.
"""

from datetime import UTC, datetime

from app.modules.ingestion.connectors.base import RawJob, RawLocation
from app.modules.ingestion.geocode import StaticGeocoder
from app.modules.ingestion.service import ingest_batch, normalize_raw
from tests.unit.ingestion.conftest import InMemoryJobStore

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _raw(external_ref: str = "j-1", **overrides: object) -> RawJob:
    champs: dict[str, object] = {
        "external_ref": external_ref,
        "title": "Data Engineer",
        "company": "ACME SAS",
        "description": "Poste de Data Engineer à Lyon.",
        "url": "https://exemple.test/j-1",
        "payload": {"id": external_ref},
        "locations": [RawLocation(label="Lyon")],
    }
    champs.update(overrides)
    return RawJob(**champs)  # type: ignore[arg-type]


async def _cycle(store: InMemoryJobStore, slug: str, raw: RawJob):
    return await ingest_batch(slug, [raw], store, geocoder=StaticGeocoder(), now=NOW)


class TestLeSecteurPeutArriverApresCoup:
    """4 % du poids, et la source ne le publie pas toujours dès le début."""

    async def test_la_meme_source_peut_ajouter_le_secteur(
        self, store: InMemoryJobStore
    ) -> None:
        store.add_source("france-travail")
        await _cycle(store, "france-travail", _raw())
        posting = next(iter(store.postings.values()))
        assert posting.sector_code is None

        rapport = await _cycle(store, "france-travail", _raw(sector="J"))

        assert rapport.updated == 1
        assert posting.sector_code == "J", (
            "le secteur n'était écrit qu'à la CRÉATION : une offre née sans "
            "secteur le gardait NULL à vie, et la dimension restait inconnue "
            "par construction"
        )

    async def test_une_source_concurrente_comble_le_secteur_manquant(
        self, store: InMemoryJobStore
    ) -> None:
        """Fusion §6.3 : remplissage du NULL, pas d'écrasement."""
        store.add_source("france-travail")
        store.add_source("greenhouse")
        await _cycle(store, "france-travail", _raw())
        posting = next(iter(store.postings.values()))

        await _cycle(store, "greenhouse", _raw(external_ref="gh-1", sector="J"))

        assert len(store.postings) == 1, "les deux offres devaient se dédoublonner"
        assert posting.sector_code == "J"

    async def test_une_source_concurrente_necrase_pas_un_secteur_connu(
        self, store: InMemoryJobStore
    ) -> None:
        store.add_source("france-travail")
        store.add_source("greenhouse")
        await _cycle(store, "france-travail", _raw(sector="J"))
        posting = next(iter(store.postings.values()))

        await _cycle(store, "greenhouse", _raw(external_ref="gh-1", sector="M"))

        assert posting.sector_code == "J"


class TestUnSecteurInconnuNeFaitPlusPerdreLoffre:
    """Le référentiel n'a que dix sections NACE ; les sources en publient
    d'autres. ``job_postings.sector_code`` étant une clé étrangère, le code
    inconnu ne dégradait pas une dimension : il annulait l'item entier."""

    async def test_le_code_hors_referentiel_est_ecarte_et_loffre_reste(
        self, store: InMemoryJobStore, caplog
    ) -> None:
        import logging

        store.add_source("france-travail")
        with caplog.at_level(logging.WARNING, logger="app.modules.ingestion.service"):
            rapport = await _cycle(store, "france-travail", _raw(sector="62.01Z"))

        assert rapport.created == 1 and rapport.errors == 0
        posting = next(iter(store.postings.values()))
        assert posting.sector_code is None
        assert any("job_sector_hors_referentiel" in r.message for r in caplog.records), (
            "sans avertissement, l'exploitant n'a aucun moyen de savoir qu'il "
            "manque une correspondance dans l'adaptateur de la source"
        )

    async def test_un_code_du_referentiel_passe(self, store: InMemoryJobStore) -> None:
        store.add_source("france-travail")
        await _cycle(store, "france-travail", _raw(sector="J"))
        assert next(iter(store.postings.values())).sector_code == "J"

    def test_sans_referentiel_fourni_rien_nest_ecarte(self) -> None:
        """Appel direct en test : ``known_sectors=None`` = pas de contrôle.
        Le contrôle appartient à ``ingest_source``, qui a la base."""
        normalise = normalize_raw(_raw(sector="62.01Z"), source_slug="x")
        assert normalise.sector_code == "62.01Z"


class TestLeDrapeauIndispensablePeutChanger:
    """25 % du poids d'un côté, 10 % de l'autre : le drapeau décide seul
    dans quelle dimension la compétence est comptée."""

    async def test_la_meme_source_promeut_une_competence_souhaitee(
        self, store: InMemoryJobStore
    ) -> None:
        store.add_source("france-travail")
        await _cycle(store, "france-travail", _raw(skills_nice=["Docker"]))
        assert [(s.label_raw, s.required) for s in store.skills] == [("Docker", False)]

        await _cycle(store, "france-travail", _raw(skills=["Docker"]))

        assert [(s.label_raw, s.required) for s in store.skills] == [("Docker", True)], (
            "seule la confiance était relevée : le drapeau restait figé sur "
            "ce que la PREMIÈRE publication en disait"
        )

    async def test_la_meme_source_peut_aussi_retrograder(
        self, store: InMemoryJobStore
    ) -> None:
        """Symétrie : inventer une exigence est aussi faux que d'en perdre une."""
        store.add_source("france-travail")
        await _cycle(store, "france-travail", _raw(skills=["Docker"]))
        await _cycle(store, "france-travail", _raw(skills_nice=["Docker"]))
        assert [s.required for s in store.skills] == [False]

    async def test_une_source_concurrente_moins_sure_ne_change_rien(
        self, store: InMemoryJobStore
    ) -> None:
        """§6.3 : à confiance égale, l'existant tient. Les deux sources
        déclarent au même niveau de confiance (0,9) — le désaccord se
        journalise, il ne se tranche pas au hasard du dernier cycle."""
        store.add_source("france-travail")
        store.add_source("greenhouse")
        await _cycle(store, "france-travail", _raw(skills=["Docker"]))

        await _cycle(
            store, "greenhouse", _raw(external_ref="gh-1", skills_nice=["Docker"])
        )

        assert [s.required for s in store.skills] == [True]


class TestUnLibelleCiteDeuxFoisNeDonneQuUneLigne:
    async def test_a_la_creation(self, store: InMemoryJobStore) -> None:
        store.add_source("france-travail")
        await _cycle(
            store,
            "france-travail",
            _raw(skills=["Python", "Docker"], skills_nice=["Docker", "Kubernetes"]),
        )

        lignes = sorted((s.label_raw, s.required) for s in store.skills)
        assert lignes == [("Docker", True), ("Kubernetes", False), ("Python", True)], (
            "deux lignes « Docker » s'affichaient à la fois en indispensable "
            "et en souhaitée, et comptaient deux fois dans le score (25+10 %)"
        )

    async def test_le_meme_flux_donne_la_meme_chose_en_creation_et_en_fusion(
        self, store: InMemoryJobStore
    ) -> None:
        """C'est l'incohérence qui rendait le défaut difficile à voir : le
        chemin de fusion dédoublonnait déjà, le chemin de création non."""
        chevauchement = {"skills": ["Docker"], "skills_nice": ["Docker"]}

        cree = InMemoryJobStore()
        cree.add_source("s")
        await _cycle(cree, "s", _raw(**chevauchement))

        fusionne = InMemoryJobStore()
        fusionne.add_source("s")
        await _cycle(fusionne, "s", _raw())
        await _cycle(fusionne, "s", _raw(**chevauchement))

        assert [(s.label_raw, s.required) for s in cree.skills] == [
            (s.label_raw, s.required) for s in fusionne.skills
        ]
