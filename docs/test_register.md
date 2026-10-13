# Test register — every strategy tested in this project

This register is kept for transparency: the paper presents one strategy (RDV), but readers must
know how many ideas were tested before it was selected (multiple-testing / data-snooping risk).
All tests use the same data, universe rules, timing (accounting data ≥ 6 months old), value
weighting and Newey-West(6) t-statistics. Tests 3–11 were pre-registered (definition written
before any result); each was run once.

## How to read the table

- Columns 1–2: strategy name and how the idea was chosen.
- Columns 3–4: the value-weighted long-short alpha (% per month, Newey-West t-stat in brackets) under FF5+MOM and q5.
- Column 5: the decision taken.

| # | Strategy | Origin | FF5+MOM α (t) | q5 α (t) | Outcome |
|---|---|---|---|---|---|
| 1 | **PI** — z(CAPEX/AT) + z(ROA) − z(ΔLeverage), all firms, from 1967 | Working note (initial idea) | 0.15 (1.6) | 0.11 (1.1) | Rejected |
| 2 | **DELEV** — −ΔLeverage alone | Working note | 0.07 (0.8) | 0.07 (0.8) | Rejected |
| 3 | **DFC** — high-CAPEX firms, low vs high debt financing, from 1967 | Working note; pre-registered | 0.26 (1.8) | 0.15 (0.9) | Borderline; not significant after correction |
| 4 | **Timing overlay on DFC** — 1.5 / 1 / 0.5 exposure by fed funds regime | Working note; pre-registered (+ amendment before outcomes) | value added −0.08 (−1.4) | — | Rejected |
| 5 | **M1** — DFC + cheapness tilt | Team proposal; pre-registered | 0.26 (1.8) | 0.13 (0.8) | No improvement beyond factors |
| 6 | **M2** — DFC + cheapness & improving profitability tilt | Team proposal; pre-registered | 0.28 (1.9) | 0.15 (0.9) | No improvement beyond factors |
| 7 | **M3** — distressed investment recovery | Team proposal; pre-registered | 0.21 (0.9) | 0.23 (0.9) | Rejected |
| 8 | **INNOV_A** — R&D-intensive firms, low vs high leverage, from 1975 | Working note (R&D + balance sheet); pre-registered | 0.16 (0.9) | 0.01 (0.0) | Rejected |
| 9 | **INNOV_B** — R&D-to-market, from 1975 | Chan, Lakonishok & Sougiannis (2001); pre-registered | 0.55 (3.4) | 0.23 (1.4) | Significant; explained by q5. Kept as the **benchmark** |
| 10 | **BUILD** — z(R&D/ME) + z(CAPX/ME) − z(ΔDebt/AT) | Pre-registered, with a value-added rule vs B | 0.26 (2.0) | 0.29 (2.0) | Value added over B 0.12 (t 0.9) → rule not met |
| 11 | **RDV** — z(R&D/ME) + z((OIBDP+R&D)/EV) + z(Δ(OIBDP+R&D)/AT) | Pre-registered, with a value-added rule vs B | **0.53 (4.0)** | **0.42 (2.9)** | Value added over B 0.32 (t 2.8) → **selected strategy** |

## Notes

- **Not counted as tests.** The decomposition sorts used to diagnose PI (CAPX, ROA, CAPX+ROA alone) were diagnostics, not candidate strategies; all were insignificant.
- **Implementation correction in test 8.** The first run of INNOV_A left its long leg empty in 2014–2017 (zero-debt ties). This was fixed without changing any definition; both runs are documented in the archived pre-registration.
- **Multiple-testing adjustment.** Bonferroni-adjusted p-values in `results/` use ×11. RDV's FF5+MOM alpha remains significant (adjusted p ≈ 0.001).
- **Archived pre-registrations.** The documents for tests 3–10 are archived in the team's Claude project. The RDV pre-registration is in `docs/preregistration_rdv.md`.
