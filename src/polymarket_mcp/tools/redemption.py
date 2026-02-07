"""
Redemption Tools for Polymarket MCP Server.

Provides tools for:
- Querying closed/resolved positions from the Data API
- Identifying redeemable positions (winning positions)
- Redeeming winning outcome tokens via CTF contract
- Batch redemption of all winning positions

Reference: https://docs.polymarket.com/developers/CTF/redeem
"""
import logging
import json
from typing import Dict, Any, List, Optional
import httpx
from web3 import Web3
from eth_account import Account

import mcp.types as types

from ..contracts.ctf_abi import CTF_ABI, CTF_ADDRESS, USDC_ADDRESS

logger = logging.getLogger(__name__)

# Polygon RPC endpoint
POLYGON_RPC = "https://polygon-rpc.com"


async def get_closed_positions(
    polymarket_client,
    rate_limiter,
    config,
    limit: int = 100
) -> List[types.TextContent]:
    """
    Get all closed/resolved positions for the user.

    Args:
        polymarket_client: PolymarketClient instance
        rate_limiter: RateLimiter instance
        config: PolymarketConfig instance
        limit: Maximum positions to return (default: 100)

    Returns:
        List with formatted closed position data
    """
    try:
        from ..utils.rate_limiter import EndpointCategory

        # Rate limit for data API
        await rate_limiter.acquire(EndpointCategory.DATA_API)

        # Fetch closed positions from Data API
        async with httpx.AsyncClient() as client:
            params = {
                "user": config.POLYGON_ADDRESS.lower()
            }

            response = await client.get(
                "https://data-api.polymarket.com/positions/closed-positions",
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            positions_data = response.json()

        if not positions_data:
            return [types.TextContent(
                type="text",
                text="No closed positions found."
            )]

        # Format output
        result = {
            "success": True,
            "total_positions": len(positions_data),
            "positions": []
        }

        for pos in positions_data[:limit]:
            position_info = {
                "condition_id": pos.get("conditionId"),
                "market_title": pos.get("title"),
                "outcome": pos.get("outcome"),
                "size": float(pos.get("size", 0)),
                "avg_price": float(pos.get("avgPrice", 0)),
                "redeemable": pos.get("redeemable", False),
                "payout": float(pos.get("payout", 0)),
                "token_id": pos.get("asset")
            }
            result["positions"].append(position_info)

        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Failed to fetch closed positions: {e}")
        error_result = {
            "success": False,
            "error": str(e)
        }
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]


async def get_redeemable_positions(
    polymarket_client,
    rate_limiter,
    config
) -> List[types.TextContent]:
    """
    Get positions that are ready to be redeemed (winning positions in resolved markets).

    Args:
        polymarket_client: PolymarketClient instance
        rate_limiter: RateLimiter instance
        config: PolymarketConfig instance

    Returns:
        List with formatted redeemable position data
    """
    try:
        from ..utils.rate_limiter import EndpointCategory

        # Rate limit for data API
        await rate_limiter.acquire(EndpointCategory.DATA_API)

        # Fetch closed positions from Data API
        async with httpx.AsyncClient() as client:
            params = {
                "user": config.POLYGON_ADDRESS.lower()
            }

            response = await client.get(
                "https://data-api.polymarket.com/positions/closed-positions",
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            positions_data = response.json()

        if not positions_data:
            return [types.TextContent(
                type="text",
                text="No positions found."
            )]

        # Filter for redeemable positions only
        redeemable = [pos for pos in positions_data if pos.get("redeemable", False)]

        if not redeemable:
            return [types.TextContent(
                type="text",
                text="No redeemable positions found. All winning positions have been redeemed."
            )]

        # Format output
        result = {
            "success": True,
            "total_redeemable": len(redeemable),
            "total_payout_usdc": sum(float(pos.get("payout", 0)) for pos in redeemable),
            "positions": []
        }

        for pos in redeemable:
            # Determine index_set based on outcome
            outcome = pos.get("outcome")
            if outcome == "Yes":
                index_set = 1
            elif outcome == "No":
                index_set = 2
            else:
                # Multi-outcome market - parse outcome index
                index_set = None

            position_info = {
                "condition_id": pos.get("conditionId"),
                "market_title": pos.get("title"),
                "outcome": outcome,
                "winning_outcome": outcome,
                "size": float(pos.get("size", 0)),
                "expected_payout_usdc": float(pos.get("payout", 0)),
                "token_id": pos.get("asset"),
                "index_set": index_set
            }
            result["positions"].append(position_info)

        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Failed to fetch redeemable positions: {e}")
        error_result = {
            "success": False,
            "error": str(e)
        }
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]


