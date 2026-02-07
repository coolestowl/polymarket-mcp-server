"""
Unit tests for API compliance fixes.

These tests verify parameter formatting without making actual API calls.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from polymarket_mcp.tools import market_discovery, market_analysis


class TestAPICompliance:
    """Test suite for API compliance fixes"""

    @pytest.mark.asyncio
    async def test_filter_markets_by_category_uses_array(self):
        """Test that tag_slug is sent as an array"""
        with patch('polymarket_mcp.tools.market_discovery._fetch_gamma_markets') as mock_fetch:
            mock_fetch.return_value = []
            
            await market_discovery.filter_markets_by_category(
                category="politics",
                active_only=True,
                limit=20
            )
            
            # Verify the call was made with tag_slug as an array
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            params = call_args[0][1]  # Second positional argument is params
            
            assert "tag_slug" in params
            assert isinstance(params["tag_slug"], list)
            assert params["tag_slug"] == ["politics"]
            assert params["closed"] == "false"

    @pytest.mark.asyncio
    async def test_get_sports_markets_uses_array(self):
        """Test that get_sports_markets sends tag_slug as an array"""
        with patch('polymarket_mcp.tools.market_discovery._fetch_gamma_markets') as mock_fetch:
            mock_fetch.return_value = []
            
            await market_discovery.get_sports_markets(limit=20)
            
            # Verify the call was made with tag_slug as an array
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            params = call_args[0][1]  # Second positional argument is params
            
            assert "tag_slug" in params
            assert isinstance(params["tag_slug"], list)
            assert params["tag_slug"] == ["sports"]
            assert params["closed"] == "false"

    @pytest.mark.asyncio
    async def test_get_crypto_markets_uses_array(self):
        """Test that get_crypto_markets sends tag_slug as an array"""
        with patch('polymarket_mcp.tools.market_discovery._fetch_gamma_markets') as mock_fetch:
            mock_fetch.return_value = []
            
            await market_discovery.get_crypto_markets(limit=20)
            
            # Verify the call was made with tag_slug as an array
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            params = call_args[0][1]  # Second positional argument is params
            
            assert "tag_slug" in params
            assert isinstance(params["tag_slug"], list)
            assert params["tag_slug"] == ["crypto"]
            assert params["closed"] == "false"

    @pytest.mark.asyncio
    async def test_get_featured_markets_uses_closed_parameter(self):
        """Test that get_featured_markets uses 'closed' instead of 'active' parameter"""
        with patch('polymarket_mcp.tools.market_discovery._fetch_gamma_markets') as mock_fetch:
            # Mock to return featured events so it doesn't fallback to trending markets
            mock_fetch.return_value = [
                {
                    "markets": [
                        {"id": "test1", "question": "Test market 1"}
                    ]
                }
            ]
            
            await market_discovery.get_featured_markets(limit=10)
            
            # Verify the first call was made with 'closed' parameter
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            params = call_args[0][1]  # Second positional argument is params
            
            assert "closed" in params
            assert params["closed"] == "false"
            assert "active" not in params  # Should NOT have 'active' parameter
            assert params["featured"] == "true"

    @pytest.mark.asyncio
    async def test_get_current_price_bid_ask_mapping(self):
        """Test that get_current_price correctly maps BUY to bid and SELL to ask"""
        with patch('polymarket_mcp.tools.market_analysis._fetch_clob_api') as mock_fetch:
            # Mock responses
            def side_effect(endpoint, params):
                if params.get("side") == "BUY":
                    return {"price": "0.65"}
                elif params.get("side") == "SELL":
                    return {"price": "0.70"}
                return {}
            
            mock_fetch.side_effect = side_effect
            
            # Test BOTH side
            result = await market_analysis.get_current_price(
                token_id="test_token",
                side="BOTH"
            )
            
            # BUY side should give bid price
            assert result.bid == 0.65, "BUY side should set bid price"
            # SELL side should give ask price
            assert result.ask == 0.70, "SELL side should set ask price"
            # Mid should be calculated correctly
            assert result.mid == (0.65 + 0.70) / 2.0

    @pytest.mark.asyncio
    async def test_get_current_price_buy_side_only(self):
        """Test that get_current_price with BUY side returns bid"""
        with patch('polymarket_mcp.tools.market_analysis._fetch_clob_api') as mock_fetch:
            mock_fetch.return_value = {"price": "0.65"}
            
            result = await market_analysis.get_current_price(
                token_id="test_token",
                side="BUY"
            )
            
            # BUY side should set bid price
            assert result.bid == 0.65, "BUY side should set bid price"
            assert result.ask is None, "SELL side was not requested"

    @pytest.mark.asyncio
    async def test_get_current_price_sell_side_only(self):
        """Test that get_current_price with SELL side returns ask"""
        with patch('polymarket_mcp.tools.market_analysis._fetch_clob_api') as mock_fetch:
            mock_fetch.return_value = {"price": "0.70"}
            
            result = await market_analysis.get_current_price(
                token_id="test_token",
                side="SELL"
            )
            
            # SELL side should set ask price
            assert result.ask == 0.70, "SELL side should set ask price"
            assert result.bid is None, "BUY side was not requested"

    @pytest.mark.asyncio
    async def test_get_closing_soon_markets_parameters(self):
        """Test that get_closing_soon_markets uses correct date parameters"""
        with patch('polymarket_mcp.tools.market_discovery._fetch_gamma_markets') as mock_fetch:
            mock_fetch.return_value = []
            
            await market_discovery.get_closing_soon_markets(hours=24, limit=20)
            
            # Verify the call was made with correct parameters
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            params = call_args[0][1]  # Second positional argument is params
            
            # Verify correct parameter names are used
            assert "closed" in params
            assert params["closed"] == "false"
            assert "end_date_min" in params
            assert "end_date_max" in params
            assert "order" in params
            assert params["order"] == "endDate"
            assert "ascending" in params
            assert params["ascending"] == "true"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
