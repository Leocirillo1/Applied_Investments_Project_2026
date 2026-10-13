"""Factor data + alpha regressions shared by steps 6, 7 and 9."""
from __future__ import annotations

import pandas as pd

import config as C
from src.utils import ts_regression


def load_factors() -> pd.DataFrame:
    path = C.DATA_FACTORS / "factors_monthly.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run 01_download_factors.py first.")
    f = pd.read_csv(path, parse_dates=["date"], index_col="date")
    f.index = f.index + pd.offsets.MonthEnd(0)
    return f


def common_sample(index: pd.DatetimeIndex, fac: pd.DataFrame) -> pd.DatetimeIndex:
    """Months where ALL factors of ALL models (and RF) are available, within REG_START/REG_END."""
    needed = sorted({x for m in C.MODELS.values() for x in m} | {"RF"})
    idx = pd.DatetimeIndex(index).intersection(fac[needed].dropna().index)
    idx = idx[idx >= pd.Timestamp(C.REG_START) + pd.offsets.MonthEnd(0)]
    if C.REG_END:
        idx = idx[idx <= pd.Timestamp(C.REG_END) + pd.offsets.MonthEnd(0)]
    return idx.sort_values()


def alphas_all_models(y: pd.Series, fac: pd.DataFrame, idx: pd.DatetimeIndex,
                      excess: bool) -> pd.DataFrame:
    """Alpha (% per month), NW t-stat and p-value of y for every model in config.MODELS.
    excess=True subtracts RF (long-only portfolio); False for zero-investment portfolios."""
    yy = y.reindex(idx)
    if excess:
        yy = yy - fac.loc[idx, "RF"]
    rows = []
    for model, fcols in C.MODELS.items():
        res = ts_regression(yy, fac.loc[idx, fcols], C.NW_LAGS)
        rows.append({"model": model, "alpha_pct": 100 * res.params["const"],
                     "t_alpha": res.tvalues["const"], "p_alpha": res.pvalues["const"],
                     "adj_R2": res.rsquared_adj, "N": int(res.nobs)})
    return pd.DataFrame(rows).set_index("model")
