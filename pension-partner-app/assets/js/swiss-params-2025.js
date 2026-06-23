/* ════════════════════════════════════════════════════════════════
   PENSION PARTNER — Swiss pension & tax parameters (swiss-params-2025.js)
   Single source of truth for every Swiss constant the engine uses.
   VERIFY EVERY TAX YEAR against the official sources at the bottom and
   bump `year`. Keeping these out of build() is the audit-safe pattern:
   a reviewer checks ONE table, not a function body.
   window.SWISS_PARAMS
   ════════════════════════════════════════════════════════════════ */
(function () {
  var SWISS_PARAMS = {
    year: 2025,

    /* 1st pillar — AHV / AVS (verified 2025) */
    ahv: {
      maxSinglePerYear: 30240,   // CHF 2'520/mo. 2024 was 29'400 (the old value in build()).
      minSinglePerYear: 15120,   // CHF 1'260/mo.
      maxCouplePerYear: 45360,   // 150% cap = CHF 3'780/mo for a married couple.
      maxAvgIncomeForFull: 90720,
      // 2026 CHANGE: a 13th AHV pension is paid from 2026 (annual = 13× the monthly amount,
      // extra instalment in December). Monthly figures are unchanged in 2026; the next
      // biennial adjustment is 2027. Factor the 13th into forward projections for 2026+.
      thirteenthFrom: 2026,
    },

    /* 3rd pillar — pillar 3a annual deduction caps (2025) */
    pillar3a: {
      cappedEmployedWithPF: 7258,     // employees affiliated to a 2nd pillar. 2024 was 7'056.
      cappedSelfEmployedNoPF: 36288,  // self-employed without a 2nd pillar: 20% of net income, capped here.
      selfEmployedPctOfIncome: 0.20,
    },

    /* 2nd pillar — LPP / BVG */
    lpp: {
      conversionRateMin: 0.068,   // statutory BVG minimum conversion rate (annuity = capital × rate).
                                  // NOTE: many funds apply a lower *enveloping* rate on super-mandatory capital.
      contribRateProxy: 0.12,     // modelling proxy (employee+employer). Real rate is age-banded 7–18%.
    },

    /* projection assumptions (surface these in the UI) */
    assumptions: {
      netRealReturn: 0.025,
    },

    sources: {
      ahv: "OFAS/BSV — bsv.admin.ch · ahv-iv.ch (pension scales 44)",
      pillar3a: "ESTV/AFC — estv.admin.ch (pillar 3a maxima)",
      lpp: "OFAS/BSV — bsv.admin.ch (BVG conversion rate)",
    },
  };

  /* AHV annual estimate proportional to income, clamped to the 2025 band.
     Mirrors the original build() logic but reads the verified constants. */
  SWISS_PARAMS.ahvAnnualEstimate = function (grossIncome) {
    var a = SWISS_PARAMS.ahv;
    return Math.round(Math.min(a.maxSinglePerYear, Math.max(a.minSinglePerYear, (grossIncome || 0) * 0.20)));
  };

  window.SWISS_PARAMS = SWISS_PARAMS;
})();
