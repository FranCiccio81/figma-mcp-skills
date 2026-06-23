/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, AI assistant (assistant.jsx)
   A always-reachable "Ask Pension AI" assistant: text + voice. Answers
   anything about retirement and the active persona's own situation via
   window.claude.complete, with a graceful scripted fallback. Voice in
   via the Web Speech API (SpeechRecognition); optional read-aloud out
   via speechSynthesis. window.AIAssistant + window.__ppOpenAI()
   ════════════════════════════════════════════════════════════════ */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

function personaContext(P) {
  if (!P) return "";
  const R = P.readiness || {};
  const adv = (P.advisories || []).slice(0, 4).map((a, i) => `${i + 1}. ${a.title}${a.benefit ? ", " + a.benefit : ""}`).join("\n");
  const plans = (P.plans || []).map((pl) => `${pl.name} (score ${pl.score}, ${pl.income}, ${pl.risk} risk)`).join("; ");
  return [
    `The user you are helping is a Swissquote Pension Partner customer.`,
    `Profile: ${P.name}, age ${P.age}, ${P.status}, canton ${P.canton}.`,
    `Gross income ${P.grossIncome ? "CHF " + P.grossIncome.toLocaleString("de-CH") : "n/a"}; target monthly retirement income CHF ${(P.targetMonthly || 0).toLocaleString("de-CH")}.`,
    `Readiness score ${R.score}/100, "${R.verdict}". ${R.sub || ""}`,
    `Today's projected monthly pension CHF ${(R.today || 0).toLocaleString("de-CH")}, reachable CHF ${(R.planned || 0).toLocaleString("de-CH")}.`,
    `Available strategies: ${plans}.`,
    `Top recommended actions:\n${adv}`,
  ].join("\n");
}

function fallbackAnswer(q, P) {
  const s = (P && P.readiness) ? P.readiness : {};
  const t = q.toLowerCase();
  if (/retire (at|by)?\s*\d|early|age/.test(t)) return `Based on your plan, retiring earlier lowers your monthly pension and your readiness score, while waiting a couple of years lifts both. Use the retirement-age tiles in your snapshot to see the exact figures for your situation.`;
  if (/gap|close|improve|increase|better|score/.test(t)) return `Your biggest levers are maxing your pillar 3a and a staged pension-fund buy-in, together they move your score the most for the least effort. They're listed in "My top moves" in your snapshot.`;
  if (/3a|pillar|buy-?in|tax/.test(t)) return `A pillar-3a contribution is deducted from taxable income and grows tax-sheltered; a 2nd-pillar buy-in does the same and lifts your future pension. Staggering withdrawals across tax years reduces the one-off withdrawal tax.`;
  if (/lump|annuity|capital/.test(t)) return `At retirement you choose between taking your 2nd-pillar capital as a lump sum (flexible, you manage it) or a lifelong annuity (guaranteed income, no market risk). Most people blend the two, an advisor reviews it with you when the time comes.`;
  return `I can help with your retirement plan${P ? ", your readiness is " + s.score + "/100 (" + (s.verdict || "") + ")" : ""}. Ask me about closing your gap, retiring earlier, pillar 3a, buy-ins, or the lump-sum vs annuity choice.`;
}

function fallbackSuggestions(q, widget) {
  const byW = {
    gauge: ["How do I close my gap?", "Can I retire earlier?", "What's my biggest risk?"],
    scenarios: ["Why does waiting help?", "Show my top moves", "Can I retire at 62?"],
    projection: ["What lifts this curve?", "Compare my strategies", "Lump sum or annuity?"],
    plans: ["Which fits me best?", "What changes if I switch?", "Show my projection"],
    annuity: ["Which is better for me?", "How is each taxed?", "Can I blend both?"],
    kpi: ["How do I improve these?", "Show my top moves", "Explain my buy-in capacity"],
    moves: ["Explain pillar 3a buy-ins", "How many points each?", "What if I do all three?"],
  };
  return byW[widget] || ["How do I close my gap?", "Can I retire at 62?", "Compare my strategies"];
}

