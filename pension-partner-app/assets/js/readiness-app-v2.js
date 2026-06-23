/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, V2 "Readiness report"  (v2.jsx)  · v0.2
   Persona-driven single-scroll report. Reads the ACTIVE persona from
   window.PP_PERSONAS and composes: readiness hero, sub-score panel,
   plans compare, projection, KPIs, journey, ranked advisories,
   lump-vs-annuity, Edit & Simulate, life-event calendar, divorce,
   improve-docs, education, handoff. window.ReadinessApp
   ════════════════════════════════════════════════════════════════ */
const V2D = window.PP_DATA;
const V2 = window.PP_DATA.v2;
const RP = window.PP_PERSONAS;
const ENG = window.PP_ENGINE;

/* ── small helpers ─────────────────────────────────────────────── */
function BrandMark({ size = 30 }) {
  return (
    <span className="pp-brand-mark" style={{ width: size, height: size, borderRadius: size * 0.27 }}>
      <svg viewBox="0 0 48 48" style={{ width: size * 0.6, height: size * 0.6 }}>
        <path d="M24 12l-9 15h7l-3 9 9-15h-7l3-9z" fill="#fff" />
      </svg>
    </span>
  );
}

function EffortDots({ n }) {
  return (
    <span className="ppv2-effort">
      <span className="dots">{[1, 2, 3].map((i) => <i key={i} className={i <= n ? "on" : ""} />)}</span>
      {["", "Low effort", "Medium effort", "Higher effort"][n]}
    </span>
  );
}

/* ── readiness gauge ring ──────────────────────────────────────── */
function Gauge({ score }) {
  const [run, setRun] = React.useState(false);
  React.useEffect(() => { const id = requestAnimationFrame(() => requestAnimationFrame(() => setRun(true))); return () => cancelAnimationFrame(id); }, []);
  const R = 74, C = 2 * Math.PI * R;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <div className="ppv2-gauge">
      <svg viewBox="0 0 168 168">
        <circle cx="84" cy="84" r={R} fill="none" stroke="rgba(255,255,255,.14)" strokeWidth="13" />
        <circle cx="84" cy="84" r={R} fill="none" stroke="url(#ppv2g)" strokeWidth="13" strokeLinecap="round"
          strokeDasharray={C} strokeDashoffset={run ? C * (1 - pct) : C}
          style={{ transition: "stroke-dashoffset 1.3s cubic-bezier(.2,0,0,1)" }} />
        <defs>
          <linearGradient id="ppv2g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#6BE3A0" />
            <stop offset="1" stopColor="#1F8A5B" />
          </linearGradient>
        </defs>
      </svg>
      <div className="ppv2-gauge-c">
        <div className="n"><CountUp end={score} run={run} /><small>%</small></div>
        <div className="l">On track</div>
      </div>
    </div>
  );
}

