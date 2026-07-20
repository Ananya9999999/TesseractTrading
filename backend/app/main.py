from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .engine.fill_model import OHLCDepthFillModel, NaiveMidFillModel
from .engine.strategy import ShortStraddle
from .engine.backtester import Backtester
from .engine.confidence import compute_confidence_report
from .data.synthetic import generate_synthetic_bars
from .models import BacktestResponse, TradeOut, ConfidenceOut

app = FastAPI(title="Backtest Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/backtest/demo", response_model=BacktestResponse)
def run_demo_backtest():
    """
    Runs the short straddle strategy over synthetic OHLC bars using the
    realistic (OHLC depth) fill model, then computes a confidence report
    including a degradation test against a harsher fill assumption.
    Swap generate_synthetic_bars() for a real data loader when ready --
    nothing else in this function needs to change.
    """
    bars = generate_synthetic_bars()

    strategy = ShortStraddle(entry_dte=30, quantity=50, stop_loss_multiple=2.0)
    realistic_fill_model = OHLCDepthFillModel(impact_exponent=0.5)
    result = Backtester(strategy, realistic_fill_model).run(bars)

    harsh_fill_model = OHLCDepthFillModel(impact_exponent=1.0)
    degraded_result = Backtester(strategy, harsh_fill_model).run(bars)

    trade_pnls = [
        (t.fill_price * t.quantity if t.side == "sell" else -t.fill_price * t.quantity)
        for t in result.trades
    ]

    confidence = compute_confidence_report(
        trade_pnls=trade_pnls,
        degraded_pnl=degraded_result.final_pnl,
    )

    return BacktestResponse(
        final_pnl=result.final_pnl,
        equity_curve=result.equity_curve,
        trades=[TradeOut(**t.__dict__) for t in result.trades],
        confidence=ConfidenceOut(**confidence.__dict__),
    )
