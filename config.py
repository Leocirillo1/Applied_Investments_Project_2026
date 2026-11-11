"""
Central configuration - "Underpriced innovators with real, improving earnings power" (RDV).

Strategy (equal weights, nothing estimated from the data):
    universe : US common stocks (NYSE/AMEX/NASDAQ), non-financial, R&D reporters (XRD > 0)
    score    : z(XRD/AT) + z((OIBDP + XRD)/EV) + z(delta[(OIBDP + XRD)/AT_{t-1}])   equal weights
    portfolio: NYSE quintiles, value-weighted, long Q5 - short Q1, rebalanced every end of June

Every design choice lives here, so it is changed in ONE place.
"""
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths (relative to this file -> the repo can be moved / cloned)
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "Data"                       # raw WRDS extracts (NOT on GitHub)
DATA_FACTORS = DATA_RAW / "factors"            # downloaded factor files
RESULTS = ROOT / "results"
DATA_PROC = RESULTS / "processed"              # cleaned intermediate files (NOT on GitHub)
OUT_TABLES = RESULTS / "tables"
OUT_FIGURES = RESULTS / "figures"

CRSP_FILE = DATA_RAW / "Prix 1.csv"            # CRSP v2 (CIZ) monthly stock file
COMPUSTAT_FILE = DATA_RAW / "Fundamentals.csv" # Compustat Fundamentals Annual
CCM_LINK_FILE = DATA_RAW / "ccm_link.csv"      # CRSP/Compustat Merged link table (required)
CRSP_DAILY_PATTERN = "crsp_daily_*.csv.gz"     # CRSP daily files (bid, ask, high, low), 1974-2025
# Compustat is linked to CRSP with the official CCM link table (LINKTYPE LU/LC, LINKPRIM P/C, link
# valid at the fiscal year-end).

# ----------------------------------------------------------------------------
# Sample
# ----------------------------------------------------------------------------
# R&D reporting became mandatory with SFAS 2 (1975): first formation June 1975,
# first return month July 1975.
FIRST_FORMATION_YEAR = 1975
LAST_RETURN_MONTH = "2025-12"

# ----------------------------------------------------------------------------
# Universe
# ----------------------------------------------------------------------------
EXCLUDE_FINANCIALS = True       # SIC 6000-6999 (banks, insurers, REITs, funds)
# Only filters needed by the signal itself: R&D reporters (XRD > 0) with positive market equity.
# A firm must also have the previous fiscal year in Compustat (lagged total assets > 0): this
# limits Compustat back-fill bias (Fama-French 1993) and is the denominator of the improvement term.
MIN_LAGGED_ASSETS = 0.0

# ----------------------------------------------------------------------------
# Timing (NO look-ahead)
# ----------------------------------------------------------------------------
# Fiscal year ending in calendar year t-1 -> used at the end of June t, held July t - June t+1.
# Accounting data are therefore 6 to 17 months old when first used (enforced by asserts).
FORMATION_MONTH = 6
MIN_REPORTING_LAG_MONTHS = 6

# ----------------------------------------------------------------------------
# Signal and portfolios
# ----------------------------------------------------------------------------
WINSOR_PCT = 0.01               # each input winsorised 1% / 99% within each June
N_PORTFOLIOS = 5                # quintiles; strategy = Q5 - Q1
NYSE_BREAKPOINTS = True
STRATEGY = "RDV"
STRATEGY_NAME = "Underpriced innovators with real, improving earnings power (RDV)"

# ----------------------------------------------------------------------------
# Evaluation
# ----------------------------------------------------------------------------
NW_LAGS = 6
REG_START = "1975-07"
REG_END = None                  # None = last month where all factors are available
MODELS = {
    "CAPM":     ["MKT"],
    "FF3":      ["MKT", "SMB", "HML"],
    "FF3+MOM":  ["MKT", "SMB", "HML", "MOM"],
    "FF5":      ["MKT", "SMB5", "HML5", "RMW", "CMA"],
    "FF5+MOM":  ["MKT", "SMB5", "HML5", "RMW", "CMA", "MOM"],
    "q":        ["Q_MKT", "Q_ME", "Q_IA", "Q_ROE"],
    "q5":       ["Q_MKT", "Q_ME", "Q_IA", "Q_ROE", "Q_EG"],
}

# ----------------------------------------------------------------------------
# Trading costs (Session 3). Half-spreads are measured from the CRSP daily files (src/spreads.py);
# price impact uses the size-group lambdas below. The break-even cost needs no assumption.
# ----------------------------------------------------------------------------
TC_LAMBDA = {"micro": 2.5, "small": 1.5, "large": 1.0}                 # 1% of ADV -> 25/15/10 bps
TC_AUM_USD = 100e6              # per leg, Dec-2025 dollars, scaled back with total market cap
TC_TRADING_DAYS = 21

# ----------------------------------------------------------------------------
# Factor sources (step 1)
# ----------------------------------------------------------------------------
FF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FF_FILES = {
    "ff3": "F-F_Research_Data_Factors_CSV.zip",
    "ff5": "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "mom": "F-F_Momentum_Factor_CSV.zip",
}
GLOBALQ_PAGE = "https://global-q.org/factors.html"
GLOBALQ_UPLOADS = "https://global-q.org/uploads/1/2/2/6/122679606/"

for _p in (DATA_FACTORS, DATA_PROC, OUT_TABLES, OUT_FIGURES):
    _p.mkdir(parents=True, exist_ok=True)
