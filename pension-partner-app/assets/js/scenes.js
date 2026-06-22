/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, scenes  (scenes.jsx)
   Onboarding (welcome/upload/confirm/gapfill) + work-scene
   conversations + monitoring home.
   ════════════════════════════════════════════════════════════════ */
const DA = window.PP_DATA;

/* sequential reveal with typing between items */
function useSequence(total, { gate = true, step = 720, typing = 540 } = {}) {
  const [count, setCount] = React.useState(0);
  const [isTyping, setTyping] = React.useState(false);
  React.useEffect(() => {
    if (!gate) return;
    let alive = true; const timers = [];
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setCount(total); return; }
    let t = 200;
    const run = (i) => {
      if (i >= total) return;
      timers.push(setTimeout(() => { if (alive) setTyping(true); }, t));
      t += typing;
      timers.push(setTimeout(() => { if (alive) { setTyping(false); setCount(i + 1); } }, t));
      t += step;
      run(i + 1);
    };
    run(0);
    return () => { alive = false; timers.forEach(clearTimeout); };
  }, [total, gate]);
  return { count, isTyping };
}

function Chips({ items }) {
  return React.createElement("div", { className: "pp-chips", style: { paddingLeft: "39px", marginTop: "2px" } },
    items.map((it, i) => React.createElement("button", { className: "pp-chip", key: i, onClick: it.onClick },
      it.icon && React.createElement("i", { className: it.icon }), it.label)));
}

/* ════════════════════════════════════════════════════════════════
   WELCOME
   ════════════════════════════════════════════════════════════════ */
function WelcomeScene({ t, go }) {
  return (
    React.createElement("div", { className: "pp-scene" },
      React.createElement("div", { className: "pp-center" },
        React.createElement("div", { className: "pp-welcome-split" },
        React.createElement("div", { className: "pp-welcome" },
          React.createElement("div", { className: "pp-welcome-mark" },
            React.createElement("svg", { viewBox: "0 0 48 48" }, React.createElement("path", { d: "M24 12l-9 15h7l-3 9 9-15h-7l3-9z", fill: "#fff" }))),
          React.createElement("div", { className: "pp-eyebrow", style: { marginBottom: "20px" } }, React.createElement("i", { className: "ri-shield-star-line" }), t.welcomeKicker),
          React.createElement("h1", null, t.welcomeH[0], React.createElement("br"), t.welcomeH[1], React.createElement("em", null, t.welcomeH[2])),
          React.createElement("p", { className: "lede" }, t.welcomeLede),
          React.createElement("div", { className: "pp-promise" },
            React.createElement("div", { className: "ic" }, React.createElement("i", { className: "ri-scales-3-line" })),
            React.createElement("p", { dangerouslySetInnerHTML: { __html: t.promise } })
          ),
          React.createElement("div", { className: "pp-welcome-cta" },
            React.createElement("button", { className: "pp-btn pp-btn-brand pp-btn-lg", onClick: () => window.__ppOpenMethod && window.__ppOpenMethod() },
              React.createElement("i", { className: "ri-upload-cloud-2-line" }), t.start),
            React.createElement("div", { className: "pp-login-row" },
              React.createElement("button", { className: "pp-btn pp-btn-dark pp-btn-lg", style: { flex: 1 }, onClick: () => window.__ppOpenLogin && window.__ppOpenLogin() },
                React.createElement("i", { className: "ri-login-circle-line" }), "Log in with Swissquote or Yuh"),
              React.createElement("button", { className: "pp-btn pp-btn-ghost pp-btn-lg", onClick: () => window.__ppOpenConsult && window.__ppOpenConsult() },
                React.createElement("i", { className: "ri-user-voice-line" }), "Talk to a consultant"))
          ),
          React.createElement("div", { className: "pp-welcome-trust" },
            React.createElement("span", null, React.createElement("i", { className: "ri-bank-line" }), "Swissquote · FINMA-regulated bank"),
            React.createElement("span", null, React.createElement("i", { className: "ri-lock-2-line" }), "revDPA · your data, your control"),
            React.createElement("span", null, React.createElement("i", { className: "ri-map-pin-line" }), "Hosted in Switzerland"),
            React.createElement("span", null, React.createElement("i", { className: "ri-global-line" }), "FR · DE · IT · EN")
          )
        ),
        React.createElement("div", { className: "pp-welcome-art" },
          React.createElement("img", { src: (window.__resources && window.__resources.heroRetire) || "assets/hero-retire.jpg", alt: "Retirement by the lake at golden hour" }),
          React.createElement("div", { className: "cap" },
            React.createElement("div", { className: "k" }, React.createElement("i", { className: "ri-sparkling-2-fill" }), "Your future, in focus"),
            React.createElement("div", { className: "d" }, "One upload. A clear plan for the retirement you're picturing.")))
        )
      )
    )
  );
}

/* ════════════════════════════════════════════════════════════════
   UPLOAD  (hero)
   ════════════════════════════════════════════════════════════════ */
