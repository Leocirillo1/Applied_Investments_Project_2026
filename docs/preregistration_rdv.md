# "Underpriced innovators with real, improving earnings power" (RDV) — pre-registration
Written 13 Oct 2026, **before** the signal was computed. Equal weights, an a priori design. Run **once**; results reported whatever they are.

## Story
Accounting expenses R&D, so innovative firms show depressed profits and look expensive. RDV buys firms that:
- invest heavily in R&D relative to their price (signal B);
- are cheap relative to their **true earnings power, with R&D added back** (Ball, Gerakos, Linnainmaa & Nikolaev 2015);
- have that earnings power improving.

Adding R&D back is required for the story to be coherent: OIBDP is measured after R&D, so without it the cheapness term would penalise exactly the firms B buys.

## Prior evidence, disclosed
- B works on its own.
- In earlier tests, cheapness (M1) and investment relative to price (BUILD) mostly added value-factor (HML) exposure, not alpha.
- So the relevant test is the **value added beyond B**, with the decision rule below fixed in advance.

## Definition (fixed)
- **Universe:** same as B — R&D reporters (XRD_FY > 0), ME_June > 0; first formation June 1975; returns 1975-07 → 2025-12.
- **Timing:** fiscal year FY ends in calendar year t−1 (data ≥ 6 months old); ME of June t.
- **Inputs:**
  - RDM = XRD_FY / ME_June(t);
  - EYR = (OIBDP_FY + XRD_FY) / EV, with EV = ME_June(t) + DLC_FY + DLTT_FY − CHE_FY; EV ≤ 0 → missing;
  - ΔOPR = (OIBDP+XRD)_FY / AT_{FY−1} − (OIBDP+XRD)_{FY−1} / AT_{FY−2} (same firm, consecutive fiscal years).
- **Score** (equal weights, nothing estimated):
  - each input is winsorised at 1%/99% and z-scored within the June-t universe;
  - **Score = z(RDM) + z(EYR) + z(ΔOPR)**;
  - a missing EYR or ΔOPR counts as z = 0 (neutral), the same rule as M2. RDM is always available.
- **Portfolios:** quintiles with NYSE breakpoints (values ≤ breakpoint go to the lower portfolio). Q5 = highest score (long), Q1 = lowest (short).
  - Value-weighted with previous month-end market cap; held July t → June t+1.

## Tests (same as BUILD)
1. Alphas under the 7 models (Newey-West 6): gross, net of costs, and equal-weighted (robustness).
2. **Value added over B:** RDV_t = a + b · B_t (+ FF5+MOM factors) + e_t.
3. Legs, quintile returns and characteristics, sub-periods 1975–1999 / 2000–2025, FF12 sector weights, factor loadings.

## Decision rule (fixed now)
- RDV **replaces B** only if *a* (with FF5+MOM factors) is **positive with t > 2**.
- Otherwise B stays the strategy.

## Multiple testing
- This is test #11.
- Bonferroni-adjusted p-values use ×11.
