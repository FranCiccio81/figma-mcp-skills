/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, app shell, scene controller, monitoring home,
   data drawer, Tweaks.  app.jsx  (mounts to #root)
   ════════════════════════════════════════════════════════════════ */
const PD = window.PP_DATA;
const I18N = window.PP_I18N;
const RPP = window.PP_PERSONAS;
const recPlanId = (id) => { const p = (RPP[id].plans.find((x) => x.rec) || RPP[id].plans[0]); return p.id; };

/* scene map: phase index per scene */
const SCENES = [
  { id: "welcome", kind: "onb", phase: 0 },
  { id: "upload", kind: "onb", phase: 0 },
  { id: "confirm", kind: "onb", phase: 0 },
  { id: "gapfill", kind: "onb", phase: 0 },
  { id: "snapshot", kind: "work", phase: 1 },
  { id: "plan", kind: "work", phase: 1 },
  { id: "property", kind: "work", phase: 2 },
  { id: "stress", kind: "work", phase: 2 },
  { id: "monitor", kind: "full", phase: 3 },
  { id: "manual", kind: "onb", phase: 0 },
];
const PHASE_FIRST = [0, 4, 6, 8];

/* ── Monitoring home ───────────────────────────────────────────── */
function MonitorHome({ go, toast, personaId, plan, setPlan }) {
  const P0 = RPP[personaId] || RPP.bergerRey;
  const P = P0.future ? Object.assign({}, P0, P0.future) : P0;
  const mon = P.monitor || { nudges: [], deadlines: [], status: "Monitoring", nextReview: ", ", cadence: "" };
  const R = P.readiness;
  const actPlan = P.plans.find((x) => x.id === plan) || P.plans.find((x) => x.rec) || P.plans[0];
  const baseAge = (P.scenarios.find((s) => s.hl) || P.scenarios[1] || P.scenarios[0]).age;
  const [simAge, setSimAge] = React.useState(baseAge);
  const [monEvents, setMonEvents] = React.useState(null);
  React.useEffect(() => { setSimAge(baseAge); }, [P.id]);
  const onSimAge = (age, silent) => { setSimAge(age); if (!silent) { const s = P.scenarios.find((x) => x.age === age); toast && toast("Simulating retirement at " + age + (s ? " · " + s.inc + "/mo" : "")); } };
  const card = (icon, title, sub, children, extra) =>
    React.createElement("section", { className: "pp-band pp-mon-band" },
      React.createElement("div", { className: "pp-band-h" },
        React.createElement("div", { className: "l" }, React.createElement("i", { className: icon }), title),
        sub && React.createElement("div", { className: "s" }, sub)),
      React.createElement("div", { className: "pp-card pp-mon-card" + (extra ? " " + extra : "") }, children));
  return (
    React.createElement("div", { className: "pp-scene", style: { background: "var(--pp-shell-bg)" } },
      React.createElement("div", { className: "pp-monitor pp-mon" },
        React.createElement("div", { className: "pp-mon-head" },
          React.createElement("div", { className: "l" },
            React.createElement("div", { className: "eb" }, React.createElement("span", { className: "live" }), "Monitoring · always on", P.year ? React.createElement("span", { className: "yr" }, "· " + P.year) : null),
            React.createElement("h1", null, "Good evening, ", P.first, "."),
            React.createElement("p", null, P.year ? ("It's " + P.year + ", " + (P.ageLabel || "") + ". Four years of acting on your plan have moved things on. Here's where you stand now.") : "Your plan is activated and watched daily. Here's what's live, what needs you, and what's coming.")),
          React.createElement("div", { className: "r" },
            React.createElement("button", { className: "pp-btn pp-btn-dark", onClick: () => window.__ppOpenEvent && window.__ppOpenEvent() },
              React.createElement("i", { className: "ri-calendar-event-line" }), "Declare a life event"))),

        React.createElement("div", { className: "pp-mon-hero" },
          React.createElement(ReadinessHero, { persona: P, simAge, onSimAge, activePlan: plan, events: monEvents })),
        window.AdvisorGlance ? React.createElement("div", { style: { marginBottom: "18px" } }, React.createElement(window.AdvisorGlance, { screen: "monitoring", persona: P })) : null,

        React.createElement("div", { className: "pp-mon-timeline" },
          card("ri-calendar-event-line", "Your living timeline", "Same calendar as your plan, drag any event to re-project",
            React.createElement("div", { className: "pp-tlcard", style: { marginTop: "4px" } },
              React.createElement(EventTimeline, { persona: P, activePlan: plan, onPick: setPlan, toast, horizontal: true, onEvents: setMonEvents })))),

        React.createElement("div", { className: "pp-mon-grid" },
          React.createElement("div", { className: "pp-mon-main" },
            card("ri-notification-4-line", "Needs your attention", mon.nudges.length + " items", 
              React.createElement("div", { className: "pp-mon-nudges" },
                mon.nudges.map((n, i) =>
                  React.createElement("div", { className: "pp-nudge " + (n.label === "advice" ? "advice" : "info"), key: i },
                    React.createElement("div", { className: "pp-nudge-ic" }, React.createElement("i", { className: n.icon })),
                    React.createElement("div", { className: "pp-nudge-bd" },
                      React.createElement("div", { className: "meta" }, n.meta, React.createElement(InfoAdvice, { kind: n.label })),
                      React.createElement("h4", null, n.h),
                      React.createElement("p", null, n.p),
                      React.createElement("div", { className: "pp-nudge-act" },
                        React.createElement("button", { className: "pp-btn pp-btn-brand pp-btn-sm", onClick: () => toast(n.cta + ", opened") }, n.cta),
                        n.deadline && React.createElement("span", { className: "pp-nudge-deadline-tag" }, React.createElement("i", { className: "ri-time-line" }), n.deadline)))))))),
            window.ProductRecs ? card("ri-price-tag-3-line", "Next best products", "Matched to your figures", React.createElement(window.ProductRecs, { persona: P, limit: 2 })) : null,

          React.createElement("div", { className: "pp-mon-side" },
            card("ri-stack-line", "Active strategy", actPlan.name,
              React.createElement("div", { className: "pp-mon-strat" },
                React.createElement("div", { className: "row" }, React.createElement("span", { className: "l" }, "Projected income"), React.createElement("span", { className: "v ppv2-sensitive" }, actPlan.income)),
                React.createElement("div", { className: "row" }, React.createElement("span", { className: "l" }, "Retire at"), React.createElement("span", { className: "v" }, actPlan.retireAge)),
                React.createElement("div", { className: "row" }, React.createElement("span", { className: "l" }, "Risk · score"), React.createElement("span", { className: "v" }, actPlan.risk, " · ", actPlan.score)),
                React.createElement("button", { className: "pp-btn pp-btn-ghost pp-btn-sm", style: { marginTop: "12px", width: "100%" }, onClick: () => go(4) },
                  React.createElement("i", { className: "ri-pencil-line" }), "Adjust in your plan"))),
            card("ri-alarm-warning-line", "Upcoming deadlines", "Don't leave money on the table",
              React.createElement("div", { className: "pp-mon-deadlines" },
                mon.deadlines.map((d, i) =>
                  React.createElement("div", { className: "pp-deadline", key: i },
                    React.createElement("div", { className: "pp-deadline-date" },
                      React.createElement("div", { className: "m" }, d.m), React.createElement("div", { className: "d" }, d.d)),
                    React.createElement("div", { className: "pp-deadline-bd" },
                      React.createElement("div", { className: "t" }, d.t), React.createElement("div", { className: "d" }, d.s)),
                    d.amt && React.createElement("div", { className: "pp-deadline-amt ppv2-sensitive" }, d.amt))))),
            React.createElement("section", { className: "pp-band pp-mon-band" },
              React.createElement("div", { className: "pp-band-h" },
                React.createElement("div", { className: "l" }, React.createElement("i", { className: "ri-user-heart-line" }), "When a human steps in")),
              React.createElement("div", { className: "pp-handoff pp-mon-handoff" },
                React.createElement("div", { className: "pp-handoff-av" }, React.createElement("i", { className: "ri-user-heart-line" })),
                React.createElement("div", { className: "pp-handoff-bd" },
                  React.createElement("h4", null, "A human, when it matters"),
                  React.createElement("p", null, "Irreversible moves, capital vs annuity, big life events, are reviewed with a Swissquote advisor, brief already prepared."),
                  React.createElement("button", { className: "pp-btn pp-btn-ghost pp-btn-sm", style: { marginTop: "10px" }, onClick: () => window.__ppOpenConsult && window.__ppOpenConsult() },
                    React.createElement("i", { className: "ri-calendar-check-line" }), "Book a 30-min handoff"))))))
      ))
  );
}

/* ── Data & privacy drawer ─────────────────────────────────────── */
function DataDrawer({ open, onClose, toast }) {
  const [mount, setMount] = React.useState(open);
  const [show, setShow] = React.useState(false);
  const [consent, setConsent] = React.useState({ process: true, train: false, outreach: true });
  React.useEffect(() => {
    if (open) { setMount(true); requestAnimationFrame(() => requestAnimationFrame(() => setShow(true))); }
    else { setShow(false); const t = setTimeout(() => setMount(false), 420); return () => clearTimeout(t); }
  }, [open]);
  if (!mount) return null;
  const rows = [
    { ic: "ri-eye-line", t: "View all your data", d: "Everything I hold, by pillar and document", danger: false },
    { ic: "ri-pencil-line", t: "Correct a value", d: "Override any figure, OCR never wins over you", danger: false },
    { ic: "ri-download-2-line", t: "Export (portability)", d: "Download your plan & data as JSON or PDF", danger: false },
    { ic: "ri-delete-bin-6-line", t: "Delete everything", d: "Erase your account and all documents", danger: true },
  ];
  return (
    React.createElement(React.Fragment, null,
      React.createElement("div", { className: "pp-scrim" + (show ? " in" : ""), onClick: onClose }),
      React.createElement("div", { className: "pp-drawer" + (show ? " in" : "") },
        React.createElement("div", { className: "pp-drawer-head" },
          React.createElement("h3", null, "Your data"),
          React.createElement("button", { className: "pp-drawer-x", onClick: onClose }, React.createElement("i", { className: "ri-close-line" }))),
        React.createElement("p", { className: "pp-drawer-sub" }, "You're always in control. View, correct, export or delete anything Pension Partner holds, your rights under the revised Swiss Data Protection Act (revDPA)."),
        React.createElement("div", { className: "pp-drawer-sec" },
          React.createElement("h4", null, "Your rights"),
          rows.map((r, i) => React.createElement("div", { className: "pp-data-row" + (r.danger ? " danger" : ""), key: i, onClick: () => toast(r.t + (r.danger ? ", confirm required" : ", opened")) },
            React.createElement("div", { className: "pp-data-row-ic" }, React.createElement("i", { className: r.ic })),
            React.createElement("div", { className: "pp-data-row-bd" }, React.createElement("div", { className: "t" }, r.t), React.createElement("div", { className: "d" }, r.d)),
            React.createElement("i", { className: "ri-arrow-right-s-line go" })))),
        React.createElement("div", { className: "pp-drawer-sec" },
          React.createElement("h4", null, "Consent"),
          [
            { k: "process", t: "Process my pension data", d: "Required to build and keep your plan", lock: true },
            { k: "train", t: "Help improve the models", d: "Off by default, never without separate consent", lock: false },
            { k: "outreach", t: "Proactive nudges & outreach", d: "Deadlines, rule changes and plan drift", lock: false },
          ].map((c) => React.createElement("div", { className: "pp-consent", key: c.k },
            React.createElement("div", { className: "pp-consent-bd" },
              React.createElement("div", { className: "t" }, c.t), React.createElement("div", { className: "d" }, c.d)),
            React.createElement("button", { className: "pp-switch" + (consent[c.k] ? " on" : ""), disabled: c.lock, onClick: () => !c.lock && setConsent((s) => ({ ...s, [c.k]: !s[c.k] })) })))),
        React.createElement("div", { className: "pp-disc" },
          React.createElement("i", { className: "ri-map-pin-line" }),
          React.createElement("div", null, "Data hosted in Switzerland · encrypted at rest · access-logged · retention per regulatory policy. Every advice turn is recorded in your immutable audit log."))
      ))
  );
}

/* ── Work-scene conversation pane ──────────────────────────────── */
function ConvoPane({ scene, go, toast, persona, onToggleBoard }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const el = ref.current; if (!el) return;
    const iv = setInterval(() => { el.scrollTop = el.scrollHeight; }, 320);
    const stop = setTimeout(() => clearInterval(iv), 9000);
    return () => { clearInterval(iv); clearTimeout(stop); };
  }, [scene]);
  let body = null;
  if (scene === 4) body = React.createElement(SnapshotConvo, { go, persona });
  else if (scene === 5) body = React.createElement(PlanConvo, { go });
  else if (scene === 6) body = React.createElement(PropertyConvo, { go });
  else if (scene === 7) body = React.createElement(StressConvo, { go, toast });
  return (
    React.createElement("div", { className: "pp-convo" },
      React.createElement("div", { className: "pp-convo-head" },
        React.createElement("div", { className: "pp-convo-mark" }, React.createElement("i", { className: "ri-sparkling-fill" })),
        React.createElement("div", { className: "id" },
          React.createElement("div", { className: "nm" }, "Pension Partner"),
          React.createElement("div", { className: "st" }, React.createElement("span", { className: "dot" }), "Monitoring your plan · always on")),
        React.createElement("button", { className: "pp-iconbtn", title: "Expand to dashboard", onClick: onToggleBoard || (() => {}) }, React.createElement("i", { className: "ri-layout-grid-line" }))),
      React.createElement("div", { className: "pp-convo-scroll", ref },
        React.createElement("div", { className: "pp-convo-inner" }, body)),
      React.createElement("div", { className: "pp-composer" },
        React.createElement("div", { className: "pp-composer-inner" },
          React.createElement("div", { className: "pp-inputbar" },
            React.createElement("input", { placeholder: I18N.EN.placeholder }),
            React.createElement("button", { className: "pp-send", onClick: () => toast("In this demo, tap a suggested reply above") }, React.createElement("i", { className: "ri-arrow-up-line" }))),
          React.createElement("div", { className: "pp-composer-disc" }, I18N.EN.disclaimer)))
    )
  );
}

