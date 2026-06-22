/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, v0.2 shared modules (v2-modules.jsx)
   Persona switcher · sub-score panel · plans compare · life-event
   calendar (drag-to-redate) · Edit & Simulate (live GO/KO) · divorce
   fork · tax-upload modal. Used by both V1 and V2. window.PPModules
   ════════════════════════════════════════════════════════════════ */
const E = window.PP_ENGINE;
const PERS = window.PP_PERSONAS;

/* ── Persona switcher ──────────────────────────────────────────── */
function PersonaSwitcher({ active, onChange }) {
  return (
    <div className="ppm-persona" role="tablist" aria-label="Reference scenario">
      {PERS.order.map((id) => {
        const p = PERS[id];
        return (
          <button key={id} className={active === id ? "on" : ""} onClick={() => onChange(id)} role="tab" aria-selected={active === id}>
            <span className="fl">{p.flag}</span>{p.first.split(" ")[0]}{p.kind === "couple" ? " & C." : ""}
          </button>
        );
      })}
    </div>
  );
}

/* ── Sub-score panel (secondary to the simple readiness %) ─────── */
function SubScorePanel({ sub }) {
  const score = E.planScore(sub);
  const mover = E.biggestMover(sub);
  const band = (v) => (v >= 70 ? "hi" : v >= 50 ? "mid" : "lo");
  return (
    <div className="ppm-subscores">
      <div className="ppm-subscore-ring">
        <div className="lbl">Plan Score</div>
        <div className="big">{score}<small>/100</small></div>
        <div className="ppm-mover"><i className="ri-arrow-up-circle-line" /><span>Biggest mover: <b>{mover.label}</b> ({mover.weight}% weight)</span></div>
      </div>
      <div className="ppm-sublist">
        {E.SCORE_WEIGHTS.map((w) => (
          <div className="ppm-sub" key={w.key}>
            <div className="nm">{w.label} <span className="wt">{w.weight}%</span><small>{w.hint}</small></div>
            <div className="ppm-sub-track"><div className={"ppm-sub-fill " + band(sub[w.key])} style={{ width: sub[w.key] + "%" }} /></div>
            <div className="val">{sub[w.key]}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Plans compare ─────────────────────────────────────────────── */
function PlansCompare({ persona, activePlan, onPick }) {
  const riskColor = { Low: "var(--ontrack)", Medium: "var(--gap)", "Medium\u2013high": "var(--gap)", Higher: "var(--loss)" };
  return (
    <div className="ppm-plans">
      {persona.plans.map((pl) => {
        const isActive = activePlan === pl.id;
        return (
          <div className={"ppm-plan" + (pl.rec ? " rec" : "") + (isActive ? " is-active" : "")} key={pl.id}>
            <div className="ppm-plan-h">
              <h4>{pl.name}</h4>
              <div className="ppm-plan-score" style={{ color: pl.score >= 70 ? "var(--ontrack)" : pl.score >= 50 ? "var(--gap)" : "var(--loss)" }}>{pl.score}<small>/100</small></div>
            </div>
            <div className="ppm-plan-thesis">{pl.thesis}</div>
            <div className="ppm-plan-stats">
              <div className="ppm-plan-stat">Income at target <b>{pl.income}</b></div>
              <div className="ppm-plan-stat">Tax saved <b>{pl.taxSaved}</b></div>
              <div className="ppm-plan-stat">Retire at <b>{pl.retireAge}</b></div>
              <div className="ppm-plan-stat">Risk <span className="ppm-plan-risk"><i style={{ background: riskColor[pl.risk] || "var(--gap)" }} /><b>{pl.risk}</b></span></div>
            </div>
            <ul className="ppm-plan-moves">
              {pl.moves.map((m, i) => <li key={i}><i className="ri-check-line" />{m}</li>)}
            </ul>
            <button className={"pp-btn pp-btn-sm ppm-plan-pick " + (isActive ? "active" : "pp-btn-brand")} onClick={() => !isActive && onPick(pl.id)}>
              {isActive ? <><i className="ri-checkbox-circle-fill" /> Active plan</> : "Choose this plan"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

/* ── Life-event calendar (drag-to-redate, scripted re-projection) ─ */
function LifeEventCalendar({ persona, onScore }) {
  const proj = persona.projection;
  const span = proj.endAge - proj.startAge;
  const [events, setEvents] = React.useState(() => [...persona.calendar.map((e) => ({ ...e, age0: e.age })), ...(((window.__ppExtraEvents || {})[persona.id]) || [])]);
  const trackRef = React.useRef(null);
  const dragId = React.useRef(null);

  React.useEffect(() => { setEvents([...persona.calendar.map((e) => ({ ...e, age0: e.age })), ...(((window.__ppExtraEvents || {})[persona.id]) || [])]); }, [persona.id]);
  React.useEffect(() => {
    const h = (ev) => { if (!ev.detail || ev.detail.personaId === persona.id) setEvents([...persona.calendar.map((e) => ({ ...e, age0: e.age })), ...(((window.__ppExtraEvents || {})[persona.id]) || [])]); };
    window.addEventListener("ppevent", h); return () => window.removeEventListener("ppevent", h);
  }, [persona.id]);

  const pos = (age) => Math.max(0, Math.min(100, ((age - proj.startAge) / span) * 100));
  const nowEv = events.find((e) => e.state === "now");
  const progPct = nowEv ? pos(nowEv.age) : 30;

  // scripted re-projection from event shifts
  const retireEv = events.find((e) => e.type === "retire");
  const propEv = events.find((e) => e.type === "property");
  const dRetire = retireEv ? retireEv.age - retireEv.age0 : 0;
  const dProp = propEv ? propEv.age - propEv.age0 : 0;
  const baseScore = persona.readiness.score;
  const score = Math.max(0, Math.min(100, Math.round(baseScore + dRetire * 1.3 + dProp * 0.5)));
  const baseCap = proj.peak.value;
  const capital = Math.round(baseCap * (1 + dRetire * 0.045 + dProp * 0.012));
  const capDelta = capital - baseCap;
  React.useEffect(() => { if (onScore) onScore(score); }, [score]);

  const startDrag = (id) => (ev) => {
    ev.preventDefault();
    dragId.current = id;
    const move = (e) => {
      const track = trackRef.current; if (!track) return;
      const r = track.getBoundingClientRect();
      const cx = (e.touches ? e.touches[0].clientX : e.clientX);
      const pct = Math.max(0, Math.min(1, (cx - r.left) / r.width));
      const age = Math.round(proj.startAge + pct * span);
      setEvents((prev) => prev.map((x) => x.id === dragId.current ? { ...x, age, yr: String(2025 + (age - persona.age)) } : x));
    };
    const up = () => { dragId.current = null; window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };

  const moved = dRetire !== 0 || dProp !== 0;
  const tips = [];
  if (persona.id === "whitmore") tips.push({ warn: true, t: "This calendar drains your buffer below 4 months around the property event, build the reserve first." });
  if (dProp < 0) tips.push({ warn: true, t: "Bringing the property forward weakens your liquidity sub-score, keep \u2265 4 months of expenses." });
  if (dRetire > 0) tips.push({ warn: false, t: "Deferring retirement lifts projected capital and removes the early-reduction, a high-impact, low-effort move." });
  tips.push({ warn: false, t: persona.id === "bergerRey" ? "Staging Thomas's buy-ins across these years keeps each year's deduction inside the high-rate band." : "Maxing 3a every year to retirement is the single biggest score-mover here." });

  return (
    <div>
      <div className="ppm-cal-top">
        <div className="ppm-scorechip">
          <span className="num">{score}<small>/100</small></span>
          {moved && <span className={"d " + (score >= baseScore ? "up" : "down")}><i className={score >= baseScore ? "ri-arrow-up-line" : "ri-arrow-down-line"} />{score >= baseScore ? "+" : ""}{score - baseScore} vs baseline</span>}
        </div>
        <div className="ppm-cal-pred">
          <div className="ppm-pred"><div className="k">Capital at retirement</div><div className={"v" + (capDelta >= 0 ? " gain" : "")}>{E.chf(capital)}</div><div className="r">expected \u00b7 {E.chf(Math.round(capital * 0.85))} conservative</div></div>
          <div className="ppm-pred"><div className="k">Δ vs baseline calendar</div><div className={"v" + (capDelta >= 0 ? " gain" : "")}>{capDelta >= 0 ? "+" : "\u2212"}{E.chf(Math.abs(capDelta))}</div><div className="r">illustrative estimate</div></div>
        </div>
      </div>

      <div className="ppm-cal">
        <div className="ppm-cal-track" ref={trackRef}>
          <div className="ppm-cal-prog" style={{ width: progPct + "%" }} />
          {events.map((e) => (
            <div key={e.id} className={"ppm-cal-ev " + (e.type === "retire" ? "retire " : e.type === "property" || e.type === "move" ? "property " : "") + e.state}
              style={{ left: pos(e.age) + "%" }} onPointerDown={startDrag(e.id)} title="Drag to re-date">
              <div className="dot" />
              <div className="card">
                <i className={"ic " + ({ milestone: "ri-flag-2-line", save: "ri-coin-line", property: "ri-home-4-line", family: "ri-group-line", retire: "ri-rest-time-line", move: "ri-flight-takeoff-line" }[e.type] || "ri-calendar-line")} />
                <div className="yr">{e.yr} · age {e.age}</div>
                <div className="t">{e.t}</div>
                {e.amt && <span className="amt">{e.amt}</span>}
              </div>
            </div>
          ))}
        </div>
        <div className="ppm-cal-hint"><i className="ri-drag-move-2-line" />Drag any event to re-date it, the plan re-projects live</div>
      </div>

      <div className="ppm-cal-tips">
        {tips.slice(0, 3).map((t, i) => (
          <div className={"ppm-tip" + (t.warn ? " warn" : "")} key={i}>
            <i className={t.warn ? "ri-alert-line" : "ri-lightbulb-flash-line"} /><p>{t.t}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Edit & Simulate, property GO / AMBER / KO ────────────────── */
function EditSimulate({ persona, toast }) {
  const base = persona.sim;
  const d = base.defaults;
  const [price, setPrice] = React.useState(d.price);
  const [currency, setCurrency] = React.useState(d.currency);
  const [down, setDown] = React.useState(d.downPayment);
  const [calcRate, setCalcRate] = React.useState(d.calcRate);
  const [foreign, setForeign] = React.useState(d.foreign);
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    const dd = persona.sim.defaults;
    setPrice(dd.price); setCurrency(dd.currency); setDown(dd.downPayment); setCalcRate(dd.calcRate); setForeign(dd.foreign); setSaved(false);
  }, [persona.id]);

  const r = E.simulate({ price, currency, fx: 0.96, downPayment: down, calcRate, foreign,
    grossIncome: base.grossIncome, cash: base.cash, securities: base.securities,
    targetIncome: base.targetIncome, projectedBase: base.projectedBase, bufferThreshold: base.bufferThreshold });

  const verdictTxt = { GO: { t: "GO", d: "Affordable, and your retirement target still holds." }, AMBER: { t: "GO with conditions", d: "Affordable, but retirement erodes within tolerance, proceed carefully." }, KO: { t: "Not yet", d: "One or more binding constraints fail today." } }[r.verdict];
  const cur = (n) => currency === "EUR" ? "EUR " + Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019") : E.chf(n);

  return (
    <div className="ppm-sim">
      <div className="ppm-sim-controls">
        <div className="ppm-sim-row">
          <div className="lab"><span className="l">Purchase price</span><span className="v">{cur(price)}</span></div>
          <input className="ppm-range" type="range" min={currency === "EUR" ? 200000 : 250000} max={currency === "EUR" ? 1500000 : 1800000} step="10000" value={price} onChange={(e) => { setPrice(+e.target.value); setSaved(false); }} />
        </div>
        <div className="ppm-sim-row">
          <div className="lab"><span className="l">Currency</span></div>
          <div className="ppm-seg">
            {["CHF", "EUR"].map((c) => <button key={c} className={currency === c ? "on" : ""} onClick={() => { setCurrency(c); setSaved(false); }}>{c}</button>)}
          </div>
        </div>
        <div className="ppm-sim-row">
          <div className="lab"><span className="l">Down payment (equity)</span><span className="v">{E.chf(down)}</span></div>
          <input className="ppm-range" type="range" min="0" max={Math.round((currency === "EUR" ? price * 0.96 : price))} step="10000" value={Math.min(down, Math.round(currency === "EUR" ? price * 0.96 : price))} onChange={(e) => { setDown(+e.target.value); setSaved(false); }} />
        </div>
        <div className="ppm-sim-row">
          <div className="lab"><span className="l">Calculatory mortgage rate</span><span className="v">{(calcRate * 100).toFixed(1)}%</span></div>
          <input className="ppm-range" type="range" min="0.03" max="0.06" step="0.0025" value={calcRate} onChange={(e) => { setCalcRate(+e.target.value); setSaved(false); }} />
        </div>
        <div className="ppm-sim-toggle">
          <div className="bd"><div className="t">Foreign property (France)</div><div className="d">No WEF · FX buffer · French carrying costs</div></div>
          <button className={"pp-switch" + (foreign ? " on" : "")} onClick={() => { setForeign((f) => !f); setSaved(false); }} aria-pressed={foreign} />
        </div>
      </div>

      <div>
        <div className={"ppm-verdict " + r.verdict}>
          <div className="ppm-verdict-top">
            <span className="ppm-verdict-badge">{verdictTxt.t}</span>
            <div className="tx"><div className="t">{persona.first.split(" ")[0]}'s {foreign ? "Provence" : "property"} simulation</div><div className="d">{verdictTxt.d}</div></div>
          </div>
          <div className="ppm-verdict-rows">
            {r.constraints.map((c, i) => (
              <div className={"ppm-vrow" + (c.ok ? "" : " bad")} key={i}>
                <span className="l"><i className={c.ok ? "ri-checkbox-circle-fill" : "ri-close-circle-fill"} />{c.label}</span>
                <span className="val">{c.v}</span>
                <span className="lim">{c.lim}</span>
              </div>
            ))}
          </div>
          {r.flips.length > 0 && (
            <div className="ppm-flips">
              <div className="h">{r.verdict === "GO" ? "Holding it green" : "What would flip it"}</div>
              <ul>{r.flips.map((f, i) => <li key={i}><i className="ri-arrow-right-line" />{f}</li>)}</ul>
            </div>
          )}
          {foreign && <div className="ppm-sim-caveat"><i className="ri-global-line" /><span>Cross-border: French taxe foncière, IFI watch and succession rules are out of deep scope, estimates only, with a human/partner handoff for the French side.</span></div>}
          <div className="ppm-sim-actions">
            <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={() => { setSaved(true); toast && toast("Saved to your life-event calendar"); }}>
              <i className={saved ? "ri-check-line" : "ri-calendar-2-line"} />{saved ? "Saved to calendar" : "Save as planned event"}
            </button>
            <button className="pp-btn pp-btn-ghost pp-btn-sm" onClick={() => toast && toast("Preparing an advisor brief…")}><i className="ri-user-heart-line" />Get a human view</button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Divorce fork ──────────────────────────────────────────────── */
function DivorcePanel({ persona, toast }) {
  const dv = persona.divorce;
  const [pct, setPct] = React.useState(dv.splitPct || 50);
  if (!dv.applicable) return (
    <div className="ppm-tip"><i className="ri-information-line" /><p>This module applies to household scenarios. Switch to the Berger-Rey couple to model a separation.</p></div>
  );
  const each = dv.marriagePillar2;
  const av = ["var(--brand-orange)", "#6D28D9"];
  return (
    <div>
      <p className="ppm-divorce-intro">{dv.intro}</p>
      <div className="ppm-split">
        <div className="lab">2nd-pillar split<b>{E.chf(dv.marriagePillar2)}</b></div>
        <div className="ppm-splitbar"><div className="a" style={{ width: pct + "%" }}>{pct}%</div><div className="b" style={{ width: (100 - pct) + "%" }}>{100 - pct}%</div></div>
      </div>
      <input className="ppm-range" type="range" min="30" max="70" step="5" value={pct} onChange={(e) => setPct(+e.target.value)} style={{ marginBottom: 18 }} />
      <div className="ppm-fork">
        {dv.people.map((p, i) => {
          const share = i === 0 ? pct : 100 - pct;
          const cap = Math.round(dv.marriagePillar2 * share / 100);
          return (
            <div className="ppm-person" key={i}>
              <div className="ppm-person-h">
                <span className="ppm-person-av" style={{ background: av[i] }}>{p.initials}</span>
                <div><div className="nm">{p.name}</div><span className="gap" style={{ background: p.gap === "Sensitive" ? "var(--loss-50)" : "var(--ontrack-50)", color: p.gap === "Sensitive" ? "var(--loss-700)" : "var(--ontrack)" }}>{p.gap} standalone plan</span></div>
              </div>
              <div className="ppm-person-cap"><div className="k">2nd-pillar after split</div><div className="v">{E.chf(cap)}</div></div>
              <p>{p.note}</p>
            </div>
          );
        })}
      </div>
      <div className="ppm-tip warn" style={{ marginTop: 14 }}>
        <i className="ri-scales-3-line" />
        <p>Divorce is irreversible and legally heavy. This is a <b>personal recommendation</b> and is routed to a human/legal advisor, Pension Partner prepares the brief, it doesn't decide. <a onClick={() => toast && toast("Routing to a human/legal advisor…")} style={{ cursor: "pointer", textDecoration: "underline" }}>Book the handoff</a></p>
      </div>
    </div>
  );
}

/* ── Tax-statement upload modal (EPIC 11) ──────────────────────── */
function BuildLoader() {
  const STEPS = ["Reading your documents", "Extracting income, assets & debts", "Modelling AHV, 2nd & 3rd pillar", "Calculating retirement scenarios at 60, 63, 65", "Generating your personalised action plan"];
  const [i, setI] = React.useState(0);
  React.useEffect(() => { const iv = setInterval(() => setI((x) => Math.min(STEPS.length - 1, x + 1)), 520); return () => clearInterval(iv); }, []);
  const pct = Math.round(((i + 1) / STEPS.length) * 100);
  return (
    <div className="ppm-build">
      <div className="ppm-build-ring"><span /></div>
      <h3 className="ppm-build-ttl">Building your retirement portrait</h3>
      <p className="ppm-build-sub">Analysing your documents and modelling your future</p>
      <ul className="ppm-build-steps">
        {STEPS.map((s, j) => (
          <li key={j} className={j < i ? "done" : j === i ? "active" : ""}>
            <span className="dot">{j < i ? <i className="ri-check-line" /> : <span className="n">{j + 1}</span>}</span>
            <span className="lab">{s}</span>
          </li>
        ))}
      </ul>
      <div className="ppm-build-bar"><span style={{ width: pct + "%" }} /></div>
    </div>
  );
}

/* ── Reconciliation banner (EPIC: trust) ───────────────────────────
   Surfaces the deterministic self-checks PP_LIVE.validate() ran during
   extraction. Pure presentation: it reads ex._checks / ex._flags only,
   never recomputes — the maths stays in the engine. Three tones:
   ✓ figures cross-check · ⚠ a few need review · ✗ figures don't reconcile. */
function ReconBanner({ ex }) {
  if (!ex) return null;
  const checks = ex._checks || [];
  const flags = ex._flags || [];
  const passed = checks.filter((c) => c.status === "pass").length;
  const failed = checks.filter((c) => c.status === "fail").length;
  const reviews = flags.length;
  if (passed === 0 && failed === 0 && reviews === 0) return null; // nothing checkable yet

  const tone = failed > 0 ? "bad" : reviews > 0 ? "warn" : "ok";
  const P = {
    ok:   { bg: "var(--ontrack-50)", bd: "var(--ontrack)", fg: "var(--ontrack-700)", ic: "ri-checkbox-circle-fill" },
    warn: { bg: "var(--warning-50)", bd: "var(--warning)", fg: "var(--warning)",     ic: "ri-error-warning-fill" },
    bad:  { bg: "var(--danger-50)",  bd: "var(--danger)",  fg: "var(--danger)",      ic: "ri-alert-fill" },
  }[tone];
  const plural = (n) => (n === 1 ? "" : "s");
  const title = tone === "ok"
    ? "Figures cross-check ✓"
    : tone === "bad"
      ? failed + " figure" + plural(failed) + " don’t reconcile"
      : reviews + " figure" + plural(reviews) + " need a quick look";
  const sub = tone === "ok"
    ? passed + " reconciliation" + plural(passed) + " passed — your numbers are internally consistent."
    : "Nothing is wrong with your plan; these just need your eye before we trust them.";

  return (
    <div role="status" style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "11px 13px", marginBottom: 12, borderRadius: 12, background: P.bg, border: "1px solid " + P.bd }}>
      <i className={P.ic} style={{ color: P.fg, fontSize: 18, lineHeight: 1.2, flex: "0 0 auto" }} />
      <div style={{ minWidth: 0 }}>
        <div style={{ font: "700 12.5px/1.35 var(--font-display)", color: P.fg }}>{title}</div>
        <div style={{ font: "400 11.5px/1.45 var(--font-body)", color: "var(--fg-3)", marginTop: 2 }}>{sub}</div>
        {reviews > 0 && (
          <ul style={{ margin: "7px 0 0", padding: 0, listStyle: "none", display: "grid", gap: 4 }}>
            {flags.slice(0, 4).map((f, i) => (
              <li key={i} style={{ font: "400 11px/1.4 var(--font-body)", color: "var(--fg-3)", display: "flex", gap: 6 }}>
                <i className="ri-arrow-right-s-line" style={{ color: P.fg, flex: "0 0 auto" }} /><span style={{ minWidth: 0 }}>{f}</span>
              </li>
            ))}
            {flags.length > 4 && <li style={{ font: "400 11px/1.4 var(--font-body)", color: "var(--fg-4)" }}>+{flags.length - 4} more</li>}
          </ul>
        )}
      </div>
      {passed > 0 && (
        <span style={{ marginLeft: "auto", flex: "0 0 auto", font: "700 10.5px/1 var(--font-body)", color: P.fg, background: "#fff", borderRadius: 999, padding: "5px 9px" }}>{passed}/{passed + failed} ok</span>
      )}
    </div>
  );
}

function TaxUploadModal({ open, onClose, persona, toast, onDone }) {
  const [mount, setMount] = React.useState(open);
  const [show, setShow] = React.useState(false);
  const [step, setStep] = React.useState(1);
  const [state, setState] = React.useState("idle"); // idle | uploading | ocr | extracted
  const [up, setUp] = React.useState({ tax: false, lpp: false });
  const [extraNote, setExtraNote] = React.useState("");
  const [consent, setConsent] = React.useState(true);
  const [prog, setProg] = React.useState(0);
  const [drag, setDrag] = React.useState(false);
  const [err, setErr] = React.useState(null);
  const fileRef = React.useRef(null);
  const filesRef = React.useRef({});
  const timers = React.useRef([]);
  const [exData, setExData] = React.useState({});

  React.useEffect(() => {
    if (open) { setMount(true); setStep(1); setState("idle"); setUp({ tax: false, lpp: false }); setConsent(true); setProg(0); setErr(null); requestAnimationFrame(() => requestAnimationFrame(() => setShow(true))); }
    else { setShow(false); const t = setTimeout(() => setMount(false), 300); return () => clearTimeout(t); }
  }, [open]);
  React.useEffect(() => () => timers.current.forEach(clearTimeout), []);
  React.useEffect(() => {
    if (!open) return;
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [open, onClose]);

  if (!mount) return null;

  const STEPS = [
    { key: "tax", title: "Add your tax statement", icon: "ri-file-shield-2-line", short: "Tax return",
      sub: "The richest single document, it pre-fills income, wealth, deductions and your prévoyance extract. Sent encrypted; never stored without your consent.",
      file: "Tax-return-2025.pdf", success: "income, wealth & deductions" },
    { key: "lpp", title: "Add your pension certificate", icon: "ri-bank-line", short: "Pension certificate",
      sub: "Your LPP / Vorsorgeausweis confirms your 2nd-pillar capital, the projected pension and your buy-in potential.",
      file: "Pension-certificate-LPP.pdf", success: "2nd-pillar capital & buy-in" },
    { key: "extra", title: "Complementary information", icon: "ri-chat-smile-2-line", optional: true, short: "A few words",
      sub: "Anything else that shapes your future? Tell us in your own words, a side income, a future inheritance, a property abroad, an early-retirement dream. The more we know, the sharper your plan." },
  ];
  const cur = STEPS[step - 1];
  const fmt = (n) => Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019");
  const ex = exData[step === 1 ? "tax" : "lpp"] || {};
  const taxFields = [
    { key: "income", label: "Taxable income", value: fmt(ex.grossIncome || persona.grossIncome), unit: "CHF", conf: ex.grossIncome ? 96 : 90, level: "high", real: !!ex.grossIncome },
    { key: "wealth", label: "Net wealth", value: fmt(ex.netWorth || persona.netWorth), unit: "CHF", conf: ex.netWorth ? 94 : 88, level: ex.netWorth ? "high" : "med", real: !!ex.netWorth },
    { key: "canton", label: "Canton of taxation", value: (ex.canton || persona.canton), unit: "", conf: 99, level: "high", real: !!ex.canton },
  ];
  const lppFields = [
    { key: "p2", label: "2nd-pillar (LPP) capital", value: fmt(ex.pillar2 || Math.round(persona.grossIncome * 1.6)), unit: "CHF", conf: ex.pillar2 ? 95 : 86, level: ex.pillar2 ? "high" : "med", real: !!ex.pillar2 },
    { key: "p3a", label: "Pillar 3a balance", value: fmt(ex.pillar3a || 0), unit: "CHF", conf: ex.pillar3a ? 93 : 80, level: ex.pillar3a ? "high" : "low", real: !!ex.pillar3a },
    { key: "retire", label: "Reference retirement age", value: String(ex.retireAge || persona.referenceAge || 65), unit: "yrs", conf: 99, level: "high", real: !!ex.retireAge },
  ];
  const fields = step === 1 ? taxFields : lppFields;
  const anyReal = () => !!(filesRef.current.tax || filesRef.current.lpp);

  const begin = () => {
    if (step === 1 && !consent) { setErr("Please acknowledge the privacy notice before we process your document."); return; }
    setErr(null); setState("uploading"); setProg(0);
    const fileKey = step === 1 ? "tax" : "lpp";
    let p = 0;
    const iv = setInterval(() => {
      p += 16; setProg(Math.min(100, p));
      if (p >= 100) {
        clearInterval(iv);
        setState("ocr");
        (async () => {
          let vals = null;
          try {
            const f = filesRef.current[fileKey];
            if (f && window.PP_LIVE) {
              const text = await window.PP_LIVE.readFile(f);
              if ((text && text.trim()) || f) vals = await window.PP_LIVE.extract(text, {}, f);
            }
          } catch (e) {}
          setExData((d) => ({ ...d, [fileKey]: vals || {} }));
          setState("extracted");
          setUp((u) => ({ ...u, [fileKey]: true }));
          toast && toast((step === 1 ? "Tax return" : "Pension certificate") + (vals ? " analysed ✓" : " read ✓"));
        })();
      }
    }, 110);
    timers.current.push(iv);
  };
  const nextStep = (to) => { setStep(to || 2); setState("idle"); setProg(0); setErr(null); };
  const finish = () => {
    setState("building");
    const real = anyReal();
    if ((window.__ppLiveMode || real) && window.PP_LIVE && window.__ppActivateLive) {
      (async () => {
        let text = "";
        try { for (const k of ["tax", "lpp"]) { if (filesRef.current[k]) text += "\n" + (await window.PP_LIVE.readFile(filesRef.current[k])); } } catch (e) {}
        const merged = Object.assign({}, exData.tax, exData.lpp);
        let p = null;
        try { const x = merged; p = window.PP_LIVE.build(x); } catch (e) {}
        if (p && window.__ppActivateLive) window.__ppActivateLive(p);
        timers.current.push(setTimeout(() => { onDone && onDone(); onClose(); }, 500));
      })();
    } else {
      timers.current.push(setTimeout(() => { onDone && onDone(); onClose(); }, 3100));
    }
  };

  return (
    <div className={"ppm-modal-scrim" + (show ? " in" : "")} onClick={onClose}>
      <div className="ppm-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={cur.title}>
        <div className="ppm-modal-head">
          <span className="ppm-modal-ic"><i className={cur.icon} /></span>
          <div className="tx"><h3>{cur.title}</h3><p>{cur.sub}</p></div>
          <button className="ppm-modal-x" onClick={onClose} aria-label="Close"><i className="ri-close-line" /></button>
        </div>
        <div className="ppm-stepbar">
          {STEPS.map((s, i) => (
            <React.Fragment key={s.key}>
              <div className={"ppm-stepdot" + (step === i + 1 ? " on" : step > i + 1 ? " done" : "")}>
                <span className="n">{step > i + 1 ? <i className="ri-check-line" /> : i + 1}</span>
                <span className="t">{s.short || s.title}</span>
              </div>
              {i < STEPS.length - 1 && <div className="ppm-stepsep" />}
            </React.Fragment>
          ))}
        </div>
        <div className="ppm-modal-bd">
          {cur.key === "extra" && (
            <>
              <textarea className="ppm-input ppm-textarea" rows={4} value={extraNote} placeholder="e.g. I expect an inheritance around 2030, I rent out a studio in Lausanne, I'd like to stop working at 60…" onChange={(e) => setExtraNote(e.target.value)} />
              <div className="ppm-extra-chips">
                {["Side income", "Future inheritance", "Property abroad", "Early retirement", "Children's costs"].map((c) => (
                  <button key={c} className="ppm-extra-chip" onClick={() => setExtraNote((n) => (n ? n.replace(/\s*$/, ", ") : "") + c.toLowerCase() + ": ")}>+ {c}</button>
                ))}
              </div>
              <button className="ppm-attach-line" onClick={() => { if (fileRef.current) fileRef.current.click(); }}>
                <i className="ri-attachment-2" />Attach another document <span className="opt">optional</span>
                <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.heic,.txt" style={{ display: "none" }} onChange={() => toast && toast("Document attached")} />
              </button>
              <div className="ppm-modal-foot">
                <div className="ppm-foot-l">
                  <span style={{ font: "400 11.5px/1.4 var(--font-body)", color: "var(--fg-4)" }}><i className="ri-sparkling-2-line" style={{ verticalAlign: "-2px", marginRight: 5, color: "var(--brand-orange-600)" }} />Optional, but it sharpens your plan.</span>
                </div>
                <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={finish}><i className="ri-sparkling-2-line" />Build my Retirement portrait</button>
              </div>
            </>
          )}
          {cur.key !== "extra" && state === "idle" && (
            <>
              <div className={"ppm-dropzone" + (drag ? " drag" : "")}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files && e.dataTransfer.files[0]) filesRef.current[step === 1 ? "tax" : "lpp"] = e.dataTransfer.files[0]; begin(); }}>
                <i className="ri-upload-cloud-2-line dzic" />
                <h4>Choose a file from your computer</h4>
                <p>or drag &amp; drop it here, {step === 1 ? "your latest tax return" : "your pension-fund certificate"}</p>
                <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.heic,.txt" style={{ display: "none" }} onChange={(e) => { if (e.target.files && e.target.files[0]) filesRef.current[step === 1 ? "tax" : "lpp"] = e.target.files[0]; begin(); }} />
                <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={() => fileRef.current && fileRef.current.click()}><i className="ri-folder-open-line" />Browse files</button>
              </div>
              <div className="ppm-modal-meta">
                <span className="chip">PDF</span><span className="chip">JPG</span><span className="chip">PNG</span><span className="chip">HEIC</span><span>· max 20 MB</span>
              </div>
              {step === 1 && (
                <div className={"ppm-consent" + (consent ? "" : " req")} onClick={() => { setConsent((c) => !c); setErr(null); }}>
                  <span className={"ppm-check" + (consent ? " on" : "")}>{consent && <i className="ri-check-line" />}</span>
                  <p>I consent to Pension Partner processing these sensitive financial documents to build my plan (revDPA). Processing only, not model training. <a onClick={(e) => { e.stopPropagation(); toast && toast("Opening your data controls…"); }}>Data controls</a></p>
                </div>
              )}
              {err && <div className="ppm-modal-err"><i className="ri-error-warning-line" /><span>{err}</span></div>}
              <div className="ppm-modal-foot">
                <div className="ppm-foot-l">
                  <button className="pp-btn pp-btn-ghost pp-btn-sm" onClick={() => { toast && toast("Switching to manual entry"); onClose(); }}><i className="ri-keyboard-line" />Enter manually</button>
                  <a className="ppm-foot-link" onClick={() => { onClose(); window.__ppOpenConsult && window.__ppOpenConsult(); }}><i className="ri-user-voice-line" />Contact a consultant</a>
                </div>
                <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={finish} disabled={!(up.tax && up.lpp)} title={up.tax && up.lpp ? "" : "Upload both documents first"}><i className="ri-sparkling-2-line" />Simulate my Retirement portrait</button>
              </div>
            </>
          )}

          {state === "uploading" && (
            <div className="ppm-uprow"><span className="fic"><i className="ri-file-pdf-2-line" /></span>
              <div className="ub"><div className="fn">{cur.file}</div><div className="fs">Uploading… {prog}%</div><div className="ppm-upbar"><span style={{ width: prog + "%" }} /></div></div>
            </div>
          )}
          {state === "ocr" && (
            <div style={{ textAlign: "center", padding: "26px 0" }}>
              <div className="pp-typing" style={{ margin: "0 auto 14px" }}><span /><span /><span /></div>
              <div style={{ font: "700 14px/1.3 var(--font-display)", color: "var(--fg-1)" }}>Reading your {step === 1 ? "tax return" : "certificate"}…</div>
              <div style={{ font: "400 12.5px/1.5 var(--font-body)", color: "var(--fg-4)", marginTop: 4 }}>Extracting {cur.success}, each field with a confidence score.</div>
            </div>
          )}
          {state === "extracted" && (
            <>
              <div className="ppm-uprow" style={{ borderColor: "var(--ontrack)", background: "var(--ontrack-50)" }}>
                <span className="fic" style={{ background: "#fff", color: "var(--ontrack)" }}><i className="ri-checkbox-circle-fill" /></span>
                <div className="ub"><div className="fn">{(step === 1 ? "Tax return" : "Pension certificate") + " " + (anyReal() ? "analysed" : "read")}</div><div className="fs" style={{ color: "var(--ontrack)" }}>{(filesRef.current[step === 1 ? "tax" : "lpp"] && filesRef.current[step === 1 ? "tax" : "lpp"].name) || cur.file} · {fields.filter((f) => f.real).length > 0 ? fields.filter((f) => f.real).length + " read from your document" : fields.length + " fields, review below"}</div></div>
                <span style={{ font: "700 11px/1 var(--font-body)", color: "var(--ontrack)", background: "#fff", borderRadius: 999, padding: "5px 10px", flex: "0 0 auto" }}>{(up.tax ? 1 : 0) + (up.lpp ? 1 : 0)} of 2</span>
              </div>
              <ReconBanner ex={ex} />
              <div className="ppm-ocr-fields">
                {fields.map((f) => <ConfirmCorrect key={f.key} field={f} onResolve={(fk, v) => { const map = { income: "grossIncome", wealth: "netWorth", canton: "canton", p2: "pillar2", p3a: "pillar3a", retire: "retireAge" }; const tgt = map[fk]; if (!tgt) return; const dkey = step === 1 ? "tax" : "lpp"; let val = v; if (tgt !== "canton") { val = Number(String(v).replace(/[^0-9.\-]/g, "")); if (isNaN(val)) return; } setExData((d) => { const cur = Object.assign({}, d[dkey]); cur[tgt] = val; cur._extracted = Object.assign({}, cur._extracted, { [tgt]: true }); cur._confirmed = Object.assign({}, cur._confirmed, { [tgt]: true }); return Object.assign({}, d, { [dkey]: cur }); }); }} />)}
              </div>
              <div className="ppm-modal-foot">
                <div className="ppm-foot-l">
                  <span style={{ font: "400 11.5px/1.4 var(--font-body)", color: "var(--fg-4)" }}><i className="ri-shield-check-line" style={{ verticalAlign: "-2px", marginRight: 5 }} />Nothing enters your plan until you confirm.</span>
                  <a className="ppm-foot-link" onClick={() => { onClose(); window.__ppOpenConsult && window.__ppOpenConsult(); }}><i className="ri-user-voice-line" />Contact a consultant</a>
                </div>
                {step === 1
                  ? <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={nextStep}><i className="ri-arrow-right-line" />Confirm &amp; add pension certificate</button>
                  : <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={() => nextStep(3)} disabled={!(up.tax && up.lpp)}><i className="ri-arrow-right-line" />Confirm &amp; add a few words</button>}
              </div>
            </>
          )}

          {state === "building" && (
            <div style={{ padding: "8px 0 4px" }}>
              <BuildLoader />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── V1 embed: v0.2 tools bundled for the monitoring hub ───────── */
function ToolSec({ title, sub, children }) {
  return (
    <section className="ppv2-sec" style={{ marginTop: 22 }}>
      <div className="ppv2-sec-h"><h2>{title}</h2>{sub && <div className="s">{sub}</div>}</div>
      {children}
    </section>
  );
}
function MonitorToolsV1({ persona, activePlan, onPick, toast }) {
  return (
    <div>
      <ToolSec title="Your readiness, decomposed" sub="Plan Score sub-scores (§25)">
        <div className="ppv2-card"><SubScorePanel sub={(persona.plans.find((p) => p.id === activePlan) || {}).sub || persona.subScores} /></div>
      </ToolSec>
      <ToolSec title="Choose your strategy" sub="Compare and switch anytime">
        <PlansCompare persona={persona} activePlan={activePlan} onPick={(id) => { onPick(id); toast && toast("Active plan updated, re-baselined"); }} />
      </ToolSec>
      <ToolSec title="Edit & Simulate, property" sub="Live GO / AMBER / KO">
        <div className="ppv2-card"><EditSimulate persona={persona} toast={toast} /></div>
      </ToolSec>
      <ToolSec title="Your life-event calendar" sub="Drag to re-date, re-projects live">
        <div className="ppv2-card"><LifeEventCalendar persona={persona} /></div>
      </ToolSec>
      <ToolSec title="Life event, separation" sub="Forks the household into two plans">
        <div className="ppv2-card"><DivorcePanel persona={persona} toast={toast} /></div>
      </ToolSec>
    </div>
  );
}

/* ── Consultant booking modal (human handoff · EPIC 9 / Journey F) ─ */
function ConsultantModal({ open, onClose, persona, toast }) {
  const [mount, setMount] = React.useState(open);
  const [show, setShow] = React.useState(false);
  const [sent, setSent] = React.useState(false);
  const [channel, setChannel] = React.useState("Phone");
  const [meeting, setMeeting] = React.useState("In person");
  const [slot, setSlot] = React.useState("This week");
  const [branch, setBranch] = React.useState(null);
  const [name, setName] = React.useState("");
  const [phone, setPhone] = React.useState("");

  const branches = ["Geneva", "Lausanne", "Z\u00fcrich", "Zug", "Lugano"];
  React.useEffect(() => {
    if (open) {
      setMount(true); setSent(false); setChannel("Phone"); setMeeting("In person"); setSlot("This week");
      setName(persona ? persona.name : ""); setPhone("");
      setBranch((persona && branches.find((b) => persona.canton.indexOf(b) === 0)) || "Geneva");
      requestAnimationFrame(() => requestAnimationFrame(() => setShow(true)));
    } else { setShow(false); const t = setTimeout(() => setMount(false), 300); return () => clearTimeout(t); }
  }, [open]);
  React.useEffect(() => {
    if (!open) return;
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [open, onClose]);
  if (!mount) return null;

  const seg = (val, set, opts) => (
    <div className="ppm-seg">{opts.map((o) => <button key={o} className={val === o ? "on" : ""} onClick={() => set(o)}>{o}</button>)}</div>
  );

  return (
    <div className={"ppm-modal-scrim" + (show ? " in" : "")} onClick={onClose}>
      <div className="ppm-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Talk to a pension consultant">
        <div className="ppm-modal-head">
          <span className="ppm-modal-ic"><i className="ri-user-voice-line" /></span>
          <div className="tx"><h3>Talk to a pension consultant</h3><p>Prefer to start with a person? A Swissquote pension expert will call you to arrange a meeting, at a branch or by video, and walk through your plan with you.</p></div>
          <button className="ppm-modal-x" onClick={onClose} aria-label="Close"><i className="ri-close-line" /></button>
        </div>
        <div className="ppm-modal-bd">
          {!sent ? (
            <>
              <div className="ppm-form">
                <div className="ppm-grid2">
                  <div className="ppm-field"><label>Your name</label><input className="ppm-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="First and last name" /></div>
                  <div className="ppm-field"><label>Phone</label><input className="ppm-input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+41 …" inputMode="tel" /></div>
                </div>
                <div className="ppm-field"><label>How should we reach you?</label>{seg(channel, setChannel, ["Phone", "Email", "WhatsApp"])}</div>
                <div className="ppm-field"><label>Meeting type</label>{seg(meeting, setMeeting, ["In person", "Video call"])}</div>
                {meeting === "In person" && (
                  <div className="ppm-field"><label>Preferred branch</label>
                    <div className="ppm-slotrow">{branches.map((b) => <button key={b} className={"ppm-slot" + (branch === b ? " on" : "")} onClick={() => setBranch(b)}>{b}</button>)}</div>
                  </div>
                )}
                <div className="ppm-field"><label>When suits you?</label>
                  <div className="ppm-slotrow">{["This week", "Next week", "Morning", "Afternoon", "Evening"].map((s) => <button key={s} className={"ppm-slot" + (slot === s ? " on" : "")} onClick={() => setSlot(s)}>{s}</button>)}</div>
                </div>
              </div>
              <div className="ppm-consent" style={{ cursor: "default" }}>
                <span className="ppm-check on"><i className="ri-shield-check-line" /></span>
                <p>Your details are used only to arrange this appointment (revDPA). A licensed Swissquote pension consultant, a real person, will follow up. <a onClick={(e) => { e.stopPropagation(); toast && toast("Opening your data controls…"); }}>Data controls</a></p>
              </div>
              <div className="ppm-modal-foot">
                <button className="pp-btn pp-btn-ghost pp-btn-sm" onClick={onClose}>Not now</button>
                <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={() => { setSent(true); toast && toast("Request sent, a consultant will be in touch"); }}><i className="ri-calendar-check-line" />Request my appointment</button>
              </div>
            </>
          ) : (
            <div className="ppm-success">
              <div className="ppm-success-ic"><i className="ri-checkbox-circle-fill" /></div>
              <h4>You're booked in</h4>
              <p>A Swissquote pension consultant will contact you by <b>{channel.toLowerCase()}</b> within <b>1 business day</b> to confirm your {meeting === "In person" ? <>in-person meeting{branch ? <> in <b>{branch}</b></> : null}</> : <>video call</>}, {slot.toLowerCase()}.</p>
              <div className="ppm-success-card">
                <div className="r"><span>Contact</span><b>{name || ", "}{phone ? " · " + phone : ""}</b></div>
                <div className="r"><span>Meeting</span><b>{meeting}{meeting === "In person" && branch ? " · " + branch : ""}</b></div>
                <div className="r"><span>Timing</span><b>{slot}</b></div>
              </div>
              <p className="ppm-success-note">We'll bring a brief prepared from your plan, so you won't start from scratch.</p>
              <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={onClose} style={{ marginTop: 4 }}><i className="ri-check-line" />Done</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Workspace: strategy picker · activation · user info (V1 right pane) ── */
// Shared recommendation logic: the plan whose target score is closest to the
// live plan score (ties → higher-scoring plan). Used by BOTH the AI-recommendation
// row on the timeline and the "Choose your strategy" picker so they never diverge.
window.PP_PICK_REC = function (persona, score) {
  return persona.plans.slice().sort((a, b) => {
    const da = Math.abs(a.score - score), db = Math.abs(b.score - score);
    return da !== db ? da - db : b.score - a.score;
  })[0];
};
function StrategyPicker({ persona, activePlan, onPick, recId, horizontal }) {
  const rid = recId || (persona.plans.find((p) => p.rec) || {}).id;
  return (
    <div className={"ppm-strat" + (horizontal ? " is-row" : "")}>
      {persona.plans.map((pl) => {
        const on = activePlan === pl.id;
        return (
          <button key={pl.id} className={"ppm-strat-opt" + (on ? " on" : "")} onClick={() => onPick(pl.id)}>
            <span className="ppm-strat-radio">{on && <i className="ri-check-line" />}</span>
            <span className="ppm-strat-bd">
              <span className="nm">{pl.name}{pl.id === rid && <span className="rec">Recommended</span>}</span>
              <span className="th">{pl.thesis}</span>
              <span className="mt"><b>{pl.income}</b><span className="d" />{pl.risk} risk<span className="d" />Score {pl.score}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ActivationCard({ toast, mode, setMode, hideCta }) {
  const [localMode, setLocalMode] = React.useState(null);
  const m = mode !== undefined ? mode : localMode;
  const sm = setMode || setLocalMode;
  const [active, setActive] = React.useState(false);
  const opts = [
    { id: "ai", icon: "ri-sparkling-2-line", t: "Full AI", d: "Autonomous & always-on. Pension Partner monitors your plan and acts within the mandate you set, nudging you before every deadline." },
    { id: "assisted", icon: "ri-user-heart-line", t: "Assisted by a consultant", d: "AI does the heavy lifting; a Swissquote pension expert reviews key moves and every irreversible decision with you." },
  ];
  const go = () => {
    if (!m) return;
    setActive(true);
    if (m === "assisted") window.__ppOpenConsult && window.__ppOpenConsult();
    toast && toast(m === "ai" ? "Activated · full-AI monitoring is on" : "Activated · a consultant will be in touch");
  };
  return (
    <div className="ppm-activate">
      {opts.map((o) => (
        <button key={o.id} className={"ppm-act-opt" + (m === o.id ? " on" : "")} onClick={() => { sm(o.id); setActive(false); }}>
          <span className="ic"><i className={o.icon} /></span>
          <span className="bd"><span className="t">{o.t}</span><span className="d">{o.d}</span></span>
          <span className="ppm-act-radio">{m === o.id && <i className="ri-checkbox-circle-fill" />}</span>
        </button>
      ))}
      {!hideCta && (
        <button className="pp-btn pp-btn-brand" style={{ width: "100%", marginTop: 4 }} disabled={!m || active} onClick={go}>
          <i className={active ? "ri-check-line" : "ri-rocket-2-line"} />{active ? (m === "ai" ? "Full-AI plan active" : "Assisted plan active") : "Activate Pension Partner"}
        </button>
      )}
    </div>
  );
}

/* ── Editable chronological life-event timeline (auto-adjusts plan) ── */
const EVENT_CATALOG = [
  { type: "property", t: "Buy property", icon: "ri-home-4-line" },
  { type: "family", t: "Child to university", icon: "ri-graduation-cap-line" },
  { type: "save", t: "Sabbatical", icon: "ri-pause-circle-line" },
  { type: "windfall", t: "Inheritance", icon: "ri-gift-line" },
  { type: "work", t: "Go self-employed", icon: "ri-briefcase-4-line" },
  { type: "divorce", t: "Divorce", icon: "ri-scales-3-line" },
  { type: "property", t: "Second home", icon: "ri-home-smile-2-line" },
  { type: "retire", t: "Retire", icon: "ri-rest-time-line" },
];
const DOT_ICON = { milestone: "ri-flag-2-line", save: "ri-coin-line", property: "ri-home-4-line", family: "ri-graduation-cap-line", retire: "ri-rest-time-line", move: "ri-flight-takeoff-line", windfall: "ri-gift-line", work: "ri-briefcase-4-line", divorce: "ri-scales-3-line" };
// scripted contribution of an event to the plan score (illustrative)
function evtContribution(ev, persona) {
  const ret = persona.retireTarget || 64;
  switch (ev.type) {
    case "retire": return (ev.age - ret) * 1.3;
    case "property": return -2.5 + (ev.age - (ev.age0 != null ? ev.age0 : ev.age)) * 0.3;
    case "windfall": return 3;
    case "work": return -2;
    case "divorce": return -6;
    case "save": return -2;
    case "family": return -1;
    default: return 0;
  }
}
function EventTimeline({ persona, activePlan, onPick, toast, horizontal, onScore, onEvents }) {
  const seed = () => [...persona.calendar.map((e) => ({ ...e, age0: e.age })), ...(((window.__ppExtraEvents || {})[persona.id]) || [])];
  const [events, setEvents] = React.useState(seed);
  const [adding, setAdding] = React.useState(false);
  React.useEffect(() => { setEvents(seed()); setAdding(false); }, [persona.id]);
  React.useEffect(() => {
    const h = (ev) => { if (!ev.detail || ev.detail.personaId === persona.id) setEvents(seed()); };
    window.addEventListener("ppevent", h); return () => window.removeEventListener("ppevent", h);
  }, [persona.id]);

  const base = persona.readiness.score;
  const baseSum = persona.calendar.reduce((s, e) => s + evtContribution({ ...e, age0: e.age }, persona), 0);
  const liveSum = events.reduce((s, e) => s + evtContribution(e, persona), 0);
  const score = Math.max(0, Math.min(100, Math.round(base + (liveSum - baseSum))));
  const delta = score - base;
  // recommended strategy = plan whose score is closest to the live score
  const rec = window.PP_PICK_REC ? window.PP_PICK_REC(persona, score) : persona.plans.slice().sort((a, b) => Math.abs(a.score - score) - Math.abs(b.score - score))[0];
  // keep the parent (and the "Choose your strategy" picker) in sync with the live recommendation
  React.useEffect(() => { if (onScore) onScore(score); }, [score]);
  React.useEffect(() => { if (onEvents) onEvents(events); }, [events]);

  const sorted = events.slice().sort((a, b) => a.age - b.age);
  const reDate = (id, d) => setEvents((prev) => prev.map((e) => e.id === id ? { ...e, age: Math.max(persona.age, Math.min(90, e.age + d)), yr: String(2025 + (Math.max(persona.age, Math.min(90, e.age + d)) - persona.age)) } : e));
  const del = (id) => setEvents((prev) => prev.filter((e) => e.id !== id));
  const [editing, setEditing] = React.useState(null);
  const openEdit = (e) => setEditing({ id: e.id, t: e.t, age: e.age, amt: e.amt || "", type: e.type });
  const saveEdit = () => {
    setEvents((prev) => prev.map((e) => e.id === editing.id ? { ...e, t: editing.t || e.t, age: editing.age, yr: String(2025 + (editing.age - persona.age)), amt: editing.amt } : e));
    const nm = editing.t; setEditing(null); toast && toast((nm || "Event") + " updated, strategy re-projected");
  };
  const editYr = editing ? 2025 + (editing.age - persona.age) : 0;
  const add = (cat) => {
    const age = Math.min(persona.retireTarget || 64, persona.age + 5);
    setEvents((prev) => [...prev, { id: "u" + Date.now(), type: cat.type, t: cat.t, age, age0: age, yr: String(2025 + (age - persona.age)), state: "next" }]);
    setAdding(false); toast && toast(cat.t + " added, plan re-projected");
  };

  return (
    <div>
      <div className="ppm-tline-top">
        <div className="ppm-tline-score">
          <span className="num">{score}<small>/100</small></span>
          {delta !== 0 && <span className={"delta " + (delta > 0 ? "up" : "down")}><i className={delta > 0 ? "ri-arrow-up-line" : "ri-arrow-down-line"} />{delta > 0 ? "+" : ""}{delta}</span>}
        </div>
        <button className="ppm-tline-addbtn" onClick={() => (window.__ppOpenEvent ? window.__ppOpenEvent() : setAdding((a) => !a))}><i className="ri-add-line" />Add life event</button>
      </div>

      {adding && (
        <div className="ppm-tline-add">
          <div className="lbl">Add a life event</div>
          <div className="ppm-tline-cats">
            {EVENT_CATALOG.map((c, i) => <button key={i} className="ppm-tline-cat" onClick={() => add(c)}><i className={c.icon} />{c.t}</button>)}
          </div>
        </div>
      )}

      {horizontal ? (
        <div className="ppm-tlh">
          <div className="ppm-tlh-track">
            {sorted.map((e, i) => {
              const kind = e.state === "done" ? "done" : e.state === "now" ? "now" : e.type === "retire" ? "retire" : e.type === "property" ? "property" : "future";
              const segDone = e.state === "done";
              return (
                <div className={"ppm-tlh-col " + e.state} key={e.id} style={{ animationDelay: (i * 60) + "ms" }}>
                  <div className="rail">
                    <span className={"seg l" + (segDone ? " fill" : "")} />
                    <span className={"node " + kind}><i className={DOT_ICON[e.type] || "ri-circle-line"} /></span>
                    <span className={"seg r" + (segDone ? " fill" : "")} />
                  </div>
                  <div className="card">
                    {e.state !== "done" && <button className="card-del" onClick={() => del(e.id)} title="Remove" aria-label="Remove event"><i className="ri-close-line" /></button>}
                    <div className="yr"><span className="y">{e.yr}</span><span className="age">age {e.age}</span></div>
                    <div className="t">{e.t}</div>
                    {e.amt && <span className="amt">{e.amt}</span>}
                    {e.state !== "done" ? (
                      <div className="redate">
                        <button className="rd" onClick={() => reDate(e.id, -1)} title="One year earlier" aria-label="Earlier"><i className="ri-arrow-left-s-line" /></button>
                        <button className="rl" onClick={() => openEdit(e)} title="Edit this event"><i className="ri-calendar-event-line" />Adjust date</button>
                        <button className="rd" onClick={() => reDate(e.id, 1)} title="One year later" aria-label="Later"><i className="ri-arrow-right-s-line" /></button>
                      </div>
                    ) : <div className="done-tag"><i className="ri-check-line" />Done</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="ppm-tline" style={{ marginTop: 12 }}>
          {sorted.map((e) => (
            <div className="ppm-tline-row" key={e.id}>
              <div className="ppm-tline-rail"><div className={"ppm-tline-dot " + (e.state === "done" ? "done" : e.state === "now" ? "now" : e.type === "retire" ? "retire" : e.type === "property" ? "property" : "")} /><div className="ppm-tline-line" /></div>
              <div className="ppm-tline-bd">
                <div className="yr"><i className={DOT_ICON[e.type] || "ri-calendar-line"} />{e.yr} · age {e.age}</div>
                <div className="t">{e.t}</div>
                {e.state !== "done" && (
                  <div className="ppm-tline-redate">
                    <button onClick={() => reDate(e.id, -1)} title="Earlier"><i className="ri-subtract-line" /></button>
                    <span className="ag">re-date</span>
                    <button onClick={() => reDate(e.id, 1)} title="Later"><i className="ri-add-line" /></button>
                  </div>
                )}
              </div>
              {e.state !== "done" && <button className="ppm-tline-del" onClick={() => del(e.id)} title="Remove"><i className="ri-delete-bin-6-line" /></button>}
            </div>
          ))}
        </div>
      )}

      <div className={"ppm-tline-rec" + (onPick && activePlan === rec.id ? " is-active" : "")}>
        <span className="spark"><i className="ri-sparkling-2-line" /></span>
        <div className="bd">
          <div className="k"><i className="ri-magic-line" />AI recommendation for this timeline</div>
          <div className="v"><b>{rec.name}</b><span className="inc">{rec.income}</span><span className="why">best fit at score {score} · {rec.thesis}</span></div>
        </div>
        {onPick && activePlan !== rec.id && (
          <button className="ppm-rec-apply" onClick={() => { onPick(rec.id); toast && toast("Switched to " + rec.name + ", your plan re-projected"); }}>
            <span>Switch to {rec.name}</span><i className="ri-arrow-right-line" />
          </button>
        )}
        {onPick && activePlan === rec.id && <span className="ppm-rec-on"><i className="ri-checkbox-circle-fill" />Active plan</span>}
      </div>

      {editing && (
        <div className="ppm-modal-scrim in" onClick={() => setEditing(null)}>
          <div className="ppm-modal ppm-editev" style={{ width: 440 }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Edit event">
            <div className="ppm-modal-head">
              <span className="ppm-modal-ic"><i className={DOT_ICON[editing.type] || "ri-calendar-event-line"} /></span>
              <div className="tx"><h3>Edit life event</h3><p>Adjust the date or amount, your plan score and strategy re-project instantly.</p></div>
              <button className="ppm-modal-x" onClick={() => setEditing(null)} aria-label="Close"><i className="ri-close-line" /></button>
            </div>
            <div className="ppm-modal-bd">
              <div className="ppm-field"><label>Event</label>
                <input className="ppm-input" value={editing.t} onChange={(ev) => setEditing({ ...editing, t: ev.target.value })} /></div>
              <div className="ppm-field" style={{ marginTop: 14 }}>
                <label>When · year {editYr} (age {editing.age})</label>
                <div className="ppm-editev-date">
                  <button onClick={() => setEditing({ ...editing, age: Math.max(persona.age, editing.age - 1) })} aria-label="Earlier"><i className="ri-arrow-left-s-line" /></button>
                  <input type="range" min={persona.age} max={90} value={editing.age} onChange={(ev) => setEditing({ ...editing, age: +ev.target.value })} />
                  <button onClick={() => setEditing({ ...editing, age: Math.min(90, editing.age + 1) })} aria-label="Later"><i className="ri-arrow-right-s-line" /></button>
                </div>
                <div className="ppm-editev-yrs"><span>{persona.age}</span><b>{editYr}</b><span>90</span></div>
              </div>
              {(editing.amt !== "" || ["property", "windfall", "save", "work"].indexOf(editing.type) >= 0) && (
                <div className="ppm-field" style={{ marginTop: 14 }}>
                  <label>Amount</label>
                  <input className="ppm-input" value={editing.amt} placeholder="e.g. CHF 37'000" onChange={(ev) => setEditing({ ...editing, amt: ev.target.value })} />
                </div>
              )}
              <div className="ppm-modal-foot" style={{ marginTop: 18 }}>
                <button className="pp-btn pp-btn-ghost pp-btn-sm" onClick={() => { del(editing.id); setEditing(null); toast && toast("Event removed, strategy re-projected"); }}><i className="ri-delete-bin-6-line" />Remove</button>
                <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={saveEdit}><i className="ri-check-line" />Save &amp; re-project</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function UserInfoCard({ persona }) {
  const chf = window.PP_ENGINE.chf;
  const rows = [
    { l: "Name", v: persona.name, s: false },
    { l: "Age", v: String(persona.age), s: false },
    { l: "Canton", v: persona.canton, s: false },
    { l: "Situation", v: persona.status, s: false },
    { l: "Gross income", v: chf(persona.grossIncome), s: true },
    { l: "Net worth", v: chf(persona.netWorth), s: true },
    { l: "Target income", v: chf(persona.targetYearly) + "/yr", s: true },
  ];
  return (
    <div className="ppm-userinfo">
      <div className="ppm-ui-head">
        <span className="t"><i className="ri-id-card-line" />Your information</span>
        <button className="ppm-ui-edit" onClick={() => window.__ppToast && window.__ppToast("Edit your details — coming up")} title="Edit your information"><i className="ri-pencil-line" /></button>
      </div>
      <div className="ppm-ui-rows">
        {rows.map((r, i) => (
          <div className="ppm-ui-row" key={i}>
            <span className="l">{r.l}</span>
            <span className={"v" + (r.s ? " ppv2-sensitive pp-pi" : "")}>{r.v}</span>
          </div>
        ))}
        <div className="ppm-ui-row"><span className="l">Documents</span><span className="v ok"><i className="ri-checkbox-circle-fill" /> Tax return · Pension certificate</span></div>
      </div>
      {window.ConfidenceMeter ? React.createElement(window.ConfidenceMeter, {
        persona: persona,
        onAction: () => window.__ppOpenTax && window.__ppOpenTax(),
      }) : null}
      <div className="ppm-ui-foot"><i className="ri-shield-keyhole-line" />Sensitive values mask with “Hide numbers” · revDPA · hosted in Switzerland</div>
    </div>
  );
}

/* ── Fast-login modal (existing Swissquote / Yuh customers) ────── */
function LoginModal({ open, onClose, onLogin, toast }) {
  const [mount, setMount] = React.useState(open);
  const [show, setShow] = React.useState(false);
  const [busy, setBusy] = React.useState(null);   // 'swissquote' | 'yuh'
  const [ok, setOk] = React.useState(null);
  const timers = React.useRef([]);
  React.useEffect(() => {
    if (open) { setMount(true); setBusy(null); setOk(null); requestAnimationFrame(() => requestAnimationFrame(() => setShow(true))); }
    else { setShow(false); const t = setTimeout(() => setMount(false), 300); return () => clearTimeout(t); }
  }, [open]);
  React.useEffect(() => () => timers.current.forEach(clearTimeout), []);
  React.useEffect(() => {
    if (!open) return; const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [open, onClose]);
  if (!mount) return null;

  const brands = {
    swissquote: { name: "Swissquote", logo: (window.__resources && window.__resources.brandSwissquote) || "assets/brand-swissquote.png", tile: "#2A2D31", sub: "Trading & banking client" },
    yuh: { name: "Yuh", logo: (window.__resources && window.__resources.brandYuh) || "assets/brand-yuh.png", tile: "#2A2D31", sub: "Yuh app user" },
  };
  const connect = (id) => {
    if (busy) return;
    setBusy(id);
    timers.current.push(setTimeout(() => { setBusy(null); setOk(id); }, 1500));
    timers.current.push(setTimeout(() => { onLogin && onLogin(id); onClose(); }, 2500));
  };

  return (
    <div className={"ppm-modal-scrim" + (show ? " in" : "")} onClick={onClose}>
      <div className="ppm-modal" style={{ width: 460 }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Log in">
        <div className="ppm-modal-head">
          <span className="ppm-modal-ic"><i className="ri-login-circle-line" /></span>
          <div className="tx"><h3>Already a client? Log in</h3><p>Connect your Swissquote or Yuh account and we'll import your prévoyance data securely, no documents to upload.</p></div>
          <button className="ppm-modal-x" onClick={onClose} aria-label="Close"><i className="ri-close-line" /></button>
        </div>
        <div className="ppm-modal-bd">
          {!ok ? (
            <div className="ppm-login">
              {Object.keys(brands).map((id) => {
                const b = brands[id];
                return (
                  <button key={id} className={"ppm-login-opt" + (busy === id ? " busy" : "")} disabled={!!busy} onClick={() => connect(id)}>
                    <span className={"mk"} style={{ background: b.tile }}><img src={b.logo} alt={b.name} /></span>
                    <span className="bd"><span className="t">Continue with {b.name}</span><span className="d">{b.sub}</span></span>
                    {busy === id ? <i className="ri-loader-4-line ppm-spin" /> : <i className="ri-arrow-right-line" />}
                  </button>
                );
              })}
              <div className="ppm-login-sep"><span>or</span></div>
              <button className={"ppm-login-opt pp-only" + (busy === "pension" ? " busy" : "")} disabled={!!busy} onClick={() => connect("pension")}>
                <span className="mk" style={{ background: "var(--fg-1)" }}><i className="ri-mail-line" /></span>
                <span className="bd"><span className="t">Continue with a Pension Partner account</span><span className="d">No Swissquote or Yuh account · sign in with email</span></span>
                {busy === "pension" ? <i className="ri-loader-4-line ppm-spin" /> : <i className="ri-arrow-right-line" />}
              </button>
              <div className="ppm-login-note"><i className="ri-shield-check-line" />Bank-grade SSO · we never see your password · revDPA</div>
            </div>
          ) : (
            <div className="ppm-success">
              <div className="ppm-success-ic"><i className="ri-checkbox-circle-fill" /></div>
              <h4>{ok === "pension" ? "You're in" : "Welcome back"}</h4>
              <p>{ok === "pension" ? "Signed in to your " : "Connected to "}<b>{ok === "pension" ? "Pension Partner account" : brands[ok].name}</b>. {ok === "pension" ? "Building your portrait…" : "Your prévoyance data is already here, building your portrait…"}</p>
              <div className="pp-typing" style={{ margin: "10px auto 0" }}><span /><span /><span /></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { LoginModal });
Object.assign(window, { EventTimeline });

function MethodChoiceModal({ open, onClose, onUpload, onManual }) {
  const [mount, setMount] = React.useState(open);
  const [show, setShow] = React.useState(false);
  React.useEffect(() => {
    if (open) { setMount(true); requestAnimationFrame(() => requestAnimationFrame(() => setShow(true))); }
    else { setShow(false); const t = setTimeout(() => setMount(false), 280); return () => clearTimeout(t); }
  }, [open]);
  React.useEffect(() => {
    if (!open) return;
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [open, onClose]);
  if (!mount) return null;
  return (
    <div className={"ppm-modal-scrim" + (show ? " in" : "")} onClick={onClose}>
      <div className="ppm-modal ppm-method" style={{ width: 540 }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="How would you like to start?">
        <div className="ppm-modal-head">
          <span className="ppm-modal-ic"><i className="ri-route-line" /></span>
          <div className="tx"><h3>How would you like to build it?</h3><p>Both lead to the same plan. Most people upload, it is faster and sharper, but you can type everything in by hand instead.</p></div>
          <button className="ppm-modal-x" onClick={onClose} aria-label="Close"><i className="ri-close-line" /></button>
        </div>
        <div className="ppm-modal-bd">
          <button className="ppm-method-opt rec" onClick={onUpload}>
            <span className="mk"><i className="ri-upload-cloud-2-line" /></span>
            <span className="bd">
              <span className="t">Upload &amp; let AI read it<span className="tag">Recommended</span></span>
              <span className="d">Drop your tax return and pension certificate. We extract every figure with a confidence score, ready in about a minute.</span>
            </span>
            <i className="ri-arrow-right-line ar" />
          </button>
          <button className="ppm-method-opt" onClick={onManual}>
            <span className="mk alt"><i className="ri-keyboard-line" /></span>
            <span className="bd">
              <span className="t">Enter my details manually</span>
              <span className="d">No documents at hand? Type your income, pillars and goals yourself. You can add documents later to sharpen the plan.</span>
            </span>
            <i className="ri-arrow-right-line ar" />
          </button>
          <div className="ppm-method-note"><i className="ri-shield-check-line" />Whichever you pick, nothing is shared without your consent. revDPA, hosted in Switzerland.</div>
        </div>
      </div>
    </div>
  );
}
Object.assign(window, { MethodChoiceModal });

Object.assign(window, { PersonaSwitcher, SubScorePanel, PlansCompare, LifeEventCalendar, EditSimulate, DivorcePanel, TaxUploadModal, MonitorToolsV1, ConsultantModal, StrategyPicker, ActivationCard, UserInfoCard, EventTimeline, LifeEventModal });

/* ── Declare-a-life-event modal (shown on return / "each connection") ── */
function LifeEventModal({ open, onClose, persona, toast }) {
  const [mount, setMount] = React.useState(open);
  const [show, setShow] = React.useState(false);
  const [sel, setSel] = React.useState(null);
  const [ageAt, setAgeAt] = React.useState((persona && persona.age + 2) || 50);
  const [amount, setAmount] = React.useState("");
  const [note, setNote] = React.useState("");
  const [done, setDone] = React.useState(false);
  React.useEffect(() => {
    if (open) { setMount(true); setSel(null); setAgeAt((persona && persona.age + 2) || 50); setAmount(""); setNote(""); setDone(false); requestAnimationFrame(() => requestAnimationFrame(() => setShow(true))); }
    else { setShow(false); const t = setTimeout(() => setMount(false), 300); return () => clearTimeout(t); }
  }, [open]);
  React.useEffect(() => {
    if (!open) return; const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [open, onClose]);
  if (!mount) return null;
  const cat = sel != null ? EVENT_CATALOG[sel] : null;
  // amount / complementary fields adapt to the event nature
  const amountTypes = { property: "Estimated price (CHF)", windfall: "Expected amount (CHF)", work: "New annual income (CHF)", save: "Monthly saving (CHF)" };
  const noteHints = { property: "Where? Primary residence or second home?", windfall: "Source (inheritance, sale, bonus)?", work: "New role or self-employed?", family: "Which child, and the cost?", divorce: "Anything we should account for?", retire: "Desired lifestyle / monthly target?", move: "Destination country?", save: "What's the sabbatical for?" };
  const showAmount = cat && amountTypes[cat.type];
  const yr = 2025 + (ageAt - (persona ? persona.age : 0));
  const confirm = () => {
    const evt = { id: "u" + Date.now(), type: cat.type, t: cat.t, age: ageAt, age0: ageAt, yr: String(yr), state: "next", amt: amount ? "CHF " + Number(amount).toLocaleString("de-CH").replace(/,/g, "\u2019") : null, note: note || null };
    window.__ppExtraEvents = window.__ppExtraEvents || {};
    window.__ppExtraEvents[persona.id] = [...(window.__ppExtraEvents[persona.id] || []), evt];
    window.dispatchEvent(new CustomEvent("ppevent", { detail: { personaId: persona.id } }));
    try { localStorage.setItem("pp_events", JSON.stringify(window.__ppExtraEvents)); } catch (e) {}
    setDone(true); toast && toast(cat.t + " declared, your plan re-projected");
  };
  return (
    <div className={"ppm-modal-scrim" + (show ? " in" : "")} onClick={onClose}>
      <div className="ppm-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Declare a life event">
        <div className="ppm-modal-head">
          <span className="ppm-modal-ic"><i className="ri-calendar-event-line" /></span>
          <div className="tx"><h3>Declare a life event</h3><p>Tell us the type, when it happens and any amount, your plan, score and strategy re-project instantly.</p></div>
          <button className="ppm-modal-x" onClick={onClose} aria-label="Close"><i className="ri-close-line" /></button>
        </div>
        <div className="ppm-modal-bd">
          {!done ? (
            <>
              <div className="ppm-tline-add" style={{ background: "var(--bg-page)", border: 0, padding: 0 }}>
                <div className="lbl">Type of event</div>
                <div className="ppm-tline-cats">
                  {EVENT_CATALOG.map((c, i) => (
                    <button key={i} className={"ppm-tline-cat" + (sel === i ? " on" : "")} onClick={() => setSel(i)}
                      style={sel === i ? { borderColor: "var(--brand-orange)", color: "var(--brand-orange-600)", background: "var(--brand-orange-50)" } : null}>
                      <i className={c.icon} />{c.t}
                    </button>
                  ))}
                </div>
              </div>
              <div className="ppm-grid2" style={{ marginTop: 16 }}>
                <div className="ppm-field">
                  <label>When? (your age, year {yr})</label>
                  <div className="ppm-agestep">
                    <button onClick={() => setAgeAt((a) => Math.max(persona.age, a - 1))} aria-label="Earlier"><i className="ri-subtract-line" /></button>
                    <span className="v">age {ageAt}</span>
                    <button onClick={() => setAgeAt((a) => Math.min(90, a + 1))} aria-label="Later"><i className="ri-add-line" /></button>
                  </div>
                </div>
                {showAmount && (
                  <div className="ppm-field">
                    <label>{amountTypes[cat.type]}</label>
                    <input className="ppm-input" type="number" inputMode="numeric" value={amount} placeholder="0" onChange={(e) => setAmount(e.target.value)} />
                  </div>
                )}
              </div>
              <div className="ppm-field" style={{ marginTop: 14 }}>
                <label>Complementary info{cat ? " · " + (noteHints[cat.type] || "anything useful") : ""}</label>
                <input className="ppm-input" value={note} placeholder={cat ? (noteHints[cat.type] || "Optional details") : "Pick an event type first"} onChange={(e) => setNote(e.target.value)} disabled={!cat} />
              </div>
              <div className="ppm-modal-foot">
                <a className="ppm-foot-link" onClick={() => { onClose(); window.__ppOpenConsult && window.__ppOpenConsult(); }}><i className="ri-user-voice-line" />Talk it through with a consultant</a>
                <button className="pp-btn pp-btn-brand pp-btn-sm" disabled={sel == null} onClick={confirm}><i className="ri-check-line" />Declare &amp; re-project</button>
              </div>
            </>
          ) : (
            <div className="ppm-success">
              <div className="ppm-success-ic"><i className="ri-checkbox-circle-fill" /></div>
              <h4>Added to your living plan</h4>
              <p><b>{cat.t}</b> at age {ageAt} (year {yr}){amount ? " · CHF " + Number(amount).toLocaleString("de-CH").replace(/,/g, "\u2019") : ""} is now on your timeline. Your plan score, projection and recommended strategy have been updated.</p>
              <button className="pp-btn pp-btn-brand pp-btn-sm" style={{ marginTop: 6 }} onClick={onClose}><i className="ri-check-line" />See my updated plan</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
