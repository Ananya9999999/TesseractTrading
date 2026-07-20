from pydantic import BaseModel


class TradeOut(BaseModel):
    timestamp: str
    symbol: str
    side: str
    quantity: float
    fill_price: float
    slippage_bps: float
    strategy_reason: str
    fill_explanation: str


class ConfidenceOut(BaseModel):
    bootstrap_mean: float
    bootstrap_p5: float
    bootstrap_p95: float
    best_day_pnl: float
    best_day_share_of_total: float
    degraded_pnl: float | None
    degradation_pct: float | None
    notes: list[str]


class BacktestResponse(BaseModel):
    final_pnl: float
    equity_curve: list[float]
    trades: list[TradeOut]
    confidence: ConfidenceOut
