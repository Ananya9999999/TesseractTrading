"""
Backtester: runs a Strategy over a sequence of Bars using a given
FillModel, and produces a fully auditable TradeLog. Every trade in the
output can be traced back to the bar and fill-model explanation that
produced it -- this IS the audit-trail feature, not a separate system
bolted on afterward.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from .fill_model import FillModel, Order, Bar, FillResult
from .strategy import Strategy


@dataclass
class TradeRecord:
    timestamp: str
    symbol: str
    side: str
    quantity: float
    fill_price: float
    slippage_bps: float
    strategy_reason: str
    fill_explanation: str


@dataclass
class BacktestResult:
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    final_pnl: float = 0.0


class Backtester:
    def __init__(self, strategy: Strategy, fill_model: FillModel, starting_cash: float = 1_000_000):
        self.strategy = strategy
        self.fill_model = fill_model
        self.starting_cash = starting_cash

    def run(self, bars: list[Bar]) -> BacktestResult:
        result = BacktestResult()
        cash = self.starting_cash
        position: dict = {}
        equity_curve = []

        for bar in bars:
            signals = self.strategy.on_bar(bar, position)

            for signal in signals:
                order = Order(
                    symbol=signal.symbol,
                    side=signal.side,
                    quantity=signal.quantity,
                    reference_price=bar.close,
                )
                fill: FillResult = self.fill_model.simulate_fill(order, bar)

                if fill.filled_quantity <= 0:
                    continue

                sign = -1 if signal.side.value == "buy" else 1
                cash += sign * fill.fill_price * fill.filled_quantity

                result.trades.append(TradeRecord(
                    timestamp=bar.timestamp,
                    symbol=bar.symbol,
                    side=signal.side.value,
                    quantity=fill.filled_quantity,
                    fill_price=fill.fill_price,
                    slippage_bps=fill.slippage_bps,
                    strategy_reason=signal.reason,
                    fill_explanation=fill.explanation,
                ))

                if signal.side.value == "sell" and not position:
                    position = {"entry_premium": fill.fill_price, "current_value": fill.fill_price}
                elif signal.side.value == "buy" and position:
                    position = {}

            if position:
                position["current_value"] = bar.close

            equity_curve.append(cash)

        result.equity_curve = equity_curve
        result.final_pnl = cash - self.starting_cash
        return result
