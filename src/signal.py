"""The RDV signal and the benchmark B, computed within each June cross-section only."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio import quantile_sort
from src.utils import winsorize, zscore


def rdv_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Add the three inputs. Accounting = fiscal year ending in t-1, ME = June t.
      rdm  = XRD / ME                                   (R&D intensity relative to price)
      eyr  = (OIBDP + XRD) / EV, EV = ME + DLC + DLTT - CHE   (earnings yield, R&D added back)
      dopr = (OIBDP+XRD)_FY / AT_{FY-1} - (OIBDP+XRD)_{FY-1} / AT_{FY-2}   (improvement)"""
    df = df.copy()
    df["rdm"] = df["xrd"] / df["me_june"]
    ev = df["me_june"] + df["dlc"] + df["dltt"] - df["che"]
    df["eyr"] = ((df["oibdp"] + df["xrd"]) / ev).where(ev > 0)
    df["dopr"] = df["d_opr"]
    return df


def score_and_sort(g: pd.DataFrame, n_port: int, winsor: float, nyse_bp: bool = True) -> pd.DataFrame:
    """One formation year: z-scores, RDV score (equal weights; missing eyr/dopr -> z = 0),
    RDV portfolios and benchmark B portfolios (sorted on rdm)."""
    g = g.copy()
    g["z_rdm"] = zscore(winsorize(g["rdm"], winsor))
    g["z_eyr"] = zscore(winsorize(g["eyr"], winsor)).fillna(0)
    g["z_dopr"] = zscore(winsorize(g["dopr"], winsor)).fillna(0)
    g["score_RDV"] = g["z_rdm"] + g["z_eyr"] + g["z_dopr"]
    nyse = g["exch"] == "N"
    g["port_RDV"] = quantile_sort(g["score_RDV"], nyse, n_port, nyse_bp)
    g["port_B"] = quantile_sort(g["rdm"], nyse, n_port, nyse_bp)
    return g


def build_signal(universe: pd.DataFrame, n_port: int, winsor: float, nyse_bp: bool = True) -> pd.DataFrame:
    """Apply score_and_sort to every formation year of an R&D-reporter universe."""
    u = rdv_inputs(universe)
    return pd.concat([score_and_sort(g, n_port, winsor, nyse_bp)
                      for _, g in u.groupby("formation_year")], ignore_index=True)