function UploadScene({ go }) {
  // status per doc: empty | load | up | err
  const [st, setSt] = React.useState({ lpp: "empty", "3a": "empty", tax: "empty" });
  const [prog, setProg] = React.useState({ lpp: 0, "3a": 0, tax: 0 });
  const [drag, setDrag] = React.useState(false);
  const timers = React.useRef([]);
  React.useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const uploadOne = (key, willErr) => {
    setSt((s) => ({ ...s, [key]: "load" }));
    setProg((p) => ({ ...p, [key]: 0 }));
    let v = 0;
    const iv = setInterval(() => {
      v += 14 + Math.random() * 16;
      if (v >= 100) { v = 100; clearInterval(iv); setProg((p) => ({ ...p, [key]: 100 }));
        timers.current.push(setTimeout(() => setSt((s) => ({ ...s, [key]: willErr ? "err" : "up" })), 250));
      } else setProg((p) => ({ ...p, [key]: v }));
    }, 130);
    timers.current.push({ clearTimeout: () => clearInterval(iv) });
  };

  const startAll = () => { uploadOne("lpp", false); timers.current.push(setTimeout(() => uploadOne("3a", true), 500)); timers.current.push(setTimeout(() => uploadOne("tax", false), 1100)); };
  const anyUp = Object.values(st).some((x) => x === "up");

  const docStat = (key) => {
    const s = st[key];
    if (s === "up") return { cls: "is-up", d: "Read · ready to confirm", dcls: "ok", ic: "ri-checkbox-circle-fill", icls: "ok" };
    if (s === "load") return { cls: "is-load", d: "Reading…", dcls: "", ic: "", icls: "" };
    if (s === "err") return { cls: "is-err", d: "Couldn't read this scan", dcls: "err", ic: "ri-error-warning-fill", icls: "err" };
    return { cls: "", d: "Photo or PDF", dcls: "", ic: "", icls: "" };
  };

  return (
    React.createElement("div", { className: "pp-scene" },
      React.createElement("div", { className: "pp-center" },
        React.createElement("div", { className: "pp-onb" },
          React.createElement("div", { className: "pp-onb-head" },
            React.createElement("span", { className: "pp-eyebrow" }, React.createElement("i", { className: "ri-upload-cloud-2-line" }), "Step 1 · One upload"),
            React.createElement("h2", null, "Send your pension documents once"),
            React.createElement("p", null, "Drop in a photo or PDF and I'll read the numbers, you'll confirm every figure before it enters your plan. One document is enough to start.")
          ),
          React.createElement("div", { className: "pp-upload-grid" },
            React.createElement("div", {
              className: "pp-dropzone" + (drag ? " is-drag" : ""),
              onDragOver: (e) => { e.preventDefault(); setDrag(true); }, onDragLeave: () => setDrag(false),
              onDrop: (e) => { e.preventDefault(); setDrag(false); startAll(); }
            },
              React.createElement("div", { className: "pp-dropzone-ic" }, React.createElement("i", { className: "ri-upload-cloud-2-line" })),
              React.createElement("h3", null, "Drag your documents here"),
              React.createElement("p", null, "Pension-fund certificate, 3a statement, tax return, or anything you have. PDF, JPG, PNG, HEIC."),
              React.createElement("div", { className: "pp-drop-actions" },
                React.createElement("button", { className: "pp-btn pp-btn-brand", onClick: startAll }, React.createElement("i", { className: "ri-folder-open-line" }), "Browse files"),
                React.createElement("button", { className: "pp-btn pp-btn-ghost", onClick: startAll }, React.createElement("i", { className: "ri-camera-line" }), "Use camera"),
                React.createElement("button", { className: "pp-btn pp-btn-ghost", onClick: () => window.__ppOpenTax && window.__ppOpenTax() }, React.createElement("i", { className: "ri-file-shield-2-line" }), "Add tax statement")
              ),
              React.createElement("div", { className: "or" }, "Secure upload")
            ),
            React.createElement("div", { className: "pp-checklist" },
              React.createElement("h4", null, "Your starter checklist"),
              React.createElement("p", { className: "sub" }, "The three that unlock the most, but bring what you have."),
              DA.docs.map((d) => {
                const ds = docStat(d.key); const s = st[d.key];
                return React.createElement("div", { className: "pp-doc " + ds.cls, key: d.key },
                  React.createElement("div", { className: "pp-doc-ic" }, React.createElement("i", { className: s === "up" ? "ri-check-line" : s === "err" ? "ri-error-warning-line" : d.icon })),
                  React.createElement("div", { className: "pp-doc-bd" },
                    React.createElement("div", { className: "t" }, d.t),
                    React.createElement("div", { className: "d " + ds.dcls }, s === "err" ? "Couldn't read this scan" : s === "up" ? "Read · ready to confirm" : s === "load" ? "Reading…" : d.d),
                    s === "load" && React.createElement("div", { className: "pp-doc-bar" }, React.createElement("span", { style: { width: prog[d.key] + "%" } })),
                    s === "err" && React.createElement("button", { className: "pp-doc-retry", onClick: () => uploadOne(d.key, false) }, "↻ Re-scan or enter manually")
                  ),
                  ds.ic && React.createElement("div", { className: "pp-doc-stat" }, React.createElement("i", { className: ds.ic + " " + ds.icls }))
                );
              }),
              React.createElement("div", { className: "pp-checklist-foot" },
                React.createElement("i", { className: "ri-lock-2-line" }),
                React.createElement("span", null, "Encrypted at rest · access-logged · deletable anytime"))
            )
          ),
          React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "22px" } },
            React.createElement("span", { className: "pp-manual", style: { margin: 0, textAlign: "left" } }, "Can't upload right now? ", React.createElement("a", { onClick: () => go(2) }, "Enter figures manually")),
            React.createElement("button", { className: "pp-btn pp-btn-dark", disabled: !anyUp, onClick: () => go(2) },
              anyUp ? "Confirm what I read" : "Upload to continue", React.createElement("i", { className: "ri-arrow-right-line" }))
          )
        )
      )
    )
  );
}

/* ════════════════════════════════════════════════════════════════
   OCR CONFIRM / CORRECT
   ════════════════════════════════════════════════════════════════ */
