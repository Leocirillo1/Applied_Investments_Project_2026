"""
Step 7 - Turnover and trading costs of the RDV strategy (Session 3).

Turnover (slides 22-23): weights drift with returns, w*_{i,t} = w_{i,t-1}(1+r_{i,t-1});
after rebalancing to the target weights w_{i,t}:
    Turn_t = sum_i | w_{i,t} - w*_{i,t} / sum_j w*_{j,t} |       (max 200% per leg, 400% L/S)

Costs per leg and month:
    spread cost = sum_i |dw_i| x half-spread_i
    price impact = sum_i |dw_i| x lambda_i x sqrt( |dw_i| x AUM_t / ADV_i )   (slide 3 / 24)
Half-spreads are MEASURED for each stock-month from the CRSP daily files Data/crsp_daily_*.csv.gz
(src/spreads.py: closing quoted spread, Abdi-Ranaldo high-low estimator when there are not enough
quotes). The daily files must cover every month of the sample (no extrapolation). A stock-month
without a measured spread gets the median measured half-spread of the same NYSE size decile, same
month (the course approach for missing quotes).
Price impact: lambda depends on the size group, ADV is the previous month's dollar volume, AUM is
TC_AUM_USD in Dec-2025 dollars scaled back in time with total CRSP market cap (a fund of constant
real importance).

Outputs: results/tables/trading_costs_RDV_{VW,EW}.csv, half_spreads_by_size_decile.csv,
         permnos_missing_daily.txt, results/processed/net_returns_RDV_{VW,EW}.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
from src.evaluation import alphas_all_models, common_sample, load_factors
from src.spreads import monthly_spreads
from src.utils import append_sheets, load_df, save_df

LS = f"Q{C.N_PORTFOLIOS}-Q1"
LEGS = [f"Q{C.N_PORTFOLIOS}", "Q1"]


MIN_STOCKS_COVERED = 100      # every month of the sample needs >= 100 stocks with a measured spread


def stock_characteristics(crsp: pd.DataFrame, spreads: pd.DataFrame):
    """Size group, size decile, ADV (known at the start of each month) and half-spreads."""
    c = crsp[["permno", "date", "ret", "me_lag", "vol", "prc", "exch", "me"]].copy()
    c = c.sort_values(["permno", "date"])
    prev_ok = c.groupby("permno")["date"].shift(1) == c["date"] - pd.offsets.MonthEnd(1)
    dollar_vol = (c["vol"] * c["prc"]).where(lambda x: x > 0)
    c["adv_lag"] = dollar_vol.groupby(c["permno"]).shift(1).where(prev_ok) / C.TC_TRADING_DAYS
    nyse = c[c["exch"] == "N"].groupby("date")["me_lag"].quantile([0.2, 0.5]).unstack()
    nyse.columns = ["p20", "p50"]
    c = c.merge(nyse, left_on="date", right_index=True, how="left")
    c["size"] = np.select([c["me_lag"] < c["p20"], c["me_lag"] < c["p50"]],
                          ["micro", "small"], "large")
    c.loc[c["me_lag"].isna(), "size"] = "micro"
    # NYSE size deciles (1 = smallest), used to fill missing spreads
    dec = c[c["exch"] == "N"].groupby("date")["me_lag"].quantile(np.linspace(0.1, 0.9, 9)).unstack()
    bp = c[["date"]].join(dec, on="date").drop(columns="date").to_numpy()
    c["decile"] = 1 + (c["me_lag"].to_numpy()[:, None] > bp).sum(axis=1)
    c.loc[c["me_lag"].isna(), "decile"] = 1
    c = c.merge(spreads[["permno", "date", "half_spread"]], on=["permno", "date"], how="left")
    c["hs_source"] = np.where(c["half_spread"].notna(), "measured", "size-decile fill")
    same_decile = c.groupby(["date", "decile"])["half_spread"].transform("median")
    same_month = c.groupby("date")["half_spread"].transform("median")
    c["hs"] = c["half_spread"].fillna(same_decile).fillna(same_month)
    meas = c[c["half_spread"].notna()]
    (100 * meas.groupby("decile")["half_spread"].median()).rename("median half-spread (%)").to_csv(
        C.OUT_TABLES / "half_spreads_by_size_decile.csv", float_format="%.4f")
    # missing ADV -> median ADV of the same size group that month
    med = c.groupby(["date", "size"])["adv_lag"].transform("median")
    c["adv_lag"] = c["adv_lag"].fillna(med)
    total_me = c.groupby("date")["me"].sum()
    return c[["permno", "date", "ret", "me_lag", "size", "adv_lag", "hs", "hs_source"]], total_me


def leg_turnover_costs(h: pd.DataFrame, weighting: str, aum: pd.Series) -> pd.DataFrame:
    """h: holdings of ONE portfolio (permno, date, ret, me_lag, size, adv_lag)."""
    h = h.copy()
    if weighting == "VW":
        h = h[h["me_lag"] > 0]
        h["w"] = h["me_lag"] / h.groupby("date")["me_lag"].transform("sum")
    else:
        h["w"] = 1.0 / h.groupby("date")["permno"].transform("size")
    # drifted weights carried to the next month
    d = h[["permno", "date", "w", "ret", "size", "adv_lag", "hs", "hs_source"]].copy()
    d["wd"] = d["w"] * (1 + d["ret"].fillna(0))
    d["wd"] = d["wd"] / d.groupby("date")["wd"].transform("sum")
    d["date"] = d["date"] + pd.offsets.MonthEnd(1)
    d = d.rename(columns={"size": "size_prev", "adv_lag": "adv_prev", "hs": "hs_prev", "hs_source": "src_prev"})
    d = d[["permno", "date", "wd", "size_prev", "adv_prev", "hs_prev", "src_prev"]]
    x = h[["permno", "date", "w", "size", "adv_lag", "hs", "hs_source"]].merge(
        d, on=["permno", "date"], how="outer")
    x = x[x["date"].isin(h["date"].unique())]
    x["dw"] = (x["w"].fillna(0) - x["wd"].fillna(0)).abs()
    x["size"] = x["size"].fillna(x["size_prev"]).fillna("micro")
    x["adv"] = x["adv_lag"].fillna(x["adv_prev"])
    x["adv"] = x["adv"].fillna(x.groupby(["date", "size"])["adv"].transform("median"))
    # a stock sold out of the portfolio is no longer in h: use its spread of the previous month
    x["hs"] = x["hs"].fillna(x["hs_prev"])
    x["hs_source"] = x["hs_source"].fillna(x["src_prev"])
    assert x["hs"].notna().all(), "every traded stock must have a half-spread"
    x["lam"] = x["size"].map(C.TC_LAMBDA)
    trade_usd = x["dw"] * x["date"].map(aum)
    x["impact"] = x["lam"] / 100 * np.sqrt(trade_usd / x["adv"])
    x["impact"] = x["impact"].fillna(x["lam"] / 100 * 0.1)   # fallback: 1% of ADV
    g = x.groupby("date")
    out = pd.DataFrame({"turnover": g["dw"].sum(),
                        "spread_cost": (x["dw"] * x["hs"]).groupby(x["date"]).sum(),
                        "impact_cost": (x["dw"] * x["impact"]).groupby(x["date"]).sum(),
                        "traded_measured": (x["dw"] * (x["hs_source"] == "measured")).groupby(x["date"]).sum()})
    out.iloc[0] = np.nan          # first month = building the portfolio, not turnover
    return out


def main():
    crsp = load_df(C.DATA_PROC / "crsp_monthly")
    panel = load_df(C.DATA_PROC / "formation_panel")
    rets = load_df(C.DATA_PROC / "portfolio_returns")
    daily_files = sorted(C.DATA_RAW.glob(C.CRSP_DAILY_PATTERN))
    if not daily_files:
        raise FileNotFoundError(f"No CRSP daily files ({C.CRSP_DAILY_PATTERN}) in {C.DATA_RAW}: they are "
                                "needed to measure the bid-ask spreads (see README).")
    print(f"Measuring bid-ask spreads from {len(daily_files)} CRSP daily file(s)")
    spreads = monthly_spreads(daily_files)
    save_df(spreads, C.DATA_PROC / "spreads_monthly")
    pd.Series(spreads.attrs["report"], name="value").to_csv(C.OUT_TABLES / "data_daily_report.csv")
    cov = spreads[spreads["half_spread"].notna()]
    print(f"  measured stock-months: {len(cov):,}, months {cov['date'].min():%Y-%m} to {cov['date'].max():%Y-%m}")
    print(cov.groupby("source")["half_spread"].describe()[["count", "50%", "mean"]].round(4).to_string())
    # stocks of the universe absent from the daily files (their spreads are filled by size decile);
    # this PERMNO list can be uploaded to WRDS to download them in one more daily file
    absent = sorted(set(panel["permno"].astype(int)) - set(spreads["permno"].astype(int)))
    (C.OUT_TABLES / "permnos_missing_daily.txt").write_text("\n".join(map(str, absent)) + "\n")
    print(f"  universe stocks absent from the daily files: {len(absent)} (list in permnos_missing_daily.txt)")
    # no extrapolation: every holding month must be covered by the daily data
    months = rets.loc[rets["signal"] == C.STRATEGY, "date"].drop_duplicates()
    n = cov.groupby("date").size().reindex(months, fill_value=0)
    if (n < MIN_STOCKS_COVERED).any():
        bad = n[n < MIN_STOCKS_COVERED].index
        raise ValueError(f"The CRSP daily files do not cover {len(bad)} month(s) of the sample "
                         f"(first {bad.min():%Y-%m}, last {bad.max():%Y-%m}): download these dates too.")
    char, total_me = stock_characteristics(crsp, spreads)
    # fund size known at the START of each month (previous month-end market size), in USD
    aum = (C.TC_AUM_USD * total_me / total_me.iloc[-1]).shift(1).bfill()
    char["formation_year"] = np.where(char["date"].dt.month > C.FORMATION_MONTH,
                                      char["date"].dt.year, char["date"].dt.year - 1)
    try:
        fac = load_factors()
    except FileNotFoundError as e:
        print("WARNING:", e, "-> alphas skipped")
        fac = None

    for strat in [C.STRATEGY]:
        port_col = f"port_{strat}"
        hold = char.merge(panel.loc[panel[port_col].notna(), ["permno", "formation_year", port_col]],
                          on=["permno", "formation_year"])
        hold = hold[hold["ret"].notna()]
        for w in ("VW", "EW"):
            run_one(strat, w, hold, port_col, rets, aum, fac)


def run_one(strat, w, hold, port_col, rets, aum, fac):
    legs = {}
    for leg in LEGS:
        q = int(leg[1:])
        legs[leg] = leg_turnover_costs(hold[hold[port_col] == q], w, aum)
    gross = (rets[(rets.signal == strat) & (rets.weighting == w)]
             .pivot(index="date", columns="portfolio", values="ret"))
    tc = pd.DataFrame(index=gross.index)
    tc["turnover_LS"] = legs[LEGS[0]]["turnover"] + legs[LEGS[1]]["turnover"]
    for k in ["spread_cost", "impact_cost", "traded_measured"]:
        tc[k] = legs[LEGS[0]][k] + legs[LEGS[1]][k]
    tc["total_cost"] = tc["spread_cost"] + tc["impact_cost"]
    tc["gross_LS"] = gross[LS]
    tc["net_LS"] = tc["gross_LS"] - tc["total_cost"].fillna(0)
    tc.to_csv(C.DATA_PROC / f"net_returns_{strat}_{w}.csv", float_format="%.6f")

    # statistics on the regression sample when factors are available
    # same sample as the alpha regressions (the first month has no turnover: portfolio set-up)
    base_idx = tc["gross_LS"].dropna().index
    idx = common_sample(base_idx, fac) if fac is not None else base_idx
    t = tc.loc[idx]
    july = t.index.month == C.FORMATION_MONTH + 1
    summary = {
        "Sample": f"{idx.min():%Y-%m} to {idx.max():%Y-%m}",
        "Avg monthly turnover L/S (%)": 100 * t["turnover_LS"].mean(),
        "  in rebalancing month (July) (%)": 100 * t.loc[july, "turnover_LS"].mean(),
        "  in other months (%)": 100 * t.loc[~july, "turnover_LS"].mean(),
        "Annual turnover L/S (%)": 1200 * t["turnover_LS"].mean(),
        "Spread cost (%/month)": 100 * t["spread_cost"].mean(),
        "Price impact (%/month)": 100 * t["impact_cost"].mean(),
        "Total cost (%/month)": 100 * t["total_cost"].mean(),
        "Gross mean L/S (%/month)": 100 * t["gross_LS"].mean(),
        "Net mean L/S (%/month)": 100 * t["net_LS"].mean(),
    }
    traded = t["turnover_LS"].sum()
    summary["Average half-spread paid (bps)"] = 1e4 * t["spread_cost"].sum() / traded
    summary["Traded value with a measured spread (%)"] = 100 * t["traded_measured"].sum() / traded
    for a, b in (("1975", "1999"), ("2000", "2025")):
        summary[f"Total cost {a}-{b} (%/month)"] = 100 * t.loc[a:b, "total_cost"].mean()
        summary[f"Average half-spread paid {a}-{b} (bps)"] = (1e4 * t.loc[a:b, "spread_cost"].sum()
                                                           / t.loc[a:b, "turnover_LS"].sum())
    if fac is not None:
        ag = alphas_all_models(t["gross_LS"], fac, idx, excess=False)
        an = alphas_all_models(t["net_LS"], fac, idx, excess=False)
        for m in C.MODELS:
            a = ag.loc[m, "alpha_pct"]
            summary[f"Gross alpha {m} (%/month)"] = a
            summary[f"Net alpha {m} (%/month)"] = an.loc[m, "alpha_pct"]
            summary[f"t net alpha {m}"] = an.loc[m, "t_alpha"]
    s = pd.Series(summary, name=f"{strat}_{w}")
    s.to_csv(C.OUT_TABLES / f"trading_costs_{strat}_{w}.csv")
    append_sheets(C.OUT_TABLES / "results.xlsx", {f"trading_costs_{w}": s.to_frame()})
    print(f"\n=== Trading costs, {strat} {w} ===")
    print(s.apply(lambda v: round(v, 3) if isinstance(v, float) else v).to_string())


if __name__ == "__main__":
    main()
