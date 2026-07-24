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
