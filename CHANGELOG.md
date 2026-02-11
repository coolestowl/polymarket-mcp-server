# Changelog

All notable changes to the Polymarket MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2025-01-10

### 🎉 Initial Public Release

The first public release of Polymarket MCP Server - a complete AI-powered trading platform for Polymarket prediction markets.

### Added

#### Core Infrastructure
- Model Context Protocol (MCP) server implementation
- L1 authentication (Polygon wallet + EIP-712 signing)
- L2 authentication (API key + HMAC signatures)
- Auto-creation of API credentials
- Advanced token bucket rate limiter respecting all Polymarket API limits
- Configurable safety limits and risk management system
- Comprehensive error handling and logging

#### Market Discovery Tools (8 tools)
- `search_markets` - Search markets by keywords, slug, or filters
- `get_trending_markets` - Get markets with highest volume
- `filter_markets_by_category` - Filter by tags and categories
- `get_event_markets` - Get all markets for a specific event
- `get_featured_markets` - Get featured/promoted markets
- `get_closing_soon_markets` - Get markets closing within timeframe
- `get_sports_markets` - Get sports betting markets
- `get_crypto_markets` - Get cryptocurrency prediction markets

#### Market Analysis Tools (10 tools)
- `get_market_details` - Complete market information
- `get_current_price` - Current bid/ask prices
- `get_orderbook` - Full orderbook with depth
- `get_spread` - Calculate current spread
- `get_market_volume` - Volume statistics (24h, 7d, 30d)
- `get_liquidity` - Available liquidity in USD
- `get_price_history` - Historical price data
- `get_market_holders` - Top position holders
- `compare_markets` - Compare multiple markets side-by-side

#### Trading Tools (10 tools)
- `create_limit_order` - Create limit orders (GTC/GTD/FOK/FAK)
- `create_market_order` - Execute market orders
- `create_batch_orders` - Submit multiple orders efficiently
- `get_order_status` - Check specific order status
- `get_open_orders` - List all active orders
- `get_order_history` - Historical order data
- `cancel_order` - Cancel specific order
- `cancel_market_orders` - Cancel all orders in a market
- `cancel_all_orders` - Emergency cancel all orders
- `rebalance_position` - Auto-adjust position to target size

#### Portfolio Management Tools (6 tools)
- `get_all_positions` - All user positions with filters
- `get_position_details` - Detailed position view
- `get_portfolio_value` - Total portfolio value calculation
- `get_pnl_summary` - Profit/loss overview
- `get_trade_history` - Historical trades with filters
- `get_activity_log` - On-chain activity tracking

#### Real-time Monitoring Tools (7 tools)
- `subscribe_market_prices` - Monitor price changes via WebSocket
- `subscribe_orderbook_updates` - Real-time orderbook updates
- `subscribe_user_orders` - User order status monitoring
- `subscribe_user_trades` - User trade execution alerts
- `subscribe_market_resolution` - Market resolution notifications
- `get_realtime_status` - WebSocket subscription status
- `unsubscribe_realtime` - Remove subscriptions

#### Safety & Risk Management
- Configurable order size limits
- Total portfolio exposure caps
- Per-market position limits
- Liquidity requirement validation
- Spread tolerance checks
- Confirmation thresholds for large orders
- Pre-trade safety validation

#### Infrastructure Features
- WebSocket manager with auto-reconnect
- Dual WebSocket connections (CLOB + Real-time)
- Token bucket rate limiting (all endpoint categories)
- HMAC authentication for WebSockets
- Event routing and notification system
- Subscription tracking and statistics

#### Testing
- Comprehensive test suite (1,900+ lines)
- Real API integration (NO MOCKS)
- Unit tests for all tools
- Integration tests for workflows
- Test runners and examples

#### Documentation
- Complete README with setup instructions
- Detailed SETUP_GUIDE.md
- Tools Reference (TOOLS_REFERENCE.md)
- Agent Integration Guide
- Trading Architecture documentation
- WebSocket Integration guide
- Usage examples and code samples
- CONTRIBUTING guidelines

### Technical Specifications

- **Python**: 3.10+
- **Total Lines of Code**: ~10,000+
- **Tools**: 45 comprehensive tools
- **API Integration**: CLOB API, Gamma API, Data API, WebSocket
- **Authentication**: L1 (EIP-712) + L2 (HMAC)
- **Rate Limiting**: Token bucket with exponential backoff
- **Dependencies**: MCP SDK, py-clob-client, websockets, eth-account, httpx, pydantic

### Credits

- **Created by**: Caio Vicentino
- **Communities**: Yield Hacker, Renda Cripto, Cultura Builder
- **Powered by**: Claude Code (Anthropic)

---

## [Unreleased]

### Planned Features
- CI/CD pipeline (GitHub Actions)
- Enhanced AI analysis tools
- Portfolio strategy templates
- Market alerts and notifications
- Performance analytics dashboard
- Multi-wallet support
- Advanced order types (trailing stop, OCO)
- Historical backtesting framework

---

## Release Notes Template

For future releases, use this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Deprecated
- Features that will be removed

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements
```

---

<div align="center">

**Maintained by Caio Vicentino and the Polymarket MCP community**

</div>
