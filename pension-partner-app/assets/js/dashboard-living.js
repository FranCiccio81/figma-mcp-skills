/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, living-plan dashboard (right pane)
   Two snapshot variations: "Pillars" (A) and "Bridge" (B).
   dashboard.jsx
   ════════════════════════════════════════════════════════════════ */
const D = window.PP_DATA;

/* ── Plan-health ring (SVG) ───────────────────────────────────── */
function HealthRing({ pct, run }) {
  const r = 46, c = 2 * Math.PI * r;
  const [draw, setDraw] = React.useState(run ? 0 : pct);
  React.useEffect(() => {
    if (!run) { setDraw(pct); return; }
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setDraw(pct); return; }
    const steps = Math.max(1, Math.round(1100 / 16));
    let i = 0;
    const id = setInterval(() => {
      i += 1; const k = Math.min(1, i / steps);
      setDraw(pct * (1 - Math.pow(1 - k, 3)));
      if (k >= 1) { clearInterval(id); setDraw(pct); }
    }, 16);
    return () => clearInterval(id);
  }, [run, pct]);
  return (
    React.createElement("div", { className: "pp-health-ring" },
      React.createElement("svg", { width: 108, height: 108, viewBox: "0 0 108 108" },
        React.createElement("circle", { cx: 54, cy: 54, r, fill: "none", stroke: "rgba(255,255,255,.14)", strokeWidth: 9 }),
        React.createElement("circle", {
          cx: 54, cy: 54, r, fill: "none", stroke: "#F4C56B", strokeWidth: 9, strokeLinecap: "round",
          strokeDasharray: c, strokeDashoffset: c * (1 - draw / 100), transform: "rotate(-90 54 54)"
        })
      ),
      React.createElement("div", { className: "ctr" },
        React.createElement("div", { className: "pv" }, Math.round(draw), "%"),
        React.createElement("div", { className: "pl" }, "Funded")
      )
    )
  );
}

/* ── Net-worth projection engine (rule-based, fully personalised) ──
   Recomputes the curve year-by-year from the persona's real figures:
   start capital, contribution rate, return assumption (driven by the
   active strategy), the chosen retirement age (accumulate → draw down),
   and each life event's financial impact. */
function eventImpact(e) {
  if (!e) return 0;
  const m = String(e.amt || "").replace(/[^0-9]/g, ""); const amt = m ? parseInt(m, 10) : 0;
  switch (e.type) {
    // property is largely asset-neutral for net worth; only fees / carrying costs drag
    case "property": return -Math.round((amt || 300000) * 0.06);
    case "move": return -Math.round((amt || 200000) * 0.05);
    case "windfall": return +(amt || 200000);
    case "family": return -(amt || 30000);
    case "work": return -(amt || 30000);
    case "save": return +(amt || 0);
    default: return 0;
  }
}
function projectNetWorth(P, opts) {
  opts = opts || {};
  const pr = P.projection, a0 = pr.startAge, aEnd = pr.endAge;
  const C0 = (pr.current && pr.current[0]) ? pr.current[0][1] : (P.netWorth || 100000);
  const base = (P.readiness && P.readiness.score) || 60;
  const plans = P.plans || [];
  const plan = plans.find((p) => p.id === opts.planId);
  const planScore = plan ? plan.score : base;
  const retire = Math.max(a0 + 1, Math.min(aEnd - 1, opts.retireAge || pr.retireAge));
  const contribCur = (P.journey && P.journey.contribNow) ? P.journey.contribNow * 12 : Math.round((P.grossIncome || 120000) * 0.08);
  const contribPlanBase = (P.journey && P.journey.contribPlanned) ? P.journey.contribPlanned * 12 : contribCur * 1.6;
  const rOf = (score) => Math.max(0.018, 0.026 + (score - base) / 100 * 0.05);
  const deltasFrom = (evs) => { const m = {}; (evs || []).forEach((e) => { const d = eventImpact(e); if (d) m[e.age] = (m[e.age] || 0) + d; }); return m; };
  const build = (r, contrib, ret, evDelta) => {
    let cap = C0;
    for (let a = a0 + 1; a <= ret; a++) { cap *= (1 + r); cap += contrib; if (evDelta[a]) cap += evDelta[a]; }
    const draw = Math.max(cap, C0) * 0.072;
    const out = []; cap = C0;
    for (let a = a0; a <= aEnd; a++) {
      if (a > a0) { cap *= (1 + r); if (a <= ret) cap += contrib; else cap -= draw; }
      if (evDelta[a]) cap += evDelta[a];
      out.push([a, Math.max(0, Math.round(cap))]);
    }
    return out;
  };
  // calibrate the model so its baseline peak matches the persona's stated planned peak
  const refPlanned = build(rOf(base), Math.round(contribPlanBase), pr.retireAge, {});
  const refPeak = Math.max.apply(null, refPlanned.map((p) => p[1])) || 1;
  const targetPeak = (pr.peak && pr.peak.value) || (P.journey && P.journey.projectedFund) || refPeak;
  const k = targetPeak / refPeak;
  const evDelta = opts.events ? deltasFrom(opts.events) : deltasFrom([].concat(P.calendar || [], ((window.__ppExtraEvents || {})[P.id]) || []));
  const contribPlan = Math.round(contribPlanBase * (planScore / base));
  const scale = (arr) => arr.map((p) => [p[0], Math.round(p[1] * k)]);
  return { current: scale(build(0.02, contribCur, retire, evDelta)), planned: scale(build(rOf(planScore), contribPlan, retire, evDelta)), retire };
}