async def redeem_winning_positions(
    polymarket_client,
    rate_limiter,
    config,
    condition_id: str,
    index_sets: List[int]
) -> List[types.TextContent]:
    """
    Redeem winning outcome tokens for USDC.e via CTF contract.

    Args:
        polymarket_client: PolymarketClient instance
        rate_limiter: RateLimiter instance
        config: PolymarketConfig instance
        condition_id: The conditionId of the resolved market
        index_sets: Index sets to redeem: [1] for YES, [2] for NO

    Returns:
        List with transaction result
    """
    try:
        # Initialize Web3
        w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
        
        if not w3.is_connected():
            raise RuntimeError("Failed to connect to Polygon RPC")

        # Get private key from config
        private_key = config.POLYGON_PRIVATE_KEY
        if not private_key:
            raise RuntimeError("Private key not available")

        # Create account from private key
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        account = Account.from_key(private_key)

        # Create contract instance
        ctf_contract = w3.eth.contract(
            address=Web3.to_checksum_address(CTF_ADDRESS),
            abi=CTF_ABI
        )

        # Convert condition_id to bytes32
        if condition_id.startswith("0x"):
            condition_id_bytes = bytes.fromhex(condition_id[2:])
        else:
            condition_id_bytes = bytes.fromhex(condition_id)

        # Prepare transaction
        parent_collection_id = b'\x00' * 32  # bytes32(0) for Polymarket

        # Build transaction with dynamic gas estimation
        tx_function = ctf_contract.functions.redeemPositions(
            Web3.to_checksum_address(USDC_ADDRESS),  # collateralToken
            parent_collection_id,  # parentCollectionId
            condition_id_bytes,  # conditionId
            index_sets  # indexSets
        )

        # Estimate gas dynamically
        try:
            estimated_gas = tx_function.estimate_gas({
                'from': account.address
            })
            # Add 20% buffer to estimated gas
            gas_limit = int(estimated_gas * 1.2)
        except Exception as gas_error:
            logger.warning(f"Gas estimation failed: {gas_error}, using default 200000")
            gas_limit = 200000

        # Build transaction
        tx = tx_function.build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': gas_limit,
            'gasPrice': w3.eth.gas_price,
            'chainId': config.POLYMARKET_CHAIN_ID
        })

        # Sign transaction
        signed_tx = account.sign_transaction(tx)

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for receipt (optional - can be async)
        logger.info(f"Redemption transaction sent: {tx_hash.hex()}")

        result = {
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "condition_id": condition_id,
            "index_sets": index_sets,
            "gas_used": gas_limit,
            "status": "Transaction sent. Check block explorer for confirmation."
        }

        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Failed to redeem positions: {e}")
        error_result = {
            "success": False,
            "error": str(e),
            "condition_id": condition_id,
            "index_sets": index_sets
        }
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]


