/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER — confidence engine (pp-confidence.js) · Pass 2
   A pure, local, deterministic data-confidence index. NEVER an AI
   call. Measures how COMPLETE + PROVEN the inputs are (not pension
   health). declared (hand-typed) = 60% of weight · verified (from a
   confirmed document) = 100% · estimated (default/regex fallback) =
   30% · non-provable fields (age, status, goals…) score 100% when
   declared. window.PP_CONFIDENCE
   ════════════════════════════════════════════════════════════════ */
(function () {
  // weight + whether a document can prove it (per PROMPT V5 §2.1)
  var FIELDS = [
    { key: "grossIncome", label: "Annual gross income", w: 14, provable: true, doc: "salary certificate" },
    { key: "pillar2", label: "2nd-pillar (LPP) capital", w: 16, provable: true, doc: "LPP certificate" },
    { key: "pillar3a", label: "Pillar 3a balance", w: 12, provable: true, doc: "3a statement" },
    { key: "netWorth", label: "Net worth", w: 10, provable: true, doc: "tax return" },
    { key: "canton", label: "Canton", w: 4, provable: true, doc: "tax return" },
    { key: "status", label: "Status", w: 6, provable: false },
    { key: "ageRetire", label: "Age & target retirement age", w: 8, provable: false },
    { key: "targetMonthly", label: "Target monthly income", w: 8, provable: false },
    { key: "savingCapacity", label: "Monthly saving capacity", w: 8, provable: false },
    { key: "objectivesRisk", label: "Goals & risk profile", w: 14, provable: false },
  ];
  var FACTOR = { verified: 1, declared: 0.6, estimated: 0.3, missing: 0 };

  function present(persona, key) {
    var P = persona || {};
    switch (key) {
      case "grossIncome": return P.grossIncome > 0;
      case "pillar2": return typeof P.pillar2 === "number" ? P.pillar2 >= 0 : (P.netWorth != null);
      case "pillar3a": return typeof P.pillar3a === "number" ? P.pillar3a >= 0 : (P.netWorth != null);
      case "netWorth": return P.netWorth > 0;
      case "canton": return !!P.canton && P.canton !== "Switzerland";
      case "status": return !!P.status && P.status !== "Individual" && P.status !== "Manual entry";
      case "ageRetire": return P.age > 0 && (P.retireTarget > 0 || P.referenceAge > 0);
      case "targetMonthly": return P.targetMonthly > 0;
      case "savingCapacity": return P.savingCapacity > 0 || (P.journey && P.journey.contribNow > 0);
      case "objectivesRisk": return !!(P.objectivesSet || (P.plans && P.plans.length));
      default: return false;
    }
  }

  // resolve each field's state: explicit fieldStates win; else infer
  function stateOf(persona, f) {
    var P = persona || {};
    var fs = P.fieldStates || {};
    if (fs[f.key]) return fs[f.key];
    if (!present(P, f.key)) {
      // a couple of "explicitly none" cases still count as declared
      if (f.key === "pillar2" && P.pillar2 === 0) return "declared";
      if (f.key === "pillar3a" && P.pillar3a === 0) return "declared";
      return "missing";
    }
    if (P.verifiedFields && P.verifiedFields.indexOf(f.key) >= 0) return "verified";
    if (P.estimatedFields && P.estimatedFields.indexOf(f.key) >= 0) return "estimated";
    return "declared";
  }

  function tierOf(score) {
    return score >= 85 ? { c: "hi", l: "High confidence" }
      : score >= 68 ? { c: "good", l: "Good confidence" }
      : { c: "fair", l: "Building confidence" };
  }

  function compute(persona) {
    var got = 0, detail = [];
    FIELDS.forEach(function (f) {
      var st = stateOf(persona, f);
      got += f.w * FACTOR[st];
      detail.push({ field: f.key, label: f.label, state: st, weight: f.w, provable: f.provable, doc: f.doc });
    });
    var score = Math.round(got);
    var t = tierOf(score);
    var verifiedList = detail.filter(function (d) { return d.state === "verified"; }).map(function (d) { return d.label; }).join(", ") || "none";
    var estimatedList = detail.filter(function (d) { return d.state === "estimated"; }).map(function (d) { return d.label; }).join(", ") || "none";
    var declaredList = detail.filter(function (d) { return d.state === "declared"; }).map(function (d) { return d.label; }).join(", ") || "none";
    return { score: score, tier: t.l, tierClass: t.c, detail: detail, verifiedList: verifiedList, estimatedList: estimatedList, declaredList: declaredList };
  }

  // top actions that would gain the most points (gain = remaining weight × jump to verified)
  function nextBestActions(persona) {
    var detail = compute(persona).detail;
    var acts = [];
    detail.forEach(function (d) {
      var cur = FACTOR[d.state];
      var best = d.provable ? 1 : 1; // verified for provable, full-declared for non-provable
      var ceil = d.provable ? "verified" : "declared";
      var gain = Math.round(d.weight * (best - cur));
      if (gain <= 0) return;
      var target = d.provable ? "upload" : "form";
      var label;
      if (d.state === "missing") label = d.provable ? ("Upload your " + d.doc) : ("Add your " + d.label.toLowerCase());
      else if (d.provable) label = ("Verify your " + d.label.toLowerCase() + " with your " + d.doc);
      else label = ("Confirm your " + d.label.toLowerCase());
      acts.push({ label: label, gain: gain, target: target, field: d.field, ceil: ceil });
    });
    acts.sort(function (a, b) { return b.gain - a.gain; });
    return acts.slice(0, 3);
  }

  // promote estimated/declared fields to verified after a document is confirmed
  function applyVerified(persona, fields) {
    if (!persona) return persona;
    persona.fieldStates = persona.fieldStates || {};
    (fields || []).forEach(function (k) { persona.fieldStates[k] = "verified"; });
    persona.dataConfidence = compute(persona).score;
    return persona;
  }

  window.PP_CONFIDENCE = { compute: compute, nextBestActions: nextBestActions, applyVerified: applyVerified, FIELDS: FIELDS };
})();
