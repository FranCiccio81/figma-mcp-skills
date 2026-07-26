"""Tests des règles déterministes FR/EN (07 §5.2) — étage 1."""

import pytest

from app.modules.ingestion import extract_rules as rules


class TestContract:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Poste à pourvoir en CDI dès que possible", "permanent"),
            ("Contrat à durée indéterminée — statut cadre", "permanent"),
            ("This is a permanent contract based in Paris", "permanent"),
            ("CDD de 6 mois renouvelable", "fixed_term"),
            ("Fixed-term contract (12 months)", "fixed_term"),
            ("Stage de fin d'études de 6 mois", "internship"),
            ("Contrat en alternance (apprentissage)", "apprenticeship"),
            ("Mission freelance, TJM selon profil", "freelance"),
            ("Mission d'intérim de 3 mois", "other"),
        ],
    )
    def test_detection(self, text: str, expected: str) -> None:
        result = rules.extract_contract(text)
        assert result is not None
        assert result.value == expected
        assert result.confidence == 0.9

    def test_contradictoire_renvoie_none(self) -> None:
        assert rules.extract_contract("CDI ou CDD selon profil") is None

    def test_aucun_motif(self) -> None:
        assert rules.extract_contract("Une offre sans type de contrat") is None


class TestRemote:
    def test_full_remote_en(self) -> None:
        result = rules.extract_remote("This position is full remote (France)")
        assert result is not None
        assert result.value == "full_remote"
        assert result.confidence == 0.85

    def test_teletravail_total_fr(self) -> None:
        result = rules.extract_remote("Télétravail total possible")
        assert result is not None
        assert result.value == "full_remote"

    def test_teletravail_3j_semaine(self) -> None:
        result = rules.extract_remote("Télétravail 3j/semaine après période d'essai")
        assert result is not None
        assert result.value == "hybrid"
        assert result.days_per_week == 3

    def test_jours_de_teletravail(self) -> None:
        result = rules.extract_remote("2 jours de télétravail par semaine")
        assert result is not None
        assert result.value == "hybrid"
        assert result.days_per_week == 2

    def test_hybrid_en(self) -> None:
        result = rules.extract_remote("Hybrid policy: 3 days of remote work per week")
        assert result is not None
        assert result.value == "hybrid"

    def test_sur_site(self) -> None:
        result = rules.extract_remote("Poste en présentiel uniquement")
        assert result is not None
        assert result.value == "onsite"

    def test_contradictoire(self) -> None:
        assert rules.extract_remote("Full remote ou sur site, au choix") is None

    def test_aucun_motif(self) -> None:
        assert rules.extract_remote("Une offre sans politique de télétravail") is None


