/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER — Advisor's glance (pp-glance.jsx) · Pass 5
   A light, non-blocking insight strip mounted on monitor / the V2
   report / the dashboard. On mount it asks Claude (via ppAI) to
   comment on the figures ACTUALLY visible on this screen, citing them.
   Skeleton first, insights arrive after; cached per screen+data.
   window.AdvisorGlance
   ════════════════════════════════════════════════════════════════ */
(function injectGlanceCSS() {
  if (document.getElementById("pp-glance-css")) return;
  const css = `
.pp-glance { border: 1px solid var(--line-2); border-radius: var(--r-xl, 14px); background: linear-gradient(135deg, #FBFAFF, var(--bg-page)); padding: 14px 16px; box-shadow: var(--shadow-card); }
.pp-glance-h { display: flex; align-items: center; gap: 8px; font: 700 11px/1 var(--font-body); text-transform: uppercase; letter-spacing: .07em; color: var(--fg-4); margin-bottom: 11px; }
.pp-glance-h .mk { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(135deg, var(--brand-orange), #FF8A5C); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; }
.pp-glance-h .live { margin-left: auto; display: inline-flex; align-items: center; gap: 5px; font: 600 9.5px/1 var(--font-body); color: var(--ontrack); text-transform: none; letter-spacing: 0; }
.pp-glance-h .live .d { width: 6px; height: 6px; border-radius: 999px; background: var(--ontrack); }
.pp-glance-list { display: flex; flex-direction: column; gap: 9px; }
.pp-glance-row { display: flex; align-items: flex-start; gap: 9px; font: 400 13px/1.55 var(--font-body); color: var(--fg-2); text-wrap: pretty; animation: ppGlanceIn .4s var(--ease-out) both; }
.pp-glance-row .dot { flex: 0 0 8px; width: 8px; height: 8px; border-radius: 999px; margin-top: 6px; }
.pp-glance-row.info .dot { background: var(--info-deep, #146AF0); }
.pp-glance-row.attention .dot { background: var(--gap-600, #B26A00); }
.pp-glance-row.opportunity .dot { background: var(--ontrack); }
@keyframes ppGlanceIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } }
.pp-glance-sk { display: flex; flex-direction: column; gap: 8px; }
.pp-glance-sk span { height: 11px; border-radius: 999px; background: linear-gradient(90deg, var(--bg-subtle), var(--line-2), var(--bg-subtle)); background-size: 200% 100%; animation: ppGlanceSk 1.3s infinite; }
.pp-glance-sk span:nth-child(2) { width: 82%; } .pp-glance-sk span:nth-child(3) { width: 64%; }
@keyframes ppGlanceSk { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`;
  const el = document.createElement("style"); el.id = "pp-glance-css"; el.textContent = css; document.head.appendChild(el);
})();

function AdvisorGlance({ screen, persona, facts }) {
  const [items, setItems] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const chf = (window.PP_ENGINE && window.PP_ENGINE.chf) || ((n) => "CHF " + n);
  const R = (persona && persona.readiness) || {};
  const conf = (persona && window.PP_CONFIDENCE) ? window.PP_CONFIDENCE.compute(persona) : null;
  const factLines = facts || [
    "Readiness score: " + R.score + "/100 (" + R.verdict + ")",
    "Today's projected pension: " + chf(R.today) + "/mo, reachable " + chf(R.planned) + "/mo",
    persona && persona.projection ? "Projected capital at retirement: " + chf(persona.projection.peak && persona.projection.peak.value) : "",
    persona && persona.advisories && persona.advisories[0] ? "Top suggested action: " + persona.advisories[0].title : "",
  ].filter(Boolean);
  const cacheKey = screen + "|" + (persona && persona.id) + "|" + R.score + "|" + factLines.join(";").length;

  React.useEffect(() => {
    let live = true; setLoading(true);
    window.__ppInsightCache = window.__ppInsightCache || {};
    if (window.__ppInsightCache[cacheKey]) { setItems(window.__ppInsightCache[cacheKey]); setLoading(false); return; }
    if (!window.ppAI) { setLoading(false); return; }
    const confLine = conf ? ("Data confidence: " + conf.score + "/100 (" + conf.tier + "). Verified: " + conf.verifiedList + ". Estimated: " + conf.estimatedList + ".") : "";
    const prompt = "You are Pension AI commenting live on the '" + screen + "' screen the user is looking at in Swissquote Pension Partner. Refer explicitly to visible elements (e.g. 'the readiness ring above', 'your second suggested action'). Use ONLY these figures, never invent numbers:\n" + factLines.join("\n") + "\n" + confLine + "\nGive 1-3 insights, 1-2 sentences each, citing the actual figures. At low confidence stay cautious. Reply ONLY with JSON array: [{\"text\":\"...\",\"tone\":\"info|attention|opportunity\"}].";
    window.ppAI.completeJSON(prompt).then((arr) => {
      if (!live) return;
      const list = (Array.isArray(arr) ? arr : (arr && arr.insights) || []).filter((x) => x && x.text).slice(0, 3);
      if (list.length) { window.__ppInsightCache[cacheKey] = list; setItems(list); }
      setLoading(false);
    }).catch(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [cacheKey]);

  if (!loading && (!items || !items.length)) return null;
  return React.createElement("div", { className: "pp-glance" },
    React.createElement("div", { className: "pp-glance-h" },
      React.createElement("span", { className: "mk" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
      "Advisor's glance",
      React.createElement("span", { className: "live" }, React.createElement("span", { className: "d" }), "Live")),
    loading ? React.createElement("div", { className: "pp-glance-sk" }, React.createElement("span", null), React.createElement("span", null), React.createElement("span", null))
      : React.createElement("div", { className: "pp-glance-list" },
        items.map((it, i) => React.createElement("div", { className: "pp-glance-row " + (it.tone || "info"), key: i },
          React.createElement("span", { className: "dot" }), React.createElement("span", null, it.text)))));
}

Object.assign(window, { AdvisorGlance });
