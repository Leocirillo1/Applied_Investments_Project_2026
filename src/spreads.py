"""Bid-ask spreads measured from the CRSP daily stock file (Session 3 approach).

For each stock and month:
  * quoted half-spread = mean of (ask - bid) / (ask + bid) over the days with a valid closing bid
    and ask;
  * if the stock has fewer than MIN_DAYS such days, the high-low half-spread of Abdi and Ranaldo
    (2017) on the same month. This is mainly the case of NYSE/AMEX stocks before 1993: CRSP then
    reports their closing quotes only on days WITHOUT trades, so most of them have no quotes.
        s_t = sqrt(max(4 (c_t - eta_t)(c_t - eta_{t+1}), 0)),  eta = (log high + log low) / 2,
        c = log close, two consecutive trading days of the same month; half-spread = mean(s_t) / 2.
A month needs at least MIN_DAYS valid days. Stock-months with no measured spread are filled in
07_trading_costs.py with the median measured half-spread of the same NYSE size decile, same month.

The daily files are read in chunks (they can have tens of millions of rows); they must be sorted
by PERMNO and date, as delivered by WRDS.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MIN_DAYS = 10
MAX_HALF_SPREAD = 0.25
CHUNK_ROWS = 2_000_000
COLS = ["permno", "dlycaldt", "dlyprc", "dlyprcflg", "dlyhigh", "dlylow", "dlybid", "dlyask"]


def _stock_blocks(path: Path):
    """Yield blocks of rows that contain the complete history of each stock in the block."""
    carry = None
    for ch in pd.read_csv(path, usecols=lambda c: c.lower() in COLS, chunksize=CHUNK_ROWS,
                          low_memory=False):
        ch.columns = [c.lower() for c in ch.columns]
        ch["permno"] = pd.to_numeric(ch["permno"], errors="coerce")
        ch = ch.dropna(subset=["permno"])
        if carry is not None:
            ch = pd.concat([carry, ch], ignore_index=True)
        p = ch["permno"].to_numpy()
        if len(p) == 0:
            continue
        if (np.diff(p) < 0).any():
            raise ValueError(f"{path.name} must be sorted by PERMNO and date (as downloaded from WRDS).")
        last = p == p[-1]
        carry = ch[last]
        if (~last).any():
            yield ch[~last]
    if carry is not None and len(carry):
        yield carry


def _prepare(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    for c in ["dlyprc", "dlyhigh", "dlylow", "dlybid", "dlyask"]:
        d[c] = pd.to_numeric(d[c], errors="coerce").astype("float32")
    d["permno"] = d["permno"].astype("int64")
    d["dlycaldt"] = pd.to_datetime(d["dlycaldt"], errors="coerce")
    d = d.dropna(subset=["dlycaldt"]).sort_values(["permno", "dlycaldt"], kind="stable")
    d["date"] = d["dlycaldt"] + pd.offsets.MonthEnd(0)
    d["trade"] = d["dlyprcflg"].astype(str) == "TR"
    return d.drop(columns="dlyprcflg")


def _monthly_from_daily(d: pd.DataFrame) -> pd.DataFrame:
    # quoted half-spread
    ok = (d["dlybid"] > 0) & (d["dlyask"] >= d["dlybid"])
    hs_q = ((d["dlyask"] - d["dlybid"]) / (d["dlyask"] + d["dlybid"])).where(ok)
    hs_q = hs_q.where(hs_q <= MAX_HALF_SPREAD)
    # Abdi-Ranaldo two-day estimates on trading days
    hl = (d["trade"] & (d["dlyhigh"] > 0) & (d["dlylow"] > 0) & (d["dlyhigh"] >= d["dlylow"])
          & (d["dlyprc"].abs() > 0))
    with np.errstate(divide="ignore", invalid="ignore"):
        eta = ((np.log(d["dlyhigh"]) + np.log(d["dlylow"])) / 2).where(hl)
        c = np.log(d["dlyprc"].abs()).where(hl)
    eta_next = eta.groupby(d["permno"]).shift(-1)
    same_month = d["date"].groupby(d["permno"]).shift(-1) == d["date"]
    s2 = (4 * (c - eta) * (c - eta_next)).where(same_month)
    s_two_day = np.sqrt(s2.clip(lower=0))
    x = pd.DataFrame({"permno": d["permno"], "date": d["date"], "hs_q": hs_q, "s_hl": s_two_day})
    m = x.groupby(["permno", "date"]).agg(hs_quoted=("hs_q", "mean"), n_quoted=("hs_q", "count"),
                                          s_hl=("s_hl", "mean"), n_hl=("s_hl", "count")).reset_index()
    m["hs_highlow"] = m.pop("s_hl") / 2
    return m


def monthly_spreads(files: list[Path]) -> pd.DataFrame:
    """Monthly measured half-spread per stock: columns permno, date, half_spread, source."""
    parts, rows, stocks, first, last = [], 0, set(), None, None
    for f in files:
        print("  reading", f.name)
        for block in _stock_blocks(f):
            d = _prepare(block)
            rows += len(d)
            stocks.update(d["permno"].unique())
            lo, hi = d["dlycaldt"].min(), d["dlycaldt"].max()
            first = lo if first is None else min(first, lo)
            last = hi if last is None else max(last, hi)
            parts.append(_monthly_from_daily(d))
    m = pd.concat(parts, ignore_index=True).drop_duplicates(["permno", "date"], keep="last")
    quoted = m["hs_quoted"].where(m["n_quoted"] >= MIN_DAYS)
    highlow = m["hs_highlow"].where(m["n_hl"] >= MIN_DAYS)
    m["half_spread"] = quoted.fillna(highlow).clip(upper=MAX_HALF_SPREAD)
    m["source"] = np.select([quoted.notna(), highlow.notna()], ["quoted", "high-low"], "none")
    m = m[["permno", "date", "half_spread", "source"]].sort_values(["permno", "date"], ignore_index=True)
    m.attrs["report"] = {"stock_days": rows, "stocks": len(stocks), "first_day": str(first.date()),
                         "last_day": str(last.date())}
    return m
