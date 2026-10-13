"""
Central configuration - "Underpriced innovators with real, improving earnings power" (RDV).

Strategy (pre-registered, docs/preregistration_rdv.md):
    universe : US common stocks (NYSE/AMEX/NASDAQ), non-financial, R&D reporters (XRD > 0)
    score    : z(XRD/ME) + z((OIBDP + XRD)/EV) + z(delta[(OIBDP + XRD)/AT_{t-1}])   equal weights
    portfolio: NYSE quintiles, value-weighted, long Q5 - short Q1, rebalanced every end of June
Benchmark "B" = R&D-to-market alone (XRD/ME), used for the pre-registered value-added test.

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
CCM_LINK_FILE = DATA_RAW / "ccm_link.csv"      # CRSP/Compustat link table (optional, recommended)
# Without CCM_LINK_FILE, Compustat is linked to CRSP by CUSIP (point-in-time, see step 4).

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
# Data-quality screen inherited from the project's common universe (unchanged since the
# pre-registration): complete core accounting data for two consecutive fiscal years.
SCREEN_ITEMS = ["capx_at", "roa", "dlev", "ddebt_at"]
ROA_DENOMINATOR = "at"          # roa = OIBDP / AT (used only by the screen)
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
BENCHMARK = "B"                 # R&D-to-market alone
STRATEGY_NAME = "Underpriced innovators with real, improving earnings power (RDV)"
MAIN_WEIGHTING = "VW"           # value-weighted; EW only as robustness

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
N_TESTS_REGISTER = 11           # strategies tested in the project (docs/test_register.md)
VALUE_ADDED_MODEL = "FF5+MOM"   # pre-registered decision test: RDV = a + b*B + FF5+MOM

# ----------------------------------------------------------------------------
# Trading costs (Session 3). Spreads are ASSUMPTIONS by size group until bid/ask data
# are added (see README, "Data to download"). The break-even cost needs no assumption.
# ----------------------------------------------------------------------------
TC_HALF_SPREAD = {"micro": 0.0100, "small": 0.0050, "large": 0.0015}   # one-way, decimal
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
