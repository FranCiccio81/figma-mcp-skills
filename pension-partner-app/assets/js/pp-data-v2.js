/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, V2 "Readiness report" data layer
   Extends window.PP_DATA.v2 with figures derived from Caroline's plan
   (same persona as V1) plus the projection / journey / annuity /
   education / to-do content drawn from the Swissquote prototype PDF.
   window.PP_DATA.v2
   ════════════════════════════════════════════════════════════════ */
(function () {
  const PD = window.PP_DATA;
  const chf = PD.chf;

  // ── Readiness score & gamified levels ────────────────────────────
  const readiness = {
    score: 77,                // % on track (ties to snapshot.fundedPct)
    verdict: "On track, with room to climb",
    sub: "Your three pillars cover 77% of your CHF 6\u2019700 monthly target. The CHF 1\u2019570 gap is closable with the levers below, no lifestyle cut required.",
    // monthly pension uplift (today's plan → with levers applied)
    today: 5133, planned: 6700, upliftPct: 30.5,
  };

  const levels = [
    { id: "critical", name: "At risk",   range: "0–40",  lo: 0, hi: 40 },
    { id: "caution",  name: "Building",  range: "40–60", lo: 40, hi: 60 },
    { id: "moderate", name: "Moderate",  range: "60–72", lo: 60, hi: 72 },
    { id: "good",     name: "On track",  range: "72–85", lo: 72, hi: 85 },
    { id: "excellent", name: "Secure",    range: "85–100", lo: 85, hi: 100 },
  ];
  const levelUp = {
    to: "Secure",
    delta: "+8 points",
    steps: [
      { t: "Max your pillar 3a for 2026", d: "Adds ~CHF 520/month of retirement income.", label: "advice" },
      { t: "Make a CHF 30\u2019000 pension-fund buy-in", d: "Lifts your 2nd-pillar pension and saves ~CHF 9\u2019600 in tax now.", label: "advice" },
    ],
  };

  // ── Projection chart (pension capital over time) ─────────────────
  // Two lines: current trajectory vs planned (levers applied), with a
  // confidence band around the planned line. Ages 42 → 85.
  const projection = {
    startAge: 42, retireAge: 64, endAge: 85,
    yTicks: [1000000, 750000, 500000, 250000],
    yMax: 1050000,
    // [age, capital]
    current: [[42,354200],[48,452000],[54,560000],[60,672000],[64,742000],[70,612000],[78,388000],[85,176000]],
    planned: [[42,354200],[48,489000],[54,632000],[60,792000],[64,915000],[70,792000],[78,548000],[85,322000]],
    bandLo:  [[42,354200],[48,470000],[54,598000],[60,742000],[64,852000],[70,724000],[78,486000],[85,262000]],
    bandHi:  [[42,354200],[48,508000],[54,672000],[60,846000],[64,982000],[70,864000],[78,612000],[85,388000]],
    peak: { age: 64, value: 915000 },
    confidence: "High confidence",
  };

  // ── Retirement journey row ───────────────────────────────────────
  const journey = {
    years: 22, nowAge: 42, retireAge: 64,
    contribNow: 530, contribPlanned: 1140,
    totalContrib: 224000, projectedFund: 915000,
    progressPct: 39, confidence: "High confidence",
  };

  // ── KPI strip ────────────────────────────────────────────────────
  const kpis = [
    { lbl: "Projected income", val: "CHF 5\u2019133", sub: "per month at 64", tone: "amber", tag: "77% of target" },
    { lbl: "Monthly gap", val: "CHF 1\u2019570", sub: "vs CHF 6\u2019700 target", tone: "amber", tag: "Closable" },
    { lbl: "Pension capital", val: "CHF 354\u2019200", sub: "2nd + 3rd pillar today", tone: "green", tag: "Confirmed" },
    { lbl: "Buy-in capacity", val: "CHF 86\u2019000", sub: "tax-deductible", tone: "green", tag: "Opportunity" },
  ];

  // ── Key decision: lump sum vs lifelong annuity ───────────────────
  const annuity = {
    capital: 915000,
    intro: "Around age 64 you'll make one irreversible choice for your 2nd-pillar capital. Here's the trade-off, in plain terms.",
    options: [
      {
        id: "lump", icon: "ri-wallet-3-line", t: "Lump sum", sub: "Control & flexibility", rec: false,
        head: "Take your CHF 915\u2019000 as capital",
        points: [
          "Full control to invest, gift or fund projects",
          "You manage market risk and longevity yourself",
          "Taxed once at a reduced lump-sum rate",
        ],
        figure: "CHF 915\u2019000", figureLabel: "one-off capital",
      },
      {
        id: "annuity", icon: "ri-shield-check-line", t: "Lifelong annuity", sub: "Security & certainty", rec: true,
        head: "Convert to a guaranteed monthly pension",
        points: [
          "Predictable income for life, no management",
          "No market or longevity risk on your side",
          "Taxed as income each year",
        ],
        figure: "CHF 3\u2019965", figureLabel: "guaranteed / month, for life",
      },
    ],
    note: "Most people blend the two. You don't decide today, when the time comes, a Swissquote advisor reviews it with you, with your plan already prepared.",
  };

  // ── Improve your analysis: document suggestions ──────────────────
  const improve = [
    { key: "3a", icon: "ri-safe-2-line", t: "3a annual statement", d: "Confirms your exact 3a balance and 2026 contributions.", impact: "high", impactTxt: "Sharpens gap by ±CHF 180/mo" },
    { key: "salary", icon: "ri-file-list-3-line", t: "Latest salary certificate", d: "Refines insured salary and buy-in capacity.", impact: "med", impactTxt: "Refines buy-in by ±CHF 12\u2019000" },
    { key: "tax", icon: "ri-government-line", t: "Geneva tax assessment", d: "Models your true marginal rate for deductions.", impact: "low", impactTxt: "Optimises tax timing" },
  ];

  // ── Education hub ────────────────────────────────────────────────
  const education = [
    { level: "Beginner", t: "Understanding the Swiss 3a pillar", a: "Urs Fischer", min: 4, ic: "ri-safe-2-line" },
    { level: "Beginner", t: "Retiring well in Switzerland", a: "Sarah M\u00fcller", min: 4, ic: "ri-sun-line" },
    { level: "Intermediate", t: "How to optimise your taxes", a: "Urs Fischer", min: 6, ic: "ri-percent-line" },
  ];

  window.PP_DATA.v2 = {
    chf, readiness, levels, levelUp, projection, journey, kpis, annuity, improve, education,
  };
})();
