/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER — live product recommendations (pp-products.jsx)
   PROMPT V5 · Pass 3 rendering. Calls ppAI.recommend(persona) and
   renders catalog-constrained product cards (why + why-now + fit +
   priority + prospective badge + "why not the others?"). Falls back
   to the deterministic recommender. window.ProductRecs
   ════════════════════════════════════════════════════════════════ */
const PPCAT_ICON = {
  "saving-easy": "ri-safe-2-line", "3a-easy-savings": "ri-bank-line", "3a-easy-invest": "ri-line-chart-line",
  "invest-easy": "ri-funds-line", "savings-plan": "ri-repeat-line", "3a-crypto-boost": "ri-coin-line",
  "themes-trading": "ri-lightbulb-flash-line", "trading-account": "ri-stock-line",
  "vested-benefits-invest": "ri-briefcase-4-line", "income-easy": "ri-wallet-3-line",
};

(function injectProdCSS() {
  if (document.getElementById("pp-prod-css")) return;
  const css = `
.pp-prod-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.pp-prod.compact .pp-prod-grid { grid-template-columns: 1fr; }
.pp-prod-card { display: flex; flex-direction: column; border: 1px solid var(--line-2); border-radius: var(--r-xl, 14px); background: var(--bg-page); padding: 16px; box-shadow: var(--shadow-card); transition: border-color .2s, box-shadow .2s, transform .2s; }
.pp-prod-card:hover { border-color: var(--brand-orange-stroke); box-shadow: 0 12px 24px -16px rgba(16,20,30,.35); transform: translateY(-1px); }
.pp-prod-top { display: flex; align-items: flex-start; gap: 11px; }
.pp-prod-top .ic { flex: 0 0 38px; width: 38px; height: 38px; border-radius: 10px; background: var(--brand-orange-50); color: var(--brand-orange-600); display: inline-flex; align-items: center; justify-content: center; font-size: 19px; }
.pp-prod-top .ti { flex: 1; min-width: 0; }
.pp-prod-top .nm { font: 700 14px/1.25 var(--font-display); color: var(--fg-1); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pp-prod-concept { font: 700 8.5px/1 var(--font-body); text-transform: uppercase; letter-spacing: .05em; color: #6D28D9; background: #F1ECFB; padding: 4px 7px; border-radius: 999px; }
.pp-prod-top .fitrow { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.pp-prod-prio { font: 700 9px/1 var(--font-body); text-transform: uppercase; letter-spacing: .05em; padding: 3px 7px; border-radius: 999px; }
.pp-prod-prio.hi { background: var(--brand-orange-50); color: var(--brand-orange-600); }
.pp-prod-prio.mid { background: var(--info-50, #EBF1FF); color: var(--info-deep, #146AF0); }
.pp-prod-prio.low { background: var(--bg-subtle); color: var(--fg-4); }
.pp-prod-top .fit { font: 600 10.5px/1 var(--font-body); color: var(--fg-4); font-variant-numeric: tabular-nums; }
.pp-prod-card .why { font: 400 12.5px/1.55 var(--font-body); color: var(--fg-2); margin: 12px 0 0; text-wrap: pretty; }
.pp-prod-card .now { display: inline-flex; align-items: center; gap: 6px; margin-top: 9px; font: 600 11px/1.3 var(--font-body); color: var(--brand-orange-600); }
.pp-prod-card .now i { font-size: 13px; }
.pp-prod-cta { display: inline-flex; align-items: center; gap: 6px; align-self: flex-start; margin-top: 13px; border: 0; background: none; cursor: pointer; padding: 0; font: 700 12px/1 var(--font-body); color: var(--fg-1); }
.pp-prod-cta i { transition: transform .2s; }
.pp-prod-cta:hover i { transform: translateX(2px); }
.pp-prod-load { display: flex; flex-direction: column; gap: 10px; }
.pp-prod-sk .skl { display: inline-flex; align-items: center; gap: 8px; font: 500 12.5px/1.4 var(--font-body); color: var(--fg-4); padding: 14px 16px; border: 1px dashed var(--line-1); border-radius: var(--r-lg); background: var(--bg-subtle); width: 100%; }
.pp-prod-sk .skl i { color: var(--brand-orange-600); animation: ppPulse 1.4s infinite; }
@keyframes ppPulse { 0%,100% { opacity: .45; } 50% { opacity: 1; } }
.pp-prod-excl { margin-top: 14px; }
.pp-prod-excl-t { display: inline-flex; align-items: center; gap: 7px; border: 0; background: none; cursor: pointer; padding: 0; font: 600 12px/1 var(--font-body); color: var(--fg-4); }
.pp-prod-excl-t:hover { color: var(--fg-2); }
.pp-prod-excl-list { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.pp-prod-excl-list .row { font: 400 11.5px/1.5 var(--font-body); color: var(--fg-4); }
.pp-prod-excl-list .row b { color: var(--fg-2); font-weight: 700; margin-right: 6px; }
@media (max-width: 720px) { .pp-prod-grid { grid-template-columns: 1fr; } }`;
  const el = document.createElement("style"); el.id = "pp-prod-css"; el.textContent = css; document.head.appendChild(el);
})();

