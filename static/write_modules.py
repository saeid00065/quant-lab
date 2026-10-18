import os
os.chdir(r'C:\Users\Lawrence\Desktop\quant-lab')

# Write risk_management.py
with open('src/modules/risk_management.py', 'w') as f:
    f.write('''from __future__ import annotations
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
    
    def get_total_exposure(self):
        return sum(p.market_value for p in self.positions.values())
    
    def get_cash_available(self):
        return self.portfolio_value * (1.0 - self.config.min_cash_pct) - self.get_total_exposure()
    
    def calculate_position_size(self, price, risk_pct=0.02):
        risk_amount = self.portfolio_value * risk_pct
        return risk_amount / price
    
    def check_daily_loss(self):
        self.daily_pnl = self.portfolio_value - self.daily_start
        daily_loss_pct = -self.daily_pnl / self.daily_start
        if daily_loss_pct > self.config.max_daily_loss_pct:
            return False, f"Daily loss {daily_loss_pct:.1%} exceeds limit"
        return True, "OK"
    
    def get_sector_exposure(self):
        sectors = {}
        for pos in self.positions.values():
            sectors[pos.sector] = sectors.get(pos.sector, 0.0) + pos.market_value
        return sectors
''')

print('risk_management.py written')

# Write execution.py
with open('src/modules/execution.py', 'w') as f:
    f.write('''from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime

@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: str = "pending"
    created_at: datetime = None
    commission: float = 0.0
    slippage_bps: float = 2.0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class ExecutionManager:
    def __init__(self, fee_bps=1.0, slippage_bps=2.0):
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.orders = {}
        self.fills = []
        self.order_counter = 0
    
    def create_order(self, symbol, side, quantity, order_type="market", price=None, stop_price=None):
        self.order_counter += 1
        order_id = f"ORD-{self.order_counter:06d}"
        order = Order(order_id, symbol, side, order_type, quantity, price, stop_price, slippage_bps=self.slippage_bps)
        self.orders[order_id] = order
        return order
    
    def simulate_fill(self, order, current_price):
        fill_price = current_price * (1 + order.slippage_bps / 10000) if order.side == "buy" else current_price * (1 - order.slippage_bps / 10000)
        commission = order.quantity * fill_price * self.fee_bps / 10000
        fill = {"fill_id": f"FILL-{len(self.fills)+1:06d}", "order_id": order.order_id, "symbol": order.symbol, "side": order.side, "quantity": order.quantity, "price": fill_price, "commission": commission, "timestamp": datetime.now()}
        self.fills.append(fill)
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.commission = commission
        order.status = "filled"
        return fill
    
    def get_execution_stats(self):
        return {"total_orders": len(self.orders), "filled_orders": len([o for o in self.orders.values() if o.status == "filled"]), "cancelled_orders": len([o for o in self.orders.values() if o.status == "cancelled"]), "pending_orders": len([o for o in self.orders.values() if o.status == "pending"]), "total_commission": sum(f["commission"] for f in self.fills)}
''')

print('execution.py written')
print('Setup complete!')