/* ── net-worth projection chart ────────────────────────────────── */
function ProjectionChart({ proj }) {
  const W = 580, H = 250, padL = 50, padR = 12, padT = 12, padB = 30;
  const x0 = padL, x1 = W - padR, y0 = padT, y1 = H - padB;
  const sx = (a) => x0 + ((a - proj.startAge) / (proj.endAge - proj.startAge)) * (x1 - x0);
  const sy = (v) => y1 - (v / proj.yMax) * (y1 - y0);
  const pts = (arr) => arr.map(([a, v]) => `${sx(a).toFixed(1)},${sy(v).toFixed(1)}`).join(" ");
  const band = "M " + proj.bandHi.map(([a, v]) => `${sx(a).toFixed(1)},${sy(v).toFixed(1)}`).join(" L ")
    + " L " + [...proj.bandLo].reverse().map(([a, v]) => `${sx(a).toFixed(1)},${sy(v).toFixed(1)}`).join(" L ") + " Z";
  const fmt = (v) => v >= 1000000 ? (v / 1000000).toFixed(v % 1000000 ? 1 : 0) + "m" : Math.round(v / 1000) + "k";
  const retX = sx(proj.retireAge), peakY = sy(proj.peak.value);
  const labels = [proj.startAge, Math.round((proj.startAge + proj.retireAge) / 2), proj.retireAge, Math.round((proj.retireAge + proj.endAge) / 2), proj.endAge];
  return (
    <div className="ppv2-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Projected pension capital over time">
        {proj.yTicks.map((t) => (
          <g key={t}>
            <line x1={x0} y1={sy(t)} x2={x1} y2={sy(t)} stroke="var(--line-2)" strokeWidth="1" />
            <text x={x0 - 8} y={sy(t) + 3.5} textAnchor="end" fontSize="10" fontWeight="600" fill="var(--fg-4)">{fmt(t)}</text>
          </g>
        ))}
        <line x1={retX} y1={y0} x2={retX} y2={y1} stroke="var(--brand-orange-stroke)" strokeWidth="1.5" strokeDasharray="3 3" />
        <text x={retX} y={y0 - 1} textAnchor="middle" fontSize="9.5" fontWeight="700" fill="var(--brand-orange-600)">RETIRE · {proj.retireAge}</text>
        <path d={band} fill="rgba(250,91,53,.13)" />
        <polyline points={pts(proj.current)} fill="none" stroke="var(--fg-disabled)" strokeWidth="2" strokeDasharray="5 4" strokeLinejoin="round" />
        <polyline points={pts(proj.planned)} fill="none" stroke="var(--brand-orange)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={retX} cy={peakY} r="5" fill="var(--brand-orange)" stroke="#fff" strokeWidth="2" />
        {labels.map((a) => (
          <text key={a} x={sx(a)} y={H - 8} textAnchor="middle" fontSize="10" fontWeight="600" fill="var(--fg-4)">{a}</text>
        ))}
      </svg>
      <div className="ppv2-chart-legend">
        <span><span className="sw" style={{ background: "var(--brand-orange)" }} />Planned (with levers)</span>
        <span><span className="sw" style={{ background: "var(--fg-disabled)" }} />Current trajectory</span>
        <span><span className="sw band" />Confidence range</span>
      </div>
    </div>
  );
}

