"""Shared helpers: I/O, cross-sectional transforms, regressions, performance statistics."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


# ----------------------------------------------------------------------------
# I/O  (parquet if pyarrow is installed, pickle otherwise)
# ----------------------------------------------------------------------------
def _has_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def save_df(df: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    if _has_pyarrow():
        path = path.with_suffix(".parquet")
        df.to_parquet(path, index=False)
    else:
        path = path.with_suffix(".pkl")
        df.to_pickle(path)
    return path


def load_df(path: Path) -> pd.DataFrame:
    path = Path(path)
    for suf, reader in ((".parquet", pd.read_parquet), (".pkl", pd.read_pickle)):
        p = path.with_suffix(suf)
        if p.exists():
            return reader(p)
    raise FileNotFoundError(f"{path.with_suffix('')}.parquet/.pkl not found - run the previous step first.")


# ----------------------------------------------------------------------------
# Cross-sectional transforms (always applied WITHIN a formation date -> no look-ahead)
# ----------------------------------------------------------------------------
def winsorize(x: pd.Series, p: float) -> pd.Series:
    if p <= 0 or x.notna().sum() < 3:
        return x
    lo, hi = x.quantile([p, 1 - p])
    return x.clip(lo, hi)


def zscore(x: pd.Series) -> pd.Series:
    sd = x.std()
    if not np.isfinite(sd) or sd == 0:
        return x * np.nan
    return (x - x.mean()) / sd


# ----------------------------------------------------------------------------
# Time-series regressions
# ----------------------------------------------------------------------------
def ts_regression(y: pd.Series, X: pd.DataFrame, nw_lags: int):
    """OLS of y on a constant + X with Newey-West (HAC) standard errors."""
    data = pd.concat([y.rename("y"), X], axis=1).dropna()
    exog = pd.DataFrame({"const": 1.0}, index=data.index)
    if len(X.columns):
        exog = exog.join(data[X.columns])
    return sm.OLS(data["y"], exog).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lags})


def grs_test(R: pd.DataFrame, F: pd.DataFrame) -> dict:
    """Gibbons-Ross-Shanken (1989) test that all N alphas are jointly zero
    (slide 'Alpha tests', Session 2):  J1 = (T-N-K)/N * (1+mu' Sf^-1 mu)^-1 * a' Se^-1 a ~ F(N, T-N-K)."""
    data = pd.concat([R, F], axis=1).dropna()
    R_, F_ = data[R.columns].values, data[F.columns].values
    T, N = R_.shape
    K = F_.shape[1]
    Xc = np.column_stack([np.ones(T), F_])
    B = np.linalg.lstsq(Xc, R_, rcond=None)[0]
    alpha = B[0]
    resid = R_ - Xc @ B
    Sigma_e = resid.T @ resid / (T - K - 1)
    mu_f = F_.mean(axis=0)
    Sigma_f = np.cov(F_, rowvar=False, ddof=1).reshape(K, K)
    quad_f = float(mu_f @ np.linalg.solve(Sigma_f, mu_f))
    quad_a = float(alpha @ np.linalg.solve(Sigma_e, alpha))
    grs = (T - N - K) / N * quad_a / (1 + quad_f)
    pval = 1 - stats.f.cdf(grs, N, T - N - K)
    return {"GRS": grs, "p_value": pval, "T": T, "N": N, "K": K,
            "mean_abs_alpha": float(np.mean(np.abs(alpha)))}


# ----------------------------------------------------------------------------
# Performance statistics (monthly decimal returns in, annualised numbers out)
# ----------------------------------------------------------------------------
def max_drawdown(r: pd.Series) -> float:
    wealth = (1 + r.fillna(0)).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def perf_stats(r: pd.Series, rf: pd.Series | None = None, nw_lags: int = 6) -> dict:
    """Summary statistics of a monthly return series. If rf is given the Sharpe ratio is
    computed on excess returns (use rf=None for a zero-investment long-short portfolio)."""
    r = r.dropna()
    ex = r - rf.reindex(r.index) if rf is not None else r
    tstat = ts_regression(ex, pd.DataFrame(index=ex.index), nw_lags).tvalues["const"]
    return {
        "Mean (%/month)": 100 * r.mean(),
        "t-stat (NW)": tstat,
        "Ann. mean (%)": 100 * 12 * r.mean(),
        "Ann. vol (%)": 100 * np.sqrt(12) * r.std(),
        "Sharpe (ann.)": np.sqrt(12) * ex.mean() / ex.std(),
        "Skewness": stats.skew(r),
        "Excess kurtosis": stats.kurtosis(r),
        "Min (%)": 100 * r.min(),
        "Max (%)": 100 * r.max(),
        "Max drawdown (%)": 100 * max_drawdown(r),
        "Months": len(r),
    }


def stars(p: float) -> str:
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def append_sheets(xlsx_path: Path, sheets: dict) -> None:
    """Add / replace sheets in an existing results workbook (created by step 6)."""
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        return
    with pd.ExcelWriter(xlsx_path, mode="a", engine="openpyxl", if_sheet_exists="replace") as xl:
        for name, df in sheets.items():
            df.to_excel(xl, sheet_name=name[:31])
