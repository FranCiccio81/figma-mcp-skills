/** Intervalle initial du polling des opérations asynchrones (12 §1 : 2 s). */
export const POLL_INITIAL_MS = 2_000;

/** Facteur de backoff entre deux polls (12 §1 : ×1,5). */
export const POLL_BACKOFF_FACTOR = 1.5;

/** Plafond de l'intervalle — évite un backoff illimité sur un parsing long. 🟡 */
export const POLL_MAX_MS = 15_000;

/**
 * Délai avant le prochain poll pour une tentative donnée (0-indexée) :
 * 2 s, 3 s, 4,5 s… plafonné à {@link POLL_MAX_MS} (pattern 12 §1).
 */
export function pollDelay(attempt: number): number {
  return Math.min(POLL_INITIAL_MS * POLL_BACKOFF_FACTOR ** Math.max(0, attempt), POLL_MAX_MS);
}

/** Sous-ensemble structurel de `Query` (TanStack) utilisé par le calcul d'intervalle. */
interface PollingQueryLike<TData> {
  state: {
    data?: TData;
    error: unknown;
    /** Nombre de fetches réussis — sert de compteur de backoff. */
    dataUpdateCount: number;
  };
}

/**
 * Fabrique un `refetchInterval` TanStack Query pour suivre une ressource
 * asynchrone (parsing CV, génération…) : tant que `isSettled(data)` est faux,
 * re-fetch avec backoff 2 s ×1,5 (12 §1) ; dès que la ressource est stabilisée
 * (ou en erreur), le polling s'arrête. Aucun état local nécessaire côté
 * composant — `dataUpdateCount` sert de compteur de tentatives.
 */
export function makePollingInterval<TData>(isSettled: (data: TData | undefined) => boolean) {
  return (query: PollingQueryLike<TData>): number | false => {
    if (query.state.error) return false;
    if (isSettled(query.state.data)) return false;
    return pollDelay(query.state.dataUpdateCount);
  };
}