/* ── Strategy-evolution chart (under the score meter) ──────────── */
function StrategyEvoChart({ persona, retireAge, activePlan, liveScore, events, onAge }) {
  const P = persona || window.PP_PERSONAS.bergerRey;
  const pr = P.projection;
  if (!pr || !pr.planned) return null;
  const svgRef = React.useRef(null);
  const [hoverAge, setHoverAge] = React.useState(null);
  const model = projectNetWorth(P, { retireAge, planId: activePlan, liveScore, events });
  const curArr = model.current, plannedArr = model.planned;
  const W = 760, H = 216, padL = 54, padR = 14, padT = 16, padB = 30;
  const a0 = pr.startAge, a1 = pr.endAge;
  const peak = Math.max.apply(null, plannedArr.map((p) => p[1]));
  const mag = Math.pow(10, Math.floor(Math.log10(peak)));
  const niceMax = Math.ceil(peak / (mag / 2)) * (mag / 2);
  const yMax = niceMax * 1.04;
  const sx = (a) => padL + (a - a0) / (a1 - a0) * (W - padL - padR);
  const pickAge = (cx) => { const el = svgRef.current; if (!el) return null; const r = el.getBoundingClientRect(); const vbx = (cx - r.left) / r.width * W; const frac = Math.max(0, Math.min(1, (vbx - padL) / (W - padL - padR))); return Math.round(a0 + frac * (a1 - a0)); };
  const sy = (v) => padT + (1 - v / yMax) * (H - padT - padB);
  const interp = (arr, a) => { for (let i = 0; i < arr.length - 1; i++) { const x0 = arr[i][0], v0 = arr[i][1], x1 = arr[i + 1][0], v1 = arr[i + 1][1]; if (a >= x0 && a <= x1) return v0 + (v1 - v0) * (a - x0) / (x1 - x0); } return a <= arr[0][0] ? arr[0][1] : arr[arr.length - 1][1]; };
  const pts = (arr) => arr.map((p) => [sx(p[0]), sy(p[1])]);
  const smooth = (P2) => { if (P2.length < 2) return ""; let d = "M" + P2[0][0].toFixed(1) + " " + P2[0][1].toFixed(1); for (let i = 0; i < P2.length - 1; i++) { const p0 = P2[i - 1] || P2[i], p1 = P2[i], p2 = P2[i + 1], p3 = P2[i + 2] || p2; const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6, c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6; d += " C" + c1x.toFixed(1) + " " + c1y.toFixed(1) + " " + c2x.toFixed(1) + " " + c2y.toFixed(1) + " " + p2[0].toFixed(1) + " " + p2[1].toFixed(1); } return d; };
  const baseY = sy(0);
  const areaOf = (arr) => { const P2 = pts(arr); return smooth(P2) + " L" + P2[P2.length - 1][0].toFixed(1) + " " + baseY.toFixed(1) + " L" + P2[0][0].toFixed(1) + " " + baseY.toFixed(1) + " Z"; };
  const rA = Math.max(a0, Math.min(a1, retireAge || pr.retireAge));
  const cProj = interp(curArr, rA), pProj = interp(plannedArr, rA);
  const yticks = [niceMax, niceMax * 0.75, niceMax * 0.5, niceMax * 0.35];
  const xticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(a0 + (a1 - a0) * f));
  const klabel = (v) => v >= 1e6 ? (+(v / 1e6).toFixed(v % 1e6 ? 1 : 0)) + "m" : Math.round(v / 1e3) + "k";
  const full = (v) => Math.round(v).toLocaleString("de-CH").replace(/,/g, "\u2019") + " CHF";
  const confRaw = (pr.confidence || "High confidence");
  const conf = /high/i.test(confRaw) ? "High confidence" : /med/i.test(confRaw) ? "Medium confidence" : confRaw;
  return (
    React.createElement("div", { className: "pp-nw" },
      React.createElement("div", { className: "pp-nw-head" },
        React.createElement("h4", null, "Projected net worth")),
      React.createElement("svg", { className: "pp-nw-svg", ref: svgRef, viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Projected net worth over time", style: { cursor: onAge ? "ew-resize" : "default", touchAction: "none" },
        onPointerMove: onAge ? (e) => { setHoverAge(pickAge(e.clientX)); } : null,
        onPointerLeave: onAge ? () => setHoverAge(null) : null,
        onPointerDown: onAge ? (e) => {
          e.preventDefault();
          const el = svgRef.current; if (!el) return;
          let last = pickAge(e.clientX); onAge(last, true); setHoverAge(last);
          const mv = (ev) => { const a = pickAge(ev.clientX); if (a !== last) { last = a; onAge(a, true); setHoverAge(a); } };
          const up = () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); onAge(last, false); };
          window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
        } : null },
        React.createElement("defs", null,
          React.createElement("linearGradient", { id: "nwPlan", x1: 0, y1: 0, x2: 0, y2: 1 },
            React.createElement("stop", { offset: "0", stopColor: "#A855C7", stopOpacity: 0.22 }),
            React.createElement("stop", { offset: "1", stopColor: "#A855C7", stopOpacity: 0.04 })),
          React.createElement("linearGradient", { id: "nwCur", x1: 0, y1: 0, x2: 0, y2: 1 },
            React.createElement("stop", { offset: "0", stopColor: "#1F8A5B", stopOpacity: 0.30 }),
            React.createElement("stop", { offset: "1", stopColor: "#1F8A5B", stopOpacity: 0.05 }))),
        yticks.map((v, i) => React.createElement("g", { key: "y" + i },
          React.createElement("line", { x1: padL, y1: sy(v), x2: W - padR, y2: sy(v), stroke: "#EEEAF4", strokeWidth: 1 }),
          React.createElement("text", { x: padL - 11, y: sy(v) + 4, textAnchor: "end", fontSize: 12.5, fontWeight: 600, fill: "#8A92A0" }, klabel(v)))),
        React.createElement("path", { d: areaOf(plannedArr), fill: "url(#nwPlan)" }),
        React.createElement("path", { d: areaOf(curArr), fill: "url(#nwCur)" }),
        React.createElement("path", { d: smooth(pts(plannedArr)), fill: "none", stroke: "#9B4DCA", strokeWidth: 2.2, strokeDasharray: "6 5", strokeLinecap: "round", strokeLinejoin: "round" }),
        React.createElement("path", { d: smooth(pts(curArr)), fill: "none", stroke: "#1F8A5B", strokeWidth: 2.2, strokeLinecap: "round", strokeLinejoin: "round" }),
        React.createElement("line", { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB, stroke: "#D6DBE4", strokeWidth: 1.2, strokeLinecap: "round" }),
        (hoverAge != null && hoverAge !== rA) ? (function () { const hx = sx(hoverAge); const hv = interp(plannedArr, hoverAge); const mx = Math.max(padL + 30, Math.min(W - padR - 30, hx)); return React.createElement("g", { key: "hov" },
          React.createElement("line", { x1: hx, y1: padT, x2: hx, y2: H - padB, stroke: "#C2B6D6", strokeWidth: 1, strokeDasharray: "2 3" }),
          React.createElement("circle", { cx: hx, cy: sy(hv), r: 3, fill: "#9B4DCA", stroke: "#fff", strokeWidth: 1.5 }),
          React.createElement("text", { x: mx, y: padT + 9, textAnchor: "middle", fontSize: 11, fontWeight: 700, fill: "#8A92A0" }, hoverAge + " · CHF " + klabel(hv))); })() : null,
        React.createElement("line", { x1: sx(rA), y1: padT, x2: sx(rA), y2: H - padB, stroke: "#9B4DCA", strokeWidth: 1.3, strokeDasharray: "4 5", opacity: 0.5 }),
        React.createElement("circle", { cx: sx(rA), cy: sy(cProj), r: 4, fill: "#1F8A5B", stroke: "#fff", strokeWidth: 2 }),
        React.createElement("circle", { cx: sx(rA), cy: sy(pProj), r: 5, fill: "#9B4DCA", stroke: "#fff", strokeWidth: 2 }),
        (function () { const mx = Math.max(padL + 32, Math.min(W - padR - 32, sx(rA))); const my = Math.max(padT + 22, sy(pProj)); return React.createElement("g", { key: "chip" },
          React.createElement("rect", { x: mx - 33, y: my - 24, width: 66, height: 19, rx: 9.5, fill: "#fff", stroke: "#E7E3EE" }),
          React.createElement("text", { x: mx, y: my - 11, textAnchor: "middle", fontSize: 11, fontWeight: 800, fill: "#8A3BBA" }, "CHF " + klabel(pProj))); })(),
        xticks.map((a, i) => React.createElement("text", { key: "x" + i, x: sx(a), y: H - 11, textAnchor: i === 0 ? "start" : i === xticks.length - 1 ? "end" : "middle", fontSize: 12.5, fontWeight: 600, fill: a === rA ? "#8A3BBA" : "#8A92A0" }, a))),
      React.createElement("div", { className: "pp-nw-rows" },
        React.createElement("div", { className: "pp-nw-row" },
          React.createElement("span", { className: "k" }, "Current projection"),
          React.createElement("span", { className: "v cur ppv2-sensitive" }, full(cProj))),
        React.createElement("div", { className: "pp-nw-arrow" }, React.createElement("i", { className: "ri-arrow-down-line" })),
        React.createElement("div", { className: "pp-nw-row" },
          React.createElement("span", { className: "k" }, "Planned projection"),
          React.createElement("span", { className: "v plan ppv2-sensitive" }, full(pProj)))),
      React.createElement("div", { className: "pp-nw-foot" },
        React.createElement("span", { className: "pp-nw-conf" }, React.createElement("span", { className: "pill" }), conf),
        React.createElement("button", { className: "pp-nw-dl", onClick: () => { if (window.__ppToast) window.__ppToast("Preparing your full report\u2026"); setTimeout(() => window.print && window.print(), 400); } }, "Download full report", React.createElement("i", { className: "ri-download-2-line" }))))
  );
}

/* interpolate a scenario (income + pct) for any retirement age, with an
   optional CHF/month target override, so custom ages stay coherent. */
function scenForAge(P, age, targetMo) {
  const pts = (P.scenarios || []).map((s) => ({
    age: s.age,
    inc: parseInt(String(s.inc).replace(/[^0-9]/g, ""), 10) || 0,
    pct: parseInt(String(s.pct).replace(/[^0-9]/g, ""), 10) || 0,
  })).sort((a, b) => a.age - b.age);
  if (!pts.length) return { age, inc: "CHF 0", incN: 0, pct: "0% of target", custom: true };
  let inc, pct;
  const lerp = (a, b, t) => Math.round(a + (b - a) * t);
  if (age <= pts[0].age) {
    const a = pts[0], b = pts[1] || pts[0], d = (b.age - a.age) || 1;
    inc = Math.round(a.inc - (b.inc - a.inc) / d * (a.age - age));
    pct = Math.round(a.pct - (b.pct - a.pct) / d * (a.age - age));
  } else if (age >= pts[pts.length - 1].age) {
    const b = pts[pts.length - 1], a = pts[pts.length - 2] || b, d = (b.age - a.age) || 1;
    inc = Math.round(b.inc + (b.inc - a.inc) / d * (age - b.age));
    pct = Math.round(b.pct + (b.pct - a.pct) / d * (age - b.age));
  } else {
    for (let i = 0; i < pts.length - 1; i++) {
      if (age >= pts[i].age && age <= pts[i + 1].age) {
        const t = (age - pts[i].age) / ((pts[i + 1].age - pts[i].age) || 1);
        inc = lerp(pts[i].inc, pts[i + 1].inc, t); pct = lerp(pts[i].pct, pts[i + 1].pct, t); break;
      }
    }
  }
  inc = Math.max(0, inc);
  if (targetMo && targetMo > 0) pct = Math.max(1, Math.round(inc / targetMo * 100));
  return { age, inc: "CHF " + inc.toLocaleString("de-CH").replace(/,/g, "\u2019"), incN: inc, pct: pct + "% of target", custom: true };
}
window.scenForAge = scenForAge;

/* Custom plan modal: collects the user's real targets and returns a
   dynamic recommendation grounded in their figures (via window.claude). */
