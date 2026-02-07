"""
Tests for spread calculation in MarketData class.
"""
import pytest
import sys
sys.path.insert(0, "src")

from polymarket_mcp.utils.safety_limits import MarketData


class TestMarketDataSpread:
    """Test MarketData spread calculation."""

    def test_spread_calculated_with_mid_price(self):
        """Test that spread is calculated using mid price as base."""
        # Create market data with known values
        market_data = MarketData(
            market_id="test_market",
            token_id="test_token",
            best_bid=0.48,
            best_ask=0.52,
            bid_liquidity=1000.0,
            ask_liquidity=1000.0,
            total_volume=5000.0
        )
        
        # Calculate expected values
        expected_mid = (0.48 + 0.52) / 2  # = 0.50
        expected_spread = (0.52 - 0.48) / 0.50  # = 0.04 / 0.50 = 0.08 (8%)
        
        # Verify spread calculation
        assert market_data.mid_price == expected_mid
        assert abs(market_data.spread - expected_spread) < 0.0001
        assert abs(market_data.spread - 0.08) < 0.0001

    def test_spread_consistency_across_codebase(self):
        """Test that spread calculation matches the formula used in market_analysis.py."""
        # Same values as used in market_analysis.py: spread_pct = (spread_value / mid) * 100
        market_data = MarketData(
            market_id="test_market",
            token_id="test_token",
            best_bid=0.60,
            best_ask=0.65,
            bid_liquidity=1000.0,
            ask_liquidity=1000.0,
            total_volume=5000.0
        )
        
        # Manual calculation matching market_analysis.py formula
        spread_value = market_data.best_ask - market_data.best_bid  # 0.05
        mid = (market_data.best_bid + market_data.best_ask) / 2  # 0.625
        expected_spread_fraction = spread_value / mid  # 0.05 / 0.625 = 0.08
        expected_spread_pct = expected_spread_fraction * 100  # 8%
        
        # Verify the spread property matches
        assert abs(market_data.spread - expected_spread_fraction) < 0.0001
        assert abs(market_data.spread * 100 - expected_spread_pct) < 0.0001

    def test_spread_with_zero_mid_price(self):
        """Test that spread returns 1.0 when mid price is zero."""
        market_data = MarketData(
            market_id="test_market",
            token_id="test_token",
            best_bid=0.0,
            best_ask=0.0,
            bid_liquidity=0.0,
            ask_liquidity=0.0,
            total_volume=0.0
        )
        
        # Should return 1.0 to avoid division by zero
        assert market_data.spread == 1.0

    def test_spread_with_small_spread(self):
        """Test spread calculation with a tight spread."""
        market_data = MarketData(
            market_id="test_market",
            token_id="test_token",
            best_bid=0.495,
            best_ask=0.505,
            bid_liquidity=1000.0,
            ask_liquidity=1000.0,
            total_volume=5000.0
        )
        
        # Calculate expected values
        expected_mid = 0.5
        expected_spread = 0.01 / 0.5  # = 0.02 (2%)
        
        assert abs(market_data.spread - expected_spread) < 0.0001
        assert abs(market_data.spread - 0.02) < 0.0001

    def test_spread_with_wide_spread(self):
        """Test spread calculation with a wide spread."""
        market_data = MarketData(
            market_id="test_market",
            token_id="test_token",
            best_bid=0.30,
            best_ask=0.70,
            bid_liquidity=100.0,
            ask_liquidity=100.0,
            total_volume=500.0
        )
        
        # Calculate expected values
        expected_mid = 0.5
        expected_spread = 0.40 / 0.5  # = 0.8 (80%)
        
        assert abs(market_data.spread - expected_spread) < 0.0001
        assert abs(market_data.spread - 0.8) < 0.0001

    def test_spread_different_from_old_formula(self):
        """Test that new formula differs from old bid-based formula."""
        market_data = MarketData(
            market_id="test_market",
            token_id="test_token",
            best_bid=0.40,
            best_ask=0.60,
            bid_liquidity=1000.0,
            ask_liquidity=1000.0,
            total_volume=5000.0
        )
        
        # New formula (mid-based): (0.60 - 0.40) / 0.50 = 0.20 / 0.50 = 0.40 (40%)
        new_spread = market_data.spread
        
        # Old formula (bid-based): (0.60 - 0.40) / 0.40 = 0.20 / 0.40 = 0.50 (50%)
        old_spread = (market_data.best_ask - market_data.best_bid) / market_data.best_bid
        
        # They should be different
        assert abs(new_spread - 0.40) < 0.0001
        assert abs(old_spread - 0.50) < 0.0001
        assert new_spread != old_spread
        
        # New spread should be smaller than old spread when bid < mid
        assert new_spread < old_spread
