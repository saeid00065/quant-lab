from __future__ import annotations
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
