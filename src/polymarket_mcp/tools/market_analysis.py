"""
Market Analysis Tools for Polymarket MCP Server.

Provides 8 tools for analyzing markets:
- get_market_details: Complete market information
- get_current_price: Current bid/ask prices
- get_orderbook: Complete order book
- get_spread: Current spread
- get_market_volume: Volume statistics
- get_liquidity: Available liquidity
- get_price_history: Historical price data
- compare_markets: Compare multiple markets
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import mcp.types as types
import httpx

from ..utils.http_client import async_client

logger = logging.getLogger(__name__)

# API URLs
GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_API_URL = "https://clob.polymarket.com"


# Data Models
class PriceData(BaseModel):
    """Price information for a token"""
    token_id: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    last: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrderBookEntry(BaseModel):
    """Single order book entry"""
    price: float
    size: float


class OrderBook(BaseModel):
    """Complete order book"""
    token_id: str
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VolumeData(BaseModel):
    """Volume statistics"""
    market_id: str
    volume_24h: Optional[float] = None
    volume_7d: Optional[float] = None
    volume_30d: Optional[float] = None
    volume_all_time: Optional[float] = None


class MarketOpportunity(BaseModel):
    """Market analysis and opportunity assessment"""
    market_id: str
    market_question: str
    current_price_yes: Optional[float] = None
    current_price_no: Optional[float] = None
    spread: Optional[float] = None
    spread_pct: Optional[float] = None
    volume_24h: Optional[float] = None
    liquidity_usd: Optional[float] = None
    price_trend_24h: Optional[str] = None  # "up", "down", "stable"
    risk_assessment: str  # "low", "medium", "high"
    recommendation: str  # "BUY", "SELL", "HOLD", "AVOID"
    confidence_score: float  # 0-100
    reasoning: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)


async def _fetch_gamma_api(endpoint: str, params: Optional[Dict] = None) -> Any:
    """Fetch from Gamma API"""
    try:
        async with async_client(timeout=30.0) as client:
            url = f"{GAMMA_API_URL}{endpoint}"
            response = await client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Gamma API error for {endpoint}: {e}")
        raise


async def _fetch_clob_api(endpoint: str, params: Optional[Dict] = None) -> Any:
    """Fetch from CLOB API (uses proxy due to IP restrictions)"""
    try:
        async with async_client(timeout=30.0, use_proxy=True) as client:
            url = f"{CLOB_API_URL}{endpoint}"
            response = await client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"CLOB API error for {endpoint}: {e}")
        raise


async def get_market_details(
    market_id: Optional[str] = None,
    condition_id: Optional[str] = None,
    slug: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get complete market information.

    Args:
        market_id: Market ID
        condition_id: Condition ID (alternative identifier)
        slug: Market slug (alternative identifier)

    Returns:
        Full market object with all metadata
    """
    try:
        # Convert numeric IDs to strings for API compatibility
        if market_id is not None:
            market_id = str(market_id)
        if condition_id is not None:
            condition_id = str(condition_id)

        # Determine which identifier to use
        if slug:
            data = await _fetch_gamma_api(f"/markets/slug/{slug}")
        elif condition_id:
            data = await _fetch_gamma_api("/markets", {"condition_ids": condition_id})
        elif market_id:
            data = await _fetch_gamma_api(f"/markets/{market_id}")
        else:
            raise ValueError("One of market_id, condition_id, or slug must be provided")

        # Handle list response
        if isinstance(data, list) and len(data) > 0:
            return data[0]

        return data

    except Exception as e:
        logger.error(f"Failed to get market details: {e}")
        raise


async def get_current_price(
    token_id: str,
    side: str = "BOTH"
) -> PriceData:
    """
    Get current bid/ask prices.

    Args:
        token_id: Token ID
        side: 'BUY', 'SELL', or 'BOTH' (default)

    Returns:
        PriceData object with bid, ask, and mid prices
    """
    try:
        price_data = PriceData(token_id=token_id)

        if side in ["BUY", "BOTH"]:
            buy_data = await _fetch_clob_api("/price", {"token_id": token_id, "side": "BUY"})
            price_data.bid = float(buy_data.get("price", 0))

        if side in ["SELL", "BOTH"]:
            sell_data = await _fetch_clob_api("/price", {"token_id": token_id, "side": "SELL"})
            price_data.ask = float(sell_data.get("price", 0))

        # Calculate mid price
        if price_data.bid is not None and price_data.ask is not None:
            price_data.mid = (price_data.bid + price_data.ask) / 2.0

        logger.info(f"Price for {token_id}: bid={price_data.bid}, ask={price_data.ask}")

        return price_data

    except Exception as e:
        logger.error(f"Failed to get current price: {e}")
        raise


