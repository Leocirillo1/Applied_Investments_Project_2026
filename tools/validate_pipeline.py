"""
Sanity check of the CRSP cleaning (run after steps 1-2):
the value-weighted return of the cleaned CRSP universe should track the Fama-French market return.

Run from the project root:  python tools/validate_pipeline.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402
from src.evaluation import load_factors  # noqa: E402
from src.utils import load_df  # noqa: E402


def main():
    crsp = load_df(C.DATA_PROC / "crsp_monthly")
    c = crsp[crsp["ret"].notna() & (crsp["me_lag"] > 0)]
    vw = (c["ret"] * c["me_lag"]).groupby(c["date"]).sum() / c["me_lag"].groupby(c["date"]).sum()
    fac = load_factors()
    d = pd.concat([vw.rename("ours"), (fac["MKT"] + fac["RF"]).rename("ff")], axis=1, sort=True)
    d = d.loc["1967":"2025"].dropna()
    print(f"Market check 1967-2025: corr = {d.corr().iloc[0, 1]:.4f}, "
          f"mean ours = {100 * d['ours'].mean():.3f}%, FF = {100 * d['ff'].mean():.3f}%")


if __name__ == "__main__":
    main()
