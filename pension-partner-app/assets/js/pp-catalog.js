/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER — product catalog + recommender (pp-catalog.js)
   PROMPT V5 · Pass 3. A closed catalog of Swissquote products; the
   recommender (ppAI.recommend) asks Claude to pick ONLY from this list,
   grounded in the persona's real figures, with a deterministic fallback.
   window.PP_CATALOG · window.ppAI.recommend
   ════════════════════════════════════════════════════════════════ */
(function () {
  var CATALOG = [
    { id: "saving-easy", name: "Saving Easy", status: "real", cat: "savings",
      fit: { risk: ["any"], horizonMax: 3 }, levers: ["safety", "liquidity"],
      why: "Fee-free interest-bearing cash strategy, the safety cushion before investing." },
    { id: "3a-easy-savings", name: "3a Easy — Savings strategy", status: "real", cat: "pillar3a",
      fit: { risk: ["conservative"], horizonMin: 0 }, levers: ["tax", "safety"],
      why: "Interest-bearing pillar 3a, every franc deducted from taxable income." },
    { id: "3a-easy-invest", name: "3a Easy — Investment strategies", status: "real", cat: "pillar3a",
      fit: { risk: ["balanced", "dynamic", "aggressive"], horizonMin: 5 }, levers: ["tax", "returns"],
      why: "Pillar 3a invested in sustainable fund strategies, 0.6% management fee." },
    { id: "invest-easy", name: "Invest Easy", status: "real", cat: "free-investing",
      fit: { risk: ["balanced", "dynamic", "aggressive"], horizonMin: 3, requiresFreeSavings: true }, levers: ["returns", "simplicity"],
      why: "Managed ETF strategies (up to ~95% equities) outside the 3a wrapper, 0.6% fee." },
    { id: "savings-plan", name: "Savings Plan (fractional)", status: "real", cat: "free-investing",
      fit: { risk: ["balanced", "dynamic", "aggressive"], horizonMin: 5, monthlyMin: 50 }, levers: ["returns", "discipline"],
      why: "Recurring fractional investing in stocks/ETFs/themes from CHF 3 per trade." },
    { id: "3a-crypto-boost", name: "3a Easy — Crypto Boost", status: "real", cat: "pillar3a",
      fit: { risk: ["dynamic", "aggressive"], horizonMin: 10, requires: "3a-easy-invest" }, levers: ["returns", "diversification"],
      why: "Adds crypto exposure inside an existing 3a Easy strategy." },
    { id: "themes-trading", name: "Themes Trading", status: "real", cat: "free-investing",
      fit: { risk: ["dynamic", "aggressive"], horizonMin: 5, requiresFreeSavings: true }, levers: ["returns", "conviction"],
      why: "Expert-curated thematic certificates, the conviction slice of a diversified portfolio, never the base." },
    { id: "trading-account", name: "Trading account (stocks, ETFs, bonds)", status: "real", cat: "free-investing",
      fit: { risk: ["dynamic", "aggressive"], horizonMin: 5, requiresAutonomy: true }, levers: ["returns", "control"],
      why: "Direct access to 3M+ products, reduced fees on ETF Leaders, fractional trading." },
    { id: "vested-benefits-invest", name: "Vested Benefits Invest", status: "prospective", cat: "pillar2",
      fit: { risk: ["balanced", "dynamic", "aggressive"], horizonMin: 5, trigger: "LPP assets without active employer / career transition" }, levers: ["returns", "pension-continuity"],
      why: "[CONCEPT] Invests vested LPP benefits sleeping in cash during career transitions." },
    { id: "income-easy", name: "Income Easy", status: "prospective", cat: "decumulation",
      fit: { risk: ["conservative", "balanced"], horizonMax: 10, trigger: "close to retirement or annuity goal" }, levers: ["regular-income", "tax", "safety"],
      why: "[CONCEPT] Turns accumulated capital into programmed monthly income with progressive de-risking and tax-optimised withdrawal ordering." },
  ];
  var byId = {}; CATALOG.forEach(function (p) { byId[p.id] = p; });

  var chf = function (n) { return "CHF " + Math.round(n || 0).toLocaleString("de-CH").replace(/,/g, "\u2019"); };

  // ── deterministic fallback: rule-based ordering over the catalog ──
  function fallbackRecommend(P) {
    var rec = [], excl = [];
    var horizon = Math.max(0, (P.retireTarget || P.referenceAge || 65) - (P.age || 45));
    var plan = (P.plans || []).find(function (x) { return x.id === (P.activePlanId || "balanced"); }) || (P.plans || [])[1] || {};
    var risk = /optim|aggress|dynamic|offensiv/i.test(plan.risk || plan.name || "") ? "dynamic" : /secure|conserv|prudent/i.test(plan.risk || plan.name || "") ? "conservative" : "balanced";
    var liquid = Math.max(0, (P.netWorth || 0) - (P.pillar2 || 0) - (P.pillar3a || 0));
    var buffer = (P.grossIncome || 120000) * 0.25;
    function add(id, why, now, fit, prio) { var p = byId[id]; if (p) rec.push({ id: id, name: p.name, status: p.status, why: why, now: now, fit: fit, priority: prio }); }
    if (liquid < buffer) add("saving-easy", "Your liquid reserve (~" + chf(liquid) + ") is below a 3-month buffer of " + chf(buffer) + ".", "Build the cushion before investing.", 78, "high");
    if ((P.pillar3a || 0) < 7258) add(horizon >= 5 && risk !== "conservative" ? "3a-easy-invest" : "3a-easy-savings", "Your pillar 3a is " + chf(P.pillar3a || 0) + ", below this year's cap. Filling it cuts taxable income now.", "Top up before 31 Dec.", 92, "high");
    if (liquid > buffer && horizon >= 3) add("invest-easy", "After the buffer, ~" + chf(liquid - buffer) + " of free savings can work over your " + horizon + "-year horizon.", "Put idle cash to work.", 80, "medium");
    if (horizon >= 5 && risk !== "conservative") add("savings-plan", "A monthly fractional plan turns your saving capacity into disciplined investing.", "Automate from CHF 50/mo.", 70, "medium");
    if (horizon <= 10) add("income-easy", "You're within " + horizon + " years of your target; a decumulation plan would order withdrawals tax-efficiently.", "Model it ahead of time.", 60, "low");
    ["themes-trading", "trading-account", "3a-crypto-boost"].forEach(function (id) { if (!rec.find(function (r) { return r.id === id; })) excl.push({ id: id, name: byId[id].name, reason: "A conviction/advanced brick — only once your base and tax levers are in place." }); });
    if ((P.pillar2 || 0) === 0) rec.push({ id: "vested-benefits-invest", name: byId["vested-benefits-invest"].name, status: "prospective", why: "You have no active 2nd-pillar capital; vested benefits would otherwise sit in cash.", now: "Relevant on a career move.", fit: 55, priority: "low" });
    return { recommendations: rec.slice(0, 5), excluded: excl };
  }

  function recommend(persona, confidence) {
    var P = persona || {};
    if (!window.ppAI) return Promise.resolve(fallbackRecommend(P));
    var conf = confidence || (window.PP_CONFIDENCE ? window.PP_CONFIDENCE.compute(P) : null);
    var plan = (P.plans || []).find(function (x) { return x.id === (P.activePlanId || "balanced"); }) || (P.plans || [])[1] || {};
    var horizon = Math.max(0, (P.retireTarget || P.referenceAge || 65) - (P.age || 45));
    var liquid = Math.max(0, (P.netWorth || 0) - (P.pillar2 || 0) - (P.pillar3a || 0));
    var figures = [
      "Name: " + (P.first || P.name), "Age: " + P.age + ", target retirement age: " + (P.retireTarget || 65) + " (horizon " + horizon + " years)",
      "Status: " + P.status + ", canton: " + P.canton, "Gross income: " + chf(P.grossIncome) + "/yr",
      "2nd-pillar (LPP): " + chf(P.pillar2) + ", pillar 3a: " + chf(P.pillar3a), "Net worth: " + chf(P.netWorth) + " (free/liquid ~" + chf(liquid) + ")",
      "Target monthly income: " + chf(P.targetMonthly), "Active strategy: " + (plan.name || "Balanced") + " (" + (plan.risk || "Medium") + " risk)",
      "Readiness score: " + ((P.readiness || {}).score) + "/100",
      conf ? ("Data confidence: " + conf.score + "/100 (" + conf.tier + "). Verified: " + conf.verifiedList + ". Estimated: " + conf.estimatedList + ".") : "",
    ].filter(Boolean).join("\n");
    var cat = JSON.stringify(CATALOG.map(function (p) { return { id: p.id, name: p.name, status: p.status, cat: p.cat, fit: p.fit, levers: p.levers, why: p.why }; }));
    var prompt = "You are the product recommender for Swissquote Pension Partner. Recommend ONLY products from this catalog, never others. Use ONLY the real figures provided, never invent numbers or promise returns.\n\nCATALOG:\n" + cat + "\n\nUSER (real figures):\n" + figures + "\n\nFor each recommendation return: id (from catalog), name, status, why (why THIS product for THIS profile — cite the actual figures shown), now (why now, short), fit (0-100), priority (high|medium|low). Also return `excluded`: products considered and rejected, each {id, name, reason} one line. Ordering rule: safety cushion first (saving-easy if liquidity below a 3-month buffer), then the tax lever (3a), then free-savings investing (invest-easy / savings-plan), conviction/advanced bricks (themes, trading, crypto) last and only if the base is covered. Prospective products allowed but keep status 'prospective'. At low data confidence, lean on declared figures and prefer safer first steps. Reply ONLY with JSON: {\"recommendations\":[...],\"excluded\":[...]}.";
    return window.ppAI.completeJSON(prompt).then(function (j) {
      var recs = (j && j.recommendations) ? j.recommendations.filter(function (r) { return r && byId[r.id]; }) : [];
      if (!recs.length) return fallbackRecommend(P);
      recs.forEach(function (r) { r.status = byId[r.id].status; r.name = byId[r.id].name; });
      return { recommendations: recs.slice(0, 5), excluded: (j.excluded || []).filter(function (e) { return e && byId[e.id]; }) };
    }).catch(function () { return fallbackRecommend(P); });
  }

  window.PP_CATALOG = CATALOG;
  window.PP_CATALOG_BYID = byId;
  if (window.ppAI) window.ppAI.recommend = recommend;
  else window.__ppRecommend = recommend;
})();