async def get_orderbook(
    token_id: str,
    depth: int = 20
) -> OrderBook:
    """
    Get complete order book.

    Args:
        token_id: Token ID
        depth: Number of price levels to return per side (default 20)

    Returns:
        OrderBook with bids and asks
    """
    try:
        book_data = await _fetch_clob_api("/book", {"token_id": token_id})

        # Parse bids and asks
        bids = [
            OrderBookEntry(price=float(entry["price"]), size=float(entry["size"]))
            for entry in book_data.get("bids", [])[:depth]
        ]

        asks = [
            OrderBookEntry(price=float(entry["price"]), size=float(entry["size"]))
            for entry in book_data.get("asks", [])[:depth]
        ]

        orderbook = OrderBook(
            token_id=token_id,
            bids=bids,
            asks=asks
        )

        logger.info(f"Orderbook for {token_id}: {len(bids)} bids, {len(asks)} asks")

        return orderbook

    except Exception as e:
        logger.error(f"Failed to get orderbook: {e}")
        raise


async def get_spread(token_id: str) -> Dict[str, float]:
    """
    Get current spread.

    Args:
        token_id: Token ID

    Returns:
        Spread value and percentage
    """
    try:
        price_data = await get_current_price(token_id, "BOTH")

        if price_data.bid is None or price_data.ask is None:
            raise ValueError("Could not retrieve both bid and ask prices")

        spread_value = price_data.ask - price_data.bid
        spread_pct = (spread_value / price_data.mid) * 100 if price_data.mid else 0

        result = {
            "token_id": token_id,
            "spread_value": spread_value,
            "spread_percentage": spread_pct,
            "bid": price_data.bid,
            "ask": price_data.ask,
            "mid": price_data.mid
        }

        logger.info(f"Spread for {token_id}: {spread_value:.4f} ({spread_pct:.2f}%)")

        return result

    except Exception as e:
        logger.error(f"Failed to get spread: {e}")
        raise


async def get_market_volume(
    market_id,
    timeframes: Optional[List[str]] = None
) -> VolumeData:
    """
    Get volume statistics.

    Args:
        market_id: Market ID (string or integer)
        timeframes: List of timeframes (default: ['24h', '7d', '30d'])

    Returns:
        VolumeData with breakdown by timeframe
    """
    try:
        market_id = str(market_id)  # Convert to string for API compatibility
        if timeframes is None:
            timeframes = ['24h', '7d', '30d']

        # Get market details which include volume data
        market_data = await get_market_details(market_id=market_id)

        volume_data = VolumeData(market_id=market_id)

        # Extract volume for each timeframe
        volume_data.volume_24h = float(market_data.get("volume24hr", 0) or 0)
        volume_data.volume_7d = float(market_data.get("volume7d", 0) or 0)
        volume_data.volume_30d = float(market_data.get("volume30d", 0) or 0)
        volume_data.volume_all_time = float(market_data.get("volumeNum", 0) or 0)

        logger.info(f"Volume for {market_id}: 24h=${volume_data.volume_24h}")

        return volume_data

    except Exception as e:
        logger.error(f"Failed to get market volume: {e}")
        raise


async def get_liquidity(market_id) -> Dict[str, Any]:
    """
    Get available liquidity.

    Args:
        market_id: Market ID (string or integer)

    Returns:
        Total liquidity in USD
    """
    try:
        market_id = str(market_id)  # Convert to string for API compatibility
        market_data = await get_market_details(market_id=market_id)

        liquidity = float(market_data.get("liquidity", 0) or 0)

        result = {
            "market_id": market_id,
            "liquidity_usd": liquidity,
            "liquidity_formatted": f"${liquidity:,.2f}"
        }

        logger.info(f"Liquidity for {market_id}: ${liquidity:,.2f}")

        return result

    except Exception as e:
        logger.error(f"Failed to get liquidity: {e}")
        raise