/* ── Top bar ───────────────────────────────────────────────────── */
function TopBar({ phase, go, lang, setLang, onData, onRestart, v2, personaId, setPersona, onAddDoc, onLogin }) {
  const t = I18N[lang];
  const onboarding = !v2 && phase === 0;
  return (
    React.createElement("div", { className: "pp-topbar" },
      React.createElement("div", { className: "pp-brand" },
        React.createElement("div", { className: "pp-brand-mark" },
          React.createElement("svg", { viewBox: "0 0 48 48" }, React.createElement("path", { d: "M24 12l-9 15h7l-3 9 9-15h-7l3-9z", fill: "#fff" }))),
        React.createElement("div", { className: "pp-brand-tx" },
          React.createElement("div", { className: "wm" }, "swissquote"),
          React.createElement("div", { className: "pr" }, "Pension Partner"))),
      v2
        ? React.createElement("div", { style: { margin: "0 auto" } })
        : React.createElement("div", { className: "pp-stages" },
          t.stages.map((s, i) =>
            React.createElement(React.Fragment, { key: i },
              i > 0 && React.createElement("div", { className: "pp-stage-sep" }),
              React.createElement("button", {
                className: "pp-stage" + (phase === i ? " is-active" : phase > i ? " is-done" : ""),
                onClick: () => go(PHASE_FIRST[i])
              },
                React.createElement("span", { className: "n" }, phase > i ? React.createElement("i", { className: "ri-check-line" }) : i + 1),
                s)))),
      React.createElement("div", { className: "pp-top-r" },
        onboarding
          ? React.createElement(React.Fragment, null,
            React.createElement("div", { className: "pp-lang" },
              ["EN", "FR"].map((l) => React.createElement("button", { key: l, className: lang === l ? "on" : "", onClick: () => setLang(l) }, l))),
            React.createElement("button", { className: "pp-btn pp-btn-brand pp-btn-sm", onClick: onLogin }, React.createElement("i", { className: "ri-login-circle-line" }), "Log in"))
          : React.createElement(React.Fragment, null,
            React.createElement(ProfileMenu, { personaId, lang, setLang, onData, onRestart })))
    )
  );
}

