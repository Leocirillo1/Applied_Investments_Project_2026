# "Underpriced innovators with real, improving earnings power" (RDV) — design, fixed before the backtest

The definition below was written down **before** the signal was computed and has not been changed
since: equal weights, nothing estimated, one run.

## Story
Accounting rules expense R&D immediately, so innovative firms show depressed profits and look
expensive. Investors tend to underprice firms that invest heavily in innovation
(Chan, Lakonishok & Sougiannis 2001). RDV buys firms that:
- invest heavily in R&D relative to their price;
- are cheap relative to their **true earnings power, with R&D added back**
  (Ball, Gerakos, Linnainmaa & Nikolaev 2015);
- have that earnings power improving.

It shorts firms with the opposite profile. Adding R&D back is required for the story to be
coherent: OIBDP is measured after R&D, so without it the cheapness term would penalise exactly the
heavy R&D investors the first term buys.

## Definition
- **Universe:** US common stocks on NYSE/AMEX/NASDAQ, non-financial, R&D reporters
  (XRD_FY > 0; missing R&D is never set to 0), ME_June > 0. First formation June 1975
  (R&D reporting mandatory since SFAS 2); returns 1975-07 → 2025-12.
- **Timing:** fiscal year FY ends in calendar year t−1 (data ≥ 6 months old); ME of June t.
- **Inputs:**
  - RDM = XRD_FY / ME_June(t);
  - EYR = (OIBDP_FY + XRD_FY) / EV, with EV = ME_June(t) + DLC_FY + DLTT_FY − CHE_FY; EV ≤ 0 → missing;
  - ΔOPR = (OIBDP+XRD)_FY / AT_{FY−1} − (OIBDP+XRD)_{FY−1} / AT_{FY−2} (same firm, consecutive fiscal years).
- **Score** (equal weights):
  - each input is winsorised at 1%/99% and z-scored within the June-t universe;
  - **Score = z(RDM) + z(EYR) + z(ΔOPR)**;
  - a missing EYR or ΔOPR counts as z = 0 (neutral). RDM is always available.
- **Portfolios:** quintiles with NYSE breakpoints (values ≤ breakpoint go to the lower portfolio).
  Q5 = highest score (long), Q1 = lowest (short).
  - Value-weighted with previous month-end market cap; held July t → June t+1 (annual rebalancing).

## Evaluation
1. Alphas under the 7 models (CAPM, FF3, FF3+MOM, FF5, FF5+MOM, q, q5; Newey-West 6 lags):
   gross, net of trading costs, and equal-weighted (robustness).
2. Quintile returns, legs, characteristics, factor loadings, GRS test.
3. Sub-periods 1975–1999 / 2000–2025, size and price filters, deciles, breakpoints, winsorisation,
   Fama-MacBeth regressions, Fama-French 12 sector weights.
