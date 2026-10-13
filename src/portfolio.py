"""Portfolio construction: NYSE-breakpoint quintiles and monthly holding-period returns."""
from __future__ import annotations

import numpy as np
import pandas as pd


def quantile_sort(score: pd.Series, nyse: pd.Series, n_port: int, nyse_breakpoints: bool = True) -> np.ndarray:
    """Portfolio 1..n_port. Breakpoints = quantiles of the NYSE scores (all scores if fewer than
    2*n_port NYSE firms or nyse_breakpoints=False). A score <= breakpoint k goes to portfolio k
    (Session 1 convention)."""
    src = score[nyse] if (nyse_breakpoints and nyse.sum() >= 2 * n_port) else score
    bps = src.quantile(np.linspace(0, 1, n_port + 1)[1:-1]).values
    return np.searchsorted(bps, score.values, side="left") + 1


def holding_returns(crsp: pd.DataFrame, panel: pd.DataFrame, port_col: str,
                    formation_month: int = 6) -> pd.DataFrame:
    """Monthly EW and VW returns of each portfolio, held from formation_month+1 for 12 months.
    VW weights = previous month-end market cap. Returns: date, port, ew, vw, n."""
    c = crsp[crsp["ret"].notna()][["permno", "date", "ret", "me_lag"]].copy()
    c["formation_year"] = np.where(c["date"].dt.month > formation_month,
                                   c["date"].dt.year, c["date"].dt.year - 1)
    d = c.merge(panel.loc[panel[port_col].notna(), ["permno", "formation_year", port_col]],
                on=["permno", "formation_year"])
    d["rw"] = d["ret"] * d["me_lag"]
    g = d.groupby(["date", port_col])
    out = pd.DataFrame({"ew": g["ret"].mean(),
                        "vw": g["rw"].sum(min_count=1) / g["me_lag"].sum(min_count=1),
                        "n": g["ret"].size()}).reset_index().rename(columns={port_col: "port"})
    return out


def long_short_wide(hr: pd.DataFrame, weighting: str, n_port: int) -> pd.DataFrame:
    """Wide frame Q1..Qn + 'Qn-Q1' for one weighting ('ew' or 'vw')."""
    w = hr.pivot(index="date", columns="port", values=weighting)
    w.columns = [f"Q{int(c)}" for c in w.columns]
    w[f"Q{n_port}-Q1"] = w[f"Q{n_port}"] - w["Q1"]
    return w