/* ── Profile menu (avatar → popover with language, data, restart) ── */
function ProfileMenu({ personaId, lang, setLang, onData, onRestart }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!open) return;
    const away = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  const P = RPP[personaId];
  return (
    React.createElement("div", { className: "pp-profile", ref },
      React.createElement("button", { className: "pp-avatar" + (open ? " on" : ""), onClick: () => setOpen((o) => !o), title: "Profile", "aria-expanded": open }, P.initials),
      open && React.createElement("div", { className: "pp-profile-menu" },
        React.createElement("div", { className: "pp-profile-id" },
          React.createElement("span", { className: "av" }, P.initials),
          React.createElement("div", { className: "tx" },
            React.createElement("div", { className: "nm" }, P.name),
            React.createElement("div", { className: "sb" }, P.flag + " · " + P.canton))),
        React.createElement("div", { className: "pp-profile-row lang" },
          React.createElement("span", { className: "l" }, React.createElement("i", { className: "ri-translate-2" }), "Language"),
          React.createElement("div", { className: "pp-lang sm" },
            ["EN", "FR"].map((l) => React.createElement("button", { key: l, className: lang === l ? "on" : "", onClick: () => setLang(l) }, l)))),
        React.createElement("button", { className: "pp-profile-item", onClick: () => { setOpen(false); onData(); } },
          React.createElement("i", { className: "ri-shield-keyhole-line" }), "Your data & privacy"),
        React.createElement("button", { className: "pp-profile-item", onClick: () => { setOpen(false); onRestart(); } },
          React.createElement("i", { className: "ri-restart-line" }), "Restart demo"))));
}

