"""
Strategy interface. Deliberately narrow for the sprint: we support ONE
concrete strategy (short straddle) end to end before generalizing.
Do not add a strategy DSL yet -- that's scope creep until the fill model
and confidence score are proven on one real case.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from .fill_model import Order, OrderSide, Bar


@dataclass
class Signal:
    """A strategy's intent to trade, before it becomes an Order."""
    symbol: str
    side: OrderSide
    quantity: float
    reason: str 


class Strategy(ABC):
    @abstractmethod
    def on_bar(self, bar: Bar, position: dict) -> list[Signal]:
        """Return zero or more signals given the current bar and open position."""
        ...

    @abstractmethod
    def entry_condition(self, bar: Bar) -> bool:
        ...

    @abstractmethod
    def exit_condition(self, bar: Bar, position: dict) -> bool:
        ...


class ShortStraddle(Strategy):
    """
    Sell an ATM call and an ATM put on entry_day, hold to expiry_day
    (or exit early if a stop-loss on combined premium is hit).

    This is intentionally simple. It exists to exercise the fill model
    and confidence score, not to be a good trading strategy.
    """

    def __init__(self, entry_dte: int, quantity: float, stop_loss_multiple: float = 2.0):
        self.entry_dte = entry_dte         
        self.quantity = quantity
        self.stop_loss_multiple = stop_loss_multiple

    def entry_condition(self, bar: Bar) -> bool:
        return True

    def exit_condition(self, bar: Bar, position: dict) -> bool:
        if not position:
            return False
        entry_premium = position.get("entry_premium", 0)
        current_value = position.get("current_value", 0)
        return current_value > entry_premium * self.stop_loss_multiple

    def on_bar(self, bar: Bar, position: dict) -> list[Signal]:
        signals = []
        if not position and self.entry_condition(bar):
            signals.append(Signal(
                symbol=bar.symbol, side=OrderSide.SELL, quantity=self.quantity,
                reason=f"Entry: sold at {self.entry_dte} DTE per strategy rule.",
            ))
        elif position and self.exit_condition(bar, position):
            signals.append(Signal(
                symbol=bar.symbol, side=OrderSide.BUY, quantity=self.quantity,
                reason=f"Exit: stop-loss triggered at {self.stop_loss_multiple}x entry premium.",
            ))
        return signals
