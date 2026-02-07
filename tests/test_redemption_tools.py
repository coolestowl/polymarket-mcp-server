"""
Tests for redemption tools.

Tests all 4 redemption tools.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from polymarket_mcp.tools.redemption import (
    get_closed_positions,
    get_redeemable_positions,
    redeem_winning_positions,
    redeem_all_winning_positions,
    REDEMPTION_TOOLS
)
from polymarket_mcp.config import PolymarketConfig
from polymarket_mcp.utils.rate_limiter import RateLimiter, EndpointCategory


@pytest.fixture
def mock_config():
    """Create mock configuration"""
    config = MagicMock(spec=PolymarketConfig)
    config.POLYGON_ADDRESS = "0x1234567890123456789012345678901234567890"
    config.POLYGON_PRIVATE_KEY = "0x" + "1" * 64
    config.POLYMARKET_CHAIN_ID = 137
    config.CLOB_API_URL = "https://clob.polymarket.com"
    return config


@pytest.fixture
def mock_rate_limiter():
    """Create mock rate limiter"""
    limiter = AsyncMock(spec=RateLimiter)
    limiter.acquire = AsyncMock(return_value=0.0)
    return limiter


@pytest.fixture
def mock_polymarket_client():
    """Create mock Polymarket client"""
    client = AsyncMock()
    return client


class TestToolDefinitions:
    """Test tool definitions and structure"""

    def test_tool_count(self):
        """Verify 4 tools are defined"""
        assert len(REDEMPTION_TOOLS) == 4

    def test_tool_names(self):
        """Verify tool names"""
        expected_names = [
            'get_closed_positions',
            'get_redeemable_positions',
            'redeem_winning_positions',
            'redeem_all_winning_positions'
        ]
        tool_names = [tool['name'] for tool in REDEMPTION_TOOLS]
        assert tool_names == expected_names

    def test_tool_handlers(self):
        """Verify all tools have handlers"""
        for tool in REDEMPTION_TOOLS:
            assert 'handler' in tool
            assert callable(tool['handler'])

    def test_tool_input_schemas(self):
        """Verify all tools have input schemas"""
        for tool in REDEMPTION_TOOLS:
            assert 'inputSchema' in tool
            assert 'type' in tool['inputSchema']
            assert tool['inputSchema']['type'] == 'object'


class TestGetClosedPositions:
    """Test get_closed_positions tool"""

    @pytest.mark.asyncio
    async def test_get_closed_positions_no_positions(
        self,
        mock_polymarket_client,
        mock_rate_limiter,
        mock_config
    ):
        """Test with no closed positions"""
        with patch('httpx.AsyncClient') as mock_client_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=[])
            mock_response.raise_for_status = MagicMock()
            
            # Create mock client that properly handles async context manager
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_closed_positions(
                mock_polymarket_client,
                mock_rate_limiter,
                mock_config,
                limit=100
            )

            assert len(result) == 1
            assert "No closed positions found" in result[0].text

    @pytest.mark.asyncio
    async def test_get_closed_positions_with_data(
        self,
        mock_polymarket_client,
        mock_rate_limiter,
        mock_config
    ):
        """Test with closed positions data"""
        mock_positions = [
            {
                "conditionId": "0xabc123",
                "title": "Test Market",
                "outcome": "Yes",
                "size": "100",
                "avgPrice": "0.55",
                "redeemable": True,
                "payout": "100",
                "asset": "token_123"
            }
        ]

        with patch('httpx.AsyncClient') as mock_client_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_positions)
            mock_response.raise_for_status = MagicMock()
            
            # Create mock client that properly handles async context manager
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_closed_positions(
                mock_polymarket_client,
                mock_rate_limiter,
                mock_config,
                limit=100
            )

            assert len(result) == 1
            import json
            data = json.loads(result[0].text)
            assert data["success"] is True
            assert data["total_positions"] == 1
            assert len(data["positions"]) == 1
            assert data["positions"][0]["condition_id"] == "0xabc123"
            assert data["positions"][0]["redeemable"] is True


class TestGetRedeemablePositions:
    """Test get_redeemable_positions tool"""

    @pytest.mark.asyncio
    async def test_get_redeemable_positions_none(
        self,
        mock_polymarket_client,
        mock_rate_limiter,
        mock_config
    ):
        """Test with no redeemable positions"""
        mock_positions = [
            {
                "conditionId": "0xabc123",
                "title": "Test Market",
                "outcome": "Yes",
                "size": "100",
                "avgPrice": "0.55",
                "redeemable": False,  # Not redeemable
                "payout": "0",
                "asset": "token_123"
            }
        ]

        with patch('httpx.AsyncClient') as mock_client_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_positions)
            mock_response.raise_for_status = MagicMock()
            
            # Create mock client that properly handles async context manager
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_redeemable_positions(
                mock_polymarket_client,
                mock_rate_limiter,
                mock_config
            )

            assert len(result) == 1
            assert "No redeemable positions found" in result[0].text

    @pytest.mark.asyncio
    async def test_get_redeemable_positions_with_data(
        self,
        mock_polymarket_client,
        mock_rate_limiter,
        mock_config
    ):
        """Test with redeemable positions"""
        mock_positions = [
            {
                "conditionId": "0xabc123",
                "title": "Test Market Yes",
                "outcome": "Yes",
                "size": "100",
                "avgPrice": "0.55",
                "redeemable": True,
                "payout": "100",
                "asset": "token_123"
            },
            {
                "conditionId": "0xdef456",
                "title": "Test Market No",
                "outcome": "No",
                "size": "50",
                "avgPrice": "0.45",
                "redeemable": True,
                "payout": "50",
                "asset": "token_456"
            }
        ]

        with patch('httpx.AsyncClient') as mock_client_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_positions)
            mock_response.raise_for_status = MagicMock()
            
            # Create mock client that properly handles async context manager
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await get_redeemable_positions(
                mock_polymarket_client,
                mock_rate_limiter,
                mock_config
            )

            assert len(result) == 1
            import json
            data = json.loads(result[0].text)
            assert data["success"] is True
            assert data["total_redeemable"] == 2
            assert data["total_payout_usdc"] == 150.0
            assert len(data["positions"]) == 2
            # Check Yes outcome gets index_set 1
            assert data["positions"][0]["index_set"] == 1
            # Check No outcome gets index_set 2
            assert data["positions"][1]["index_set"] == 2


class TestRedeemWinningPositions:
    """Test redeem_winning_positions tool"""

    @pytest.mark.asyncio
    async def test_redeem_winning_positions_structure(
        self,
        mock_polymarket_client,
        mock_rate_limiter,
        mock_config
    ):
        """Test that redemption function has correct structure (mock web3)"""
        with patch('polymarket_mcp.tools.redemption.Web3') as mock_web3_class:
            # Mock Web3 instance
            mock_web3 = MagicMock()
            mock_web3.is_connected.return_value = True
            mock_web3.eth.get_transaction_count.return_value = 0
            mock_web3.eth.gas_price = 30000000000
            
            # Mock transaction hash
            mock_tx_hash = MagicMock()
            mock_tx_hash.hex.return_value = "0x123abc"
            mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash
            
            # Mock contract
            mock_contract = MagicMock()
            mock_function = MagicMock()
            mock_function.build_transaction.return_value = {
                'from': mock_config.POLYGON_ADDRESS,
                'nonce': 0,
                'gas': 200000,
                'gasPrice': 30000000000,
                'chainId': 137
            }
            mock_contract.functions.redeemPositions.return_value = mock_function
            mock_web3.eth.contract.return_value = mock_contract
            
            # Mock Account
            with patch('polymarket_mcp.tools.redemption.Account') as mock_account_class:
                mock_account = MagicMock()
                mock_account.address = mock_config.POLYGON_ADDRESS
                mock_signed_tx = MagicMock()
                mock_signed_tx.rawTransaction = b'signed_tx_data'
                mock_account.sign_transaction.return_value = mock_signed_tx
                mock_account_class.from_key.return_value = mock_account
                
                mock_web3_class.return_value = mock_web3
                
                result = await redeem_winning_positions(
                    mock_polymarket_client,
                    mock_rate_limiter,
                    mock_config,
                    condition_id="0xabc123",
                    index_sets=[1]
                )

                assert len(result) == 1
                import json
                data = json.loads(result[0].text)
                assert data["success"] is True
                assert "transaction_hash" in data
                assert data["condition_id"] == "0xabc123"
                assert data["index_sets"] == [1]


class TestRedeemAllWinningPositions:
    """Test redeem_all_winning_positions tool"""

    @pytest.mark.asyncio
    async def test_redeem_all_dry_run(
        self,
        mock_polymarket_client,
        mock_rate_limiter,
        mock_config
    ):
        """Test dry run mode"""
        mock_positions = [
            {
                "conditionId": "0xabc123",
                "title": "Test Market",
                "outcome": "Yes",
                "size": "100",
                "avgPrice": "0.55",
                "redeemable": True,
                "payout": "100",
                "asset": "token_123"
            }
        ]

        with patch('httpx.AsyncClient') as mock_client_class:
            # Create mock response
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_positions)
            mock_response.raise_for_status = MagicMock()
            
            # Create mock client that properly handles async context manager
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await redeem_all_winning_positions(
                mock_polymarket_client,
                mock_rate_limiter,
                mock_config,
                dry_run=True
            )

            assert len(result) == 1
            import json
            data = json.loads(result[0].text)
            assert data["success"] is True
            assert data["dry_run"] is True
            assert data["total_positions"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