/* ── Floating prototype selector (use case + scenario) ─────────────
   A draggable, collapsible demo control. Lifts persona + scenario
   switching OUT of the product header so the chrome stays realistic. */
function ProtoSelector({ personaId, onPersona, prospect, onProspect, go, mobileView, setViewport }) {
  const [open, setOpen] = React.useState(() => localStorage.getItem("pp_proto_open") !== "0");
  const [pos, setPos] = React.useState(() => {
    try { const p = JSON.parse(localStorage.getItem("pp_proto_pos")); if (p && typeof p.x === "number") return p; } catch (e) {}
    return { x: 20, y: 96 };
  });
  const drag = React.useRef(null);
  React.useEffect(() => { localStorage.setItem("pp_proto_open", open ? "1" : "0"); }, [open]);

  const onDown = (e) => {
    const startX = e.clientX, startY = e.clientY, base = { ...pos };
    drag.current = { moved: false };
    const move = (ev) => {
      const dx = ev.clientX - startX, dy = ev.clientY - startY;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.current.moved = true;
      const w = window.innerWidth, h = window.innerHeight;
      setPos({ x: Math.max(8, Math.min(w - 80, base.x + dx)), y: Math.max(72, Math.min(h - 60, base.y + dy)) });
    };
    const up = () => {
      window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
      setPos((p) => { localStorage.setItem("pp_proto_pos", JSON.stringify(p)); return p; });
    };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const toggle = () => { if (!drag.current || !drag.current.moved) setOpen((o) => !o); };

  const personas = RPP.order.filter((id) => id !== "live").map((id) => {
    const p = RPP[id];
    return { id, label: p.first.split(" ")[0] + (p.kind === "couple" ? " & C." : ""), sub: p.canton, flag: p.flag };
  });
  const liveBuilt = !!RPP.live;
  const onLive = () => {
    if (liveBuilt) { onPersona("live"); return; }
    window.__ppSetLiveMode && window.__ppSetLiveMode(true);
    window.__ppSetProspect && window.__ppSetProspect(false);
    if (window.__ppGo) window.__ppGo(0);
  };

  return (
    React.createElement("div", { className: "pp-proto" + (open ? " is-open" : ""), style: { left: pos.x + "px", top: pos.y + "px" } },
      React.createElement("button", { className: "pp-proto-handle", onPointerDown: onDown, onClick: toggle, title: "Drag to move · click to expand" },
        React.createElement("i", { className: "ri-flask-line" }),
        React.createElement("span", { className: "lbl" }, "Prototype"),
        React.createElement("i", { className: "chev ri-arrow-down-s-line" })),
      open && React.createElement("div", { className: "pp-proto-body" },
        React.createElement("div", { className: "pp-proto-sec" },
          React.createElement("div", { className: "pp-proto-lbl" }, "Scenario"),
          React.createElement("div", { className: "pp-proto-seg" },
            React.createElement("button", { className: !prospect ? "on" : "", onClick: () => onProspect(false) },
              React.createElement("i", { className: "ri-shield-user-line" }), "Client"),
            React.createElement("button", { className: prospect ? "on" : "", onClick: () => onProspect(true) },
              React.createElement("i", { className: "ri-lock-2-line" }), "Prospect"))),
        React.createElement("div", { className: "pp-proto-sec" },
          React.createElement("div", { className: "pp-proto-lbl" }, "Viewport"),
          React.createElement("div", { className: "pp-proto-seg" },
            React.createElement("button", { className: !mobileView ? "on" : "", onClick: () => setViewport && setViewport(false) },
              React.createElement("i", { className: "ri-computer-line" }), "Desktop"),
            React.createElement("button", { className: mobileView ? "on" : "", onClick: () => setViewport && setViewport(true) },
              React.createElement("i", { className: "ri-smartphone-line" }), "Mobile"))),
        React.createElement("div", { className: "pp-proto-foot" }, "Demo controls · not part of the product")))
  );
}

/* ── Root ──────────────────────────────────────────────────────── */
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "version": "V1 \u00b7 Workspace",
  "snapshotTake": "Pillars",
  "language": "EN",
  "motion": true
}/*EDITMODE-END*/;

