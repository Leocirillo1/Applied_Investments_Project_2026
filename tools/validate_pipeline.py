"""
Sanity checks of the data pipeline (run after steps 1-4):
  1. VW return of the cleaned CRSP universe vs the Fama-French market return.
  2. Replication of the Session 1 example: asset-growth deciles (Cooper, Gulen & Schill 2008),
     NYSE breakpoints, June formation, all linked stocks (incl. financials), 1963-07 to 2024-12.

Run from the project root (after steps 1-4):  python tools/validate_pipeline.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402
from src.evaluation import load_factors  # noqa: E402
from src.portfolio import holding_returns  # noqa: E402
from src.utils import load_df  # noqa: E402


def main():
    crsp = load_df(C.DATA_PROC / "crsp_monthly")
    c = crsp[crsp["ret"].notna() & (crsp["me_lag"] > 0)]
    vw = (c["ret"] * c["me_lag"]).groupby(c["date"]).sum() / c["me_lag"].groupby(c["date"]).sum()
    fac = load_factors()
    d = pd.concat([vw.rename("ours"), (fac["MKT"] + fac["RF"]).rename("ff")], axis=1, sort=True)
    d = d.loc["1967":"2025"].dropna()
    print(f"1) Market check 1967-2025: corr = {d.corr().iloc[0, 1]:.4f}, "
          f"mean ours = {100 * d['ours'].mean():.3f}%, FF = {100 * d['ff'].mean():.3f}%")

    # 2) asset growth deciles, CUSIP/CCM link exactly as in step 4 but without the financial filter
    import importlib.util
    spec = importlib.util.spec_from_file_location("step4", C.ROOT / "04_link_and_signal.py")
    step4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(step4)
    cs = load_df(C.DATA_PROC / "compustat_signals")
    june = crsp[crsp["date"].dt.month == 6].copy()
    june["formation_year"] = june["date"].dt.year
    june = june.rename(columns={"me": "me_june", "date": "formation_date"})
    m = step4.link_ccm(cs) if C.CCM_LINK_FILE.exists() else step4.link_cusip(cs, june)
    m = m.merge(june[["permno", "formation_year", "me_june", "exch"]], on=["permno", "formation_year"])
    m = m.sort_values(["gvkey", "formation_year", "link_priority", "me_june"], ascending=[1, 1, 1, 0])
    m = m.drop_duplicates(["gvkey", "formation_year"]).drop_duplicates(["permno", "formation_year"])
    m = m.dropna(subset=["asset_growth"])
    m = m[m["me_june"] > 0]

    def deciles(g):
        bps = g.loc[g["exch"] == "N", "asset_growth"].quantile(np.linspace(0, 1, 11)[1:-1]).values
        g = g.copy()
        g["d"] = np.searchsorted(bps, g["asset_growth"].values, side="left") + 1
        return g
    m = pd.concat([deciles(g) for _, g in m.groupby("formation_year")])
    hr = holding_returns(crsp[(crsp["date"] >= "1963-07-31") & (crsp["date"] <= "2024-12-31")], m, "d")
    ew = hr.pivot(index="date", columns="port", values="ew")
    vw = hr.pivot(index="date", columns="port", values="vw")
    print("2) Asset-growth deciles, mean monthly return (%):")
    print(pd.DataFrame({"EW": 100 * ew.mean(), "VW": 100 * vw.mean()}).T.round(2).to_string())
    print(f"   10-1: EW {100 * (ew[10] - ew[1]).mean():.2f}%, VW {100 * (vw[10] - vw[1]).mean():.2f}% "
          "(Session 1 slides: EW -0.85%, VW -0.26%)")


if __name__ == "__main__":
    main()