async def get_price_history(
    token_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    interval: str = "1h",
    fidelity: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get historical price data from CLOB /prices-history endpoint.

    Args:
        token_id: CLOB token ID
        start_date: Start date (ISO format or unix timestamp)
        end_date: End date (ISO format or unix timestamp)
        interval: Duration string ('1m', '1h', '6h', '1d', '1w', 'max').
                  Mutually exclusive with start_date/end_date.
        fidelity: Data resolution in minutes (e.g., 60 for hourly)

    Returns:
        Price history data with timestamps and prices
    """
    try:
        params: Dict[str, Any] = {"market": token_id}

        # If start/end dates are provided, convert to unix timestamps
        if start_date or end_date:
            if start_date:
                if isinstance(start_date, str) and not start_date.isdigit():
                    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    params["startTs"] = int(start_dt.timestamp())
                else:
                    params["startTs"] = int(start_date)

            if end_date:
                if isinstance(end_date, str) and not end_date.isdigit():
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    params["endTs"] = int(end_dt.timestamp())
                else:
                    params["endTs"] = int(end_date)
        else:
            # Use interval if no explicit date range
            params["interval"] = interval

        if fidelity is not None:
            params["fidelity"] = fidelity

        data = await _fetch_clob_api("/prices-history", params)

        # Response format: {"history": [{"t": timestamp, "p": price}, ...]}
        history = data.get("history", [])

        result = [
            {"timestamp": entry["t"], "price": entry["p"]}
            for entry in history
        ]

        logger.info(f"Price history for {token_id}: {len(result)} data points")
        return result

    except Exception as e:
        logger.error(f"Failed to get price history: {e}")
        raise


async def get_market_holders(
    market_id: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get top position holders.

    Args:
        market_id: Market ID
        limit: Number of top holders to return (default 10)

    Returns:
        Top holders with positions
    """
    try:
        # Note: Position holder data requires authenticated access
        # and may not be publicly available for all users

        logger.warning(
            "Position holder data requires authenticated access and "
            "may not be publicly available"
        )

        return [{
            "error": "Position holder data not available via public API",
            "suggestion": "This data may require authenticated access with proper permissions"
        }]

    except Exception as e:
        logger.error(f"Failed to get market holders: {e}")
        raise


async def compare_markets(market_ids: List) -> List[Dict[str, Any]]:
    """
    Compare multiple markets.

    Args:
        market_ids: List of market IDs to compare (strings or integers)

    Returns:
        Comparison table with metrics for each market
    """
    try:
        # Convert all IDs to strings
        market_ids = [str(mid) for mid in market_ids]

        if len(market_ids) < 2:
            raise ValueError("At least 2 markets required for comparison")

        if len(market_ids) > 10:
            raise ValueError("Maximum 10 markets can be compared at once")

        comparisons = []

        for market_id in market_ids:
            try:
                # Get market details
                market = await get_market_details(market_id=market_id)
                volume = await get_market_volume(market_id)
                liquidity = await get_liquidity(market_id)

                # Compile comparison data
                comparison = {
                    "market_id": market_id,
                    "question": market.get("question", "Unknown"),
                    "volume_24h": volume.volume_24h,
                    "volume_7d": volume.volume_7d,
                    "liquidity_usd": liquidity.get("liquidity_usd"),
                    "end_date": market.get("endDate") or market.get("end_date_iso"),
                    "active": market.get("active", True),
                    "tags": market.get("tags", [])
                }

                comparisons.append(comparison)

            except Exception as market_error:
                logger.warning(f"Failed to fetch data for {market_id}: {market_error}")
                comparisons.append({
                    "market_id": market_id,
                    "error": str(market_error)
                })

        logger.info(f"Compared {len(comparisons)} markets")

        return comparisons

    except Exception as e:
        logger.error(f"Failed to compare markets: {e}")
        raise


# Tool definitions for MCP
def get_tools() -> List[types.Tool]:
    """Get list of market analysis tools"""
    return [
        types.Tool(
            name="get_market_details",
            description="Get complete market information including metadata, tokens, volume, and liquidity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {
                        "type": ["string", "integer"],
                        "description": "Market ID"
                    },
                    "condition_id": {
                        "type": "string",
                        "description": "Condition ID (alternative identifier)"
                    },
                    "slug": {
                        "type": "string",
                        "description": "Market slug (alternative identifier)"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_current_price",
            description="Get current bid/ask prices for a token. Returns PriceData with bid, ask, and mid prices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token_id": {
                        "type": "string",
                        "description": "Token ID"
                    },
                    "side": {
                        "type": "string",
                        "enum": ["BUY", "SELL", "BOTH"],
                        "description": "Price side to fetch (default: BOTH)",
                        "default": "BOTH"
                    }
                },
                "required": ["token_id"]
            }
        ),
        types.Tool(
            name="get_orderbook",
            description="Get complete order book with bids and asks arrays.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token_id": {
                        "type": "string",
                        "description": "Token ID"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Number of price levels per side (default 20)",
                        "default": 20
                    }
                },
                "required": ["token_id"]
            }
        ),
        types.Tool(
            name="get_spread",
            description="Get current spread (difference between bid and ask prices).",
            inputSchema={
                "type": "object",
                "properties": {
                    "token_id": {
                        "type": "string",
                        "description": "Token ID"
                    }
                },
                "required": ["token_id"]
            }
        ),
        types.Tool(
            name="get_market_volume",
            description="Get volume statistics for different timeframes (24h, 7d, 30d, all-time).",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {
                        "type": ["string", "integer"],
                        "description": "Market ID"
                    },
                    "timeframes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of timeframes (default: ['24h', '7d', '30d'])"
                    }
                },
                "required": ["market_id"]
            }
        ),
        types.Tool(
            name="get_liquidity",
            description="Get available liquidity in USD for a market.",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_id": {
                        "type": ["string", "integer"],
                        "description": "Market ID"
                    }
                },
                "required": ["market_id"]
            }
        ),
        types.Tool(
            name="get_price_history",
            description="Get historical price data from CLOB API. Use interval for relative time ranges, or start_date/end_date for absolute ranges.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token_id": {
                        "type": "string",
                        "description": "CLOB token ID"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (ISO format or unix timestamp). Mutually exclusive with interval."
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (ISO format or unix timestamp). Mutually exclusive with interval."
                    },
                    "interval": {
                        "type": "string",
                        "enum": ["1m", "1h", "6h", "1d", "1w", "max"],
                        "description": "Duration string (default: 1h). Mutually exclusive with start_date/end_date.",
                        "default": "1h"
                    },
                    "fidelity": {
                        "type": "integer",
                        "description": "Data resolution in minutes (e.g., 60 for hourly)"
                    }
                },
                "required": ["token_id"]
            }
        ),
        types.Tool(
            name="compare_markets",
            description="Compare multiple markets side-by-side with key metrics (volume, liquidity, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "market_ids": {
                        "type": "array",
                        "items": {"type": ["string", "integer"]},
                        "description": "List of market IDs to compare (2-10 markets)"
                    }
                },
                "required": ["market_ids"]
            }
        )
    ]


async def handle_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """
    Handle tool execution.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of TextContent with results
    """
    try:
        # Route to appropriate function
        if name == "get_market_details":
            result = await get_market_details(**arguments)
        elif name == "get_current_price":
            result = await get_current_price(**arguments)
            # Convert Pydantic model to dict
            result = result.model_dump(mode='json')
        elif name == "get_orderbook":
            result = await get_orderbook(**arguments)
            result = result.model_dump(mode='json')
        elif name == "get_spread":
            result = await get_spread(**arguments)
        elif name == "get_market_volume":
            result = await get_market_volume(**arguments)
            result = result.model_dump(mode='json')
        elif name == "get_liquidity":
            result = await get_liquidity(**arguments)
        elif name == "get_price_history":
            result = await get_price_history(**arguments)
        elif name == "compare_markets":
            result = await compare_markets(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Tool execution failed for {name}: {e}")
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(e)}, indent=2)
        )]
