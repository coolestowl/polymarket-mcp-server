"""
Polymarket CLOB client with authentication.
Handles L1 (private key) and L2 (API key) authentication.

Signature Types:
- EOA (0): Standard Externally Owned Account signatures (supported)
- POLY_PROXY (1): Email/Magic wallet signatures (not supported)
- POLY_GNOSIS_SAFE (2): Browser wallet proxy signatures (not supported)

This client only supports EOA (signature_type=0) for simplicity.
"""
from typing import Dict, Any, List, Optional
import logging
import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.constants import POLYGON

from .signer import OrderSigner
from ..utils.http_client import async_client

logger = logging.getLogger(__name__)

# Signature type for EOA (Externally Owned Account)
SIGNATURE_TYPE_EOA = 0


class PolymarketClient:
    """
    Authenticated client for Polymarket CLOB API.

    Features:
    - L1 authentication with private key signing
    - L2 authentication with API key HMAC
    - Auto-creation of API credentials if not provided
    - Comprehensive market and trading operations
    """

    def __init__(
        self,
        private_key: str,
        address: str,
        chain_id: int = 137,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        host: str = "https://clob.polymarket.com",
    ):
        """
        Initialize Polymarket client.

        Args:
            private_key: Polygon wallet private key
            address: Polygon wallet address
            chain_id: Chain ID (137 for mainnet, 80002 for Amoy testnet)
            api_key: Optional L2 API key
            api_secret: Optional L2 API secret (same as passphrase)
            passphrase: Optional L2 API passphrase
            host: CLOB API host URL
        """
        self.private_key = private_key
        self.address = address.lower()
        self.chain_id = chain_id
        self.host = host

        # Initialize order signer
        self.signer = OrderSigner(private_key, chain_id)

        # L2 API credentials
        self.api_creds: Optional[ApiCreds] = None
        if api_key and api_secret and passphrase:
            self.api_creds = ApiCreds(
                api_key=api_key,
                api_secret=api_secret,
                api_passphrase=passphrase
            )

        # Initialize CLOB client
        self.client: Optional[ClobClient] = None
        self._initialize_client()

        logger.info(
            f"PolymarketClient initialized for {self.address} "
            f"(chain_id: {chain_id}, L2 auth: {self.api_creds is not None})"
        )

    def _initialize_client(self) -> None:
        """Initialize the ClobClient with appropriate authentication (EOA only)"""
        try:
            # Build client arguments
            client_args = {
                "host": self.host,
                "chain_id": self.chain_id,
                "key": self.private_key,
                "signature_type": SIGNATURE_TYPE_EOA,  # EOA signatures only
            }

            # Add L2 credentials if available
            if self.api_creds:
                client_args["creds"] = self.api_creds

            # Create client
            self.client = ClobClient(**client_args)

            logger.info("ClobClient initialized successfully (signature_type=EOA)")

        except Exception as e:
            logger.error(f"Failed to initialize ClobClient: {e}")
            raise

    def get_client(self) -> ClobClient:
        """
        Get the underlying ClobClient instance.

        Returns:
            ClobClient instance

        Raises:
            RuntimeError: If client not initialized
        """
        if not self.client:
            raise RuntimeError("ClobClient not initialized")
        return self.client

    async def create_api_credentials(self, nonce_timeout: int = 3600) -> ApiCreds:
        """
        Create L2 API credentials for this wallet.

        This is required for authenticated operations like posting orders.
        The credentials are created once and can be reused.

        Args:
            nonce_timeout: Nonce timeout in seconds (default: 1 hour)

        Returns:
            ApiCreds object with api_key, api_secret, api_passphrase

        Raises:
            Exception: If credential creation fails
        """
        try:
            logger.info("Creating API credentials...")

            # Use the client's built-in method to create or derive credentials
            creds = self.client.create_or_derive_api_creds(nonce=0)

            # Store credentials
            self.api_creds = ApiCreds(
                api_key=creds.api_key,
                api_secret=creds.api_secret,
                api_passphrase=creds.api_passphrase
            )

            # Reinitialize client with new credentials
            self._initialize_client()

            logger.info(f"API credentials created: {creds.api_key[:8]}...")
            return self.api_creds

        except Exception as e:
            logger.error(f"Failed to create API credentials: {e}")
            raise

    async def get_markets(
        self,
        next_cursor: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Fetch markets from Polymarket.

        Args:
            next_cursor: Pagination cursor (passed to CLOB client)
            limit: Number of markets to fetch (max 100)

        Returns:
            Dictionary with markets data
        """
        try:
            # Note: CLOB client's get_markets still uses next_cursor internally
            markets = self.client.get_markets(next_cursor=next_cursor)
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            raise

    async def get_market(self, condition_id: str) -> Dict[str, Any]:
        """
        Fetch single market by condition ID.

        Args:
            condition_id: Market condition ID

        Returns:
            Market data dictionary
        """
        try:
            market = self.client.get_market(condition_id)
            return market

        except Exception as e:
            logger.error(f"Failed to fetch market {condition_id}: {e}")
            raise

    async def get_orderbook(
        self,
        token_id: str
    ) -> Dict[str, Any]:
        """
        Fetch order book for a token.

        Args:
            token_id: Token ID to fetch orderbook for

        Returns:
            Order book with bids and asks
        """
        try:
            orderbook = self.client.get_order_book(token_id)
            return orderbook

        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {token_id}: {e}")
            raise

    async def get_price(
        self,
        token_id: str,
        side: str
    ) -> float:
        """
        Get current price for a token.

        Args:
            token_id: Token ID
            side: BUY or SELL

        Returns:
            Price as float
        """
        try:
            price_data = self.client.get_price(token_id, side.upper())
            return float(price_data.get("price", 0))

        except Exception as e:
            logger.error(f"Failed to fetch price for {token_id}: {e}")
            raise

    async def post_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str = "GTC",
        expiration: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Post a limit order.

        Args:
            token_id: Token ID to trade
            price: Limit price (0-1 for probabilities)
            size: Order size in shares
            side: BUY or SELL
            order_type: Order type (GTC, FOK, GTD)
            expiration: Order expiration timestamp (required for GTD)

        Returns:
            Order response dictionary

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError(
                "L2 API credentials required for posting orders. "
                "Call create_api_credentials() first."
            )

        try:
            # Build order args (order_type is NOT part of OrderArgs)
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side.upper(),
            )

            if expiration:
                order_args.expiration = expiration

            # Create the signed order first
            signed_order = self.client.create_order(order_args)

            # Map order_type string to OrderType enum
            order_type_enum = OrderType.GTC  # default
            if order_type:
                order_type_upper = order_type.upper()
                if order_type_upper == "FOK":
                    order_type_enum = OrderType.FOK
                elif order_type_upper == "GTD":
                    order_type_enum = OrderType.GTD
                elif order_type_upper in ("FAK", "IOC"):
                    # FAK is also known as IOC (Immediate-Or-Cancel)
                    order_type_enum = OrderType.FOK  # Use FOK as closest equivalent

            # Post the signed order with order type
            order_response = self.client.post_order(signed_order, order_type_enum)

            # Convert OrderSummary object to dictionary if needed
            if not isinstance(order_response, dict):
                # Get order ID - try 'id' first, then fall back to 'orderID'
                order_id_value = getattr(order_response, 'id', None)
                if order_id_value is None:
                    order_id_value = getattr(order_response, 'orderID', None)
                
                order_response = {
                    'orderID': order_id_value,
                    'status': getattr(order_response, 'status', 'submitted'),
                    'success': getattr(order_response, 'success', True),
                }

            logger.info(
                f"Order posted: {side} {size} @ {price} "
                f"(token: {token_id}, order_id: {order_response.get('orderID')})"
            )

            return order_response

        except Exception as e:
            logger.error(f"Failed to post order: {e}")
            raise

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an open order.

        Args:
            order_id: ID of order to cancel

        Returns:
            Cancellation response

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError("L2 API credentials required for canceling orders")

        try:
            response = self.client.cancel(order_id)

            logger.info(f"Order cancelled: {order_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    async def cancel_orders(self, order_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel multiple orders by IDs.

        Args:
            order_ids: List of order IDs to cancel

        Returns:
            Cancellation response

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError("L2 API credentials required for canceling orders")

        try:
            response = self.client.cancel_orders(order_ids)

            logger.info(f"Cancelled {len(order_ids)} orders")
            return response

        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")
            raise

    async def cancel_market_orders(
        self,
        market: str = "",
        asset_id: str = ""
    ) -> Dict[str, Any]:
        """
        Cancel all orders for a specific market or asset.

        Uses the official SDK's cancel_market_orders method for efficiency.

        Args:
            market: Market condition ID (optional)
            asset_id: Asset/token ID (optional)

        Returns:
            Cancellation response

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError("L2 API credentials required")

        try:
            response = self.client.cancel_market_orders(market=market, asset_id=asset_id)

            logger.info(f"Cancelled orders for market={market}, asset_id={asset_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to cancel market orders: {e}")
            raise

    async def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all open orders.

        Returns:
            Cancellation response

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError("L2 API credentials required")

        try:
            response = self.client.cancel_all()

            logger.info("All orders cancelled")
            return response

        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            raise

    async def get_orders(
        self,
        market: Optional[str] = None,
        asset_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's open orders.

        Args:
            market: Filter by market ID
            asset_id: Filter by asset ID

        Returns:
            List of open orders

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError("L2 API credentials required")

        try:
            # Build params
            params = {}
            if market:
                params["market"] = market
            if asset_id:
                params["asset_id"] = asset_id

            orders = self.client.get_orders(**params)
            return orders

        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            raise

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get a specific order by ID.

        Uses the official SDK's get_order method for direct lookup.

        Args:
            order_id: Order ID to fetch

        Returns:
            Order details dictionary

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError("L2 API credentials required")

        try:
            order = self.client.get_order(order_id)
            return order

        except Exception as e:
            logger.error(f"Failed to fetch order {order_id}: {e}")
            raise

    def get_tick_size(self, token_id: str) -> str:
        """
        Get the tick size (minimum price increment) for a token.

        Args:
            token_id: Token ID

        Returns:
            Tick size as string (e.g., "0.01", "0.001", "0.0001")
        """
        try:
            tick_size = self.client.get_tick_size(token_id)
            return str(tick_size)

        except Exception as e:
            logger.error(f"Failed to get tick size for {token_id}: {e}")
            # Default to 0.01 if unable to fetch
            return "0.01"

    def get_neg_risk(self, token_id: str) -> bool:
        """
        Check if a token/market uses the NegRisk CTF adapter.

        Args:
            token_id: Token ID

        Returns:
            True if market uses neg-risk CTF, False otherwise
        """
        try:
            return self.client.get_neg_risk(token_id)

        except Exception as e:
            logger.error(f"Failed to get neg_risk for {token_id}: {e}")
            # Default to False if unable to fetch
            return False

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get user's positions via Polymarket Data API.

        Returns:
            List of positions with normalized field names

        Raises:
            RuntimeError: If address not available
        """
        if not self.address:
            raise RuntimeError("Polygon address required")

        try:
            async with async_client(timeout=10.0) as http_client:
                # Data API requires lowercase address
                response = await http_client.get(
                    "https://data-api.polymarket.com/positions",
                    params={"user": self.address.lower()},
                )
                response.raise_for_status()
                positions_data = response.json()
            
            # Normalize field names to match expected format
            normalized_positions = []
            for pos in positions_data:
                normalized_pos = {
                    'asset_id': pos.get('asset', ''),
                    'market': pos.get('conditionId', ''),
                    'size': pos.get('size', 0),
                    'avg_price': pos.get('avgPrice', 0),
                    # NOTE: current_price set to avg_price as approximation since Data API doesn't provide it.
                    # For precise calculations, current price should be fetched from orderbook separately.
                    'current_price': pos.get('avgPrice', 0),
                    # NOTE: unrealized_pnl set to 0 as placeholder. Will be calculated if needed based on
                    # current_price - avg_price. The Data API doesn't provide this directly.
                    'unrealized_pnl': 0
                }
                normalized_positions.append(normalized_pos)
            
            return normalized_positions

        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            raise

    async def get_balance(self) -> Dict[str, float]:
        """
        Get user's USDC balance.

        Returns:
            Dictionary with balance info

        Raises:
            RuntimeError: If L2 credentials not available
        """
        if not self.api_creds:
            raise RuntimeError("L2 API credentials required")

        try:
            balance_data = self.client.get_balance(self.address)
            return balance_data

        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise

    def has_api_credentials(self) -> bool:
        """Check if L2 API credentials are available"""
        return self.api_creds is not None

    def get_address(self) -> str:
        """Get wallet address"""
        return self.address

    def get_chain_id(self) -> int:
        """Get chain ID"""
        return self.chain_id


def create_polymarket_client(
    private_key: str,
    address: str,
    chain_id: int = 137,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    passphrase: Optional[str] = None,
) -> PolymarketClient:
    """
    Create PolymarketClient instance.

    Args:
        private_key: Polygon wallet private key
        address: Polygon wallet address
        chain_id: Chain ID (default: 137)
        api_key: Optional L2 API key
        api_secret: Optional L2 API secret
        passphrase: Optional L2 API passphrase

    Returns:
        PolymarketClient instance
    """
    return PolymarketClient(
        private_key=private_key,
        address=address,
        chain_id=chain_id,
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase
    )
