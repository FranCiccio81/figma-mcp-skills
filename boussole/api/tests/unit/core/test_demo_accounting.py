"""L'amorçage de démonstration doit CRIER quand une offre s'est perdue.

Trouvé en revue : ``ingest_batch`` isole chaque offre dans un savepoint, donc
une offre qui échoue est annulée seule et comptée dans ``errors`` — et
personne ne lisait ``errors``. Repro contre PostgreSQL, corpus de douze
offres dont une portait un code secteur hors référentiel :

    ERROR ingestion_item_error source=demo-corpus external_ref=demo-001
    ...
      Offres ingérées      : 11 créées, 0 mises à jour, 0 rattachées (dédup)
      ✅ Application utilisable.
    EXIT=0

Onze offres sur douze, code de sortie 0, verdict « utilisable ». C'est
précisément le genre de sortie sur laquelle on s'appuie pour conclure que
l'environnement est bon, et aller chercher le problème ailleurs.
"""

from app.demo import ingestion_problems


def _rapport(**ecarts: int) -> dict[str, int]:
    base = {
        "recues": 12,
        "creees": 12,
        "mises_a_jour": 0,
        "rattachees_etage1": 0,
        "rattachees_etage2": 0,
        "erreurs": 0,
    }
    base.update(ecarts)
    return base


class TestUnAmorcageCompletNeSignaleRien:
    def test_douze_recues_douze_creees(self) -> None:
        assert ingestion_problems(_rapport()) == []

    def test_deuxieme_execution_en_mise_a_jour(self) -> None:
        """``make demo`` est idempotent : rejouer ne doit pas alarmer."""
        assert ingestion_problems(_rapport(creees=0, mises_a_jour=12)) == []

    def test_une_offre_rattachee_par_dedup_est_traitee(self) -> None:
        """Une offre dédoublonnée ne crée pas de ligne — et n'est pas perdue.
        Compter les lignes en base, et non le compte rendu, ferait crier la
        déduplication à chaque fois qu'elle fait son travail."""
        assert (
            ingestion_problems(_rapport(creees=11, rattachees_etage1=1)) == []
        )
        assert (
            ingestion_problems(_rapport(creees=11, rattachees_etage2=1)) == []
        )


class TestUneOffrePerdueEstSignalee:
    def test_une_erreur_ditem_remonte(self) -> None:
        problemes = ingestion_problems(_rapport(creees=11, erreurs=1))
        assert problemes, "c'est exactement le cas qui rendait « ✅ » à tort"
        assert "ingestion_item_error" in problemes[0], (
            "le message doit dire OÙ chercher : sans ça, l'exploitant sait "
            "qu'il manque une offre mais pas laquelle ni pourquoi"
        )

    def test_un_ecart_de_comptage_remonte_meme_sans_erreur(self) -> None:
        """Ceinture et bretelles : un chemin de perte qui n'incrémenterait
        pas ``errors`` reste visible."""
        problemes = ingestion_problems(_rapport(creees=11))
        assert problemes == ["12 offre(s) reçues du corpus, 11 traitées"]

    def test_les_deux_signaux_sont_cumules(self) -> None:
        assert len(ingestion_problems(_rapport(creees=10, erreurs=1))) == 2
