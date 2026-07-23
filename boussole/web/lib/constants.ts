/** Préfixe des appels API côté navigateur — proxifiés en même origine (12 §1, D11). */
export const API_BASE_PATH = "/api/v1";

/** Cookie de session httpOnly posé par `POST /auth/login` (openapi.yaml → cookieAuth). */
export const SESSION_COOKIE_NAME = "boussole_session";

/**
 * Cookie CSRF double-submit, lisible par JS, posé par l'API (12 §1).
 * Sa valeur est renvoyée dans l'en-tête `X-CSRF-Token` sur toute méthode mutante.
 * 🟡 Nom à confirmer avec le back (non spécifié dans openapi.yaml).
 */
export const CSRF_COOKIE_NAME = "boussole_csrf";

/**
 * Versions des consentements envoyées à `POST /auth/register` (D09).
 * 🟡 À synchroniser avec les documents juridiques publiés.
 */
export const CONSENT_TERMS_VERSION = "2026-07";
export const CONSENT_PRIVACY_VERSION = "2026-07";
