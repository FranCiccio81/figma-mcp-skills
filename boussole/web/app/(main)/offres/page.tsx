"use client";

// SCR-20 — M2
// Recherche & liste d'offres (Flux 3) : recherche `q` (debounce 300 ms),
// filtres en panneau accessible, tri date/pertinence, pagination par curseur
// (« Charger plus », jamais de scroll infini sans bouton), actions
// sauvegarder/masquer optimistes avec rollback. État piloté par l'URL
// (partage / rafraîchissement). Le tri `match` et les scores arrivent au M3.

import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { SearchX } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { JobCard } from "@/components/jobs/job-card";
import { JobFilters, type JobFiltersValue } from "@/components/jobs/job-filters";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { getNextCursor, isApiProblem } from "@/lib/api/client";
import {
  clearSavedState,
  getSources,
  jobsKeys,
  searchJobs,
  setSavedState,
  type JobSearchParams,
} from "@/lib/api/jobs";
import type {
  ContractType,
  JobSort,
  RemotePolicy,
  SavedState,
  SearchPage,
} from "@/lib/api/types";

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

const REMOTE_VALUES: ReadonlySet<string> = new Set(["onsite", "hybrid", "full_remote"]);
const CONTRACT_VALUES: ReadonlySet<string> = new Set([
  "permanent",
  "fixed_term",
  "freelance",
  "internship",
  "apprenticeship",
  "other",
]);

/** État complet de l'écran, sérialisé dans l'URL (`?q=…&remote=…`). */
interface ListState extends JobFiltersValue {
  q: string;
  /** M2 : `relevance` (défaut) ou `date` — le tri `match` attend le jalon M3. */
  sort: Extract<JobSort, "relevance" | "date">;
}

function parseIntOrNull(raw: string | null): number | null {
  if (!raw) return null;
  const parsed = Number.parseInt(raw, 10);
  return Number.isNaN(parsed) || parsed < 0 ? null : parsed;
}

/** Lit l'état de l'écran depuis les `searchParams` (valeurs inconnues ignorées). */
function parseListState(searchParams: URLSearchParams): ListState {
  return {
    q: searchParams.get("q") ?? "",
    remote: searchParams.getAll("remote").filter((v): v is RemotePolicy => REMOTE_VALUES.has(v)),
    contract: searchParams
      .getAll("contract")
      .filter((v): v is ContractType => CONTRACT_VALUES.has(v)),
    salaryMin: parseIntOrNull(searchParams.get("salary_min")),
    postedSince: parseIntOrNull(searchParams.get("posted_since")),
    savedOnly: searchParams.get("saved_only") === "1",
    sort: searchParams.get("sort") === "date" ? "date" : "relevance",
  };
}

/** Sérialise l'état vers l'URL — mêmes noms que les paramètres de `GET /jobs`. */
function serializeListState(state: ListState): string {
  const search = new URLSearchParams();
  if (state.q) search.set("q", state.q);
  for (const remote of state.remote) search.append("remote", remote);
  for (const contract of state.contract) search.append("contract", contract);
  if (state.salaryMin !== null) search.set("salary_min", String(state.salaryMin));
  if (state.postedSince !== null) search.set("posted_since", String(state.postedSince));
  if (state.savedOnly) search.set("saved_only", "1");
  if (state.sort !== "relevance") search.set("sort", state.sort);
  return search.toString();
}

/** Traduit l'état d'écran en paramètres `GET /jobs` (`include_hidden` reste au défaut `false`). */
function toApiParams(state: ListState): JobSearchParams {
  return {
    q: state.q || undefined,
    remote: state.remote.length > 0 ? state.remote : undefined,
    contract: state.contract.length > 0 ? state.contract : undefined,
    salary_min: state.salaryMin ?? undefined,
    posted_since: state.postedSince ?? undefined,
    saved_only: state.savedOnly || undefined,
    sort: state.sort,
    limit: PAGE_SIZE,
  };
}

interface SavedMutationVars {
  id: string;
  title: string;
  /** Nouvel état demandé (`null` = retirer sauvegarde/masquage). */
  state: SavedState | null;
  /** État avant mutation — pour le rollback et le « Annuler » du masquage. */
  previousState: SavedState | null;
}

/** Avis « Offre masquée » avec action Annuler (Flux 3 §5 — toujours restaurable). */
interface HiddenNotice {
  id: string;
  title: string;
  previousState: SavedState | null;
}

type JobItem = SearchPage["items"][number];

