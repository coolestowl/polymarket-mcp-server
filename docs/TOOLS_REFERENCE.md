# Polymarket MCP Server - Tools Reference

## Complete Tool Inventory (30 Tools)

### Phase 1: Trading Tools (12 tools) ✅
Previously implemented by other agents.

#### Order Creation (4 tools)
- `create_limit_order` - Create limit order with specified price
- `create_market_order` - Create market order at best price
- `create_batch_orders` - Create multiple orders in one transaction
- `suggest_order_price` - Get AI-suggested optimal order price

#### Order Management (6 tools)
- `get_order_status` - Get status of specific order
- `get_open_orders` - List all open orders
- `get_order_history` - Get order history with filters
- `cancel_order` - Cancel specific order by ID
- `cancel_market_orders` - Cancel all orders for a market
- `cancel_all_orders` - Cancel all open orders

#### Smart Trading (2 tools)
- `execute_smart_trade` - AI-optimized trade execution
- `rebalance_position` - Rebalance position to target allocation

---

### Phase 2: Market Discovery & Analysis (18 tools) ✅ NEW

#### Market Discovery (8 tools)

**1. search_markets**
```json
{
  "name": "search_markets",
  "parameters": {
    "query": "string (required)",
    "limit": "integer (default: 20)",
    "filters": "object (optional)"
  },
  "returns": "List[Market]"
}
```
Search markets by text query, slug, or keywords.

**2. get_trending_markets**
```json
{
  "name": "get_trending_markets",
  "parameters": {
    "timeframe": "enum['24h', '7d', '30d'] (default: '24h')",
    "limit": "integer (default: 10)"
  },
  "returns": "List[Market]"
}
```
Get markets with highest trading volume in specified timeframe.

**3. filter_markets_by_category**
```json
{
  "name": "filter_markets_by_category",
  "parameters": {
    "category": "string (required)",
    "active_only": "boolean (default: true)",
    "limit": "integer (default: 20)"
  },
  "returns": "List[Market]"
}
```
Filter markets by category/tag (e.g., "Politics", "Sports", "Crypto").

**4. get_event_markets**
```json
{
  "name": "get_event_markets",
  "parameters": {
    "event_slug": "string (optional)",
    "event_id": "string (optional)"
  },
  "returns": "List[Market]"
}
```
Get all markets for a specific event.

**5. get_featured_markets**
```json
{
  "name": "get_featured_markets",
  "parameters": {
    "limit": "integer (default: 10)"
  },
  "returns": "List[Market]"
}
```
Get featured/promoted markets.

**6. get_closing_soon_markets**
```json
{
  "name": "get_closing_soon_markets",
  "parameters": {
    "hours": "integer (default: 24)",
    "limit": "integer (default: 20)"
  },
  "returns": "List[Market]"
}
```
Get markets closing within specified timeframe.

**7. get_sports_markets**
```json
{
  "name": "get_sports_markets",
  "parameters": {
    "sport_type": "string (optional)",
    "limit": "integer (default: 20)"
  },
  "returns": "List[Market]"
}
```
Get sports betting markets. Filter by sport type if specified.

**8. get_crypto_markets**
```json
{
  "name": "get_crypto_markets",
  "parameters": {
    "symbol": "string (optional)",
    "limit": "integer (default: 20)"
  },
  "returns": "List[Market]"
}
```
Get cryptocurrency-related markets. Filter by symbol if specified.

---

#### Market Analysis (10 tools)

**1. get_market_details**
```json
{
  "name": "get_market_details",
  "parameters": {
    "market_id": "string (optional)",
    "condition_id": "string (optional)",
    "slug": "string (optional)"
  },
  "returns": "Market"
}
```
Get complete market information with all metadata.

**2. get_current_price**
```json
{
  "name": "get_current_price",
  "parameters": {
    "token_id": "string (required)",
    "side": "enum['BUY', 'SELL', 'BOTH'] (default: 'BOTH')"
  },
  "returns": "PriceData"
}
```
Get current bid/ask prices for a token.

**Response Schema (PriceData)**:
```json
{
  "token_id": "string",
  "bid": "float",
  "ask": "float",
  "mid": "float",
  "timestamp": "datetime"
}
```

**3. get_orderbook**
```json
{
  "name": "get_orderbook",
  "parameters": {
    "token_id": "string (required)",
    "depth": "integer (default: 20)"
  },
  "returns": "OrderBook"
}
```
Get complete order book with bids and asks.

**Response Schema (OrderBook)**:
```json
{
  "token_id": "string",
  "bids": [{"price": "float", "size": "float"}],
  "asks": [{"price": "float", "size": "float"}],
  "timestamp": "datetime"
}
```

**4. get_spread**
```json
{
  "name": "get_spread",
  "parameters": {
    "token_id": "string (required)"
  },
  "returns": "SpreadData"
}
```
Get current spread (bid-ask difference).

**Response Schema**:
```json
{
  "token_id": "string",
  "spread_value": "float",
  "spread_percentage": "float",
  "bid": "float",
  "ask": "float",
  "mid": "float"
}
```

**5. get_market_volume**
```json
{
  "name": "get_market_volume",
  "parameters": {
    "market_id": "string (required)",
    "timeframes": "List[string] (default: ['24h', '7d', '30d'])"
  },
  "returns": "VolumeData"
}
```
Get volume statistics for different timeframes.

**Response Schema (VolumeData)**:
```json
{
  "market_id": "string",
  "volume_24h": "float",
  "volume_7d": "float",
  "volume_30d": "float",
  "volume_all_time": "float"
}
```

**6. get_liquidity**
```json
{
  "name": "get_liquidity",
  "parameters": {
    "market_id": "string (required)"
  },
  "returns": "LiquidityData"
}
```
Get available liquidity in USD.

