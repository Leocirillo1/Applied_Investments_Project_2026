"""
Step 3 - Clean Compustat Fundamentals Annual and build the accounting inputs of the RDV signal.

Filters: INDL / STD / D / C / USD (standard Compustat screens), one report per firm and
calendar year of the fiscal-year-end (the latest one if a firm changes fiscal year end).

Variables (from the annual report with fiscal year end `datadate`; t-1 = the PREVIOUS FISCAL
YEAR of the same firm, exact fyear-1 match -> 2 consecutive years needed, which also limits
Compustat back-fill bias as in Fama-French):
  RDV inputs   xrd, oibdp, dlc, dltt, che (enterprise value) and
               opr   = (OIBDP + XRD)_t / AT_{t-1}   operating profitability with R&D added back
               d_opr = opr_t - opr_{t-1}            improvement (needs 3 consecutive years)

Missing values are kept missing (never replaced by zero, as required in class).

Timing (NO look-ahead): a report with fiscal year end in calendar year Y is first used at
the end of June of year Y+1 (Fama-French convention). The gap between datadate and the
first use is therefore between 6 and 17 months. This is checked by an assertion.

Output: results/processed/compustat_signals.parquet
"""
import numpy as np
import pandas as pd

import config as C
from src.utils import save_df


def main():
    cs = pd.read_csv(C.COMPUSTAT_FILE, dtype={"GVKEY": str}, low_memory=False)
    rep = {"rows_raw": len(cs)}
    cs = cs[(cs["indfmt"] == "INDL") & (cs["datafmt"] == "STD") & (cs["popsrc"] == "D")
            & (cs["consol"] == "C") & (cs["curcd"] == "USD")].copy()
    rep["after_standard_screens"] = len(cs)

    cs["datadate"] = pd.to_datetime(cs["datadate"])
    cs = cs.rename(columns={"GVKEY": "gvkey"})

    # one report per firm-fiscal year (latest datadate), then per firm-calendar year
    cs = cs.sort_values(["gvkey", "fyear", "datadate"])
    cs = cs.drop_duplicates(["gvkey", "fyear"], keep="last")
    cs["year_fye"] = cs["datadate"].dt.year
    cs = cs.drop_duplicates(["gvkey", "year_fye"], keep="last")
    rep["firm_years_unique"] = len(cs)

    # total assets must be positive to be used as a denominator
    cs.loc[~(cs["at"] > 0), "at"] = np.nan

    # previous fiscal year of the SAME firm (exact fyear-1 match, not just previous row)
    lag = cs[["gvkey", "fyear", "at"]].copy()
    lag["fyear"] = lag["fyear"] + 1
    cs = cs.merge(lag, on=["gvkey", "fyear"], how="left", suffixes=("", "_lag"))

    # RDV input: operating profitability with R&D added back (OIBDP is after R&D expense)
    #   opr = (OIBDP + XRD)_FY / AT_{FY-1}; its previous value comes from the SAME firm's FY-1 report
    cs["opr"] = (cs["oibdp"] + cs["xrd"]) / cs["at_lag"]
    lag2 = cs[["gvkey", "fyear", "opr"]].copy()
    lag2["fyear"] = lag2["fyear"] + 1
    cs = cs.merge(lag2, on=["gvkey", "fyear"], how="left", suffixes=("", "_lag"))
    cs["d_opr"] = cs["opr"] - cs["opr_lag"]

    cs = cs[cs["at_lag"] > C.MIN_LAGGED_ASSETS]          # previous fiscal year required
    rep["firm_years_with_previous_year"] = len(cs)
    cs = cs.replace([np.inf, -np.inf], np.nan)
    rep["firm_years_with_rd"] = int((cs["xrd"] > 0).sum())

    # ---- timing: first portfolio formation that may use this report ------------
    cs["formation_year"] = cs["year_fye"] + 1
    cs["formation_date"] = pd.to_datetime(
        dict(year=cs["formation_year"], month=C.FORMATION_MONTH, day=1)) + pd.offsets.MonthEnd(0)
    lag_months = ((cs["formation_date"].dt.year - cs["datadate"].dt.year) * 12
                  + (cs["formation_date"].dt.month - cs["datadate"].dt.month))
    assert lag_months.min() >= C.MIN_REPORTING_LAG_MONTHS, "look-ahead: accounting data used too early!"
    rep["reporting_lag_months_min"] = int(lag_months.min())
    rep["reporting_lag_months_max"] = int(lag_months.max())

    keep = ["gvkey", "conm", "datadate", "fyear", "formation_year", "gsector",
            "xrd", "oibdp", "dlc", "dltt", "che", "d_opr"]
    out = cs[keep].reset_index(drop=True)
    path = save_df(out, C.DATA_PROC / "compustat_signals")

    rep = pd.Series(rep, name="value")
    rep.to_csv(C.OUT_TABLES / "data_compustat_cleaning_report.csv")
    print(rep.to_string())
    print(out[["xrd", "oibdp", "d_opr"]].describe(percentiles=[.01, .5, .99]).round(3).to_string())
    print("saved", path)


if __name__ == "__main__":
    main()