function AIAssistant({ persona, lang }) {
  const [open, setOpen] = React.useState(false);
  const [msgs, setMsgs] = React.useState([]);
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [listening, setListening] = React.useState(false);
  const [speak, setSpeak] = React.useState(false);
  const [voiceErr, setVoiceErr] = React.useState(null);
  const recRef = React.useRef(null);
  const scrollRef = React.useRef(null);
  const inputRef = React.useRef(null);
  const sigRef = React.useRef(null);
  React.useEffect(() => () => { if (sigRef.current) try { sigRef.current.abort(); } catch (e) {} }, []);

  React.useEffect(() => { window.__ppOpenAI = () => setOpen(true); }, []);
  React.useEffect(() => {
    if (open && msgs.length === 0) {
      setMsgs([{ role: "ai", text: `Hi, I'm your Pension AI. Ask me anything about your retirement or your situation${persona ? ", " + persona.first.split(/[ &]/)[0] : ""}. You can type or tap the mic to talk.`, widget: "gauge", suggestions: ["How do I close my gap?", "Can I retire at 62?", "Compare my strategies"] }]);
    }
  }, [open]);
  React.useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [msgs, busy]);
  React.useEffect(() => {
    if (!open) return;
    const esc = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc);
  }, [open]);

  const sayAloud = (text) => {
    if (!speak || !window.speechSynthesis) return;
    try { window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.rate = 1.04; u.lang = "en-GB"; window.speechSynthesis.speak(u); } catch (e) {}
  };

  const send = async (raw) => {
    const q = (raw != null ? raw : input).trim();
    if (!q || busy) return;
    setInput(""); stopVoice();
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try { if (sigRef.current) sigRef.current.abort(); } catch (e) {}
    sigRef.current = (typeof AbortController !== "undefined") ? new AbortController() : null;
    let answer = "", widget = null, suggestions = null;
    try {
      if (window.ppAI) {
        const ctx = personaContext(persona);
        const history = msgs.slice(-6).map((m) => (m.role === "user" ? "User" : "Assistant") + ": " + m.text).join("\n");
        const types = (window.PP_WIDGET_TYPES || []).join(", ");
        const conf = (window.PP_CONFIDENCE && persona) ? window.PP_CONFIDENCE.compute(persona) : null;
        const confLine = conf ? `\n\nData confidence: ${conf.score}/100 (${conf.tier}). Estimated fields: ${conf.estimatedList || "none"}. Verified fields: ${conf.verifiedList || "none"}. At low confidence use cautious language ("based on your declared figures...") and suggest one document to verify; at high confidence use confident language.` : "";
        const legend = "Widget meanings, gauge: overall readiness score; scenarios: retire-age income tiles; projection: pension capital over time; plans: compare Secure/Balanced/Optimise strategies; annuity: lump sum vs lifelong annuity; kpi: key figures (income, buy-in, concentration); moves: ranked actions to raise the score.";
        const prompt = `You are Pension AI, the calm, precise in-app assistant for Swissquote Pension Partner (a Swiss retirement product). Use ONLY the figures provided to answer.\n\n${ctx}${confLine}\n\n${legend}\n\nRecent conversation:\n${history}\n\nUser question: ${q}\n\nReply ONLY with a JSON object, no prose around it:\n{\n "reply": "2-4 short sentences, plain language, Swiss context (AHV/AVS, pillars 1/2/3a, CHF). Educational, not a binding recommendation. Do not invent precise figures beyond those given.",\n "widget": one of [${types}] or null, the dashboard visual that best supports the answer,\n "suggestions": [up to 3 very short follow-up questions the user might tap next, each <= 6 words]\n}`;
        const j = await window.ppAI.completeJSON(prompt, { signal: sigRef.current && sigRef.current.signal });
        answer = (j.reply || "").trim();
        if (j.widget && (window.PP_WIDGET_TYPES || []).indexOf(j.widget) >= 0) widget = j.widget;
        if (Array.isArray(j.suggestions)) suggestions = j.suggestions.filter(Boolean).slice(0, 3);
      }
    } catch (e) { answer = ""; }
    if (!answer) answer = fallbackAnswer(q, persona);
    if (!widget) widget = window.ppAiwGuess ? window.ppAiwGuess(q) : null;
    if (!suggestions || !suggestions.length) suggestions = fallbackSuggestions(q, widget);
    setBusy(false);
    setMsgs((m) => [...m, { role: "ai", text: answer.trim(), widget, suggestions }]);
    sayAloud(answer);
  };

  const stopVoice = () => { try { if (recRef.current) { recRef.current.onend = null; recRef.current.stop(); } } catch (e) {} setListening(false); };
  const toggleVoice = () => {
    if (!SR) { setVoiceErr("Voice input isn't supported in this browser, try Chrome, Edge or Safari, opened in its own tab."); return; }
    if (listening) { stopVoice(); return; }
    setVoiceErr(null);
    let rec;
    try { rec = new SR(); } catch (e) { setVoiceErr("Voice input couldn't start in this view."); return; }
    recRef.current = rec;
    rec.lang = lang === "FR" ? "fr-FR" : "en-GB";
    rec.interimResults = true; rec.continuous = false;
    let finalT = "", got = false;
    rec.onstart = () => { setListening(true); };
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const tr = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalT += tr; else interim += tr;
      }
      got = true;
      setInput((finalT + interim).trim());
    };
    rec.onerror = (e) => {
      setListening(false);
      const err = e && e.error;
      if (err === "not-allowed" || err === "service-not-allowed") setVoiceErr("Microphone access was blocked. Allow it for this page (open it in its own tab) to use voice.");
      else if (err === "no-speech") setVoiceErr("I didn't catch that, tap the mic and speak again.");
      else if (err === "audio-capture") setVoiceErr("No microphone was found on this device.");
      else if (err === "network") setVoiceErr("Voice recognition needs a network connection and a standard browser tab.");
      else if (err !== "aborted") setVoiceErr("Voice input stopped unexpectedly. Please try again.");
    };
    rec.onend = () => { setListening(false); const t = finalT.trim(); if (t) send(t); };
    // start on the user gesture — SpeechRecognition raises its own mic permission prompt
    try { rec.start(); }
    catch (e) {
      // calling start() twice throws InvalidStateError; recover by restarting once
      try { rec.stop(); } catch (e2) {}
      setTimeout(() => { try { rec.start(); } catch (e3) { setListening(false); setVoiceErr("Voice input couldn't start, try again, or open this page in its own browser tab."); } }, 150);
    }
  };

  const recId = (persona && window.PP_PICK_REC) ? window.PP_PICK_REC(persona, persona.readiness.score).id : undefined;

  return (
    React.createElement(React.Fragment, null,
      React.createElement("button", { className: "pp-ai-fab" + (open ? " hidden" : ""), onClick: () => setOpen(true), title: "Ask Pension AI", "aria-label": "Ask Pension AI" },
        React.createElement("span", { className: "orb" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
        React.createElement("span", { className: "lbl" }, "Ask AI")),
      open && React.createElement("div", { className: "pp-ai-panel" },
        React.createElement("div", { className: "pp-ai-phead" },
          React.createElement("span", { className: "mk" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
          React.createElement("div", { className: "id" },
            React.createElement("div", { className: "nm" }, "Pension AI"),
            React.createElement("div", { className: "st" }, React.createElement("span", { className: "d" }), "Online · knows your plan")),
          React.createElement("button", { className: "ic" + (speak ? " on" : ""), title: speak ? "Read answers aloud: on" : "Read answers aloud: off", onClick: () => { if (speak && window.speechSynthesis) window.speechSynthesis.cancel(); setSpeak((s) => !s); } },
            React.createElement("i", { className: speak ? "ri-volume-up-line" : "ri-volume-mute-line" })),
          React.createElement("button", { className: "ic", title: "Close", onClick: () => { stopVoice(); setOpen(false); } }, React.createElement("i", { className: "ri-close-line" }))),
        React.createElement("div", { className: "pp-ai-thread", ref: scrollRef },
          msgs.map((m, i) => React.createElement("div", { className: "pp-ai-mw", key: i },
            React.createElement("div", { className: "pp-ai-m " + m.role },
              m.role === "ai" && React.createElement("span", { className: "av" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
              React.createElement("div", { className: "bub" }, m.text)),
            m.role === "ai" && m.widget && React.createElement("div", { className: "pp-ai-widget" }, React.createElement(window.AIWidget, { type: m.widget, P: persona, recId: recId })),
            m.role === "ai" && i === msgs.length - 1 && !busy && m.suggestions && m.suggestions.length > 0 &&
              React.createElement("div", { className: "pp-ai-sugg" },
                React.createElement("span", { className: "lab" }, "Try next"),
                m.suggestions.map((s, j) => React.createElement("button", { key: j, onClick: () => send(s) }, s, React.createElement("i", { className: "ri-arrow-right-up-line" })))))),
          busy && React.createElement("div", { className: "pp-ai-m ai", key: "busy" },
            React.createElement("span", { className: "av" }, React.createElement("i", { className: "ri-sparkling-2-fill" })),
            React.createElement("div", { className: "bub typing" }, React.createElement("span", null), React.createElement("span", null), React.createElement("span", null)))),
        voiceErr && React.createElement("div", { className: "pp-ai-voiceerr" }, React.createElement("i", { className: "ri-mic-off-line" }), voiceErr),
        React.createElement("div", { className: "pp-ai-inputbar" + (listening ? " listening" : "") },
          React.createElement("button", { className: "mic" + (listening ? " on" : ""), onClick: toggleVoice, title: listening ? "Stop listening" : "Speak", "aria-label": "Voice input" },
            React.createElement("i", { className: listening ? "ri-stop-circle-fill" : "ri-mic-line" })),
          React.createElement("input", {
            ref: inputRef, className: "in", value: input, placeholder: listening ? "Listening…" : "Ask about your retirement…",
            onChange: (e) => setInput(e.target.value),
            onKeyDown: (e) => { if (e.key === "Enter") send(); }
          }),
          React.createElement("button", { className: "go", onClick: () => send(), disabled: !input.trim() || busy, "aria-label": "Send" },
            React.createElement("i", { className: "ri-arrow-up-line" }))),
        React.createElement("div", { className: "pp-ai-foot" }, "Educational guidance · not a binding financial recommendation"))
    )
  );
}

Object.assign(window, { AIAssistant });