function ProductRecs({ persona, limit, compact, title, sub }) {
  const pid = persona && persona.id;
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [openExcl, setOpenExcl] = React.useState(false);
  const cacheKey = pid + "|" + (persona && persona.activePlanId);

  React.useEffect(() => {
    let live = true;
    setLoading(true); setData(null); setOpenExcl(false);
    window.__ppRecCache = window.__ppRecCache || {};
    if (window.__ppRecCache[cacheKey]) { setData(window.__ppRecCache[cacheKey]); setLoading(false); return; }
    const rec = (window.ppAI && window.ppAI.recommend) ? window.ppAI.recommend(persona) : (window.__ppRecommend ? window.__ppRecommend(persona) : Promise.resolve({ recommendations: [], excluded: [] }));
    Promise.resolve(rec).then((r) => { if (!live) return; window.__ppRecCache[cacheKey] = r; setData(r); setLoading(false); })
      .catch(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [cacheKey]);

  const recs = (data && data.recommendations ? data.recommendations : []).slice(0, limit || 5);
  const excl = (data && data.excluded) ? data.excluded : [];
  const prio = { high: { l: "Priority", c: "hi" }, medium: { l: "Worth it", c: "mid" }, low: { l: "Later", c: "low" } };

  return React.createElement("div", { className: "pp-prod" + (compact ? " compact" : "") },
    loading ? React.createElement("div", { className: "pp-prod-load" },
      [0, 1, 2].map((i) => React.createElement("div", { className: "pp-prod-sk", key: i },
        React.createElement("span", { className: "skl" }, React.createElement("i", { className: "ri-sparkling-2-fill" }), "Pension AI is matching products to your figures\u2026")))) : null,
    !loading ? React.createElement("div", { className: "pp-prod-grid" },
      recs.map((r, i) => {
        const p = prio[r.priority] || prio.medium;
        return React.createElement("div", { className: "pp-prod-card", key: i },
          React.createElement("div", { className: "pp-prod-top" },
            React.createElement("span", { className: "ic" }, React.createElement("i", { className: PPCAT_ICON[r.id] || "ri-price-tag-3-line" })),
            React.createElement("div", { className: "ti" },
              React.createElement("div", { className: "nm" }, r.name,
                r.status === "prospective" ? React.createElement("span", { className: "pp-prod-concept" }, "Concept \u2014 coming soon") : null),
              React.createElement("div", { className: "fitrow" },
                React.createElement("span", { className: "pp-prod-prio " + p.c }, p.l),
                typeof r.fit === "number" ? React.createElement("span", { className: "fit" }, r.fit, "% fit") : null))),
          React.createElement("p", { className: "why ppv2-sensitive" }, r.why),
          r.now ? React.createElement("div", { className: "now" }, React.createElement("i", { className: "ri-time-line" }), r.now) : null,
          React.createElement("button", { className: "pp-prod-cta", onClick: () => window.__ppToast && window.__ppToast("Opening " + r.name) },
            "Explore ", r.name, React.createElement("i", { className: "ri-arrow-right-line" })));
      })) : null,
    (!loading && excl.length) ? React.createElement("div", { className: "pp-prod-excl" },
      React.createElement("button", { className: "pp-prod-excl-t", onClick: () => setOpenExcl((v) => !v) },
        React.createElement("i", { className: openExcl ? "ri-subtract-line" : "ri-add-line" }), "Why not the others?"),
      openExcl ? React.createElement("div", { className: "pp-prod-excl-list" },
        excl.map((e, i) => React.createElement("div", { className: "row", key: i },
          React.createElement("b", null, e.name), React.createElement("span", null, e.reason)))) : null) : null);
}

Object.assign(window, { ProductRecs });
