"""Tests de la taxonomie de compétences (07 §5.5)."""

import uuid

from app.modules.ingestion.taxonomy import SkillResolver, canonicalize


class TestCanonicalize:
    def test_lowercase_unaccent_trim(self) -> None:
        assert canonicalize("  Développement  Web  ") == "developpement web"

    def test_ponctuation_terminale(self) -> None:
        assert canonicalize("PostgreSQL.") == "postgresql"
        assert canonicalize("React.js") == "react.js"  # point interne conservé


class TestSkillResolver:
    def test_alias_exact_casefold(self) -> None:
        skill_id = uuid.uuid4()
        resolver = SkillResolver(aliases={"react.js": skill_id})
        assert resolver.resolve("React.JS") == skill_id
        assert resolver.resolve("react.js.") == skill_id  # ponctuation terminale

    def test_canonical_label_en_second(self) -> None:
        skill_id = uuid.uuid4()
        resolver = SkillResolver(canonicals={"PostgreSQL": skill_id})
        assert resolver.resolve("postgresql") == skill_id

    def test_alias_prioritaire_sur_canonique(self) -> None:
        alias_target = uuid.uuid4()
        canonical_target = uuid.uuid4()
        resolver = SkillResolver(
            aliases={"postgres": alias_target},
            canonicals={"postgres": canonical_target},
        )
        assert resolver.resolve("Postgres") == alias_target

    def test_non_rattache_renvoie_none(self) -> None:
        resolver = SkillResolver(aliases={"react": uuid.uuid4()})
        # label_raw conservé côté job_skills, skill_id NULL (07 §5.5.4)
        assert resolver.resolve("compétence inconnue") is None

    def test_label_vide(self) -> None:
        assert SkillResolver().resolve("   ") is None
