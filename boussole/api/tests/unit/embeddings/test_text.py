"""Textes source des embeddings (06 §2.3, 07 §5.5/§5.6).

Ce qui entre dans un vecteur est aussi normatif que le modèle : toute
modification impose un re-embedding complet (08 §8). D'où des tests
explicites sur la composition et sur la MINIMISATION (D09 : aucun champ
nominatif n'entre dans un vecteur).
"""

from app.ai.embeddings.text import (
    MAX_PARAGRAPH_CHARS,
    first_paragraph,
    job_embedding_text,
    profile_embedding_text,
    skill_embedding_text,
    source_text_hash,
)


class TestPremierParagraphe:
    def test_prend_le_premier_bloc_non_vide(self) -> None:
        description = "\n\n  \n\nNous cherchons un développeur.\n\nAvantages : tickets."
        assert first_paragraph(description) == "Nous cherchons un développeur."

    def test_sans_ligne_vide_tout_le_texte_est_un_paragraphe(self) -> None:
        assert first_paragraph("Une seule ligne\nsuivie d'une autre") == (
            "Une seule ligne suivie d'une autre"
        )

    def test_tronque_a_la_borne(self) -> None:
        assert len(first_paragraph("a" * 5000)) == MAX_PARAGRAPH_CHARS

    def test_description_vide(self) -> None:
        assert first_paragraph("") == ""


class TestTexteOffre:
    def test_combine_intitule_et_premier_paragraphe(self) -> None:
        text = job_embedding_text(
            "Développeur backend", "Vous rejoindrez l'équipe.\n\nAvantages : RTT."
        )
        assert "Développeur backend" in text
        assert "Vous rejoindrez l'équipe." in text
        assert "RTT" not in text  # le 2e paragraphe n'entre pas dans le vecteur

    def test_intitule_seul_si_description_vide(self) -> None:
        assert job_embedding_text("Développeur backend", "") == "Développeur backend"


class TestTexteProfil:
    def test_cumule_intitules_cibles_et_occupes(self) -> None:
        text = profile_embedding_text(
            ["Développeur backend"], ["Développeur fullstack", "Stagiaire", "Vendeur"]
        )
        assert "Développeur backend" in text
        assert "Développeur fullstack" in text
        assert "Stagiaire" in text
        assert "Vendeur" not in text  # borne max_held=2

    def test_deduplique_sans_tenir_compte_de_la_casse(self) -> None:
        text = profile_embedding_text(["Data Engineer"], ["data engineer"])
        assert text.lower().count("data engineer") == 1

    def test_profil_sans_intitule_rend_une_chaine_vide(self) -> None:
        # → aucun vecteur persisté → title_similarity reste inconnue (k=0).
        assert profile_embedding_text([], []) == ""

    def test_minimisation_seuls_des_intitules_entrent_dans_le_vecteur(self) -> None:
        # D09 : la fonction ne prend QUE des intitulés — ni résumé, ni
        # description d'expérience (susceptibles de porter des coordonnées
        # ou des attributs sensibles issus du CV).
        text = profile_embedding_text(["Développeur backend"], [])
        assert text == "Développeur backend"


class TestCondensat:
    def test_stable_pour_le_meme_texte(self) -> None:
        assert source_text_hash("Développeur backend") == source_text_hash(
            "Développeur backend"
        )

    def test_change_avec_le_texte(self) -> None:
        assert source_text_hash("Développeur") != source_text_hash("Développeuse")


class TestTexteCompetence:
    def test_compacte_le_libelle(self) -> None:
        assert skill_embedding_text("  Python   3  ") == "Python 3"

    def test_libelle_vide(self) -> None:
        assert skill_embedding_text("") == ""
