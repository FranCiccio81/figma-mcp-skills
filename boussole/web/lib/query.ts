import { QueryClient } from "@tanstack/react-query";
import { isApiProblem } from "@/lib/api/client";

/**
 * QueryClient Boussole.
 *
 * Politique de retry : jamais sur les 4xx (401 session expirée, 404 anti-énumération,
 * 409 métier, 422 validation, 429 rate limit — rejouer aggraverait le quota) ;
 * 2 tentatives max sinon (erreurs réseau / 5xx).
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (isApiProblem(error) && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 2;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}
