"""
Trading tools for Polymarket MCP server.
Implements 12 comprehensive tools for order management and smart trading.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import mcp.types as types

from ..config import PolymarketConfig
from ..auth import PolymarketClient
from ..utils import (
    SafetyLimits,
    OrderRequest,
    Position,
    MarketData,
)

logger = logging.getLogger(__name__)


def _parse_orderbook(orderbook) -> dict:
    """
    Parse orderbook data whether it's a dict or SDK object.

    Args:
        orderbook: Either a dict or SDK OrderBookSummary object from get_orderbook()

    Returns:
        dict: Normalized orderbook dict with 'bids' and 'asks' keys,
              where each entry is a dict with 'price' and 'size' keys
    """
    if isinstance(orderbook, dict):
        return orderbook
    # Handle SDK OrderBookSummary object
    return {
        'bids': getattr(orderbook, 'bids', []) or [],
        'asks': getattr(orderbook, 'asks', []) or [],
    }


def _get_price_from_entry(entry) -> float:
    """
    Extract price from an orderbook entry, handling both dict and object formats.

    Args:
        entry: Either a dict with 'price' key or an object with price attribute

    Returns:
        float: The price value
    """
    if isinstance(entry, dict):
        return float(entry.get('price', 0))
    return float(getattr(entry, 'price', 0))


def _get_size_from_entry(entry) -> float:
    """
    Extract size from an orderbook entry, handling both dict and object formats.

    Args:
        entry: Either a dict with 'size' key or an object with size attribute

    Returns:
        float: The size value
    """
    if isinstance(entry, dict):
        return float(entry.get('size', 0))
    return float(getattr(entry, 'size', 0))


class TradingTools:
    """
    Trading tools for Polymarket.

    Provides 12 tools organized into three categories:
    - Order Creation (4 tools)
    - Order Management (6 tools)
    - Smart Trading (2 tools)
    """

    def __init__(
        self,
        client: PolymarketClient,
        safety_limits: SafetyLimits,
        config: PolymarketConfig
    ):
        self.client = client
        self.safety_limits = safety_limits
        self.config = config

    # ========== ORDER CREATION TOOLS ==========

    async def create_limit_order(
        self,
        condition_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "GTC",
        expiration: Optional[int] = None,
        token_id: Optional[str] = None,
        outcome: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a limit order on Polymarket.

        Args:
            condition_id: Market condition ID (hex string, e.g., '0x...')
            side: 'BUY' or 'SELL'
            price: Limit price (0.00-1.00)
            size: Order size in USD
            order_type: 'GTC'|'GTD'|'FOK'|'FAK' (default 'GTC')
            expiration: Unix timestamp for GTD orders (optional)
            token_id: Specific token ID to trade (optional, for multi-outcome markets)
            outcome: Outcome name/index for multi-outcome markets (optional, alternative to token_id)

        Returns:
            Dict with order ID, status, and details

        Raises:
            ValueError: If safety checks fail or invalid parameters
        """
        try:
            # Rate limit check
            
            # Validate parameters
            if not 0 < price <= 1.0:
                raise ValueError(f"Price must be between 0 and 1, got {price}")

            if size <= 0:
                raise ValueError(f"Size must be positive, got {size}")

            side = side.upper()
            if side not in ['BUY', 'SELL']:
                raise ValueError(f"Side must be BUY or SELL, got {side}")

            order_type = order_type.upper()
            if order_type not in ['GTC', 'GTD', 'FOK', 'FAK']:
                raise ValueError(f"Invalid order type: {order_type}")

            if order_type == 'GTD' and not expiration:
                raise ValueError("GTD orders require expiration timestamp")

            # Get market data
            logger.info(f"Fetching market data for {condition_id}")
            market = await self.client.get_market(condition_id)

            # Get token ID with proper selection for binary and multi-outcome markets
            tokens = market.get('tokens', [])
            if not tokens:
                raise ValueError(f"No tokens found for market {condition_id}")

            # If token_id not explicitly provided, select based on market type and outcome
            if not token_id:
                token_id = self._select_token_id(tokens, side, outcome)

            # Validate token_id exists in market
            if not any(t.get('token_id') == token_id for t in tokens):
                raise ValueError(f"Token ID {token_id} not found in market {condition_id}")

            # Get orderbook for validation
            orderbook = await self.client.get_orderbook(token_id)

            # Parse orderbook data
            parsed_orderbook = _parse_orderbook(orderbook)
            bids = parsed_orderbook.get('bids', [])
            asks = parsed_orderbook.get('asks', [])

            # Note: Polymarket orderbook returns bids in ascending order and asks in descending order
            # Best bid is the highest bid (last in list), best ask is the lowest ask (last in list)
            best_bid = _get_price_from_entry(bids[-1]) if bids else 0.0
            best_ask = _get_price_from_entry(asks[-1]) if asks else 1.0

            # Calculate liquidity
            bid_liquidity = sum(_get_price_from_entry(b) * _get_size_from_entry(b) for b in bids[:10])
            ask_liquidity = sum(_get_price_from_entry(a) * _get_size_from_entry(a) for a in asks[:10])

            # Get tick size and validate price
            tick_size = self.client.get_tick_size(token_id)
            price = self._round_to_tick_size(price, tick_size)

            market_data = MarketData(
                market_id=condition_id,
                token_id=token_id,
                best_bid=best_bid,
                best_ask=best_ask,
                bid_liquidity=bid_liquidity,
                ask_liquidity=ask_liquidity,
                total_volume=float(market.get('volume', 0))
            )

            # Get current positions
            positions_data = await self.client.get_positions()
            positions = self._convert_positions(positions_data)

            # Convert size from USD to shares using best available price
            # BUY: use best_ask to calculate shares (what we'd pay at market)
            # SELL: use best_bid to calculate shares (what we'd receive at market)
            if side == 'BUY':
                reference_price = best_ask if best_ask > 0 else price
            else:
                reference_price = best_bid if best_bid > 0 else price

            # Round size_in_shares to 2 decimal places
            # Polymarket API requires: maker_amount max 2 decimals, taker_amount max 4 decimals
            # For simplicity, we use 2 decimals for shares which satisfies both constraints
            size_in_shares = round(size / reference_price, 2)

            # Create order request for validation
            order_request = OrderRequest(
                token_id=token_id,
                price=price,
                size=size_in_shares,
                side=side,
                market_id=condition_id
            )

            # Safety validation
            is_valid, error_msg = self.safety_limits.validate_order(
                order_request,
                positions,
                market_data
            )

            if not is_valid:
                raise ValueError(f"Safety check failed: {error_msg}")

            # Check if confirmation required
            if self.safety_limits.should_require_confirmation(
                order_request,
                self.config.ENABLE_AUTONOMOUS_TRADING
            ):
                logger.warning(
                    f"Order requires confirmation: ${size:.2f} exceeds threshold "
                    f"${self.config.REQUIRE_CONFIRMATION_ABOVE_USD:.2f}"
                )
                # In autonomous mode, we proceed with logging
                # In interactive mode, this would prompt the user

            # Post order
            logger.info(
                f"Posting limit order: {side} {size_in_shares:.2f} shares @ {price} "
                f"({order_type}), reference_price={reference_price}"
            )

            order_response = await self.client.post_order(
                token_id=token_id,
                price=price,
                size=size_in_shares,
                side=side,
                order_type=order_type,
                expiration=expiration
            )

            result = {
                "success": True,
                "order_id": order_response.get('orderID'),
                "status": order_response.get('status', 'submitted'),
                "details": {
                    "condition_id": condition_id,
                    "token_id": token_id,
                    "side": side,
                    "price": price,
                    "reference_price": reference_price,
                    "size_shares": size_in_shares,
                    "size_usd": size,
                    "order_type": order_type,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                "order_response": order_response
            }

            logger.info(f"Order created successfully: {result['order_id']}")
            return result

        except Exception as e:
            logger.error(f"Failed to create limit order: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {
                    "condition_id": condition_id,
                    "side": side,
                    "price": price,
                    "size_usd": size
                }
            }

    async def create_market_order(
        self,
        condition_id: str,
        side: str,
        size: float,
        token_id: Optional[str] = None,
        outcome: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute market order at best available price (FOK).

        Uses extreme prices (0.99 for BUY, 0.01 for SELL) to ensure immediate
        execution at the best available market price. The FOK order type
        guarantees either full execution or complete cancellation.

        Args:
            condition_id: Market condition ID (hex string, e.g., '0x...')
            side: 'BUY' or 'SELL'
            size: Order size in USD
            token_id: Specific token ID to trade (optional)
            outcome: Outcome name/index for multi-outcome markets (optional)

        Returns:
            Dict with execution details
        """
        try:
            side_upper = side.upper()
            # Use extreme prices to ensure immediate execution
            # Actual execution will be at best available price
            price = 0.99 if side_upper == 'BUY' else 0.01

            logger.info(
                f"Executing market order: {side} ${size} @ market price (FAK)"
            )

            # Use FAK (Fill-And-Kill) for market orders
            # FAK fills as much as possible immediately and cancels the rest
            result = await self.create_limit_order(
                condition_id=condition_id,
                side=side,
                price=price,
                size=size,
                order_type='FAK',
                token_id=token_id,
                outcome=outcome
            )

            result['execution_type'] = 'market_order'

            return result

        except Exception as e:
            logger.error(f"Failed to create market order: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_type": "market_order",
                "details": {
                    "condition_id": condition_id,
                    "side": side,
                    "size_usd": size
                }
            }

    async def create_batch_orders(
        self,
        orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Submit multiple orders in batch.

        Args:
            orders: List of order objects with fields:
                - condition_id (str): Market condition ID
                - side (str)
                - price (float)
                - size (float)
                - order_type (str, optional)
                - expiration (int, optional)

        Returns:
            Dict with results for each order
        """
        try:

            results = []
            successful = 0
            failed = 0

            logger.info(f"Processing batch of {len(orders)} orders")

            # Process orders sequentially (could be parallelized with care)
            for idx, order in enumerate(orders):
                try:
                    result = await self.create_limit_order(
                        condition_id=order['condition_id'],
                        side=order['side'],
                        price=order['price'],
                        size=order['size'],
                        order_type=order.get('order_type', 'GTC'),
                        expiration=order.get('expiration')
                    )

                    results.append({
                        "index": idx,
                        "success": result.get('success', False),
                        "order_id": result.get('order_id'),
                        "details": result.get('details', {})
                    })

                    if result.get('success'):
                        successful += 1
                    else:
                        failed += 1

                except Exception as e:
                    logger.error(f"Order {idx} failed: {e}")
                    results.append({
                        "index": idx,
                        "success": False,
                        "error": str(e),
                        "details": order
                    })
                    failed += 1

            return {
                "success": True,
                "total_orders": len(orders),
                "successful": successful,
                "failed": failed,
                "results": results
            }

        except Exception as e:
            logger.error(f"Batch order processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_orders": len(orders)
            }

    # ========== ORDER MANAGEMENT TOOLS ==========

    async def get_order_status(
        self,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Check status of a specific order.

        Uses the SDK's get_order method for direct lookup instead of
        fetching all orders and filtering.

        Args:
            order_id: Order ID to check

        Returns:
            Dict with order details and fill status
        """
        try:
            # Use direct order lookup via SDK
            order = await self.client.get_order(order_id)

            if not order:
                return {
                    "success": False,
                    "error": f"Order {order_id} not found",
                    "order_id": order_id
                }

            # Handle both dict and object response formats
            if isinstance(order, dict):
                filled_amount = float(order.get('sizeMatched', 0))
                total_amount = float(order.get('originalSize', order.get('size', 0)))
                status = order.get('status', 'unknown')
                details = order
            else:
                filled_amount = float(getattr(order, 'sizeMatched', 0) or 0)
                total_amount = float(getattr(order, 'originalSize', 0) or getattr(order, 'size', 0) or 0)
                status = getattr(order, 'status', 'unknown')
                # Convert object to dict for details
                details = {
                    'id': getattr(order, 'id', None) or getattr(order, 'orderID', None),
                    'status': status,
                    'price': getattr(order, 'price', None),
                    'size': getattr(order, 'size', None),
                    'sizeMatched': getattr(order, 'sizeMatched', None),
                    'side': getattr(order, 'side', None),
                    'token_id': getattr(order, 'token_id', None) or getattr(order, 'asset_id', None),
                }

            fill_percentage = (filled_amount / total_amount * 100) if total_amount > 0 else 0

            return {
                "success": True,
                "order_id": order_id,
                "status": status,
                "fill_status": {
                    "filled": filled_amount,
                    "total": total_amount,
                    "remaining": total_amount - filled_amount,
                    "fill_percentage": fill_percentage
                },
                "details": details
            }

        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return {
                "success": False,
                "error": str(e),
                "order_id": order_id
            }

    async def get_open_orders(
        self,
        condition_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all active/open orders.

        Args:
            condition_id: Optional market condition ID filter

        Returns:
            Dict with list of open orders
        """
        try:

            orders = await self.client.get_orders(market=condition_id)

            # Filter for open orders only (status can be uppercase or lowercase)
            open_orders = [
                order for order in orders
                if order.get('status', '').upper() in ['OPEN', 'LIVE', 'PENDING']
            ]

            # Organize by market
            by_market = {}
            for order in open_orders:
                market = order.get('market', 'unknown')
                if market not in by_market:
                    by_market[market] = []
                by_market[market].append(order)

            return {
                "success": True,
                "total_open_orders": len(open_orders),
                "markets": len(by_market),
                "orders": open_orders,
                "by_market": by_market
            }

        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_order_history(
        self,
        condition_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get historical orders.

        Args:
            condition_id: Optional market condition ID filter
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum number of orders (default 100)

        Returns:
            Dict with order history
        """
        try:

            orders = await self.client.get_orders(market=condition_id)

            # Filter by date if provided
            if start_date or end_date:
                filtered_orders = []
                start_dt = datetime.fromisoformat(start_date) if start_date else None
                end_dt = datetime.fromisoformat(end_date) if end_date else None

                for order in orders:
                    order_time_str = order.get('timestamp') or order.get('created_at')
                    if order_time_str:
                        try:
                            order_time = datetime.fromisoformat(order_time_str.replace('Z', '+00:00'))
                            if start_dt and order_time < start_dt:
                                continue
                            if end_dt and order_time > end_dt:
                                continue
                            filtered_orders.append(order)
                        except:
                            filtered_orders.append(order)

                orders = filtered_orders

            # Apply limit
            orders = orders[:limit]

            # Calculate statistics
            total_volume = sum(
                float(o.get('size', 0)) * float(o.get('price', 0))
                for o in orders
            )

            filled_orders = [o for o in orders if o.get('status') == 'filled']
            cancelled_orders = [o for o in orders if o.get('status') == 'cancelled']

            return {
                "success": True,
                "total_orders": len(orders),
                "filled": len(filled_orders),
                "cancelled": len(cancelled_orders),
                "total_volume_usd": total_volume,
                "orders": orders
            }

        except Exception as e:
            logger.error(f"Failed to get order history: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def cancel_order(
        self,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Cancel a specific order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Dict with cancellation confirmation
        """
        try:
            
            response = await self.client.cancel_order(order_id)

            return {
                "success": True,
                "order_id": order_id,
                "cancelled": True,
                "response": response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "order_id": order_id
            }

    async def cancel_market_orders(
        self,
        condition_id: str,
        asset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel all orders in a specific market.

        Uses the SDK's cancel_market_orders method for efficient batch cancellation.

        Args:
            condition_id: Market condition ID (hex string, e.g., '0x...')
            asset_id: Optional asset/token filter

        Returns:
            Dict with cancellation result
        """
        try:
            # Use SDK's batch cancel method for efficiency
            response = await self.client.cancel_market_orders(
                market=condition_id,
                asset_id=asset_id or ""
            )

            # Parse response to get count
            cancelled_count = 0
            if isinstance(response, dict):
                cancelled_count = len(response.get('canceled', response.get('cancelled', [])))
            elif isinstance(response, list):
                cancelled_count = len(response)

            return {
                "success": True,
                "condition_id": condition_id,
                "asset_id": asset_id,
                "cancelled_count": cancelled_count,
                "response": response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to cancel market orders: {e}")
            return {
                "success": False,
                "error": str(e),
                "condition_id": condition_id
            }

    async def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all open orders across all markets.

        Returns:
            Dict with count of cancelled orders
        """
        try:
            
            response = await self.client.cancel_all_orders()

            # Count cancelled orders
            cancelled_count = 0
            if isinstance(response, dict):
                cancelled_count = len(response.get('cancelled', []))
            elif isinstance(response, list):
                cancelled_count = len(response)

            return {
                "success": True,
                "cancelled_count": cancelled_count,
                "response": response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def rebalance_position(
        self,
        condition_id: str,
        target_size: Optional[float] = None,
        max_slippage: float = 0.02,
        token_id: Optional[str] = None,
        outcome: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adjust position to target size (or close if target_size is None).

        Args:
            condition_id: Market condition ID (hex string, e.g., '0x...')
            target_size: Target position size in USD (None to close)
            max_slippage: Maximum acceptable slippage (default 2%)
            token_id: Specific token ID (optional)
            outcome: Outcome for multi-outcome markets (optional)

        Returns:
            Dict with rebalance summary
        """
        try:
            logger.info(f"Rebalancing position in market {condition_id} to target ${target_size}")

            # Get current position
            positions_data = await self.client.get_positions()

            current_size = 0.0
            current_position = None

            for pos in positions_data:
                if pos.get('market') == condition_id or pos.get('condition_id') == condition_id:
                    current_size += float(pos.get('size', 0)) * float(pos.get('price', 0))
                    current_position = pos

            if target_size is None:
                target_size = 0.0

            # Calculate required adjustment
            adjustment = target_size - current_size

            if abs(adjustment) < 1.0:  # Less than $1 difference
                return {
                    "success": True,
                    "message": "Position already at target",
                    "current_size": current_size,
                    "target_size": target_size,
                    "adjustment_needed": adjustment
                }

            # Determine side and size
            if adjustment > 0:
                # Need to buy more
                side = 'BUY'
                size = abs(adjustment)
            else:
                # Need to sell
                side = 'SELL'
                size = abs(adjustment)

            # Get market data for slippage check
            market = await self.client.get_market(condition_id)
            tokens = market.get('tokens', [])
            if not tokens:
                raise ValueError(f"No tokens found for market {condition_id}")

            # Select token ID if not provided
            if not token_id:
                token_id = self._select_token_id(tokens, side, outcome)

            orderbook = await self.client.get_orderbook(token_id)

            parsed_orderbook = _parse_orderbook(orderbook)
            bids = parsed_orderbook.get('bids', [])
            asks = parsed_orderbook.get('asks', [])

            # Note: Polymarket orderbook returns bids ascending, asks descending
            # Best bid is last in bids list, best ask is last in asks list
            best_bid = _get_price_from_entry(bids[-1]) if bids else 0.0
            best_ask = _get_price_from_entry(asks[-1]) if asks else 1.0
            mid_price = (best_bid + best_ask) / 2

            # Calculate expected execution price
            if side == 'BUY':
                expected_price = best_ask
                max_price = mid_price * (1 + max_slippage)
                if expected_price > max_price:
                    raise ValueError(
                        f"Slippage too high: expected {expected_price:.4f} > "
                        f"max {max_price:.4f}"
                    )
            else:
                expected_price = best_bid
                min_price = mid_price * (1 - max_slippage)
                if expected_price < min_price:
                    raise ValueError(
                        f"Slippage too high: expected {expected_price:.4f} < "
                        f"min {min_price:.4f}"
                    )

            # Execute rebalancing order
            logger.info(f"Rebalancing: {side} ${size} @ ~{expected_price:.4f}")

            result = await self.create_limit_order(
                condition_id=condition_id,
                side=side,
                price=expected_price,
                size=size,
                order_type='GTC'
            )

            return {
                "success": result.get('success', False),
                "rebalance_summary": {
                    "current_size": current_size,
                    "target_size": target_size,
                    "adjustment": adjustment,
                    "side": side,
                    "size": size,
                    "execution_price": expected_price,
                    "mid_price": mid_price,
                    "slippage": abs(expected_price - mid_price) / mid_price
                },
                "order_result": result
            }

        except Exception as e:
            logger.error(f"Position rebalancing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "condition_id": condition_id,
                "target_size": target_size
            }

    # ========== HELPER METHODS ==========

    def _round_to_tick_size(self, price: float, tick_size: str) -> float:
        """
        Round price to the nearest valid tick size.

        Args:
            price: The price to round
            tick_size: Tick size as string (e.g., "0.01", "0.001", "0.0001")

        Returns:
            Price rounded to the nearest tick size
        """
        try:
            tick = float(tick_size)
            if tick <= 0:
                return price
            # Round to nearest tick
            rounded = round(price / tick) * tick
            # Ensure within valid range
            rounded = max(0.01, min(0.99, rounded))
            # Format to avoid floating point precision issues
            decimals = len(tick_size.split('.')[-1]) if '.' in tick_size else 2
            return round(rounded, decimals)
        except (ValueError, TypeError):
            logger.warning(f"Invalid tick size {tick_size}, returning original price")
            return price

    def _select_token_id(
        self,
        tokens: List[Dict[str, Any]],
        side: str,
        outcome: Optional[str] = None
    ) -> str:
        """
        Select appropriate token ID based on market type and trading intent.

        Supports:
        - Binary markets (YES/NO): Automatically selects based on side
        - Multi-outcome markets: Selects based on outcome parameter or first token

        Args:
            tokens: List of token dictionaries from market data
            side: 'BUY' or 'SELL'
            outcome: Optional outcome identifier (name, index, or token_id)

        Returns:
            Selected token_id

        Raises:
            ValueError: If outcome not found in multi-outcome market
        """
        side_upper = side.upper()

        # Binary market (2 tokens): YES and NO
        if len(tokens) == 2:
            # For binary markets:
            # - BUY side typically means buying YES (index 0)
            # - SELL side typically means selling YES (or buying NO)
            # Token order: [YES, NO] or based on outcome field

            if outcome:
                # Try to match by outcome name/id
                for token in tokens:
                    if (str(outcome).lower() in str(token.get('outcome', '')).lower() or
                        str(outcome) == token.get('token_id')):
                        return token['token_id']
                raise ValueError(f"Outcome '{outcome}' not found in binary market tokens")

            # Default: BUY = YES token (index 0), SELL = NO token (index 1)
            # This assumes standard binary market structure
            if side_upper == 'BUY':
                # For BUY, default to YES outcome (typically index 0)
                return tokens[0]['token_id']
            else:
                # For SELL, default to NO outcome (typically index 1)
                return tokens[1]['token_id'] if len(tokens) > 1 else tokens[0]['token_id']

        # Multi-outcome market (>2 tokens)
        elif len(tokens) > 2:
            if not outcome:
                raise ValueError(
                    f"Multi-outcome market with {len(tokens)} outcomes requires 'outcome' parameter. "
                    f"Available outcomes: {[t.get('outcome', t.get('token_id')) for t in tokens]}"
                )

            # Try to match outcome by various methods
            # 1. Try exact token_id match
            for token in tokens:
                if outcome == token.get('token_id'):
                    return token['token_id']

            # 2. Try outcome name match (case-insensitive)
            outcome_lower = str(outcome).lower()
            for token in tokens:
                if outcome_lower in str(token.get('outcome', '')).lower():
                    return token['token_id']

            # 3. Try index match (0-based)
            try:
                outcome_idx = int(outcome)
                if 0 <= outcome_idx < len(tokens):
                    return tokens[outcome_idx]['token_id']
            except (ValueError, TypeError):
                pass

            # No match found
            available = [f"{i}: {t.get('outcome', t.get('token_id'))}" for i, t in enumerate(tokens)]
            raise ValueError(
                f"Outcome '{outcome}' not found in multi-outcome market. "
                f"Available: {', '.join(available)}"
            )

        # Single token market (uncommon)
        else:
            return tokens[0]['token_id']

    def _convert_positions(
        self,
        positions_data: List[Dict[str, Any]]
    ) -> List[Position]:
        """Convert raw position data to Position objects."""
        positions = []

        for pos_data in positions_data:
            try:
                position = Position(
                    token_id=pos_data.get('asset_id', ''),
                    market_id=pos_data.get('market', ''),
                    size=float(pos_data.get('size', 0)),
                    avg_price=float(pos_data.get('avg_price', 0)),
                    current_price=float(pos_data.get('current_price', pos_data.get('avg_price', 0))),
                    unrealized_pnl=float(pos_data.get('unrealized_pnl', 0))
                )
                positions.append(position)
            except Exception as e:
                logger.warning(f"Failed to convert position: {e}")
                continue

        return positions


def get_tool_definitions() -> List[types.Tool]:
    """
    Get MCP tool definitions for all trading tools.

    Returns:
        List of Tool definitions
    """
    return [
        # Order Creation Tools
        types.Tool(
            name="create_limit_order",
            description=(
                "Create a limit order on Polymarket. "
                "Validates order against safety limits before execution. "
                "Supports GTC, GTD, FOK, and FAK order types. "
                "For binary markets (YES/NO), side determines token automatically. "
                "For multi-outcome markets, specify 'outcome' parameter."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {
                        "type": "string",
                        "description": "Market condition ID (hex string from CLOB API, e.g., '0x...')"
                    },
                    "side": {
                        "type": "string",
                        "enum": ["BUY", "SELL"],
                        "description": "Order side"
                    },
                    "price": {
                        "type": "number",
                        "minimum": 0.01,
                        "maximum": 0.99,
                        "description": "Limit price (0.01-0.99)"
                    },
                    "size": {
                        "type": "number",
                        "minimum": 1,
                        "description": "Order size in USD"
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["GTC", "GTD", "FOK", "FAK"],
                        "default": "GTC",
                        "description": "Order type"
                    },
                    "expiration": {
                        "type": "integer",
                        "description": "Unix timestamp for GTD orders (optional)"
                    },
                    "token_id": {
                        "type": "string",
                        "description": "Specific token ID to trade (optional, for advanced use)"
                    },
                    "outcome": {
                        "type": "string",
                        "description": "Outcome name/index for multi-outcome markets (required for >2 outcomes, e.g., 'Candidate A', '0', '1')"
                    }
                },
                "required": ["condition_id", "side", "price", "size"]
            }
        ),
        types.Tool(
            name="create_market_order",
            description=(
                "Execute market order at best available price using FOK. "
                "Provides immediate execution at current market price. "
                "For binary markets, side determines token. For multi-outcome markets, specify outcome."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {
                        "type": "string",
                        "description": "Market condition ID (hex string from CLOB API, e.g., '0x...')"
                    },
                    "side": {
                        "type": "string",
                        "enum": ["BUY", "SELL"],
                        "description": "Order side"
                    },
                    "size": {
                        "type": "number",
                        "minimum": 1,
                        "description": "Order size in USD"
                    },
                    "token_id": {
                        "type": "string",
                        "description": "Specific token ID to trade (optional)"
                    },
                    "outcome": {
                        "type": "string",
                        "description": "Outcome name/index for multi-outcome markets (optional)"
                    }
                },
                "required": ["condition_id", "side", "size"]
            }
        ),
        types.Tool(
            name="create_batch_orders",
            description=(
                "Submit multiple orders in batch. "
                "Each order is validated against safety limits. "
                "Returns results for each individual order."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "orders": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "condition_id": {"type": "string", "description": "Market condition ID"},
                                "side": {"type": "string", "enum": ["BUY", "SELL"]},
                                "price": {"type": "number"},
                                "size": {"type": "number"},
                                "order_type": {"type": "string"},
                                "expiration": {"type": "integer"}
                            },
                            "required": ["condition_id", "side", "price", "size"]
                        },
                        "description": "List of orders to submit"
                    }
                },
                "required": ["orders"]
            }
        ),

        # Order Management Tools
        types.Tool(
            name="get_order_status",
            description="Check status and fill details of a specific order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order ID to check"
                    }
                },
                "required": ["order_id"]
            }
        ),
        types.Tool(
            name="get_open_orders",
            description="Get all active/open orders, optionally filtered by market condition ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {
                        "type": "string",
                        "description": "Optional market condition ID filter"
                    }
                }
            }
        ),
        types.Tool(
            name="get_order_history",
            description="Get historical orders with optional filters for market and date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {
                        "type": "string",
                        "description": "Optional market condition ID filter"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (ISO format)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (ISO format)"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "Maximum number of orders"
                    }
                }
            }
        ),
        types.Tool(
            name="cancel_order",
            description="Cancel a specific open order by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order ID to cancel"
                    }
                },
                "required": ["order_id"]
            }
        ),
        types.Tool(
            name="cancel_market_orders",
            description="Cancel all open orders in a specific market.",
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {
                        "type": "string",
                        "description": "Market condition ID (hex string from CLOB API)"
                    },
                    "asset_id": {
                        "type": "string",
                        "description": "Optional asset/token filter"
                    }
                },
                "required": ["condition_id"]
            }
        ),
        types.Tool(
            name="cancel_all_orders",
            description="Cancel all open orders across all markets. Use with caution.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # Position Rebalancing Tool
        types.Tool(
            name="rebalance_position",
            description=(
                "Adjust position to target size or close position entirely. "
                "Automatically calculates required trades and validates slippage."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {
                        "type": "string",
                        "description": "Market condition ID (hex string from CLOB API)"
                    },
                    "target_size": {
                        "type": "number",
                        "description": "Target position size in USD (null to close)"
                    },
                    "max_slippage": {
                        "type": "number",
                        "default": 0.02,
                        "description": "Maximum acceptable slippage (0.02 = 2%)"
                    }
                },
                "required": ["condition_id"]
            }
        ),
    ]