function ConfirmScene({ go }) {
  const [resolved, setResolved] = React.useState({});
  const onResolve = (k, v) => setResolved((r) => ({ ...r, [k]: v }));
  const total = DA.ocr.fields.length;
  const done = Object.keys(resolved).length;
  return (
    React.createElement("div", { className: "pp-scene" },
      React.createElement("div", { className: "pp-center" },
        React.createElement("div", { className: "pp-onb" },
          React.createElement("div", { className: "pp-onb-head" },
            React.createElement("span", { className: "pp-eyebrow" }, React.createElement("i", { className: "ri-double-quotes-l" }), "Step 2 · Confirm what I read"),
            React.createElement("h2", null, "Check the figures, then they're yours"),
            React.createElement("p", null, "I never trust a scan blindly. Confirm or correct each field; anything I read faintly is flagged for you.")
          ),
          React.createElement("div", { className: "pp-ocr-grid" },
            React.createElement("div", { className: "pp-doc-preview" },
              React.createElement("div", { className: "pp-doc-paper" },
                React.createElement("div", { className: "pp-doc-paper-head" },
                  React.createElement("i", { className: "ri-bank-line" }),
                  React.createElement("div", { className: "dt" }, React.createElement("div", { className: "t" }, DA.ocr.docTitle), React.createElement("div", { className: "d" }, DA.ocr.docMeta))
                ),
                React.createElement("div", { className: "pp-doc-lines" },
                  [0, 1, 0, 0, 1, 0, 0, 1].map((h, i) => React.createElement("div", { className: "pp-doc-line" + (h ? " hl" : ""), key: i, style: { width: (55 + (i * 37) % 45) + "%" } }))
                )
              ),
              React.createElement("div", { className: "pp-doc-scan" }, React.createElement("i", { className: "ri-scan-2-line" }), "6 fields extracted · highlighted on the document")
            ),
            React.createElement("div", { className: "pp-ocr-list" },
              React.createElement("div", { className: "pp-ocr-summary" },
                React.createElement("i", { className: "ri-information-line" }),
                React.createElement("p", { dangerouslySetInnerHTML: { __html: "Read from your <b>" + DA.ocr.docTitle + "</b>. Five came through clearly; <b>one needs your eyes</b>." } })
              ),
              DA.ocr.fields.map((f) => React.createElement(ConfirmCorrect, { field: f, key: f.key, onResolve }))
            )
          ),
          React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "22px" } },
            React.createElement("span", { className: "pp-manual", style: { margin: 0 } }, done, " of ", total, " confirmed"),
            React.createElement("button", { className: "pp-btn pp-btn-dark", onClick: () => go(3) }, "Continue", React.createElement("i", { className: "ri-arrow-right-line" }))
          )
        )
      )
    )
  );
}

/* ════════════════════════════════════════════════════════════════
   GAP-FILL
   ════════════════════════════════════════════════════════════════ */
function GapfillScene({ go, persona }) {
  const [ans, setAns] = React.useState(() => Object.fromEntries(DA.gapfill.map((q) => [q.key, q.sel])));
  return (
    React.createElement("div", { className: "pp-scene" },
      React.createElement("div", { className: "pp-center" },
        React.createElement("div", { className: "pp-onb", style: { maxWidth: "720px" } },
          React.createElement("div", { className: "pp-onb-head" },
            React.createElement("span", { className: "pp-eyebrow" }, React.createElement("i", { className: "ri-chat-3-line" }), "Step 3 · A few quick things"),
            React.createElement("h2", null, "Four taps to finish your picture"),
            React.createElement("p", null, "No typing needed, just pick what fits. I've pre-filled what I could infer.")
          ),
          React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: "20px" } },
            DA.gapfill.map((q) =>
              React.createElement("div", { key: q.key },
                React.createElement("div", { style: { font: "600 14px/1.3 var(--font-display)", color: "var(--fg-1)", marginBottom: "10px" } }, q.q),
                React.createElement("div", { className: "pp-chips", style: { paddingLeft: 0 } },
                  q.opts.map((o) => React.createElement("button", {
                    key: o, className: "pp-chip" + (ans[q.key] === o ? " is-sel" : ""),
                    onClick: () => setAns((a) => ({ ...a, [q.key]: o }))
                  }, ans[q.key] === o && React.createElement("i", { className: "ri-check-line" }), o))
                )
              )
            )
          ),
          React.createElement("div", { style: { display: "flex", justifyContent: "flex-end", marginTop: "26px" } },
            React.createElement("button", { className: "pp-btn pp-btn-brand pp-btn-lg", onClick: () => go(4) },
              React.createElement("i", { className: "ri-sparkling-line" }), "See my snapshot"))
        )
      )
    )
  );
}

/* ════════════════════════════════════════════════════════════════
   MANUAL ENTRY  (no documents / no OCR)
   ════════════════════════════════════════════════════════════════ */
