from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class RiskConfig:
    max_position_pct: float = 0.10
    max_sector_pct: float = 0.25
    max_leverage: float = 1.0
    max_loss_per_trade_pct: float = 0.02
    max_daily_loss_pct: float = 0.05
    min_cash_pct: float = 0.05

@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float = 0.0
    sector: str = "general"
    
    @property
    def market_value(self):
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self):
        return self.quantity * self.entry_price
    
    @property
    def unrealized_pnl(self):
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self):
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis

class RiskManager:
    def __init__(self, config=None, portfolio_value=1000000.0):
        self.config = config or RiskConfig()
        self.portfolio_value = portfolio_value
        self.positions = {}
        self.daily_pnl = 0.0
        self.daily_start = portfolio_value
    
    def update_portfolio_value(self, value):
        self.portfolio_value = value
    
    def add_position(self, symbol, quantity, price, sector="general"):
        self.positions[symbol] = Position(symbol, quantity, price, price, sector)
    
    def remove_position(self, symbol):
        self.positions.pop(symbol, None)
    
    def update_prices(self, prices):
        for sym, pos in self.positions.items():
            if sym in prices:
                pos.current_price = prices[sym]
    
    def get_total_exposure(self):
        return sum(p.market_value for p in self.positions.values())
    
    def get_cash_available(self):
        return self.portfolio_value * (1.0 - self.config.min_cash_pct) - self.get_total_exposure()
    
    def check_position_size(self, symbol, amount):
        position_value = amount * self.portfolio_value
        pct = position_value / self.portfolio_value
        if pct > self.config.max_position_pct:
            return False, f"Position {pct:.1%} exceeds max {self.config.max_position_pct:.1%}"
        total_exposure = self.get_total_exposure() + position_value
        if total_exposure / self.portfolio_value > self.config.max_leverage:
            return False, f"Would exceed leverage limit {self.config.max_leverage:.1f}x"
        return True, "OK"
    
    def calculate_position_size(self, price, risk_pct=0.02):
        risk_amount = self.portfolio_value * risk_pct
        return risk_amount / price
    
    def check_daily_loss(self):
        self.daily_pnl = self.portfolio_value - self.daily_start
        daily_loss_pct = -self.daily_pnl / self.daily_start
        if daily_loss_pct > self.config.max_daily_loss_pct:
            return False, f"Daily loss {daily_loss_pct:.1%} exceeds {self.config.max_daily_loss_pct:.1%}"
        return True, "OK"
    
    def get_sector_exposure(self):
        sectors = {}
        for pos in self.positions.values():
            sectors[pos.sector] = sectors.get(pos.sector, 0.0) + pos.market_value
        return sectors
    
    def get_risk_metrics(self):
        total_exposure = self.get_total_exposure()
        return {
            "portfolio_value": self.portfolio_value,
            "total_exposure": total_exposure,
            "cash_available": self.get_cash_available(),
            "exposure_pct": total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0,
            "num_positions": len(self.positions),
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": self.daily_pnl / self.daily_start if self.daily_start > 0 else 0,
            "sector_exposure": self.get_sector_exposure(),
        }
