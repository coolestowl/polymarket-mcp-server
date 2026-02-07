#!/usr/bin/env python3
"""
Simple test script to verify the get_positions fix.
Tests that the method uses the Data API correctly.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock httpx for testing without real API call
import unittest.mock as mock


async def test_get_positions_structure():
    """Test that get_positions normalizes Data API response correctly."""
    from polymarket_mcp.auth.client import PolymarketClient
    
    # Create a mock client with minimal setup
    client = PolymarketClient(
        private_key="0" * 64,
        address="0x1234567890123456789012345678901234567890",
        chain_id=137
    )
    
    # Mock the HTTP response
    mock_response_data = [
        {
            'asset': 'test_asset_id_123',
            'conditionId': 'test_market_id_456',
            'size': 100.5,
            'avgPrice': 0.65,
            'title': 'Test Market'
        },
        {
            'asset': 'test_asset_id_789',
            'conditionId': 'test_market_id_012',
            'size': 50.0,
            'avgPrice': 0.45,
            'title': 'Another Test Market'
        }
    ]
    
    # Mock httpx.AsyncClient
    with mock.patch('httpx.AsyncClient') as mock_client:
        mock_response = mock.MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = mock.MagicMock()
        
        # Create async mock for the get method
        async def mock_get(*args, **kwargs):
            return mock_response
        
        mock_context = mock.MagicMock()
        mock_context.__aenter__ = mock.AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = mock.AsyncMock(return_value=None)
        mock_context.get = mock_get
        
        mock_client.return_value = mock_context
        
        # Call get_positions
        positions = await client.get_positions()
        
        # Verify response normalization
        assert len(positions) == 2
        
        # Check first position
        pos1 = positions[0]
        assert pos1['asset_id'] == 'test_asset_id_123'
        assert pos1['market'] == 'test_market_id_456'
        assert pos1['size'] == 100.5
        assert pos1['avg_price'] == 0.65
        assert pos1['current_price'] == 0.65  # Placeholder value
        assert pos1['unrealized_pnl'] == 0
        
        # Check second position
        pos2 = positions[1]
        assert pos2['asset_id'] == 'test_asset_id_789'
        assert pos2['market'] == 'test_market_id_012'
        assert pos2['size'] == 50.0
        assert pos2['avg_price'] == 0.45
        
        print("✅ All assertions passed!")
        print(f"✅ Response correctly normalized {len(positions)} positions")
        print(f"✅ Field mapping correct: asset -> asset_id, conditionId -> market, avgPrice -> avg_price")
        
        return True


async def test_get_positions_no_address():
    """Test that get_positions raises error when no address."""
    from polymarket_mcp.auth.client import PolymarketClient
    
    # Create client without address
    client = PolymarketClient(
        private_key="0" * 64,
        address="",  # Empty address
        chain_id=137
    )
    
    try:
        await client.get_positions()
        print("❌ Should have raised RuntimeError for missing address")
        return False
    except RuntimeError as e:
        if "address required" in str(e).lower():
            print("✅ Correctly raises error when address is missing")
            return True
        else:
            print(f"❌ Wrong error message: {e}")
            return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing get_positions() Data API implementation")
    print("=" * 60)
    print()
    
    print("Test 1: Response structure and field normalization")
    print("-" * 60)
    result1 = await test_get_positions_structure()
    print()
    
    print("Test 2: Error handling for missing address")
    print("-" * 60)
    result2 = await test_get_positions_no_address()
    print()
    
    print("=" * 60)
    if result1 and result2:
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
