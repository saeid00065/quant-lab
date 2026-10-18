from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum
import json
import pandas as pd
import sqlite3
from pathlib import Path

class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class AlertType(Enum):
    PRICE = \"price\"
    RISK = \"risk\"
    POSITION = \"position\"
    SYSTEM = \"system\"
    EXECUTION = \"execution\"

@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    message: str
    source: str = \"\"
    details: Optional[dict] = None

@dataclass
class Alert:
    alert_id: str
    alert_type: AlertType
    message: str
    severity: LogLevel
    triggered_at: datetime
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    details: Optional[dict] = None

class PortfolioTracker:
    def __init__(self, name: str = \"default\", db_path: Optional[str] = None):
        self.name = name
        self.db_path = db_path or f\"portfolio_{name}.db\"
        self._positions: dict[str, dict] = {}
        self._transaction_history: list[dict] = []
        self._daily_pnl: dict[str, float] = {}
        self._init_db()
    
    def _init_db(self):
        \"\"\"Initialize SQLite database for persistence.\"\"\"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL,
                avg_price REAL,
                current_price REAL,
                market_value REAL,
                unrealized_pnl REAL,
                unrealized_pnl_pct REAL,
                updated_at TEXT
            )
        \"\"\")
        cursor.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                commission REAL,
                timestamp TEXT
            )
        \"\"\")
        cursor.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date TEXT PRIMARY KEY,
                pnl REAL,
                starting_equity REAL,
                ending_equity REAL
            )
        \"\"\")
        conn.commit()
        conn.close()
    
    def update_position(self, symbol: str, quantity: float, price: float, commission: float = 0.0):
        \"\"\"Update or create a position.\"\"\"
        current = self._positions.get(symbol, {\"quantity\": 0, \"avg_price\": 0})
        
        if quantity == 0:
            # Close position
            self._positions.pop(symbol, None)
        else:
            if current[\"quantity\"] == 0:
                avg_price = price
            else:
                # Weighted average
                total_cost = current[\"quantity\"] * current[\"avg_price\"] + quantity * price
                new_quantity = current[\"quantity\"] + quantity
                avg_price = total_cost / new_quantity if new_quantity != 0 else 0
            
            self._positions[symbol] = {
                \"quantity\": quantity,
                \"avg_price\": avg_price,
                \"current_price\": price,
                \"market_value\": quantity * price,
                \"unrealized_pnl\": quantity * (price - avg_price),
                \"updated_at\": datetime.now().isoformat()
            }
        
        # Record transaction
        self._transaction_history.append({
            \"symbol\": symbol,
            \"side\": \"buy\" if quantity > 0 else \"sell\",
            \"quantity\": abs(quantity),
            \"price\": price,
            \"commission\": commission,
            \"timestamp\": datetime.now().isoformat()
        })
    
    def update_prices(self, prices: dict[str, float]):
        \"\"\"Update current prices for all positions.\"\"\"
        for symbol, price in prices.items():
            if symbol in self._positions:
                pos = self._positions[symbol]
                pos[\"current_price\"] = price
                pos[\"market_value\"] = pos[\"quantity\"] * price
                pos[\"unrealized_pnl\"] = pos[\"quantity\"] * (price - pos[\"avg_price\"])
                pos[\"unrealized_pnl_pct\"] = (price - pos[\"avg_price\"]) / pos[\"avg_price\"] if pos[\"avg_price\"] > 0 else 0
                pos[\"updated_at\"] = datetime.now().isoformat()
    
    def get_portfolio_summary(self) -> dict:
        \"\"\"Get comprehensive portfolio summary.\"\"\"
        total_value = sum(p[\"market_value\"] for p in self._positions.values())
        total_cost = sum(p[\"quantity\"] * p[\"avg_price\"] for p in self._positions.values())
        total_pnl = sum(p[\"unrealized_pnl\"] for p in self._positions.values())
        
        long_value = sum(p[\"market_value\"] for p in self._positions.values() if p[\"quantity\"] > 0)
        short_value = sum(-p[\"market_value\"] for p in self._positions.values() if p[\"quantity\"] < 0)
        
        return {
            \"total_market_value\": total_value,
            \"total_cost_basis\": total_cost,
            \"total_unrealized_pnl\": total_pnl,
            \"num_positions\": len(self._positions),
            \"long_exposure\": long_value,
            \"short_exposure\": short_value,
            \"net_exposure\": long_value - short_value,
            \"positions\": self._positions,
        }
    
    def get_positions_dataframe(self) -> pd.DataFrame:
        \"\"\"Get positions as DataFrame.\"\"\"
        if not self._positions:
            return pd.DataFrame()
        
        data = []
        for symbol, pos in self._positions.items():
            data.append({
                \"symbol\": symbol,
                \"quantity\": pos[\"quantity\"],
                \"avg_price\": pos[\"avg_price\"],
                \"current_price\": pos[\"current_price\"],
                \"market_value\": pos[\"market_value\"],
                \"unrealized_pnl\": pos[\"unrealized_pnl\"],
                \"unrealized_pnl_pct\": pos[\"unrealized_pnl_pct\"] * 100,
                \"updated_at\": pos[\"updated_at\"],
            })
        return pd.DataFrame(data).sort_values(\"market_value\", ascending=False)
    
    def get_transactions_df(self, days: int = 30) -> pd.DataFrame:
        \"\"\"Get recent transactions.\"\"\"
        cutoff = datetime.now() - timedelta(days=days)
        filtered = [t for t in self._transaction_history if datetime.fromisoformat(t[\"timestamp\"]) >= cutoff]
        
        if not filtered:
            return pd.DataFrame()
        
        return pd.DataFrame(filtered).sort_values(\"timestamp\", ascending=False)
    
    def record_daily_pnl(self, date: str, pnl: float, starting: float, ending: float):
        \"\"\"Record daily P&L.\"\"\"
        self._daily_pnl[date] = {\"pnl\": pnl, \"starting_equity\": starting, \"ending_equity\": ending}
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(\"INSERT OR REPLACE INTO daily_pnl VALUES (?, ?, ?, ?)\",
                    (date, pnl, starting, ending))
        conn.commit()
        conn.close()

class MonitoringSystem:
    def __init__(self, name: str = \"quantlab\"):
        self.name = name
        self.logs: list[LogEntry] = []
        self.alerts: list[Alert] = []
        self.alert_counter = 0
        self.portfolio_tracker = PortfolioTracker(name)
        self.started_at = datetime.now()
        
        # Health checks
        self._health_checks: dict[str, callable] = {}
    
    def log(self, level: LogLevel, message: str, source: str = \"\", details: Optional[dict] = None):
        \"\"\"Add a log entry.\"\"\"
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            source=source,
            details=details,
        )
        self.logs.append(entry)
        
        # Keep only last 1000 logs
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
    
    def info(self, message: str, source: str = \"\", **kwargs):
        self.log(LogLevel.INFO, message, source, kwargs)
    
    def warning(self, message: str, source: str = \"\", **kwargs):
        self.log(LogLevel.WARNING, message, source, kwargs)
    
    def error(self, message: str, source: str = \"\", **kwargs):
        self.log(LogLevel.ERROR, message, source, kwargs)
    
    def create_alert(
        self,
        alert_type: AlertType,
        message: str,
        severity: LogLevel = LogLevel.WARNING,
        details: Optional[dict] = None,
    ) -> Alert:
        self.alert_counter += 1
        alert = Alert(
            alert_id=f\"ALT-{self.alert_counter:04d}\",
            alert_type=alert_type,
            message=message,
            severity=severity,
            triggered_at=datetime.now(),
            details=details,
        )
        self.alerts.append(alert)
        self.log(severity, f\"ALERT: {message}\", \"monitoring\", {\"alert_id\": alert.alert_id})
        return alert
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        \"\"\"Acknowledge an alert.\"\"\"
        for alert in self.alerts:
            if alert.alert_id == alert_id and not alert.acknowledged:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now()
                return True
        return False
    
    def get_active_alerts(self) -> list[Alert]:
        \"\"\"Get unacknowledged alerts.\"\"\"
        return [a for a in self.alerts if not a.acknowledged]
    
    def get_critical_alerts(self) -> list[Alert]:
        \"\"\"Get critical and warning alerts.\"\"\"
        return [a for a in self.alerts if not a.acknowledged and a.severity in (LogLevel.ERROR, LogLevel.CRITICAL)]
    
    def add_health_check(self, name: str, check_func: callable):
        \"\"\"Add a health check function.\"\"\"
        self._health_checks[name] = check_func
    
    def run_health_check(self) -> dict:
        \"\"\"Run all health checks.\"\"\"
        results = {}
        for name, check_func in self._health_checks.items():
            try:
                result = check_func()
                results[name] = {\"status\": \"healthy\" if result else \"unhealthy\", \"message\": \"OK\" if result else \"Check failed\"}
            except Exception as e:
                results[name] = {\"status\": \"error\", \"message\": str(e)}
        return results
    
    def get_logs_df(self, level: Optional[LogLevel] = None, source: str = \"\", limit: int = 100) -> pd.DataFrame:
        \"\"\"Get logs as DataFrame.\"\"\"
        df = pd.DataFrame([
            {
                \"timestamp\": l.timestamp.isoformat(),
                \"level\": l.level.name,
                \"source\": l.source,
                \"message\": l.message,
            }
            for l in self.logs
        ])
        
        if df.empty:
            return df
        
        if level:
            df = df[df[\"level\"] >= level.name]
        if source:
            df = df[df[\"source\"] == source]
        
        return df.tail(limit).sort_values(\"timestamp\", ascending=False)
    
    def get_alerts_df(self, include_acked: bool = False) -> pd.DataFrame:
        \"\"\"Get alerts as DataFrame.\"\"\"
        alerts_to_use = self.alerts if include_acked else [a for a in self.alerts if not a.acknowledged]
        
        if not alerts_to_use:
            return pd.DataFrame()
        
        return pd.DataFrame([
            {
                \"alert_id\": a.alert_id,
                \"type\": a.alert_type.value,
                \"severity\": a.severity.name,
                \"message\": a.message,
                \"triggered_at\": a.triggered_at.isoformat(),
                \"acknowledged\": a.acknowledged,
                \"details\": json.dumps(a.details) if a.details else None,
            }
            for a in alerts_to_use
        ]).sort_values(\"triggered_at\", ascending=False)
    
    def get_system_health(self) -> dict:
        \"\"\"Get system health summary.\"\"\"
        uptime = (datetime.now() - self.started_at).total_seconds()
        
        health = self.run_health_check()
        active_alerts = self.get_active_alerts()
        critical_alerts = self.get_critical_alerts()
        
        portfolio = self.portfolio_tracker.get_portfolio_summary()
        
        return {
            \"status\": \"healthy\" if not critical_alerts else \"degraded\",
            \"uptime_seconds\": uptime,
            \"uptime_formatted\": str(timedelta(seconds=int(uptime))),
            \"health_checks\": health,
            \"active_alerts\": len(active_alerts),
            \"critical_alerts\": len(critical_alerts),
            \"total_logs\": len(self.logs),
            \"total_alerts\": len(self.alerts),
            \"portfolio\": portfolio,
        }
