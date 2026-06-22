/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, shared primitives  (components.jsx)
   Exposed on window for the other babel scripts.
   ════════════════════════════════════════════════════════════════ */
const { useState, useEffect, useRef, useCallback } = React;
const PPD = window.PP_DATA;

/* ── Info vs advice label ──────────────────────────────────────── */
function InfoAdvice({ kind }) {
  const advice = kind === "advice";
  return (
    React.createElement("span", { className: "pp-iadv " + (advice ? "advice" : "info"), title: advice ? "A personal recommendation for you, suitability logic and disclosures apply." : "General information / education." },
      React.createElement("i", { className: advice ? "ri-user-star-line" : "ri-information-line" }),
      advice ? "Personal recommendation" : "Information"
    )
  );
}

/* ── Animated count-up number ──────────────────────────────────── */
function CountUp({ end, run = true, dur = 1100, prefix = "", suffix = "", decimals = 0, group = true }) {
  const [v, setV] = useState(run ? 0 : end);
  const started = useRef(false);
  useEffect(() => {
    if (!run || started.current) return;
    started.current = true;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setV(end); return; }
    const steps = Math.max(1, Math.round(dur / 16));
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      const k = Math.min(1, i / steps);
      setV(end * (1 - Math.pow(1 - k, 3)));
      if (k >= 1) { clearInterval(id); setV(end); }
    }, 16);
    return () => clearInterval(id);
  }, [run, end, dur]);
  let s = v.toFixed(decimals);
  if (group) {
    const parts = s.split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, "\u2019");
    s = parts.join(".");
  }
  return React.createElement("span", { className: "sq-num-tabular" }, prefix + s + suffix);
}

/* ── Typing indicator ──────────────────────────────────────────── */
function Typing() {
  return React.createElement("div", { className: "pp-typing" },
    React.createElement("span"), React.createElement("span"), React.createElement("span"));
}

/* ── Show-the-math expander ────────────────────────────────────── */
function ShowMath({ steps, rule, label = "Show the math" }) {
  return (
    React.createElement("details", { className: "pp-math" },
      React.createElement("summary", { className: "pp-math-sum" },
        React.createElement("i", { className: "ri-function-line" }),
        label,
        React.createElement("i", { className: "ri-arrow-down-s-line chev" })
      ),
      React.createElement("div", { className: "pp-math-bd" },
        steps.map((st, i) =>
          React.createElement("div", { className: "pp-math-step", key: i },
            React.createElement("div", { className: "pp-math-k" }, st[0]),
            React.createElement("div", { className: "pp-math-v", dangerouslySetInnerHTML: { __html: st[1] } })
          )
        ),
        rule && React.createElement("div", { className: "pp-math-rule" },
          React.createElement("i", { className: "ri-scales-3-line" }),
          "Rule applied · ", rule
        )
      )
    )
  );
}

/* ── Confidence chip ───────────────────────────────────────────── */
function ConfBars({ level }) {
  const n = level === "high" ? 3 : level === "med" ? 2 : 1;
  const txt = level === "high" ? "High confidence" : level === "med" ? "Medium" : "Low, please check";
  return (
    React.createElement("span", { className: "pp-conf " + level },
      React.createElement("span", { className: "bars" },
        [0, 1, 2].map((i) => React.createElement("i", { key: i, className: i < n ? "on" : "", style: { height: (6 + i * 3) + "px" } }))
      ),
      txt
    )
  );
}