function CustomPlanModal({ persona, initial, project, scoreOf, onClose, onApply, onClear }) {
  const [age, setAge] = React.useState(initial.age);
  const [target, setTarget] = React.useState(initial.target);
  const [save, setSave] = React.useState("");
  const [oneOff, setOneOff] = React.useState("");
  const [rec, setRec] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const proj = project(age, target);
  const score = scoreOf(proj);
  const chf = (n) => "CHF " + Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019");
  React.useEffect(() => {
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, []);
  const getRec = async () => {
    setBusy(true); setRec(null);
    let out = "";
    const R = persona.readiness || {};
    try {
      if (window.claude && window.claude.complete) {
        const prompt = "You are Pension AI for Swissquote Pension Partner. Using ONLY the real figures below, give one concrete, personalised recommendation (3 to 4 short sentences, plain language, Swiss context: AHV/AVS, pillars 1/2/3a, CHF). No preamble, no lists. Do not invent figures beyond those given.\n\n"
          + "Profile: " + persona.name + ", age " + persona.age + ", " + persona.status + ", " + persona.canton + ". Gross income " + chf(persona.grossIncome || 0) + ". Net worth ~" + chf(persona.netWorth || 0) + ". Current readiness " + R.score + "/100 (" + R.verdict + ").\n"
          + "Goal: retire at age " + age + " on " + chf(target) + "/month. At that age the projected income is " + proj.inc + "/mo (" + proj.pct + "). The user can set aside about " + chf(parseInt(save, 10) || 0) + " extra per month and a one-off of " + chf(parseInt(oneOff, 10) || 0) + ".\n\n"
          + "Give the single best path to reach that target, naming specific pillar 3a / 2nd-pillar buy-in / timing moves and their rough effect.";
        out = await window.claude.complete(prompt);
      }
    } catch (e) { out = ""; }
    if (!out || !out.trim()) {
      const gap = Math.max(0, target - proj.incN);
      out = gap > 0
        ? "To reach " + chf(target) + "/month at " + age + ", max your pillar 3a every year and add a staged 2nd-pillar buy-in. With about " + chf(parseInt(save, 10) || 0) + " extra each month" + ((parseInt(oneOff, 10) || 0) > 0 ? " plus your " + chf(parseInt(oneOff, 10)) + " one-off" : "") + ", you close a meaningful part of the ~" + chf(gap) + "/mo gap; retiring a year or two later closes the rest."
        : "You're already on track for " + chf(target) + "/month at " + age + ". Keep maxing your pillar 3a and protect the plan, no extra effort needed.";
    }
    setRec(out.trim().replace(/\s*\u2014\s*/g, ", ").replace(/\s*\u2013\s*/g, " to ")); setBusy(false);
  };
  const stepper = (val, set, lo, hi) => React.createElement("div", { className: "stp" },
    React.createElement("button", { "aria-label": "Decrease", onClick: () => set(Math.max(lo, val - 1)) }, React.createElement("i", { className: "ri-subtract-line" })),
    React.createElement("span", { className: "val" }, val),
    React.createElement("button", { "aria-label": "Increase", onClick: () => set(Math.min(hi, val + 1)) }, React.createElement("i", { className: "ri-add-line" })));
  const money = (val, set, ph) => React.createElement("div", { className: "cur" },
    React.createElement("span", { className: "p" }, "CHF"),
    React.createElement("input", { type: "number", step: 100, min: 0, placeholder: ph || "0", value: val, onChange: (e) => set(e.target.value.replace(/[^0-9]/g, "")) }),
    React.createElement("span", { className: "su" }, "/mo"));
  return React.createElement("div", { className: "ppm-modal-scrim in", onClick: onClose },
    React.createElement("div", { className: "ppm-modal pp-cpm", style: { width: 480 }, onClick: (e) => e.stopPropagation(), role: "dialog", "aria-modal": "true", "aria-label": "Tailor your plan" },
      React.createElement("div", { className: "ppm-modal-head" },
        React.createElement("span", { className: "ppm-modal-ic" }, React.createElement("i", { className: "ri-equalizer-2-line" })),
        React.createElement("div", { className: "tx" },
          React.createElement("h3", null, "Tailor your plan"),
          React.createElement("p", null, "Tell us your real goal, we'll recommend the path, not a simulation.")),
        React.createElement("button", { className: "ppm-modal-x", onClick: onClose, "aria-label": "Close" }, React.createElement("i", { className: "ri-close-line" }))),
      React.createElement("div", { className: "ppm-modal-bd" },
        React.createElement("div", { className: "pp-cpm-grid" },
          React.createElement("div", { className: "fld" }, React.createElement("label", null, "Retirement age"), stepper(age, setAge, 58, 70)),
          React.createElement("div", { className: "fld" }, React.createElement("label", null, "Target income"), money(target, (v) => setTarget(Math.max(0, parseInt(v, 10) || 0)))),
          React.createElement("div", { className: "fld" }, React.createElement("label", null, "Extra you could save"), money(save, setSave, "e.g. 500")),
          React.createElement("div", { className: "fld" }, React.createElement("label", null, "One-off contribution"), money(oneOff, setOneOff, "optional"))),
        React.createElement("div", { className: "pp-cpm-proj" },
          React.createElement("div", null, React.createElement("span", { className: "k" }, "Projected at ", age), React.createElement("span", { className: "v ppv2-sensitive" }, proj.inc, " /mo")),
          React.createElement("div", { className: "sc" }, React.createElement("span", { className: "k" }, "Readiness"), React.createElement("span", { className: "v" }, score, React.createElement("small", null, "/100"))),
          React.createElement("div", { className: "pct" }, proj.pct)),
        busy ? React.createElement("div", { className: "pp-cpm-rec busy" }, React.createElement("span", { className: "pp-typing" }, React.createElement("span", null), React.createElement("span", null), React.createElement("span", null)), "Building your recommendation from your figures…")
          : rec ? React.createElement("div", { className: "pp-cpm-rec" },
            React.createElement("div", { className: "h" }, React.createElement("i", { className: "ri-sparkling-2-fill" }), "Your recommendation"),
            React.createElement("p", { className: "ppv2-sensitive" }, rec)) : null,
        React.createElement("button", { className: "pp-btn pp-btn-ghost pp-cpm-getrec", onClick: getRec, disabled: busy },
          React.createElement("i", { className: "ri-sparkling-2-line" }), rec ? "Refresh recommendation" : "Get my recommendation"),
        React.createElement("div", { className: "ppm-modal-foot" },
          React.createElement("button", { className: "pp-btn pp-btn-ghost pp-btn-sm", onClick: onClear }, React.createElement("i", { className: "ri-close-circle-line" }), "Remove custom"),
          React.createElement("button", { className: "pp-btn pp-btn-brand pp-btn-sm", onClick: () => onApply({ age, target }) }, React.createElement("i", { className: "ri-check-line" }), "Apply to my plan")))));
}

/* ── Plan-health hero (shared by both variations) ─────────────── */
function ReadinessHero({ persona, simAge, onSimAge, activePlan, liveScore, events }) {
  const P = persona || window.PP_PERSONAS.bergerRey, R = P.readiness;
  const [custom, setCustom] = React.useState(null); // { age, target } applied from the modal
  const [customModal, setCustomModal] = React.useState(false);
  React.useEffect(() => { setCustom(null); setCustomModal(false); }, [P.id]);
  const brackets = [
    { k: "critical", l: "Critical", r: "0–25", lo: 0, hi: 25 },
    { k: "caution", l: "Caution", r: "26–45", lo: 26, hi: 45 },
    { k: "moderate", l: "Moderate", r: "46–65", lo: 46, hi: 65 },
    { k: "good", l: "Good", r: "66–80", lo: 66, hi: 80 },
    { k: "excellent", l: "Excellent", r: "81–100", lo: 81, hi: 100 },
  ];
  const pctNum = (s) => parseInt(String(s.pct).replace(/[^0-9]/g, ""), 10) || 0;
  const baseScen = P.scenarios.find((s) => s.hl) || P.scenarios[1] || P.scenarios[0];
  const factor = R.score / (pctNum(baseScen) || 100);
  const scoreFor = (s) => Math.max(1, Math.min(100, Math.round(pctNum(s) * factor)));
  const realSel = P.scenarios.find((s) => s.age === simAge) || (typeof scenForAge === "function" && simAge ? scenForAge(P, simAge) : baseScen);
  const sel = custom ? scenForAge(P, custom.age, custom.target) : realSel;
  const score = scoreFor(sel);
  const curIdx = brackets.findIndex((b) => score >= b.lo && score <= b.hi);
  const cur = brackets[curIdx] || brackets[0];
  const next = brackets[Math.min(brackets.length - 1, curIdx + 1)];
  const ptsNeeded = Math.max(0, next.lo - score);
  const reachSrc = (P.takeAction && P.takeAction.length) ? P.takeAction : (P.advisories || []);
  // ── dynamic "top moves": point values recompute to bridge the gap to the
  //    next tier, the set adapts to the selected retirement age / score ──
  const movePool = reachSrc.slice(0, 4).map((a) => ({
    t: a.title,
    why: a.benefit || a.impactNote || (a.desc ? a.desc.split(/[., ]/)[0].trim() : ""),
    w: (a.impact && a.impact > 0) ? 3 : 2, // CHF-impact moves weigh more than risk-only ones
  }));
  const isTopTier = ptsNeeded <= 0;
  let moves;
  if (isTopTier) {
    moves = movePool.slice(0, 3).map((m, i) => ({ ...m, p: [2, 1, 1][i] || 1 }));
  } else {
    const total = ptsNeeded + 1; // slight over-shoot so the shown moves visibly clear the bar
    const wsum = movePool.reduce((s, m) => s + m.w, 0) || 1;
    const pts = movePool.map((m) => Math.max(1, Math.round(total * m.w / wsum)));
    let sum = pts.reduce((a, b) => a + b, 0), k = 0;
    while (sum < total && k < 24) { pts[k % pts.length]++; sum++; k++; }
    const withP = movePool.map((m, i) => ({ ...m, p: pts[i] }));
    let cum = 0; moves = [];
    for (const m of withP) { moves.push(m); cum += m.p; if (cum >= ptsNeeded && moves.length >= 2) break; if (moves.length >= 4) break; }
  }
  const changed = sel.age !== baseScen.age;
  const confData = (window.PP_CONFIDENCE && P) ? window.PP_CONFIDENCE.compute(P) : null;
  const confScore = confData ? confData.score : ((P && P.dataConfidence) || 80);
  const confTier = confData ? confData.tier : (confScore >= 85 ? "High confidence" : confScore >= 68 ? "Good confidence" : "Building confidence");
  const confClass = confData ? confData.tierClass : (confScore >= 85 ? "hi" : confScore >= 68 ? "good" : "fair");
  const confActs = (window.PP_CONFIDENCE && P) ? window.PP_CONFIDENCE.nextBestActions(P) : [];
  const nba = confActs[0] || null;
  const docAct = confActs.find((a) => a.target === "upload") || null;
  const docName = (docAct && window.PP_CONFIDENCE) ? ((window.PP_CONFIDENCE.FIELDS.find((f) => f.key === docAct.field) || {}).doc || "document") : null;
  const confRaw = (P.projection && P.projection.confidence) || "High confidence";
  const conf = /high/i.test(confRaw) ? "High confidence" : /med/i.test(confRaw) ? "Medium confidence" : confRaw;
  const RR = 66, CC = 2 * Math.PI * RR;
  return (
    React.createElement("div", { className: "pp-rh2" },
      React.createElement("div", { className: "pp-rh2-head" },
        React.createElement("div", { className: "pp-rh2-orb" }, React.createElement("span", { className: "core" }, React.createElement("i", { className: "ri-sparkling-2-fill" }))),
        React.createElement("div", { className: "who" }, "Pension AI", React.createElement("span", null, "Analysis complete · your plan, up to date"))),
      React.createElement("button", { className: "pp-rh2-conf " + confClass, onClick: () => { if (nba && nba.target === "form") { window.__ppOpenEvent && window.__ppOpenEvent(); } else { window.__ppOpenTax && window.__ppOpenTax(); } }, title: "Raise your data confidence" },
        React.createElement("span", { className: "lb" }, React.createElement("i", { className: "ri-shield-check-line" }), confTier, React.createElement("b", null, confScore + "%")),
        nba ? React.createElement("span", { className: "nx" },
          React.createElement("i", { className: "ri-add-circle-line" }),
          React.createElement("span", { className: "tx" }, nba.target === "upload" ? "Add a document to gain" : (nba.label + " to gain")),
          React.createElement("span", { className: "pts" }, "+", nba.gain, " pts of confidence"))
          : React.createElement("span", { className: "nx done" }, React.createElement("i", { className: "ri-checkbox-circle-fill" }), "Fully verified")),
      React.createElement("div", { className: "pp-rh2-top" },
        React.createElement("div", { className: "pp-rh2-ring" },
          React.createElement("svg", { viewBox: "0 0 150 150" },
            React.createElement("circle", { cx: 75, cy: 75, r: RR, fill: "none", stroke: "#E3E6EC", strokeWidth: 11 }),
            React.createElement("circle", { cx: 75, cy: 75, r: RR, fill: "none", stroke: "url(#rh2grad)", strokeWidth: 11, strokeLinecap: "round", strokeDasharray: CC, strokeDashoffset: CC * (1 - score / 100), style: { transition: "stroke-dashoffset .6s cubic-bezier(.2,0,0,1)" } }),
            React.createElement("defs", null,
              React.createElement("linearGradient", { id: "rh2grad", x1: 0, y1: 0, x2: 1, y2: 1 },
                React.createElement("stop", { offset: "0", stopColor: "#FA5B35" }),
                React.createElement("stop", { offset: "0.5", stopColor: "#146AF0" }),
                React.createElement("stop", { offset: "1", stopColor: "#12A454" })))),
          React.createElement("div", { className: "c" },
            React.createElement("div", { className: "n ppv2-sensitive", key: score }, score, React.createElement("small", null, "/100")),
            React.createElement("div", { className: "verdict" }, cur.l))),
        React.createElement("div", { className: "pp-rh2-msg" },
          React.createElement("div", { className: "bubble" },
            React.createElement("h3", null, R.verdict),
            React.createElement("p", null, changed
              ? React.createElement(React.Fragment, null, React.createElement("span", { className: "simtag" }, "Modelling retirement at " + sel.age + ": "), sel.inc + "/mo · " + sel.pct + ". Pick another age below to re-simulate.")
              : R.sub)),
          (P.report && P.report.portrait) ? React.createElement("div", { className: "pp-rh2-portrait" },
            React.createElement("div", { className: "ic" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
            React.createElement("div", { className: "bd" },
              React.createElement("div", { className: "ti" }, "My retirement portrait"),
              React.createElement("p", { className: "ppv2-sensitive" }, P.report.portrait),
              React.createElement("div", { className: "path" }, React.createElement("i", { className: "ri-footprint-line" }),
                isTopTier
                  ? React.createElement("span", null, "You're already in great shape, a few small moves keep you ahead.")
                  : React.createElement("span", null, "Your clearest, lowest-effort path up: ", React.createElement("b", null, moves.slice(0, 2).map((m) => m.t).join(" + ")), ".")))) : null),
        React.createElement("div", { className: "pp-rh2-art" },
          React.createElement("img", { src: (window.__resources && window.__resources.heroRetire) || "assets/hero-retire.jpg", alt: "Retirement, envisioned" }),
          React.createElement("span", { className: "cap" }, React.createElement("i", { className: "ri-sparkling-2-fill" }), "Your retirement, envisioned"))),
      React.createElement(StrategyEvoChart, { persona: P, retireAge: sel.age, activePlan, liveScore, events, onAge: onSimAge }),
      React.createElement("div", { className: "pp-rh2-scenh" }, React.createElement("i", { className: "ri-cursor-line" }), "Choose a retirement age to re-simulate your plan"),
      React.createElement("div", { className: "pp-rh2-scen has-custom" },
        P.scenarios.map((s) => React.createElement("button", {
          className: "sc" + (!custom && s.age === sel.age ? " on" : ""), key: s.age,
          onClick: () => { setCustom(null); onSimAge && onSimAge(s.age); } },
          React.createElement("div", { className: "sk" }, "Retire at ", s.age, (!custom && s.age === sel.age) ? React.createElement("i", { className: "ri-checkbox-circle-fill ck" }) : null),
          React.createElement("div", { className: "sv ppv2-sensitive" }, s.inc, React.createElement("span", null, " /mo")),
          React.createElement("div", { className: "sp" }, s.pct, " · score ", scoreFor(s)))),
        React.createElement("button", { className: "sc custom" + (custom ? " on" : ""), onClick: () => setCustomModal(true) },
          React.createElement("div", { className: "sk" }, React.createElement("i", { className: "ri-equalizer-2-line" }), " Custom", custom ? React.createElement("i", { className: "ri-checkbox-circle-fill ck" }) : null),
          custom
            ? React.createElement(React.Fragment, null,
              React.createElement("div", { className: "sv ppv2-sensitive" }, sel.inc, React.createElement("span", null, " /mo")),
              React.createElement("div", { className: "sp" }, sel.pct, " · score ", score))
            : React.createElement(React.Fragment, null,
              React.createElement("div", { className: "sv set" }, "Set your own"),
              React.createElement("div", { className: "sp" }, "age + CHF target")))),
      customModal ? React.createElement(CustomPlanModal, {
        persona: P,
        initial: custom || { age: baseScen.age, target: Math.round(P.targetMonthly || 6000) },
        project: (a, t) => scenForAge(P, a, t),
        scoreOf: (s) => scoreFor(s),
        onClose: () => setCustomModal(false),
        onApply: (c) => { setCustom(c); onSimAge && onSimAge(c.age); setCustomModal(false); },
        onClear: () => { setCustom(null); onSimAge && onSimAge(baseScen.age); setCustomModal(false); }
      }) : null,
      React.createElement("div", { className: "pp-band-kpi pp-rh2-kpi" }, React.createElement(KpiStrip, { persona: P, simScen: sel }))
    )
  );
}

function HealthHero({ run }) {
  const s = D.snapshot;
  return (
    React.createElement("div", { className: "pp-health" },
      React.createElement("div", { className: "pp-health-grid" }),
      React.createElement("div", { className: "pp-health-top" },
        React.createElement("span", { className: "pp-health-badge gap" }, React.createElement("span", { className: "dot" }), "Minding the gap"),
        React.createElement("span", { className: "pp-health-updated" }, "Updated just now")
      ),
      React.createElement("div", { className: "pp-health-body" },
        React.createElement(HealthRing, { pct: s.fundedPct, run }),
        React.createElement("div", { className: "pp-health-num" },
          React.createElement("div", { className: "k" }, "Projected retirement income at 64"),
          React.createElement("div", { className: "v" }, React.createElement(CountUp, { end: s.projectedMonthly, run }), React.createElement("span", { className: "u" }, "CHF/mo")),
          React.createElement("div", { className: "sub" }, "Against your ", D.chf(s.targetMonthly), " target, a gap of ", React.createElement("b", null, D.chf(s.gapMonthly), "/mo"), ".")
        )
      ),
      React.createElement("div", { className: "pp-incomebar" },
        React.createElement("div", { className: "pp-incomebar-track" },
          React.createElement("div", { className: "pp-incomebar-fill p1", style: { width: s.seg.p1 + "%" } }),
          React.createElement("div", { className: "pp-incomebar-fill p2", style: { width: s.seg.p2 + "%" } }),
          React.createElement("div", { className: "pp-incomebar-fill p3", style: { width: s.seg.p3 + "%" } }),
          React.createElement("div", { className: "pp-incomebar-target", style: { left: "100%" } })
        ),
        React.createElement("div", { className: "pp-incomebar-legend" },
          React.createElement("span", null, React.createElement("span", { className: "d", style: { background: "#6A7BA8" } }), "AVS/AHV"),
          React.createElement("span", null, React.createElement("span", { className: "d", style: { background: "#3E6CC4" } }), "LPP/BVG"),
          React.createElement("span", null, React.createElement("span", { className: "d", style: { background: "var(--brand-orange)" } }), "Pillar 3a"),
          React.createElement("span", null, React.createElement("span", { className: "d", style: { background: "rgba(255,255,255,.25)" } }), "Gap to target")
        )
      )
    )
  );
}

/* ── Pillar rows (variation A) ─────────────────────────────────── */
function PillarRows({ run }) {
  const maxCap = 312400;
  return (
    React.createElement("div", { className: "pp-card" },
      React.createElement("div", { className: "pp-card-h" },
        React.createElement("div", { className: "t" }, "Your three pillars"),
        React.createElement("div", { className: "s" }, "Capital · projected income")
      ),
      D.pillars.map((p, i) =>
        React.createElement("div", { className: "pp-pillar", key: p.id },
          React.createElement("div", { className: "pp-pillar-top" },
            React.createElement("div", { className: "pp-pillar-ic " + p.id }, p.code),
            React.createElement("div", { className: "pp-pillar-id" },
              React.createElement("div", { className: "t" }, p.tag),
              React.createElement("div", { className: "d" }, p.desc)
            ),
            React.createElement("div", { className: "pp-pillar-rt" },
              React.createElement("div", { className: "cap" }, p.capital ? D.chf(p.capital) : ", "),
              React.createElement("div", { className: "inc" }, D.chf(p.pensionYr) + "/yr")
            )
          ),
          p.capital && React.createElement("div", { className: "pp-pillar-bar" },
            React.createElement("span", { className: p.id, style: { width: run ? (p.capital / maxCap * 100) + "%" : "0%" } })),
          p.estimate && React.createElement("div", { className: "pp-pillar-conf" }, React.createElement("i", { className: "ri-information-line" }), "Estimate, official AVS figures to confirm")
        )
      ),
      React.createElement("button", { className: "pp-pillar-add", onClick: () => window.__ppOpenTax && window.__ppOpenTax() },
        React.createElement("span", { className: "ic" }, React.createElement("i", { className: "ri-add-line" })),
        React.createElement("span", { className: "tx" },
          React.createElement("span", { className: "t" }, "Add a pillar"),
          React.createElement("span", { className: "d" }, "Vested benefits, a 2nd 3a, life insurance, more")),
        React.createElement("i", { className: "ri-arrow-right-line ar" }))
    )
  );
}

/* ── Bridge chart (variation B) ────────────────────────────────── */
function BridgeChart({ run }) {
  const s = D.snapshot, H = 188;
  const segs = [
    { id: "p1", h: s.seg.p1, lbl: "AVS/AHV" },
    { id: "p2", h: s.seg.p2, lbl: "LPP/BVG" },
    { id: "p3", h: s.seg.p3, lbl: "Pillar 3a" },
  ];
  let acc = 0;
  return (
    React.createElement("div", { className: "pp-card" },
      React.createElement("div", { className: "pp-card-h" },
        React.createElement("div", { className: "t" }, "Bridge to your target"),
        React.createElement("div", { className: "s" }, "Monthly income at 64")
      ),
      React.createElement("div", { style: { display: "flex", gap: "18px", alignItems: "stretch" } },
        React.createElement("div", { style: { position: "relative", flex: "0 0 96px", height: H + "px" } },
          // target dashed line
          React.createElement("div", { style: { position: "absolute", left: 0, right: 0, top: 0, borderTop: "2px dashed var(--fg-disabled)" } }),
          // stacked pillars + gap
          (() => {
            const out = [];
            segs.forEach((sg) => {
              const hpx = (sg.h / 100) * H * (run ? 1 : 1);
              out.push(React.createElement("div", {
                key: sg.id,
                style: { position: "absolute", left: 0, right: 0, bottom: (acc / 100 * H) + "px", height: (run ? hpx : 0) + "px", transition: "height 1s var(--ease-out), bottom 1s var(--ease-out)" },
                className: "pp-bridge-seg " + sg.id
              }));
              acc += sg.h;
            });
            // gap (striped)
            out.push(React.createElement("div", {
              key: "gap",
              style: { position: "absolute", left: 0, right: 0, bottom: (run ? (s.seg.p1 + s.seg.p2 + s.seg.p3) / 100 * H : 0) + "px", height: (run ? s.seg.gap / 100 * H : 0) + "px", transition: "all 1s var(--ease-out)", borderRadius: "0" },
              className: "pp-bridge-seg gap"
            }));
            return out;
          })()
        ),
        React.createElement("div", { style: { flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "2px 0" } },
          React.createElement("div", null,
            React.createElement("div", { style: { font: "700 11px/1 var(--font-body)", color: "var(--fg-4)", textTransform: "uppercase", letterSpacing: ".04em" } }, "Target"),
            React.createElement("div", { style: { font: "800 18px/1.1 var(--font-display)", color: "var(--fg-1)", fontVariantNumeric: "tabular-nums" } }, D.chf(s.targetMonthly), React.createElement("small", { style: { font: "600 11px/1 var(--font-body)", color: "var(--fg-4)" } }, " /mo"))
          ),
          React.createElement("div", { style: { padding: "8px 11px", borderRadius: "var(--r-md)", background: "var(--gap-50)", border: "1px solid #F0D59A" } },
            React.createElement("div", { style: { font: "600 10.5px/1 var(--font-body)", color: "var(--gap-600)", textTransform: "uppercase", letterSpacing: ".04em" } }, "The gap"),
            React.createElement("div", { style: { font: "800 18px/1.1 var(--font-display)", color: "var(--gap)", fontVariantNumeric: "tabular-nums", marginTop: "4px" } }, D.chf(s.gapMonthly), React.createElement("small", { style: { font: "600 11px/1 var(--font-body)", color: "var(--gap-600)" } }, " /mo"))
          ),
          React.createElement("div", null,
            React.createElement("div", { style: { font: "700 11px/1 var(--font-body)", color: "var(--fg-4)", textTransform: "uppercase", letterSpacing: ".04em" } }, "Today's path"),
            React.createElement("div", { style: { font: "800 18px/1.1 var(--font-display)", color: "var(--fg-1)", fontVariantNumeric: "tabular-nums" } }, D.chf(s.projectedMonthly), React.createElement("small", { style: { font: "600 11px/1 var(--font-body)", color: "var(--fg-4)" } }, " /mo"))
          )
        )
      ),
      React.createElement("div", { className: "pp-incomebar-legend", style: { marginTop: "14px", paddingTop: "12px", borderTop: "1px solid var(--line-3)" } },
        React.createElement("span", { style: { color: "var(--fg-3)" } }, React.createElement("span", { className: "d", style: { background: "#6A7BA8" } }), "AVS/AHV"),
        React.createElement("span", { style: { color: "var(--fg-3)" } }, React.createElement("span", { className: "d", style: { background: "#3E6CC4" } }), "LPP/BVG"),
        React.createElement("span", { style: { color: "var(--fg-3)" } }, React.createElement("span", { className: "d", style: { background: "var(--brand-orange)" } }), "Pillar 3a")
      )
    )
  );
}

/* ── KPI strip ─────────────────────────────────────────────────── */
function KpiStrip({ persona, simScen }) {
  const P = persona || window.PP_PERSONAS.bergerRey;
  const items = (P.kpis || []).slice(0, 4).map((k, i) => (i === 0 && simScen)
    ? [simScen.inc.replace("CHF ", "") + "/mo", "Projected income · at " + simScen.age]
    : [k.val.replace("CHF ", ""), k.lbl]);
  return (
    React.createElement("div", { className: "pp-kpis" },
      items.map((it, i) => React.createElement("div", { className: "pp-kpi", key: i },
        React.createElement("div", { className: "v ppv2-sensitive" }, it[0]),
        React.createElement("div", { className: "l" }, it[1])))
    )
  );
}

/* ── Next-best-action ─────────────────────────────────────────── */
function NextBestAction({ onClick }) {
  return (
    React.createElement("div", { className: "pp-nba", onClick },
      React.createElement("div", { className: "pp-nba-ic" }, React.createElement("i", { className: "ri-flashlight-line" })),
      React.createElement("div", { className: "pp-nba-bd" },
        React.createElement("div", { className: "t" }, "Close your CHF 1\u2019570/mo gap"),
        React.createElement("div", { className: "d" }, "5 ranked levers, top 4 close ~CHF 1\u2019470")
      ),
      React.createElement("i", { className: "ri-arrow-right-line go" })
    )
  );
}

/* ── The dashboard ─────────────────────────────────────────────── */
function dashSection(icon, title, child) {
  return React.createElement("div", { className: "pp-dash-sec" },
    React.createElement("div", { className: "pp-dash-sec-h" }, React.createElement("i", { className: icon }), title),
    child);
}

function deriveTakeAction(P) {
  const cats = [{ cat: "Pension", catTone: "pension" }, { cat: "Tax", catTone: "tax" }, { cat: "Wealth", catTone: "wealth" }, { cat: "Protection", catTone: "protection" }];
  const advs = (P.advisories || []).slice(0, 6);
  if (!advs.length) return null;
  const strip = (v) => String(v).replace(/<[^>]+>/g, "");
  const ctaFor = (a) => {
    const t = (a.title || "").toLowerCase();
    if (/buy-?in|buy-?back|pillar 2|2nd pillar|lpp/.test(t)) return "Plan my buy-in";
    if (/lombard/.test(t)) return "Explore a Lombard loan";
    if (/3a|third pillar|pillar 3/.test(t)) return /max|top|cap/.test(t) ? "Top up my 3a" : (/equit|invest/.test(t) ? "Invest my 3a" : "Open a 3a with Swissquote");
    if (/buffer|savings|liquidit|reserve|cash/.test(t)) return "Open a savings account";
    if (/diversif|concentrat|rebalanc|allocation|portfolio/.test(t)) return "Review my allocation";
    if (/protect|cover|insurance|disability|survivor|life/.test(t)) return "Review my protection";
    if (/mortgage|amortis|property|home/.test(t)) return "Review my mortgage";
    if (/portab|abroad|vested|cross-border|leave/.test(t)) return "Plan for portability";
    if (/tax|deduct/.test(t)) return "Optimise my tax";
    if (/annuity|capital|drawdown|retire/.test(t)) return "Model this option";
    if (/automat|standing order|monthly/.test(t)) return "Set it up";
    return "Plan this move";
  };
  return advs.map((a, i) => ({
    cat: cats[i % cats.length].cat, catTone: cats[i % cats.length].catTone,
    title: a.title, benefit: a.benefit || a.impactNote || "",
    pts: (a.impact && a.impact > 0) ? Math.max(1, Math.round(a.impact / 90)) : (a.effort === 1 ? 3 : 2),
    body: a.desc || "",
    math: a.math ? a.math.map((r) => [r[0], strip(r[1]), r[2] || ""]) : null,
    result: (a.impact && a.impact > 0) ? ["Monthly impact", "+CHF " + a.impact.toLocaleString("de-CH").replace(/,/g, "\u2019") + "/mo"] : ["Effort", ["", "Low", "Medium", "Higher"][a.effort] || "Medium"],
    cta: ctaFor(a),
  }));
}

function TACard({ a, toast, name }) {
  const [open, setOpen] = React.useState(false);
  const [why, setWhy] = React.useState(false);
  const catIcon = { pension: "ri-bank-line", tax: "ri-percent-line", wealth: "ri-line-chart-line", protection: "ri-shield-check-line" }[a.catTone] || "ri-focus-3-line";
  const whyText = a.why || ({
    pension: "Your second pillar is the largest single driver of your future pension. Acting here lifts the guaranteed, life-long part of your retirement income, and most moves are tax-deductible today.",
    tax: "This turns money you'd otherwise pay in tax into retirement capital. Given your marginal rate, the saving is immediate and compounds every year you repeat it.",
    wealth: "Your time horizon lets returns compound. Putting this capital to work, rather than leaving it idle, is what closes the gap between your current path and your target.",
    protection: "A plan is only as solid as what protects it. Sized to your situation, this shields the income your household depends on if life doesn't go to plan, cheapest to secure now.",
  }[a.catTone] || "This move targets the weakest part of your current plan, so it lifts your readiness score more than the effort it takes.");
  // dynamic, name-aware title: address the move to the user (sentence case)
  const nm = (name || "").trim();
  const rawTitle = String(a.title || "").trim();
  const ownTitle = (nm && !new RegExp("^" + nm, "i").test(rawTitle))
    ? nm + ", " + rawTitle.charAt(0).toLowerCase() + rawTitle.slice(1)
    : rawTitle;
  return React.createElement("div", { className: "pp-ta-card" },
    React.createElement("div", { className: "pp-ta-top" },
      React.createElement("span", { className: "pp-ta-cat " + a.catTone },
        React.createElement("i", { className: catIcon }), a.cat),
      a.pts ? React.createElement("span", { className: "pp-ta-pts" }, React.createElement("i", { className: "ri-arrow-up-line" }), "+", a.pts, " pts") : null),
    React.createElement("h4", { className: "pp-ta-ttl" }, rawTitle),
    React.createElement("p", { className: "pp-ta-body" }, a.body),
    React.createElement("div", { className: "pp-ta-meta" },
      a.benefit ? React.createElement("span", { className: "pp-ta-chip" }, React.createElement("i", { className: "ri-check-line" }), a.benefit) : null,
      React.createElement("span", { className: "pp-ta-metric" }, React.createElement("span", { className: "l" }, a.result[0]),
        a.result[0] === "Effort"
          ? (function () { const lvl = /high/i.test(a.result[1]) ? 3 : /med/i.test(a.result[1]) ? 2 : 1; return React.createElement("span", { className: "pp-ta-effort lvl-" + lvl }, [1, 2, 3].map((i) => React.createElement("i", { key: i, className: i <= lvl ? "on" : "" })), React.createElement("b", null, a.result[1])); })()
          : React.createElement("span", { className: "v ppv2-sensitive" }, a.result[1]))),
    React.createElement("button", { className: "pp-ta-why-toggle" + (why ? " open" : ""), onClick: () => setWhy((w) => !w) },
      React.createElement("i", { className: "ri-sparkling-2-line" }), "Why this matches you", React.createElement("i", { className: "ri-arrow-down-s-line ch" })),
    why ? React.createElement("div", { className: "pp-ta-why" }, whyText) : null,
    a.math ? React.createElement("button", { className: "pp-ta-toggle" + (open ? " open" : ""), onClick: () => setOpen((o) => !o) },
      open ? "Hide the calculation" : "Show how it's calculated", React.createElement("i", { className: "ri-arrow-down-s-line ch" })) : null,
    (a.math && open) ? React.createElement("div", { className: "pp-ta-math" },
      a.math.map((row, j) => React.createElement("div", { className: "r", key: j },
        React.createElement("span", { className: "l" }, row[0]),
        React.createElement("span", { className: "v ppv2-sensitive " + (row[2] || "") }, row[1])))) : null,
    React.createElement("button", { className: "pp-ta-cta", onClick: () => toast && toast(a.cta + "…") }, a.cta, React.createElement("i", { className: "ri-arrow-right-line" }))
  );
}

function TakeAction({ items, toast, name }) {
  if (!items || !items.length) return null;
  const n = items.length;
  const cols = n <= 3 ? n : Math.min(4, Math.ceil(n / 2)); // 4→2x2, 6→3x2, 8→4x2
  return React.createElement("div", { className: "pp-ta-grid", style: { "--ta-cols": cols } },
    items.map((a, i) => React.createElement(TACard, { a, toast, name, key: i }))
  );
}

function LearnHub({ P, toast }) {
  const items = [
    { ic: "ri-seedling-line", tag: "Basics", t: "Pillar 3a, explained simply", d: "Why the third pillar is the easiest tax win in Swiss retirement.", min: 4 },
    { ic: "ri-scales-3-line", tag: "Decision", t: "Lump sum vs lifelong annuity", d: "The one irreversible choice at retirement, how to weigh it.", min: 5 },
    { ic: "ri-flight-takeoff-line", tag: "Cross-border", t: "Moving abroad: what happens to your pension", d: "Vested benefits, 3a portability and avoiding CH-locked capital.", min: 5 },
  ];
  return React.createElement("div", { className: "pp-learn" },
    items.map((a, i) => React.createElement("button", { className: "pp-learn-item", key: i, onClick: () => toast && toast("Opening: " + a.t) },
      React.createElement("span", { className: "ic" }, React.createElement("i", { className: a.ic })),
      React.createElement("span", { className: "bd" },
        React.createElement("span", { className: "tag" }, a.tag, a.live ? React.createElement("span", { className: "live" }, "Live") : null),
        React.createElement("span", { className: "t" }, a.t),
        React.createElement("span", { className: "d" }, a.d)),
      React.createElement("span", { className: "meta" }, a.min, " min", React.createElement("i", { className: "ri-arrow-right-line" }))))
  );
}

function ProspectGate({ persona, toast }) {
  return (
    React.createElement("div", { className: "pp-prospect-gate" },
      React.createElement("div", { className: "pp-pg-card" },
        React.createElement("div", { className: "pp-pg-badge" }, React.createElement("i", { className: "ri-lock-2-line" }), "Preview"),
        React.createElement("div", { className: "pp-pg-ic" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
        React.createElement("h3", null, "Unlock your full retirement plan"),
        React.createElement("p", null, "You've seen your readiness score. Your complete portrait, projections, tax moves, strategy and the live scenario tools, is ready. Open a free account to unlock it, or log in if you're already with us."),
        React.createElement("div", { className: "pp-pg-actions" },
          React.createElement("button", { className: "pp-btn pp-btn-brand pp-btn-lg", onClick: () => { window.__ppSetProspect && window.__ppSetProspect(false); toast && toast("Account created, your full plan is unlocked"); } },
            React.createElement("i", { className: "ri-user-add-line" }), "Open an account"),
          React.createElement("button", { className: "pp-btn pp-btn-dark pp-btn-lg", onClick: () => window.__ppOpenLogin && window.__ppOpenLogin() },
            React.createElement("i", { className: "ri-login-circle-line" }), "Log in with Swissquote or Yuh")),
        React.createElement("div", { className: "pp-pg-foot" },
          React.createElement("span", null, React.createElement("i", { className: "ri-shield-check-line" }), "No commitment · your data stays in Switzerland"),
          React.createElement("button", { className: "pp-pg-link", onClick: () => window.__ppOpenConsult && window.__ppOpenConsult() }, "Talk to a consultant")))
    )
  );
}

function LivingDashboard({ variation, setVariation, built, onOpenLevers, persona, activePlan, onPick, toast, board, onToggleBoard, scenarios, onActivate, prospect }) {
  const P = persona || window.PP_PERSONAS.caroline;
  const [actMode, setActMode] = React.useState("ai");
  const [activated, setActivated] = React.useState(false);
  const [hideNums, setHideNums] = React.useState(false);
  const baseAge = (P.scenarios.find((s) => s.hl) || P.scenarios[1] || P.scenarios[0]).age;
  const [simAge, setSimAge] = React.useState(baseAge);
  React.useEffect(() => { setSimAge(baseAge); }, [P.id]);
  // live plan score (driven by the life-event timeline) → shared recommended strategy,
  // so the AI-recommendation row and the "Choose your strategy" picker always agree.
  // The timeline is the single source of truth (it re-reports on persona change via onScore),
  // so we must NOT reset here, a parent effect would race and clobber the child's value.
  const [liveScore, setLiveScore] = React.useState(P.readiness.score);
  const liveRecId = (window.PP_PICK_REC ? window.PP_PICK_REC(P, liveScore) : (P.plans.find((p) => p.rec) || P.plans[0])).id;
  const selScen = window.scenForAge ? window.scenForAge(P, simAge) : (P.scenarios.find((s) => s.age === simAge) || P.scenarios[0]);
  const [liveEvents, setLiveEvents] = React.useState(null);
  React.useEffect(() => {
    if (!scenarios) return;
    let tries = 0;
    const jump = () => {
      const el = document.getElementById("pp-ta-anchor");
      const sc = document.querySelector(".pp-board-scroll");
      if (el && sc) { sc.scrollTop = sc.scrollTop + el.getBoundingClientRect().top - sc.getBoundingClientRect().top - 14; }
      else if (tries++ < 8) { t = setTimeout(jump, 150); }
    };
    let t = setTimeout(jump, 820);
    return () => clearTimeout(t);
  }, [scenarios, P.id]);
  const onSimAge = (age, silent) => { setSimAge(age); if (!silent) { const s = P.scenarios.find((x) => x.age === age); toast && toast("Simulating retirement at " + age + (s ? " · " + s.inc + "/mo" : "")); } };
  const doActivate = () => {
    if (!actMode) { toast && toast("Pick Full AI or consultant-assisted to activate"); const el = document.querySelector(".ppm-activate"); if (el) el.scrollIntoView({ block: "center", behavior: "smooth" }); return; }
    setActivated(true);
    if (actMode === "assisted") window.__ppOpenConsult && window.__ppOpenConsult();
    toast && toast(actMode === "ai" ? "Activated · full-AI monitoring is on, explore your scenarios" : "Activated · a consultant will be in touch, explore your scenarios");
    if (onActivate) setTimeout(() => onActivate(), 650);
  };

  const pillarsEl = React.createElement(PillarRows, { run: built });

  // rail / chat-pane stacking (unchanged)
  const railBlocks = [
    { key: "hero", el: React.createElement(HealthHero, { run: built }) },
    { key: "pillars", el: pillarsEl },
    { key: "kpi", el: React.createElement(KpiStrip, null) },
    { key: "nba", el: React.createElement(NextBestAction, { onClick: onOpenLevers }) },
    { key: "strategy", el: dashSection("ri-stack-line", "Choose your strategy", React.createElement(StrategyPicker, { persona: P, activePlan, onPick: onPick || (() => {}), recId: liveRecId })) },
    { key: "timeline", el: dashSection("ri-calendar-event-line", "Your life-event timeline", React.createElement(EventTimeline, { persona: P, activePlan, onPick: onPick || (() => {}), toast, onScore: setLiveScore })) },
    { key: "activate", el: dashSection("ri-rocket-2-line", "Activate your service", React.createElement(ActivationCard, { toast })) },
    { key: "userinfo", el: React.createElement(UserInfoCard, { persona: P }) },
  ];

  const head = React.createElement("div", { className: "pp-dash-head" },
    React.createElement("div", { className: "ttl" },
      React.createElement("div", { className: "t" }, React.createElement("i", { className: "ri-shield-star-line" }), scenarios ? "Your plan" : "Your analysis"),
      React.createElement("div", { className: "d" }, P.name, " · age ", P.age, " · ", P.canton)
    ),
    React.createElement("div", { className: "pp-dash-head-r" },
      board && React.createElement("button", { className: "pp-iconbtn pp-hidebtn" + (hideNums ? " on" : ""), title: hideNums ? "Show numbers" : "Hide numbers", onClick: () => setHideNums((h) => !h) },
        React.createElement("i", { className: hideNums ? "ri-eye-off-line" : "ri-eye-line" })),
      board && React.createElement("button", { className: "pp-iconbtn", title: "Save PDF", onClick: () => { toast && toast("Preparing your PDF…"); setTimeout(() => window.print(), 400); } },
        React.createElement("i", { className: "ri-file-pdf-2-line" })),
      onToggleBoard && React.createElement("button", { className: "pp-iconbtn pp-ai-trigger", title: "Ask Pension AI", onClick: () => window.__ppOpenAI && window.__ppOpenAI() },
        React.createElement("i", { className: "ri-sparkling-2-fill" }))
    )
  );

  if (board) {
    const bandHead = (icon, title, sub) => React.createElement("div", { className: "pp-band-h" },
      React.createElement("div", { className: "l" }, React.createElement("i", { className: icon }), title),
      sub && React.createElement("div", { className: "s" }, sub));

    return (
      React.createElement("div", { className: "pp-board" + (prospect ? " is-prospect" : "") },
        head,
        React.createElement("div", { className: "pp-board-scroll" + (hideNums ? " pp-hidenums" : "") },
          React.createElement("div", { className: "pp-board-h" + (prospect ? " is-prospect" : "") },
            // BAND 1, snapshot + situation overview + profile (always free)
            React.createElement(Reveal, { delay: 40 },
              React.createElement("section", { className: "pp-band" },
                bandHead("ri-dashboard-2-line", "Your situation at a glance"),
                React.createElement(ReadinessHero, { persona: P, simAge, onSimAge, activePlan, liveScore, events: liveEvents })
              )),
            // PROSPECT GATE, sticky unlock popup over the blurred lower plan
            prospect && React.createElement(ProspectGate, { persona: P, toast }),
            // ANALYSIS, income & wealth + tax + insights + enrich/learn
            !scenarios && window.IncomeWealth && React.createElement(Reveal, { delay: 120 },
              React.createElement("section", { className: "pp-band" },
                bandHead("ri-pie-chart-2-line", "Income & wealth health", "Where it comes from · 5-dimension score"),
                React.createElement(window.IncomeWealth, { P }))),
            !scenarios && window.DeductionsTax && React.createElement(Reveal, { delay: 150 },
              React.createElement("section", { className: "pp-band" },
                bandHead("ri-government-line", "Deductions & tax profile"),
                React.createElement(window.DeductionsTax, { P }))),
            !scenarios && React.createElement(Reveal, { delay: 165 },
              React.createElement("section", { className: "pp-band" },
                bandHead("ri-bar-chart-grouped-line", "Your pillars & profile", "Three pillars and the data behind your plan"),
                React.createElement("div", { className: "pp-band-cols2" },
                  React.createElement("div", { className: "ov-pillars" }, pillarsEl),
                  React.createElement("div", { className: "ov-profile" }, React.createElement(UserInfoCard, { persona: P }))))),
            !scenarios && window.Insights && React.createElement(Reveal, { delay: 180 },
              React.createElement("section", { className: "pp-band" },
                bandHead("ri-flag-2-line", "Key insights", "Opportunities, risks & things to know"),
                React.createElement(window.Insights, { P }))),
            !scenarios && React.createElement(Reveal, { delay: 210 },
              React.createElement("div", { className: "pp-enrich-row" },
                React.createElement("section", { className: "pp-band" },
                  bandHead("ri-add-circle-line", "Enrich your analysis", "Add data to sharpen your portrait"),
                  React.createElement("div", { className: "pp-enrich-grid" },
                    window.RealEstateEnrich && React.createElement(window.RealEstateEnrich, { P, toast }))),
                React.createElement("section", { className: "pp-band" },
                  bandHead("ri-graduation-cap-line", "Learn & optimise", "Guides for this stage of your plan"),
                  React.createElement(LearnHub, { P, toast })))),
            // PLAN, take action (dynamic) + build & activate strategy
            scenarios && React.createElement(Reveal, { delay: 120 },
              React.createElement("section", { className: "pp-band", id: "pp-ta-anchor" },
                bandHead("ri-flashlight-line", "Take action", "Enhance your situation, pick a strategy or add a product"),
                React.createElement("div", { className: "pp-build pp-build-card" },
                  React.createElement("div", { className: "pp-build-h" }, React.createElement("i", { className: "ri-route-line" }), "Build & activate your strategy", React.createElement("span", null, "Pick a strategy, then choose how it's run")),
                  React.createElement("div", { className: "pp-build-step" }, React.createElement("span", { className: "n" }, "1"), "Choose your strategy"),
                  React.createElement(StrategyPicker, { persona: P, activePlan, onPick: onPick || (() => {}), recId: liveRecId, horizontal: true }),
                  React.createElement("div", { className: "pp-build-step", style: { marginTop: "20px" } }, React.createElement("span", { className: "n" }, "2"), "Choose your activation"),
                  React.createElement(ActivationCard, { toast, mode: actMode, setMode: setActMode, hideCta: true })),
                React.createElement(TakeAction, { items: (P.takeAction && P.takeAction.length ? P.takeAction : (deriveTakeAction(P) || window.PP_PERSONAS.caroline.takeAction)), toast, name: P.first }))),
            scenarios && React.createElement(Reveal, { delay: 160 },
              React.createElement("section", { className: "pp-band" },
                bandHead("ri-calendar-event-line", "Plan around life events", "Add an event that impacts your plan, it re-projects live"),
                React.createElement("div", { className: "pp-tlcard" },
                  React.createElement(EventTimeline, { persona: P, activePlan, onPick: onPick || (() => {}), toast, horizontal: true, onScore: setLiveScore, onEvents: setLiveEvents })))),
            // Footer
            React.createElement("div", { className: "pp-board-foot" },
              React.createElement("span", { className: "b" }, React.createElement("i", { className: "ri-shield-star-line" }), "Pension Partner · AI Beta"),
              React.createElement("span", { className: "d" }, "For illustrative purposes only. Not financial, tax or investment advice. Figures are estimates derived from documents you confirmed. Swissquote Bank Ltd is regulated by FINMA."))
          )),
        // sticky always-visible CTA
        scenarios
          ? React.createElement("div", { className: "pp-board-sticky" },
            React.createElement("div", { className: "pp-board-sticky-in" },
              React.createElement("div", { className: "info" },
                React.createElement("span", { className: "k" }, activated ? "Plan active" : "Active plan"),
                React.createElement("span", { className: "v" }, (P.plans.find((x) => x.id === activePlan) || P.plans[0]).name, actMode ? React.createElement("span", { className: "mode" }, actMode === "ai" ? " · Full AI" : " · Consultant-assisted") : null)),
              React.createElement("div", { className: "acts" },
                React.createElement("button", { className: "pp-btn pp-btn-ghost", onClick: () => window.__ppOpenConsult && window.__ppOpenConsult() },
                  React.createElement("i", { className: "ri-user-voice-line" }), "Talk to a consultant"),
                React.createElement("button", { className: "pp-btn pp-btn-brand", disabled: activated, onClick: doActivate },
                  React.createElement("i", { className: activated ? "ri-check-line" : "ri-rocket-2-line" }), activated ? ((actMode === "ai" ? "Full-AI · " : "Assisted · ") + (P.plans.find((x) => x.id === activePlan) || P.plans[0]).name + " active") : ("Activate " + (P.plans.find((x) => x.id === activePlan) || P.plans[0]).name))))
          )
          : React.createElement("div", { className: "pp-board-sticky" },
            React.createElement("div", { className: "pp-board-sticky-in" },
              React.createElement("div", { className: "info" },
                React.createElement("span", { className: "k" }, React.createElement("i", { className: "ri-check-double-line", style: { color: "var(--ontrack)", marginRight: 5 } }), "Analysis ready"),
                React.createElement("span", { className: "v" }, "Recommended: ", (P.plans.find((x) => x.id === liveRecId) || P.plans[0]).name)),
              React.createElement("div", { className: "acts" },
                React.createElement("button", { className: "pp-btn pp-btn-ghost", onClick: () => window.__ppOpenAI && window.__ppOpenAI() },
                  React.createElement("i", { className: "ri-sparkling-2-fill" }), "Ask Pension AI"),
                React.createElement("button", { className: "pp-btn pp-btn-brand", onClick: () => { toast && toast("Let's build your plan"); if (window.__ppGo) window.__ppGo(6); } },
                  React.createElement("i", { className: "ri-arrow-right-line" }), "Continue to your plan")))
          )
      )
    );
  }

  return (
    React.createElement("div", { className: "pp-dash" },
      head,
      React.createElement("div", { className: "pp-dash-scroll" },
        railBlocks.map((b, i) => React.createElement(Reveal, { key: b.key, delay: Math.min(60 + i * 110, 880) }, b.el))
      )
    )
  );
}

/* ── Reusable confidence meter (atomic) ───────────────────────────
   <ConfidenceMeter score={0-100} nudge="..." /> — self-tiers its
   colour/label. Reused on onboarding, analysis, monitoring, etc. */
function ConfidenceMeter({ score, nudge, label, actionLabel, onAction, persona, detail }) {
  const [open, setOpen] = React.useState(false);
  const comp = (persona && window.PP_CONFIDENCE) ? window.PP_CONFIDENCE.compute(persona) : null;
  const s = Math.max(0, Math.min(100, Math.round((comp ? comp.score : score) || 0)));
  const tier = s >= 85 ? { l: "High confidence", c: "hi" } : s >= 68 ? { l: "Good confidence", c: "good" } : { l: "Building confidence", c: "fair" };
  const nba = (persona && window.PP_CONFIDENCE) ? window.PP_CONFIDENCE.nextBestActions(persona)[0] : null;
  const nudgeTxt = nudge != null ? nudge : (nba ? nba.label + " " : (s >= 90 ? "Your plan is built on confirmed data." : ""));
  const actLabel = actionLabel != null ? actionLabel : (nba ? "+" + nba.gain + " pts" : null);
  const act = onAction || (nba ? () => window.__ppOpenTax && window.__ppOpenTax() : null);
  const stIcon = { verified: "ri-checkbox-circle-fill", declared: "ri-circle-half-line", estimated: "ri-error-warning-line", missing: "ri-checkbox-blank-circle-line" };
  return React.createElement("div", { className: "pp-conf c-" + tier.c },
    React.createElement("div", { className: "pp-conf-h", style: (comp || detail) ? { cursor: "pointer" } : null, onClick: (comp || detail) ? () => setOpen((v) => !v) : null },
      React.createElement("span", { className: "lb" }, React.createElement("i", { className: "ri-shield-check-line" }), label || tier.l),
      React.createElement("span", { className: "pc" }, s, "%", (comp || detail) ? React.createElement("i", { className: "ri-arrow-down-s-line", style: { fontSize: "14px", marginLeft: "3px", transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" } }) : null)),
    React.createElement("div", { className: "pp-conf-bar" }, React.createElement("span", { style: { width: s + "%" } })),
    (open && comp) ? React.createElement("div", { className: "pp-conf-detail" },
      comp.detail.map((d, i) => React.createElement("div", { className: "pp-conf-drow s-" + d.state, key: i },
        React.createElement("i", { className: stIcon[d.state] }),
        React.createElement("span", { className: "dl" }, d.label),
        React.createElement("span", { className: "ds" }, d.state)))) : null,
    (nudgeTxt || actLabel) ? React.createElement("div", { className: "pp-conf-n" },
      React.createElement("i", { className: "ri-sparkling-2-fill" }),
      React.createElement("span", null, nudgeTxt,
        (actLabel && act) ? React.createElement("button", { className: "pp-conf-link", onClick: act }, actLabel) : null)) : null);
}

Object.assign(window, { LivingDashboard, HealthHero, ReadinessHero, KpiStrip, ConfidenceMeter });
