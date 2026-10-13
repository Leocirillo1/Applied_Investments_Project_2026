"""
Step 4 - Link Compustat to CRSP, build the June universe, compute the RDV signal and assign
stocks to NYSE-breakpoint quintiles (plus the benchmark B = R&D-to-market).

Formation at the end of June of year t uses ONLY information available at that date:
  * accounting data: fiscal year ending in calendar year t-1 (>= 6 months old, asserted)
  * market data:     CRSP June t (market cap, exchange, SIC code)
  * winsorisation, z-scores and NYSE breakpoints use only the June-t cross-section.

Universe: US common stocks NYSE/AMEX/NASDAQ linked to Compustat, non-financial, complete core
accounting data (config.SCREEN_ITEMS), R&D reporters (XRD > 0; missing R&D is never set to 0).

RDV score = z(XRD/ME) + z((OIBDP+XRD)/EV) + z(delta[(OIBDP+XRD)/AT_{t-1}])   (equal weights)
Portfolios: Q1 (lowest) ... Q5 (highest), strategy = Q5 - Q1.

Output: results/processed/formation_panel.parquet  (one row per stock x formation year)
"""
import numpy as np
import pandas as pd

import config as C
from src.signal import build_signal
from src.utils import load_df, save_df


# ----------------------------------------------------------------------------
# Linking
# ----------------------------------------------------------------------------
def link_ccm(cs: pd.DataFrame) -> pd.DataFrame:
    """Official CRSP/Compustat Merged link table (preferred)."""
    lk = pd.read_csv(C.CCM_LINK_FILE, dtype=str)
    lk.columns = [c.lower() for c in lk.columns]
    lk = lk.rename(columns={"lpermno": "permno"})
    lk = lk[lk["linktype"].isin(["LU", "LC"]) & lk["linkprim"].isin(["P", "C"])]
    lk["permno"] = pd.to_numeric(lk["permno"], errors="coerce")
    lk["linkdt"] = pd.to_datetime(lk["linkdt"], errors="coerce")
    lk["linkenddt"] = pd.to_datetime(lk["linkenddt"].replace({"E": None}), errors="coerce")
    lk["linkenddt"] = lk["linkenddt"].fillna(pd.Timestamp("2099-12-31"))
    lk["gvkey"] = lk["gvkey"].str.zfill(6)
    m = cs.merge(lk[["gvkey", "permno", "linkdt", "linkenddt", "linkprim"]], on="gvkey")
    # the accounting report must belong to the linked security (link valid at datadate)
    m = m[(m["datadate"] >= m["linkdt"]) & (m["datadate"] <= m["linkenddt"])]
    m["link_priority"] = np.where(m["linkprim"] == "P", 0, 1)
    return m.drop(columns=["linkdt", "linkenddt", "linkprim"])


def link_cusip(cs: pd.DataFrame, june: pd.DataFrame) -> pd.DataFrame:
    """Fallback: point-in-time CUSIP link on the June formation cross-section.
    Priority 0: Compustat CUSIP (8) = CRSP historical CUSIP at June t or header CUSIP.
    Priority 1: same 6-digit issuer code (other share class / re-issued security)."""
    j = june[["permno", "formation_year", "cusip8", "hdrcusip8"]]
    cands = []
    for col in ["cusip8", "hdrcusip8"]:
        a = cs.merge(j, left_on=["formation_year", "cusip8"],
                     right_on=["formation_year", col], suffixes=("", "_crsp"))
        a["link_priority"] = 0
        cands.append(a)
        k = j.assign(c6=j[col].str[:6])
        b = cs.assign(c6=cs["cusip8"].str[:6]).merge(
            k, on=["formation_year", "c6"], suffixes=("", "_crsp"))
        b["link_priority"] = 1
        cands.append(b)
    m = pd.concat(cands, ignore_index=True)
    m = m.drop(columns=[c for c in m.columns if c.endswith("_crsp") or c == "c6"])
    return m


def ff12(sic: pd.Series) -> pd.Series:
    """Fama-French 12 industries from SIC codes (12 = Other)."""
    ranges = {
        1: [(100, 999), (2000, 2399), (2700, 2749), (2770, 2799), (3100, 3199), (3940, 3989)],
        2: [(2500, 2519), (2590, 2599), (3630, 3659), (3710, 3711), (3714, 3714), (3716, 3716),
            (3750, 3751), (3792, 3792), (3900, 3939), (3990, 3999)],
        3: [(2520, 2589), (2600, 2699), (2750, 2769), (3000, 3099), (3200, 3569), (3580, 3629),
            (3700, 3709), (3712, 3713), (3715, 3715), (3717, 3749), (3752, 3791), (3793, 3799),
            (3830, 3839), (3860, 3899)],
        4: [(1200, 1399), (2900, 2999)], 5: [(2800, 2829), (2840, 2899)],
        6: [(3570, 3579), (3660, 3692), (3694, 3699), (3810, 3829), (7370, 7379)],
        7: [(4800, 4899)], 8: [(4900, 4949)], 9: [(5000, 5999), (7200, 7299), (7600, 7699)],
        10: [(2830, 2839), (3693, 3693), (3840, 3859), (8000, 8099)], 11: [(6000, 6999)]}
    out = pd.Series(12, index=sic.index)
    for k, rr in ranges.items():
        for lo, hi in rr:
            out[(sic >= lo) & (sic <= hi)] = k
    return out


