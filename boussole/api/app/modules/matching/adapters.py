"""Adaptateurs ORM → entrées du moteur pur ``app.matching`` (D02).

Fonctions pures (aucune E/S) : elles reçoivent des instances ORM déjà
chargées et rendent les dataclasses ``CandidateInput`` / ``JobInput``.

Embeddings (M4) — activation SANS régression :

- ``title_embedding`` (offre) est lu directement sur ``job_postings.embedding``
  et ``target_titles_embeddings`` (candidat) sur ``profiles.embedding``,
  complété par les vecteurs d'intitulés cibles (``preference_titles.embedding``)
  fournis via ``title_embeddings`` — ``MatchingService._load_context`` les lit
  par ``MatchingRepository.preference_title_embeddings``. Ce complément n'est
  pas cosmétique : 06 §2.3 prend le MAX des cosinus, et le vecteur agrégé du
  profil (tous les intitulés fondus en un) écrase l'intitulé le mieux ciblé.
  Toutes ces colonnes sont peuplées par ``ai.embeddings.*`` (08 §8) ;
- **quand un vecteur manque d'un côté, le comportement est EXACTEMENT celui
  d'avant** : ``title_similarity`` reste inconnue (k=0) et le crédit
  « proche » reste désactivé (match exact uniquement). Aucune offre ni
  aucun profil ne change de score tant que les vecteurs n'existent pas ;
- ``skill_embeddings`` (crédit « proche » 0,5, 06 §2.1, seuil 0,75) est
  alimenté par le paramètre optionnel ``skill_embeddings`` :
  ``skill_id`` → vecteur (``skills.embedding``). Il est branché en
  production : ``MatchingService._load_context`` lit
  ``MatchingRepository.skill_embeddings`` et passe le MÊME dictionnaire aux
  DEUX côtés (candidat *et* offre). Les deux sont nécessaires :
  ``matching/dimensions.py`` n'accorde le crédit « proche » que si le libellé
  exigé par l'offre porte lui aussi un vecteur — n'en fournir qu'un seul côté
  laisse le crédit définitivement mort.

Hypothèses M3 🟡 :
- labels de compétences : canonique de la taxonomie via ``skill_id`` quand le
  rapprochement existe, sinon ``label_raw`` normalisé (trim — le moteur
  casefold lui-même) ;
- colonnes de confiance absentes du schéma (secteur, expérience, salaire,
  localisation) → confiance 1,0 ; ``*_conf`` null → 1,0 (attribut posé par
  les règles déterministes de l'ingestion) ;
- ``salary_period`` ``day``/``hour`` non supporté par le moteur → salaire
  traité comme non communiqué (dimension inconnue) plutôt qu'une erreur ;
- ``sector_parent`` / ``sector_parents`` non alimentés (référentiel des
  parents non chargé au M3) → le score « adjacent » ne s'applique pas ;
- préférences absentes → défauts produit du module preferences (remote
  ``indifferent``, ``contract_types=[permanent]``, listes vides) ;
- les préférences ne capturent qu'un salaire minimum souhaité →
  ``salary_expected_max`` reste ``None`` (borne ouverte, complétée par le
  padding du moteur).
"""

import uuid
from collections.abc import Mapping, Sequence
from typing import Literal, cast

from app.matching.models import (
    CandidateInput,
    CandidateLocation,
    Confident,
    JobInput,
    RemotePreference,
    Vector,
)
from app.matching.models import JobLanguage as EngineJobLanguage
from app.matching.models import JobLocation as EngineJobLocation
from app.matching.models import JobSkill as EngineJobSkill
from app.modules.jobs.models import JobLanguage, JobLocation, JobPosting, JobSkill
from app.modules.preferences.repository import PreferencesData
from app.modules.profiles.models import Profile

__all__ = ["candidate_input_from", "job_input_from"]

#: Périodes de salaire supportées par le moteur (06 §2.11).
_SUPPORTED_SALARY_PERIODS = ("year", "month")

#: Défauts produit du module preferences (🟡 alignés sur
#: ``preferences.service.default_preferences``).
_DEFAULT_REMOTE_PREF = "indifferent"
_DEFAULT_CONTRACT_TYPES = ("permanent",)


def _vector(raw: Sequence[float] | None) -> Vector | None:
    """Colonne pgvector → tuple de flottants ; ``None`` si absente ou vide.

    ``None`` et vecteur vide sont traités pareil : le moteur les lit comme
    « donnée absente » (k=0), jamais comme un vecteur nul — un vecteur nul
    donnerait un cosinus de 0,0 présenté comme un FAIT (« métier très
    éloigné »), alors que la donnée est simplement manquante.
    """
    if raw is None:
        return None
    vector = tuple(float(value) for value in raw)
    return vector or None