/* ── section wrapper ───────────────────────────────────────────── */
function Sec({ title, sub, children, className = "" }) {
  return (
    <section className={"ppv2-sec ppv2-rise " + className}>
      {title && (
        <div className="ppv2-sec-h">
          <h2>{title}</h2>
          {sub && <div className="s">{sub}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/* ── Report sections (Yvan spec §5) ────────────────────────────── */
function PortraitCard({ P }) {
  return (
    <div className="ppv2-card ppv2-portrait">
      <div className="ppv2-portrait-mark"><i className="ri-sparkling-fill" /></div>
      <p className="ppv2-sensitive">{P.report.portrait}</p>
    </div>
  );
}

function Donut({ data, size = 132 }) {
  const r = size / 2 - 12, C = 2 * Math.PI * r, cx = size / 2;
  let off = 0;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} style={{ width: size, height: size, transform: "rotate(-90deg)", flex: "0 0 auto" }}>
      {data.map((d, i) => {
        const len = (d.pct / 100) * C, dash = `${len} ${C - len}`, el = (
          <circle key={i} cx={cx} cy={cx} r={r} fill="none" stroke={d.color} strokeWidth="14" strokeDasharray={dash} strokeDashoffset={-off} />
        );
        off += len; return el;
      })}
    </svg>
  );
}

function IncomeWealth({ P }) {
  const R = P.report;
  const wealthTotal = R.wealthDims.reduce((s, d) => s + d.s, 0);
  const ring = { r: 52, c: 2 * Math.PI * 52 };
  const [editing, setEditing] = React.useState(false);
  const [info, setInfo] = React.useState(false);
  const [sources, setSources] = React.useState(R.incomeSources);
  React.useEffect(() => { setSources(R.incomeSources); setEditing(false); }, [P.id]);
  const total = sources.reduce((s, d) => s + (+d.pct || 0), 0);
  const setPct = (i, v) => setSources((prev) => prev.map((d, j) => j === i ? { ...d, pct: Math.max(0, Math.min(100, Math.round(+v || 0))) } : d));
  return (
    <div className="ppv2-grid2">
      <div className="ppv2-card">
        <div className="ppv2-mini-h">Income sources
          <span className="ppv2-card-tools">
            <button className="ppv2-itool" title="How is this estimated?" onClick={() => setInfo((v) => !v)}><i className="ri-information-line" /></button>
            <button className={"ppv2-itool" + (editing ? " on" : "")} title={editing ? "Done editing" : "Edit income sources"} onClick={() => setEditing((v) => !v)}><i className={editing ? "ri-check-line" : "ri-pencil-line"} /></button>
          </span>
        </div>
        {info && <div className="ppv2-infonote"><i className="ri-information-line" />Estimated from the salary, pension and investment figures in the documents you shared. Edit any share to model a different mix, the breakdown re-balances live.</div>}
        <div className="ppv2-incwrap">
          <Donut data={sources} />
          <div className="ppv2-leg">
            {sources.map((d, i) => (
              <div className="ppv2-leg-row" key={i}>
                <span className="dot" style={{ background: d.color }} />
                <span className="nm">{d.l}</span>
                {editing
                  ? <span className="ppv2-leg-edit"><input type="number" min="0" max="100" value={d.pct} onChange={(e) => setPct(i, e.target.value)} /><span className="su">%</span></span>
                  : <span className="pc">{d.pct}%</span>}
              </div>
            ))}
            {editing && <div className={"ppv2-leg-total" + (total === 100 ? " ok" : " warn")}><i className={total === 100 ? "ri-checkbox-circle-line" : "ri-error-warning-line"} />{total === 100 ? "Balanced at 100%" : "Totals " + total + "% · aim for 100%"}</div>}
          </div>
        </div>
      </div>
      <div className="ppv2-card">
        <div className="ppv2-mini-h">Wealth health <span className="ppv2-mini-sub">5 dimensions · /20</span></div>
        <div className="ppv2-wealth">
          <div className="ppv2-wring">
            <svg viewBox="0 0 132 132" style={{ width: 116, height: 116, transform: "rotate(-90deg)" }}>
              <circle cx="66" cy="66" r={ring.r} fill="none" stroke="var(--bg-subtle)" strokeWidth="11" />
              <circle cx="66" cy="66" r={ring.r} fill="none" stroke="var(--ontrack)" strokeWidth="11" strokeLinecap="round" strokeDasharray={ring.c} strokeDashoffset={ring.c * (1 - wealthTotal / 100)} />
            </svg>
            <div className="ppv2-wring-c"><div className="n">{wealthTotal}</div><div className="l">/ 100</div></div>
          </div>
          <div className="ppv2-wdims">
            {R.wealthDims.map((d, i) => (
              <div className="ppv2-wdim" key={i}>
                <span className="l">{d.l}</span>
                <span className="tr"><span className="fl" style={{ width: (d.s / 20 * 100) + "%", background: d.s >= 14 ? "var(--ontrack)" : d.s >= 9 ? "var(--gap)" : "var(--loss)" }} /></span>
                <span className="v">{d.s}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function DeductionsTax({ P }) {
  const R = P.report, max = Math.max(...R.deductions.map((d) => d.amt), 1);
  return (
    <div className="ppv2-grid2">
      <div className="ppv2-card">
        <div className="ppv2-mini-h">Deductions taken</div>
        <div className="ppv2-ded">
          {R.deductions.map((d, i) => (
            <div className="ppv2-ded-row" key={i}>
              <span className="l">{d.l}</span>
              <span className="tr"><span className="fl" style={{ width: (d.amt / max * 100) + "%" }} /></span>
              <span className="v ppv2-sensitive">{d.amt ? V2D.chf(d.amt) : ", "}</span>
            </div>
          ))}
        </div>
        <button className="ppv2-ded-cta" onClick={() => window.__ppOpenTax && window.__ppOpenTax()}>
          <span className="ic"><i className="ri-add-circle-line" /></span>
          <span className="tx">
            <span className="t">Declare more deductions</span>
            <span className="d">3a, pillar buy-ins, childcare, training, health, the more we see, the more we can optimise.</span>
          </span>
          <i className="ri-arrow-right-line ar" />
        </button>
      </div>
      <div className="ppv2-card">
        <div className="ppv2-mini-h">Tax profile</div>
        <table className="ppv2-taxtable">
          <tbody>
            {R.taxProfile.map((row, i) => (
              <tr key={i}><td>{row[0]}</td><td className="ppv2-sensitive">{row[1]}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Insights({ P }) {
  return (
    <div className="ppv2-insights">
      {P.report.insights.map((n, i) => (
        <div className={"ppv2-insight " + n.kind} key={i}>
          <span className="ic"><i className={n.icon} /></span>
          <div className="bd"><div className="t">{n.t}</div><div className="d">{n.d}</div></div>
        </div>
      ))}
    </div>
  );
}

function LombardCard({ P, toast }) {
  const L = P.report.lombard;
  if (!L) return null;
  return (
    <div className="ppv2-card ppv2-lombard">
      <div className="ppv2-lombard-h">
        <span className="tag"><i className="ri-bank-card-line" />Swissquote · Lombard</span>
        <InfoAdvice kind="advice" />
      </div>
      <h4>Fund a pension-fund buy-in with a Lombard loan</h4>
      <p>Borrow against your portfolio to make a <b>{V2D.chf(L.buyback)}</b> buy-in now, deduct it this tax year, and repay from cashflow, keeping your invested capital working.</p>
      <div className="ppv2-lombard-math">
        <div className="ppv2-mini-h">How the numbers work</div>
        <div className="r"><span>Buy-in funded</span><b className="ppv2-sensitive">{V2D.chf(L.buyback)}</b></div>
        <div className="r"><span>Lombard rate (≈ market + 1.5%)</span><b>{L.rate}% p.a.</b></div>
        <div className="r"><span>Marginal tax rate</span><b>~{L.marginal}%</b></div>
        <div className="r tot"><span>Tax saved now</span><b className="ppv2-sensitive">{V2D.chf(L.taxSaved)}</b></div>
        {L.pension > 0 && <div className="r tot"><span>Future pension uplift</span><b className="ppv2-sensitive">+{V2D.chf(L.pension)}/mo</b></div>}
      </div>
      <button className="pp-btn pp-btn-brand pp-btn-sm" style={{ marginTop: 14 }} onClick={() => toast("Opening Swissquote Lombard…")}><i className="ri-external-link-line" />Explore a Lombard loan</button>
    </div>
  );
}

function RealEstateEnrich({ P, toast }) {
  const seed = P.report.realEstate.length ? P.report.realEstate : [{ name: "Property", fiscal: 0, mortgage: 0 }];
  const [rows, setRows] = React.useState(seed.map((r) => ({ ...r, market: r.fiscal || "" })));
  const [done, setDone] = React.useState(false);
  React.useEffect(() => { const s = P.report.realEstate.length ? P.report.realEstate : [{ name: "Property", fiscal: 0, mortgage: 0 }]; setRows(s.map((r) => ({ ...r, market: r.fiscal || "" }))); setDone(false); }, [P.id]);
  const set = (i, k, v) => setRows((p) => p.map((r, j) => j === i ? { ...r, [k]: v } : r));
  const add = () => setRows((p) => [...p, { name: "Property " + (p.length + 1), fiscal: 0, mortgage: 0, market: "" }]);
  const totMarket = rows.reduce((s, r) => s + (+r.market || 0), 0);
  const totMort = rows.reduce((s, r) => s + (+r.mortgage || 0), 0);
  const totFiscal = rows.reduce((s, r) => s + (+r.fiscal || 0), 0);
  const equity = totMarket - totMort, uplift = totMarket - totFiscal;
  return (
    <div className="ppv2-card">
      <div className="ppv2-mini-h">Real estate <span className="ppv2-mini-sub">enter today's market value</span></div>
      <div className="ppv2-re">
        {rows.map((r, i) => (
          <div className="ppv2-re-row" key={i}>
            <input className="ppv2-re-name" value={r.name} onChange={(e) => set(i, "name", e.target.value)} />
            <div className="ppv2-re-inps">
              <label>Market value<input type="number" value={r.market} placeholder="0" onChange={(e) => { set(i, "market", e.target.value); setDone(false); }} /></label>
              <label>Mortgage<input type="number" value={r.mortgage} placeholder="0" onChange={(e) => { set(i, "mortgage", e.target.value); setDone(false); }} /></label>
            </div>
          </div>
        ))}
        <div className="ppv2-re-actions">
          <button className="ppv2-re-add" onClick={add}><i className="ri-add-line" />Add a property</button>
          <button className="pp-btn pp-btn-brand pp-btn-sm" onClick={() => { setDone(true); toast("Real estate updated in your portrait"); }}><i className="ri-arrow-right-line" />Apply</button>
        </div>
        {done && (
          <div className="ppv2-re-result">
            <div className="r"><span>Total market value</span><b className="ppv2-sensitive">{V2D.chf(totMarket)}</b></div>
            <div className="r"><span>Net equity (− mortgages)</span><b className="ppv2-sensitive">{V2D.chf(equity)}</b></div>
            {totFiscal > 0 && <div className="r"><span>Uplift vs fiscal value</span><b className="ppv2-sensitive" style={{ color: uplift >= 0 ? "var(--ontrack)" : "var(--loss)" }}>{uplift >= 0 ? "+" : "−"}{V2D.chf(Math.abs(uplift))}</b></div>}
          </div>
        )}
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   ROOT
   ════════════════════════════════════════════════════════════════ */
function ReadinessApp({ go, toast, lang, personaId, setPersonaId, activePlan, setPlan, openTax }) {
  const [privacy, setPrivacy] = React.useState(false);
  const [added, setAdded] = React.useState({});
  const P = RP[personaId] || RP.caroline;
  const R = P.readiness;
  const chf = V2D.chf;

  const curLevel = V2.levels.find((l) => R.score >= l.lo && R.score < l.hi) || V2.levels[0];
  const levers = P.advisories.slice(0, 4);
  const activeSub = (P.plans.find((p) => p.id === activePlan) || {}).sub || P.subScores;
  const proj = P.projection;

  return (
    <div className={"ppv2-body ppv2-blur" + (privacy ? " is-on" : "")}>
      <div className="ppv2-wrap">

        {/* toolbar */}
        <div className="ppv2-toolbar ppv2-rise">
          <div className="ppv2-toolbar-l">
            <div className="k"><i className="ri-shield-star-line" /> Retirement readiness report</div>
            <h1>{P.kind === "couple" ? "Good evening, " + P.first + "." : "Good evening, " + P.first + "."}</h1>
          </div>
          <div className="ppv2-toolbar-r">
            <PersonaSwitcher active={personaId} onChange={setPersonaId} />
            <button className="ppv2-tbtn" onClick={openTax}><i className="ri-file-add-line" />Add document</button>
            <button className={"ppv2-tbtn" + (privacy ? " on" : "")} onClick={() => setPrivacy((p) => !p)}>
              <i className={privacy ? "ri-eye-off-line" : "ri-eye-line"} />{privacy ? "Hidden" : "Privacy"}
            </button>
            <button className="ppv2-tbtn" onClick={() => window.print()}><i className="ri-printer-line" />Export</button>
          </div>
        </div>

        {/* HERO */}
        <div className="ppv2-hero ppv2-rise" key={personaId}>
          <div className="ppv2-hero-top">
            <Gauge score={R.score} key={personaId} />
            <div className="ppv2-hero-id">
              <div className="lbl">{P.flag} {P.name} · {P.status}</div>
              <h2>{R.verdict}</h2>
              <p>{R.sub}</p>
            </div>
          </div>

          <div className="ppv2-uplift">
            <div className="seg"><span className="k">Today's plan</span><span className="v ppv2-sensitive">{chf(R.today)}</span></div>
            <i className="ri-arrow-right-line arrow" />
            <div className="seg"><span className="k">With your levers</span><span className="v tgt ppv2-sensitive">{chf(R.planned)}</span></div>
            <span className="pct"><i className="ri-arrow-up-line" />+{R.upliftPct}%</span>
          </div>

          <div className="ppv2-scen">
            {P.scenarios.map((s) => (
              <div className={"ppv2-scen-c" + (s.hl ? " hl" : "")} key={s.age}>
                <div className="ppv2-scen-age">Retire at {s.age}<span className={"tag " + s.tag}>{s.tagTxt}</span></div>
                <div className="inc ppv2-sensitive">{s.inc}<span style={{ font: "600 12px/1 var(--font-body)", color: "rgba(255,255,255,.5)" }}> /mo</span></div>
                <div className="pctx">{s.pct}</div>
              </div>
            ))}
          </div>
        </div>

        {/* AI PORTRAIT */}
        <Sec title="Your portrait" sub="Written from the documents you confirmed">
          <PortraitCard P={P} />
        </Sec>

        {/* ADVISOR'S GLANCE — live insights on the figures visible here */}
        {window.AdvisorGlance ? <div className="ppv2-sec ppv2-rise"><window.AdvisorGlance screen="readiness report" persona={P} /></div> : null}

        {/* PLAN SCORE, simple readiness % above; sub-scores breakdown here */}
        <Sec title="What drives your score" sub="Plan Score = weighted sub-scores (§25)">
          <div className="ppv2-card"><SubScorePanel sub={activeSub} /></div>
        </Sec>

        {/* PLANS COMPARE */}
        <Sec title="Choose your strategy" sub="2–3 plans · compare and switch anytime">
          <PlansCompare persona={P} activePlan={activePlan} onPick={(id) => { setPlan(id); toast("Active plan: " + (P.plans.find((x) => x.id === id) || {}).name + ", calendar & score re-baselined"); }} />
        </Sec>

        {/* LEVELS */}
        <Sec title="Your readiness level" sub={`You're "${curLevel.name}"`}>
          <div className="ppv2-card">
            <div className="ppv2-levels">
              {V2.levels.map((l) => (
                <div className={"ppv2-level " + l.id + (l.id === curLevel.id ? " is-current" : "")} key={l.id} style={{ color: l.id === curLevel.id ? undefined : "transparent" }}>
                  {l.id === curLevel.id && <span className="you">You · {R.score}</span>}
                  <div className="nm">{l.name}</div>
                  <div className="rg">{l.range}</div>
                </div>
              ))}
            </div>
            <div className="ppv2-levelup">
              <div className="ppv2-levelup-l">
                <div className="k">Single biggest mover</div>
                <div className="v"><em>{ENG.biggestMover(activeSub).label}</em><br />{ENG.biggestMover(activeSub).weight}% of your score</div>
              </div>
              <div className="ppv2-levelup-steps">
                {levers.slice(0, 2).map((s, i) => (
                  <div className="ppv2-lustep" key={i}>
                    <span className="b">{i + 1}</span>
                    <div className="bd">
                      <div className="t">{s.title}<InfoAdvice kind={s.label} /></div>
                      <div className="d">{s.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Sec>

        {/* PROJECTION */}
        <Sec title="Projected pension capital" sub="If you continue vs. if you act">
          <div className="ppv2-card">
            <div className="ppv2-chart-wrap">
              <ProjectionChart proj={proj} />
              <div className="ppv2-chart-side">
                <div className="ppv2-stat">
                  <div className="k">Projected fund at {proj.retireAge}</div>
                  <div className="v gain ppv2-sensitive">{chf(proj.peak.value)}</div>
                  <div className="d">pension capital, levers applied</div>
                </div>
                <div className="ppv2-stat">
                  <div className="k">Monthly pension then</div>
                  <div className="v ppv2-sensitive">{chf(R.planned)}</div>
                  <div className="d">vs {chf(R.today)} on today's plan</div>
                </div>
                <span className="ppv2-conf"><i className="ri-shield-check-line" />{proj.confidence}</span>
              </div>
            </div>
          </div>
        </Sec>

        {/* KPI */}
        <Sec title="The numbers behind it">
          <div className="ppv2-kpis">
            {P.kpis.map((k, i) => (
              <div className="ppv2-kpi" key={i}>
                <div className="k">{k.lbl}</div>
                <div className="v ppv2-sensitive">{k.val}</div>
                <div className="s">{k.sub}</div>
                <span className={"ppv2-tag " + k.tone}>{k.tag}</span>
              </div>
            ))}
          </div>
        </Sec>

        {/* INCOME + WEALTH */}
        <Sec title="Income & wealth health" sub="Where it comes from · 5-dimension score">
          <IncomeWealth P={P} />
        </Sec>

        {/* DEDUCTIONS + TAX */}
        <Sec title="Deductions & tax profile">
          <DeductionsTax P={P} />
        </Sec>

        {/* JOURNEY */}
        <Sec title="Your retirement journey" sub={`${P.journey.years} years to go`}>
          <div className="ppv2-card">
            <div className="ppv2-journey-bar">
              <div className="ppv2-journey-fill" style={{ width: P.journey.progressPct + "%" }} />
              <div className="ppv2-journey-knob" style={{ left: P.journey.progressPct + "%" }}>
                <span className="tip">{P.journey.progressPct}% there</span>
              </div>
            </div>
            <div className="ppv2-journey-ends"><span>Now · age {P.journey.nowAge}</span><span>Retire · age {P.journey.retireAge}</span></div>
            <div className="ppv2-journey-rows">
              <div className="ppv2-jrow">
                <span className="l">Monthly contribution</span>
                <span className="r"><span className="now ppv2-sensitive">{chf(P.journey.contribNow)}</span><i className="ri-arrow-right-line arr" /><span className="fut ppv2-sensitive">{chf(P.journey.contribPlanned)}</span></span>
              </div>
              <div className="ppv2-jrow">
                <span className="l">Total contributions</span>
                <span className="single ppv2-sensitive">{chf(P.journey.totalContrib)}</span>
              </div>
              <div className="ppv2-jrow">
                <span className="l">Projected retirement fund</span>
                <span className="single ppv2-sensitive">{chf(P.journey.projectedFund)}</span>
              </div>
            </div>
          </div>
        </Sec>

        {/* ADVISORIES */}
        <Sec title="Suggested actions" sub="Products matched to your figures by Pension AI">
          {window.ProductRecs ? <div className="ppv2-card" style={{ marginBottom: 16 }}><window.ProductRecs persona={P} /></div> : null}
          <div className="ppv2-actions">
            {levers.map((lv) => (
              <div className="ppv2-act" key={lv.rank}>
                <div className="ppv2-act-top">
                  <span className="ppv2-act-rank">{lv.rank}</span>
                  <div className="ppv2-act-id">
                    <div className="t"><h4>{lv.title}</h4><InfoAdvice kind={lv.label} /></div>
                    <p>{lv.desc}</p>
                  </div>
                </div>
                <div className="ppv2-act-impact">
                  <span className="ppv2-pill">
                    <span className="v">{lv.impact > 0 ? "+" + chf(lv.impact) : lv.impactNote}</span>
                    {lv.impact > 0 && <span className="u">/mo</span>}
                  </span>
                  <EffortDots n={lv.effort} />
                </div>
                <div className="ppv2-act-foot">
                  <ShowMath steps={lv.math} rule={lv.rule} />
                </div>
              </div>
            ))}
          </div>
        </Sec>

        {/* LOMBARD ACTION */}
        {P.report.lombard && (
          <Sec title="A Swissquote move" sub="Lombard loan → pension-fund buy-in">
            <LombardCard P={P} toast={toast} />
          </Sec>
        )}

        {/* EDIT & SIMULATE */}
        <Sec title="Edit & Simulate, property" sub="Live GO / AMBER / KO, with what would flip it">
          <div className="ppv2-card"><EditSimulate persona={P} toast={toast} /></div>
        </Sec>

        {/* LIFE-EVENT CALENDAR */}
        <Sec title="Your life-event calendar" sub="Drag to re-date, the plan re-projects live">
          <div className="ppv2-card"><LifeEventCalendar persona={P} /></div>
        </Sec>

        {/* DIVORCE */}
        <Sec title="Life event, separation" sub="Forks the household into two plans">
          <div className="ppv2-card"><DivorcePanel persona={P} toast={toast} /></div>
        </Sec>

        {/* KEY DECISION, lump sum vs annuity */}
        <Sec title="A key retirement choice" sub="Lump sum vs lifelong annuity">
          <div className="ppv2-card">
            <p className="ppv2-decide-intro">{P.lumpAnnuity.intro}</p>
            <div className="ppv2-opts">
              {P.lumpAnnuity.options.map((o) => (
                <div className={"ppv2-opt" + (o.rec ? " rec" : "")} key={o.id}>
                  {o.rec && <span className="ppv2-opt-flag"><i className="ri-bookmark-fill" style={{ fontSize: 12 }} />Often preferred</span>}
                  <div className="ppv2-opt-head">
                    <span className="ppv2-opt-ic"><i className={o.icon} /></span>
                    <div className="ti"><h4>{o.t}</h4><div className="sub">{o.sub}</div></div>
                  </div>
                  <div className="ppv2-opt-fig">
                    <div className="v ppv2-sensitive">{o.figure}</div>
                    <div className="l">{o.figureLabel}</div>
                  </div>
                  <ul className="ppv2-opt-pts">
                    {o.points.map((p, i) => <li key={i}><i className="ri-checkbox-circle-line" />{p}</li>)}
                  </ul>
                </div>
              ))}
            </div>
            <div className="ppv2-decide-note"><i className="ri-information-line" /><span>{P.lumpAnnuity.note}<span style={{ marginLeft: 6 }}><InfoAdvice kind="info" /></span></span></div>
          </div>
        </Sec>

        {/* KEY INSIGHTS */}
        <Sec title="Key insights" sub="Opportunities, risks & things to know">
          <Insights P={P} />
        </Sec>

        {/* IMPROVE */}
        <Sec title="Sharpen your analysis" sub="Add a document, tighten the numbers">
          <RealEstateEnrich P={P} toast={toast} />
          <div className="ppv2-improve" style={{ marginTop: 14 }}>
            {P.improve.map((d) => {
              const on = !!added[d.key];
              return (
                <div className={"ppv2-imp" + (on ? " is-added" : "")} key={d.key}
                  onClick={() => { if (!on) { setAdded((a) => ({ ...a, [d.key]: true })); toast(d.t + " added, recalculating"); } }}>
                  <span className="ppv2-imp-ic"><i className={on ? "ri-check-line" : d.icon} /></span>
                  <div className="ppv2-imp-bd"><div className="t">{d.t}</div><div className="d">{d.d}</div></div>
                  <div className="ppv2-imp-r">
                    {on ? <span className="ppv2-imp-add" style={{ color: "var(--ontrack)" }}>Added</span> : <>
                      <span className={"ppv2-imp-impact " + d.impact}>{d.impact} impact</span>
                      <span className="x">{d.impactTxt}</span>
                    </>}
                  </div>
                </div>
              );
            })}
          </div>
        </Sec>

        {/* EDUCATION */}
        <Sec title="Want to learn more?" sub="Short reads, no jargon">
          <div className="ppv2-edu">
            {RP.education.map((e, i) => (
              <div className="ppv2-educard" key={i} onClick={() => toast("Opening: " + e.t)}>
                <div className="ppv2-edu-thumb"><i className={e.ic} /></div>
                <div className="ppv2-edu-bd">
                  <div className="ppv2-edu-lvl">{e.level}</div>
                  <div className="t">{e.t}</div>
                  <div className="ppv2-edu-meta">{e.a}<span className="dot" />{e.min} min read</div>
                </div>
              </div>
            ))}
          </div>
        </Sec>

        {/* HANDOFF */}
        <Sec>
          <div className="ppv2-handoff">
            <span className="ppv2-handoff-av"><i className="ri-user-heart-line" /></span>
            <div className="ppv2-handoff-bd">
              <h4>When it gets serious, a human steps in</h4>
              <p>Irreversible choices, capital vs annuity, divorce, cross-border, are routed to a Swissquote advisor with a brief already prepared from this report, so you never start from scratch.</p>
              <button className="pp-btn pp-btn-ghost pp-btn-sm" onClick={() => window.__ppOpenConsult && window.__ppOpenConsult()}><i className="ri-calendar-check-line" />Book a 30-min handoff</button>
            </div>
          </div>
        </Sec>

        {/* FOOTER */}
        <div className="ppv2-foot ppv2-rise">
          <span className="brand"><BrandMark size={24} /><span><b>Swissquote</b> Pension Partner · Readiness report</span></span>
          <p className="legal">For illustrative purposes only. Not financial, tax or investment advice. Figures are estimates derived from documents you confirmed. Swissquote Bank Ltd is regulated by FINMA. Capital at risk.</p>
        </div>

      </div>
    </div>
  );
}

Object.assign(window, { ReadinessApp, PortraitCard, IncomeWealth, DeductionsTax, Insights, LombardCard, RealEstateEnrich });
