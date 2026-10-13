"""
Run the whole RDV pipeline in order.

    python run_all.py                    # everything (re-downloads the factors)
    python run_all.py --skip-download    # use the factor files already in Data/factors
    python run_all.py --from 4           # restart from step 4 (e.g. after changing config.py)
"""
import argparse
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    "01_download_factors.py",
    "02_clean_crsp.py",
    "03_clean_compustat.py",
    "04_link_and_signal.py",
    "05_portfolio_returns.py",
    "06_alpha_regressions.py",
    "07_trading_costs.py",
    "08_figures.py",
    "09_robustness.py",
    "10_fama_macbeth.py",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1, help="first step to run (1-10)")
    ap.add_argument("--skip-download", action="store_true", help="do not re-download the factors")
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    t_all = time.time()
    for i, step in enumerate(STEPS, start=1):
        if i < args.start or (args.skip_download and i == 1):
            continue
        print(f"\n{'=' * 78}\nSTEP {i}: {step}\n{'=' * 78}")
        t0 = time.time()
        runpy.run_path(str(ROOT / step), run_name="__main__")
        print(f"[{step} done in {time.time() - t0:.0f}s]")
    print(f"\nPipeline finished in {(time.time() - t_all) / 60:.1f} min. "
          f"Results: results/tables (results.xlsx) and results/figures")


if __name__ == "__main__":
    main()
