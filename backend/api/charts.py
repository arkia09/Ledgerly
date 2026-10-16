"""Matplotlib charts rendered to PNG bytes.

Object API only (Figure, never pyplot): pyplot keeps global state and is not safe across
web requests. Note: matplotlib has no complex-text shaping, so some Devanagari conjuncts
and vowel signs may look slightly off even with a proper font.
"""
import io
from functools import lru_cache

import matplotlib

matplotlib.use("Agg")

from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .ledger import BUCKETS  # noqa: E402

DEVANAGARI_FONTS = ["Nirmala UI", "Mangal", "Kokila", "Aparajita", "Utsaah",
                    "Noto Sans Devanagari", "Noto Serif Devanagari", "Lohit Devanagari",
                    "Mukta", "Sanskrit Text"]
BUCKET_COLORS = {"0-30": "#4caf50", "31-60": "#ffb300", "61+": "#e53935", "unknown": "#9e9e9e"}


@lru_cache(maxsize=1)
def devanagari_font() -> str | None:
    """Name of an installed font with Devanagari glyphs, or None."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    return next((n for n in DEVANAGARI_FONTS if n in installed), None)


def _fp(size=10, weight="normal"):
    # Family list = per-glyph fallback, so Latin and Devanagari both render.
    families = [devanagari_font(), "DejaVu Sans"] if devanagari_font() else ["DejaVu Sans"]
    return font_manager.FontProperties(family=families, size=size, weight=weight)


def _png(fig: Figure) -> bytes:
    FigureCanvasAgg(fig)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    return buf.getvalue()


def _short(name: str, n=22) -> str:
    return name if len(name) <= n else name[: n - 1] + "…"


def no_data_png(title: str) -> bytes:
    fig = Figure(figsize=(8, 4), layout="constrained")
    ax = fig.add_subplot()
    ax.axis("off")
    ax.text(0.5, 0.58, "No data yet", ha="center", va="center", fontproperties=_fp(22, "bold"),
            color="#555")
    ax.text(0.5, 0.38, title, ha="center", va="center", fontproperties=_fp(11), color="#888")
    return _png(fig)


def balances_png(customers: list[dict]) -> bytes:
    """customers: [{"name", "balance"}] sorted descending, balance > 0."""
    top = customers[:10]
    if not top:
        return no_data_png("Nobody owes anything right now.")
    fig = Figure(figsize=(8, 5), layout="constrained")
    ax = fig.add_subplot()
    names = [_short(c["name"]) for c in top][::-1]       # largest at the top
    values = [float(c["balance"]) for c in top][::-1]
    bars = ax.barh(range(len(values)), values, color="#3f51b5")
    ax.set_yticks(range(len(values)))
    ax.set_yticklabels(names, fontproperties=_fp(10))
    for bar, v in zip(bars, values):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f" Rs {v:,.0f}",
                va="center", fontproperties=_fp(9))
    ax.set_xlim(0, max(values) * 1.18)
    ax.set_xlabel("Balance owed (Rs)", fontproperties=_fp(10))
    ax.set_title("Who owes the most (top 10)", fontproperties=_fp(13, "bold"))
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def aging_png(report: dict) -> bytes:
    """report: the dict from services.aging_report()."""
    top = report["customers"][:10]
    if not top:
        return no_data_png("No outstanding balances to age.")
    fig = Figure(figsize=(8, 5), layout="constrained")
    ax = fig.add_subplot()
    names = [_short(c["name"]) for c in top][::-1]
    left = [0.0] * len(top)
    for b in BUCKETS:
        vals = [float(c[b]) for c in top][::-1]
        label = f"{b} days" if b != "unknown" else "unknown date"
        ax.barh(range(len(vals)), vals, left=left, color=BUCKET_COLORS[b],
                label=f"{label}: Rs {float(report['buckets'][b]):,.0f}")
        left = [l + v for l, v in zip(left, vals)]
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontproperties=_fp(10))
    ax.set_xlabel("Outstanding (Rs)", fontproperties=_fp(10))
    ax.set_title("Outstanding by age (top 10 customers)", fontproperties=_fp(13, "bold"))
    ax.legend(title="All customers", prop=_fp(9), title_fontproperties=_fp(9), loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)