class TestSalary:
    def test_fourchette_keuro_compacte(self) -> None:
        result = rules.extract_salary("Rémunération : 45-55k€ selon profil")
        assert result is not None
        assert (result.salary_min, result.salary_max) == (45000, 55000)
        assert result.currency == "EUR"
        assert result.period == "year"
        assert result.confidence == 0.8

    def test_fourchette_45_55K_sans_euro(self) -> None:
        result = rules.extract_salary("Package : 45-55K")
        assert result is not None
        assert (result.salary_min, result.salary_max) == (45000, 55000)

    def test_fourchette_entre_et(self) -> None:
        result = rules.extract_salary("entre 42 et 48 k€ brut annuel")
        assert result is not None
        assert (result.salary_min, result.salary_max) == (42000, 48000)
        assert result.period == "year"

    def test_montants_pleins_annuels(self) -> None:
        result = rules.extract_salary("De 38 000 € à 45 000 € par an")
        assert result is not None
        assert (result.salary_min, result.salary_max) == (38000, 45000)

    def test_mensuel(self) -> None:
        result = rules.extract_salary("Salaire : 2 500 € par mois")
        assert result is not None
        assert (result.salary_min, result.salary_max) == (2500, 2500)
        assert result.period == "month"

    def test_tjm(self) -> None:
        result = rules.extract_salary("TJM : 500 € par jour selon expérience")
        assert result is not None
        assert result.salary_min == 500
        assert result.period == "day"

    def test_montant_aberrant_rejete(self) -> None:
        assert rules.extract_salary("Salaire : 600 000 € par an") is None

    def test_montant_trop_faible_rejete(self) -> None:
        assert rules.extract_salary("Prime de 5 000 € par an") is None

    def test_aucun_montant(self) -> None:
        assert rules.extract_salary("Rémunération attractive selon profil") is None

    # --- garde-fous revue : marqueur salarial + itération des matches ---
    def test_montant_sans_marqueur_salarial_ignore(self) -> None:
        # Un montant en devise SANS contexte de rémunération n'est pas un salaire.
        assert rules.extract_salary("Capital de 100 000 €") is None

    def test_montant_aberrant_nabandonne_pas_les_suivants(self) -> None:
        result = rules.extract_salary(
            "Prime de 1 500 € par an. Salaire : 45 000 € brut annuel."
        )
        assert result is not None
        assert (result.salary_min, result.salary_max) == (45000, 45000)
        assert result.period == "year"

    def test_avantage_hors_contexte_puis_salaire_marque(self) -> None:
        result = rules.extract_salary(
            "Tickets restaurant 10 €/jour pris en charge. Salaire : 50 000 € annuel."
        )
        assert result is not None
        assert (result.salary_min, result.salary_max) == (50000, 50000)
        assert result.period == "year"  # « /jour » de la phrase voisine non lu

    def test_periode_adjacente_vaut_marqueur(self) -> None:
        result = rules.extract_salary("De 38 000 € à 45 000 € par an")
        assert result is not None
        assert (result.salary_min, result.salary_max) == (38000, 45000)


class TestExperience:
    def test_5_plus_ans(self) -> None:
        result = rules.extract_experience("5+ ans d'expérience en développement")
        assert result is not None
        assert result.minimum == 5.0
        assert result.maximum is None
        assert result.confidence == 0.85

    def test_3_a_5_ans(self) -> None:
        result = rules.extract_experience("3 à 5 ans d'expérience exigés")
        assert result is not None
        assert (result.minimum, result.maximum) == (3.0, 5.0)

    def test_english_years(self) -> None:
        result = rules.extract_experience("At least 4 years of experience required")
        assert result is not None
        assert result.minimum == 4.0

    def test_5_plus_years(self) -> None:
        result = rules.extract_experience("5+ years of experience with Python")
        assert result is not None
        assert result.minimum == 5.0

    def test_duree_sans_contexte_experience_ignoree(self) -> None:
        assert rules.extract_experience("CDD de 2 ans à pourvoir") is None

    # --- garde-fous revue : adjacence stricte, plus de fenêtre ±60 ---
    def test_anciennete_societe_non_adjacente_ignoree(self) -> None:
        assert rules.extract_experience(
            "Notre société existe depuis 25 ans et recherche un profil avec expérience"
        ) is None

    def test_duree_cdd_et_experience_dans_autre_phrase(self) -> None:
        assert rules.extract_experience(
            "CDD de 2 ans. Une première expérience est demandée."
        ) is None

    def test_experience_avant_le_nombre(self) -> None:
        result = rules.extract_experience("Expérience de 5 ans en gestion de projet")
        assert result is not None
        assert (result.minimum, result.maximum) == (5.0, 5.0)

    def test_experience_deux_points_libelle_france_travail(self) -> None:
        result = rules.extract_experience("expérience : 3 ans")
        assert result is not None
        assert result.minimum == 3.0

    def test_experience_au_moins_apres_le_mot(self) -> None:
        result = rules.extract_experience("Expérience d'au moins 4 ans exigée")
        assert result is not None
        assert result.minimum == 4.0
        assert result.maximum is None

    def test_minimum_x_ans_adjacent_experience(self) -> None:
        result = rules.extract_experience("Minimum 5 ans d'expérience sur Python")
        assert result is not None
        assert result.minimum == 5.0
        assert result.maximum is None


