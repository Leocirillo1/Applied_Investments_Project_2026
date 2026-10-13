"""
Step 5 - Monthly returns of the RDV quintiles and of the RDV long-short strategy.

Portfolios formed at the end of June of year t are held July t - June t+1 (annual rebalancing).
  * VW return: weights = previous month-end market cap (= buy-and-hold within the year)
  * EW return: simple average (robustness only)
A delisted stock keeps its last CRSP return (CIZ returns include the delisting return).

Outputs (results/processed/ and results/tables/):
  portfolio_returns.parquet         long: signal, weighting, portfolio, date, ret, n
  portfolio_returns_wide.csv        one column per signal_weighting_portfolio
  quintile_characteristics_RDV.csv  time-series averages of yearly medians/means by quintile
  sector_weights_RDV.csv            average Fama-French 12 weights of the long (Q5) and short (Q1) legs
"""
import pandas as pd

import config as C
from src.portfolio import holding_returns, long_short_wide
from src.utils import load_df, save_df

LS = f"Q{C.N_PORTFOLIOS}-Q1"


def main():
    crsp = load_df(C.DATA_PROC / "crsp_monthly")[["permno", "date", "ret", "me_lag"]]
    crsp = crsp[crsp["date"] <= pd.Timestamp(C.LAST_RETURN_MONTH) + pd.offsets.MonthEnd(0)]
    panel = load_df(C.DATA_PROC / "formation_panel")

    out = []
    for s in (C.STRATEGY,):
        hr = holding_returns(crsp, panel, f"port_{s}", C.FORMATION_MONTH)
        n = hr.pivot(index="date", columns="port", values="n")
        n.columns = [f"Q{int(c)}" for c in n.columns]
        n[LS] = n[f"Q{C.N_PORTFOLIOS}"] + n["Q1"]
        for wname in ("VW", "EW"):
            wide = long_short_wide(hr, wname.lower(), C.N_PORTFOLIOS)
            long = wide.stack().rename("ret").to_frame()
            long["n"] = n.stack()
            long = long.reset_index()
            long.columns = ["date", "portfolio", "ret", "n"]
            long.insert(0, "weighting", wname)
            long.insert(0, "signal", s)
            out.append(long)
    rets = pd.concat(out, ignore_index=True)
    save_df(rets, C.DATA_PROC / "portfolio_returns")
    wide = rets.pivot_table(index="date", columns=["signal", "weighting", "portfolio"], values="ret")
    wide.columns = ["_".join(c) for c in wide.columns]
    wide.to_csv(C.DATA_PROC / "portfolio_returns_wide.csv", float_format="%.6f")

    # ---- characteristics of the RDV quintiles at formation --------------------------
    p = panel.copy()
    p["port"] = "Q" + p["port_RDV"].astype(int).astype(str)
    p["is_nyse"] = (p["exch"] == "N").astype(float)
    agg = p.groupby(["formation_year", "port"]).agg(
        n_stocks=("permno", "size"),
        me_mean=("me_june", "mean"),
        me_median=("me_june", "median"),
        me_share=("me_june", "sum"),
        pct_nyse=("is_nyse", "mean"),
        score=("score_RDV", "median"),
        rd_to_market=("rdm", "median"),
        earnings_yield_rd_added=("eyr", "median"),
        change_profitability_rd_added=("dopr", "median"),
        rd_to_assets=("rd_at", "median"),
        leverage=("lev", "median"),
        asset_growth=("asset_growth", "median"),
    )
    agg["me_share"] = agg["me_share"] / agg.groupby(level=0)["me_share"].transform("sum")
    char = agg.groupby(level=1).mean().T
    char.to_csv(C.OUT_TABLES / "quintile_characteristics_RDV.csv", float_format="%.4f")
    print("RDV quintile characteristics (time-series average of yearly medians/means):")
    print(char.round(3).to_string())
    # ---- sector weights of the legs (June market cap weights) -------------------------
    names = {1: "NoDur", 2: "Durbl", 3: "Manuf", 4: "Enrgy", 5: "Chems", 6: "BusEq", 7: "Telcm",
             8: "Utils", 9: "Shops", 10: "Hlth", 11: "Money", 12: "Other"}
    legs = panel[panel["port_RDV"].isin([1, C.N_PORTFOLIOS])].copy()
    legs["leg"] = legs["port_RDV"].map({C.N_PORTFOLIOS: "long", 1: "short"})
    legs["w"] = legs["me_june"] / legs.groupby(["formation_year", "leg"])["me_june"].transform("sum")
    sw = legs.groupby(["leg", "formation_year", "ff12"])["w"].sum().unstack(fill_value=0)
    sw = sw.groupby(level=0).mean() * 100
    sw.columns = [names[c] for c in sw.columns]
    sw.to_csv(C.OUT_TABLES / "sector_weights_RDV.csv", float_format="%.2f")
    print("\nSector weights of the legs (%):\n", sw.round(1).to_string())

    m = rets.pivot_table(index="portfolio", columns=["signal", "weighting"], values="ret").mul(100)
    print(f"\nMean monthly return (%), {rets.date.min():%Y-%m} to {rets.date.max():%Y-%m}:")
    print(m.round(3).to_string())


if __name__ == "__main__":
    main()
