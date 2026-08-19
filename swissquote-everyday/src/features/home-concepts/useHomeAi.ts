/**
 * React binding for the Home AI service.
 *
 * Holds the three states a network-backed feature actually has — loading,
 * ready, unavailable — and guarantees the third one still renders something
 * useful by falling back to the deterministic brief. The service is chosen
 * here, so neither variant knows whether it is talking to a mock.
 */
import { useEffect, useState } from 'react';
import {
  fallbackAnalysis,
  fallbackBrief,
  failingHomeAi,
  mockHomeAi,
  toAiContext,
  type AiAnalysis,
  type AiBrief,
} from './ai';
import type { HomeData } from './homeData';

export type AiStatus = 'loading' | 'ready' | 'unavailable';

export interface AiBriefState {
  status: AiStatus;
  brief: AiBrief | null;
}

export function useHomeAiBrief(data: HomeData, enabled = true): AiBriefState {
  const [state, setState] = useState<AiBriefState>({ status: 'loading', brief: null });
  // Re-runs only when the underlying facts change, not on every render.
  // `chf(0)` changes when balances are hidden, so the wording re-renders masked.
  const key = `${data.scenario}|${data.today.map((t) => t.id).join(',')}|${enabled}|${data.chf(0)}`;

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    setState({ status: 'loading', brief: null });
    const ctx = toAiContext(data);
    const service = data.aiUnavailable ? failingHomeAi : mockHomeAi;
    service
      .dailyBrief(ctx)
      .then((brief) => live && setState({ status: 'ready', brief }))
      // Unavailable is a state, not a dead end: show the same facts, plainly.
      .catch(() => live && setState({ status: 'unavailable', brief: fallbackBrief(ctx) }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}

export function useHomeAiPrompts(data: HomeData): { status: AiStatus; prompts: string[] } {
  const [state, setState] = useState<{ status: AiStatus; prompts: string[] }>({
    status: 'loading',
    prompts: [],
  });
  const key = `${data.scenario}|${data.today.map((t) => t.id).join(',')}|${data.chf(0)}`;

  useEffect(() => {
    let live = true;
    setState({ status: 'loading', prompts: [] });
    const service = data.aiUnavailable ? failingHomeAi : mockHomeAi;
    service
      .prompts(toAiContext(data))
      .then((prompts) => live && setState({ status: 'ready', prompts }))
      .catch(
        () =>
          live &&
          setState({
            status: 'unavailable',
            // Generic, always-answerable questions — no personalisation claimed.
            prompts: ['What is my buying power right now?', 'How much did I spend last month?'],
          }),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}

/** The analytical read, for Variant D's wealth-analysis tile. */
export function useHomeAiAnalysis(data: HomeData): { status: AiStatus; analysis: AiAnalysis | null } {
  const [state, setState] = useState<{ status: AiStatus; analysis: AiAnalysis | null }>({
    status: 'loading',
    analysis: null,
  });
  const key = `${data.scenario}|${data.analytics.findings.map((f) => f.id).join(',')}|${data.chf(0)}`;

  useEffect(() => {
    let live = true;
    setState({ status: 'loading', analysis: null });
    const ctx = toAiContext(data);
    const service = data.aiUnavailable ? failingHomeAi : mockHomeAi;
    service
      .analysis(ctx)
      .then((analysis) => live && setState({ status: 'ready', analysis }))
      // The findings are computed locally, so an outage costs phrasing only.
      .catch(() => live && setState({ status: 'unavailable', analysis: fallbackAnalysis(ctx) }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}
