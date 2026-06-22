/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, v0.2 personas + deterministic engine
   Three reference scenarios from the spec (§20–§22), all figures wired:
     · caroline , employed, Geneva (Part I persona)
     · bergerRey, couple +++, Founex VD (Scenario A)
     · whitmore , single expat, Lausanne VD (Scenario B)
   Plus a transparent Edit & Simulate GO/AMBER/KO engine (§26) and the
   weighted Plan Score (§25). All numbers are illustrative estimates.
   window.PP_PERSONAS · window.PP_ENGINE
   ════════════════════════════════════════════════════════════════ */
(function () {
  const chf = (n) => "CHF " + Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019");
  const k = (n) => (Math.abs(n) >= 1000 ? (n / 1000).toFixed(0) + "k" : "" + n);

  /* ── Plan Score weights (§25) ─────────────────────────────────── */
  const SCORE_WEIGHTS = [
    { key: "funding", label: "Funding ratio", weight: 40, hint: "Projected vs target income" },
    { key: "tax", label: "Tax efficiency", weight: 20, hint: "3a max, buy-ins, staggering" },
    { key: "diversification", label: "Diversification", weight: 15, hint: "Concentration risk" },
    { key: "liquidity", label: "Liquidity buffer", weight: 15, hint: "Months of expenses" },
    { key: "protection", label: "Protection", weight: 10, hint: "Survivor / disability cover" },
  ];
  function planScore(sub) {
    // sub = { funding, tax, diversification, liquidity, protection } each 0–100
    let total = 0;
    SCORE_WEIGHTS.forEach((w) => { total += (sub[w.key] || 0) * w.weight / 100; });
    return Math.round(total);
  }
  function biggestMover(sub) {
    // lowest weighted contribution headroom → biggest opportunity
    let worst = null, gap = -1;
    SCORE_WEIGHTS.forEach((w) => {
      const head = (100 - (sub[w.key] || 0)) * w.weight / 100;
      if (head > gap) { gap = head; worst = w; }
    });
    return worst;
  }

  /* ── Edit & Simulate verdict engine (§26.2) ───────────────────── */
  // inputs: priceEUR or priceCHF + currency, downPayment(CHF), calcRate,
  // foreign(bool), and a persona "sim" context (income, cash, securities,
  // targetIncome, projectedBase, bufferThreshold).
  function simulate(inp) {
    const fx = inp.fx || 0.96; // EUR→CHF
    const priceCHF = inp.currency === "EUR" ? inp.price * fx : inp.price;
    const down = inp.downPayment;
    const mortgage = Math.max(0, priceCHF - down);
    const equityPct = priceCHF > 0 ? down / priceCHF : 0;
    const maint = 0.01, frenchCarry = inp.foreign ? 0.015 : 0; // taxe foncière etc.
    const annualCarry = mortgage * inp.calcRate + priceCHF * (maint + frenchCarry);
    const affordRatio = annualCarry / inp.grossIncome;

    const cash = inp.cash, securities = inp.securities;
    // affluent draw order: from invested securities first, preserving the cash buffer
    const securitiesDrawn = Math.min(down, securities);
    const cashDrawn = Math.max(0, down - securities);
    const erosion = securities > 0 ? Math.min(0.40, (securitiesDrawn / securities) * 0.10) : 0;
    const incomeAfter = Math.round(inp.projectedBase * (1 - erosion));
    const bufferAfter = Math.max(0, cash - cashDrawn);
    const fxBuffer = inp.foreign ? inp.bufferThreshold * 1.5 : inp.bufferThreshold;

    const reqEquity = inp.foreign ? 0.25 : 0.20;
    const affordOK = affordRatio <= 0.33;
    const equityOK = equityPct >= reqEquity;
    const incomeOK = incomeAfter >= inp.targetIncome * 0.95;
    const bufferOK = bufferAfter >= fxBuffer;

    let verdict;
    if (!affordOK || !equityOK || !incomeOK || !bufferOK) verdict = "KO";
    else if (incomeAfter < inp.projectedBase * 0.99 || inp.foreign) verdict = "AMBER";
    else verdict = "GO";

    // binding constraints (what's tight or failing), ranked
    const constraints = [];
    constraints.push({ ok: affordOK, label: "Affordability", v: Math.round(affordRatio * 100) + "% of income", lim: "\u2264 33%" });
    constraints.push({ ok: equityOK, label: "Equity", v: Math.round(equityPct * 100) + "%", lim: "\u2265 " + Math.round(reqEquity * 100) + "%" });
    constraints.push({ ok: incomeOK, label: "Retirement income", v: chf(incomeAfter), lim: "\u2265 " + chf(Math.round(inp.targetIncome * 0.95)) });
    constraints.push({ ok: bufferOK, label: "Liquidity buffer", v: chf(bufferAfter), lim: "\u2265 " + chf(fxBuffer) });

    // "what would flip it"
    const flips = [];
    if (!affordOK) {
      const maxMortgage = (inp.grossIncome * 0.33 - priceCHF * (maint + frenchCarry)) / inp.calcRate;
      const cutPrice = Math.max(0, priceCHF - (maxMortgage + down));
      if (cutPrice > 0) flips.push("Reduce price by ~" + chf(cutPrice));
    }
    if (!equityOK) flips.push("Add ~" + chf(Math.round((reqEquity * priceCHF) - down)) + " equity");
    if (!bufferOK) flips.push("Keep ~" + chf(Math.round(fxBuffer - bufferAfter)) + " more in reserve");
    if (!incomeOK) flips.push("Draw less from invested capital, or retire 2\u20133 yrs later");
    if (verdict === "AMBER") flips.push("Proceed with the named conditions below");

    return {
      verdict, priceCHF, mortgage, equityPct, affordRatio, incomeAfter, bufferAfter,
      erosionPct: +(erosion * 100).toFixed(1), constraints, flips,
    };
  }

  window.PP_ENGINE = { chf, k, SCORE_WEIGHTS, planScore, biggestMover, simulate };

  /* ════════════════════════════════════════════════════════════════
     PERSONA REGISTRY
     ════════════════════════════════════════════════════════════════ */
  const PD = window.PP_DATA; // Caroline's existing rich data
  try { window.__ppExtraEvents = JSON.parse(localStorage.getItem("pp_events") || "{}"); } catch (e) { window.__ppExtraEvents = {}; }

  // ── CAROLINE (Part I), reuse existing PP_DATA / PP_DATA.v2 ──────
  const caroline = {
    id: "caroline", name: "Caroline Berger", first: "Caroline", initials: "CB",
    kind: "single", age: 42, canton: "Geneva", status: "Married \u00b7 2 children \u00b7 employed",
    flag: "\ud83c\udded\ud83c\udde8", headline: "On track, with room to climb",
    grossIncome: 132000, targetYearly: 80400, targetMonthly: 6700,
    netWorth: 396000, retireTarget: 64, referenceAge: 65,
    taxFixture: "Declaration-impot-2025_Berger.pdf",
    readiness: window.PP_DATA.v2.readiness,
    scenarios: [
      { age: 62, inc: "CHF 4\u2019430", pct: "66% of target", tag: "tight", tagTxt: "Tight" },
      { age: 64, inc: "CHF 5\u2019133", pct: "77% of target", tag: "ok", tagTxt: "On plan", hl: true },
      { age: 65, inc: "CHF 5\u2019560", pct: "83% of target", tag: "ok", tagTxt: "Comfortable" },
    ],
    subScores: { funding: 77, tax: 64, diversification: 72, liquidity: 70, protection: 66 },
    kpis: window.PP_DATA.v2.kpis,
    projection: window.PP_DATA.v2.projection,
    journey: window.PP_DATA.v2.journey,
    advisories: PD.levers,
    lumpAnnuity: window.PP_DATA.v2.annuity,
    improve: window.PP_DATA.v2.improve,
    plans: [
      { id: "secure", name: "Secure", thesis: "Certainty over upside", rec: false, income: "CHF 4\u2019900/mo", taxSaved: "Lower", risk: "Low", retireAge: 65, score: 71,
        moves: ["Amortise toward the mortgage", "Conservative 3a allocation", "No early retirement"], sub: { funding: 74, tax: 55, diversification: 78, liquidity: 78, protection: 70 } },
      { id: "balanced", name: "Balanced", thesis: "Balance growth, tax & flexibility", rec: true, income: "CHF 5\u2019133/mo", taxSaved: "Medium\u2013high", risk: "Medium", retireAge: 64, score: 77,
        moves: ["Max 3a \u00d7 securities-based", "Staged pension-fund buy-in", "Stagger withdrawals over 3 yrs"], sub: { funding: 77, tax: 64, diversification: 72, liquidity: 70, protection: 66 } },
      { id: "optimise", name: "Optimise", thesis: "Maximise capital & flexibility", rec: false, income: "CHF 5\u2019560/mo", taxSaved: "High", risk: "Higher", retireAge: 64, score: 80,
        moves: ["Front-loaded buy-ins", "Higher equity allocation", "Retroactive 3a catch-up"], sub: { funding: 83, tax: 78, diversification: 64, liquidity: 62, protection: 66 } },
    ],
    calendar: [
      { id: "c0", yr: "2024", age: 40, t: "Plan created", d: "First snapshot from 3 documents.", type: "milestone", state: "done" },
      { id: "c1", yr: "2026", age: 42, t: "Max 3a + review buy-in", d: "Closing the CHF 1\u2019570/mo gap.", type: "save", state: "now", amt: "CHF 4\u2019058" },
      { id: "c2", yr: "2028", age: 44, t: "Mortgage renewal", d: "Re-check WEF vs pledge.", type: "property", state: "next" },
      { id: "c3", yr: "2034", age: 50, t: "Children to university", d: "Cashflow squeeze, protect 3a.", type: "family", state: "next" },
      { id: "c4", yr: "2048", age: 64, t: "Retirement", d: "Capital vs annuity, with a human.", type: "retire", state: "next" },
    ],
    sim: { grossIncome: 132000, cash: 38000, securities: 41800, targetIncome: 80400, projectedBase: 61600, bufferThreshold: 30000,
      defaults: { price: 1200000, currency: "CHF", downPayment: 280000, calcRate: 0.05, foreign: false } },
    divorce: { applicable: false },
  };

  // ── BERGER-REY (Scenario A, couple +++) ────────────────────────
  const bergerRey = {
    id: "bergerRey", name: "Berger-Rey household", first: "Thomas & Sandrine", initials: "TR",
    kind: "couple", age: 46, canton: "Founex (VD)", status: "Married \u00b7 2 kids \u00b7 Thomas 46 / Sandrine 44",
    flag: "\ud83c\udded\ud83c\udde8", headline: "Broadly on track, but concentrated",
    grossIncome: 362000, targetYearly: 180000, targetMonthly: 15000,
    netWorth: 1450000, retireTarget: 63, referenceAge: 65,
    taxFixture: "Declaration-impot-2025_Couple-Berger-Rey.pdf",
    readiness: {
      score: 81, verdict: "Strong income, three structural risks",
      sub: "You're broadly on track for income, but concentration, Sandrine's missing 2nd pillar, and lump-sum withdrawal tax are the risks to manage now.",
      today: 13800, planned: 15000, upliftPct: 8.7,
    },
    scenarios: [
      { age: 61, inc: "CHF 13\u2019100", pct: "87% of target", tag: "tight", tagTxt: "Stretch" },
      { age: 63, inc: "CHF 14\u2019200", pct: "95% of target", tag: "ok", tagTxt: "On plan", hl: true },
      { age: 65, inc: "CHF 16\u2019000", pct: "107% of target", tag: "ok", tagTxt: "Surplus" },
    ],
    subScores: { funding: 88, tax: 58, diversification: 46, liquidity: 74, protection: 52 },
    kpis: [
      { lbl: "Projected income", val: "CHF 13\u2019800", sub: "per month at 63", tone: "green", tag: "92% of target" },
      { lbl: "Buy-in capacity", val: "CHF 184\u2019000", sub: "Thomas \u00b7 tax-deductible", tone: "green", tag: "Opportunity" },
      { lbl: "Concentration", val: "61%", sub: "property + 1 securities line", tone: "amber", tag: "Risk" },
      { lbl: "Sandrine pillar 2", val: "None", sub: "self-employed \u00b7 large 3a only", tone: "red", tag: "Gap" },
    ],
    projection: {
      startAge: 46, retireAge: 63, endAge: 88, yTicks: [3000000, 2250000, 1500000, 750000], yMax: 3200000,
      current: [[46, 915000], [52, 1240000], [58, 1560000], [63, 1780000], [70, 1520000], [79, 1020000], [88, 560000]],
      planned: [[46, 915000], [52, 1360000], [58, 1820000], [63, 2240000], [70, 2010000], [79, 1480000], [88, 940000]],
      bandLo: [[46, 915000], [52, 1300000], [58, 1700000], [63, 2060000], [70, 1820000], [79, 1280000], [88, 760000]],
      bandHi: [[46, 915000], [52, 1420000], [58, 1940000], [63, 2420000], [70, 2220000], [79, 1700000], [88, 1140000]],
      peak: { age: 63, value: 2240000 }, confidence: "High confidence",
    },
    journey: { years: 17, nowAge: 46, retireAge: 63, contribNow: 4200, contribPlanned: 7600, totalContrib: 1280000, projectedFund: 2240000, progressPct: 46, confidence: "High confidence" },
    advisories: [
      { rank: 1, title: "Stage Thomas's LPP buy-ins (~CHF 184k)", label: "advice", impact: 980, effort: 2,
        desc: "Spread the buy-in over ~5 years for a tax deduction now and a higher pension, respecting the 3-year lock before any capital withdrawal.",
        math: [["Inputs", "Buy-in capacity <b>CHF 184\u2019000</b>; Vaud marginal \u2248 41%; CHF 37k/yr \u00d7 5."], ["Assumption", "Conversion basis held; 3-year lock respected before withdrawals."], ["Result", "Tax saved \u2248 <b>CHF 75\u2019000</b> cumulatively; pension +\u2248 <b>CHF 980/mo</b>."]],
        rule: "LPP voluntary buy-in \u00b7 3-year withdrawal lock" },
      { rank: 2, title: "Open a 2nd 3a for Sandrine & keep maxing", label: "advice", impact: 0, impactNote: "saves \u2248 CHF 34k", effort: 1,
        desc: "A large-3a saver with no 2nd pillar, Sandrine should split across accounts so withdrawals stagger across tax years and break progression.",
        math: [["Inputs", "Large-3a \u2248 CHF 130\u2019000 growing CHF 22k/yr; single account."], ["Assumption", "Withdrawals spread over 3 tax years near retirement."], ["Result", "One-off withdrawal tax cut \u2248 <b>CHF 34\u2019000</b>."]],
        rule: "Self-employed large 3a \u00b7 max 20% income / CHF 36\u2019288" },
      { rank: 3, title: "Diversify the concentrated securities line", label: "advice", impact: 0, impactNote: "lowers risk", effort: 2,
        desc: "A single securities line plus the property is 61% of net worth. Align allocation to the 17-year horizon to cut drawdown risk.",
        math: [["Inputs", "Securities CHF 705\u2019000 in one position; property CHF 2.2M."], ["Assumption", "Phased rebalance to a diversified mandate over 12\u201318 months."], ["Result", "Concentration sub-score rises; sequence-of-returns risk falls."]],
        rule: "Diversification \u00b7 suitability-gated" },
      { rank: 4, title: "Close Sandrine's protection gap", label: "advice", impact: 0, impactNote: "survivor cover", effort: 2,
        desc: "With no 2nd pillar, Sandrine's survivor and disability cover is thin. Add term cover sized to the household's obligations.",
        math: [["Inputs", "No LPP death/disability for Sandrine; mortgage CHF 1.1M; 2 children."], ["Assumption", "Term life + disability sized to liabilities and income."], ["Result", "Protection sub-score lifts from low to adequate."]],
        rule: "Survivor / disability adequacy" },
    ],
    lumpAnnuity: { capital: 2240000, intro: "Thomas's 2nd-pillar capital reaches ~CHF 2.24M at 63. The capital-vs-annuity choice is the single biggest irreversible decision, here's the trade-off.",
      options: [
        { id: "lump", icon: "ri-wallet-3-line", t: "Lump sum", sub: "Control & flexibility", rec: false, head: "Take the capital", figure: "CHF 2\u20192M+", figureLabel: "one-off, staggered for tax", points: ["Full control to invest and gift", "You carry market & longevity risk", "Stagger across years to cut withdrawal tax"] },
        { id: "annuity", icon: "ri-shield-check-line", t: "Lifelong annuity", sub: "Security & certainty", rec: true, head: "Convert to a pension", figure: "CHF 9\u2019700", figureLabel: "guaranteed / month, for life", points: ["Predictable income for life", "No market or longevity risk", "Taxed as income each year"] },
      ],
      note: "A blend is common. Given the concentration, a partial annuity floor + lump-sum flex is worth modelling with an advisor." },
    improve: [
      { key: "lpp-t", icon: "ri-bank-line", t: "Thomas's LPP certificate", d: "Confirms buy-in capacity & conversion basis.", impact: "high", impactTxt: "Sharpens pension by \u00b1CHF 320/mo" },
      { key: "3a-c", icon: "ri-safe-2-line", t: "Sandrine's 3a statements", d: "Exact large-3a balance & contributions.", impact: "med", impactTxt: "Refines tax staggering" },
      { key: "mortgage", icon: "ri-home-4-line", t: "Mortgage statement", d: "Rate & amortisation for renewal modelling.", impact: "med", impactTxt: "Amortise-vs-invest at renewal" },
    ],
    plans: [
      { id: "secure", name: "Secure", thesis: "Certainty over upside", rec: false, income: "CHF 14\u2019600/mo", taxSaved: "Lower", risk: "Low", retireAge: 65, score: 76,
        moves: ["Amortise the mortgage", "Conservative allocation", "No early retirement"], sub: { funding: 84, tax: 52, diversification: 70, liquidity: 82, protection: 64 } },
      { id: "balanced", name: "Balanced", thesis: "Balance growth, tax & flexibility", rec: true, income: "CHF 16\u2019000/mo", taxSaved: "Medium\u2013high", risk: "Medium", retireAge: 63, score: 81,
        moves: ["Staged buy-ins + max 3a (\u00d72 accounts)", "Balanced diversified portfolio", "Staggered withdrawals"], sub: { funding: 88, tax: 70, diversification: 68, liquidity: 78, protection: 66 } },
      { id: "optimise", name: "Optimise", thesis: "Maximise capital & early exit", rec: false, income: "CHF 17\u2019100/mo", taxSaved: "High", risk: "Higher", retireAge: 61, score: 83,
        moves: ["Front-loaded buy-ins", "Higher equity, retire 61/63", "Aggressive tax-staggering"], sub: { funding: 92, tax: 82, diversification: 62, liquidity: 66, protection: 64 } },
    ],
    calendar: [
      { id: "c0", yr: "2025", age: 46, t: "Plan created", d: "Snapshot from the joint tax statement.", type: "milestone", state: "done" },
      { id: "c1", yr: "2026", age: 46, t: "Start staged LPP buy-ins", d: "CHF 37k/yr \u00d7 5, tax-deductible.", type: "save", state: "now", amt: "CHF 37\u2019000/yr" },
      { id: "c2", yr: "2027", age: 47, t: "Provence second home", d: "EUR 500k, simulate GO/KO.", type: "property", state: "next" },
      { id: "c3", yr: "2031", age: 51, t: "Children to university", d: "Two overlapping years of costs.", type: "family", state: "next" },
      { id: "c4", yr: "2042", age: 63, t: "Retirement (Thomas)", d: "Capital vs annuity, with a human.", type: "retire", state: "next" },
    ],
    sim: { grossIncome: 362000, cash: 180000, securities: 705000, targetIncome: 180000, projectedBase: 180000, bufferThreshold: 120000,
      defaults: { price: 500000, currency: "EUR", downPayment: 180000, calcRate: 0.05, foreign: true } },
    divorce: {
      applicable: true,
      intro: "Declaring a separation forks the household into two individual plans. 2nd-pillar assets built during the marriage are split (default 50/50, editable). This is irreversible and legally heavy, routed to a human.",
      marriagePillar2: 690000, splitPct: 50,
      people: [
        { name: "Thomas", initials: "TB", afterSplit: "CHF 345\u2019000", gap: "Manageable", note: "Keeps salary & buy-in capacity; single-tax rates now apply." },
        { name: "Sandrine", initials: "SR", afterSplit: "CHF 345\u2019000", gap: "Sensitive", note: "No 2nd pillar of her own, the split is her main retirement capital. Protection gap widens." },
      ],
    },
  };

  // ── WHITMORE (Scenario B, single expat) ────────────────────────
  const whitmore = {
    id: "whitmore", name: "James Whitmore", first: "James", initials: "JW",
    kind: "single", age: 34, canton: "Lausanne (VD)", status: "British \u00b7 single \u00b7 arrived 03.2025",
    flag: "\ud83c\uddec\ud83c\udde7", headline: "Thin today, high potential if he starts now",
    grossIncome: 119000, targetYearly: 72000, targetMonthly: 6000,
    netWorth: 31000, retireTarget: 65, referenceAge: 65,
    taxFixture: "Declaration-impot-2025_Expat-Whitmore.pdf",
    readiness: {
      score: 60, verdict: "Moderate, a clear, low-effort path up",
      sub: "Your Swiss assets are still building, but you sit firmly in Moderate. Maxing your 3a, a 6-month buffer and keeping capital portable lift you toward Good, with a 30-year horizon firmly on your side.",
      today: 1900, planned: 4200, upliftPct: 121,
    },
    scenarios: [
      { age: 63, inc: "CHF 3\u2019400", pct: "57% of target", tag: "tight", tagTxt: "Short" },
      { age: 65, inc: "CHF 4\u2019200", pct: "70% of target", tag: "tight", tagTxt: "Building", hl: true },
      { age: 67, inc: "CHF 4\u2019900", pct: "82% of target", tag: "ok", tagTxt: "Better" },
    ],
    subScores: { funding: 34, tax: 48, diversification: 40, liquidity: 44, protection: 36 },
    kpis: [
      { lbl: "Pension capital", val: "CHF 12\u2019200", sub: "new LPP + 3a", tone: "amber", tag: "Building" },
      { lbl: "Liquidity", val: "CHF 28\u2019000", sub: "~3 months \u00b7 target 6", tone: "amber", tag: "Thin" },
      { lbl: "3a headroom 2026", val: "CHF 4\u2019258", sub: "of CHF 7\u2019258 cap", tone: "green", tag: "Act now" },
      { lbl: "CH runway", val: "1.2 yrs", sub: "may leave in ~8", tone: "red", tag: "Mobility" },
    ],
    projection: {
      startAge: 34, retireAge: 65, endAge: 88, yTicks: [800000, 600000, 400000, 200000], yMax: 850000,
      current: [[34, 12200], [42, 92000], [50, 196000], [58, 318000], [65, 432000], [74, 322000], [88, 110000]],
      planned: [[34, 12200], [42, 138000], [50, 286000], [58, 452000], [65, 624000], [74, 498000], [88, 248000]],
      bandLo: [[34, 12200], [42, 124000], [50, 256000], [58, 408000], [65, 558000], [74, 432000], [88, 196000]],
      bandHi: [[34, 12200], [42, 152000], [50, 318000], [58, 502000], [65, 692000], [74, 568000], [88, 312000]],
      peak: { age: 65, value: 624000 }, confidence: "Medium, mobility-dependent",
    },
    journey: { years: 31, nowAge: 34, retireAge: 65, contribNow: 250, contribPlanned: 920, totalContrib: 268000, projectedFund: 624000, progressPct: 9, confidence: "Medium confidence" },
    advisories: [
      { rank: 1, title: "Max your 3a now, and plan retroactive buy-ins", label: "advice", impact: 360, effort: 1,
        desc: "You've used CHF 3\u2019000 of the 2026 cap. Top up the remaining CHF 4\u2019258, then use the new retroactive 3a buy-ins for partial years.",
        math: [["Inputs", "Paid CHF 3\u2019000 of <b>CHF 7\u2019258</b>; 31 years to 65; one new 3a."], ["Assumption", "2.5% net real return; contributions indexed to the cap."], ["Result", "Extra capital \u2248 <b>CHF 96\u2019000</b> \u2192 \u2248 <b>CHF 360/mo</b>."]],
        rule: "3a cap 2026 \u00b7 CHF 7\u2019258 + retroactive buy-ins (2025/26)" },
      { rank: 2, title: "Build a 6-month liquidity buffer first", label: "info", impact: 0, impactNote: "resilience", effort: 1,
        desc: "Before any property commitment, get the buffer to ~6 months of expenses. It's what makes the Provence simulation flip later.",
        math: [["Inputs", "Cash CHF 28\u2019000 \u2248 3 months; target \u2248 6 months."], ["Assumption", "Monthly expenses \u2248 CHF 4\u2019700."], ["Result", "Target buffer \u2248 <b>CHF 28\u2019000</b> more."]],
        rule: "Liquidity buffer \u00b7 months of expenses" },
      { rank: 3, title: "Keep your plan portable", label: "info", impact: 0, impactNote: "flexibility", effort: 2,
        desc: "If you leave Switzerland, your 3a, 2nd pillar and vested benefits follow specific rules. Design the plan to stay flexible.",
        math: [["Inputs", "Possible departure within ~8 years; no prior CH vested benefits."], ["Assumption", "Vested-benefits account on departure; cross-border tax applies."], ["Result", "Avoid CH-locked capital you can't move efficiently."]],
        rule: "Cross-border vested benefits \u00b7 human handoff" },
      { rank: 4, title: "Track AVS continuity", label: "info", impact: 0, impactNote: "avoid gaps", effort: 1,
        desc: "Contribution gaps reduce your 1st-pillar pension. Keep AVS contributions continuous, especially around any career break.",
        math: [["Inputs", "Arrived 03.2025; building CH contribution history."], ["Assumption", "Continuous contributions to reference age."], ["Result", "No AVS reduction from gap years."]],
        rule: "AVS contribution years" },
    ],
    lumpAnnuity: { capital: 624000, intro: "If James stays in Switzerland to 65, his 2nd-pillar capital reaches ~CHF 624k. The capital-vs-annuity choice (and cross-border portability) is years away, but worth understanding now.",
      options: [
        { id: "lump", icon: "ri-wallet-3-line", t: "Lump sum", sub: "Portable, flexible", rec: true, head: "Take capital, useful if leaving CH", figure: "CHF 624\u2019000", figureLabel: "one-off, portable", points: ["Easier to move abroad", "You manage the capital", "Cross-border tax applies"] },
        { id: "annuity", icon: "ri-shield-check-line", t: "Lifelong annuity", sub: "Security if staying", rec: false, head: "Convert to a CH pension", figure: "CHF 2\u2019700", figureLabel: "guaranteed / month, for life", points: ["Predictable income for life", "Best if staying in CH", "Less flexible across borders"] },
      ],
      note: "For a mobile expat, portability usually outweighs annuity certainty, but it depends on where you retire. Revisit before any decision." },
    improve: [
      { key: "3a-stmt", icon: "ri-safe-2-line", t: "3a statement", d: "Confirms your new 3a balance & YTD.", impact: "high", impactTxt: "Sharpens gap by \u00b1CHF 90/mo" },
      { key: "uk", icon: "ri-global-line", t: "UK pension summary", d: "Cross-border picture if you return.", impact: "med", impactTxt: "Models portability" },
      { key: "salary", icon: "ri-file-list-3-line", t: "Salary certificate", d: "Refines insured salary & 3a capacity.", impact: "low", impactTxt: "Optimises contributions" },
    ],
    plans: [
      { id: "foundations", name: "Foundations", thesis: "Build the base first", rec: true, income: "CHF 4\u2019200/mo", taxSaved: "Medium", risk: "Low", retireAge: 65, score: 38,
        moves: ["6-month buffer + max 3a", "Start vested-benefits awareness", "Defer property"], sub: { funding: 34, tax: 48, diversification: 40, liquidity: 44, protection: 36 } },
      { id: "anchor", name: "CH anchor", thesis: "Commit to Switzerland", rec: false, income: "CHF 4\u2019900/mo", taxSaved: "Medium\u2013high", risk: "Medium", retireAge: 65, score: 44,
        moves: ["Prioritise a CH primary residence", "Build pillar 2 actively", "Long-horizon equity 3a"], sub: { funding: 42, tax: 56, diversification: 46, liquidity: 40, protection: 42 } },
      { id: "mobile", name: "Mobile", thesis: "Optimise for leaving", rec: false, income: "CHF 4\u2019000/mo", taxSaved: "Lower", risk: "Low", retireAge: 65, score: 41,
        moves: ["Keep assets liquid & portable", "Minimise CH-locked capital", "Track cross-border rules"], sub: { funding: 36, tax: 44, diversification: 52, liquidity: 58, protection: 36 } },
    ],
    calendar: [
      { id: "c0", yr: "2025", age: 34, t: "Arrived in Switzerland", d: "New LPP + first 3a opened.", type: "milestone", state: "done" },
      { id: "c1", yr: "2026", age: 34, t: "Max 3a + start buffer", d: "Top up CHF 4\u2019258; build reserve.", type: "save", state: "now", amt: "CHF 4\u2019258" },
      { id: "c2", yr: "2029", age: 37, t: "Provence flat (deferred)", d: "Simulate, KO today, revisit.", type: "property", state: "next" },
      { id: "c3", yr: "2033", age: 41, t: "Possible departure from CH", d: "Portability & vested benefits.", type: "move", state: "next" },
      { id: "c4", yr: "2056", age: 65, t: "Retirement", d: "Where? Capital vs annuity depends on it.", type: "retire", state: "next" },
    ],
    sim: { grossIncome: 119000, cash: 28000, securities: 3000, targetIncome: 72000, projectedBase: 50400, bufferThreshold: 28000,
      defaults: { price: 450000, currency: "EUR", downPayment: 90000, calcRate: 0.05, foreign: true } },
    divorce: { applicable: false },
  };

  // ── Take Action: cross-sell proposals (spec §6) ──
  caroline.takeAction = [
    { cat: "Pension", catTone: "pension",
      title: "Finance your CHF 86\u2019000 PK buy-in via a Lombard loan",
      benefit: "Save up to CHF 27\u2019520 in taxes immediately",
      body: "You have CHF 86\u2019000 of pension-fund buy-in potential. A Swissquote Lombard loan (\u2248 market +1.5% \u2248 3%) can finance it today. At a ~32% marginal rate (Geneva), the tax saving is \u2248 CHF 27\u2019520; net of 3 years of interest the benefit is \u2248 CHF 19\u2019780.",
      math: [["PK buy-in amount", "CHF 86\u2019000", ""], ["Lombard rate (~mkt +1.5%)", "~3.0% p.a.", ""], ["Annual loan cost", "\u2212CHF 2\u2019580", "neg"], ["Immediate tax saving", "+CHF 27\u2019520", "pos"], ["Year-1 net benefit", "CHF 24\u2019940", "pos"]],
      result: ["Estimated net tax saving (after 3yr loan cost)", "CHF 19\u2019780"], cta: "Get a Lombard loan with Swissquote" },
    { cat: "Tax saving", catTone: "tax",
      title: "Top up your pillar 3a to the 2026 maximum",
      benefit: "Save \u2248 CHF 1\u2019300 in tax this year",
      body: "You've paid CHF 3\u2019200 of the CHF 7\u2019258 cap. Topping up the remaining CHF 4\u2019058 is fully deductible, at a ~32% marginal rate that's \u2248 CHF 1\u2019300 saved this year, and the capital keeps compounding tax-sheltered to retirement.",
      math: null, result: ["Additional tax saving", "CHF 1\u2019300/yr"], cta: "Top up my 3a with Swissquote",
      math: [["Remaining 3a allowance", "CHF 4\u2019058", ""], ["Marginal rate (Geneva)", "~32%", ""], ["Tax saved this year", "+CHF 1\u2019300", "pos"]] },
    { cat: "Pension", catTone: "pension",
      title: "Stagger your CHF 86\u2019000 buy-in over 3 years",
      benefit: "Spread the deduction for maximum tax impact",
      body: "Even without Lombard financing, splitting the CHF 86\u2019000 buy-in across 3 years (\u2248 CHF 29\u2019000/yr) deducts it fully each year near the top of your marginal band, maximising cumulative tax savings and boosting projected retirement capital.",
      math: null, result: ["Total tax saving over 3 years", "CHF 27\u2019500"], cta: "Plan my PK buy-back",
      math: [["Buy-in amount", "CHF 86’000", ""], ["Per year × 3", "CHF 29’000/yr", ""], ["Marginal rate", "~32%", ""], ["Total tax saved", "+CHF 27’500", "pos"]] },
    { cat: "Swissquote", catTone: "swissquote",
      title: "Switch your 3a to an equity strategy",
      benefit: "Boost long-term 3a growth by ~2\u20133% p.a.",
      body: "With CHF 41\u2019800 in pillar 3a and 22 years to retirement, moving from a cash/bond 3a to a diversified equity 3a solution could add \u2248 CHF 30\u2019000\u201345\u2019000 of capital at 64. Swissquote offers self-directed 3a investing with full equity exposure.",
      math: null, result: ["Estimated extra capital at 64 (3% p.a. uplift)", "CHF 38\u2019000"], cta: "Invest my 3a in equities",
      math: [["Current pillar 3a", "CHF 41’800", ""], ["Horizon to 64", "22 years", ""], ["Equity uplift", "~3% p.a.", ""], ["Extra capital at 64", "+CHF 38’000", "pos"]] },
    { cat: "Wealth", catTone: "wealth",
      title: "Switch to indirect mortgage amortisation via 3a",
      benefit: "Keep your mortgage deduction while building 3a",
      body: "Instead of directly repaying the CHF 520\u2019000 mortgage on your flat, pledge pillar-3a contributions as indirect amortisation. This preserves the full mortgage-interest deduction while accumulating tax-sheltered retirement capital, optimising both ICC and IFD.",
      math: null, result: ["Annual interest deduction preserved", "CHF 9\u2019400/yr"], cta: "Learn about indirect amortisation",
      math: [["Mortgage on your flat", "CHF 520\u2019000", ""], ["Interest deduction kept", "CHF 9\u2019400/yr", "pos"], ["3a contributions", "tax-sheltered", ""]] },
    { cat: "Swissquote", catTone: "swissquote",
      title: "Fund a pension-fund buy-in with a Lombard loan",
      benefit: "Keep your invested capital working while you deduct",
      body: "Borrow against your portfolio to make a CHF 30\u2019000 buy-in now, deduct it this tax year, and repay from cashflow, so your invested capital stays in the market instead of being liquidated.",
      math: [["Buy-in funded", "CHF 30\u2019000", ""], ["Lombard rate (\u2248 mkt +1.5%)", "4.5% p.a.", ""], ["Marginal tax rate", "~32%", ""], ["Tax saved now", "+CHF 9\u2019600", "pos"], ["Future pension uplift", "+CHF 410/mo", "pos"]],
      result: ["Tax saved now", "CHF 9\u2019600"], cta: "Explore a Lombard loan" },
  ];

  // ── Whitmore (James) cross-sell, aligned to his hero "reach Good" moves ──
  whitmore.takeAction = [
    { cat: "Tax saving", catTone: "tax", pts: 4,
      title: "Max your pillar 3a now",
      benefit: "Save \u2248 CHF 1\u2019110 in tax this year",
      body: "You've paid CHF 3\u2019000 of the CHF 7\u2019258 cap. Topping up the remaining CHF 4\u2019258 is fully deductible, at a ~26% marginal rate that's \u2248 CHF 1\u2019110 saved this year, and the capital compounds tax-sheltered over your 31-year horizon.",
      math: [["Remaining 3a allowance", "CHF 4\u2019258", ""], ["Marginal rate (Vaud)", "~26%", ""], ["Tax saved this year", "+CHF 1\u2019110", "pos"], ["Extra capital at 65 (2.5% p.a.)", "+CHF 96\u2019000", "pos"]],
      result: ["Tax saved this year", "CHF 1\u2019110"], cta: "Top up my 3a with Swissquote" },
    { cat: "Wealth", catTone: "wealth", pts: 2,
      title: "Build your 6-month safety buffer",
      benefit: "Resilience before any property step",
      body: "Your cash covers \u2248 3 months of expenses; the target is \u2248 6. Building the reserve first is what later flips a Provence-property simulation from KO to GO, and protects your plan from forced selling.",
      math: [["Cash today", "CHF 28\u2019000", ""], ["Monthly expenses", "\u2248 CHF 4\u2019700", ""], ["Buffer still to build", "+CHF 28\u2019000", "pos"]],
      result: ["Target safety buffer", "6 months"], cta: "Open a Swissquote savings account" },
    { cat: "Swissquote", catTone: "swissquote", pts: 2,
      title: "Keep your capital portable",
      benefit: "Avoid CH-locked assets you can't move",
      body: "With a possible departure in ~8 years, design the plan so your 3a, 2nd pillar and vested benefits stay flexible. Portability usually outweighs locking capital into CH-only products.",
      math: [["Possible departure", "~8 years", ""], ["Vested-benefits on exit", "yes", ""], ["CH-locked capital", "minimise", "pos"]],
      result: ["Plan flexibility", "Preserved"], cta: "Talk portability with Swissquote" },
    { cat: "Swissquote", catTone: "swissquote",
      title: "Invest your 3a in equities",
      benefit: "Boost long-term 3a growth by ~2\u20133% p.a.",
      body: "With a 31-year horizon, a diversified equity 3a instead of cash could add \u2248 CHF 40\u2019000\u201360\u2019000 of capital by 65. Swissquote offers self-directed 3a investing with full equity exposure.",
      math: [["Horizon to 65", "31 years", ""], ["Equity uplift", "~3% p.a.", ""], ["Extra capital at 65", "+CHF 50\u2019000", "pos"]],
      result: ["Estimated extra capital at 65", "CHF 50\u2019000"], cta: "Invest my 3a in equities" },
    { cat: "Wealth", catTone: "wealth",
      title: "Automate your monthly 3a",
      benefit: "Never miss the annual cap again",
      body: "A standing order of \u2248 CHF 605/month fills the 3a cap automatically and smooths the cost across the year, so contributions happen before lifestyle spending does.",
      math: [["3a cap 2026", "CHF 7\u2019258", ""], ["Monthly standing order", "\u2248 CHF 605", ""], ["Cap reached", "every year", "pos"]],
      result: ["Annual cap captured", "100%"], cta: "Set up auto-contributions" },
    { cat: "Pension", catTone: "pension",
      title: "Add disability & life cover",
      benefit: "Protect your income while you build",
      body: "As a single earner with thin Swiss assets, a long-term illness or accident would hit hard. Right-sized disability and term-life cover protects the plan you're building, cheapest while you're young.",
      math: [["Swiss assets today", "thin", ""], ["Dependants", "single earner", ""], ["Cover cost at 34", "lowest", "pos"]],
      result: ["Income protection", "Secured"], cta: "Review my protection" },
  ];

  // ── Report blocks (Yvan's spec §5: portrait, income, wealth-score, deductions, tax, insights, lombard, real-estate) ──
  caroline.verifiedFields = ["grossIncome", "pillar2", "pillar3a"]; caroline.objectivesSet = true;
  caroline.report = {
    portrait: "Caroline, you're a 42-year-old employed professional in Geneva, married, two children, with a mortgaged flat. A CHF 132\u2019000 income and CHF 396\u2019000 net worth put you on solid footing, but a single 3a account and an untouched pension-fund buy-in are clear, low-effort upside. Across all three pillars you're funded to about 77% of your target, a closable CHF 1\u2019570/month gap, no lifestyle cut required.",
    incomeSources: [{ l: "Employment", pct: 86, color: "#3B82F6" }, { l: "Investments", pct: 8, color: "#12A454" }, { l: "Pillar 3a growth", pct: 6, color: "#FA5B35" }],
    wealthDims: [{ l: "Retirement readiness", s: 15 }, { l: "Tax efficiency", s: 12 }, { l: "3a optimisation", s: 11 }, { l: "Income stability", s: 18 }, { l: "Pension coverage", s: 13 }],
    deductions: [{ l: "Childcare", amt: 10100 }, { l: "Professional expenses", amt: 4300 }, { l: "Insurance premiums", amt: 3500 }, { l: "Pillar 3a", amt: 3200 }, { l: "Pension buy-in", amt: 0 }],
    taxProfile: [["Taxable income", "CHF 118\u2019400"], ["Marginal rate (GE)", "~32%"], ["Effective rate", "18.4%"], ["Wealth-tax base", "CHF 396\u2019000"], ["Canton", "Geneva"]],
    insights: [
      { kind: "opportunity", icon: "ri-lightbulb-flash-line", t: "Pillar 3a is under-used", d: "You've paid CHF 3\u2019200 of the CHF 7\u2019258 cap, the single biggest, lowest-effort mover." },
      { kind: "risk", icon: "ri-alert-line", t: "One 3a account → withdrawal-tax progression", d: "A single 3a heading past CHF 50\u2019000 will be taxed in one tranche. Splitting accounts staggers it." },
      { kind: "info", icon: "ri-government-line", t: "Retroactive 3a buy-ins now allowed", d: "New from 2025/26, you may top up missed years, up to ~10 back, under conditions." },
    ],
    lombard: { buyback: 30000, rate: 4.5, marginal: 32, taxSaved: 9600, pension: 410 },
    realEstate: [{ name: "Flat \u00b7 Geneva", fiscal: 680000, mortgage: 520000 }],
  };
  bergerRey.verifiedFields = ["grossIncome", "pillar2", "pillar3a", "netWorth", "canton"]; bergerRey.objectivesSet = true;
  bergerRey.report = {
    portrait: "Thomas (46) and Sandrine (44) earn CHF 362\u2019000 between you and hold ~CHF 1.45M net worth plus a CHF 2.2M home in Founex. You're broadly on track for income, but three structural risks dominate: concentration (property + one securities line is 61% of net worth), Sandrine's missing 2nd pillar, and the lump-sum withdrawal tax if pension capital is taken in few tranches. The levers here are tax buy-ins and diversification, not saving more.",
    incomeSources: [{ l: "Thomas \u00b7 employment", pct: 64, color: "#3B82F6" }, { l: "Sandrine \u00b7 self-employed", pct: 24, color: "#FA5B35" }, { l: "Securities", pct: 9, color: "#12A454" }, { l: "Rental", pct: 3, color: "#6D28D9" }],
    wealthDims: [{ l: "Retirement readiness", s: 18 }, { l: "Tax efficiency", s: 12 }, { l: "3a optimisation", s: 14 }, { l: "Income stability", s: 16 }, { l: "Pension coverage", s: 11 }],
    deductions: [{ l: "Pension buy-in (capacity)", amt: 37000 }, { l: "Mortgage interest", amt: 24000 }, { l: "Sandrine large 3a", amt: 22000 }, { l: "Thomas 3a", amt: 7258 }, { l: "Insurance premiums", amt: 6400 }],
    taxProfile: [["Taxable income", "CHF 318\u2019000"], ["Marginal rate (VD)", "~41%"], ["Effective rate", "24.6%"], ["Wealth-tax base", "CHF 1\u2019450\u2019000"], ["Canton", "Vaud"]],
    insights: [
      { kind: "risk", icon: "ri-pie-chart-2-line", t: "Concentration risk", d: "Property + a single securities line is 61% of net worth, diversify to the 17-year horizon." },
      { kind: "risk", icon: "ri-shield-cross-line", t: "Sandrine's protection gap", d: "No 2nd pillar means thin survivor/disability cover, size term cover to the household's liabilities." },
      { kind: "opportunity", icon: "ri-bank-line", t: "CHF 184\u2019000 buy-in capacity", d: "Staged over ~5 years, tax-deductible at ~41%, the highest-value lever on the table." },
    ],
    lombard: { buyback: 37000, rate: 4.5, marginal: 41, taxSaved: 15170, pension: 200 },
    realEstate: [{ name: "Home \u00b7 Founex (VD)", fiscal: 1850000, mortgage: 1100000 }],
  };
  whitmore.verifiedFields = ["pillar3a"]; whitmore.objectivesSet = true;
  whitmore.report = {
    portrait: "James, 34, arrived in Switzerland in March 2025 on a CHF 119\u2019000 salary. Your Swiss assets are thin, a new LPP (~CHF 9\u2019200), a new 3a (CHF 3\u2019000) and CHF 28\u2019000 in cash, and your CH history is short. But a high income and a 31-year horizon give you strong potential if you start now. Mobility is the key planning variable: design the plan to stay portable in case you leave.",
    incomeSources: [{ l: "Employment", pct: 97, color: "#3B82F6" }, { l: "Pillar 3a growth", pct: 3, color: "#FA5B35" }],
    wealthDims: [{ l: "Retirement readiness", s: 7 }, { l: "Tax efficiency", s: 9 }, { l: "3a optimisation", s: 8 }, { l: "Income stability", s: 14 }, { l: "Pension coverage", s: 6 }],
    deductions: [{ l: "Pillar 3a", amt: 3000 }, { l: "Professional expenses", amt: 3800 }, { l: "Insurance premiums", amt: 2600 }, { l: "Pension buy-in", amt: 0 }],
    taxProfile: [["Taxable income", "CHF 108\u2019200"], ["Marginal rate (VD)", "~30%"], ["Effective rate", "16.1%"], ["Wealth-tax base", "CHF 31\u2019000"], ["Canton", "Vaud"]],
    insights: [
      { kind: "opportunity", icon: "ri-safe-2-line", t: "Max your 3a now", d: "CHF 4\u2019258 of headroom this year, then retroactive buy-ins for partial years, start the compounding clock." },
      { kind: "risk", icon: "ri-flight-takeoff-line", t: "Mobility risk", d: "A possible departure in ~8 years means avoid CH-locked capital you can't move efficiently." },
      { kind: "info", icon: "ri-water-flash-line", t: "Build a 6-month buffer first", d: "Cash is ~3 months of expenses; reach ~6 before any property commitment." },
    ],
    lombard: null,
    realEstate: [],
  };

  // ── Monitoring content (persona-aware), drives the "always-on" page ──
  bergerRey.monitor = {
    status: "All systems monitoring",
    nextReview: "Jan 2027 · tax-season sweep",
    cadence: "Checked daily · last sync just now",
    nudges: [
      { label: "advice", icon: "ri-bank-line", meta: "2nd pillar · Thomas", h: "Stage your next CHF 37\u2019000 buy-in", p: "Spreading the buy-in keeps each year's deduction inside your ~41% band. The 2026 window closes 31 Dec.", cta: "Plan the buy-in", deadline: "Dec 31, 2026" },
      { label: "advice", icon: "ri-pie-chart-2-line", meta: "Diversification", h: "Trim the 61% concentration", p: "Property plus a single securities line is 61% of net worth. A phased rebalance cuts drawdown risk before retirement.", cta: "Review allocation" },
      { label: "info", icon: "ri-shield-cross-line", meta: "Protection · Sandrine", h: "Sandrine's survivor cover is thin", p: "With no 2nd pillar, term cover sized to your mortgage protects the household.", cta: "See protection" },
    ],
    deadlines: [
      { m: "DEC", d: "31", t: "Max pillar 3a (\u00d72 accounts)", s: "Both 2026 contributions", amt: "CHF 14\u2019516" },
      { m: "JAN", d: "15", t: "Stage LPP buy-in", s: "Year 1 of 5", amt: "CHF 37\u2019000" },
      { m: "MAR", d: "31", t: "Vaud tax filing", s: "Deductions applied", amt: "" },
    ],
  };
  whitmore.monitor = {
    status: "Monitoring · building phase",
    nextReview: "Dec 2026 · year-end 3a sweep",
    cadence: "Checked daily · last sync just now",
    nudges: [
      { label: "advice", icon: "ri-safe-2-line", meta: "3a · 2026", h: "Top up your 3a before year-end", p: "You've used CHF 3\u2019000 of CHF 7\u2019258. Topping up the rest is your single biggest score-mover this year.", cta: "Top up CHF 4\u2019258", deadline: "Dec 31, 2026" },
      { label: "info", icon: "ri-water-flash-line", meta: "Liquidity", h: "Build toward a 6-month buffer", p: "You're at ~3 months. Reaching 6 is what makes a future property simulation flip to GO.", cta: "Set a savings goal" },
      { label: "info", icon: "ri-flight-takeoff-line", meta: "Mobility", h: "Keep your plan portable", p: "If you may leave Switzerland, I'll keep your vested benefits and 3a flexible.", cta: "Learn about portability" },
    ],
    deadlines: [
      { m: "DEC", d: "31", t: "Top up pillar 3a", s: "Remaining 2026 headroom", amt: "CHF 4\u2019258" },
      { m: "Q1", d: "\u2192", t: "Build 6-month buffer", s: "~CHF 28\u2019000 to target", amt: "" },
      { m: "YR", d: "\u2713", t: "AVS continuity check", s: "Avoid 1st-pillar gaps", amt: "" },
    ],
  };

  // ── 2029 future snapshots, drive the Monitoring scene only ──────────
  // Personas advanced ~4 years; they've executed the plan, so wealth, score
  // and timeline have moved on, with once-future events now done + new ones.
  bergerRey.future = {
    year: 2029, ageLabel: "Thomas 50 · Sandrine 48",
    age: 50, status: "Married · 2 kids · Thomas 50 / Sandrine 48",
    headline: "Strong and de-risked, staying the course",
    readiness: { score: 88, verdict: "Strong and de-risked, staying the course", sub: "It's 2029. The staged buy-ins are nearly complete, the portfolio is rebalanced and Sandrine is covered. You're on track to ~CHF 2.9M of pension capital by 63, the amount that funds CHF 16'200/month alongside your AHV pension.", today: 14600, planned: 16200, upliftPct: 11 },
    scenarios: [
      { age: 61, inc: "CHF 14\u2019900", pct: "93% of target", tag: "tight", tagTxt: "Stretch" },
      { age: 63, inc: "CHF 16\u2019200", pct: "101% of target", tag: "ok", tagTxt: "On plan", hl: true },
      { age: 65, inc: "CHF 17\u2019900", pct: "112% of target", tag: "ok", tagTxt: "Surplus" },
    ],
    subScores: { funding: 92, tax: 72, diversification: 78, liquidity: 77, protection: 72 },
    kpis: [
      { lbl: "Projected income", val: "CHF 16\u2019200", sub: "per month at 63", tone: "green", tag: "101% of target" },
      { lbl: "Pension capital", val: "CHF 1\u2019486\u2019000", sub: "2nd + 3rd pillar today", tone: "green", tag: "+CHF 571k since 2025" },
      { lbl: "Concentration", val: "44%", sub: "down from 61%", tone: "green", tag: "De-risked" },
      { lbl: "Provence home", val: "EUR 500\u2019000", sub: "owned since 2027", tone: "amber", tag: "FR tax to watch" },
    ],
    journey: { years: 13, nowAge: 50, retireAge: 63, contribNow: 7600, contribPlanned: 8200, totalContrib: 1640000, projectedFund: 2900000, progressPct: 63, confidence: "High confidence" },
    takeAction: null,
    advisories: [
      { rank: 1, title: "Complete the final LPP buy-in", label: "advice", impact: 280, effort: 1, benefit: "Locks the last high-band deduction", desc: "Year 5 of 5, the closing CHF 37\u2019000 finishes the buy-in and the 3-year withdrawal lock is already satisfied." },
      { rank: 2, title: "Optimise your Provence French tax", label: "advice", impact: 0, impactNote: "cross-border", effort: 2, benefit: "Keeps the second home efficient", desc: "Taxe fonci\u00e8re and the IFI wealth-tax threshold now apply, a yearly review avoids surprises." },
      { rank: 3, title: "Pre-fund the 2031 university years", label: "advice", impact: 0, impactNote: "protects 3a", effort: 1, benefit: "Protects your contributions", desc: "Setting aside now smooths two overlapping years of costs without touching pillar 3a." },
      { rank: 4, title: "Shape your capital vs annuity blend", label: "info", impact: 0, impactNote: "13 yrs out", effort: 2, benefit: "Decide calmly, early", desc: "With ~CHF 2.9M projected at 63, the capital needed for your CHF 16'200/month target, it's worth shaping the lump-sum / annuity split now." },
    ],
    monitor: {
      status: "All systems monitoring · 2029", nextReview: "Jan 2030 · tax-season sweep", cadence: "Checked daily · last sync just now",
      nudges: [
        { label: "advice", icon: "ri-bank-line", meta: "2nd pillar · Thomas", h: "Complete the final buy-in tranche", p: "You're in year 4 of 5. The last CHF 37\u2019000 closes the buy-in and locks the deduction, the 3-year withdrawal lock is already satisfied.", cta: "Finish the buy-in", deadline: "Dec 31, 2029" },
        { label: "advice", icon: "ri-france-line", meta: "Provence · French tax", h: "Review your French property tax", p: "Now you own the Provence home, taxe foncière and IFI wealth-tax thresholds apply. A cross-border review keeps it efficient.", cta: "Plan a FR review" },
        { label: "info", icon: "ri-graduation-cap-line", meta: "Family · 2031", h: "Pre-fund two university years", p: "Both children reach university around 2031, overlapping costs. Setting aside now protects your 3a contributions.", cta: "Model the cashflow" },
        { label: "advice", icon: "ri-scales-3-line", meta: "Retirement · 13 yrs out", h: "Start modelling capital vs annuity", p: "With ~CHF 2.9M projected at 63, what your CHF 16'200/month target needs, it's worth shaping the lump-sum / annuity blend early.", cta: "Open the decision" },
      ],
      deadlines: [
        { m: "DEC", d: "31", t: "Final LPP buy-in tranche", s: "2029 · year 5 of 5", amt: "CHF 37\u2019000" },
        { m: "MAR", d: "15", t: "French property tax filing", s: "2030 · taxe foncière · IFI", amt: "" },
        { m: "SEP", d: "01", t: "University pre-fund", s: "2030 · 2031 run-up", amt: "CHF 30\u2019000" },
      ],
    },
    calendar: [
      { id: "f0", yr: "2025", age: 46, t: "Plan created", d: "Snapshot from the joint tax statement.", type: "milestone", state: "done" },
      { id: "f1", yr: "2026", age: 47, t: "Started staged LPP buy-ins", d: "CHF 37k/yr, deduction in the high band.", type: "save", state: "done", amt: "CHF 148\u2019000 so far" },
      { id: "f2", yr: "2027", age: 48, t: "Bought the Provence home", d: "EUR 500k, simulation flipped to GO.", type: "property", state: "done" },
      { id: "f3", yr: "2029", age: 50, t: "Final buy-in + Sandrine's cover", d: "Closing the buy-in; survivor cover added.", type: "save", state: "now", amt: "CHF 37\u2019000" },
      { id: "f4", yr: "2031", age: 52, t: "Children to university", d: "Two overlapping years of costs.", type: "family", state: "next" },
      { id: "f5", yr: "2042", age: 63, t: "Retirement (Thomas)", d: "Capital vs annuity, with a human.", type: "retire", state: "next" },
    ],
  };

  whitmore.future = {
    year: 2029, ageLabel: "James 38",
    age: 38, status: "British · single · resident since 2025",
    headline: "Real momentum, the runway is paying off",
    readiness: { score: 54, verdict: "Real momentum, the runway is paying off", sub: "It's 2029. Four years of maxed 3a, a full 6-month buffer and a promotion have moved James from fragile to building. He needs ~CHF 910k of pension capital for his CHF 6'300/month target at 65, he's now on a credible path to it, with a first property and a 2nd-pillar buy-in within reach.", today: 2600, planned: 4900, upliftPct: 88 },
    scenarios: [
      { age: 63, inc: "CHF 4\u2019000", pct: "63% of target", tag: "tight", tagTxt: "Short" },
      { age: 65, inc: "CHF 4\u2019900", pct: "78% of target", tag: "tight", tagTxt: "Building", hl: true },
      { age: 67, inc: "CHF 5\u2019700", pct: "90% of target", tag: "ok", tagTxt: "Comfortable" },
    ],
    subScores: { funding: 52, tax: 62, diversification: 48, liquidity: 66, protection: 46 },
    kpis: [
      { lbl: "Pension capital", val: "CHF 84\u2019000", sub: "2nd + 3rd pillar", tone: "green", tag: "+CHF 72k since 2025" },
      { lbl: "Liquidity", val: "CHF 56\u2019000", sub: "~6 months · target met", tone: "green", tag: "Buffer built" },
      { lbl: "Income", val: "CHF 138\u2019000", sub: "after 2028 promotion", tone: "green", tag: "+16%" },
      { lbl: "Buy-in capacity", val: "CHF 41\u2019000", sub: "newly available", tone: "amber", tag: "Opportunity" },
    ],
    journey: { years: 27, nowAge: 38, retireAge: 65, contribNow: 920, contribPlanned: 1480, totalContrib: 312000, projectedFund: 724000, progressPct: 16, confidence: "Medium\u2013high confidence" },
    takeAction: null,
    advisories: [
      { rank: 1, title: "Run your first-property simulation", label: "advice", impact: 0, impactNote: "now feasible", effort: 2, benefit: "Your buffer makes it a GO", desc: "With a full 6-month reserve and a higher salary, a Swiss primary residence now simulates to GO." },
      { rank: 2, title: "Open a pillar-2 buy-in", label: "advice", impact: 240, effort: 1, benefit: "New capacity from your raise", desc: "Your promotion created CHF 41\u2019000 of buy-in room, a tax-efficient lift to pension and deduction." },
      { rank: 3, title: "Consolidate your vested benefits", label: "info", impact: 0, impactNote: "simpler", effort: 1, benefit: "Simpler, better terms", desc: "Now you're staying in Switzerland, merging earlier accounts streamlines and can improve terms." },
      { rank: 4, title: "Keep maxing your pillar 3a", label: "advice", impact: 180, effort: 1, benefit: "Compounds your runway", desc: "Filling the 2029 cap every year stays your single most reliable score-mover." },
    ],
    monitor: {
      status: "Monitoring · scaling phase · 2029", nextReview: "Dec 2029 · year-end 3a sweep", cadence: "Checked daily · last sync just now",
      nudges: [
        { label: "advice", icon: "ri-home-4-line", meta: "Property · now feasible", h: "You're ready for a first property", p: "With a full 6-month buffer and a higher salary, a Swiss primary residence now simulates to GO. Worth running before prices move.", cta: "Run the simulation", deadline: "" },
        { label: "advice", icon: "ri-bank-line", meta: "2nd pillar", h: "Open a pillar-2 buy-in", p: "Your promotion created CHF 41\u2019000 of buy-in capacity, a tax-efficient way to lift both your pension and this year's deduction.", cta: "Plan a buy-in" },
        { label: "info", icon: "ri-anchor-line", meta: "CH commitment", h: "Consolidate your vested benefits", p: "Now you're staying in Switzerland, consolidating earlier vested-benefits accounts simplifies and can improve terms.", cta: "Review accounts" },
      ],
      deadlines: [
        { m: "DEC", d: "31", t: "Max pillar 3a", s: "2029 · annual cap", amt: "CHF 7\u2019560" },
        { m: "APR", d: "30", t: "Mortgage pre-approval", s: "2030 · first property", amt: "" },
        { m: "JUN", d: "30", t: "Pillar-2 buy-in", s: "2030 · new capacity", amt: "CHF 41\u2019000" },
      ],
    },
    calendar: [
      { id: "f0", yr: "2025", age: 34, t: "Arrived in Switzerland", d: "New LPP + first 3a opened.", type: "milestone", state: "done" },
      { id: "f1", yr: "2026", age: 35, t: "Maxed 3a + started buffer", d: "Full cap every year since.", type: "save", state: "done", amt: "CHF 29\u2019000 in 3a" },
      { id: "f2", yr: "2028", age: 37, t: "Promotion (+16% salary)", d: "Created buy-in capacity.", type: "work", state: "done" },
      { id: "f3", yr: "2029", age: 38, t: "6-month buffer reached", d: "Decided to stay in Switzerland.", type: "milestone", state: "now" },
      { id: "f4", yr: "2031", age: 40, t: "First property (CH)", d: "Simulation now flips to GO.", type: "property", state: "next" },
      { id: "f5", yr: "2056", age: 65, t: "Retirement", d: "Capital vs annuity, in CH.", type: "retire", state: "next" },
    ],
  };

  window.PP_PERSONAS = {
    order: ["bergerRey", "whitmore"],
    caroline, bergerRey, whitmore,
    education: window.PP_DATA.v2.education,
  };
  // Reference personas onboarded via document upload → fields are verified (high confidence).
  bergerRey.verifiedFields = ["grossIncome", "pillar2", "pillar3a", "netWorth", "canton", "status"];
  whitmore.verifiedFields = ["grossIncome", "pillar3a", "canton"];
})();
