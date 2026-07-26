"""Tâche ``extract_job`` — étage 2 de secours (07 §5.2, 08 §2).

Appelée UNIQUEMENT quand les règles déterministes laissent des attributs
clés inconnus, et pour ``job_skills`` (extraction sémantique). Modèles
Pydantic fidèles à ``ai-output-schemas.json#job_extraction`` : sortie du
provider validée strictement ; échec de validation → 1 retry avec le
message d'erreur, puis échec propre (repair-parse 🟡 M3, D08). Les valeurs
de l'étage 1 PRIMENT toujours sur celles de l'étage 2.

Branché sur :class:`FakeProvider` par défaut — provider réel M3+ 🟡.
"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_VERSION = "extract_job/1.0.0"  # versionnement des prompts (D08)

_Seniority = Literal["intern", "junior", "mid", "senior", "lead", "principal", "executive"]
_Contract = Literal["permanent", "fixed_term", "freelance", "internship",
                    "apprenticeship", "other"]
_Remote = Literal["onsite", "hybrid", "full_remote"]
_SalaryPeriod = Literal["year", "month", "day", "hour"]
_Cefr = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

class Evidence(BaseModel):
    """Citation exacte du texte source (ancrage anti-hallucination)."""

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(max_length=500)


class ExtractedSkill(BaseModel):
    """Compétence extraite avec confiance et citation."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(max_length=100)
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence


class ExtractedLanguage(BaseModel):
    """Exigence de langue extraite (code ISO 639-1 + niveau CECRL)."""

    model_config = ConfigDict(extra="forbid")

    lang_code: str = Field(pattern=r"^[a-z]{2}$")
    min_level: _Cefr
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence


class JobExtraction(BaseModel):
    """Sortie validée du schéma ``job_extraction`` (ai-output-schemas.json)."""

    model_config = ConfigDict(extra="forbid")

    seniority: _Seniority | None = None
    seniority_confidence: float | None = Field(default=None, ge=0, le=1)
    experience_min_years: float | None = None
    experience_max_years: float | None = None
    contract: _Contract | None = None
    contract_confidence: float | None = Field(default=None, ge=0, le=1)
    remote: _Remote | None = None
    remote_confidence: float | None = Field(default=None, ge=0, le=1)
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_period: _SalaryPeriod | None = None
    sector_code: str | None = None
    skills_required: list[ExtractedSkill]
    skills_nice: list[ExtractedSkill]
    languages: list[ExtractedLanguage]
    warnings: list[str] = Field(default_factory=list)


class JobExtractionError(RuntimeError):
    """Échec propre de l'étage 2 : l'offre est publiée avec les seuls
    attributs déterministes (07 §5.2, compteur ``job_extraction_failed``)."""


_PROMPT_TEMPLATE = (
    "Tu extrais des attributs structurés d'une offre d'emploi.\n"
    "Réponds UNIQUEMENT avec un JSON conforme au schéma job_extraction.\n"
    "Chaque item porte une confiance [0,1] et une citation exacte du texte.\n"
    "N'invente RIEN : attribut absent du texte => null.\n\n"
    "--- OFFRE (texte sanitisé, étage 0) ---\n{text}\n--- FIN OFFRE ---"
)


def extract_job(text: str, provider: LLMProvider) -> JobExtraction:
    """Extraction de secours d'une offre (texte SANITISÉ uniquement, 08 §6).

    Validation stricte de la sortie ; 1 retry avec le message d'erreur en
    cas d'échec, puis :class:`JobExtractionError` (repair-parse 🟡 M3).
    Cache par (offre, prompt_version) géré par l'appelant (R7).
    """
    prompt = _PROMPT_TEMPLATE.format(text=text)
    schema: dict[str, Any] = JobExtraction.model_json_schema()

    last_error: ValidationError | None = None
    for attempt in range(2):
        current_prompt = prompt
        if last_error is not None:
            current_prompt = (
                f"{prompt}\n\nTa précédente réponse était invalide :\n{last_error}\n"
                "Corrige et renvoie un JSON strictement conforme."
            )
        raw = provider.complete_json("extract_job", current_prompt, schema)
        try:
            return JobExtraction.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            logger.warning("job_extraction_invalid attempt=%d", attempt + 1)
    raise JobExtractionError(f"sortie invalide après retry : {last_error}")
