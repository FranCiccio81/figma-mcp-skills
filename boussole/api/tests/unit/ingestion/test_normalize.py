"""Tests de la normalisation de dédup (07 §6.1) : norm, hash, localisation."""

import hashlib

from app.modules.ingestion.normalize import (
    compute_dedup_hash,
    norm,
    norm_company,
    norm_location,
    strip_html,
)


class TestNorm:
    def test_accents_et_casse(self) -> None:
        assert norm("Développeur Sénior") == "developpeur senior"

    def test_nfkc_ligatures_et_espaces_insecables(self) -> None:
        # NFKC décompose ﬁ (ligature) et l'espace insécable.
        assert norm("Œuvre ﬁnale") == "œuvre finale" or norm("ﬁnale") == "finale"

    def test_ponctuation_remplacee_par_espace(self) -> None:
        assert norm("Full-Stack (H/F) / CDI, Paris.") == "full stack h f cdi paris"

    def test_compactage_espaces(self) -> None:
        assert norm("  data   engineer  ") == "data engineer"

    def test_casefold(self) -> None:
        assert norm("STRASSE straße") == "strasse strasse"


class TestNormCompany:
    def test_suffixe_juridique_terminal(self) -> None:
        assert norm_company("ACME SAS") == "acme"
        assert norm_company("Vinci SA") == "vinci"
        assert norm_company("Initech GmbH") == "initech"

    def test_groupe_en_tete(self) -> None:
        assert norm_company("Groupe ACME") == "acme"
        assert norm_company("Group Initech Ltd") == "initech"

    def test_ne_vide_jamais_la_chaine(self) -> None:
        assert norm_company("SAS") == "sas"

    def test_sans_suffixe(self) -> None:
        assert norm_company("Café de la Gare") == "cafe de la gare"


class TestNormLocation:
    def test_ville_geocodee(self) -> None:
        assert norm_location(city="Lyon", country_code="FR") == "fr:lyon"

    def test_full_remote_avec_pays(self) -> None:
        assert norm_location(full_remote=True, country_code="FR") == "remote:fr"

    def test_full_remote_sans_pays(self) -> None:
        assert norm_location(full_remote=True) == "remote:"

    def test_libelle_brut(self) -> None:
        assert norm_location(raw_label="75 - PARIS 09") == "75 paris 09"

    def test_vide(self) -> None:
        assert norm_location() == ""


class TestComputeDedupHash:
    def test_separateur_x1f_et_sha256(self) -> None:
        expected_payload = "\x1f".join(["acme", "data engineer", "fr:lyon", "req 42"])
        expected = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
        assert compute_dedup_hash("ACME SAS", "Data Engineer", "fr:lyon", "REQ-42") == expected

    def test_stable_aux_variations_de_forme(self) -> None:
        h1 = compute_dedup_hash("ACME SAS", "Développeur Sénior (H/F)", "fr:paris", None)
        h2 = compute_dedup_hash("Groupe acme", "developpeur senior h/f", "fr:paris", "")
        assert h1 == h2

    def test_sensible_a_la_reference_employeur(self) -> None:
        h1 = compute_dedup_hash("ACME", "Data Engineer", "fr:lyon", "REQ-1")
        h2 = compute_dedup_hash("ACME", "Data Engineer", "fr:lyon", "REQ-2")
        assert h1 != h2

    def test_champ_vide_sans_collision_de_position(self) -> None:
        # \x1f garantit que ("ab","c") != ("a","bc").
        h1 = compute_dedup_hash("ab", "c", "", "")
        h2 = compute_dedup_hash("a", "bc", "", "")
        assert h1 != h2


class TestStripHtml:
    def test_html_vers_texte(self) -> None:
        html = "<div><p>Hello <strong>world</strong></p><script>evil()</script></div>"
        assert strip_html(html) == "Hello world"

    def test_html_echappe_greenhouse(self) -> None:
        escaped = "&lt;p&gt;We are &lt;em&gt;hiring&lt;/em&gt;.&lt;/p&gt;"
        assert strip_html(escaped) == "We are hiring ."

    def test_idempotent_sur_texte_brut(self) -> None:
        assert strip_html("Texte simple, sans balise.") == "Texte simple, sans balise."
