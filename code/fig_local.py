import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# reference palette (light mode)
SURF, INK, SEC, MUT, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 11,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": SEC,
    "xtick.color": MUT, "ytick.color": MUT, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.dpi": 200,
})
FIGDIR = "/Users/simon/Desktop/NEW_SCOTT/report/figures"

# ---- Fig 1: ETP percolation ----
eps = np.array([0.001, 0.003, 0.01, 0.03, 0.1, 0.2, 0.3, 0.5])
surv = np.array([0.9979, 0.9887, 0.9572, 0.8843, 0.5815, 0.2753, 0.1026, 0.0197])
sd = np.array([0.0018, 0.0059, 0.0174, 0.0217, 0.0635, 0.0206, 0.0232, 0.0035])
fig, ax = plt.subplots(figsize=(7, 4.6))
xs = np.geomspace(0.0008, 0.55, 200)
ax.plot(xs, (1 - xs) ** 14.2, ls="--", lw=1.6, color=MUT, zorder=1)
ax.annotate("single 14-step chain\n$(1-\\varepsilon)^{14.2}$", xy=(0.055, 0.33),
            color=MUT, fontsize=9.5, ha="left")
ax.errorbar(eps, surv, yerr=sd, color=S1, lw=2, marker="o", ms=5,
            capsize=2.5, zorder=3)
ax.annotate("ETP derivation skeleton\n(10,657 direct proofs)", xy=(0.0045, 0.60),
            color=S1, fontsize=10, ha="left", fontweight="bold")
# 2022 proof-network reference marker
ax.plot([0.01], [0.991], marker="*", ms=14, color=S2, zorder=4)
ax.annotate("classical proof networks:\nmean $f_2$ = 0.99 at $\\varepsilon$ = 0.01\n(Viteri & DeDeo 2022)",
            xy=(0.035, 0.93), color=S2, fontsize=9.5, ha="left", va="top")
ax.set_xscale("log")
ax.set_xlabel("per-certificate failure rate  $\\varepsilon$")
ax.set_ylabel("fraction of derived implications surviving")
ax.set_title("Machine-scale mathematics abandons redundancy:\npercolation of the Equational Theories Project derivation skeleton",
             fontsize=11.5, color=INK, loc="left")
ax.set_ylim(0, 1.04)
fig.tight_layout()
fig.savefig(f"{FIGDIR}/fig1_etp_percolation.png")
plt.close(fig)

# ---- Fig 2: Study 3 reuse (dot plot, 3 metrics x 3 layers) ----
metrics = [
    ("Citations per 1,000\ncandidate citers", [1.31, 0.38, 1.30]),
    ("Share of lemmas never\ncited in-repo (%)", [24.1, 67.3, 19.6]),
    ("Verbatim-duplicated\n`have` lines (%)", [20.1, 29.4, 12.9]),
]
layers = ["Human team\n(sphere packing)", "Gauss AI\n(sphere packing)", "Gauss AI\n(strong PNT)"]
colors = [S1, S2, S3]
fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.4))
for ax, (label, vals) in zip(axes, metrics):
    ypos = [2, 1, 0]
    for y, v, c in zip(ypos, vals, colors):
        ax.plot([0, v], [y, y], color=c, lw=2, solid_capstyle="round")
        ax.plot([v], [y], "o", ms=7, color=c)
        ax.annotate(f"{v:g}", xy=(v, y), xytext=(5, 0), textcoords="offset points",
                    va="center", fontsize=10, color=INK)
    ax.set_yticks(ypos)
    ax.set_yticklabels(layers if ax is axes[0] else ["", "", ""], fontsize=9.5, color=SEC)
    ax.set_xlim(0, max(vals) * 1.3)
    ax.set_xlabel(label, fontsize=9.5)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
fig.suptitle("AI formalization reuses less and repeats more (Sphere-Packing-Lean & strongpnt, source-level)",
             fontsize=11.5, color=INK, x=0.02, ha="left")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(f"{FIGDIR}/fig2_gauss_reuse.png")
plt.close(fig)
print("wrote fig1, fig2")

# ---- Fig 3: three regimes of mathematical certainty ----
fig, ax = plt.subplots(figsize=(7.4, 4.8))
S4 = "#4a3aa7"  # violet slot 7 -> use slot 1,2,3 + muted for 4th
# (a) individual classic proofs (Lean 2026, n=33): median + IQR
eps_c = np.array([0.4,0.3,0.2,0.15,0.1,0.07,0.05,0.03,0.02,0.01,0.005])
med   = np.array([0.5810,0.7619,0.8800,0.9397,0.9651,0.9833,1.0,1.0,1.0,1.0,1.0])
q25   = np.array([0.5302,0.7016,0.8444,0.9100,0.9467,0.9556,0.9833,0.9746,0.9733,0.9746,0.9800])
q75   = np.array([0.6233,0.7873,0.9267,0.9667,0.9933,1.0,1.0,1.0,1.0,1.0,1.0])
ax.fill_between(eps_c, q25, q75, color=S1, alpha=0.16, lw=0)
ax.plot(eps_c, med, color=S1, lw=2.2, marker="o", ms=4.5, zorder=3)
# (b) Mathlib as a whole
eps_m = np.array([0.3,0.2,0.1,0.05,0.02,0.01])
ax.plot(eps_m, [0.9967,0.9985,0.9992,0.9993,0.9994,0.9995], color=S3, lw=2.2,
        marker="s", ms=4.5, zorder=3)
ax.plot(eps_m, [0.9105,0.9347,0.9479,0.9526,0.9554,0.9562], color=S3, lw=1.8,
        ls=":", marker="s", ms=4, zorder=3)
# (c) ETP skeleton
ax.plot(eps, surv, color=S2, lw=2.2, marker="^", ms=5, zorder=3)
ax.annotate("individual theorem proofs\n(33 Lean proofs, median & IQR)", xy=(0.0011, 0.93),
            color=S1, fontsize=9.5, fontweight="bold", ha="left", va="top")
ax.annotate("all of Mathlib\n(308k declarations, 8.4M edges)", xy=(0.0011, 0.78),
            color=S3, fontsize=9.5, fontweight="bold", ha="left", va="top")
ax.annotate("\u2026same library, human-visible\ncitations only", xy=(0.0011, 0.63),
            color=S3, fontsize=9, ha="left", va="top")
ax.annotate("Equational Theories Project\nderivation skeleton", xy=(0.33, 0.22),
            color=S2, fontsize=9.5, fontweight="bold", ha="right", va="top")
ax.set_xscale("log"); ax.set_xlim(0.0009, 0.55); ax.set_ylim(0, 1.05)
ax.set_xlabel("one-step inference error rate  $\\varepsilon$")
ax.set_ylabel("degree of belief in the conclusion (proofs, Mathlib)\nor fraction still derivable (ETP)", fontsize=9.5)
ax.set_title("Three regimes of mathematical certainty", fontsize=12, color=INK, loc="left")
ax.text(0, -0.20, "Blue/green: belief-propagation model of Viteri & DeDeo (2022). Orange: fraction of the 8.16M derived implications retaining a derivation path.",
        transform=ax.transAxes, fontsize=8, color=MUT)
fig.tight_layout()
fig.savefig(f"{FIGDIR}/fig3_three_regimes.png")
plt.close(fig)
print("wrote fig3")
