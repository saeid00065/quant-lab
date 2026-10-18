from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime
import pandas as pd
import numpy as np

@dataclass
class MarketData:
    symbol: str
    data: pd.DataFrame
    source: str
    last_updated: datetime
    
    @property
    def latest(self) -> dict:
        if self.data.empty:
            return {}
        row = self.data.iloc[-1]
        return {
            \"date\": row.get(\"date\"),
            \"open\": row.get(\"open\"),
            \"high\": row.get(\"high\"),
            \"low\": row.get(\"low\"),
            \"close\": row.get(\"close\"),
            \"volume\": row.get(\"volume\"),
        }

class MarketDataProvider:
    \"\"\"Unified market data provider supporting multiple sources.\"\"\"
    
    def __init__(self):
        self._cache: dict[str, MarketData] = {}
        self._providers: dict[str, callable] = {
            \"synthetic\": self._fetch_synthetic,
            \"yfinance\": self._fetch_yfinance,
            \"csv\": self._fetch_csv,
        }
    
    def fetch(
        self,
        symbol: str,
        source: str = \"synthetic\",
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = \"1d\",
        **kwargs,
    ) -> MarketData:
        \"\"\"Fetch market data from specified source.\"\"\"
        if source not in self._providers:
            raise ValueError(f\"Unknown source: {source}\")
        
        cache_key = f\"{symbol}_{source}_{start}_{end}\"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        data = self._providers[source](symbol, start, end, interval, **kwargs)
        market_data = MarketData(
            symbol=symbol,
            data=data,
            source=source,
            last_updated=datetime.now(),
        )
        self._cache[cache_key] = market_data
        return market_data
    
    def _fetch_synthetic(
        self,
        symbol: str,
        start: Optional[str],
        end: Optional[str],
        interval: str,
        **kwargs,
    ) -> pd.DataFrame:
        \"\"\"Generate synthetic market data.\"\"\"
        from src.data_loader import generate_synthetic_ohlcv
        
        return generate_synthetic_ohlcv(
            start=start or \"2020-01-01\",
            periods=kwargs.get(\"periods\", 1000),
            seed=kwargs.get(\"seed\", 42),
            volatility=kwargs.get(\"volatility\", 0.02),
            drift=kwargs.get(\"drift\", 0.0002),
        )
    
    def _fetch_yfinance(
        self,
        symbol: str,
        start: Optional[str],
        end: Optional[str],
        interval: str,
        **kwargs,
    ) -> pd.DataFrame:
        \"\"\"Fetch from Yahoo Finance.\"\"\"
        from src.data_loader import fetch_yfinance_ohlcv
        
        return fetch_yfinance_ohlcv(
            symbol,
            start=start or \"2020-01-01\",
            end=end,
            interval=interval,
        )
    
    def _fetch_csv(
        self,
        symbol: str,
        start: Optional[str],
        end: Optional[str],
        interval: str,
        **kwargs,
    ) -> pd.DataFrame:
        \"\"\"Load from CSV.\"\"\"
        from src.data_loader import load_csv_bytes
        
        if \"content\" not in kwargs:
            raise ValueError(\"CSV source requires 'content' parameter\")
        
        return load_csv_bytes(kwargs[\"content\"])
    
    def get_latest_prices(self, symbols: list[str]) -> dict[str, float]:
        \"\"\"Get latest prices for multiple symbols.\"\"\"
        prices = {}
        for symbol in symbols:
            try:
                data = self.fetch(symbol)
                latest = data.latest
                if \"close\" in latest:
                    prices[symbol] = float(latest[\"close\"])
            except Exception:
                prices[symbol] = 0.0
        return prices
    
    def clear_cache(self):
        \"\"\"Clear the data cache.\"\"\"
        self._cache.clear()