def _skill_vectors(
    skills: Sequence[tuple[uuid.UUID | None, str]],
    taxonomy: Mapping[uuid.UUID, str],
    embeddings: Mapping[uuid.UUID, Sequence[float]] | None,
) -> dict[str, Vector]:
    """``label utilisé par le moteur`` → vecteur, pour les compétences résolues.

    Seules les compétences rapprochées de la taxonomie (``skill_id`` non
    nul) portent un vecteur : ``skills.embedding`` est indexé par
    compétence canonique, pas par libellé brut.
    """
    if not embeddings:
        return {}
    vectors: dict[str, Vector] = {}
    for skill_id, label_raw in skills:
        if skill_id is None:
            continue
        vector = _vector(embeddings.get(skill_id))
        if vector is not None:
            vectors[_skill_label(skill_id, label_raw, taxonomy)] = vector
    return vectors


def _skill_label(
    skill_id: uuid.UUID | None, label_raw: str, taxonomy: Mapping[uuid.UUID, str]
) -> str:
    """Label canonique si le rapprochement taxonomie existe, sinon brut trimé."""
    if skill_id is not None:
        canonical = taxonomy.get(skill_id)
        if canonical:
            return canonical
    return label_raw.strip()


def _dedupe(labels: Sequence[str]) -> tuple[str, ...]:
    """Déduplique en préservant l'ordre (insensible à la casse)."""
    seen: set[str] = set()
    result: list[str] = []
    for label in labels:
        key = label.casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(label)
    return tuple(result)


def candidate_input_from(
    profile: Profile,
    preferences: PreferencesData | None,
    skills_taxonomy: Mapping[uuid.UUID, str],
    *,
    title_embeddings: Sequence[Sequence[float]] = (),
    skill_embeddings: Mapping[uuid.UUID, Sequence[float]] | None = None,
) -> CandidateInput:
    """Construit l'entrée candidat du moteur depuis le profil validé + préférences.

    ``skills_taxonomy`` : ``skill_id`` → label canonique (table ``skills``).
    ``title_embeddings`` : vecteurs des intitulés cibles
    (``preference_titles.embedding``) — 06 §2.3 prend le MAX des cosinus, un
    vecteur par intitulé est donc plus fidèle que le vecteur agrégé du
    profil ; les deux sont cumulés quand ils existent.
    ``skill_embeddings`` : ``skill_id`` → ``skills.embedding`` (crédit
    « proche » 0,5). Omis → match exact uniquement, comme avant.
    """
    skills = _dedupe(
        [
            _skill_label(skill.skill_id, skill.label_raw, skills_taxonomy)
            for skill in profile.skills
        ]
    )
    sectors_experienced = frozenset(
        exp.sector_code for exp in profile.experiences if exp.sector_code
    )
    languages = {lang.lang_code: lang.level for lang in profile.languages}

    if preferences is None:
        remote_pref = _DEFAULT_REMOTE_PREF
        contract_types: tuple[str, ...] = _DEFAULT_CONTRACT_TYPES
        contract_strict = False
        salary_min: int | None = None
        salary_min_strict: int | None = None
        locations: tuple[CandidateLocation, ...] = ()
        sectors_preferred: frozenset[str] = frozenset()
        sectors_excluded: frozenset[str] = frozenset()
        target_companies: frozenset[str] = frozenset()
        keywords: tuple[str, ...] = ()
    else:
        remote_pref = preferences.remote_pref
        contract_types = preferences.contract_types or _DEFAULT_CONTRACT_TYPES
        contract_strict = preferences.contract_strict
        salary_min = preferences.salary_min
        salary_min_strict = preferences.salary_min_strict
        locations = tuple(
            CandidateLocation(lat=loc.lat, lon=loc.lon, radius_km=float(loc.radius_km))
            for loc in preferences.locations
        )
        sectors_preferred = frozenset(preferences.sectors_preferred)
        sectors_excluded = frozenset(preferences.sectors_excluded)
        target_companies = frozenset(preferences.target_companies)
        keywords = tuple(preferences.keywords)

    # 06 §2.3 : max des cosinus sur les intitulés du candidat. On cumule les
    # vecteurs par intitulé cible (les plus fidèles) et le vecteur agrégé du
    # profil (intitulés cibles + occupés). Vide → k=0, comme avant.
    candidate_titles = [
        vector for vector in (_vector(raw) for raw in title_embeddings) if vector is not None
    ]
    profile_vector = _vector(profile.embedding)
    if profile_vector is not None:
        candidate_titles.append(profile_vector)

    return CandidateInput(
        skills=skills,
        skill_embeddings=_skill_vectors(
            [(skill.skill_id, skill.label_raw) for skill in profile.skills],
            skills_taxonomy,
            skill_embeddings,
        ),
        target_titles_embeddings=tuple(candidate_titles),
        seniority=profile.seniority,
        total_experience_years=(
            None
            if profile.total_experience_years is None
            else float(profile.total_experience_years)
        ),
        sectors_preferred=sectors_preferred,
        sectors_excluded=sectors_excluded,
        sectors_experienced=sectors_experienced,
        locations=locations,
        remote_pref=cast(RemotePreference, remote_pref),
        languages=languages,
        contract_types=frozenset(contract_types),
        contract_strict=contract_strict,
        salary_expected_min=None if salary_min is None else float(salary_min),
        salary_expected_max=None,  # 🟡 le produit ne capture qu'un minimum souhaité
        salary_min_strict=None if salary_min_strict is None else float(salary_min_strict),
        target_companies=target_companies,
        keywords=keywords,
    )