function ManualEntryScene({ go, toast }) {
  const chf = (n) => Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019");
  const [val, setVal] = React.useState({
    name: "", canton: "", email: "", age: 45, retire: 64,
    income: 120000, target: 6500, networth: 250000,
    p2: 200000, p3a: 30000, p3aYr: 3000,
  });
  const set = (k, v) => setVal((s) => ({ ...s, [k]: v }));
  const [step, setStep] = React.useState(0);   // highest revealed step
  const [building, setBuilding] = React.useState(false);
  const [aiCoach, setAiCoach] = React.useState(null);
  React.useEffect(() => {
    if (!window.ppAI) return; let live = true;
    const prompt = "You are Pension AI guiding a Swiss user through a 4-step manual onboarding (1 About you, 2 Income & wealth, 3 Your pillars, 4 Add documents). Current values: age " + val.age + ", target retirement age " + val.retire + ", gross income " + val.income + ", target monthly " + val.target + ", net worth " + val.networth + ", 2nd pillar " + val.p2 + ", pillar 3a " + val.p3a + ". Write ONE short encouraging coaching line per step (max ~14 words each), warm, never guilt-tripping, Swiss retirement context. Reply ONLY with a JSON array of 4 strings.";
    window.ppAI.completeJSON(prompt).then((arr) => { if (live && Array.isArray(arr) && arr.length >= 4) setAiCoach(arr.map(String)); }).catch(() => {});
    return () => { live = false; };
  }, []);
  const [extras, setExtras] = React.useState({ inc: [], pil: [] });
  const addExtra = (g) => setExtras((s) => ({ ...s, [g]: [...s[g], { label: "", amt: "" }] }));
  const setExtra = (g, idx, patch) => setExtras((s) => ({ ...s, [g]: s[g].map((r, j) => j === idx ? { ...r, ...patch } : r) }));
  const delExtra = (g, idx) => setExtras((s) => ({ ...s, [g]: s[g].filter((_, j) => j !== idx) }));
  const extraSum = (g) => extras[g].reduce((t, r) => t + (parseInt(String(r.amt).replace(/[^0-9]/g, ""), 10) || 0), 0);
  const extraBlock = (g, addLabel) => React.createElement("div", { className: "pp-wiz-extras" },
    extras[g].map((r, idx) => React.createElement("div", { className: "pp-wiz-extra", key: idx },
      React.createElement("input", { className: "nm", placeholder: g === "pil" ? "Account (e.g. Vested benefits)" : "Source (e.g. Rental income)", value: r.label, onChange: (e) => setExtra(g, idx, { label: e.target.value }) }),
      React.createElement("span", { className: "pp-mf-input amt" },
        React.createElement("input", { inputMode: "numeric", placeholder: "0", value: r.amt, onChange: (e) => setExtra(g, idx, { amt: e.target.value.replace(/[^0-9]/g, "") }) }),
        React.createElement("span", { className: "suf" }, "CHF")),
      React.createElement("button", { className: "rm", onClick: () => delExtra(g, idx), title: "Remove" }, React.createElement("i", { className: "ri-close-line" })))),
    React.createElement("button", { className: "pp-wiz-addline", onClick: () => addExtra(g) }, React.createElement("i", { className: "ri-add-circle-line" }), addLabel));

  const years = Math.max(1, val.retire - val.age);
  const replacement = Math.round((val.target * 12) / Math.max(val.income, 1) * 100);
  const pillarsTotal = (+val.p2 || 0) + (+val.p3a || 0);

  // AI-style reactions per step
  const coachAbout = years >= 20
    ? "That's " + years + " years of compounding ahead, time is your biggest asset."
    : years >= 10 ? years + " years to go, still plenty of room to shape this."
    : "A " + years + "-year runway, we'll focus on the highest-impact moves.";
  const coachIncome = replacement >= 90 ? "Aiming high, you want to keep close to your current lifestyle. Noted."
    : replacement >= 60 ? "A " + replacement + "% replacement target, right in the healthy Swiss range."
    : "A lean target at " + replacement + "%, we'll see how comfortably your pillars cover it.";
  const coach3 = pillarsTotal > 0
    ? "Starting from CHF " + chf(pillarsTotal) + " across your pillars, good base to build on."
    : "No pillar balances yet? No problem, I'll model from your income and we refine later.";

  const [docs, setDocs] = React.useState([]);
  const docFileRef = React.useRef(null);
  const addDocs = (fileList) => { const names = Array.from(fileList || []).map((f) => f.name); if (names.length) { setDocs((d) => [...d, ...names]); toast && toast(names.length + " document" + (names.length > 1 ? "s" : "") + " attached"); } };
  const delDoc = (i) => setDocs((d) => d.filter((_, j) => j !== i));
  // confidence score — pure deterministic engine (declared vs verified)
  const confPersona = {
    grossIncome: +val.income || 0, netWorth: +val.networth || 0, pillar2: +val.p2 || 0, pillar3a: +val.p3a || 0,
    canton: val.canton || "", status: "Manual entry", age: +val.age || 0, retireTarget: +val.retire || 0,
    targetMonthly: +val.target || 0, savingCapacity: 1, objectivesSet: true, plans: [1],
    fieldStates: docs.length ? { grossIncome: "verified", pillar2: "verified", pillar3a: "verified", netWorth: "verified", canton: "verified" } : null,
  };
  const confComp = window.PP_CONFIDENCE ? window.PP_CONFIDENCE.compute(confPersona) : { score: 60, tier: "Good confidence" };
  const conf = confComp.score;
  const confTier = conf >= 85 ? { l: "High confidence", c: "hi" } : conf >= 68 ? { l: "Good confidence", c: "good" } : { l: "Building confidence", c: "fair" };
  const nbaTop = window.PP_CONFIDENCE ? window.PP_CONFIDENCE.nextBestActions(confPersona)[0] : null;
  const confNudge = nbaTop ? nbaTop.label + " " : (!val.email ? "Add your email so we can save and refine your plan. " : "Your inputs are sharp.");
  const confAction = nbaTop ? "+" + nbaTop.gain + " pts" : null;
  const docsCoach = docs.length ? (docs.length + " document" + (docs.length > 1 ? "s" : "") + " attached — I'll read these to replace estimates with exact figures.") : "Optional, but powerful: attach a tax return, LPP or 3a statement and every figure gets confirmed, not estimated.";

  const STEPS = [
    { t: "About you", ic: "ri-user-smile-line", coach: (aiCoach && aiCoach[0]) || coachAbout },
    { t: "Income & wealth", ic: "ri-wallet-3-line", coach: (aiCoach && aiCoach[1]) || coachIncome },
    { t: "Your pillars", ic: "ri-stack-line", coach: (aiCoach && aiCoach[2]) || coach3 },
    { t: "Add documents", ic: "ri-attachment-2", coach: (aiCoach && aiCoach[3]) || docsCoach },
  ];

  const Slider = (k, lo, hi, st, fmt) => React.createElement("div", { className: "pp-sl" },
    React.createElement("div", { className: "pp-sl-top" },
      React.createElement("span", { className: "v" }, fmt(val[k]))),
    React.createElement("input", { type: "range", min: lo, max: hi, step: st, value: val[k],
      style: { "--pct": ((val[k] - lo) / (hi - lo) * 100) + "%" },
      onChange: (e) => set(k, +e.target.value) }),
    React.createElement("div", { className: "pp-sl-ends" }, React.createElement("span", null, fmt(lo)), React.createElement("span", null, fmt(hi))));

  const submit = () => {
    setBuilding(true);
    try {
      if (window.PP_LIVE && window.__ppActivateLive) {
        const incExtra = extras.inc.reduce((t, r) => t + (parseInt(String(r.amt).replace(/[^0-9]/g, ""), 10) || 0), 0);
        const pilExtra = extras.pil.reduce((t, r) => t + (parseInt(String(r.amt).replace(/[^0-9]/g, ""), 10) || 0), 0);
        const x = { firstName: (val.name || "").trim(), age: +val.age, canton: (val.canton || "").trim(),
          status: "Manual entry", grossIncome: +val.income, netWorth: (+val.networth) + incExtra,
          pillar2: (+val.p2) + pilExtra, pillar3a: +val.p3a, targetMonthly: +val.target, retireAge: +val.retire, confidence: conf };
        const p = window.PP_LIVE.build(x); window.__ppActivateLive(p);
      }
    } catch (e) {}
    toast && toast("Building your plan from what you entered");
    setTimeout(() => go(4), 900);
  };

  const summary = (i) => {
    if (i === 0) return [(val.name || "You").trim() || "You", val.age + " yrs", "retire " + val.retire].join(" · ");
    if (i === 1) return ["CHF " + chf(val.income) + " income", "CHF " + chf(val.target) + "/mo target"].join(" · ");
    if (i === 2) return ["2nd pillar CHF " + chf(val.p2), "3a CHF " + chf(val.p3a)].join(" · ");
    return docs.length ? (docs.length + " document" + (docs.length > 1 ? "s" : "") + " attached") : "No documents (optional)";
  };

  return (
    React.createElement("div", { className: "pp-scene" },
      React.createElement("div", { className: "pp-center" },
        React.createElement("div", { className: "pp-onb", style: { maxWidth: "640px" } },
          React.createElement("div", { className: "pp-onb-head" },
            React.createElement("span", { className: "pp-eyebrow" }, React.createElement("i", { className: "ri-keyboard-line" }), "Guided manual entry"),
            React.createElement("h2", null, "Let's build it together"),
            React.createElement("p", null, "No documents needed. Answer a few questions, I'll react as we go and estimate anything you skip.")
          ),
          React.createElement(ConfidenceMeter, { score: conf, nudge: confNudge, actionLabel: confAction, onAction: () => docFileRef.current && docFileRef.current.click() }),
          React.createElement("input", { ref: docFileRef, type: "file", multiple: true, accept: ".pdf,.jpg,.jpeg,.png,.heic,.txt", style: { display: "none" }, onChange: (e) => addDocs(e.target.files) }),
          React.createElement("div", { className: "pp-wiz" },
            STEPS.map((s, i) => {
              const state = i < step ? "done" : i === step ? "active" : "locked";
              return React.createElement("div", { className: "pp-wiz-step is-" + state, key: i },
                React.createElement("button", { className: "pp-wiz-head", disabled: state === "locked",
                  onClick: () => { if (state === "done") setStep(i); } },
                  React.createElement("span", { className: "pp-wiz-n" }, state === "done" ? React.createElement("i", { className: "ri-check-line" }) : React.createElement("i", { className: s.ic })),
                  React.createElement("span", { className: "pp-wiz-t" }, s.t,
                    state === "done" ? React.createElement("span", { className: "sum" }, summary(i)) : null),
                  state === "done" ? React.createElement("i", { className: "ri-pencil-line ed" }) : null),
                state === "active" ? React.createElement("div", { className: "pp-wiz-body", key: "b" + i },
                  // STEP CONTENT
                  i === 0 ? React.createElement("div", { className: "pp-wiz-fields" },
                    React.createElement("label", { className: "pp-mf-field" },
                      React.createElement("span", { className: "lab" }, "First name ", React.createElement("span", { className: "opt" }, "optional")),
                      React.createElement("span", { className: "pp-mf-input" }, React.createElement("input", { placeholder: "e.g. Sandrine", value: val.name, onChange: (e) => set("name", e.target.value) }))),
                    React.createElement("label", { className: "pp-mf-field" },
                      React.createElement("span", { className: "lab" }, "Canton ", React.createElement("span", { className: "opt" }, "optional")),
                      React.createElement("span", { className: "pp-mf-input" }, React.createElement("input", { placeholder: "e.g. Vaud", value: val.canton, onChange: (e) => set("canton", e.target.value) }))),
                    React.createElement("label", { className: "pp-mf-field" },
                      React.createElement("span", { className: "lab" }, "Email ", React.createElement("span", { className: "opt" }, "to save your plan")),
                      React.createElement("span", { className: "pp-mf-input" },
                        React.createElement("i", { className: "ri-mail-line lead-ic" }),
                        React.createElement("input", { type: "email", placeholder: "you@email.ch", value: val.email, onChange: (e) => set("email", e.target.value) }))),
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "Your age today"), Slider("age", 25, 64, 1, (v) => v + " yrs")),
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "Target retirement age"), Slider("retire", Math.max(58, +val.age + 1), 70, 1, (v) => v + " yrs"))
                  ) : i === 1 ? React.createElement("div", { className: "pp-wiz-fields" },
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "Gross annual income"), Slider("income", 40000, 500000, 5000, (v) => "CHF " + chf(v))),
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "Target income in retirement"), Slider("target", 2000, 25000, 100, (v) => "CHF " + chf(v) + "/mo")),
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "Approx. net worth ", React.createElement("span", { className: "opt" }, "optional")), Slider("networth", 0, 3000000, 10000, (v) => "CHF " + chf(v))),
                    extraBlock("inc", "Add another income or asset")
                  ) : i === 2 ? React.createElement("div", { className: "pp-wiz-fields" },
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "2nd pillar (LPP/BVG) capital"), Slider("p2", 0, 1500000, 10000, (v) => "CHF " + chf(v))),
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "Pillar 3a balance"), Slider("p3a", 0, 200000, 1000, (v) => "CHF " + chf(v))),
                    React.createElement("div", { className: "pp-sl-field" }, React.createElement("span", { className: "lab" }, "3a paid this year"), Slider("p3aYr", 0, 7258, 258, (v) => "CHF " + chf(v))),
                    extraBlock("pil", "Add another pillar or account")
                  ) : React.createElement("div", { className: "pp-wiz-fields" },
                    React.createElement("div", { className: "pp-wiz-drop", onClick: () => docFileRef.current && docFileRef.current.click(),
                      onDragOver: (e) => { e.preventDefault(); }, onDrop: (e) => { e.preventDefault(); addDocs(e.dataTransfer.files); } },
                      React.createElement("i", { className: "ri-upload-cloud-2-line" }),
                      React.createElement("div", { className: "t" }, "Attach a document"),
                      React.createElement("div", { className: "d" }, "Tax return, LPP / pension certificate, 3a statement — PDF, JPG, PNG")),
                    docs.length ? React.createElement("div", { className: "pp-wiz-doclist" },
                      docs.map((d, j) => React.createElement("div", { className: "pp-wiz-doc", key: j },
                        React.createElement("i", { className: "ri-file-text-line" }),
                        React.createElement("span", { className: "fn" }, d),
                        React.createElement("i", { className: "ri-checkbox-circle-fill ok" }),
                        React.createElement("button", { className: "rm", onClick: (e) => { e.stopPropagation(); delDoc(j); }, title: "Remove" }, React.createElement("i", { className: "ri-close-line" }))))) : null
                  ),
                  // AI COACH LINE
                  React.createElement("div", { className: "pp-wiz-coach" },
                    React.createElement("span", { className: "av" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
                    React.createElement("p", null, s.coach)),
                  // STEP ACTION
                  React.createElement("div", { className: "pp-wiz-act" },
                    i > 0 ? React.createElement("button", { className: "pp-btn pp-btn-ghost", onClick: () => setStep(i - 1) }, "Back") : React.createElement("button", { className: "pp-btn pp-btn-ghost", onClick: () => window.__ppOpenMethod && window.__ppOpenMethod() }, React.createElement("i", { className: "ri-upload-cloud-2-line" }), "Upload instead"),
                    i < STEPS.length - 1
                      ? React.createElement("button", { className: "pp-btn pp-btn-dark pp-btn-lg", onClick: () => setStep(i + 1) }, "Continue", React.createElement("i", { className: "ri-arrow-right-line" }))
                      : React.createElement("button", { className: "pp-btn pp-btn-dark pp-btn-lg", disabled: building, onClick: submit }, React.createElement("i", { className: building ? "ri-loader-4-line pp-spin" : "ri-sparkling-line" }), building ? "Building\u2026" : "Build my plan"))
                ) : null
              );
            })
          ),
          React.createElement("div", { className: "pp-wiz-trust" },
            React.createElement("i", { className: "ri-lock-2-line" }),
            React.createElement("span", null, "Your figures are processed to build your plan only, encrypted in transit and ", React.createElement("b", null, "hosted in Switzerland"), ". Nothing is shared or used for training (revDPA). You can delete it anytime."))
        )
      )
    )
  );
}

