"""
Step 1 - Download the factor returns used to compute alphas.

* Fama-French 3 factors, 5 factors (2x3) and Momentum  (Kenneth French data library)
* q-factors and q5-factors                               (global-q.org, Hou-Xue-Zhang)

Output: Data/factors/factors_monthly.csv   (all factors in DECIMAL monthly returns)
        + the raw downloaded files in Data/factors/raw/

Run:  python 01_download_factors.py
"""
import io
import re
import zipfile
import urllib.request
from datetime import date

import pandas as pd

import config as C

RAW = C.DATA_FACTORS / "raw"
RAW.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (academic research; HEC Lausanne)"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_french_csv(text: str) -> pd.DataFrame:
    """Keep only the MONTHLY block of a Ken French CSV (rows whose first field is YYYYMM)."""
    lines = text.splitlines()
    header, rows = None, []
    for line in lines:
        fields = [x.strip() for x in line.split(",")]
        if header is None:
            # header line: starts with an empty field followed by factor names
            if len(fields) > 1 and fields[0].lower() in ("", "date") and all(fields[1:]):
                header = ["yyyymm"] + fields[1:]
            continue
        if re.fullmatch(r"\d{6}", fields[0]):
            rows.append(fields[: len(header)])
        elif rows:            # first non-monthly line after the monthly block -> stop
            break
    df = pd.DataFrame(rows, columns=header)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df.loc[df[c] <= -99.99, c] = float("nan")       # French's missing-value codes
    df["date"] = pd.to_datetime(df["yyyymm"], format="%Y%m") + pd.offsets.MonthEnd(0)
    return df.drop(columns="yyyymm").set_index("date")


def download_french(key: str) -> pd.DataFrame:
    fname = C.FF_FILES[key]
    print(f"  downloading {fname} ...")
    content = fetch(C.FF_BASE + fname)
    (RAW / fname).write_bytes(content)
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        inner = z.namelist()[0]
        text = z.read(inner).decode("latin-1")
    return parse_french_csv(text)


def download_q5() -> pd.DataFrame:
    """Find the latest monthly q5 file. First scrape the factors page, then fall back
    to the usual upload path for recent vintages."""
    candidates = []
    try:
        html = fetch(C.GLOBALQ_PAGE).decode("utf-8", errors="replace")
        for href in re.findall(r'href="([^"]*q5_factors_monthly[^"]*\.csv)"', html):
            candidates.append(urllib.request.urljoin(C.GLOBALQ_PAGE, href))
    except Exception as e:  # noqa: BLE001
        print("  (could not read global-q page:", e, ")")
    this_year = date.today().year
    candidates += [f"{C.GLOBALQ_UPLOADS}q5_factors_monthly_{y}.csv"
                   for y in range(this_year, 2019, -1)]
    for url in candidates:
        try:
            content = fetch(url)
            df = pd.read_csv(io.BytesIO(content))
            if {"year", "month", "R_MKT"}.issubset(df.columns):
                print(f"  downloaded {url}")
                (RAW / url.rsplit("/", 1)[-1]).write_bytes(content)
                return df
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError(
        "Could not download the q5 factors automatically. Download the MONTHLY q5 "
        "factors CSV manually from https://global-q.org/factors.html and save it as "
        "Data/factors/raw/q5_factors_monthly_manual.csv, then re-run this script.")


def main():
    print("Fama-French factors:")
    ff3 = download_french("ff3")          # Mkt-RF, SMB, HML, RF
    ff5 = download_french("ff5")          # Mkt-RF, SMB, HML, RMW, CMA, RF
    mom = download_french("mom")          # Mom
    mom.columns = [c.strip() for c in mom.columns]

    print("q-factors:")
    manual = RAW / "q5_factors_monthly_manual.csv"
    q = pd.read_csv(manual) if manual.exists() else download_q5()
    q["date"] = pd.to_datetime(dict(year=q["year"], month=q["month"], day=1)) + pd.offsets.MonthEnd(0)
    q = q.set_index("date")

    fac = pd.DataFrame(index=ff3.index)
    fac["MKT"] = ff3["Mkt-RF"]
    fac["SMB"] = ff3["SMB"]
    fac["HML"] = ff3["HML"]
    fac["RF"] = ff3["RF"]
    fac = fac.join(ff5[["SMB", "HML", "RMW", "CMA"]].rename(columns={"SMB": "SMB5", "HML": "HML5"}), how="left")
    fac = fac.join(mom[["Mom"]].rename(columns={"Mom": "MOM"}), how="left")
    fac = fac.join(q[["R_F", "R_MKT", "R_ME", "R_IA", "R_ROE", "R_EG"]].rename(columns={
        "R_F": "Q_RF", "R_MKT": "Q_MKT", "R_ME": "Q_ME", "R_IA": "Q_IA",
        "R_ROE": "Q_ROE", "R_EG": "Q_EG"}), how="left")
    fac = fac / 100.0                     # percent -> decimal
    fac.index.name = "date"
    out = C.DATA_FACTORS / "factors_monthly.csv"
    fac.to_csv(out, float_format="%.6f")
    print(f"\nSaved {out}")
    print(fac.dropna().agg(["count", "mean", "std"]).T.round(4))
    print("First month with all factors:", fac.dropna().index.min().date(),
          "| last:", fac.dropna().index.max().date())


if __name__ == "__main__":
    main()