/* ── Confirm / correct card ────────────────────────────────────── */
function ConfirmCorrect({ field, onResolve }) {
  const [state, setState] = useState("idle"); // idle | editing | done
  const [val, setVal] = useState(field.value);
  const low = field.level === "low";

  const confirm = (v) => { setVal(v); setState("done"); onResolve && onResolve(field.key, v); };

  return (
    React.createElement("div", { className: "pp-cc " + (state === "done" ? "is-done" : low ? "is-low" : "") },
      React.createElement("div", { className: "pp-cc-top" },
        React.createElement("div", null,
          React.createElement("div", { className: "pp-cc-lbl" }, field.label),
          React.createElement("div", { className: "pp-cc-val" },
            state === "done" ? val : field.value,
            React.createElement("span", { className: "u" }, field.unit)
          )
        ),
        React.createElement(ConfBars, { level: field.level })
      ),
      state === "idle" && React.createElement(React.Fragment, null,
        low && React.createElement("div", { className: "pp-cc-hint" },
          React.createElement("i", { className: "ri-error-warning-line" }),
          React.createElement("span", null, "This one came through faint. It looks like it may be ", React.createElement("b", null, field.correct + " " + field.unit), ", please confirm or correct before it enters your plan.")
        ),
        React.createElement("div", { className: "pp-cc-actions" },
          React.createElement("button", { className: "pp-cc-confirm", onClick: () => confirm(low ? field.value : field.value) },
            React.createElement("i", { className: "ri-check-line" }), low ? "Keep as read" : "Confirm"),
          React.createElement("button", { className: "pp-cc-edit", onClick: () => { setVal(low ? field.correct : field.value); setState("editing"); } },
            React.createElement("i", { className: "ri-pencil-line" }), low ? "Correct it" : "Edit")
        )
      ),
      state === "editing" && React.createElement(React.Fragment, null,
        React.createElement("div", { className: "pp-cc-edit-row" },
          React.createElement("input", { className: "pp-cc-input", value: val, onChange: (e) => setVal(e.target.value), autoFocus: true }),
          React.createElement("button", { className: "pp-cc-confirm", onClick: () => confirm(val) },
            React.createElement("i", { className: "ri-check-line" }), "Save")
        )
      ),
      state === "done" && React.createElement("div", { className: "pp-cc-actions" },
        React.createElement("span", { className: "pp-cc-confirmed" },
          React.createElement("i", { className: "ri-checkbox-circle-fill" }), "Confirmed, added to your plan"),
        React.createElement("button", { className: "pp-cc-edit", style: { marginLeft: "auto" }, onClick: () => setState("editing") },
          React.createElement("i", { className: "ri-pencil-line" }), "Edit")
      )
    )
  );
}

/* ── Lever / action card ───────────────────────────────────────── */
function Lever({ lever }) {
  const effortLbl = ["", "Low effort", "Medium effort", "Higher effort"][lever.effort];
  return (
    React.createElement("div", { className: "pp-lever" },
      React.createElement("div", { className: "pp-lever-top" },
        React.createElement("div", { className: "pp-lever-rank" }, lever.rank),
        React.createElement("div", { className: "pp-lever-id" },
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" } },
            React.createElement("h4", null, lever.title),
            React.createElement(InfoAdvice, { kind: lever.label })
          ),
          React.createElement("p", null, lever.desc)
        )
      ),
      React.createElement("div", { className: "pp-lever-impact" },
        React.createElement("div", { className: "pp-impact cash" },
          React.createElement("div", { className: "l" }, "Closes the gap by"),
          React.createElement("div", { className: "v" }, lever.impact > 0 ? "+" + lever.impact + " " : "", lever.impact > 0 ? React.createElement("small", null, "CHF/mo") : lever.impactNote)
        ),
        React.createElement("div", { className: "pp-impact effort" },
          React.createElement("div", { className: "l" }, "Effort"),
          React.createElement("div", { className: "v", style: { fontSize: "13px", color: "var(--fg-2)" } }, effortLbl,
            React.createElement("div", { className: "pp-effort-dots" },
              [1, 2, 3].map((i) => React.createElement("i", { key: i, className: i <= lever.effort ? "on" : "" }))
            )
          )
        )
      ),
      React.createElement("div", { className: "pp-lever-foot" },
        React.createElement(ShowMath, { steps: lever.math, rule: lever.rule })
      )
    )
  );
}

/* ── Disclosure strip ──────────────────────────────────────────── */
function Disclosure({ children }) {
  return React.createElement("div", { className: "pp-disc" },
    React.createElement("i", { className: "ri-shield-check-line" }),
    React.createElement("div", null, children)
  );
}

/* ── AI message block (with optional widget) ──────────────────── */
function AiMsg({ children, label, widget }) {
  return (
    React.createElement("div", { className: "pp-msg ai" },
      React.createElement("div", { className: "pp-ai-row" },
        React.createElement("div", { className: "pp-ai-mark" }, React.createElement("i", { className: "ri-sparkling-fill" })),
        React.createElement("div", { className: "pp-ai-bd" },
          label && React.createElement("div", { style: { marginBottom: "8px" } }, React.createElement(InfoAdvice, { kind: label })),
          children
        )
      ),
      widget && React.createElement("div", { className: "pp-ai-widget", style: { paddingLeft: "39px", width: "100%" } }, widget)
    )
  );
}
function UserMsg({ children }) {
  return React.createElement("div", { className: "pp-msg user" }, React.createElement("div", { className: "pp-bubble-user" }, children));
}

/* Reveal-on-mount wrapper (staggered, transform-only so content is never hidden) */
function Reveal({ delay = 0, children, className = "" }) {
  return React.createElement("div", { className: "pp-reveal " + className, style: { animationDelay: delay + "ms" } }, children);
}

Object.assign(window, {
  InfoAdvice, CountUp, Typing, ShowMath, ConfBars, ConfirmCorrect, Lever, Disclosure, AiMsg, UserMsg, Reveal,
});
