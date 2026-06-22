/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, AI chat widgets (aiwidgets.jsx)
   Compact, chat-sized versions of dashboard modules. The assistant's
   model picks WHICH widget fits the question; these render it from the
   active persona's REAL data (never model-invented figures).
   window.AIWidget  ·  window.PP_WIDGET_TYPES
   ════════════════════════════════════════════════════════════════ */
const AIW_TYPES = ["gauge", "scenarios", "projection", "plans", "annuity", "kpi", "moves"];

function aiwScoreFor(P, s) {
  const pctNum = (x) => parseInt(String(x.pct).replace(/[^0-9]/g, ""), 10) || 0;
  const base = P.scenarios.find((x) => x.hl) || P.scenarios[1] || P.scenarios[0];
  const factor = P.readiness.score / (pctNum(base) || 100);
  return Math.max(1, Math.min(100, Math.round(pctNum(s) * factor)));
}
function aiwBracket(score) {
  const b = [["Critical", 0, 25], ["Caution", 26, 45], ["Moderate", 46, 65], ["Good", 66, 80], ["Excellent", 81, 100]];
  const f = b.find((x) => score >= x[1] && score <= x[2]) || b[0];
  return { label: f[0], next: (b[b.indexOf(f) + 1] || f)[0], nextLo: (b[b.indexOf(f) + 1] || f)[1] };
}

/* ── gauge: readiness score ring + verdict ── */
function AIWGauge({ P }) {
  const R = P.readiness, score = R.score, RR = 34, C = 2 * Math.PI * RR;
  const br = aiwBracket(score);
  return (
    React.createElement("div", { className: "pp-aiw pp-aiw-gauge" },
      React.createElement("div", { className: "ring" },
        React.createElement("svg", { viewBox: "0 0 80 80" },
          React.createElement("circle", { cx: 40, cy: 40, r: RR, fill: "none", stroke: "#E3E6EC", strokeWidth: 7 }),
          React.createElement("circle", { cx: 40, cy: 40, r: RR, fill: "none", stroke: "url(#aiwg)", strokeWidth: 7, strokeLinecap: "round", strokeDasharray: C, strokeDashoffset: C * (1 - score / 100), transform: "rotate(-90 40 40)" }),
          React.createElement("defs", null, React.createElement("linearGradient", { id: "aiwg", x1: 0, y1: 0, x2: 1, y2: 1 },
            React.createElement("stop", { offset: 0, stopColor: "#FA5B35" }), React.createElement("stop", { offset: .5, stopColor: "#146AF0" }), React.createElement("stop", { offset: 1, stopColor: "#12A454" })))),
        React.createElement("div", { className: "c" }, score, React.createElement("small", null, "/100"))),
      React.createElement("div", { className: "tx" },
        React.createElement("div", { className: "lv" }, br.label),
        React.createElement("div", { className: "vd" }, R.verdict)))
  );
}

/* ── scenarios: retire-age tiles ── */
function AIWScenarios({ P }) {
  return (
    React.createElement("div", { className: "pp-aiw pp-aiw-scen" },
      P.scenarios.map((s) => React.createElement("div", { className: "t" + (s.hl ? " hl" : ""), key: s.age },
        React.createElement("div", { className: "a" }, "Retire ", s.age),
        React.createElement("div", { className: "v" }, s.inc),
        React.createElement("div", { className: "p" }, "score ", aiwScoreFor(P, s)))))
  );
}

/* ── projection: current vs planned sparkline ── */
function AIWProjection({ P }) {
  const pj = P.projection; if (!pj) return null;
  const W = 300, H = 92, pad = 6;
  const xs = pj.planned.map((d) => d[0]), allv = pj.planned.concat(pj.current).map((d) => d[1]);
  const minA = Math.min.apply(null, xs), maxA = Math.max.apply(null, xs), maxV = pj.yMax || Math.max.apply(null, allv);
  const sx = (a) => pad + ((a - minA) / (maxA - minA)) * (W - pad * 2);
  const sy = (v) => (H - pad) - (v / maxV) * (H - pad * 2);
  const path = (arr) => arr.map((d, i) => (i ? "L" : "M") + sx(d[0]).toFixed(1) + " " + sy(d[1]).toFixed(1)).join(" ");
  const retX = sx(pj.retireAge);
  return (
    React.createElement("div", { className: "pp-aiw pp-aiw-proj" },
      React.createElement("svg", { viewBox: "0 0 " + W + " " + H },
        React.createElement("line", { x1: retX, y1: 4, x2: retX, y2: H - 4, stroke: "var(--brand-orange-stroke)", strokeWidth: 1, strokeDasharray: "3 3" }),
        React.createElement("path", { d: path(pj.current), fill: "none", stroke: "var(--fg-disabled)", strokeWidth: 2, strokeDasharray: "4 3" }),
        React.createElement("path", { d: path(pj.planned), fill: "none", stroke: "var(--brand-orange)", strokeWidth: 2.5, strokeLinecap: "round" }),
        React.createElement("circle", { cx: retX, cy: sy(pj.peak.value), r: 3.5, fill: "var(--brand-orange)", stroke: "#fff", strokeWidth: 1.5 })),
      React.createElement("div", { className: "lg" },
        React.createElement("span", null, React.createElement("i", { className: "sw o" }), "Planned"),
        React.createElement("span", null, React.createElement("i", { className: "sw g" }), "Current"),
        React.createElement("span", { className: "pk" }, "Peak CHF ", Math.round(pj.peak.value / 1000), "k @ ", pj.retireAge)))
  );
}