def _confident(value: str | None, confidence: float | None) -> Confident | None:
    """``Confident`` depuis colonne + ``*_conf`` (null → 1,0 🟡)."""
    if value is None:
        return None
    return Confident(value=value, confidence=1.0 if confidence is None else float(confidence))


def job_input_from(
    job_posting: JobPosting,
    job_skills: Sequence[JobSkill],
    job_languages: Sequence[JobLanguage],
    job_locations: Sequence[JobLocation],
    skills_taxonomy: Mapping[uuid.UUID, str] | None = None,
    *,
    skill_embeddings: Mapping[uuid.UUID, Sequence[float]] | None = None,
    embedding_model: str | None = None,
) -> JobInput:
    """Construit l'entrée offre du moteur — chaque champ extrait porte sa confiance.

    Les confiances proviennent des colonnes ``*_conf`` (item par item pour les
    compétences et langues) ; les champs sans colonne de confiance dans le
    schéma valent 1,0 🟡 (voir docstring du module).

    ``title_embedding`` est lu sur ``job_postings.embedding`` (« intitulé +
    1er paragraphe », 06 §2.3) : absent → ``title_similarity`` inconnue
    (k=0), exactement comme avant les embeddings.

    ``embedding_model`` : identifiant du modèle qui a produit ce vecteur. Le
    moteur le rapproche du ``calibrated_for_model`` de la dimension et rend la
    dimension INCONNUE en cas de discordance — un cosinus lu avec les seuils
    d'un autre modèle est une mesure fausse, pas imprécise (N14).

    🟡 **Approximation assumée** : la valeur passée est celle du provider
    ACTIF, pas celle qui a réellement produit la ligne. `job_postings` ne
    porte pas encore de colonne `embedding_model_version` (§8.2 item 12) ;
    tant qu'elle n'existe pas, un vecteur calculé par un modèle précédent est
    indiscernable d'un vecteur à jour. Le rapprochement reste utile — il
    attrape le cas courant, celui où la configuration n'a jamais été calibrée
    — mais il ne remplace pas cette colonne.
    """
    taxonomy: Mapping[uuid.UUID, str] = skills_taxonomy or {}

    def _engine_skill(skill: JobSkill) -> EngineJobSkill:
        return EngineJobSkill(
            label=_skill_label(skill.skill_id, skill.label_raw, taxonomy),
            confidence=float(skill.confidence),
        )

    skills_required = tuple(_engine_skill(s) for s in job_skills if s.required)
    skills_nice = tuple(_engine_skill(s) for s in job_skills if not s.required)

    locations = tuple(
        EngineJobLocation(lat=loc.lat, lon=loc.lon)
        for loc in job_locations
        if loc.lat is not None and loc.lon is not None
    )
    languages_required = tuple(
        EngineJobLanguage(
            code=lang.lang_code, level=lang.min_level, confidence=float(lang.confidence)
        )
        for lang in job_languages
    )

    # 🟡 Périodes day/hour non supportées par le moteur (06 §2.11) : le salaire
    # est traité comme non communiqué plutôt que de lever une erreur.
    salary_period_raw = job_posting.salary_period or "year"
    if salary_period_raw in _SUPPORTED_SALARY_PERIODS:
        salary_min = None if job_posting.salary_min is None else float(job_posting.salary_min)
        salary_max = None if job_posting.salary_max is None else float(job_posting.salary_max)
        salary_period = cast(Literal["year", "month"], salary_period_raw)
    else:
        salary_min = None
        salary_max = None
        salary_period = "year"

    return JobInput(
        skills_required=skills_required,
        skills_nice=skills_nice,
        skill_embeddings=_skill_vectors(
            [(skill.skill_id, skill.label_raw) for skill in job_skills],
            taxonomy,
            skill_embeddings,
        ),
        title_embedding=_vector(job_posting.embedding),
        title_embedding_model=embedding_model,
        seniority=_confident(job_posting.seniority, job_posting.seniority_conf),
        experience_min=(
            None if job_posting.experience_min is None else float(job_posting.experience_min)
        ),
        experience_max=(
            None if job_posting.experience_max is None else float(job_posting.experience_max)
        ),
        experience_confidence=1.0,  # 🟡 pas de colonne de confiance dédiée
        sector=_confident(job_posting.sector_code, None),  # 🟡 confiance 1,0
        sector_parent=None,  # 🟡 parents sectoriels non chargés au M3
        locations=locations,
        location_confidence=1.0,  # 🟡 pas de colonne de confiance dédiée
        remote=_confident(job_posting.remote, job_posting.remote_conf),
        languages_required=languages_required,
        contract=_confident(job_posting.contract, job_posting.contract_conf),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=salary_period,
        salary_currency=job_posting.salary_currency or "EUR",
        salary_confidence=1.0,  # 🟡 pas de colonne de confiance dédiée
        company_name=job_posting.company_name,
        description_text=job_posting.description_text,
    )
