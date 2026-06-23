/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, data model + scripted content (Caroline, Geneva)
   All CHF figures use Swiss formatting (apostrophe thousands).
   Numbers are illustrative defaults from the assumptions registry.
   window.PP_DATA / window.PP_I18N
   ════════════════════════════════════════════════════════════════ */
(function () {
  const chf = (n) => "CHF " + Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019");

  const persona = {
    name: "Caroline Berger",
    first: "Caroline",
    initials: "CB",
    age: 42,
    canton: "Geneva",
    status: "Married · 2 children",
    employment: "Employed",
    grossIncome: 132000,
    netMonthly: 8400,
    retireTarget: 64,
    referenceAge: 65,
    targetPct: 80,
    targetMonthly: 6700,
    targetYearly: 80400,
  };

  // ── Snapshot: three pillars projected to age 64 ──
  const pillars = [
    {
      id: "p1", code: "1", tag: "AVS / AHV", name: "State pension",
      desc: "1st pillar · pay-as-you-go", capital: null, capitalLabel: "Estimate",
      pensionYr: 26200, monthly: 2183, estimate: true,
      note: "Estimated from your contribution years, official AVS figures to confirm.",
    },
    {
      id: "p2", code: "2", tag: "LPP / BVG", name: "Occupational pension",
      desc: "2nd pillar · accrued capital", capital: 312400, capitalLabel: "Accrued",
      pensionYr: 28900, monthly: 2408, estimate: false,
      note: "From your confirmed pension-fund certificate.",
    },
    {
      id: "p3", code: "3a", tag: "Pillar 3a", name: "Private pension",
      desc: "Tied · 1 account today", capital: 41800, capitalLabel: "Balance",
      pensionYr: 6500, monthly: 542, estimate: false,
      note: "Projected if you keep contributing at today's rate.",
    },
  ];

  const snapshot = {
    projectedMonthly: 5133,
    projectedYearly: 61600,
    targetMonthly: 6700,
    targetYearly: 80400,
    gapMonthly: 1570,
    gapYearly: 18800,
    fundedPct: 77,
    // income bar segments as % of target (monthly)
    seg: { p1: 32.6, p2: 35.9, p3: 8.1, gap: 23.4 },
  };

  // ── Ranked levers ──
  const levers = [
    {
      rank: 1, title: "Max your pillar 3a every year",
      desc: "You've paid CHF 3\u2019200 of the 2026 maximum. Topping up and holding a securities-based 3a for your long horizon is the single biggest mover.",
      impact: 520, effort: 1, label: "advice",
      math: [
        ["Inputs", "Paid CHF 3\u2019200 of 2026 max <b>CHF 7\u2019258</b>; 22 years to age 64; one cash 3a today."],
        ["Assumption", "2.5% net real return on a securities-based 3a; contributions indexed to the cap."],
        ["Result", "Extra capital at 64 \u2248 <b>CHF 138\u2019000</b> \u2192 about <b>CHF 520/month</b> of retirement income."],
      ],
      rule: "3a cap 2026 · CHF 7\u2019258 (with pension fund)",
    },
    {
      rank: 2, title: "Make a pension-fund buy-in (rachat)",
      desc: "Your certificate shows CHF 86\u2019000 of buy-in capacity. A CHF 30\u2019000 buy-in lifts your 2nd-pillar pension and is tax-deductible this year.",
      impact: 410, effort: 2, label: "advice",
      math: [
        ["Inputs", "Buy-in capacity <b>CHF 86\u2019000</b>; Geneva marginal tax \u2248 32%; buy-in CHF 30\u2019000."],
        ["Assumption", "Conversion basis held; 3-year lock before any capital withdrawal respected."],
        ["Result", "Tax saved now \u2248 <b>CHF 9\u2019600</b>; future pension +\u2248 <b>CHF 410/month</b>."],
      ],
      rule: "LPP voluntary buy-in · 3-year withdrawal lock applies",
    },
    {
      rank: 3, title: "Work to reference age 65, not 64",
      desc: "One extra year of contributions and conversion removes the early-retirement reduction. A lifestyle choice, but high-impact.",
      impact: 300, effort: 3, label: "info",
      math: [
        ["Inputs", "Target 64 vs reference age <b>65</b>; one extra year of 2nd-pillar + AVS accrual."],
        ["Assumption", "No early-AVS reduction; salary held flat in the final year."],
        ["Result", "Combined uplift \u2248 <b>CHF 300/month</b> for life."],
      ],
      rule: "AVS 21 · women's reference age 65",
    },
    {
      rank: 4, title: "Use the new retroactive 3a buy-in",
      desc: "From 2025/26 you can top up missed 3a years (up to ~10 back) under conditions. A staged catch-up that's also tax-deductible.",
      impact: 240, effort: 2, label: "advice",
      math: [
        ["Inputs", "Several past years below the 3a cap; staged top-ups of ~CHF 6\u2019000/yr."],
        ["Assumption", "Eligibility conditions met; same 2.5% net real return."],
        ["Result", "Extra capital \u2248 <b>CHF 64\u2019000</b> \u2192 about <b>CHF 240/month</b>."],
      ],
      rule: "Retroactive 3a buy-in · new from 2025/26",
    },
    {
      rank: 5, title: "Open a 2nd 3a account to stagger withdrawals",
      desc: "Splitting your 3a across accounts lets you draw them in different years and break the one-off withdrawal-tax progression.",
      impact: 0, impactNote: "saves \u2248 CHF 14\u2019000", effort: 1, label: "info",
      math: [
        ["Inputs", "Single 3a heading past <b>CHF 50\u2019000</b>; Geneva lump-sum withdrawal tax is progressive."],
        ["Assumption", "Withdrawals spread over 3 separate tax years near retirement."],
        ["Result", "One-off withdrawal tax cut by \u2248 <b>CHF 14\u2019000</b> over retirement."],
      ],
      rule: "Staggered capital withdrawal · cantonal lump-sum tax",
    },
  ];

  // ── OCR confirm/correct (LPP certificate) ──
  const ocr = {
    docTitle: "Pension-fund certificate", docMeta: "Certificat LPP · 2026 · Caisse de pension",
    fields: [
      { key: "accrued", label: "Accrued capital (avoir de prévoyance)", value: "312\u2019400", unit: "CHF", conf: 98, level: "high" },
      { key: "pension", label: "Projected pension at 65", value: "28\u2019900", unit: "CHF/yr", conf: 96, level: "high" },
      { key: "salary", label: "Insured salary", value: "118\u2019200", unit: "CHF", conf: 95, level: "high" },
      { key: "conv", label: "Conversion rate", value: "5.20", unit: "%", conf: 82, level: "med" },
      { key: "death", label: "Death / disability pension", value: "17\u2019340", unit: "CHF/yr", conf: 79, level: "med" },
      { key: "buyin", label: "Buy-in potential (rachat)", value: "8\u2019600", correct: "86\u2019000", unit: "CHF", conf: 54, level: "low" },
    ],
  };

  // ── Document upload checklist ──
  const docs = [
    { key: "lpp", t: "Pension-fund certificate", d: "Certificat LPP / Vorsorgeausweis", icon: "ri-bank-line" },
    { key: "3a", t: "3a statement", d: "Attestation 3a · 2025", icon: "ri-safe-2-line" },
    { key: "tax", t: "Tax return", d: "Déclaration d'impôts · Genève", icon: "ri-file-text-line" },
  ];

  // ── Gap-fill questions ──
  const gapfill = [
    { key: "household", q: "Who's in your household?", opts: ["Just me", "Couple", "Couple + children"], sel: "Couple + children" },
    { key: "property", q: "Do you own your home?", opts: ["Renting", "Own with mortgage", "Own outright"], sel: "Own with mortgage" },
    { key: "target", q: "When would you like to retire?", opts: ["At 62", "At 64", "At 65", "Not sure yet"], sel: "At 64" },
    { key: "lifestyle", q: "What retirement income are you aiming for?", opts: ["~80% of today's income", "A specific amount", "Help me decide"], sel: "~80% of today's income" },
  ];

  // ── Property life event: WEF vs pledge ──
  const property = {
    headline: "Buying a CHF 1.2M family home · deploying CHF 100\u2019000 of pension",
    options: [
      {
        id: "wef", icon: "ri-bank-card-line", t: "WEF withdrawal", sub: "Take CHF 100\u2019000 out of your 2nd pillar", rec: false,
        metrics: [
          { l: "Retirement pension effect at 64", v: "\u2212 CHF 430 / month", tone: "loss", n: "Capital leaves the fund, so future conversion is lower." },
          { l: "One-off withdrawal tax (Geneva)", v: "CHF 5\u2019900", tone: "", n: "Charged at a reduced lump-sum rate, separate from income." },
          { l: "Cover & flexibility", v: "Lower death / disability", tone: "", n: "You can repay later; a 3-year lock then applies before buy-ins." },
        ],
      },
      {
        id: "pledge", icon: "ri-lock-2-line", t: "Pledge (nantissement)", sub: "Keep the CHF 100\u2019000 invested as collateral", rec: true,
        metrics: [
          { l: "Retirement pension effect at 64", v: "No change", tone: "gain", n: "Your capital stays in the fund and keeps compounding." },
          { l: "Extra annual cost", v: "+ CHF 1\u2019350 / year", tone: "", n: "Interest on a slightly larger mortgage while pledged." },
          { l: "Cover & flexibility", v: "Cover preserved", tone: "", n: "Needs affordability headroom, which your income supports." },
        ],
      },
    ],
  };

  // ── Stress test: retire early ──
  const stress = {
    min: 60, max: 67, def: 62, reference: 65,
    verdicts: {
      60: { tone: "no", t: "Out of reach today", d: "A four-year bridge before AVS plus a deep conversion cut leaves too large a hole.", conf: "High" },
      61: { tone: "no", t: "Very stretched", d: "Three-plus years of bridging income and a meaningful pension cut.", conf: "High" },
      62: { tone: "tight", t: "Tight, feasible with trade-offs", d: "Workable if you buy in now, bridge with 3a + vested benefits, and defer your AVS claim to 65.", conf: "Medium" },
      63: { tone: "tight", t: "Within reach", d: "A two-year bridge and a modest pension cut, comfortably closable with the levers below.", conf: "Medium" },
      64: { tone: "ok", t: "On plan", d: "Your current target. The CHF 1\u2019570 gap is closable with the ranked levers.", conf: "High" },
      65: { tone: "ok", t: "Comfortable", d: "Full reference age, no early reduction, maximum conversion and AVS.", conf: "High" },
      66: { tone: "ok", t: "Surplus building", d: "Deferring adds an AVS bonus and another year of growth.", conf: "High" },
      67: { tone: "ok", t: "Strong surplus", d: "Two years of deferral materially lifts every pillar.", conf: "High" },
    },
    bridge: [
      { yr: "Age 62", amt: "CHF 26\u2019200", src: "from 3a + vested benefits" },
      { yr: "Age 63", amt: "CHF 26\u2019200", src: "from 3a + vested benefits" },
      { yr: "Age 64", amt: "CHF 26\u2019200", src: "bridge until AVS at 65" },
    ],
    levers: ["Buy in now while deductible", "Bridge with 3a + vested benefits", "Defer AVS claim to 65", "Part-time 62 \u2192 64"],
  };

  // ── Monitoring home ──
  const monitor = {
    nudges: [
      {
        kind: "deadline", icon: "ri-calendar-todo-line", meta: "Contribution deadline",
        h: "Max your 3a before 31 December", deadline: "24 days left",
        p: "You've paid CHF 3\u2019200 of the 2026 maximum. Topping up the remaining <b>CHF 4\u2019058</b> is fully deductible this tax year.",
        cta: "Top up 3a", label: "advice",
      },
      {
        kind: "regulatory", icon: "ri-government-line", meta: "Rule change · 2026",
        h: "Retroactive 3a buy-ins are now possible",
        p: "New from 2025/26: you can top up missed 3a years up to ~10 years back. Based on your history you may be <b>eligible for ~CHF 64\u2019000</b> of catch-up.",
        cta: "Check eligibility", label: "info",
      },
      {
        kind: "drift", icon: "ri-line-chart-line", meta: "Plan drift detected",
        h: "Your buy-in capacity grew after your raise",
        p: "A 4% rise in your insured salary lifted your pension-fund buy-in potential to <b>CHF 92\u2019000</b> (was CHF 86\u2019000).",
        cta: "Review buy-in", label: "info",
      },
    ],
    timeline: [
      { yr: "2024", t: "Plan created", d: "First snapshot built from 3 documents.", state: "done" },
      { yr: "2026 · now", t: "Maxing 3a + reviewing buy-in", d: "Closing the CHF 1\u2019570/month gap.", state: "now" },
      { yr: "2028", t: "Mortgage renewal", d: "We'll re-check WEF vs pledge for you.", state: "next" },
      { yr: "2031", t: "Pension-fund buy-in window", d: "Staged buy-ins, timed for tax.", state: "next" },
      { yr: "2048", t: "Retirement · age 64", d: "Capital vs annuity decision, with a human advisor.", state: "next" },
    ],
    deadlines: [
      { m: "Dec", d: "31", t: "3a top-up", s: "Deductible for 2026", amt: "CHF 4\u2019058" },
      { m: "Mar", d: "31", t: "Tax return", s: "Canton of Geneva", amt: "" },
      { m: "2028", d: "\u2192", t: "Mortgage renewal", s: "Re-plan property", amt: "" },
    ],
  };

  window.PP_DATA = { chf, persona, pillars, snapshot, levers, ocr, docs, gapfill, property, stress, monitor };

  // ── Light i18n for chrome + welcome (content stays EN for the demo) ──
  window.PP_I18N = {
    EN: {
      stages: ["Onboard", "Your Analysis", "Plan", "Dashboard"],
      yourData: "Your data",
      placeholder: "Reply to Pension Partner, or ask anything\u2026",
      disclaimer: "Pension Partner gives information and personal recommendations, clearly labelled. Figures are estimates, not guarantees. Not tax or legal advice.",
      welcomeKicker: "Pension Partner · powered by Swissquote",
      welcomeH: ["Your retirement plan,", "built in minutes, and ", "kept alive."],
      welcomeLede: "Pension Partner reads your pension documents, builds a realistic three-pillar plan, and adapts it every time your life changes, no appointment, no waiting.",
      promise: "I'll always tell you when something is <b>general information</b> versus a <b>personal recommendation</b> for you. Every number traces back to a document you confirmed.",
      start: "Start my Retirement portrait",
      manual: "Prefer to enter things manually?",
    },
    FR: {
      stages: ["Démarrer", "Votre analyse", "Plan", "Tableau de bord"],
      yourData: "Vos donn\u00e9es",
      placeholder: "R\u00e9pondez \u00e0 Pension Partner, ou posez une question\u2026",
      disclaimer: "Pension Partner fournit de l'information et des recommandations personnelles, clairement indiqu\u00e9es. Les chiffres sont des estimations, pas des garanties. Ni conseil fiscal ni juridique.",
      welcomeKicker: "Pension Partner · propuls\u00e9 par Swissquote",
      welcomeH: ["Votre plan de retraite,", "en quelques minutes, et ", "toujours \u00e0 jour."],
      welcomeLede: "Pension Partner lit vos documents de pr\u00e9voyance, construit un plan r\u00e9aliste sur les trois piliers, et l'adapte \u00e0 chaque \u00e9v\u00e9nement de votre vie, sans rendez-vous.",
      promise: "Je vous indiquerai toujours s'il s'agit d'une <b>information g\u00e9n\u00e9rale</b> ou d'une <b>recommandation personnelle</b>. Chaque chiffre renvoie \u00e0 un document que vous avez valid\u00e9.",
      start: "Démarrer mon portrait retraite",
      manual: "Vous pr\u00e9f\u00e9rez saisir manuellement\u00a0?",
    },
  };
})();
