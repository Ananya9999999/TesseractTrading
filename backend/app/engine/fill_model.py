"""
Fill models: given an order and the market data available at that bar,
decide what price (and how much size) actually fills.

This is the swappable core of the "market-impact-aware" claim. Every fill
model implements the same interface, so we can start with OHLC-based
synthetic depth and later swap in a real order-book replay model without
touching the backtester or strategy code.

Design principle: every FillResult carries an `explanation` string. This
is not cosmetic -- it's the audit trail. Any fill we can't explain in one
sentence is a fill we shouldn't trust.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Bar:
    """One OHLCV bar for a single contract at a point in time."""
    timestamp: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: float
    reference_price: float


@dataclass
class FillResult:
    filled_quantity: float
    fill_price: float
    slippage_bps: float        
    explanation: str             


class FillModel(ABC):
    """Base interface. Swap implementations without touching the backtester."""

    @abstractmethod
    def simulate_fill(self, order: Order, bar: Bar) -> FillResult:
        ...


class NaiveMidFillModel(FillModel):
    """
    The thing every other retail backtester does: assume you get filled
    at the reference price with no slippage, regardless of size.
    We keep this ONLY as a baseline to show how much it overstates returns
    versus OHLCDepthFillModel -- never present this as the "real" result.
    """

    def simulate_fill(self, order: Order, bar: Bar) -> FillResult:
        return FillResult(
            filled_quantity=order.quantity,
            fill_price=order.reference_price,
            slippage_bps=0.0,
            explanation="Naive model: filled in full at reference price, no market impact assumed.",
        )


class OHLCDepthFillModel(FillModel):
    """
    Synthetic depth model when we only have OHLC + volume (no real order book).

    Core assumption, stated explicitly so it can be challenged/tuned:
    - The bar's (high - low) range approximates the price dispersion available
      to trade against during that bar.
    - An order's impact scales with its size relative to the bar's volume:
      a small order relative to volume fills near the reference price; an
      order that is a large fraction of bar volume walks toward the
      unfavorable side of the bar's range.
    - Impact is modeled as: slippage_fraction = participation_rate ** impact_exponent
      capped at the bar's high/low so we never claim a fill outside the bar.

    This is a deliberately simple, named, swappable assumption -- not a
    claim of real order-book microstructure. Replace with a real depth
    replay model when tick/order-book data is available.
    """

    def __init__(self, impact_exponent: float = 0.5, max_participation: float = 0.25):
        self.impact_exponent = impact_exponent
        self.max_participation = max_participation

    def simulate_fill(self, order: Order, bar: Bar) -> FillResult:
        if bar.volume <= 0:
            return FillResult(
                filled_quantity=0.0,
                fill_price=order.reference_price,
                slippage_bps=0.0,
                explanation=f"No volume in bar {bar.timestamp} for {bar.symbol}; order unfilled.",
            )

        participation = min(order.quantity / bar.volume, self.max_participation)
        # unfilled portion if participation cap is binding
        fillable_fraction = min(1.0, self.max_participation / max(participation, 1e-9)) \
            if participation >= self.max_participation else 1.0
        filled_qty = order.quantity * fillable_fraction

        impact_fraction = participation ** self.impact_exponent
        bar_range = max(bar.high - bar.low, 0.0)

        if order.side == OrderSide.BUY:
            fill_price = order.reference_price + impact_fraction * bar_range
            fill_price = min(fill_price, bar.high)
        else:
            fill_price = order.reference_price - impact_fraction * bar_range
            fill_price = max(fill_price, bar.low)

        slippage_bps = (
            (fill_price - order.reference_price) / order.reference_price * 10_000
            if order.side == OrderSide.BUY
            else (order.reference_price - fill_price) / order.reference_price * 10_000
        )

        explanation = (
            f"Bar {bar.timestamp}: order size {order.quantity:.0f} vs bar volume "
            f"{bar.volume:.0f} (participation {participation:.1%}). "
            f"Impact model pushed fill {impact_fraction:.1%} of the bar's "
            f"{bar_range:.2f}-point range against the order. "
            f"{'Capped fill at max participation.' if fillable_fraction < 1.0 else ''}"
        ).strip()

        return FillResult(
            filled_quantity=filled_qty,
            fill_price=round(fill_price, 2),
            slippage_bps=round(slippage_bps, 2),
            explanation=explanation,
        )