/* ════════════════════════════════════════════════════════════════
   WORK-SCENE CONVERSATIONS
   ════════════════════════════════════════════════════════════════ */
function SnapshotConvo({ go, persona }) {
  const items = [
    React.createElement(AiMsg, { key: 0, label: "info" },
      React.createElement("div", { className: "pp-ai-text" }, "Here's where you stand today, ", persona.first, ". I built this only from the documents you confirmed, every figure on the right traces back to one of your inputs.")),
    React.createElement(AiMsg, { key: 1 },
      React.createElement("div", { className: "pp-ai-text", dangerouslySetInnerHTML: { __html: "Across all three pillars you're on track for about <span class='amt'>CHF 5\u2019130/month</span> at 64, roughly <b>77%</b> of your CHF 6\u2019700 lifestyle target." } })),
    React.createElement(AiMsg, { key: 2 },
      React.createElement("div", { className: "pp-ai-text", dangerouslySetInnerHTML: { __html: "That leaves a gap of about <span class='amt'>CHF 1\u2019570/month</span>. It's very closable from where you are. Want the levers, ranked by impact?" } })),
  ];
  const { count, isTyping } = useSequence(items.length);
  return (
    React.createElement(React.Fragment, null,
      items.slice(0, count),
      isTyping && React.createElement("div", { className: "pp-msg ai" }, React.createElement("div", { className: "pp-ai-row" },
        React.createElement("div", { className: "pp-ai-mark" }, React.createElement("i", { className: "ri-sparkling-fill" })), React.createElement(Typing, null))),
      count >= items.length && React.createElement(Chips, { items: [
        { icon: "ri-flashlight-line", label: "Show me the levers", onClick: () => go(5) },
        { icon: "ri-bank-card-line", label: "We're thinking of buying", onClick: () => go(6) },
        { icon: "ri-calendar-line", label: "Could I retire at 62?", onClick: () => go(7) },
      ] })
    )
  );
}

