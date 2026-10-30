# Underpriced innovators with real, improving earnings power (RDV)
Applied Investments — portfolio strategy project (HEC Lausanne, Fall 2026)

A long-short US equity strategy, evaluated with the alphas of seven factor models:
CAPM, FF3, FF3+MOM, FF5, FF5+MOM, q-factor and q5.

## The strategy

Every end of June, among US non-financial firms that report R&D:

$$\text{Score} = z\!\left(\frac{R\&D}{ME}\right) + z\!\left(\frac{OIBDP + R\&D}{EV}\right) + z\!\left(\Delta\frac{OIBDP + R\&D}{AT_{-1}}\right)$$

- **Inputs:**
  - **R&D / ME:** innovation effort relative to price (Chan, Lakonishok & Sougiannis 2001).
  - **(OIBDP + R&D) / EV:** cheap relative to true earnings power. R&D is added back because accounting expenses it (Ball, Gerakos, Linnainmaa & Nikolaev 2015). EV = ME + DLC + DLTT − CHE.
  - **Δ (OIBDP + R&D) / AT₋₁:** earnings power is improving.
- **Score:** equal weights. Each input is winsorised at 1%/99% and z-scored within each June.
- **Portfolios:** quintiles with NYSE breakpoints. **Long Q5, short Q1, value-weighted**, held July to June.
- **Story:** accounting hides the value of innovation. We buy firms that invest heavily in R&D relative to their price, are cheap once R&D is added back to earnings, and whose earnings power is improving.
- **Design fixed in advance:** the definition was written down before the backtest and never changed (`docs/preregistration_rdv.md`).

## How to run

1. After cloning, copy the raw WRDS files into the `Data/` folder, with exactly these names
   (they are not on GitHub because WRDS data are licensed):
   - `Prix 1.csv` (CRSP monthly)
   - `Fundamentals.csv` (Compustat annual)
   - `ccm_link.csv` (CRSP/Compustat Merged link table, see "Data to download" below)
2. Install packages once: `pip install -r requirements.txt`.
3. Run `python run_all.py` (about 2–3 minutes).
   - After changing `config.py`: `python run_all.py --from 4 --skip-download`.

Main results: `results/tables/results.xlsx` and `results/figures/`.

## Repository

| File | What it does |
|---|---|
| `config.py` | All design choices: sample, universe, signal, portfolios, models, cost assumptions |
| `01_download_factors.py` | FF3, FF5 (2×3), MOM from Ken French; q and q5 from global-q.org |
| `02_clean_crsp.py` | CRSP monthly: common equity, NYSE/AMEX/NASDAQ, no ADRs/funds, market cap, lagged ME |
| `03_clean_compustat.py` | Compustat annual: inputs of the signal, previous-year values, 6-month reporting lag |
| `04_link_and_signal.py` | Compustat↔CRSP link, June universe, RDV score, NYSE quintiles |
| `05_portfolio_returns.py` | Monthly VW/EW returns of Q1–Q5 and Q5−Q1; quintile characteristics; sector weights |
| `06_alpha_regressions.py` | 7-model alphas (Newey-West), factor loadings, GRS test, performance statistics |
| `07_trading_costs.py` | Turnover (Session 3 formula), spread and price-impact costs, net alphas, break-even cost |
| `08_figures.py` | Figures for the paper and the presentation |
| `09_robustness.py` | Sub-periods, size filters, price filter, deciles, breakpoints, winsorisation |
| `10_fama_macbeth.py` | Fama-MacBeth regressions (score, components, size, momentum) |
| `src/` | Helpers: I/O, winsorise/z-score, regressions, GRS, portfolio sorts, the RDV signal |
| `tools/validate_pipeline.py` | Data check: value-weighted return of the cleaned CRSP universe vs the Fama-French market |
| `docs/` | Definition of the strategy, written before the backtest |

## Methodology and how biases are avoided

- **No look-ahead.**
  - Fiscal years ending in calendar year t−1 are first used at the end of June t, so accounting data are at least 6 months old (asserted in steps 3 and 4).
  - Market equity is taken at the end of June t.
  - Winsorisation, z-scores and NYSE breakpoints use only the June-t cross-section.
  - Monthly value weights use the previous month-end market cap.
- **Universe.**
  - US common stocks (CRSP v2/CIZ `SecurityType = EQTY`, no ADRs) listed on NYSE, AMEX or NASDAQ in the month considered.
  - Compustat linked to CRSP with the official CRSP/Compustat Merged link table (link types LU/LC, primary links P/C, link valid at the fiscal year-end).
  - Financials (SIC 6000–6999) excluded.
  - Only filters needed by the signal: R&D reporters (XRD > 0) with positive market equity, and the previous fiscal year in Compustat (limits back-fill bias). No other accounting item is required; a missing EV yield or improvement term counts as 0 in the score.
  - **R&D reporters only:** missing R&D is never treated as zero.
  - Dead firms are included.
- **Delisting returns** are already included in CIZ monthly returns.
- **Sample:** 1975-07 → 2025-12 (606 months; R&D reporting mandatory since SFAS 2, 1975).
- **Inference:**
  - Newey-West (6 lags).
  - All 7 models on the same sample.
  - GRS joint test.
- **Trading costs** (Session 3):
  - Turnover = Σ|w_t − w*_t|, with weights drifting with returns.
  - Cost = |Δw| × half-spread + |Δw| × λ√(trade / ADV), with λ = 2.5 / 1.5 / 1.0 for micro / small / large caps.
  - Spreads are size-group assumptions until bid/ask data are added (see below). The break-even cost needs no assumption.

## Validation checks (`python tools/validate_pipeline.py`)

- Value-weighted return of the cleaned CRSP universe vs the Fama-French market: correlation 0.999 (1967–2025).

## Data to download at WRDS

**Required** (with `Prix 1.csv` and `Fundamentals.csv`):

1. **CRSP → CRSP/Compustat Merged → Linking Table** → `Data/ccm_link.csv`
   - Company codes: search the entire database. Variables: GVKEY, LPERMNO, LPERMCO, LINKTYPE, LINKPRIM, LIID, LINKDT, LINKENDDT.
   - Output: comma-delimited (.csv), dates YYYY-MM-DD. Step 4 stops with a clear message if the file is missing.

**Next step, for the trading costs** (not used yet by the code):

2. **CRSP Stock v2 (CIZ) → Daily Stock File**
   - Variables: `PERMNO, DlyCalDt, DlyPrc, DlyPrcFlg, DlyBid, DlyAsk, DlyHigh, DlyLow, DlyVol`, from 1974 to 2025, entire database, gzip-compressed csv.
   - Split the dates into about 10-year queries and save them as `Data/crsp_daily_1.csv.gz`, `crsp_daily_2.csv.gz`, …
   - Use: closing bid/ask quoted spreads where they exist, high/low spread estimates (Corwin-Schultz 2012; Abdi-Ranaldo 2017) for the other months, remaining gaps filled with size-group means (the professor's method), and average daily dollar volume for the price-impact term.

## Known limitations

- Spreads are assumed by size group until the daily bid/ask data are added.
- The alpha is weaker after 2000: FF5+MOM 0.28%/month (t 1.6) vs 0.61 (t 3.0) over 1975–1999.
- The alpha is smaller and not significant among large caps only (FF5+MOM 0.22%/month, t 1.7).
