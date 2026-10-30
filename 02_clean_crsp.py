"""
Step 2 - Clean the CRSP monthly stock file (CRSP v2 / CIZ format from WRDS).

Universe (all point-in-time, i.e. using the information valid in that month):
  * SecurityType == 'EQTY'                -> drops funds, ETFs, closed-end funds, derivatives
  * not an ADR (flag inside SecurityNm)   -> CIZ equivalent of dropping share code 3x
  * PrimaryExch in N / A / Q              -> NYSE, AMEX, NASDAQ  (= legacy EXCHCD 1, 2, 3)
  * one row per PERMNO-month

Returns: MthRet in the CIZ format ALREADY INCLUDES DELISTING RETURNS (CRSP compounds the
delisting payment into the final month), so no separate delisting adjustment is made
(adding DLRET as in the legacy format would double count).

Output: results/processed/crsp_monthly.parquet with
  permno, date (month end), ret, prc, me ($ million), me_lag (previous month ME),
  vol (shares, for trading volume), exch (N/A/Q), siccd (to exclude financials)

Memory friendly: the ~1 GB CSV is read in chunks with only the needed columns.
"""
import time

import numpy as np
import pandas as pd

import config as C
from src.utils import save_df

USECOLS = ["PERMNO", "PrimaryExch", "SecurityNm",
           "SecurityType", "SICCD", "MthCalDt", "MthPrc", "MthCap", "MthRet",
           "MthVol", "ShrOut"]
CHUNK = 500_000


def clean_chunk(df: pd.DataFrame, stats: dict) -> pd.DataFrame:
    stats["rows_raw"] += len(df)
    if "SecurityType" in df.columns:
        df = df[df["SecurityType"] == "EQTY"]
    stats["after_equity"] += len(df)
    # ADR flag: second ';'-separated block of SecurityNm, e.g. "COM NONE ADR"
    share_desc = df["SecurityNm"].fillna("").str.split(";").str[1].fillna("")
    df = df[~share_desc.str.contains(r"\bADR\b", regex=True)]
    stats["after_adr"] += len(df)
    df = df[df["PrimaryExch"].isin(["N", "A", "Q"])]
    stats["after_exchange"] += len(df)

    out = pd.DataFrame({
        "permno": pd.to_numeric(df["PERMNO"], errors="coerce").astype("int64"),
        "date": pd.to_datetime(df["MthCalDt"], errors="coerce") + pd.offsets.MonthEnd(0),
        "ret": pd.to_numeric(df["MthRet"], errors="coerce"),
        "prc": pd.to_numeric(df["MthPrc"], errors="coerce").abs(),
        "mthcap": pd.to_numeric(df["MthCap"], errors="coerce"),
        "shrout": pd.to_numeric(df["ShrOut"], errors="coerce"),
        "vol": pd.to_numeric(df["MthVol"], errors="coerce"),
        "exch": df["PrimaryExch"].astype(str),
        "siccd": pd.to_numeric(df["SICCD"], errors="coerce"),
    })
    return out


def main():
    t0 = time.time()
    stats = {k: 0 for k in ["rows_raw", "after_equity", "after_adr", "after_exchange"]}
    pieces = []
    print("reading", C.CRSP_FILE)
    reader = pd.read_csv(C.CRSP_FILE, usecols=lambda c: c in USECOLS, dtype=str,
                         keep_default_na=False, na_values=[""], chunksize=CHUNK)
    for chunk in reader:
        pieces.append(clean_chunk(chunk, stats))
    crsp = pd.concat(pieces, ignore_index=True)
    del pieces

    # Market equity in $ million. MthCap is in $ thousands (= |price| x shares in thousands).
    me = crsp["mthcap"].where(crsp["mthcap"] > 0, crsp["prc"] * crsp["shrout"])
    crsp["me"] = me / 1000.0
    crsp.loc[~(crsp["me"] > 0), "me"] = np.nan
    crsp = crsp.drop(columns=["mthcap", "shrout"])

    # One row per PERMNO-month
    n0 = len(crsp)
    crsp = crsp.dropna(subset=["date"]).sort_values(["permno", "date"])
    crsp = crsp.drop_duplicates(["permno", "date"], keep="last")
    stats["duplicates_removed"] = n0 - len(crsp)

    # Previous month's market equity = value weight for this month's return.
    # Only used if the previous row is exactly the previous calendar month.
    prev_date = crsp.groupby("permno")["date"].shift(1)
    prev_me = crsp.groupby("permno")["me"].shift(1)
    consecutive = prev_date == (crsp["date"] - pd.offsets.MonthEnd(1))
    crsp["me_lag"] = prev_me.where(consecutive)

    # Sanity: returns below -100% are impossible
    bad = crsp["ret"] < -1
    crsp.loc[bad, "ret"] = np.nan
    stats["ret_below_-100%_set_missing"] = int(bad.sum())

    crsp = crsp.reset_index(drop=True)
    path = save_df(crsp, C.DATA_PROC / "crsp_monthly")

    # ---- report ---------------------------------------------------------------
    stats["rows_final"] = len(crsp)
    stats["permnos"] = crsp["permno"].nunique()
    stats["first_month"] = str(crsp["date"].min().date())
    stats["last_month"] = str(crsp["date"].max().date())
    stats["share_missing_ret"] = round(crsp["ret"].isna().mean(), 4)
    rep = pd.Series(stats, name="value")
    rep.to_csv(C.OUT_TABLES / "data_crsp_cleaning_report.csv")
    print(rep.to_string())
    by_year = crsp.groupby(crsp["date"].dt.year).agg(
        n_stocks=("permno", "nunique"), total_me_bn=("me", lambda x: x.sum() / 1000 / 12))
    by_year.to_csv(C.OUT_TABLES / "data_crsp_by_year.csv")
    print(f"saved {path}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