function PlanConvo({ go }) {
  const items = [
    React.createElement(AiMsg, { key: 0 },
      React.createElement("div", { className: "pp-ai-text", dangerouslySetInnerHTML: { __html: "Here are your levers, ranked by what each adds to your monthly retirement income. The <b>top four close about CHF 1\u2019470</b> of your CHF 1\u2019570 gap, without changing your lifestyle today." } })),
    React.createElement("div", { key: 1, className: "pp-ai-widget", style: { paddingLeft: "39px", display: "flex", flexDirection: "column", gap: "12px" } },
      DA.levers.map((l) => React.createElement(Lever, { lever: l, key: l.rank }))),
    React.createElement(AiMsg, { key: 2, label: "info" },
      React.createElement("div", { className: "pp-ai-text" }, "Each card is tagged ", React.createElement("b", null, "Information"), " or ", React.createElement("b", null, "Personal recommendation"), ", and every number opens its own \u201cshow the math.\u201d Nothing here is a product pitch.")),
  ];
  const { count, isTyping } = useSequence(items.length, { step: 820 });
  return (
    React.createElement(React.Fragment, null,
      items.slice(0, count),
      isTyping && React.createElement("div", { className: "pp-msg ai" }, React.createElement("div", { className: "pp-ai-row" },
        React.createElement("div", { className: "pp-ai-mark" }, React.createElement("i", { className: "ri-sparkling-fill" })), React.createElement(Typing, null))),
      count >= items.length && React.createElement(Chips, { items: [
        { icon: "ri-bank-card-line", label: "Model buying a home", onClick: () => go(6) },
        { icon: "ri-calendar-line", label: "Could I retire at 62?", onClick: () => go(7) },
        { icon: "ri-bar-chart-box-line", label: "Go to my monitoring home", onClick: () => go(8) },
      ] })
    )
  );
}

