import pytest
import pandas as pd
import numpy as np
from risk.manager import RiskManager


class TestRiskManager:
    @pytest.fixture
    def basic_config(self):
        return {
            "risk": {
                "risk_per_trade_pct": 2.0,
                "daily_loss_limit_pct": 10.0,
                "daily_loss_limit_usd": 1000,
                "max_open_positions": 2,
                "max_daily_trades": 50,
                "enable_compounding": False,
            },
            "pair_config": {
                "EURUSD": {
                    "pip_value": 10.0,
                    "pip_size": 0.0001,
                    "min_lot": 0.01,
                    "max_lot": 100.0,
                }
            },
        }

    def test_initialization(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)
        assert rm.balance == 10000.0
        assert rm.risk_pct == 2.0
        assert rm.max_open == 2
        assert rm.open_positions == 0
        assert rm.killed is False

    def test_calculate_position_size(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        entry_price = 1.0850
        sl_price = 1.0830

        lot_size = rm.calculate_position_size("EURUSD", entry_price, sl_price)

        risk_amount = 10000.0 * (2.0 / 100)
        sl_distance = abs(1.0850 - 1.0830)
        pips_at_risk = sl_distance / 0.0001
        expected_lot = risk_amount / (pips_at_risk * 10.0)

        assert lot_size > 0
        assert lot_size == pytest.approx(expected_lot, 0.01)

    def test_calculate_position_size_zero_sl_distance(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        lot_size = rm.calculate_position_size("EURUSD", 1.0850, 1.0850)
        assert lot_size == 0

    def test_can_open_trade(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        assert rm.can_open_trade() is True

        rm.open_position()
        rm.open_position()
        assert rm.open_positions == 2
        assert rm.can_open_trade() is False

    def test_can_open_trade_kill_switch(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        rm.killed = True
        assert rm.can_open_trade() is False

    def test_record_trade_result(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        rm.record_trade_result(100.0)
        assert rm.balance == 10100.0
        assert rm.daily_pnl == 100.0
        assert rm.daily_trades == 1

        rm.record_trade_result(-50.0)
        assert rm.balance == 10050.0
        assert rm.daily_pnl == 50.0

    def test_close_position(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        rm.open_position()
        rm.open_position()
        assert rm.open_positions == 2

        rm.close_position()
        assert rm.open_positions == 1

        rm.close_position()
        rm.close_position()
        assert rm.open_positions == 0

    def test_reset_daily(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        rm.daily_pnl = 500.0
        rm.daily_trades = 10
        rm.killed = True

        rm.reset_daily()

        assert rm.daily_pnl == 0.0
        assert rm.daily_trades == 0
        assert rm.killed is False

    def test_get_pair_config_fallback(self, basic_config):
        rm = RiskManager(basic_config, 10000.0)

        config = rm._get_pair_config("UNKNOWN_PAIR")
        assert "pip_value" in config
        assert "pip_size" in config
        assert config["min_lot"] == 0.01
