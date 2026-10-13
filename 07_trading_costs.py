"""
Step 7 - Turnover and trading costs of the RDV strategy (Session 3).

Turnover (slides 22-23): weights drift with returns, w*_{i,t} = w_{i,t-1}(1+r_{i,t-1});
after rebalancing to the target weights w_{i,t}:
    Turn_t = sum_i | w_{i,t} - w*_{i,t} / sum_j w*_{j,t} |       (max 200% per leg, 400% L/S)

Costs per leg and month:
    spread cost = sum_i |dw_i| x half-spread_i
    price impact = sum_i |dw_i| x lambda_i x sqrt( |dw_i| x AUM_t / ADV_i )   (slide 3 / 24)
Half-spreads and lambda depend on the size group (micro / small / large). ADV uses the
previous month's dollar volume, AUM is TC_AUM_USD in Dec-2025 dollars scaled back in time
with total CRSP market cap (a fund of constant real importance).

Also reported (assumption free): BREAK-EVEN one-way cost = gross alpha / turnover, i.e. the
cost per dollar traded that would wipe out the alpha.

Outputs: results/tables/trading_costs_RDV_{VW,EW}.csv,
         results/processed/net_returns_RDV_{VW,EW}.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
from src.evaluation import alphas_all_models, common_sample, load_factors
from src.utils import append_sheets, load_df

LS = f"Q{C.N_PORTFOLIOS}-Q1"
LEGS = [f"Q{C.N_PORTFOLIOS}", "Q1"]


def stock_characteristics(crsp: pd.DataFrame) -> pd.DataFrame:
    """Size group and ADV known at the START of each month (from the previous month)."""
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
    # missing ADV -> median ADV of the same size group that month
    med = c.groupby(["date", "size"])["adv_lag"].transform("median")
    c["adv_lag"] = c["adv_lag"].fillna(med)
    total_me = c.groupby("date")["me"].sum()
    return c[["permno", "date", "ret", "me_lag", "size", "adv_lag"]], total_me


def leg_turnover_costs(h: pd.DataFrame, weighting: str, aum: pd.Series) -> pd.DataFrame:
    """h: holdings of ONE portfolio (permno, date, ret, me_lag, size, adv_lag)."""
    h = h.copy()
    if weighting == "VW":
        h = h[h["me_lag"] > 0]
        h["w"] = h["me_lag"] / h.groupby("date")["me_lag"].transform("sum")
    else:
        h["w"] = 1.0 / h.groupby("date")["permno"].transform("size")
    # drifted weights carried to the next month
    d = h[["permno", "date", "w", "ret", "size", "adv_lag"]].copy()
    d["wd"] = d["w"] * (1 + d["ret"].fillna(0))
    d["wd"] = d["wd"] / d.groupby("date")["wd"].transform("sum")
    d["date"] = d["date"] + pd.offsets.MonthEnd(1)
    d = d.rename(columns={"size": "size_prev", "adv_lag": "adv_prev"})[["permno", "date", "wd", "size_prev", "adv_prev"]]
    x = h[["permno", "date", "w", "size", "adv_lag"]].merge(d, on=["permno", "date"], how="outer")
    x = x[x["date"].isin(h["date"].unique())]
    x["dw"] = (x["w"].fillna(0) - x["wd"].fillna(0)).abs()
    x["size"] = x["size"].fillna(x["size_prev"]).fillna("micro")
    x["adv"] = x["adv_lag"].fillna(x["adv_prev"])
    x["adv"] = x["adv"].fillna(x.groupby(["date", "size"])["adv"].transform("median"))
    x["half_spread"] = x["size"].map(C.TC_HALF_SPREAD)
    x["lam"] = x["size"].map(C.TC_LAMBDA)
    trade_usd = x["dw"] * x["date"].map(aum)
    x["impact"] = x["lam"] / 100 * np.sqrt(trade_usd / x["adv"])
    x["impact"] = x["impact"].fillna(x["lam"] / 100 * 0.1)   # fallback: 1% of ADV
    g = x.groupby("date")
    out = pd.DataFrame({"turnover": g["dw"].sum(),
                        "spread_cost": (x["dw"] * x["half_spread"]).groupby(x["date"]).sum(),
                        "impact_cost": (x["dw"] * x["impact"]).groupby(x["date"]).sum()})
    out.iloc[0] = np.nan          # first month = building the portfolio, not turnover
    return out


def main():
    crsp = load_df(C.DATA_PROC / "crsp_monthly")
    panel = load_df(C.DATA_PROC / "formation_panel")
    rets = load_df(C.DATA_PROC / "portfolio_returns")
    char, total_me = stock_characteristics(crsp)
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
    tc["spread_cost"] = legs[LEGS[0]]["spread_cost"] + legs[LEGS[1]]["spread_cost"]
    tc["impact_cost"] = legs[LEGS[0]]["impact_cost"] + legs[LEGS[1]]["impact_cost"]
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
    if fac is not None:
        ag = alphas_all_models(t["gross_LS"], fac, idx, excess=False)
        an = alphas_all_models(t["net_LS"], fac, idx, excess=False)
        turn = t["turnover_LS"].mean()
        for m in C.MODELS:
            a = ag.loc[m, "alpha_pct"]
            summary[f"Gross alpha {m} (%/month)"] = a
            summary[f"Net alpha {m} (%/month)"] = an.loc[m, "alpha_pct"]
            summary[f"t net alpha {m}"] = an.loc[m, "t_alpha"]
            # cost per dollar traded that wipes out the alpha (only meaningful if alpha > 0)
            summary[f"Break-even one-way cost {m} (bps)"] = 1e4 * a / 100 / turn if a > 0 else np.nan
    s = pd.Series(summary, name=f"{strat}_{w}")
    s.to_csv(C.OUT_TABLES / f"trading_costs_{strat}_{w}.csv")
    append_sheets(C.OUT_TABLES / "results.xlsx", {f"trading_costs_{w}": s.to_frame()})
    print(f"\n=== Trading costs, {strat} {w} ===")
    print(s.apply(lambda v: round(v, 3) if isinstance(v, float) else v).to_string())


if __name__ == "__main__":
    main()