function PropertyConvo({ go }) {
  const p = DA.property;
  const items = [
    React.createElement(UserMsg, { key: 0 }, "We found a flat, CHF 1.2M. We'd use some pension money to make it work."),
    React.createElement(AiMsg, { key: 1, label: "advice" },
      React.createElement("div", { className: "pp-ai-text", dangerouslySetInnerHTML: { __html: "Congratulations. Two routes use your pension very differently. Here's the side-by-side at your retirement date, withdrawing <b>CHF 100\u2019000</b> now is about <span class='amt'>\u2212 CHF 430/month</span> at 64." } })),
    React.createElement("div", { key: 2, className: "pp-ai-widget", style: { paddingLeft: "39px" } },
      React.createElement("div", { className: "pp-compare" },
        p.options.map((o) => React.createElement("div", { className: "pp-opt" + (o.rec ? " is-rec" : ""), key: o.id },
          React.createElement("div", { className: "pp-opt-head" },
            React.createElement("div", { className: "pp-opt-ic " + o.id }, React.createElement("i", { className: o.icon })),
            React.createElement("div", { style: { flex: 1, minWidth: 0 } }, React.createElement("div", { className: "t" }, o.t, React.createElement("small", null, o.sub))),
            o.rec && React.createElement("span", { className: "pp-opt-flag" }, React.createElement("i", { className: "ri-thumb-up-line" }), "Suits you")
          ),
          React.createElement("div", { className: "pp-opt-bd" },
            o.metrics.map((m, i) => React.createElement("div", { className: "pp-opt-metric", key: i },
              React.createElement("div", { className: "l" }, m.l),
              React.createElement("div", { className: "v " + (m.tone || "") }, m.v),
              React.createElement("div", { className: "n" }, m.n)))
          )
        )))),
    React.createElement(AiMsg, { key: 3, label: "advice" },
      React.createElement("div", { className: "pp-ai-text", dangerouslySetInnerHTML: { __html: "For your age and 22-year horizon, a <b>pledge</b> keeps your retirement plan whole while your capital keeps compounding, I'd lean that way. It does need affordability headroom, which your income supports." } })),
    React.createElement("div", { key: 4, className: "pp-ai-widget", style: { paddingLeft: "39px" } },
      React.createElement(Disclosure, null, "This is a personal recommendation under FinSA: a suitability check on your situation and objectives applies, and it's documented in your advice log. Tax effects are cantonal estimates. Swissquote is affiliated with the Swiss Banking Ombudsman.")),
  ];
  const { count, isTyping } = useSequence(items.length, { step: 800 });
  return (
    React.createElement(React.Fragment, null,
      items.slice(0, count),
      isTyping && React.createElement("div", { className: "pp-msg ai" }, React.createElement("div", { className: "pp-ai-row" },
        React.createElement("div", { className: "pp-ai-mark" }, React.createElement("i", { className: "ri-sparkling-fill" })), React.createElement(Typing, null))),
      count >= items.length && React.createElement(Chips, { items: [
        { icon: "ri-calculator-line", label: "Model amortisation too", onClick: () => {} },
        { icon: "ri-calendar-line", label: "Compare retirement ages", onClick: () => go(7) },
        { icon: "ri-flashlight-line", label: "Back to my levers", onClick: () => go(5) },
      ] })
    )
  );
}

