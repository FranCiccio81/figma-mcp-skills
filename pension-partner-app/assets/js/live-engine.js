/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER, LIVE engine (live-engine.js) · Pass 2
   A real "Live" use case: reads an actual uploaded document, extracts
   the pension-relevant figures, and BUILDS a full persona object so the
   existing Plan / Scenarios / Monitoring screens become tailored to the
   file.
   Pass 2 upgrades:
     · extract() now sends the ACTUAL PDF/image to Claude vision (via
       ppAI.completeJSONWithDocs) when a File is provided — so scanned
       returns and phone photos are read, not silently estimated. Pass
       the File as the 3rd arg: extract(text, prior, file) — or just
       extract(file, prior). pdf.js text remains the fallback.
     · build() reads every Swiss constant from window.SWISS_PARAMS
       (versioned), with verified-2025 fallbacks so it never breaks.
   window.PP_LIVE = { readFile, extract, build, enrich, chf }
   ════════════════════════════════════════════════════════════════ */
(function () {
  const chf = (n) => "CHF " + Math.round(n).toLocaleString("de-CH").replace(/,/g, "\u2019");
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  try { if (window.pdfjsLib) window.pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js"; } catch (e) {}

  /* ── read an uploaded File → plain text ───────────────────────── */
  async function readFile(file) {
    if (!file) return "";
    const name = (file.name || "").toLowerCase();
    if (name.endsWith(".pdf") || file.type === "application/pdf") {
      try {
        const pdfjs = window.pdfjsLib;
        if (!pdfjs) return "";
        const buf = await file.arrayBuffer();
        const doc = await pdfjs.getDocument({ data: buf }).promise;
        let out = "";
        for (let p = 1; p <= Math.min(doc.numPages, 8); p++) {
          const page = await doc.getPage(p);
          const tc = await page.getTextContent();
          out += tc.items.map((i) => i.str).join(" ") + "\n";
        }
        return out;
      } catch (e) { return ""; }
    }
    if (name.match(/\.(txt|csv|md)$/) || (file.type || "").startsWith("text")) {
      try { return await file.text(); } catch (e) { return ""; }
    }
    return ""; // images: no in-browser OCR, we fall back to estimates
  }

  /* ── extract structured figures from a document (text or File) ──
     Signatures: extract(text, prior, file?)  OR  extract(file, prior)
     When a File is supplied and vision is available, Claude reads the
     real document; the pdf.js text is sent as an embedded fallback. */
  async function extract(textOrFile, prior, maybeFile) {
    let text = "", file = null;
    if (textOrFile && typeof textOrFile !== "string") file = textOrFile; else text = textOrFile || "";
    if (maybeFile && typeof maybeFile !== "string") file = maybeFile;
    if (file && !text) { try { text = await readFile(file); } catch (e) {} }
    const base = Object.assign({
      firstName: "", age: null, canton: "", status: "",
      grossIncome: null, netWorth: null, pillar2: null, pillar3a: null,
      targetMonthly: null, retireAge: 65,
    }, prior || {});
    const t = (text || "").trim();
    base._extracted = Object.assign({}, base._extracted);   // keep any prior verifications/confirmations
    base._sources = Object.assign({}, base._sources); base._audit = Object.assign({}, base._audit);
    if ((t || file) && window.ppAI) {
      try {
        const prompt = `You are extracting figures from a Swiss tax return or pension (LPP/3a) statement for a retirement plan. Accuracy and provenance matter: for EVERY field, "value" is the figure (CHF, integer, no separators) or null, and "source" is the VERBATIM label+amount text you read it from (e.g. "Salaire net - M. Jordan CHF 198'000") or null. NEVER guess: if you cannot point to it in the document, set BOTH value and source to null. Also fill "audit" with reconciliation figures if present (used for self-checking), each value or null.\n\nReturn ONLY this JSON shape:\n{\n "fields": {\n  "firstName": {"value": "str|null", "source": "str|null"},\n  "age": {"value": "num|null", "source": "str|null"},\n  "canton": {"value": "str|null", "source": "str|null"},\n  "status": {"value": "str|null", "source": "str|null"},\n  "grossIncome": {"value": "num|null", "source": "str|null"},\n  "netWorth": {"value": "num|null", "source": "str|null"},\n  "pillar2": {"value": "num|null", "source": "str|null"},\n  "pillar3a": {"value": "num|null", "source": "str|null"},\n  "targetMonthly": {"value": "num|null", "source": "str|null"},\n  "retireAge": {"value": "num|null", "source": "str|null"}\n },\n "audit": {\n  "totalDeductions": "num|null", "taxableIncomeICC": "num|null", "taxableIncomeIFD": "num|null",\n  "taxICC": "num|null", "taxIFD": "num|null", "totalTax": "num|null",\n  "fortuneBrute": "num|null", "dettes": "num|null", "fortuneNette": "num|null",\n  "pillar3aContribTotal": "num|null"\n }\n}\n\nDOCUMENT:\n${t.slice(0, 7000)}`;
        const j = (file && window.ppAI.canVision && window.ppAI.canVision())
          ? await window.ppAI.completeJSONWithDocs(prompt, [file])
          : await window.ppAI.completeJSON(prompt);
        const F = (j && j.fields) ? j.fields : (j || {});
        const read = (k) => {
          const cell = F[k];
          if (cell && typeof cell === "object") return { v: cell.value, s: (cell.source != null ? String(cell.source) : null) };
          return { v: cell, s: null }; // tolerate a flat {key:value} shape too
        };
        ["firstName", "canton", "status"].forEach((k) => {
          if (base._confirmed && base._confirmed[k]) return;   // human confirmation wins
          const r = read(k); if (r.v != null && String(r.v).trim()) { base[k] = String(r.v).trim(); base._sources[k] = r.s; if (r.s) base._extracted[k] = true; }
        });
        ["age", "grossIncome", "netWorth", "pillar2", "pillar3a", "targetMonthly", "retireAge"].forEach((k) => {
          if (base._confirmed && base._confirmed[k]) return;   // human confirmation wins
          const r = read(k); const n = Number(r.v); if (!isNaN(n) && n > 0) { base[k] = n; base._sources[k] = r.s; if (r.s) base._extracted[k] = true; }
        });
        if (j && j.audit && typeof j.audit === "object") {
          Object.keys(j.audit).forEach((k) => { const n = Number(j.audit[k]); if (!isNaN(n)) base._audit[k] = n; });
        }
      } catch (e) { /* fall through to regex */ }
    }
    // regex fallback for the biggest CHF numbers if model gave nothing
    if (base.grossIncome == null) {
      const nums = (t.match(/\d[\d'’ .]{3,}/g) || []).map((s) => Number(s.replace(/[^\d]/g, ""))).filter((n) => n > 1000);
      nums.sort((a, b) => b - a);
      if (nums.length) { base.netWorth = base.netWorth || nums[0]; base.grossIncome = base.grossIncome || Math.round(nums[0] / 3); }
    }
    // sensible defaults so the build never breaks
    base.firstName = base.firstName || "You";
    base.age = base.age || 45;
    base.canton = base.canton || "Switzerland";
    base.status = base.status || "Individual";
    base.grossIncome = base.grossIncome || 120000;
    base.netWorth = base.netWorth || 250000;
    base.pillar2 = base.pillar2 || Math.round(base.grossIncome * 1.6);
    base.pillar3a = base.pillar3a || 30000;
    base.targetMonthly = base.targetMonthly || Math.round((base.grossIncome * 0.7) / 12 / 100) * 100;
    base.retireAge = base.retireAge || 65;
    validate(base);
    return base;
  }

  /* ── deterministic self-checks: reconciliation + bounds + provenance ──
     Pure local code, never an AI call. Sets base._checks (per-test
     pass/fail/skip) and base._flags (human-readable warnings). This is
     the "never silently wrong" layer: the document validates itself. */
  function validate(base) {
    const SP = window.SWISS_PARAMS || { pillar3a: { cappedEmployedWithPF: 7258, cappedSelfEmployedNoPF: 36288 } };
    const a = base._audit || {};
    const checks = [], flags = [];
    function rec(name, lhs, rhs, label) {
      if (lhs == null || rhs == null) { checks.push({ name, status: "skipped", label }); return; }
      const tol = Math.max(100, Math.abs(rhs) * 0.01);
      const ok = Math.abs(lhs - rhs) <= tol;
      checks.push({ name, status: ok ? "pass" : "fail", label, lhs: Math.round(lhs), rhs: Math.round(rhs), diff: Math.round(lhs - rhs) });
      if (!ok) flags.push("Figures don't reconcile: " + label + " (" + Math.round(lhs) + " vs " + Math.round(rhs) + ")");
    }
    rec("taxable", (base.grossIncome != null && a.totalDeductions != null) ? base.grossIncome - a.totalDeductions : null, a.taxableIncomeICC, "gross income \u2212 deductions = taxable income (ICC)");
    rec("tax_sum", (a.taxICC != null && a.taxIFD != null) ? a.taxICC + a.taxIFD : null, a.totalTax, "cantonal + federal tax = total tax");
    rec("fortune", (a.fortuneBrute != null && a.dettes != null) ? a.fortuneBrute - a.dettes : null, a.fortuneNette, "gross wealth \u2212 debts = net wealth");
    function bound(name, v, lo, hi, label) {
      if (v == null) return;
      const ok = v >= lo && v <= hi;
      checks.push({ name: "bound_" + name, status: ok ? "pass" : "fail", label, value: v });
      if (!ok) flags.push("Outside the expected range: " + label + " = " + v);
    }
    bound("grossIncome", base.grossIncome, 0, 10000000, "gross income");
    bound("netWorth", base.netWorth, -5000000, 100000000, "net wealth");
    bound("age", base.age, 18, 75, "age");
    bound("retireAge", base.retireAge, 58, 72, "retirement age");
    bound("pillar2", base.pillar2, 0, 20000000, "2nd-pillar capital");
    bound("pillar3a", base.pillar3a, 0, 500000, "pillar 3a balance");
    if (a.totalTax != null && base.grossIncome > 0) {
      const r = a.totalTax / base.grossIncome;
      const ok = r >= 0.03 && r <= 0.45;
      checks.push({ name: "eff_rate", status: ok ? "pass" : "warn", label: "effective tax rate", value: Math.round(r * 1000) / 10 });
      if (!ok) flags.push("Unusual effective tax rate: " + (Math.round(r * 1000) / 10) + "%");
    }
    const cap = (SP.pillar3a && SP.pillar3a.cappedSelfEmployedNoPF) || 36288;
    if (a.pillar3aContribTotal != null && a.pillar3aContribTotal > cap * 2 + 1000) {
      flags.push("Pillar 3a contributions (" + a.pillar3aContribTotal + ") exceed the plausible annual cap");
      checks.push({ name: "cap_3a", status: "fail", label: "pillar 3a within annual cap" });
    }
    // provenance: any money figure used but NOT verified from a source needs a human eye
    ["grossIncome", "netWorth", "pillar2", "pillar3a"].forEach((k) => {
      if (base[k] != null && !(base._extracted && base._extracted[k])) {
        flags.push((k === "grossIncome" ? "Gross income" : k === "netWorth" ? "Net wealth" : k === "pillar2" ? "2nd-pillar capital" : "Pillar 3a") + " was not confirmed from a document \u2014 please review.");
      }
    });
    base._checks = checks;
    base._flags = flags;
    base._reconciled = checks.filter((c) => c.status === "pass").length;
    base._needsReview = flags.length;
    return base;
  }

  /* ── build a full persona from extracted figures ──────────────── */
  function build(raw) {
    // self-sufficient defaulting so a partial/empty extraction never breaks the plan
    const x = Object.assign({}, raw || {});
    const _def = {};
    const num = (v, d, k) => { const n = Number(v); if (!isNaN(n) && n > 0) return n; if (k) _def[k] = true; return d; };
    if (!(x.firstName && String(x.firstName).trim())) _def.firstName = true;
    x.firstName = (x.firstName && String(x.firstName).trim()) || "You";
    if (!(x.canton && String(x.canton).trim())) _def.canton = true;
    x.canton = (x.canton && String(x.canton).trim()) || "Switzerland";
    if (!(x.status && String(x.status).trim())) _def.status = true;
    x.status = (x.status && String(x.status).trim()) || "Individual";
    x.grossIncome = num(x.grossIncome, 120000, "grossIncome");
    x.netWorth = num(x.netWorth, Math.round(x.grossIncome * 2), "netWorth");
    x.pillar2 = num(x.pillar2, Math.round(x.grossIncome * 1.6), "pillar2");
    x.pillar3a = num(x.pillar3a, 30000, "pillar3a");
    x.targetMonthly = num(x.targetMonthly, Math.round((x.grossIncome * 0.7) / 12 / 100) * 100, "targetMonthly");
    x.age = num(x.age, 45, "age");
    x.retireAge = num(x.retireAge, 65, "retireAge");
    x._defaulted = _def;
    const tmpl = JSON.parse(JSON.stringify(window.PP_PERSONAS.bergerRey)); // structural template
    // ── Real retirement maths (Swiss 3-pillar), no simulation ──────
    const age = clamp(Math.round(x.age), 18, 70);
    const retire = clamp(Math.round(x.retireAge), age + 1, 72);
    const yrs = retire - age;
    // Swiss constants from the versioned params module (fallbacks = verified 2025 values)
    const SP = window.SWISS_PARAMS || { ahv: { maxSinglePerYear: 30240, minSinglePerYear: 15120 }, lpp: { conversionRateMin: 0.068, contribRateProxy: 0.12 }, assumptions: { netRealReturn: 0.025 }, pillar3a: { cappedEmployedWithPF: 7258 } };
    const REAL_RETURN = SP.assumptions.netRealReturn;   // net real return on capital
    const CONV_RATE = SP.lpp.conversionRateMin;         // LPP statutory conversion: annuity = capital × rate
    const CONTRIB_RATE_2P = SP.lpp.contribRateProxy;    // 2nd-pillar annual contribution proxy (employee+employer)
    const fv = (pv, r, n) => pv * Math.pow(1 + r, n);             // future value of a lump sum
    const fvAnnuity = (pmt, r, n) => r === 0 ? pmt * n : pmt * (Math.pow(1 + r, n) - 1) / r; // FV of yearly contributions
    const capital = x.pillar2 + x.pillar3a;                       // confirmed pillar capital today
    const annualContrib = Math.round(x.grossIncome * CONTRIB_RATE_2P);
    // projected 2nd+3rd-pillar capital at retirement = grown today's capital + grown future contributions
    const fund = Math.round(fv(capital, REAL_RETURN, yrs) + fvAnnuity(annualContrib, REAL_RETURN, yrs));
    // 1st pillar (AHV/AVS): proportional to income, clamped to the verified band (2025: 15'120–30'240/yr)
    const ahv = Math.round(Math.min(SP.ahv.maxSinglePerYear, Math.max(SP.ahv.minSinglePerYear, x.grossIncome * 0.20)) / 12);
    const fromCapital = (cap) => Math.round((cap * CONV_RATE) / 12); // monthly pension from capital at conversion rate
    const planned = ahv + fromCapital(fund);
    // "today's path": only current capital grown (no further contributions) — the do-nothing baseline
    const today = ahv + fromCapital(Math.round(fv(capital, REAL_RETURN, yrs)));
    const target = Math.max(planned, x.targetMonthly);
    const fundedPct = clamp(Math.round((planned / target) * 100), 8, 99);
    const upliftPct = today > 0 ? +(((planned - today) / today) * 100).toFixed(1) : 0;
    const verdict = fundedPct >= 85 ? "Secure, well on track" : fundedPct >= 66 ? "On track, with room to climb" : fundedPct >= 46 ? "Building, close the gap now" : "Early days, the runway is the opportunity";

    const scen = (a) => {
      const yy = Math.max(0, a - age), f = Math.round(fv(capital, REAL_RETURN, yy) + fvAnnuity(annualContrib, REAL_RETURN, yy));
      const inc = ahv + fromCapital(f);
      return { age: a, inc: chf(Math.max(inc, 600)), pct: clamp(Math.round((inc / target) * 100), 5, 130) + "% of target", incN: inc };
    };
    const s1 = scen(retire - 2), s2 = scen(retire), s3 = scen(retire + 1);
    s2.hl = true;
    const tag = (s) => { const p = parseInt(s.pct); s.tag = p >= 80 ? "ok" : "tight"; s.tagTxt = p >= 95 ? "Comfortable" : p >= 80 ? "On plan" : "Tight"; return s; };
    [s1, s2, s3].forEach(tag);

    const sub = {
      funding: fundedPct,
      tax: clamp(40 + Math.round((x.pillar3a / 7258) * 30), 20, 95),
      diversification: clamp(72 - Math.round((capital / Math.max(x.netWorth, 1)) * 20), 30, 90),
      liquidity: clamp(Math.round(((x.netWorth - capital) / Math.max(x.grossIncome, 1)) * 18), 25, 95),
      protection: clamp(x.pillar2 > 0 ? 70 : 40, 20, 90),
    };

    const mkPlan = (id, nm, thesis, dScore, risk, dRetire, taxSaved) => ({
      id, name: nm, thesis, rec: id === "balanced", risk, retireAge: retire + dRetire, taxSaved,
      income: chf(Math.round(planned * (1 + dScore / 100))) + "/mo", score: clamp(fundedPct + dScore, 5, 99),
      moves: tmpl.plans.find((p) => p.id === id).moves,
      sub: Object.assign({}, sub, { funding: clamp(fundedPct + dScore, 5, 99) }),
    });

    const projYrs = [age, Math.round((age + retire) / 2), retire, Math.round((retire + 88) / 2), 88];
    // real curves: capital + contributions compounded each year; post-retirement draws the conversion annuity
    const accAt = (a, withContrib) => Math.round(fv(capital, REAL_RETURN, a - age) + (withContrib ? fvAnnuity(annualContrib, REAL_RETURN, a - age) : 0));
    const drawAt = (a, peakFund) => Math.round(Math.max(0, fv(peakFund, REAL_RETURN, a - retire) - fromCapital(peakFund) * 12 * fvAnnuity(1, REAL_RETURN, a - retire)));
    const curPeak = accAt(retire, false);
    const curAt = (a) => a <= retire ? accAt(a, false) : drawAt(a, curPeak);
    const plAt = (a) => a <= retire ? accAt(a, true) : drawAt(a, fund);
    const yMax = Math.max(fund * 1.15, plAt(retire) * 1.15);

    Object.assign(tmpl, {
      id: "live", name: x.firstName, first: x.firstName, initials: (x.firstName[0] || "Y").toUpperCase() + (x.firstName.split(" ")[1] ? x.firstName.split(" ")[1][0].toUpperCase() : "L"),
      kind: "single", age, canton: x.canton, status: x.status, flag: "\ud83d\udcc4",
      headline: verdict, grossIncome: x.grossIncome, targetYearly: target * 12, targetMonthly: target,
      pillar2: x.pillar2, pillar3a: x.pillar3a,
      netWorth: x.netWorth, retireTarget: retire, referenceAge: 65, taxFixture: "Your uploaded document",
      readiness: { score: fundedPct, verdict, sub: "Built live from your uploaded document. " + chf(capital) + " in pillars today, projected to " + chf(fund) + " at " + retire + ".", today, planned, upliftPct },
      scenarios: [s1, s2, s3], subScores: sub,
      kpis: [
        { lbl: "Projected income", val: chf(planned), sub: "per month at " + retire, tone: fundedPct >= 66 ? "green" : "amber", tag: fundedPct + "% of target" },
        { lbl: "Pension capital", val: chf(capital), sub: "2nd + 3rd pillar today", tone: "green", tag: "From your docs" },
        { lbl: "Projected fund", val: chf(fund), sub: "at retirement", tone: "green", tag: "Calculated" },
        { lbl: "3a balance", val: chf(x.pillar3a), sub: "pillar 3a", tone: x.pillar3a >= 30000 ? "green" : "amber", tag: x.pillar3a >= 30000 ? "Healthy" : "Top up" },
      ],
      projection: {
        startAge: age, retireAge: retire, endAge: 88,
        yTicks: [yMax, yMax * 0.75, yMax * 0.5, yMax * 0.25].map((v) => Math.round(v / 50000) * 50000), yMax,
        current: projYrs.map((a) => [a, curAt(a)]), planned: projYrs.map((a) => [a, plAt(a)]),
        bandLo: projYrs.map((a) => [a, Math.round(plAt(a) * 0.9)]), bandHi: projYrs.map((a) => [a, Math.round(plAt(a) * 1.1)]),
        peak: { age: retire, value: plAt(retire) }, confidence: "Calculated from your figures",
      },
      journey: { years: yrs, nowAge: age, retireAge: retire, contribNow: Math.round(annualContrib / 12), contribPlanned: Math.round(annualContrib / 12 * 1.6), totalContrib: annualContrib * yrs, projectedFund: fund, progressPct: clamp(Math.round((capital / fund) * 100), 4, 90), confidence: "Calculated" },
      plans: [
        mkPlan("secure", "Secure", "Certainty over upside", -4, "Low", 1, "Lower"),
        mkPlan("balanced", "Balanced", "Balance growth, tax & flexibility", 0, "Medium", 0, "Medium\u2013high"),
        mkPlan("optimise", "Optimise", "Maximise capital & flexibility", 5, "Higher", -1, "High"),
      ],
      monitor: {
        status: "Live · built from your document", nextReview: "On your next upload", cadence: "Tailored to your file",
        nudges: [
          { label: "advice", icon: "ri-safe-2-line", meta: "3a · this year", h: x.pillar3a >= 7258 ? "Keep maxing your pillar 3a" : "Top up your pillar 3a", p: "Your 3a is " + chf(x.pillar3a) + ". Filling the annual cap is the simplest tax-efficient lever to lift your score.", cta: "Plan 3a top-up", deadline: "Dec 31" },
          { label: fundedPct < 66 ? "advice" : "info", icon: "ri-line-chart-line", meta: "Funding", h: fundedPct < 66 ? "Close your " + (100 - fundedPct) + "-point gap" : "Protect your trajectory", p: "Projected income covers " + fundedPct + "% of your target. Buy-ins and contribution increases move this most.", cta: "See top moves" },
          { label: "info", icon: "ri-upload-cloud-2-line", meta: "Sharper", h: "Add another document", p: "Each statement you add tightens this estimate, salary certificate, LPP certificate or 3a statement.", cta: "Add a document" },
        ],
        deadlines: [
          { m: "DEC", d: "31", t: "Max pillar 3a", s: "This year's cap", amt: chf(Math.max(0, 7258 - x.pillar3a)) },
          { m: "Q1", d: "\u2192", t: "Review buy-in capacity", s: "From your LPP certificate", amt: "" },
          { m: "YR", d: "\u2713", t: "AVS continuity", s: "Avoid 1st-pillar gaps", amt: "" },
        ],
      },
      calendar: [
        { id: "l0", yr: String(new Date().getFullYear()), age, t: "Plan created from your document", d: "Live analysis of your upload.", type: "milestone", state: "now" },
        { id: "l1", yr: String(new Date().getFullYear() + 1), age: age + 1, t: "Max pillar 3a", d: "Tax-efficient contribution.", type: "save", state: "next", amt: chf(Math.min(7258, x.grossIncome * 0.1)) },
        { id: "l2", yr: String(new Date().getFullYear() + (retire - age)), age: retire, t: "Retirement", d: "Capital vs annuity, with a human.", type: "retire", state: "next" },
      ],
      sim: { grossIncome: x.grossIncome, cash: Math.round((x.netWorth - capital) * 0.5), securities: Math.round((x.netWorth - capital) * 0.5), targetIncome: target * 12, projectedBase: planned * 12, bufferThreshold: Math.round(x.grossIncome * 0.25), defaults: { price: 800000, currency: "CHF", downPayment: Math.round(x.netWorth * 0.4), calcRate: 0.05, foreign: false } },
      divorce: { applicable: false },
      lumpAnnuity: Object.assign({}, tmpl.lumpAnnuity, { capital: fund, intro: "At retirement your ~" + chf(fund) + " of 2nd-pillar capital becomes a one-off choice. Here's the trade-off.", options: tmpl.lumpAnnuity.options.map((o) => Object.assign({}, o, { figure: o.id === "lump" ? chf(fund) : chf(fromCapital(fund)) })) }),
      improve: tmpl.improve,
    });
    // real, name-based report (override the cloned template so no Thomas/Sandrine text leaks)
    const fname = (x.firstName || "You").trim() || "You";
    const incPct = clamp(Math.round((x.grossIncome / Math.max(x.grossIncome + (x.netWorth - capital) * 0.03, 1)) * 100), 70, 97);
    tmpl.report = {
      portrait: fname + ", you're " + age + (x.canton && x.canton !== "Switzerland" ? " in " + x.canton : "") + " with a gross income of " + chf(x.grossIncome) + " and " + chf(capital) + " across your pillars today. On current contributions you're calculated to reach " + chf(fund) + " by " + retire + ", about " + chf(planned) + "/month, " + fundedPct + "% of your " + chf(target) + " target.",
      incomeSources: [
        { l: "Employment", pct: incPct, color: "#3B82F6" },
        { l: "Investments & assets", pct: clamp(100 - incPct - 4, 1, 25), color: "#12A454" },
        { l: "Pillar 3a growth", pct: 4, color: "#FA5B35" },
      ],
      wealthDims: [
        { l: "Retirement readiness", s: Math.round(fundedPct / 5) },
        { l: "Tax efficiency", s: clamp(Math.round(x.pillar3a / 7258 * 16), 4, 18) },
        { l: "3a optimisation", s: clamp(Math.round(x.pillar3a / 50000 * 16), 3, 18) },
        { l: "Income stability", s: 16 },
        { l: "Pension coverage", s: clamp(Math.round(capital / Math.max(x.grossIncome, 1) * 6), 4, 18) },
      ],
      deductions: [
        { l: "Pillar 3a", amt: x.pillar3a > 0 ? Math.min(7258, Math.round(x.pillar3a / 8)) : 0 },
        { l: "Pension buy-in", amt: 0 },
        { l: "Professional expenses", amt: Math.round(x.grossIncome * 0.03) },
        { l: "Insurance premiums", amt: 1750 },
      ],
      tax: tmpl.report ? tmpl.report.tax : null,
      taxProfile: (tmpl.report && tmpl.report.taxProfile) ? tmpl.report.taxProfile : [],
      insights: tmpl.report ? tmpl.report.insights : [],
      lombard: null,
      realEstate: [],
    };
    // ── data-confidence field states: extracted = verified, defaults = estimated, manual = declared ──
    const ex = raw && raw._extracted ? raw._extracted : {};
    const wasDefaulted = raw ? raw._defaulted || {} : {};
    const fmap = { firstName: "objectivesRisk", grossIncome: "grossIncome", pillar2: "pillar2", pillar3a: "pillar3a", netWorth: "netWorth", canton: "canton", status: "status", age: "ageRetire", retireAge: "ageRetire", targetMonthly: "targetMonthly" };
    const fs = {};
    Object.keys(fmap).forEach((src) => {
      const f = fmap[src];
      if (ex[src]) fs[f] = "verified";
      else if (wasDefaulted[src]) { if (!fs[f]) fs[f] = "estimated"; }
      else if (!fs[f]) fs[f] = (raw && raw.confidence) ? "declared" : "declared";
    });
    tmpl.fieldStates = fs;
    tmpl.dataConfidence = window.PP_CONFIDENCE ? window.PP_CONFIDENCE.compute(tmpl).score : (raw && raw.confidence ? Math.round(raw.confidence) : 60);
    tmpl._needsEnrich = true;
    return tmpl;
  }

  /* ── enrich(persona): regenerate the SUGGESTED ACTIONS + KEY INSIGHTS
     so they're written for THIS person from THEIR extracted figures,
     not inherited from the template. AI-driven, deterministic fallback. */
  function fallbackEnrich(P) {
    const first = (P.first || P.name || "you").split(/[ &]/)[0];
    const horizon = Math.max(0, (P.retireTarget || 65) - (P.age || 45));
    const cap3aGap = Math.max(0, 7258 - (P.pillar3a || 0));
    const adv = [];
    if (cap3aGap > 0) adv.push({ rank: 1, title: "Top up your pillar 3a", label: "advice", impact: Math.round(cap3aGap * 0.06), effort: 1,
      desc: "Your 3a is " + chf(P.pillar3a || 0) + ", below this year's cap. Adding " + chf(cap3aGap) + " cuts taxable income now and compounds tax-free.",
      math: [["Inputs", "3a balance " + chf(P.pillar3a || 0) + "; cap CHF 7\u2019258."], ["Result", "Deduct " + chf(cap3aGap) + " now."]], rule: "Pillar 3a annual cap" });
    adv.push({ rank: adv.length + 1, title: "Put your free savings to work", label: "advice", impact: 0, impactNote: "long-horizon growth", effort: 2,
      desc: "With about " + horizon + " years to retirement, idle cash beyond a buffer can follow a diversified strategy.",
      math: [["Horizon", horizon + " years"], ["Result", "Invest the surplus above a 3-month buffer."]], rule: "Free-savings investing" });
    adv.push({ rank: adv.length + 1, title: "Confirm your figures with a document", label: "info", impact: 0, impactNote: "sharper plan", effort: 1,
      desc: "Some inputs are estimated. A salary certificate or LPP statement turns them into verified figures and tightens this plan.",
      math: [["Now", "Estimated inputs"], ["Result", "Verified, higher confidence"]], rule: "Data confidence" });
    P.advisories = adv;
    if (P.report) P.report.insights = [
      { kind: "opportunity", icon: "ri-line-chart-line", t: "Projected to " + chf((P.projection && P.projection.peak && P.projection.peak.value) || 0), d: "On your strategy, your capital reaches about " + chf((P.projection && P.projection.peak && P.projection.peak.value) || 0) + " by " + (P.retireTarget || 65) + "." },
      { kind: cap3aGap > 0 ? "opportunity" : "info", icon: "ri-safe-2-line", t: "3a headroom", d: cap3aGap > 0 ? chf(cap3aGap) + " of unused 3a allowance this year." : "Your 3a is at the cap, well done." },
      { kind: "info", icon: "ri-time-line", t: horizon + " years to act", d: "Time is your biggest lever; the moves above compound across that horizon." },
    ];
    return P;
  }
  function enrich(P) {
    if (!P) return Promise.resolve(P);
    P._needsEnrich = false;
    if (!window.ppAI) return Promise.resolve(fallbackEnrich(P));
    const conf = window.PP_CONFIDENCE ? window.PP_CONFIDENCE.compute(P) : null;
    const fig = [
      "Name: " + (P.first || P.name), "Age " + P.age + ", target retirement " + (P.retireTarget || 65) + " (horizon " + Math.max(0, (P.retireTarget || 65) - P.age) + " yrs)",
      "Status " + P.status + ", canton " + P.canton, "Gross income " + chf(P.grossIncome) + "/yr; target " + chf(P.targetMonthly) + "/mo",
      "2nd pillar " + chf(P.pillar2) + "; pillar 3a " + chf(P.pillar3a) + "; net worth " + chf(P.netWorth),
      "Readiness " + ((P.readiness || {}).score) + "/100; projected capital " + chf((P.projection && P.projection.peak && P.projection.peak.value) || 0) + " at retirement",
      conf ? ("Data confidence " + conf.score + "/100; estimated fields: " + conf.estimatedList) : "",
    ].filter(Boolean).join("\n");
    const prompt = "You are Pension AI for Swissquote Pension Partner. Write the personalised SUGGESTED ACTIONS and KEY INSIGHTS for THIS person, using ONLY the real figures below. Address them by their first name where natural. Never invent numbers; cite the figures shown. Reply ONLY with JSON:\n{\n \"advisories\": [3-4 items, ordered by impact, each {\"title\": short imperative action (<=8 words), \"label\": \"advice\" or \"info\", \"impactNote\": short benefit phrase, \"desc\": 1-2 sentences citing the real figures, \"effort\": 1|2|3, \"calc\": one short sentence on how it's estimated}],\n \"insights\": [exactly 3 items, each {\"icon\": a remixicon name like ri-line-chart-line, \"title\": <=6 words, \"body\": 1 sentence citing a real figure}]\n}\n\nFIGURES:\n" + fig;
    return window.ppAI.completeJSON(prompt).then((j) => {
      if (j && Array.isArray(j.advisories) && j.advisories.length) {
        P.advisories = j.advisories.slice(0, 4).map((a, i) => ({
          rank: i + 1, title: String(a.title || "").trim() || ("Action " + (i + 1)),
          label: a.label === "info" ? "info" : "advice", impact: 0, impactNote: String(a.impactNote || "opportunity"),
          effort: Math.max(1, Math.min(3, +a.effort || 1)), desc: String(a.desc || "").trim(),
          math: [["How we estimate", String(a.calc || "Estimated from your figures.")]], rule: "Estimated from your figures",
        }));
      }
      if (P.report && j && Array.isArray(j.insights) && j.insights.length) {
        P.report.insights = j.insights.slice(0, 3).map((it) => ({
          kind: (it.kind === "risk" || it.kind === "info") ? it.kind : "opportunity",
          icon: /^ri-/.test(it.icon || "") ? it.icon : "ri-lightbulb-flash-line",
          t: String(it.title || it.t || "").trim(), d: String(it.body || it.d || "").trim(),
        }));
      }
      return P;
    }).catch(() => fallbackEnrich(P));
  }

  window.PP_LIVE = { readFile, extract, build, enrich, validate, chf };
})();
