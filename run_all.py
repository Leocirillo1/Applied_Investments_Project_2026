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


def check_raw_data() -> bool:
    """The WRDS files are not on GitHub: each user must copy them into Data/ once."""
    import config as C
    crsp_parts = list((C.DATA_RAW / "_transfer").glob(C.CRSP_FILE.stem.replace(" ", "") + "_part*.csv.gz"))
    missing = [p for p in (C.CRSP_FILE, C.COMPUSTAT_FILE)
               if not p.exists() and not (p == C.CRSP_FILE and crsp_parts)]
    if missing:
        print("\n" + "!" * 78)
        print("Raw WRDS data not found (they are not on GitHub because WRDS data are licensed).")
        print("Copy these files into the Data folder of this project, with exactly these names:")
        for p in missing:
            print(f"   {p}")
        print("Then run run_all.py again.")
        print("!" * 78)
    return not missing


def run_step(path: Path):
    """Run one step; a script that calls sys.exit() must not stop the whole pipeline."""
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1, help="first step to run (1-10)")
    ap.add_argument("--skip-download", action="store_true", help="do not re-download the factors")
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    import config as C
    factors_file = C.DATA_FACTORS / "factors_monthly.csv"
    # step 1 runs when asked, and always when the factor file is missing (e.g. a fresh clone)
    download = (args.start <= 1 and not args.skip_download) or not factors_file.exists()
    if args.start <= 3 and not check_raw_data():
        sys.exit(1)
    t_all = time.time()
    for i, step in enumerate(STEPS, start=1):
        if (i == 1 and not download) or (i > 1 and i < args.start):
            continue
        print(f"\n{'=' * 78}\nSTEP {i}: {step}\n{'=' * 78}")
        t0 = time.time()
        run_step(ROOT / step)
        print(f"[{step} done in {time.time() - t0:.0f}s]")
    print(f"\nPipeline finished in {(time.time() - t_all) / 60:.1f} min. "
          f"Results: results/tables (results.xlsx) and results/figures")


if __name__ == "__main__":
    main()
