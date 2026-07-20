"""
Synthetic OHLC bar generator. Placeholder ONLY -- replace with a real
loader (NSE bhavcopy / Kite Connect historical API) in app/data/nse_loader.py
once data access is confirmed. Keeping this as a separate module means
swapping data sources never touches engine code.
"""

import random
from ..engine.fill_model import Bar


def generate_synthetic_bars(
    symbol: str = "NIFTY26AUGSTRADDLE",
    n_bars: int = 30,
    start_price: float = 220.0,
    seed: int = 42,
) -> list[Bar]:
    random.seed(seed)
    bars = []
    price = start_price
    for i in range(n_bars):
        drift = random.uniform(-0.03, 0.02) * price  
        vol = random.uniform(0.01, 0.05) * price
        open_p = price
        close_p = max(1.0, price + drift + random.uniform(-vol, vol))
        high_p = max(open_p, close_p) + random.uniform(0, vol)
        low_p = max(0.5, min(open_p, close_p) - random.uniform(0, vol))
        volume = random.uniform(500, 5000)

        bars.append(Bar(
            timestamp=f"2026-08-{i+1:02d}",
            symbol=symbol,
            open=round(open_p, 2),
            high=round(high_p, 2),
            low=round(low_p, 2),
            close=round(close_p, 2),
            volume=round(volume, 0),
        ))
        price = close_p
    return bars