class TestLanguages:
    def test_anglais_courant(self) -> None:
        result = rules.extract_languages("Anglais courant exigé")
        assert result == [rules.LanguageRule("en", "B2", 0.8)]

    def test_fluent_english(self) -> None:
        result = rules.extract_languages("Fluent English required for this role")
        assert result == [rules.LanguageRule("en", "B2", 0.8)]

    def test_bilingue_c2(self) -> None:
        result = rules.extract_languages("Bilingue espagnol souhaité")
        assert result == [rules.LanguageRule("es", "C2", 0.8)]

    def test_niveau_cecrl_explicite(self) -> None:
        result = rules.extract_languages("Allemand niveau B2 minimum")
        assert result == [rules.LanguageRule("de", "B2", 0.8)]

    def test_langue_sans_niveau_non_emise(self) -> None:
        # La langue de rédaction n'est jamais convertie en exigence.
        assert rules.extract_languages("Nous parlons français au bureau") == []

    def test_plusieurs_langues(self) -> None:
        results = rules.extract_languages("Anglais courant et notions d'italien")
        codes = {r.lang_code for r in results}
        assert codes == {"en", "it"}

    # --- garde-fous revue : adjacence langue↔niveau, plus de fenêtre ±30 ---
    def test_niveau_non_adjacent_non_associe(self) -> None:
        # « professionnel » dans la phrase voisine n'est PAS un niveau d'anglais,
        # et « un plus » n'est pas une exigence → rien n'est émis.
        assert rules.extract_languages(
            "environnement professionnel exigeant. L'anglais est un plus."
        ) == []

    def test_cecrl_hors_contexte_non_associe_mais_requis_adjacent(self) -> None:
        # Le « B2 » de l'adresse n'est jamais associé ; « anglais est requis »
        # (motif adjacent) déclenche le défaut B2 🟡 — pas le B2 de l'adresse.
        results = rules.extract_languages(
            "Local B2, avenue de la gare. L'anglais est requis."
        )
        assert results == [rules.LanguageRule("en", "B2", 0.8)]

    def test_langue_requise_sans_motif_adjacent_non_emise(self) -> None:
        # « requis » porte sur autre chose : aucune exigence de langue émise.
        assert rules.extract_languages(
            "Un diplôme est requis. L'anglais sera apprécié au quotidien."
        ) == []

    def test_required_english_adjacent(self) -> None:
        results = rules.extract_languages("English required for this position")
        assert results == [rules.LanguageRule("en", "B2", 0.8)]


class TestSeniority:
    def test_senior(self) -> None:
        result = rules.extract_seniority("Senior Backend Engineer")
        assert result == rules.RuleResult("senior", 0.9)

    def test_junior_fr(self) -> None:
        result = rules.extract_seniority("Développeur junior (H/F)")
        assert result == rules.RuleResult("junior", 0.9)

    def test_lead(self) -> None:
        result = rules.extract_seniority("Lead Developer")
        assert result == rules.RuleResult("lead", 0.9)

    def test_contradictoire(self) -> None:
        assert rules.extract_seniority("Senior or junior welcome") is None

    def test_aucun(self) -> None:
        assert rules.extract_seniority("Data Engineer") is None


class TestDetectLanguage:
    def test_francais(self) -> None:
        code, confidence = rules.detect_language(
            "Nous recherchons pour notre équipe un développeur passionné par le web "
            "et les données. Vous travaillerez dans nos bureaux avec des experts."
        )
        assert code == "fr"
        assert confidence >= 0.7

    def test_anglais(self) -> None:
        code, confidence = rules.detect_language(
            "We are looking for an engineer to join our team. You will work with "
            "the platform and be responsible for our data pipelines."
        )
        assert code == "en"
        assert confidence >= 0.7

    def test_texte_trop_court_confiance_basse(self) -> None:
        _, confidence = rules.detect_language("xyz")
        assert confidence < 0.7
