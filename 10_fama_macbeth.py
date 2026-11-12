"""
Step 10 - Fama-MacBeth (1973) cross-sectional regressions (Session 1, slides 33-35).

Each month t (July y to June y+1), regress individual returns (%) of the RDV universe on
characteristics known at the end of June y (momentum: known at the end of month t-1):
  (1) RDV score
  (2) RDV score + log(ME) + momentum(12-2)
  (3) the three z-scored inputs of the score + log(ME) + momentum
Regressors winsorised 1/99% each month; t-stats from Newey-West standard errors of the monthly
coefficient series.  Output: results/tables/fama_macbeth_RDV.csv
Also: 60-month rolling averages of the monthly coefficients of the three inputs in (3), which show
in which periods each input predicted returns: results/tables/fama_macbeth_rolling.csv and
results/figures/fig9_rolling_fama_macbeth.png
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

import config as C
from src.utils import append_sheets, load_df, ts_regression, winsorize


def momentum(crsp: pd.DataFrame) -> pd.DataFrame:
    """Cumulative return from t-12 to t-2 (skips the most recent month), known at end of t-1."""
    c = crsp[["permno", "date", "ret"]].sort_values(["permno", "date"]).copy()
    c["lr"] = np.log1p(c["ret"].clip(lower=-0.9999))
    c["mom"] = np.expm1(c.groupby("permno")["lr"].transform(lambda s: s.shift(2).rolling(11, min_periods=8).sum()))
    return c[["permno", "date", "mom"]]


def fm(d: pd.DataFrame, xs: list, keep: dict | None = None) -> dict:
    coefs = []
    for dt, g in d.dropna(subset=xs).groupby("date"):
        if len(g) < 50:
            continue
        X = pd.DataFrame({x: winsorize(g[x], C.WINSOR_PCT) for x in xs})
        res = sm.OLS(g["ret"] * 100, sm.add_constant(X)).fit()
        coefs.append(res.params.rename(dt).to_frame().T.assign(adjR2=res.rsquared_adj, n=len(g)))
    cf = pd.concat(coefs)
    if keep is not None:
        keep["coefs"] = cf
    col = {}
    for x in ["const"] + xs:
        r = ts_regression(cf[x], pd.DataFrame(index=cf.index), C.NW_LAGS)
        col[x] = f"{cf[x].mean():.3f} ({r.tvalues['const']:.2f})"
    col["avg adj R2"] = f"{cf['adjR2'].mean():.3f}"
    col["avg N stocks"] = f"{cf['n'].mean():.0f}"
    col["months"] = f"{len(cf)}"
    return col


def main():
    crsp = load_df(C.DATA_PROC / "crsp_monthly")[["permno", "date", "ret"]]
    crsp = crsp[crsp["date"] <= pd.Timestamp(C.LAST_RETURN_MONTH) + pd.offsets.MonthEnd(0)]
    panel = load_df(C.DATA_PROC / "formation_panel")
    d = crsp.dropna(subset=["ret"]).merge(momentum(crsp), on=["permno", "date"], how="left")
    d["formation_year"] = np.where(d["date"].dt.month > C.FORMATION_MONTH, d["date"].dt.year, d["date"].dt.year - 1)
    d = d.merge(panel[["permno", "formation_year", "me_june", "score_RDV", "z_rda", "z_eyr", "z_dopr"]],
                on=["permno", "formation_year"])
    d["log_me"] = np.log(d["me_june"])
    d = d[d["date"] >= pd.Timestamp(C.REG_START) + pd.offsets.MonthEnd(0)]
    specs = {
        "(1) RDV score": ["score_RDV"],
        "(2) RDV score + size + mom": ["score_RDV", "log_me", "mom"],
        "(3) components + size + mom": ["z_rda", "z_eyr", "z_dopr", "log_me", "mom"],
    }
    keep = {}
    out = pd.DataFrame({name: fm(d, xs, keep if name.startswith("(3)") else None) for name, xs in specs.items()})
    rolling_inputs(keep["coefs"])
    out.to_csv(C.OUT_TABLES / "fama_macbeth_RDV.csv")
    append_sheets(C.OUT_TABLES / "results.xlsx", {"fama_macbeth": out})
    print("Fama-MacBeth: average coefficients (returns in % per month), NW t-stats in parentheses")
    print(out.to_string())


def rolling_inputs(cf: pd.DataFrame, win: int = 60) -> None:
    """60-month rolling average of the monthly Fama-MacBeth coefficients of the three inputs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = {"z_rda": "R&D / total assets", "z_eyr": "(OIBDP + R&D) / EV", "z_dopr": "Change in profitability"}
    colors = {"z_rda": "#2a78d6", "z_eyr": "#eb6834", "z_dopr": "#8a8984"}
    roll = cf[list(labels)].rolling(win).mean().dropna()
    roll.to_csv(C.OUT_TABLES / "fama_macbeth_rolling.csv", float_format="%.4f")
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    for k, lab in labels.items():
        ax.plot(roll.index, roll[k], color=colors[k], linewidth=1.6, label=lab)
    ax.axhline(0, color="#8a8984", linewidth=0.9)
    ax.set_title(f"RDV inputs: rolling {win}-month average Fama-MacBeth coefficient", loc="left",
                 fontsize=11, fontweight="bold")
    ax.set_ylabel("Coefficient (% per month)")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, color="#e6e5e1", linewidth=0.6)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3, frameon=False, fontsize=9)
    fig.savefig(C.OUT_FIGURES / "fig9_rolling_fama_macbeth.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("saved fig9_rolling_fama_macbeth.png")


if __name__ == "__main__":
    main()