/**
 * Snapshot ciblé d'une offre dans une recherche en cache, avant mutation
 * optimiste. Le rollback ne restaure que cette entrée : deux mutations
 * concurrentes sur des offres différentes ne s'écrasent plus.
 */
interface JobSnapshot {
  queryKey: ReturnType<typeof jobsKeys.search>;
  pageIndex: number;
  itemIndex: number;
  item: JobItem;
  /** L'offre a été retirée de cette liste (masquage, ou dé-sauvegarde en `saved_only`). */
  removed: boolean;
}

function JobsSearchScreen() {
  const t = useTranslations();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const state = useMemo(
    () => parseListState(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  const applyPatch = useCallback(
    (patch: Partial<ListState>) => {
      const queryString = serializeListState({ ...state, ...patch });
      router.replace(queryString ? `${pathname}?${queryString}` : pathname, { scroll: false });
    },
    [state, pathname, router],
  );

  // Champ de recherche : état local, propagé vers l'URL après 300 ms (Flux 3 §3).
  const [searchInput, setSearchInput] = useState(state.q);
  // Dernière valeur `q` commitée vers l'URL — garde contre l'écrasement d'une
  // saisie en cours quand `state.q` revient de manière asynchrone.
  const committedQRef = useRef(state.q);
  useEffect(() => {
    // Ne resynchronise depuis l'URL que si aucune saisie n'est en cours
    // (la valeur locale correspond à la dernière valeur commitée).
    if (searchInput === committedQRef.current) {
      setSearchInput(state.q);
    }
    committedQRef.current = state.q;
    // `searchInput` est volontairement hors dépendances : seul un changement
    // externe de `state.q` doit déclencher la resynchronisation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.q]);
  useEffect(() => {
    if (searchInput === state.q) return;
    const handle = setTimeout(() => {
      committedQRef.current = searchInput;
      applyPatch({ q: searchInput });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInput, state.q, applyPatch]);

  const apiParams = useMemo(() => toApiParams(state), [state]);

  const jobsQuery = useInfiniteQuery({
    queryKey: jobsKeys.search(apiParams),
    queryFn: ({ pageParam, signal }) => searchJobs(apiParams, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (page: SearchPage) => getNextCursor(page) ?? null,
    // Garde les résultats précédents affichés pendant un changement de filtres
    // (évite le flash d'écran vide entre deux requêtes).
    placeholderData: keepPreviousData,
  });

  const jobs = useMemo(
    () => jobsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [jobsQuery.data],
  );

  const [hiddenNotice, setHiddenNotice] = useState<HiddenNotice | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Gestion de focus au masquage (Flux 3 §5) : la carte disparaissant du DOM,
  // le focus est déplacé sur l'avis « Offre masquée » ; à l'annulation, sur le
  // titre de la liste (les deux focalisables via `tabIndex={-1}`).
  const titleRef = useRef<HTMLHeadingElement>(null);
  const hiddenNoticeRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (hiddenNotice) {
      hiddenNoticeRef.current?.focus();
    }
  }, [hiddenNotice]);

  const savedMutation = useMutation({
    mutationFn: ({ id, state: nextState }: SavedMutationVars) =>
      nextState ? setSavedState(id, nextState) : clearSavedState(id),
    onMutate: async ({ id, state: nextState }) => {
      setActionError(null);
      await queryClient.cancelQueries({ queryKey: jobsKeys.searches() });
      // Mise à jour optimiste de chaque recherche en cache, selon ses propres
      // paramètres : une offre masquée sort des listes (include_hidden=false),
      // une offre dé-sauvegardée sort des listes « Sauvegardées uniquement ».
      // Snapshot par (queryKey, offre) — jamais de rollback global.
      const snapshots: JobSnapshot[] = [];
      const cached = queryClient.getQueriesData<InfiniteData<SearchPage, string | null>>({
        queryKey: jobsKeys.searches(),
      });
      for (const [queryKey, data] of cached) {
        if (!data) continue;
        const params = queryKey[2] as JobSearchParams | undefined;
        const removed =
          nextState === "hidden" || (params?.saved_only === true && nextState !== "saved");
        let touched = false;
        const pages = data.pages.map((page, pageIndex) => {
          const itemIndex = page.items.findIndex((item) => item.id === id);
          if (itemIndex === -1) return page;
          touched = true;
          snapshots.push({
            queryKey: queryKey as JobSnapshot["queryKey"],
            pageIndex,
            itemIndex,
            item: page.items[itemIndex],
            removed,
          });
          return {
            ...page,
            items: removed
              ? page.items.filter((item) => item.id !== id)
              : page.items.map((item) =>
                  item.id === id ? { ...item, saved_state: nextState } : item,
                ),
          };
        });
        if (!touched) continue;
        queryClient.setQueryData<InfiniteData<SearchPage, string | null>>(queryKey, {
          ...data,
          pages,
        });
      }
      return { snapshots };
    },
    onSuccess: (_data, vars) => {
      if (vars.state === "hidden") {
        setHiddenNotice({ id: vars.id, title: vars.title, previousState: vars.previousState });
      } else if (hiddenNotice?.id === vars.id) {
        setHiddenNotice(null);
      }
    },
    onError: (_error, _vars, context) => {
      // Rollback ciblé : ne restaure que l'offre concernée dans chaque cache,
      // sans écraser les mutations optimistes concurrentes d'autres offres.
      for (const { queryKey, pageIndex, itemIndex, item, removed } of context?.snapshots ?? []) {
        const data = queryClient.getQueryData<InfiniteData<SearchPage, string | null>>(queryKey);
        if (!data || !data.pages[pageIndex]) continue;
        queryClient.setQueryData<InfiniteData<SearchPage, string | null>>(queryKey, {
          ...data,
          pages: data.pages.map((page, index) => {
            if (index !== pageIndex) return page;
            if (removed) {
              if (page.items.some((entry) => entry.id === item.id)) return page;
              const items = [...page.items];
              items.splice(Math.min(itemIndex, items.length), 0, item);
              return { ...page, items };
            }
            return {
              ...page,
              items: page.items.map((entry) => (entry.id === item.id ? item : entry)),
            };
          }),
        });
      }
      setActionError(t("jobs.list.actionError"));
    },
    onSettled: (_data, _error, vars) => {
      void queryClient.invalidateQueries({ queryKey: jobsKeys.searches() });
      // Resynchronise aussi le cache détail (staleTime 30 s) : l'écran SCR-21
      // doit refléter le nouvel état sauvegardé/masqué sans attendre.
      void queryClient.invalidateQueries({ queryKey: jobsKeys.detail(vars.id) });
    },
  });

  const pendingJobId = savedMutation.isPending ? savedMutation.variables?.id : undefined;

  const isEmpty = jobsQuery.isSuccess && jobs.length === 0;

  // Rappel transparence de l'état vide : « Boussole interroge {n} sources » (Flux 3).
  const sourcesQuery = useQuery({
    queryKey: jobsKeys.sources,
    queryFn: ({ signal }) => getSources(signal),
    enabled: isEmpty,
    staleTime: Number.POSITIVE_INFINITY,
  });

  const hasActiveCriteria =
    state.q !== "" ||
    state.remote.length > 0 ||
    state.contract.length > 0 ||
    state.salaryMin !== null ||
    state.postedSince !== null ||
    state.savedOnly;

  const resetAll = useCallback(() => {
    setSearchInput("");
    router.replace(pathname, { scroll: false });
  }, [pathname, router]);

  const listErrorMessage = (error: unknown): string => {
    if (isApiProblem(error) && error.status === 429) {
      return t("jobs.list.rateLimited", { seconds: error.retryAfter ?? 60 });
    }
    return t("jobs.list.errorTitle");
  };

  return (
    <section aria-labelledby="jobs-title" className="space-y-6">
      <h1
        id="jobs-title"
        ref={titleRef}
        tabIndex={-1}
        className="text-2xl font-semibold text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        {t("pages.jobs.title")}
      </h1>

      <div className="space-y-4 lg:grid lg:grid-cols-[280px_minmax(0,1fr)] lg:items-start lg:gap-6 lg:space-y-0">
        {/* TODO M3 : chips de filtres actifs supprimables au clavier au-dessus
            de la liste (04-user-flows SCR-20). */}
        <JobFilters value={state} onChange={applyPatch} onReset={resetAll} />

        <div className="space-y-4">
          <div role="search" className="flex flex-wrap items-end gap-3">
            <div className="min-w-52 flex-1 space-y-1.5">
              <label htmlFor="jobs-search" className="block text-sm font-medium text-content">
                {t("jobs.list.searchLabel")}
              </label>
              <Input
                id="jobs-search"
                type="search"
                placeholder={t("jobs.list.searchPlaceholder")}
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="jobs-sort" className="block text-sm font-medium text-content">
                {t("jobs.list.sortLabel")}
              </label>
              <select
                id="jobs-sort"
                value={state.sort}
                onChange={(event) =>
                  applyPatch({ sort: event.target.value === "date" ? "date" : "relevance" })
                }
                className="h-11 rounded-md border border-border bg-surface px-3 text-sm text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none"
              >
                <option value="relevance">{t("jobs.list.sortRelevance")}</option>
                <option value="date">{t("jobs.list.sortDate")}</option>
              </select>
            </div>
          </div>

          {/* Annonce du nombre de résultats après chaque filtrage (a11y, Flux 3). */}
          <p role="status" aria-live="polite" className="text-sm text-content-secondary">
            {jobsQuery.isSuccess ? t("jobs.list.resultsCount", { count: jobs.length }) : null}
          </p>

          {hiddenNotice ? (
            <Alert ref={hiddenNoticeRef} tabIndex={-1} variant="info">
              <div className="flex flex-wrap items-center gap-3">
                <span>{t("jobs.list.hiddenNotice", { title: hiddenNotice.title })}</span>
                <Button
                  variant="secondary"
                  onClick={() => {
                    // TODO M3 : réinsertion optimiste de la carte dans la liste
                    // à l'annulation d'un masquage (aujourd'hui elle ne
                    // réapparaît qu'après l'invalidation de la recherche).
                    savedMutation.mutate({
                      id: hiddenNotice.id,
                      title: hiddenNotice.title,
                      state: hiddenNotice.previousState,
                      previousState: "hidden",
                    });
                    setHiddenNotice(null);
                    titleRef.current?.focus();
                  }}
                >
                  {t("jobs.list.undo")}
                </Button>
              </div>
            </Alert>
          ) : null}

          {actionError ? <Alert variant="error">{actionError}</Alert> : null}

          {jobsQuery.isPending ? (
            <div role="status" aria-live="polite" className="space-y-3">
              <span className="sr-only">{t("jobs.list.loading")}</span>
              {Array.from({ length: 5 }, (_, index) => (
                <div
                  key={index}
                  aria-hidden="true"
                  className="h-36 animate-pulse rounded-lg border border-border bg-surface-muted"
                />
              ))}
            </div>
          ) : null}

          {jobsQuery.isError && !jobsQuery.data ? (
            <Alert variant="error" title={listErrorMessage(jobsQuery.error)}>
              <Button variant="secondary" onClick={() => void jobsQuery.refetch()}>
                {t("jobs.list.retry")}
              </Button>
            </Alert>
          ) : null}

          {isEmpty ? (
            <EmptyState
              icon={SearchX}
              title={t("jobs.list.emptyTitle")}
              description={t("jobs.list.emptyDescription")}
            >
              {hasActiveCriteria ? (
                <Button variant="secondary" onClick={resetAll}>
                  {t("jobs.list.resetFilters")}
                </Button>
              ) : null}
              {sourcesQuery.data ? (
                <p className="text-sm text-content-secondary">
                  {t("jobs.list.sourcesReminder", { count: sourcesQuery.data.length })}
                </p>
              ) : null}
            </EmptyState>
          ) : null}

          {jobs.length > 0 ? (
            <>
              <ul className="space-y-3">
                {jobs.map((job) => (
                  <li key={job.id}>
                    <JobCard
                      job={job}
                      actionsDisabled={pendingJobId === job.id}
                      onSavedStateChange={(nextState) =>
                        savedMutation.mutate({
                          id: job.id,
                          title: job.title,
                          state: nextState,
                          previousState: job.saved_state,
                        })
                      }
                    />
                  </li>
                ))}
              </ul>

              {jobsQuery.isError ? (
                <Alert variant="error" title={listErrorMessage(jobsQuery.error)}>
                  <Button variant="secondary" onClick={() => void jobsQuery.fetchNextPage()}>
                    {t("jobs.list.retry")}
                  </Button>
                </Alert>
              ) : null}

              {jobsQuery.hasNextPage ? (
                <div className="flex justify-center">
                  <Button
                    variant="secondary"
                    onClick={() => void jobsQuery.fetchNextPage()}
                    disabled={jobsQuery.isFetchingNextPage}
                    aria-busy={jobsQuery.isFetchingNextPage}
                  >
                    {jobsQuery.isFetchingNextPage
                      ? t("common.loading")
                      : t("jobs.list.loadMore")}
                  </Button>
                </div>
              ) : (
                <p className="text-center text-sm text-content-secondary">
                  {t("jobs.list.endOfList")}
                </p>
              )}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={null}>
      <JobsSearchScreen />
    </Suspense>
  );
}
