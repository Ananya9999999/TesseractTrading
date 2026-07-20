"""
Confidence score: attacks the core lie of backtesting (a single P&L number
implies certainty). Instead of one number, we quantify how fragile that
number is.

v1, deliberately simple and explainable:
1. Bootstrap resampling: resample trade-level P&Ls with replacement N times,
   see the distribution of total returns. Wide distribution = fragile result.
2. Outlier concentration: what fraction of total P&L came from the single
   best day? If one day explains most of the return, that's a red flag.
3. Degradation test: rerun with worse fill assumptions (e.g. impact_exponent
   scaled up) and report how much the return drops. Small drop = robust to
   our own modeling uncertainty; large drop = the result depends heavily on
   fill assumptions we can't fully verify.

Each of these is a separate, named, explainable number. We are NOT
collapsing this into a single opaque "confidence: 73%" score in v1 --
that would repeat the exact sin we're trying to fix.
"""

from __future__ import annotations
from dataclasses import dataclass
import random


@dataclass
class ConfidenceReport:
    bootstrap_mean: float
    bootstrap_p5: float           
    bootstrap_p95: float
    best_day_pnl: float
    best_day_share_of_total: float  
    degraded_pnl: float | None      
    degradation_pct: float | None
    notes: list[str]


def compute_confidence_report(
    trade_pnls: list[float],
    n_resamples: int = 2000,
    degraded_pnl: float | None = None,
) -> ConfidenceReport:
    if not trade_pnls:
        return ConfidenceReport(
            bootstrap_mean=0, bootstrap_p5=0, bootstrap_p95=0,
            best_day_pnl=0, best_day_share_of_total=0,
            degraded_pnl=None, degradation_pct=None,
            notes=["No trades to analyze."],
        )

    total_pnl = sum(trade_pnls)
    n = len(trade_pnls)

    resampled_totals = []
    for _ in range(n_resamples):
        sample = [random.choice(trade_pnls) for _ in range(n)]
        resampled_totals.append(sum(sample))
    resampled_totals.sort()

    p5 = resampled_totals[int(0.05 * n_resamples)]
    p95 = resampled_totals[int(0.95 * n_resamples)]
    mean = sum(resampled_totals) / n_resamples

    best_day = max(trade_pnls)
    best_day_share = (best_day / total_pnl) if total_pnl != 0 else float("inf")

    notes = []
    if best_day_share > 0.5 and total_pnl > 0:
        notes.append(
            f"Warning: a single trade accounts for {best_day_share:.0%} of total P&L. "
            "Result is not robust -- it depends heavily on one outlier."
        )
    if p5 < 0 < total_pnl:
        notes.append(
            "Warning: bootstrap resampling shows a plausible scenario (5th percentile) "
            "where this strategy loses money, despite a positive headline result."
        )

    degradation_pct = None
    if degraded_pnl is not None and total_pnl != 0:
        degradation_pct = (total_pnl - degraded_pnl) / abs(total_pnl) * 100
        if degradation_pct > 30:
            notes.append(
                f"Warning: worsening fill assumptions drops P&L by {degradation_pct:.0f}%. "
                "Result is highly sensitive to execution quality."
            )

    if not notes:
        notes.append("No major fragility flags detected under current tests.")

    return ConfidenceReport(
        bootstrap_mean=round(mean, 2),
        bootstrap_p5=round(p5, 2),
        bootstrap_p95=round(p95, 2),
        best_day_pnl=round(best_day, 2),
        best_day_share_of_total=round(best_day_share, 4),
        degraded_pnl=degraded_pnl,
        degradation_pct=round(degradation_pct, 2) if degradation_pct is not None else None,
        notes=notes,
    )
