# 12 — Contrats API

> API REST FastAPI, préfixe `/api/v1`. Spécification machine : `openapi.yaml` (source de vérité pour les schémas). Ce document fixe les conventions et donne des exemples.

## 1. Conventions transverses

- **Authentification** : session par cookie httpOnly `Secure; SameSite=Lax` posé par `POST /auth/login` (session Redis, TTL 30 j glissants). Le front Next proxifie en même origine (D11). CSRF : double-submit token (`X-CSRF-Token`) sur toute méthode mutante. Pas d'API publique tierce au MVP.
- **Erreurs** : RFC 9457 `application/problem+json` — champs `type`, `title`, `status`, `detail`, `errors[]` (violations de champ), `trace_id`. Codes stables documentés par endpoint (`profile_not_validated`, `job_expired`, `generation_not_validated`…).
- **Pagination** : par curseur — `?limit=20&cursor=<opaque>` → réponse `{ items: [...], next_cursor: string|null }`. `limit` max 100. Jamais d'offset (résultats mouvants).
- **Idempotence** : toute création coûteuse ou à effet (POST `/generations`, `/applications`, `/privacy/export`) accepte l'en-tête `Idempotency-Key` (UUID, TTL 24 h, portée utilisateur) : rejouer la même clé renvoie la réponse d'origine (200/201 avec `Idempotent-Replay: true`). L'ingestion interne est idempotente par `(source_id, external_ref)`.
- **Rate limiting** (Redis, par utilisateur puis par IP) : global 60 req/min ; recherche 30/min ; générations LLM 10/h et 40/j ; upload CV 5/j ; export données 2/j. Réponse 429 + `Retry-After`.
- **Asynchrone** : les opérations longues (parsing CV, génération, export) répondent `202 { task: { id, status } }` ; l'état se lit sur la ressource (`GET /cv-documents/{id}`, `/generations/{id}`…). Polling recommandé : 2 s, backoff ×1,5, TanStack Query côté front.
- **Versionnement** : chemin `/v1` ; champs additifs sans bump ; breaking → `/v2`.
- **I18n** : `Accept-Language` (fr par défaut) pour les libellés d'erreurs et d'explications déterministes.

## 2. Inventaire des endpoints

| Domaine | Méthode + chemin | Rôle | Auth |
|---|---|---|---|
| Auth | `POST /auth/register` | création de compte (email+mdp, consentements) | — |
| | `POST /auth/login` / `POST /auth/logout` | session | — / ✔ |
| | `POST /auth/password-reset/request` / `.../confirm` | réinitialisation | — |
| | `GET /me` | utilisateur courant + état d'onboarding | ✔ |
| CV | `POST /cv-documents` | upload PDF/DOCX (multipart, ≤ 10 Mo) → 202, parsing async | ✔ |
| | `GET /cv-documents/{id}` | statut parsing + résultat d'extraction | ✔ |
| Profil | `GET /profile` | profil complet avec provenance et confiance par champ | ✔ |
| | `PATCH /profile` | champs racine (headline, summary, seniority) | ✔ |
| | `POST/PATCH/DELETE /profile/experiences[/{id}]` | CRUD expériences (idem educations, skills, languages) | ✔ |
| | `POST /profile/validate` | valide le profil (promeut la provenance, exige ≥ 3 compétences, ≥ 1 expérience ou formation) | ✔ |
| Préférences | `GET /preferences` / `PUT /preferences` | lecture / remplacement complet (payload unique avec listes imbriquées) | ✔ |
| Offres | `GET /jobs` | recherche + filtres + tri (`sort=match|date|relevance`) | ✔ |
| | `GET /jobs/{id}` | détail + sources + lien(s) d'origine | ✔ |
| | `GET /jobs/{id}/match` | score, confiance, bloquants, inconnues, dimensions | ✔ |
| | `POST /jobs/{id}/explanation` | reformulation LLM des faits (cache par version) | ✔ |
| | `PUT /jobs/{id}/saved-state` / `DELETE` | sauvegarder ou masquer / retirer | ✔ |
| Matches | `GET /matches` | liste classée des offres scorées pour le profil | ✔ |
| Générations | `GET /generations` | bibliothèque des contenus générés (filtres `doc_type`, `status`, `job_id`) | ✔ |
| | `POST /generations` | crée un brouillon (email, lettre, cv_variant, cv_optimization) → 202 | ✔ |
| | `GET /generations/{id}` | statut + contenu + claims d'ancrage | ✔ |
| | `PATCH /generations/{id}` | édition manuelle du brouillon | ✔ |
| | `POST /generations/{id}/validate` | validation humaine (D10) | ✔ |
| | `POST /generations/{id}/export` | export (copie/PDF/DOCX) — exige `validated` | ✔ |
| Candidatures | `GET/POST /applications`, `GET/PATCH/DELETE /applications/{id}` | suivi (offres internes ou externes) | ✔ |
| | `POST /applications/{id}/status` | transition de statut + note (historisée) | ✔ |
| Privacy | `POST /privacy/export` → `GET /privacy/exports/{id}` | export RGPD (archive JSON, lien signé 7 j) | ✔ |
| | `DELETE /account` | suppression (soft immédiat, purge J+30) — confirmation par mot de passe | ✔ |
| Meta | `GET /sources` | transparence : sources actives, nature, fraîcheur | ✔ |
| | `GET /healthz` / `GET /readyz` | liveness / readiness | interne |

