"""
Step 6 - Performance evaluation of RDV: alphas under seven asset pricing models.

    CAPM | FF3 | FF3+MOM | FF5 | FF5+MOM | q-factor (HXZ 2015) | q5 (HMXZ 2021)

  quintiles :  R_p,t - RF_t = alpha + beta' F_t + e_t
  long-short:  R_Q5,t - R_Q1,t = alpha + beta' F_t + e_t      (zero-investment, no RF)
Newey-West (HAC) t-statistics; all models on the same sample (1975-07 onwards). The GRS test
checks whether the five quintile alphas are jointly zero. Bonferroni-adjusted p-values use the
number of strategies tested in the project (docs/test_register.md).

Pre-registered decision test (docs/preregistration_rdv.md): value added over the benchmark B
    RDV_t = a + b B_t + FF5+MOM factors + e_t     (and without factors)

Outputs: results/tables/*.csv and results/tables/results.xlsx
"""
import pandas as pd

import config as C
from src.evaluation import alphas_all_models, common_sample, load_factors
from src.utils import grs_test, load_df, perf_stats, stars, ts_regression

LS = f"Q{C.N_PORTFOLIOS}-Q1"
PORTS = [f"Q{i}" for i in range(1, C.N_PORTFOLIOS + 1)] + [LS]


def run(wide: pd.DataFrame, fac: pd.DataFrame, idx: pd.DatetimeIndex):
    alpha_rows, load_rows = [], []
    for model, fcols in C.MODELS.items():
        X = fac.loc[idx, fcols]
        for p in PORTS:
            y = wide.loc[idx, p] if p == LS else wide.loc[idx, p] - fac.loc[idx, "RF"]
            res = ts_regression(y, X, C.NW_LAGS)
            alpha_rows.append({"model": model, "portfolio": p, "alpha_pct": 100 * res.params["const"],
                               "t_alpha": res.tvalues["const"], "p_alpha": res.pvalues["const"],
                               "p_bonferroni": min(1.0, C.N_TESTS_REGISTER * res.pvalues["const"]),
                               "alpha_ann_pct": 1200 * res.params["const"],
                               "adj_R2": res.rsquared_adj, "N": int(res.nobs)})
            if p == LS:
                row = {"model": model, "alpha_pct": 100 * res.params["const"], "t_alpha": res.tvalues["const"]}
                for fc in fcols:
                    row[fc] = res.params[fc]
                    row[f"t_{fc}"] = res.tvalues[fc]
                row["adj_R2"] = res.rsquared_adj
                load_rows.append(row)
    excess = wide.loc[idx, PORTS[:-1]].sub(fac.loc[idx, "RF"], axis=0)
    grs = pd.DataFrame([{"model": m, **grs_test(excess, fac.loc[idx, f])} for m, f in C.MODELS.items()])
    return pd.DataFrame(alpha_rows), pd.DataFrame(load_rows), grs


def pretty(alphas: pd.DataFrame) -> pd.DataFrame:
    a = alphas.copy()
    a["cell"] = a.apply(lambda r: f"{r.alpha_pct:.3f}{stars(r.p_alpha)} ({r.t_alpha:.2f})", axis=1)
    return a.pivot(index="model", columns="portfolio", values="cell").loc[list(C.MODELS), PORTS]


def main():
    fac = load_factors()
    rets = load_df(C.DATA_PROC / "portfolio_returns")
    wide_all = rets.pivot_table(index="date", columns=["signal", "weighting", "portfolio"], values="ret")
    idx = common_sample(wide_all.dropna().index, fac)
    print(f"Regression sample: {idx.min():%Y-%m} to {idx.max():%Y-%m} ({len(idx)} months)")

    def wide(sig, w):
        return rets[(rets.signal == sig) & (rets.weighting == w)].pivot(index="date", columns="portfolio",
                                                                        values="ret")[PORTS]

    sheets = {}
    for w in ("VW", "EW"):
        wd = wide(C.STRATEGY, w)
        alphas, loadings, grs = run(wd, fac, idx)
        perf = pd.DataFrame({p: perf_stats(wd.loc[idx, p], None if p == LS else fac.loc[idx, "RF"], C.NW_LAGS)
                             for p in PORTS}).T
        alphas.to_csv(C.OUT_TABLES / f"alphas_RDV_{w}.csv", index=False, float_format="%.4f")
        loadings.to_csv(C.OUT_TABLES / f"loadings_LS_RDV_{w}.csv", index=False, float_format="%.4f")
        grs.to_csv(C.OUT_TABLES / f"grs_RDV_{w}.csv", index=False, float_format="%.4f")
        perf.to_csv(C.OUT_TABLES / f"performance_RDV_{w}.csv", float_format="%.4f")
        sheets[f"alphas_{w}"] = pretty(alphas)
        sheets[f"loadings_LS_{w}"] = loadings.round(3)
        sheets[f"GRS_{w}"] = grs.round(4)
        sheets[f"performance_{w}"] = perf.round(3)
        print(f"\n=== RDV {w}: alphas in % per month (NW t-stat) ===")
        print(pretty(alphas).to_string())
        print(grs[["model", "GRS", "p_value"]].round(3).to_string(index=False))

    # ---- benchmark B and the pre-registered value-added test (VW) ----------------------
    y = wide(C.STRATEGY, "VW").loc[idx, LS]
    yb = wide(C.BENCHMARK, "VW").loc[idx, LS]
    comp = pd.DataFrame({
        "RDV_alpha": alphas_all_models(y, fac, idx, excess=False)["alpha_pct"],
        "RDV_t": alphas_all_models(y, fac, idx, excess=False)["t_alpha"],
        "B_alpha": alphas_all_models(yb, fac, idx, excess=False)["alpha_pct"],
        "B_t": alphas_all_models(yb, fac, idx, excess=False)["t_alpha"]})
    comp.to_csv(C.OUT_TABLES / "rdv_vs_benchmark_B_alphas.csv", float_format="%.4f")
    va = []
    r0 = ts_regression(y, yb.rename("B").to_frame(), C.NW_LAGS)
    X = pd.concat([yb.rename("B"), fac.loc[idx, C.MODELS[C.VALUE_ADDED_MODEL]]], axis=1)
    r1 = ts_regression(y, X, C.NW_LAGS)
    for name, r in (("RDV = a + b B", r0), (f"RDV = a + b B + {C.VALUE_ADDED_MODEL}", r1)):
        va.append({"regression": name, "a_pct": 100 * r.params["const"], "t_a": r.tvalues["const"],
                   "b_B": r.params["B"], "t_b": r.tvalues["B"], "adj_R2": r.rsquared_adj})
    va = pd.DataFrame(va)
    decision = ("RDV replaces B (pre-registered rule met: a > 0, t > 2)"
                if (r1.params["const"] > 0 and r1.tvalues["const"] > 2) else "rule NOT met: keep B")
    va["decision"] = decision
    va.to_csv(C.OUT_TABLES / "rdv_value_added_over_B.csv", index=False, float_format="%.4f")
    sheets["RDV_vs_B_alphas"] = comp.round(3)
    sheets["value_added_over_B"] = va.round(3)
    print("\n=== RDV vs benchmark B (VW long-short) ===\n", comp.round(3).to_string())
    print(va.round(3).to_string(index=False))

    with pd.ExcelWriter(C.OUT_TABLES / "results.xlsx") as xl:
        for name, df in sheets.items():
            df.to_excel(xl, sheet_name=name[:31])
    print("\nsaved tables to", C.OUT_TABLES)


if __name__ == "__main__":
    main()
