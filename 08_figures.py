"""
Step 8 - Figures for the paper and the investment-committee presentation (PNG, 300 dpi).

fig1_cumulative_long_short.png    growth of $1: RDV Q5-Q1 (gross and net of trading costs)
fig2_cumulative_quintiles_VW.png  growth of $1 in each RDV quintile (VW) and the market
fig3_mean_excess_returns.png      average monthly excess return by quintile (VW | EW)
fig4_alpha_by_model.png           Q5-Q1 alpha and 95% CI under the 7 factor models (VW, EW)
fig5_rolling_alpha.png            60-month rolling FF5+MOM alpha of Q5-Q1 (VW)
fig6_universe.png                 number of firms per formation year
fig7_characteristics.png          the three signal inputs by quintile
fig8_sector_weights.png           Fama-French 12 sector weights of the long and short legs
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from src.evaluation import common_sample, load_factors  # noqa: E402
from src.utils import load_df, ts_regression  # noqa: E402

LS = f"Q{C.N_PORTFOLIOS}-Q1"
QUINT = [f"Q{i}" for i in range(1, C.N_PORTFOLIOS + 1)]
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#8a8984"
RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b", "#0a2c57",
        "#08244a", "#061c3b", "#04142c"][:C.N_PORTFOLIOS]
INK2 = "#52514e"
FF12_NAMES = {1: "NoDur", 2: "Durbl", 3: "Manuf", 4: "Enrgy", 5: "Chems", 6: "BusEq", 7: "Telcm",
              8: "Utils", 9: "Shops", 10: "Hlth", 11: "Money", 12: "Other"}

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": "#bdbcb7", "axes.labelcolor": INK2, "axes.titlesize": 11,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1", "grid.linewidth": 0.6,
    "xtick.color": INK2, "ytick.color": INK2, "legend.frameon": False, "lines.linewidth": 1.6,
    "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight"})


def save(fig, name):
    fig.savefig(C.OUT_FIGURES / name)
    plt.close(fig)
    print("saved", name)


def main():
    name = C.STRATEGY_NAME
    rets = load_df(C.DATA_PROC / "portfolio_returns")
    piv = lambda s, w: rets[(rets.signal == s) & (rets.weighting == w)].pivot(  # noqa: E731
        index="date", columns="portfolio", values="ret")
    vw, ew = piv(C.STRATEGY, "VW"), piv(C.STRATEGY, "EW")
    fac = load_factors()
    idx = common_sample(vw.dropna().index, fac)
    vw, ew = vw.loc[idx], ew.loc[idx]
    span = f"{idx.min():%Y-%m} to {idx.max():%Y-%m}"

    # 1. cumulative long-short
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.plot((1 + vw[LS]).cumprod(), color=BLUE, label="RDV, gross")
    net_path = C.DATA_PROC / "net_returns_RDV_VW.csv"
    if net_path.exists():
        net = pd.read_csv(net_path, parse_dates=["date"], index_col="date")["net_LS"].reindex(idx).fillna(0)
        ax.plot((1 + net).cumprod(), color=BLUE, linewidth=1.1, linestyle="--", label="RDV, net of costs")
    ax.set_yscale("log")
    ax.axhline(1, color=GREY, linewidth=0.8)
    ax.set_title(f"{name}\n{LS}, value-weighted: growth of $1, {span}")
    ax.set_ylabel("Value of $1 (log scale)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2)
    save(fig, "fig1_cumulative_long_short.png")

    # 2. cumulative quintiles VW
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for q, col in zip(QUINT, RAMP):
        ax.plot((1 + vw[q]).cumprod(), color=col, label=q)
    ax.plot((1 + fac.loc[idx, "MKT"] + fac.loc[idx, "RF"]).cumprod(), color=GREY, linewidth=1.2,
            linestyle=":", label="Market")
    ax.set_yscale("log")
    ax.set_title(f"RDV value-weighted quintiles: growth of $1, {span}")
    ax.set_ylabel("Value of $1 (log scale)")
    ax.legend(ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    save(fig, "fig2_cumulative_quintiles_VW.png")

    # 3. mean excess returns by quintile
    rf = fac.loc[idx, "RF"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.4), sharey=True)
    for ax, (lab, df) in zip(axes, (("Value-weighted (strategy)", vw), ("Equal-weighted (robustness)", ew))):
        m = 100 * df[QUINT].sub(rf, axis=0).mean()
        ax.bar(range(len(QUINT)), m.values, color=RAMP, width=0.7)
        for i, v in enumerate(m.values):
            ax.text(i, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=8, color=INK2)
        ax.set_xticks(range(len(QUINT)), QUINT)
        ax.set_title(lab)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Mean excess return (% per month)")
    fig.suptitle("RDV: average monthly excess return by quintile (Q1 = low score, Q5 = high)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig3_mean_excess_returns.png")

    # 4. alpha by model with 95% CI
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    models = list(C.MODELS)
    for k, (lab, df, col) in enumerate((("Value-weighted (strategy)", vw, BLUE),
                                        ("Equal-weighted (robustness)", ew, GREY))):
        a, lo, hi = [], [], []
        for m in models:
            res = ts_regression(df[LS], fac.loc[idx, C.MODELS[m]], C.NW_LAGS)
            ci = res.conf_int().loc["const"] * 100
            a.append(100 * res.params["const"]); lo.append(ci[0]); hi.append(ci[1])
        x = np.arange(len(models)) + (k - 0.5) * 0.25
        a, lo, hi = map(np.array, (a, lo, hi))
        ax.errorbar(x, a, yerr=[a - lo, hi - a], fmt="o", color=col, markersize=6, capsize=3,
                    linewidth=1.4, label=lab)
    ax.axhline(0, color=GREY, linewidth=0.9)
    ax.set_xticks(range(len(models)), models)
    ax.set_ylabel("Alpha (% per month)")
    ax.set_title(f"RDV {LS} alpha under seven factor models (95% CI, Newey-West)")
    ax.legend(loc="lower left")
    save(fig, "fig4_alpha_by_model.png")

    # 5. rolling alpha
    fcols = C.MODELS["FF5+MOM"]
    win = 60
    roll = []
    for end in range(win, len(idx) + 1):
        sub = idx[end - win:end]
        res = ts_regression(vw.loc[sub, LS], fac.loc[sub, fcols], C.NW_LAGS)
        roll.append((sub[-1], 100 * res.params["const"]))
    roll = pd.Series(dict(roll))
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(roll, color=BLUE)
    ax.axhline(0, color=GREY, linewidth=0.9)
    ax.set_title(f"RDV: rolling {win}-month FF5+MOM alpha of {LS} (value-weighted)")
    ax.set_ylabel("Alpha (% per month)")
    save(fig, "fig5_rolling_alpha.png")

    # 6. universe
    uni = pd.read_csv(C.OUT_TABLES / "data_universe_by_year.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    ax.plot(uni.index, uni["n_complete_data"], color=GREY, label="All non-financial firms (complete data)")
    ax.plot(uni.index, uni["n_rd_reporters"], color=BLUE, label="R&D reporters (RDV universe)")
    ax.plot(uni.index, uni["n_nyse_rd_reporters"], color=ORANGE, label="NYSE R&D reporters (breakpoints)")
    ax.set_title("Number of firms per formation year (end of June)")
    ax.set_ylabel("Firms")
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "fig6_universe.png")

    # 7. characteristics by quintile
    ch = pd.read_csv(C.OUT_TABLES / "quintile_characteristics_RDV.csv", index_col=0)
    items = [("rd_to_market", "R&D / market equity"),
             ("earnings_yield_rd_added", "(OIBDP + R&D) / EV"),
             ("change_profitability_rd_added", "Change in (OIBDP + R&D) / AT")]
    fig, axes = plt.subplots(1, 3, figsize=(9, 3))
    for ax, (k, lab) in zip(axes, items):
        v = ch.loc[k, QUINT].values
        ax.bar(range(len(QUINT)), v, color=RAMP, width=0.7)
        ax.axhline(0, color=GREY, linewidth=0.8)
        ax.set_xticks(range(len(QUINT)), QUINT)
        ax.set_title(lab, fontsize=10)
        ax.grid(axis="x", visible=False)
    fig.suptitle("RDV signal inputs by quintile (median, time-series average)", x=0.01, ha="left",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig7_characteristics.png")

    # 8. sector weights
    sw = pd.read_csv(C.OUT_TABLES / "sector_weights_RDV.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    x = np.arange(sw.shape[1])
    ax.bar(x - 0.2, sw.loc["long"], width=0.4, color=BLUE, label="Long leg (Q5)")
    ax.bar(x + 0.2, sw.loc["short"], width=0.4, color=GREY, label="Short leg (Q1)")
    ax.set_xticks(x, sw.columns, rotation=0, fontsize=8)
    ax.set_ylabel("Average weight (%)")
    ax.set_title("RDV: Fama-French 12 sector weights (value-weighted, at formation)")
    ax.grid(axis="x", visible=False)
    ax.legend()
    save(fig, "fig8_sector_weights.png")


if __name__ == "__main__":
    main()