## 3. Paramètres de recherche `GET /jobs`

`q` (texte libre), `location_id` (référence à une preference_location) ou `lat,lon,radius_km`, `remote[]`, `contract[]`, `seniority[]`, `language`, `salary_min`, `posted_since` (jours), `source[]`, `include_blocked` (défaut `true` — badgées, jamais silencieusement retirées), `include_hidden` (défaut `false`), `saved_only` (défaut `false`), `sort` (`match` par défaut si profil validé, sinon `relevance`), `limit`, `cursor`.

## 4. Exemples

**`GET /jobs/{id}/match` → 200**
```json
{
  "job_id": "8b1e…", "profile_version": 4, "scoring_version": "1.0.0",
  "score": 72, "confidence": 61, "low_data": false,
  "blocking_criteria": [],
  "unknown_dimensions": [
    { "dimension": "salary", "reason": "job_not_provided", "label": "Salaire non communiqué" },
    { "dimension": "seniority", "reason": "job_not_provided", "label": "Niveau non précisé dans l'offre" }
  ],
  "dimensions": [
    { "dimension": "skills_required", "subscore": 0.86, "weight": 25, "known": true,
      "details": { "matched": ["python", "fastapi", "postgresql"], "related": [{"required": "aws", "matched_with": "gcp"}], "missing": ["kubernetes"] } },
    { "dimension": "location", "subscore": 1.0, "weight": 8, "known": true,
      "details": { "distance_km": 4.2, "matched_location": "Lyon" } }
  ]
}
```

**`POST /generations` (Idempotency-Key requis)**
```json
{ "doc_type": "cover_letter", "job_id": "8b1e…", "options": { "tone": "sobre", "language": "fr", "length": "standard" } }
```
→ `202 { "id": "c91a…", "status": "pending" }` puis `GET /generations/c91a…` :
```json
{
  "id": "c91a…", "doc_type": "cover_letter", "status": "draft",
  "based_on_profile_version": 4, "prompt_version": "cover_letter@1.2.0",
  "content": { "body": "…", "claims": [ { "claim": "5 ans d'expérience backend", "profile_ref": "experience:2f00…" } ] },
  "anchoring_check": { "status": "passed", "unanchored_claims": [] }
}
```

**Erreur type — export non validé (`POST /generations/{id}/export`) → 409**
```json
{ "type": "https://api.boussole.eu/errors/generation_not_validated",
  "title": "Validation requise", "status": 409,
  "detail": "Ce document doit être relu et validé avant export.", "trace_id": "…" }
```

## 5. Sécurité des contrats

- Toutes les ressources sont scopées utilisateur ; l'accès à une ressource d'autrui → 404 (pas 403, anti-énumération).
- Upload CV : validation MIME réelle (magic bytes), scan antivirus 🟡 (ClamAV), taille ≤ 10 Mo, types `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.
- Aucune donnée de profil dans les URL ; identifiants UUID non séquentiels.
- CORS fermé (même origine via proxy Next) ; en-têtes de sécurité (CSP, HSTS) posés par le front/edge.
