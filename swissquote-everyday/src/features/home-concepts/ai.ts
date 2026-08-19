/**
 * Home AI — an interface with a mock behind it.
 *
 * There is no model here and no network call. `HomeAiService` is the seam: a
 * real implementation swaps in without either Home variant changing, because
 * the variants only ever see this contract.
 *
 * Three rules the mock enforces, and a real service would have to keep:
 *   1. Grounded — every statement names the figure it came from (`basis`), and
 *      that figure comes from the adapter, never from the generator.
 *   2. Never transactional — the service returns words and suggested
 *      questions. Moving money stays behind the app's normal confirmation
 *      flow, always initiated by the client.
 *   3. Degradable — when it is unavailable, the Home falls back to the same
 *      statements written deterministically from the data. The client loses
 *      the phrasing, not the information.
 */
import type { Finding, HomeData, TodayItem } from './homeData';

export interface AiStatement {
  text: string;
  /** The record or figure behind the sentence. Always shown to the client. */
  basis: string;
  /** The Today item this sentence re-words. A statement without one is not shown against an item. */
  itemId?: string;
}

export interface AiBrief {
  statements: AiStatement[];
  /** True when this came from the deterministic fallback, not the service. */
  fallback: boolean;
}

/**
 * A read of the client's position: one summary line, then a re-wording of
 * each finding the adapter computed. The service never adds a finding, drops
 * one, or changes their order.
 */
export interface AiAnalysis {
  summary: string;
  statements: AiStatement[];
  fallback: boolean;
}

/** What the service is allowed to see. Balances only — no identifiers. */
export interface AiContext {
  firstName: string;
  /** Already formatted, and already masked if the client hid their balances. */
  totalWealth: string;
  universes: { key: string; title: string; value: number; signal: string }[];
  today: TodayItem[];
  /** Already computed, already ranked. The service only phrases these. */
  findings: Finding[];
}

export interface HomeAiService {
  /** 2–3 short statements about what is going on with this client's money. */
  dailyBrief(ctx: AiContext): Promise<AiBrief>;
  /** Questions worth asking right now, given what the data currently says. */
  prompts(ctx: AiContext): Promise<string[]>;
  /** A read of the position, for the analytical Home. */
  analysis(ctx: AiContext): Promise<AiAnalysis>;
}

export function toAiContext(data: HomeData): AiContext {
  return {
    firstName: data.firstName,
    totalWealth: data.chf(data.totalWealth),
    universes: data.universes.map((u) => ({
      key: u.key,
      title: u.title,
      value: u.value,
      signal: u.signal.text,
    })),
    today: data.today,
    findings: data.analytics.findings,
  };
}

/* ------------------------------------------------------------------ */
/* Deterministic fallback — also the offline/error path                */
/* ------------------------------------------------------------------ */

/**
 * Written from the data, with no generation step. This is what the client
 * sees when the service is down, and it is deliberately not much worse.
 */
export function fallbackBrief(ctx: AiContext): AiBrief {
  const statements: AiStatement[] = [];

  for (const item of ctx.today.slice(0, 3)) {
    statements.push({ text: item.body, basis: item.basis, itemId: item.id });
  }

  if (statements.length === 0) {
    statements.push({
      text: `Nothing needs you today. ${ctx.totalWealth} across your Swissquote products.`,
      basis: 'Your balances, as of this morning',
    });
  }

  return { statements: statements.slice(0, 3), fallback: true };
}

/**
 * The analysis as the data alone would state it: the adapter's own sentences,
 * in the adapter's own order. This is what the client reads when the service
 * is unavailable, and it is deliberately no less true.
 */
export function fallbackAnalysis(ctx: AiContext): AiAnalysis {
  return {
    summary:
      ctx.findings.length > 0
        ? `${ctx.findings.length} thing${ctx.findings.length === 1 ? '' : 's'} stand out in your position.`
        : 'Nothing stands out in your position right now.',
    statements: ctx.findings.map((f) => ({ text: f.detail, basis: f.evidence[0]?.label ?? '', itemId: f.id })),
    fallback: true,
  };
}

/* ------------------------------------------------------------------ */
/* Mock service                                                        */
/* ------------------------------------------------------------------ */