function StressWidget({ toast }) {
  const S = DA.stress;
  const [age, setAge] = React.useState(S.def);
  const v = S.verdicts[age];
  const fill = ((age - S.min) / (S.max - S.min)) * 100;
  const bridgeYears = [];
  for (let a = age; a < S.reference; a++) bridgeYears.push({ yr: "Age " + a, amt: "CHF 26\u2019200", src: a === S.reference - 1 ? "bridge until AVS at 65" : "from 3a + vested benefits" });
  return (
    React.createElement("div", { className: "pp-card" },
      React.createElement("div", { className: "pp-stress-age" },
        React.createElement("div", { className: "l" }, "Target retirement age"),
        React.createElement("div", { className: "v" }, age)),
      React.createElement("input", { type: "range", className: "pp-stress-slider", min: S.min, max: S.max, value: age, style: { "--fill": fill + "%" }, onChange: (e) => setAge(+e.target.value) }),
      React.createElement("div", { className: "pp-stress-scale" }, [60, 61, 62, 63, 64, 65, 66, 67].map((n) => React.createElement("span", { key: n }, n))),
      React.createElement("div", { className: "pp-feas " + v.tone },
        React.createElement("div", { className: "pp-feas-ic" }, React.createElement("i", { className: v.tone === "ok" ? "ri-check-line" : v.tone === "tight" ? "ri-scales-3-line" : "ri-close-line" })),
        React.createElement("div", { className: "pp-feas-bd" },
          React.createElement("div", { className: "t" }, v.t),
          React.createElement("div", { className: "d" }, v.d)),
        React.createElement("div", { className: "pp-feas-conf" },
          React.createElement("div", { className: "cv" }, v.conf), React.createElement("div", { className: "cl" }, "Confidence"))
      ),
      bridgeYears.length > 0 && React.createElement(React.Fragment, null,
        React.createElement("div", { style: { font: "700 11px/1 var(--font-body)", color: "var(--fg-4)", textTransform: "uppercase", letterSpacing: ".04em", margin: "4px 0 10px" } }, "Bridging income needed before AVS at 65"),
        React.createElement("div", { className: "pp-bridgeyears", style: { gridTemplateColumns: "repeat(" + Math.min(bridgeYears.length, 3) + ",1fr)" } },
          bridgeYears.slice(0, 3).map((b, i) => React.createElement("div", { className: "pp-by", key: i },
            React.createElement("div", { className: "yr" }, b.yr), React.createElement("div", { className: "amt" }, b.amt), React.createElement("div", { className: "src" }, b.src))))),
      React.createElement("div", { style: { display: "flex", flexWrap: "wrap", gap: "7px", marginTop: "14px" } },
        S.levers.map((l, i) => React.createElement("span", { key: i, className: "sq-badge brand", style: { display: "inline-flex", alignItems: "center", gap: "5px", padding: "6px 11px", borderRadius: "999px", background: "var(--brand-orange-50)", color: "var(--brand-orange-600)", font: "600 11.5px/1 var(--font-body)" } },
          React.createElement("i", { className: "ri-check-line" }), l))),
      React.createElement("div", { style: { marginTop: "14px" } },
        React.createElement(ShowMath, { steps: [
          ["Inputs", "Target age <b>" + age + "</b>; AVS reference age 65; 3a + vested-benefits available for bridging."],
          ["Assumption", "AVS deferral over early claim; 2nd-pillar conversion reduced for early exit; 2.5% net real return."],
          ["Result", v.tone === "ok" ? "No bridge needed, pillars cover the target." : "Bridge \u2248 CHF 26\u2019200/yr until 65, then full pillars resume."],
        ], rule: "Early retirement · AVS reduction & bridging" }))
    )
  );
}

function StressConvo({ go, toast }) {
  const items = [
    React.createElement(UserMsg, { key: 0 }, "Could I retire at 62 instead of 64?"),
    React.createElement(AiMsg, { key: 1, label: "info" },
      React.createElement("div", { className: "pp-ai-text" }, "Let's stress-test it. Drag to set a target age and I'll re-run the bridge to AVS, the conversion-rate effect and the drawdown, calmly, no alarms.")),
    React.createElement("div", { key: 2, className: "pp-ai-widget", style: { paddingLeft: "39px" } }, React.createElement(StressWidget, { toast })),
    React.createElement(AiMsg, { key: 3 },
      React.createElement("div", { className: "pp-ai-text" }, "At 62 it's tight but doable. When you're closer, the capital-vs-annuity call is irreversible, that's where I'd bring in a human advisor with everything already prepared.")),
  ];
  const { count, isTyping } = useSequence(items.length, { step: 800 });
  return (
    React.createElement(React.Fragment, null,
      items.slice(0, count),
      isTyping && React.createElement("div", { className: "pp-msg ai" }, React.createElement("div", { className: "pp-ai-row" },
        React.createElement("div", { className: "pp-ai-mark" }, React.createElement("i", { className: "ri-sparkling-fill" })), React.createElement(Typing, null))),
      count >= items.length && React.createElement(Chips, { items: [
        { icon: "ri-user-shared-line", label: "Talk to a human advisor", onClick: () => go(8) },
        { icon: "ri-flashlight-line", label: "Back to my levers", onClick: () => go(5) },
        { icon: "ri-bar-chart-box-line", label: "Go to monitoring home", onClick: () => go(8) },
      ] })
    )
  );
}

Object.assign(window, { useSequence, Chips, WelcomeScene, UploadScene, ConfirmScene, GapfillScene, ManualEntryScene, SnapshotConvo, PlanConvo, PropertyConvo, StressConvo, StressWidget });