async def redeem_all_winning_positions(
    polymarket_client,
    rate_limiter,
    config,
    dry_run: bool = False
) -> List[types.TextContent]:
    """
    Batch redeem all redeemable winning positions.

    Args:
        polymarket_client: PolymarketClient instance
        rate_limiter: RateLimiter instance
        config: PolymarketConfig instance
        dry_run: If true, only simulate without executing (default: false)

    Returns:
        List with batch redemption results
    """
    try:
        # First, get all redeemable positions
        redeemable_result = await get_redeemable_positions(
            polymarket_client,
            rate_limiter,
            config
        )

        # Parse the result
        redeemable_data = json.loads(redeemable_result[0].text)

        if not redeemable_data.get("success"):
            return redeemable_result

        positions = redeemable_data.get("positions", [])
        
        if not positions:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": "No redeemable positions found."
                }, indent=2)
            )]

        # Dry run mode - just return what would be redeemed
        if dry_run:
            result = {
                "success": True,
                "dry_run": True,
                "total_positions": len(positions),
                "total_payout_usdc": redeemable_data.get("total_payout_usdc", 0),
                "positions_to_redeem": positions
            }
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        # Execute redemptions
        redemption_results = []
        total_success = 0
        total_failed = 0

        for pos in positions:
            condition_id = pos.get("condition_id")
            index_set = pos.get("index_set")

            if not condition_id or index_set is None:
                logger.warning(f"Skipping position with missing data: {pos}")
                total_failed += 1
                continue

            try:
                result = await redeem_winning_positions(
                    polymarket_client,
                    rate_limiter,
                    config,
                    condition_id,
                    [index_set]
                )
                
                result_data = json.loads(result[0].text)
                if result_data.get("success"):
                    total_success += 1
                else:
                    total_failed += 1
                
                redemption_results.append({
                    "condition_id": condition_id,
                    "market_title": pos.get("market_title"),
                    "payout": pos.get("expected_payout_usdc"),
                    "result": result_data
                })

            except Exception as e:
                logger.error(f"Failed to redeem position {condition_id}: {e}")
                total_failed += 1
                redemption_results.append({
                    "condition_id": condition_id,
                    "market_title": pos.get("market_title"),
                    "result": {
                        "success": False,
                        "error": str(e)
                    }
                })

        # Summary result
        summary = {
            "success": True,
            "total_positions": len(positions),
            "successful_redemptions": total_success,
            "failed_redemptions": total_failed,
            "total_payout_usdc": redeemable_data.get("total_payout_usdc", 0),
            "results": redemption_results
        }

        return [types.TextContent(
            type="text",
            text=json.dumps(summary, indent=2)
        )]

    except Exception as e:
        logger.error(f"Failed to batch redeem positions: {e}")
        error_result = {
            "success": False,
            "error": str(e)
        }
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]


# Tool definitions for MCP registration
REDEMPTION_TOOLS = [
    {
        "name": "get_closed_positions",
        "description": "Get all closed/resolved positions for the user, including payout information and redeemable status",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "number",
                    "description": "Maximum positions to return (default: 100)",
                    "default": 100
                }
            }
        },
        "handler": get_closed_positions
    },
    {
        "name": "get_redeemable_positions",
        "description": "Get positions that are ready to be redeemed (winning positions in resolved markets with unredeemed tokens)",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
        "handler": get_redeemable_positions
    },
    {
        "name": "redeem_winning_positions",
        "description": "Redeem winning outcome tokens for USDC.e via CTF contract. Executes blockchain transaction.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "condition_id": {
                    "type": "string",
                    "description": "The conditionId of the resolved market (with or without 0x prefix)"
                },
                "index_sets": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Index sets to redeem: [1] for YES, [2] for NO. For multi-outcome, use the appropriate index."
                }
            },
            "required": ["condition_id", "index_sets"]
        },
        "handler": redeem_winning_positions
    },
    {
        "name": "redeem_all_winning_positions",
        "description": "Batch redeem all redeemable winning positions. Executes multiple blockchain transactions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only simulate without executing transactions (default: false)",
                    "default": False
                }
            }
        },
        "handler": redeem_all_winning_positions
    }
]


def get_redemption_tool_definitions() -> list[types.Tool]:
    """
    Get redemption tool definitions for MCP server.

    Returns:
        List of 4 redemption tools as MCP Tool objects
    """
    tools = []

    for tool_def in REDEMPTION_TOOLS:
        tools.append(types.Tool(
            name=tool_def["name"],
            description=tool_def["description"],
            inputSchema=tool_def["inputSchema"]
        ))

    return tools


async def call_redemption_tool(
    name: str,
    arguments: dict,
    polymarket_client,
    rate_limiter,
    config
) -> list[types.TextContent]:
    """
    Call a redemption tool by name.

    Args:
        name: Tool name
        arguments: Tool arguments
        polymarket_client: PolymarketClient instance
        rate_limiter: RateLimiter instance
        config: PolymarketConfig instance

    Returns:
        List of TextContent with tool results

    Raises:
        ValueError: If tool name is unknown
    """
    # Find the tool handler
    tool_handler = None
    for tool_def in REDEMPTION_TOOLS:
        if tool_def["name"] == name:
            tool_handler = tool_def["handler"]
            break

    if not tool_handler:
        raise ValueError(f"Unknown redemption tool: {name}")

    # Call the handler with required dependencies
    result = await tool_handler(
        polymarket_client=polymarket_client,
        rate_limiter=rate_limiter,
        config=config,
        **arguments
    )

    return result
