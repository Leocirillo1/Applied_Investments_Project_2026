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
- **Pre-registration:** the design was written down before testing (`docs/preregistration_rdv.md`).
- **Benchmark B** = R&D/ME alone. RDV was selected because its value added over B is significant (pre-registered rule).
- **Test register:** every strategy tested in the project is listed in `docs/test_register.md`.

## How to run

1. After cloning, copy the raw WRDS files into the `Data/` folder, with exactly these names
   (they are not on GitHub because WRDS data are licensed):
   - `Prix 1.csv` (CRSP monthly)
   - `Fundamentals.csv` (Compustat annual)
   - optionally `ccm_link.csv` (link table)
2. Install packages once: `pip install -r requirements.txt`.
3. Run `python run_all.py`, or double-click `tools/run_all.bat` (about 2–3 minutes).
   - After changing `config.py`: `python run_all.py --from 4 --skip-download`.

Main results: `results/tables/results.xlsx` and `results/figures/`.

## Repository

| File | What it does |
|---|---|
| `config.py` | All design choices: sample, universe, signal, portfolios, models, cost assumptions |
| `01_download_factors.py` | FF3, FF5 (2×3), MOM from Ken French; q and q5 from global-q.org |
| `02_clean_crsp.py` | CRSP monthly: common equity, NYSE/AMEX/NASDAQ, no ADRs/funds, market cap, lagged ME |
| `03_clean_compustat.py` | Compustat annual: inputs of the signal, previous-year values, 6-month reporting lag |
| `04_link_and_signal.py` | Compustat↔CRSP link, June universe, RDV score, NYSE quintiles (and benchmark B) |
| `05_portfolio_returns.py` | Monthly VW/EW returns of Q1–Q5 and Q5−Q1; quintile characteristics; sector weights |
| `06_alpha_regressions.py` | 7-model alphas (Newey-West), loadings, GRS, performance, value added over B |
| `07_trading_costs.py` | Turnover (Session 3 formula), spread and price-impact costs, net alphas, break-even cost |
| `08_figures.py` | Figures for the paper and the presentation |
| `09_robustness.py` | Sub-periods, size filters, price filter, deciles, breakpoints, winsorisation, single components |
| `10_fama_macbeth.py` | Fama-MacBeth regressions (score, components, size, momentum) |
| `src/` | Helpers: I/O, winsorise/z-score, regressions, GRS, portfolio sorts, the RDV signal |
| `tools/validate_pipeline.py` | Data checks: market return vs Fama-French; replication of the Session 1 asset-growth example |
| `tools/permnos_rdv_universe.txt` | PERMNO list for a targeted download of CRSP daily data (see below) |
| `docs/` | Pre-registration of RDV and the test register |

## Methodology and how biases are avoided

- **No look-ahead.**
  - Fiscal years ending in calendar year t−1 are first used at the end of June t, so accounting data are at least 6 months old (asserted in steps 3 and 4).
  - Market equity is taken at the end of June t.
  - Winsorisation, z-scores and NYSE breakpoints use only the June-t cross-section.
  - Monthly value weights use the previous month-end market cap.
- **Universe.**
  - US common stocks (CRSP v2/CIZ `SecurityType = EQTY`, no ADRs) listed on NYSE, AMEX or NASDAQ in the month considered.
  - Financials (SIC 6000–6999) excluded.
  - Complete core accounting data required (two consecutive fiscal years).
  - **R&D reporters only:** missing R&D is never treated as zero.
  - Dead firms are included.
- **Delisting returns** are already included in CIZ monthly returns.
- **Sample:** 1975-07 → 2025-12 (606 months; R&D reporting mandatory since SFAS 2, 1975).
- **Inference:**
  - Newey-West (6 lags).
  - All 7 models on the same sample.
  - GRS joint test.
  - Bonferroni-adjusted p-values for the 11 strategies tested in the project.
- **Trading costs** (Session 3):
  - Turnover = Σ|w_t − w*_t|, with weights drifting with returns.
  - Cost = |Δw| × half-spread + |Δw| × λ√(trade / ADV), with λ = 2.5 / 1.5 / 1.0 for micro / small / large caps.
  - Spreads are size-group assumptions until bid/ask data are added (see below). The break-even cost needs no assumption.

## Validation checks (`python tools/validate_pipeline.py`)

- Value-weighted return of the cleaned CRSP universe vs the Fama-French market: correlation 0.999 (1967–2025).
- Session 1 asset-growth example: VW 10−1 = −0.34%/month (slides −0.26%), EW −0.99% (slides −0.85%).

## Data to download at WRDS (to improve the data and the cost estimates)

1. **CRSP/Compustat Merged → Compustat CRSP Link** → `Data/ccm_link.csv`
   - Variables: GVKEY, LPERMNO, LPERMCO, LINKTYPE, LINKPRIM, LIID, LINKDT, LINKENDDT.
   - The official link replaces the CUSIP fallback, which misses about 6–30% of market cap. Used automatically.
2. **CRSP Stock v2 (CIZ) → Monthly Stock File**: add
   - `ShareType, SecuritySubType, USIncFlg, IssuerType, ConditionalType, TradingStatusFlg`: exact legacy share-code 10/11 and exchange filters.
   - `MthRetx`: price return without dividends, used in the Session 3 turnover formula.
3. **CRSP Stock v2 (CIZ) → Delisting Information (StkDelists)**: `PERMNO, DelistingDt, DelActionType, DelReasonType, DelStatusType, DelPaymentType, DelRet`.
   - Lets us check delisting returns and apply a Shumway-type correction when a performance-related delisting has no return.
4. **CRSP Stock v2 (CIZ) → Daily Stock File** (for prof-style transaction costs):
   - Variables: `PERMNO, DlyCalDt, DlyPrc, DlyBid, DlyAsk, DlyHigh, DlyLow, DlyVol`, from 1974 to 2025.
   - To keep the file small, upload `tools/permnos_rdv_universe.txt` as the company list (8,663 PERMNOs).
   - Use: closing bid/ask quoted spreads where they exist (NASDAQ from the 1980s, NYSE/AMEX from the 1990s), as in the slides.
   - Use: high/low spread estimates (Corwin-Schultz 2012; Abdi-Ranaldo 2017) for the other months; remaining gaps filled with size-group means, the professor's method.
   - Use: average daily dollar volume for the price-impact term.
5. **Compustat Fundamentals Annual**: add
   - `RDIP` (in-process R&D written off at acquisitions; to be removed from XRD before 2009);
   - `OIADP, DP` (EBIT version of the earnings yield);
   - `CEQ, SEQ, TXDITC, PSTK, PSTKRV, PSTKL` (book equity: book-to-market control);
   - `SICH` (historical SIC).
6. *Optional:* **WRDS Intraday Indicators** (TAQ-based effective spreads, 1993+) give exact effective spreads for the recent period.

## Known limitations

- The Compustat↔CRSP link is CUSIP-based until `ccm_link.csv` is added.
- Spreads are assumed by size group until the daily bid/ask data are added.
- The alpha is weaker after 2000: FF5+MOM 0.31%/month (t 1.8) vs 0.66 (t 3.4) over 1975–1999.