const LATENCY_MS = 550;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS));
}

/**
 * Phrasing templates, one per item id the adapter can emit. Each returns the
 * BODY of a statement — the title always comes from the adapter, so the
 * service can change how something is said but never what it is about. A real
 * service would generate these; keying them to ids is what stops the mock
 * saying anything the data has not already established.
 */
const PHRASING: Record<string, (item: TodayItem, ctx: AiContext) => string> = {
  'cover-failed': (i) => `Start here. ${i.body}`,
  'allocation-pending': (i) => i.body,
  'margin-call': (i) => `${i.body} This one has a deadline.`,
  'salary-in': (i) => `${i.body} Nothing else is due this week.`,
  'cover-ran': (i) => `Nothing needed from you. ${i.body}`,
  'trade-move': (i, c) =>
    `${i.body} That is most of today's movement across your ${c.totalWealth}.`,
  surplus: (i) => `${i.body} Left where it is, it earns nothing.`,
  'pillar-3a': (i) => `${i.body} Worth doing before December rather than in December.`,
  forecast: (i) => `${i.body} Built on your own pattern, not an average.`,
  'orders-reserved': (i) => i.body,
};

export const mockHomeAi: HomeAiService = {
  async dailyBrief(ctx) {
    const picked = ctx.today.slice(0, 3);
    if (picked.length === 0) return delay(fallbackBrief(ctx));
    return delay({
      statements: picked.map((item) => ({
        text: PHRASING[item.id] ? PHRASING[item.id](item, ctx) : `${item.title}. ${item.body}`,
        basis: item.basis,
        itemId: item.id,
      })),
      fallback: false,
    });
  },

  async prompts(ctx) {
    const out: string[] = [];
    for (const item of ctx.today) {
      if (item.id === 'surplus') out.push('What could I do with the cash sitting still?');
      if (item.id === 'forecast') out.push('How much will I need before my next salary?');
      if (item.id === 'pillar-3a') out.push('Should I top up my 3a now?');
      if (item.id === 'cover-ran' || item.id === 'cover-failed') out.push('Why did Auto Cover move money?');
      if (item.id === 'trade-move') out.push('What moved in my portfolio today?');
      if (item.id === 'allocation-pending') out.push('When does my next salary allocation run?');
    }
    if (out.length < 3) out.push('What is my buying power right now?', 'Is my spending higher than usual?');
    return delay([...new Set(out)].slice(0, 3));
  },

  async analysis(ctx) {
    if (ctx.findings.length === 0) return delay(fallbackAnalysis(ctx));
    return delay({
      summary: `Across ${ctx.totalWealth}, the largest single thing you could change is the cash you are holding above what this cycle needs. Everything below is yours to act on or ignore.`,
      statements: ctx.findings.map((f) => ({
        text: ANALYSIS_PHRASING[f.id] ? ANALYSIS_PHRASING[f.id](f) : f.detail,
        basis: f.evidence[0]?.label ?? '',
        itemId: f.id,
      })),
      fallback: false,
    });
  },
};

/**
 * Re-wordings, keyed to the finding they belong to. Same constraint as the
 * daily brief: the service can change how something is said, never what the
 * numbers are — and never into advice. These observe; they do not recommend.
 */
const ANALYSIS_PHRASING: Record<string, (f: Finding) => string> = {
  'idle-cash': (f) => `${f.detail} It is the largest single thing you could change today.`,
  'over-covered': (f) => `${f.detail} Nothing forces the question — it is simply more cushion than most people hold.`,
  concentration: (f) => `${f.detail} Worth revisiting when you next add to a space.`,
  'pillar-3a-room': (f) => `${f.detail} It is the one item here with a date on it.`,
};

/** A service that always fails — the Simulate rig's "AI unavailable" state. */
export const failingHomeAi: HomeAiService = {
  dailyBrief: () => new Promise((_, reject) => setTimeout(() => reject(new Error('unavailable')), LATENCY_MS)),
  prompts: () => new Promise((_, reject) => setTimeout(() => reject(new Error('unavailable')), LATENCY_MS)),
  analysis: () => new Promise((_, reject) => setTimeout(() => reject(new Error('unavailable')), LATENCY_MS)),
};