**Response Schema**:
```json
{
  "market_id": "string",
  "liquidity_usd": "float",
  "liquidity_formatted": "string"
}
```

**7. get_price_history**
```json
{
  "name": "get_price_history",
  "parameters": {
    "token_id": "string (required)",
    "start_date": "string (optional)",
    "end_date": "string (optional)",
    "resolution": "enum['1m', '5m', '1h', '1d'] (default: '1h')"
  },
  "returns": "List[OHLC]"
}
```
Get historical price data. **Note**: Limited availability via public API.

**8. get_market_holders**
```json
{
  "name": "get_market_holders",
  "parameters": {
    "market_id": "string (required)",
    "limit": "integer (default: 10)"
  },
  "returns": "List[Holder]"
}
```
Get top position holders. **Note**: Requires authenticated access.

**9. analyze_market_opportunity** 🤖 AI-Powered
```json
{
  "name": "analyze_market_opportunity",
  "parameters": {
    "market_id": "string (required)"
  },
  "returns": "MarketOpportunity"
}
```
AI-powered comprehensive market analysis with trading recommendation.

**Response Schema (MarketOpportunity)**:
```json
{
  "market_id": "string",
  "market_question": "string",
  "current_price_yes": "float",
  "current_price_no": "float",
  "spread": "float",
  "spread_pct": "float",
  "volume_24h": "float",
  "liquidity_usd": "float",
  "price_trend_24h": "enum['up', 'down', 'stable']",
  "risk_assessment": "enum['low', 'medium', 'high']",
  "recommendation": "enum['BUY', 'SELL', 'HOLD', 'AVOID']",
  "confidence_score": "float (0-100)",
  "reasoning": "string",
  "last_updated": "datetime"
}
```

**10. compare_markets**
```json
{
  "name": "compare_markets",
  "parameters": {
    "market_ids": "List[string] (required, 2-10 markets)"
  },
  "returns": "List[MarketComparison]"
}
```
Compare multiple markets side-by-side.

**Response Schema (MarketComparison)**:
```json
{
  "market_id": "string",
  "question": "string",
  "volume_24h": "float",
  "volume_7d": "float",
  "liquidity_usd": "float",
  "end_date": "string",
  "active": "boolean",
  "tags": "List[string]"
}
```

---

## Usage Workflows

### Workflow 1: Find Trading Opportunities
```
1. search_markets(query="crypto") or get_trending_markets()
2. For each market:
   - get_market_details()
   - get_current_price()
   - get_market_volume()
   - analyze_market_opportunity()
3. Filter by recommendation == "BUY" and confidence > 70
4. execute_smart_trade() (trading tool)
```

### Workflow 2: Market Analysis
```
1. get_market_details(market_id)
2. get_current_price(token_id)
3. get_orderbook(token_id)
4. get_spread(token_id)
5. get_liquidity(market_id)
6. analyze_market_opportunity(market_id)
```

### Workflow 3: Market Comparison
```
1. filter_markets_by_category(category="Politics")
2. Extract top 5 market_ids
3. compare_markets(market_ids)
4. Sort by liquidity or volume
5. Select best market for trading
```

### Workflow 4: Monitor Closing Markets
```
1. get_closing_soon_markets(hours=24)
2. For each market:
   - analyze_market_opportunity()
   - Check if current position exists
   - Decide to enter/exit before closing
```

---

## API Rate Limits

| Endpoint Category | Rate Limit | Tools Using It |
|-------------------|------------|----------------|
| `GAMMA_API` | 750/10s | All discovery tools |
| `MARKET_DATA` | 200/10s | get_current_price, get_orderbook, get_spread |
| `CLOB_GENERAL` | 5000/10s | get_market_details |
| `TRADING_BURST` | 2400/10s | Trading tools |

**Rate Limiter**: Token bucket algorithm with automatic backoff on 429 errors.

---

## Error Handling

All tools return consistent error format:
```json
{
  "error": "Error message",
  "tool": "tool_name",
  "arguments": {...}
}
```

Common errors:
- `Market not found` - Invalid market_id
- `Token not found` - Invalid token_id
- `Rate limit exceeded` - Too many requests
- `API error` - Polymarket API issues
- `Invalid parameters` - Missing/invalid arguments

---

## Best Practices

1. **Rate Limiting**: Don't make more than recommended requests
2. **Error Handling**: Always check for error field in response
3. **Market Selection**: Use analyze_market_opportunity for decision making
4. **Liquidity Check**: Verify liquidity > $10k before trading
5. **Spread Check**: Avoid markets with spread > 5%
6. **Volume Check**: Prefer markets with volume_24h > $1k

---

## Quick Reference

### Get Started Fast
```python
# 1. Find trending market
markets = await get_trending_markets(limit=1)
market_id = markets[0]["id"]

# 2. Analyze opportunity
analysis = await analyze_market_opportunity(market_id)

# 3. If good opportunity, get details for trading
if analysis.recommendation == "BUY":
    details = await get_market_details(market_id=market_id)
    token_id = details["tokens"][0]["token_id"]
    price = await get_current_price(token_id)
    # Use trading tools to execute
```

### Common Queries
- Find Trump markets: `search_markets("Trump")`
- Top volume today: `get_trending_markets("24h")`
- Politics markets: `filter_markets_by_category("Politics")`
- BTC markets: `get_crypto_markets(symbol="BTC")`
- NFL markets: `get_sports_markets(sport_type="NFL")`
- Closing today: `get_closing_soon_markets(hours=24)`

---

**Total Tools**: 30 (12 trading + 18 market)
**Status**: Production Ready ✅
**API**: Real Polymarket integration (NO MOCKS)
**Tests**: Comprehensive coverage
