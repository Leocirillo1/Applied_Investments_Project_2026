"""
Step 9 - Robustness of the RDV long-short (Q5-Q1) alpha. The strategy rule is never changed over
time; each row re-runs the full sort under ONE alternative design choice:

  baseline                    config as in steps 4-5
  1975-1999 / 2000-2025       sub-periods
  no microcaps                drop stocks below the NYSE 20th percentile of June ME
  large caps only             keep June ME >= NYSE median
  price >= $5                 drop low-priced stocks at formation
  deciles                     10 portfolios, Q10-Q1
  all-stock breakpoints       breakpoints from all stocks instead of NYSE only
  no winsorisation            raw inputs in the z-scores

Outputs: results/tables/robustness_RDV_{VW,EW}.csv
"""
import pandas as pd

import config as C
from src.evaluation import alphas_all_models, common_sample, load_factors
from src.portfolio import holding_returns, long_short_wide
from src.signal import build_signal
from src.utils import append_sheets, load_df, ts_regression

LS_N = lambda n: f"Q{n}-Q1"  # noqa: E731
BASE_COLS = ["permno", "formation_year", "exch", "me_june", "prc", "xrd", "oibdp", "dlc", "dltt",
             "che", "d_opr"]


def run_spec(crsp, base, n_port=C.N_PORTFOLIOS, nyse_bp=C.NYSE_BREAKPOINTS, winsor=C.WINSOR_PCT):
    panel = build_signal(base, n_port, winsor, nyse_bp)
    hr = holding_returns(crsp, panel, "port_RDV", C.FORMATION_MONTH)
    return {w: long_short_wide(hr, w.lower(), n_port)[LS_N(n_port)] for w in ("VW", "EW")}


def main():
    fac = load_factors()
    crsp = load_df(C.DATA_PROC / "crsp_monthly")[["permno", "date", "ret", "me_lag"]]
    crsp = crsp[crsp["date"] <= pd.Timestamp(C.LAST_RETURN_MONTH) + pd.offsets.MonthEnd(0)]
    panel = load_df(C.DATA_PROC / "formation_panel")
    base = panel[BASE_COLS].copy()

    nyse_bp = base[base.exch == "N"].groupby("formation_year")["me_june"].quantile([0.2, 0.5]).unstack()
    specs = {
        "baseline": run_spec(crsp, base),
        "no microcaps (ME >= NYSE p20)": run_spec(crsp, base[base["me_june"] >= base["formation_year"].map(nyse_bp[0.2])]),
        "large caps only (ME >= NYSE median)": run_spec(crsp, base[base["me_june"] >= base["formation_year"].map(nyse_bp[0.5])]),
        "price >= $5": run_spec(crsp, base[base["prc"] >= 5]),
        "deciles (Q10-Q1)": run_spec(crsp, base, n_port=10),
        "all-stock breakpoints": run_spec(crsp, base, nyse_bp=False),
        "no winsorisation": run_spec(crsp, base, winsor=0.0),
    }
    full = common_sample(specs["baseline"]["VW"].dropna().index, fac)
    periods = {"": full, "1975-1999": full[full <= "1999-12-31"], "2000-2025": full[full >= "2000-01-31"]}

    for w in ("VW", "EW"):
        rows = []
        for name, series in specs.items():
            for pname, idx in periods.items():
                if pname and name != "baseline":
                    continue
                y = series[w]
                ii = idx.intersection(y.dropna().index)
                a = alphas_all_models(y, fac, ii, excess=False)
                mean_t = ts_regression(y.loc[ii], pd.DataFrame(index=ii), C.NW_LAGS).tvalues["const"]
                row = {"specification": f"{name} {pname}".strip(), "start": f"{ii.min():%Y-%m}",
                       "end": f"{ii.max():%Y-%m}", "mean_pct": 100 * y.loc[ii].mean(), "t_mean": mean_t}
                for m in C.MODELS:
                    row[f"a_{m}"] = a.loc[m, "alpha_pct"]
                    row[f"t_{m}"] = a.loc[m, "t_alpha"]
                rows.append(row)
        out = pd.DataFrame(rows)
        out.to_csv(C.OUT_TABLES / f"robustness_RDV_{w}.csv", index=False, float_format="%.4f")
        append_sheets(C.OUT_TABLES / "results.xlsx", {f"robustness_{w}": out.round(4).set_index("specification")})
        print(f"\n=== Robustness, RDV long-short, {w} (alpha % per month; t-stats in the csv) ===")
        show = ["specification", "mean_pct", "t_mean", "a_CAPM", "a_FF5+MOM", "t_FF5+MOM", "a_q5", "t_q5"]
        print(out[show].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
