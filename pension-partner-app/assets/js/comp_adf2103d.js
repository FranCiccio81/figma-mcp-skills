/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER — Conversational manual onboarding ("Léa")
   "Guided momentum": a calm chat that estimates a Swiss pension as the
   user answers. 6-step rail, an honest "Estimate sharpness" meter
   (Rough → Getting clearer → Sharp), quick-reply chips, a secondary
   "Fast-track: upload" pill, and a closing reveal. window.ConvoOnboard
   ════════════════════════════════════════════════════════════════ */
const { useState, useRef, useEffect } = React;

function ConvoOnboard({ go, toast }) {
  const chf = (n) => "CHF " + Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019");
  const AGENT = "Léa";

  const [ans, setAns] = useState({});
  const [est, setEst] = useState({});
  const [idx, setIdx] = useState(0);
  const [building, setBuilding] = useState(false);
  const [listening, setListening] = useState(false);
  const [docs, setDocs] = useState([]);
  const recRef = useRef(null);
  const threadRef = useRef(null);
  const docRef = useRef(null);

  // ── 5 questions + closing reveal = 6 steps ──────────────────────
  const STEPS = [
    { key: "name", ask: () => "Let's build your retirement picture together. First, what should I call you?",
      kind: "text", placeholder: "Your first name", optional: true,
      react: (v) => v ? ("Nice to meet you, " + v + ". Let's keep going.") : "No problem, let's keep it simple." },
    { key: "age", ask: () => "How old are you today?",
      kind: "chips-num", options: [30, 40, 50, 60], stepper: { min: 25, max: 64 }, def: 45, unit: "",
      react: (v) => v <= 35 ? "Plenty of runway, time is on your side." : v <= 49 ? "A great moment to shape your plan." : "We'll focus on what moves the needle now." },
    { key: "income", ask: () => "Roughly, what's your gross annual salary? This sharpens the estimate the most.",
      kind: "money", min: 40000, max: 400000, step: 5000, def: 120000,
      react: () => "Got it. That already narrows the picture a lot." },
    { key: "retire", ask: () => "At what age would you like to retire?",
      kind: "chips-num", options: [60, 62, 65], laterFrom: 67, def: 65, unit: "",
      react: (v) => v < 64 ? ("Retiring at " + v + " is ambitious, we'll see how reachable it is.") : v === 65 ? "65, the classic baseline to plan around." : ("Working to " + v + " noticeably strengthens your pension.") },
    { key: "pillars", ask: () => "And your pension savings so far?",
      kind: "chips", options: ["Pillar 2 & 3a", "Mostly 3a", "Just starting"], def: "Mostly 3a",
      react: (v) => v === "Pillar 2 & 3a" ? "A solid base across both pillars, good." : v === "Mostly 3a" ? "Your 3a is your most actionable lever, noted." : "Early days, the best time to start is now." },
  ];

  const cur = STEPS[idx];
  const atEnd = idx >= STEPS.length;
  const totalSteps = STEPS.length + 1; // +1 closing
  const stepNo = Math.min(idx + 1, totalSteps);

  useEffect(() => { const t = threadRef.current; if (t) t.scrollTop = t.scrollHeight; }, [idx, docs.length, building]);

  // ── honest "estimate sharpness" ─────────────────────────────────
  const answered = STEPS.filter((s) => ans[s.key] !== undefined && !est[s.key]).length;
  const sharpPct = Math.round((Object.keys(ans).length / STEPS.length) * 78) + (atEnd ? 22 : 6);
  const sharpW = Math.max(8, Math.min(100, sharpPct));
  const sharpWord = sharpW >= 80 ? "Sharp" : sharpW >= 45 ? "Getting clearer" : "Rough";

  // ── derive pillar figures from the chip answer ──────────────────
  const incomeV = +ans.income || 120000;
  const pillarMap = { "Pillar 2 & 3a": { p2: Math.round(incomeV * 1.4), p3a: 40000 }, "Mostly 3a": { p2: Math.round(incomeV * 0.5), p3a: 30000 }, "Just starting": { p2: Math.round(incomeV * 0.3), p3a: 8000 } };
  const pill = pillarMap[ans.pillars] || pillarMap["Mostly 3a"];

  // ── answering ───────────────────────────────────────────────────
  const [draftVal, setDraftVal] = useState(null);
  useEffect(() => { setDraftVal(cur ? (cur.kind === "text" ? "" : (cur.def != null ? cur.def : "")) : ""); }, [idx]);
  const answer = (val, estimated) => {
    if (!cur) return;
    setAns((a) => ({ ...a, [cur.key]: val }));
    if (estimated) setEst((e) => ({ ...e, [cur.key]: true }));
    setIdx((i) => i + 1);
  };
  const skipAll = () => { // "Skip — estimate it for me": fill the rest with defaults
    const next = { ...ans }, ne = { ...est };
    STEPS.forEach((s) => { if (next[s.key] === undefined) { next[s.key] = s.def != null ? s.def : ""; ne[s.key] = true; } });
    setAns(next); setEst(ne); setIdx(STEPS.length);
  };

  const micToggle = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { toast && toast("Voice needs Chrome, Edge or Safari"); return; }
    if (listening) { try { recRef.current && recRef.current.stop(); } catch (e) {} setListening(false); return; }
    let rec; try { rec = new SR(); } catch (e) { return; }
    recRef.current = rec; rec.lang = "en-GB"; rec.interimResults = true; rec.continuous = false;
    let finalT = "";
    rec.onstart = () => setListening(true);
    rec.onresult = (e) => { let it = ""; for (let i = e.resultIndex; i < e.results.length; i++) { const t = e.results[i][0].transcript; if (e.results[i].isFinal) finalT += t; else it += t; } setDraftVal((finalT + it).trim()); };
    rec.onerror = () => setListening(false); rec.onend = () => setListening(false);
    try { rec.start(); } catch (e) { setListening(false); }
  };

  // ── draft estimate ──────────────────────────────────────────────
  const dRetire = +ans.retire || 64, dAge = +ans.age || 45;
  const dCap = pill.p2 + pill.p3a;
  const dFund = Math.round(dCap * Math.pow(1.025, Math.max(1, dRetire - dAge)) + incomeV * 0.12 * Math.max(1, dRetire - dAge) * 1.1);
  const dMonthly = Math.round((2100 + dFund * 0.068 / 12) / 50) * 50;

  const build = () => {
    setBuilding(true);
    try {
      if (window.PP_LIVE && window.__ppActivateLive) {
        const x = { firstName: (ans.name || "").trim(), age: dAge, canton: "",
          status: "Manual entry", grossIncome: incomeV, netWorth: Math.round(dCap + incomeV * 0.6),
          pillar2: pill.p2, pillar3a: pill.p3a, targetMonthly: Math.round(incomeV * 0.7 / 12 / 100) * 100, retireAge: dRetire, confidence: sharpW };
        const p = window.PP_LIVE.build(x); window.__ppActivateLive(p);
      }
    } catch (e) {}
    toast && toast("Building your plan from our conversation");
    setTimeout(() => go(4), 1100);
  };

  // ── render helpers ──────────────────────────────────────────────
  const leaBubble = (txt, key) => React.createElement("div", { className: "lea2-row", key },
    React.createElement("div", { className: "lea2-bubble" }, txt));
  const userChip = (txt, onEdit, key) => React.createElement("div", { className: "lea2-user", key },
    React.createElement("button", { className: "lea2-answer", onClick: onEdit, title: "Edit" }, txt, React.createElement("i", { className: "ri-pencil-line" })));

  const thread = [];
  STEPS.forEach((s, j) => {
    if (j >= idx) return;
    thread.push(leaBubble(s.ask(ans), "q" + j));
    const v = ans[s.key];
    const shown = s.kind === "money" ? chf(v) : (s.unit ? v + s.unit : (v || (s.optional ? "Skipped" : "—")));
    thread.push(userChip(shown + (est[s.key] ? " · estimated" : ""), () => setIdx(j), "a" + j));
    thread.push(leaBubble(s.react(v, ans), "r" + j));
  });

  return React.createElement("div", { className: "pp-scene" },
    React.createElement("div", { className: "pp-center" },
      React.createElement("div", { className: "lea2", style: { maxWidth: "440px" } },

        // step rail
        React.createElement("div", { className: "lea2-rail" },
          Array.from({ length: totalSteps }).map((_, j) => React.createElement("span", { key: j, className: j < stepNo - 1 ? "done" : j === stepNo - 1 ? "on" : "" }))),
        React.createElement("div", { className: "lea2-railmeta" },
          React.createElement("span", null, "Step ", stepNo, " of ", totalSteps),
          React.createElement("span", null, "\u2248 2 min")),

        // Léa identity
        React.createElement("div", { className: "lea2-id" },
          React.createElement("span", { className: "av" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
          React.createElement("span", { className: "nm" }, AGENT)),

        // estimate sharpness meter
        React.createElement("div", { className: "lea2-sharp" },
          React.createElement("div", { className: "h" },
            React.createElement("span", { className: "l" }, React.createElement("i", { className: "ri-pulse-line" }), "Estimate sharpness"),
            React.createElement("span", { className: "w" }, sharpWord)),
          React.createElement("div", { className: "bar" }, React.createElement("span", { style: { width: sharpW + "%" } })),
          React.createElement("div", { className: "sub" }, "Gets sharper with every answer you give.")),

        // thread
        React.createElement("div", { className: "lea2-thread", ref: threadRef },
          thread,
          (!atEnd && cur) ? React.createElement("div", { className: "lea2-active", key: "active" },
            leaBubble(cur.ask(ans), "qa"),
            // controls
            cur.kind === "text" ? React.createElement("div", { className: "lea2-composer" },
              React.createElement("input", { className: "lea2-input", placeholder: cur.placeholder, value: draftVal || "", autoFocus: true,
                onChange: (e) => setDraftVal(e.target.value), onKeyDown: (e) => { if (e.key === "Enter") answer((draftVal || "").trim(), !draftVal); } }),
              React.createElement("button", { className: "lea2-mic" + (listening ? " on" : ""), onClick: micToggle, "aria-label": "Voice" }, React.createElement("i", { className: listening ? "ri-mic-fill" : "ri-mic-line" })),
              React.createElement("button", { className: "lea2-send", onClick: () => answer((draftVal || "").trim(), !draftVal), "aria-label": "Send" }, React.createElement("i", { className: "ri-arrow-right-line" }))) : null,

            cur.kind === "chips-num" ? React.createElement("div", { className: "lea2-quick" },
              cur.options.map((o) => React.createElement("button", { key: o, className: "lea2-qchip", onClick: () => answer(o, false) }, o)),
              cur.laterFrom ? React.createElement("button", { className: "lea2-qchip", onClick: () => answer(cur.laterFrom, false) }, "Later") : null,
              cur.stepper ? React.createElement("span", { className: "lea2-or" }, "or pick exactly") : null,
              cur.stepper ? React.createElement("span", { className: "lea2-stepper" },
                React.createElement("button", { onClick: () => setDraftVal((d) => Math.max(cur.stepper.min, (+d || cur.def) - 1)) }, React.createElement("i", { className: "ri-subtract-line" })),
                React.createElement("b", null, draftVal != null && draftVal !== "" ? draftVal : cur.def),
                React.createElement("button", { onClick: () => setDraftVal((d) => Math.min(cur.stepper.max, (+d || cur.def) + 1)) }, React.createElement("i", { className: "ri-add-line" })),
                React.createElement("button", { className: "go", onClick: () => answer(draftVal != null && draftVal !== "" ? +draftVal : cur.def, false) }, React.createElement("i", { className: "ri-arrow-right-line" }))) : null) : null,

            cur.kind === "money" ? React.createElement("div", { className: "lea2-money" },
              React.createElement("div", { className: "v" }, chf(draftVal != null ? draftVal : cur.def)),
              React.createElement("input", { type: "range", min: cur.min, max: cur.max, step: cur.step, value: draftVal != null ? draftVal : cur.def,
                style: { "--pct": (((draftVal != null ? draftVal : cur.def) - cur.min) / (cur.max - cur.min) * 100) + "%" },
                onChange: (e) => setDraftVal(+e.target.value) }),
              React.createElement("button", { className: "lea2-confirm", onClick: () => answer(draftVal != null ? draftVal : cur.def, false) }, "Confirm", React.createElement("i", { className: "ri-arrow-right-line" }))) : null,

            cur.kind === "chips" ? React.createElement("div", { className: "lea2-quick" },
              cur.options.map((o) => React.createElement("button", { key: o, className: "lea2-qchip wide", onClick: () => answer(o, false) }, o))) : null,

            // fast-track + skip (only while answering)
            React.createElement("button", { className: "lea2-fasttrack", onClick: () => window.__ppOpenMethod ? window.__ppOpenMethod() : (window.__ppOpenTax && window.__ppOpenTax()) },
              React.createElement("i", { className: "ri-flashlight-line" }), React.createElement("span", null, React.createElement("b", null, "Fast-track:"), " upload your certificate to skip ahead")),
            React.createElement("button", { className: "lea2-skip", onClick: skipAll }, "Skip — estimate it for me")) : null,

          // closing reveal
          atEnd ? React.createElement("div", { key: "end" },
            leaBubble("Here's your first estimate" + (ans.name ? ", " + ans.name : "") + ". Around " + chf(dMonthly) + "/month from age " + dRetire + ", on roughly " + chf(dFund) + " of projected capital.", "draft"),
            React.createElement("div", { className: "lea2-reveal" },
              React.createElement("div", { className: "r" }, React.createElement("span", null, "Projected monthly income"), React.createElement("b", null, chf(dMonthly), "/mo")),
              React.createElement("div", { className: "r" }, React.createElement("span", null, "Projected capital at " + dRetire), React.createElement("b", null, chf(dFund)))),
            React.createElement("input", { ref: docRef, type: "file", multiple: true, accept: ".pdf,.jpg,.jpeg,.png,.heic,.txt", style: { display: "none" },
              onChange: (e) => { const n = Array.from(e.target.files || []).map((f) => f.name); if (n.length) { setDocs((d) => [...d, ...n]); toast && toast(n.length + " document attached"); } } }),
            React.createElement("button", { className: "lea2-fasttrack", onClick: () => docRef.current && docRef.current.click() },
              React.createElement("i", { className: "ri-attachment-2" }), React.createElement("span", null, docs.length ? (docs.length + " document attached — we'll sharpen it") : "Add a document to make it exact")),
            React.createElement("button", { className: "lea2-build", disabled: building, onClick: build },
              React.createElement("i", { className: building ? "ri-loader-4-line pp-spin" : "ri-arrow-right-line" }), building ? "Building…" : "See my full plan")) : null),

        React.createElement("div", { className: "lea2-privacy" }, React.createElement("i", { className: "ri-lock-2-line" }), "Encrypted. Nothing's saved unless you ask."))));
}

window.ConvoOnboard = ConvoOnboard;