/* ── plans: strategy compare ── */
function AIWPlans({ P, recId }) {
  const rid = recId || (P.plans.find((p) => p.rec) || {}).id;
  return (
    React.createElement("div", { className: "pp-aiw pp-aiw-plans" },
      P.plans.map((pl) => React.createElement("div", { className: "pl" + (pl.id === rid ? " rec" : ""), key: pl.id },
        React.createElement("div", { className: "nm" }, pl.name, pl.id === rid && React.createElement("span", { className: "tag" }, "Pick")),
        React.createElement("div", { className: "in" }, pl.income),
        React.createElement("div", { className: "mt" }, pl.risk, " risk · ", pl.score))))
  );
}

/* ── annuity: lump vs annuity ── */
function AIWAnnuity({ P }) {
  const la = P.lumpAnnuity; if (!la) return null;
  return (
    React.createElement("div", { className: "pp-aiw pp-aiw-annuity" },
      la.options.map((o) => React.createElement("div", { className: "o" + (o.rec ? " rec" : ""), key: o.id },
        React.createElement("div", { className: "h" }, React.createElement("i", { className: o.icon }), o.t, o.rec && React.createElement("span", { className: "tag" }, "Often preferred")),
        React.createElement("div", { className: "fg" }, o.figure),
        React.createElement("div", { className: "fl" }, o.figureLabel))))
  );
}

/* ── kpi: stat chips ── */
function AIWKpi({ P }) {
  return (
    React.createElement("div", { className: "pp-aiw pp-aiw-kpi" },
      (P.kpis || []).slice(0, 4).map((k, i) => React.createElement("div", { className: "k", key: i },
        React.createElement("div", { className: "v" }, k.val),
        React.createElement("div", { className: "l" }, k.lbl),
        React.createElement("span", { className: "tg " + (k.tone || "green") }, k.tag))))
  );
}

/* ── moves: top moves to next tier ── */
function AIWMoves({ P }) {
  const src = (P.takeAction && P.takeAction.length) ? P.takeAction : (P.advisories || []);
  const br = aiwBracket(P.readiness.score);
  const need = Math.max(0, br.nextLo - P.readiness.score);
  const items = src.slice(0, 3).map((a, i) => ({ t: a.title, why: a.benefit || a.impactNote || "", p: [3, 2, 2][i] || 2 }));
  return (
    React.createElement("div", { className: "pp-aiw pp-aiw-moves" },
      React.createElement("div", { className: "hd" }, React.createElement("i", { className: "ri-sparkling-2-fill" }), need > 0 ? "Reach " + br.next + ", " + need + " pts to go" : "Stay ahead"),
      items.map((m, i) => React.createElement("div", { className: "mv", key: i },
        React.createElement("span", { className: "n" }, i + 1),
        React.createElement("span", { className: "t" }, m.t, m.why && React.createElement("small", null, m.why)),
        React.createElement("span", { className: "p" }, "+", m.p))))
  );
}

function AIWidget({ type, P, recId }) {
  if (!P || !type) return null;
  switch (type) {
    case "gauge": return React.createElement(AIWGauge, { P });
    case "scenarios": return React.createElement(AIWScenarios, { P });
    case "projection": return React.createElement(AIWProjection, { P });
    case "plans": return React.createElement(AIWPlans, { P, recId });
    case "annuity": return React.createElement(AIWAnnuity, { P });
    case "kpi": return React.createElement(AIWKpi, { P });
    case "moves": return React.createElement(AIWMoves, { P });
    default: return null;
  }
}

/* keyword heuristic when the model doesn't name a widget */
function aiwGuess(q) {
  const t = (q || "").toLowerCase();
  if (/lump|annuit|capital at retire/.test(t)) return "annuity";
  if (/strateg|secure|balanced|optimi|plan\b|which plan/.test(t)) return "plans";
  if (/project|capital|grow|over time|trajector|future value/.test(t)) return "projection";
  if (/retire (at|by)|early|age \d|62|63|64|65/.test(t)) return "scenarios";
  if (/gap|close|improve|move|action|score|reach|better/.test(t)) return "moves";
  if (/income|wealth|buy-?in|concentrat|liquidit|number|kpi/.test(t)) return "kpi";
  if (/ready|readiness|how am i|on track|overall/.test(t)) return "gauge";
  return null;
}

Object.assign(window, { AIWidget, PP_WIDGET_TYPES: AIW_TYPES, ppAiwGuess: aiwGuess });