FF12_NAMES = {1: "NoDur", 2: "Durbl", 3: "Manuf", 4: "Enrgy", 5: "Chems", 6: "BusEq", 7: "Telcm",
              8: "Utils", 9: "Shops", 10: "Hlth", 11: "Money", 12: "Other"}


def main():
    crsp = load_df(C.DATA_PROC / "crsp_monthly")
    cs = load_df(C.DATA_PROC / "compustat_signals")
    cs = cs[cs["formation_year"] >= C.FIRST_FORMATION_YEAR]

    june = crsp[crsp["date"].dt.month == C.FORMATION_MONTH].copy()
    june["formation_year"] = june["date"].dt.year
    june = june.rename(columns={"me": "me_june", "date": "formation_date"})

    if C.CCM_LINK_FILE.exists():
        link_method = "CCM link table"
        m = link_ccm(cs)
    else:
        link_method = "CUSIP (fallback - download ccm_link.csv for the official link)"
        m = link_cusip(cs, june)
    print("Link method:", link_method)

    # attach the June t CRSP cross-section (security must trade at formation)
    m = m.merge(june[["permno", "formation_year", "formation_date", "permco", "me_june",
                      "prc", "exch", "siccd"]], on=["permno", "formation_year"], how="inner")
    m = m[m["me_june"] > 0]
    # one security per firm-year (best link, then largest share class), one firm per security-year
    m = m.sort_values(["gvkey", "formation_year", "link_priority", "me_june"],
                      ascending=[True, True, True, False])
    m = m.drop_duplicates(["gvkey", "formation_year"], keep="first")
    m = m.sort_values(["permno", "formation_year", "link_priority", "datadate"],
                      ascending=[True, True, True, False])
    m = m.drop_duplicates(["permno", "formation_year"], keep="first")

    # look-ahead guard: the report is at least 6 months old at formation
    gap = ((m["formation_date"].dt.year - m["datadate"].dt.year) * 12
           + m["formation_date"].dt.month - m["datadate"].dt.month)
    assert gap.min() >= C.MIN_REPORTING_LAG_MONTHS, "look-ahead bias detected"

    cov = (m.groupby("formation_year")["me_june"].sum()
           / june.groupby("formation_year")["me_june"].sum()).rename("linked_me_share")

    # ---- universe ---------------------------------------------------------------
    n_linked = m.groupby("formation_year").size().rename("n_linked")
    sic = m["siccd"].where(m["siccd"] > 0)
    is_fin = sic.between(6000, 6999) | (sic.isna() & m["gsector"].isin([40, 60]))
    if C.EXCLUDE_FINANCIALS:
        m = m[~is_fin]
    n_nonfin = m.groupby("formation_year").size().rename("n_nonfinancial")
    m = m.dropna(subset=C.SCREEN_ITEMS)
    n_screen = m.groupby("formation_year").size().rename("n_complete_data")
    m = m[(m["xrd"] > 0) & (m["me_june"] > 0)]
    m["ff12"] = ff12(m["siccd"].fillna(0))

    # ---- signal (cross-sectional, within each formation year) ------------------
    panel = build_signal(m, C.N_PORTFOLIOS, C.WINSOR_PCT, C.NYSE_BREAKPOINTS)

    keep = ["permno", "permco", "gvkey", "conm", "formation_year", "formation_date", "datadate",
            "me_june", "prc", "exch", "siccd", "ff12", "at", "at_lag", "xrd", "oibdp", "dlc", "dltt",
            "che", "lev", "rd_at", "asset_growth", "opr", "d_opr", "rdm", "eyr", "dopr",
            "z_rdm", "z_eyr", "z_dopr", "score_RDV", "port_RDV", "port_B"]
    panel = panel[keep]
    path = save_df(panel, C.DATA_PROC / "formation_panel")

    cov = cov[cov.index.isin(n_linked.index)]
    g = panel.groupby("formation_year")
    summary = pd.concat([n_linked, cov, n_nonfin, n_screen,
                         g.size().rename("n_rd_reporters"),
                         g["exch"].apply(lambda x: (x == "N").sum()).rename("n_nyse_rd_reporters")], axis=1)
    summary.to_csv(C.OUT_TABLES / "data_universe_by_year.csv")
    with open(C.OUT_TABLES / "data_link_method.txt", "w") as f:
        f.write(link_method + "\n")
    print(summary.iloc[::5].round(3).to_string())
    n = panel.groupby(["formation_year", "port_RDV"]).size().unstack()
    assert n[1].min() > 0 and n[C.N_PORTFOLIOS].min() > 0, "empty long or short portfolio in some year"
    print(f"\nFormation years {panel.formation_year.min()}-{panel.formation_year.max()}, "
          f"{len(panel):,} stock-years, stocks per RDV quintile (avg/yr): {n.mean().round(0).to_dict()}")
    print("saved", path)


if __name__ == "__main__":
    main()