const VERSIONS = ["V1 \u00b7 Workspace", "V2 \u00b7 Readiness"];

/* ── AI engine badge + BYOK key modal (Pass 1) ─────────────────── */
function AIEngineGate() {
  const [mode, setMode] = React.useState(window.ppAI ? window.ppAI.mode : null);
  const [needKey, setNeedKey] = React.useState(false);
  const [key, setKey] = React.useState("");
  const [err, setErr] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => {
    if (!window.ppAI) return;
    const offC = window.ppAI.on("change", (m) => setMode(m));
    const offN = window.ppAI.on("keyNeeded", () => { if (window.ppAI.needsKey()) setNeedKey(true); });
    const offE = window.ppAI.on("keyError", (msg) => { setErr(msg || "Your key was rejected."); setNeedKey(true); });
    if (window.ppAI.needsKey()) setNeedKey(true);
    return () => { offC(); offN(); offE(); };
  }, []);
  const integrated = window.ppAI && window.ppAI.mode === "integrated";
  const connect = () => {
    setBusy(true); setErr(null);
    window.ppAI.connect(key).then(() => { setBusy(false); setNeedKey(false); setKey(""); })
      .catch((e) => { setBusy(false); setErr(String(e.message || e)); });
  };
  return React.createElement(React.Fragment, null,
    React.createElement("div", { className: "pp-engine-badge" + (integrated ? " ok" : ""), onClick: function(){ if(!integrated) setNeedKey(true); }, style: integrated ? null : { cursor: "pointer" }, title: integrated ? "" : "Manage engine / key" },
      React.createElement("span", { className: "d" }), window.ppAI ? window.ppAI.badgeLabel() : "Engine: …"),
    (needKey && !integrated) ? React.createElement("div", { className: "ppm-modal-scrim in", style: { zIndex: 400 } },
      React.createElement("div", { className: "ppm-modal", style: { width: 460 }, onClick: (e) => e.stopPropagation() },
        React.createElement("div", { className: "ppm-modal-head" },
          React.createElement("span", { className: "ppm-modal-ic" }, React.createElement("i", { className: "ri-key-2-line" })),
          React.createElement("div", { className: "tx" },
            React.createElement("h3", null, "Connect your analysis engine"),
            React.createElement("p", null, "This shared copy runs on your own Anthropic key. It's remembered in this browser for next time, sent only to Anthropic, and you can Forget it anytime \u2014 or explore the demo with no key."))),
        React.createElement("div", { className: "ppm-modal-bd" },
          React.createElement("label", { className: "pp-mf-field" },
            React.createElement("span", { className: "lab" }, "Anthropic API key"),
            React.createElement("span", { className: "pp-mf-input" },
              React.createElement("span", { className: "dot", style: { width: 8, height: 8, borderRadius: 999, marginLeft: 12, background: key ? "var(--ontrack)" : "var(--line-1)", flex: "0 0 auto" } }),
              React.createElement("input", { type: "password", placeholder: "sk-ant-\u2026", value: key, autoFocus: true, onChange: (e) => setKey(e.target.value), onKeyDown: (e) => { if (e.key === "Enter") connect(); } }))),
          err ? React.createElement("div", { className: "ppm-modal-err" }, React.createElement("i", { className: "ri-error-warning-line" }), React.createElement("span", null, err)) : null,
          React.createElement("div", { className: "ppm-modal-foot", style: { marginTop: 16 } },
            React.createElement("div", { style: { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" } }, React.createElement("button", { className: "pp-btn pp-btn-ghost pp-btn-sm", onClick: function(){ window.__ppSimMode = true; setNeedKey(false); if (window.__ppToast) window.__ppToast("Simulation mode \u2014 sample data, no key needed"); } }, React.createElement("i", { className: "ri-play-circle-line" }), "Explore demo \u2014 no key"), (window.ppAI && window.ppAI.ready && !integrated) ? React.createElement("button", { className: "pp-btn pp-btn-ghost pp-btn-sm", onClick: function(){ window.ppAI.disconnect(); setErr(null); } }, React.createElement("i", { className: "ri-delete-bin-line" }), "Forget key") : null, React.createElement("span", { style: { font: "400 11px/1.4 var(--font-body)", color: "var(--fg-4)" } }, React.createElement("i", { className: "ri-shield-check-line", style: { verticalAlign: "-2px", marginRight: 5 } }), "Remembered in this browser")),
            React.createElement("button", { className: "pp-btn pp-btn-brand pp-btn-sm", disabled: busy || !key, onClick: connect },
              React.createElement("i", { className: busy ? "ri-loader-4-line" : "ri-link" }), busy ? "Connecting\u2026" : "Connect"))))) : null);
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [scene, setScene] = React.useState(() => {
    const s = parseInt(localStorage.getItem("pp_scene") || "0", 10);
    return isNaN(s) ? 0 : Math.max(0, Math.min(8, s));
  });
  const [drawer, setDrawer] = React.useState(false);
  const [toastMsg, setToastMsg] = React.useState(null);
  const [personaId, setPersonaId] = React.useState(() => { const s = localStorage.getItem("pp_persona"); return (s && RPP.order.indexOf(s) >= 0) ? s : RPP.order[0]; });
  const [plan, setPlan] = React.useState(() => { const s = localStorage.getItem("pp_persona"); return recPlanId((s && RPP.order.indexOf(s) >= 0) ? s : RPP.order[0]); });
  const [taxOpen, setTaxOpen] = React.useState(false);
  const [consultOpen, setConsultOpen] = React.useState(false);
  const [eventOpen, setEventOpen] = React.useState(false);
  const [loginOpen, setLoginOpen] = React.useState(false);
  const [methodOpen, setMethodOpen] = React.useState(false);
  const [prospect, setProspect] = React.useState(() => localStorage.getItem("pp_prospect") === "1");
  const [enrichTick, setEnrichTick] = React.useState(0);
  const [boardOverride, setBoardOverride] = React.useState(null); // null = use the scene's natural default
  const [mobileView, setMobileView] = React.useState(() => localStorage.getItem("pp_viewport") === "mobile");
  const setViewport = React.useCallback((m) => { localStorage.setItem("pp_viewport", m ? "mobile" : "desktop"); setMobileView(!!m); }, []);
  React.useEffect(() => { window.__ppSetMobile = setViewport; }, [setViewport]);
  React.useEffect(() => {
    const apply = () => { if (window.innerWidth <= 640) { const r = document.querySelector(".pp"); if (r) r.classList.add("pp-mobile"); } };
    apply(); window.addEventListener("resize", apply); return () => window.removeEventListener("resize", apply);
  }, []);
  const toastT = React.useRef(null);
  const setBoardP = (v) => setBoardOverride(v);
  const variation = t.snapshotTake === "Bridge" ? "B" : "A";
  const lang = t.language === "FR" ? "FR" : "EN";
  const isV2 = (t.version || "").indexOf("V2") === 0;

  const go = React.useCallback((n) => {
    setScene(n); localStorage.setItem("pp_scene", String(n));
    setBoardOverride(null); // each scene resumes its natural default layout
    const sc = document.querySelector(".pp-body"); if (sc) sc.scrollTop = 0;
  }, []);
  React.useEffect(() => { window.__ppGo = go; }, [go]);
  React.useEffect(() => { window.__ppToast = toast; }, [toast]);
  React.useEffect(() => { window.__ppOpenTax = () => setTaxOpen(true); }, []);
  React.useEffect(() => { window.__ppOpenConsult = () => setConsultOpen(true); }, []);
  React.useEffect(() => { window.__ppOpenEvent = () => setEventOpen(true); }, []);
  React.useEffect(() => { window.__ppOpenLogin = () => setLoginOpen(true); }, []);
  React.useEffect(() => { window.__ppOpenMethod = () => setMethodOpen(true); }, []);
  React.useEffect(() => { window.__ppSetProspect = (v) => { localStorage.setItem("pp_prospect", v ? "1" : "0"); setProspect(!!v); }; }, []);
  React.useEffect(() => {
    window.__ppSetLiveMode = (v) => { window.__ppLiveMode = !!v; };
    window.__ppActivateLive = (p) => {
      window.PP_PERSONAS.live = p;
      if (RPP.order.indexOf("live") < 0) RPP.order.push("live");
      window.__ppLiveMode = true;
      window.__ppRecCache = {}; window.__ppInsightCache = {}; // doc -> recompute recommendations + insights
      localStorage.setItem("pp_persona", "live"); setPersonaId("live"); setPlan(recPlanId("live"));
      const c = window.PP_CONFIDENCE ? window.PP_CONFIDENCE.compute(p).score : null;
      toast(c != null ? ("Plan built from your document, " + c + "% confidence") : "Live plan built from your document");
      // personalise the suggested actions + key insights from THIS document's figures
      if (window.PP_LIVE && window.PP_LIVE.enrich) {
        window.PP_LIVE.enrich(p).then(() => { window.__ppRecCache = {}; window.__ppInsightCache = {}; setEnrichTick((n) => n + 1); }).catch(() => {});
      }
    };
  }, []);
  const doLogin = React.useCallback((brand) => { localStorage.setItem("pp_prospect", "0"); setProspect(false); setBoardP(false); go(4); toast((brand === "yuh" ? "Yuh" : brand === "pension" ? "Pension Partner" : "Swissquote") + " connected, your full plan is unlocked"); }, []);
  const toast = React.useCallback((m) => {
    setToastMsg(m); clearTimeout(toastT.current); toastT.current = setTimeout(() => setToastMsg(null), 2600);
  }, []);
  const setVariation = (v) => setTweak("snapshotTake", v === "B" ? "Bridge" : "Pillars");
  const setLang = (l) => setTweak("language", l);
  const changePersona = React.useCallback((id) => { if (id !== "live") window.__ppLiveMode = false; localStorage.setItem("pp_persona", id); setPersonaId(id); setPlan(recPlanId(id)); }, []);
  const restart = () => { go(0); toast("Demo restarted"); };

  const cur = SCENES[scene];
  const ti = I18N[lang];
  // Plan + Scenarios stages default to the full dashboard layout; the snapshot
  // intro keeps chat. Manual toggle overrides per scene.
  const board = boardOverride !== null ? boardOverride : (cur.id === "plan" || cur.id === "snapshot" || cur.id === "property" || cur.id === "stress");

  let bodyEl = null;
  if (isV2) bodyEl = React.createElement(ReadinessApp, { go, toast, lang, personaId, setPersonaId: changePersona, activePlan: plan, setPlan, openTax: () => setTaxOpen(true) });
  else if (cur.id === "welcome") bodyEl = React.createElement(WelcomeScene, { t: ti, go });
  else if (cur.id === "upload") bodyEl = React.createElement(UploadScene, { go });
  else if (cur.id === "confirm") bodyEl = React.createElement(ConfirmScene, { go });
  else if (cur.id === "gapfill") bodyEl = React.createElement(GapfillScene, { go, persona: PD.persona });
  else if (cur.id === "manual") bodyEl = React.createElement(window.ConvoOnboard || ManualEntryScene, { go, toast });
  else if (cur.kind === "work") {
    const wPlan = RPP[personaId].plans.find((x) => x.id === plan) ? plan : recPlanId(personaId);
    const wPick = (id) => { setPlan(id); toast("Active plan: " + (RPP[personaId].plans.find((x) => x.id === id) || {}).name); };
    const isScenarios = cur.id === "property" || cur.id === "stress";
    const onActivate = () => go(8); // activation now lives on the Plan stage and leads to the Dashboard
    if (board) {
      bodyEl = React.createElement(LivingDashboard, { variation, setVariation, built: true, onOpenLevers: () => go(5), persona: RPP[personaId], activePlan: wPlan, onPick: wPick, toast, board: true, onToggleBoard: () => setBoardP(false), scenarios: isScenarios, onActivate, prospect: prospect && !isScenarios });
    } else {
      bodyEl = React.createElement("div", { className: "pp-work" + (scene === 5 ? " wide" : "") },
        React.createElement(ConvoPane, { scene, go, toast, persona: PD.persona, onToggleBoard: () => setBoardP(true) }),
        React.createElement(LivingDashboard, { variation, setVariation, built: true, onOpenLevers: () => go(5), persona: RPP[personaId], activePlan: wPlan, onPick: wPick, toast, board: false, onToggleBoard: () => setBoardP(true), scenarios: isScenarios, onActivate }));
    }
  } else if (cur.id === "monitor") bodyEl = React.createElement(MonitorHome, { go, toast, personaId, plan, setPlan });

  return (
    React.createElement("div", { className: "pp" + (t.motion ? "" : " pp-static") + (mobileView ? " pp-mobile pp-framed" : "") },
      React.createElement(TopBar, { phase: cur.phase, go, lang, setLang, onData: () => setDrawer(true), onRestart: restart, v2: isV2, personaId, setPersona: changePersona, onAddDoc: () => setTaxOpen(true), onLogin: () => setLoginOpen(true) }),
      React.createElement("div", { className: "pp-body" },
        React.createElement("div", { key: isV2 ? "v2" : scene, style: { position: "absolute", inset: 0 } }, bodyEl)),
      React.createElement(DataDrawer, { open: drawer, onClose: () => setDrawer(false), toast }),
      React.createElement(TaxUploadModal, { open: taxOpen, onClose: () => setTaxOpen(false), persona: RPP[personaId], toast, onDone: () => { if (!isV2 && scene <= 1) go(4); } }),
      React.createElement(ConsultantModal, { open: consultOpen, onClose: () => setConsultOpen(false), persona: RPP[personaId], toast }),
      React.createElement(LifeEventModal, { open: eventOpen, onClose: () => setEventOpen(false), persona: RPP[personaId], toast }),
      React.createElement(LoginModal, { open: loginOpen, onClose: () => setLoginOpen(false), onLogin: doLogin, toast }),
      React.createElement(MethodChoiceModal, { open: methodOpen, onClose: () => setMethodOpen(false),
        onUpload: () => { setMethodOpen(false); window.__ppSetProspect && window.__ppSetProspect(true); window.__ppOpenTax && window.__ppOpenTax(); },
        onManual: () => { setMethodOpen(false); window.__ppSetProspect && window.__ppSetProspect(true); go(9); } }),
      !isV2 && cur.phase !== 0 && React.createElement(AIAssistant, { persona: RPP[personaId], lang }),
      React.createElement(AIEngineGate, null),
      toastMsg && React.createElement("div", { className: "pp-toast-wrap" },
        React.createElement("div", { className: "pp-toast" }, React.createElement("i", { className: "ri-checkbox-circle-fill" }), toastMsg)),
      React.createElement(TweaksPanel, null,
        React.createElement(TweakSection, { label: "Version" }),
        React.createElement(TweakRadio, { label: "Experience", value: t.version, options: VERSIONS, onChange: (v) => setTweak("version", v) }),
        React.createElement(TweakSection, { label: "Display" }),
        React.createElement(TweakRadio, { label: "Language", value: t.language, options: ["EN", "FR"], onChange: (v) => setTweak("language", v) }),
        React.createElement(TweakToggle, { label: "Motion & reveals", value: t.motion, onChange: (v) => setTweak("motion", v) }),
        React.createElement(TweakSection, { label: "Prototype" }),
        React.createElement(TweakRadio, { label: "Use case", value: RPP[personaId].first.split(" ")[0], options: RPP.order.map((id) => RPP[id].first.split(" ")[0]), onChange: (v) => { const id = RPP.order.find((x) => RPP[x].first.split(" ")[0] === v); if (id) changePersona(id); } }),
        React.createElement(TweakRadio, { label: "Scenario", value: prospect ? "Prospect" : "Client", options: ["Client", "Prospect"], onChange: (v) => { const p = v === "Prospect"; window.__ppSetProspect(p); if (p) { setBoardP(null); go(4); } } }),
        React.createElement(TweakToggle, { label: "Mobile viewport", value: mobileView, onChange: (v) => setViewport(v) }))
    )
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(React.createElement(App));
