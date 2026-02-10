"""
Allowance management tools for Polymarket trading.

Manages USDC and Conditional Token approvals for the Polymarket exchange contracts.
Required before trading can occur.

Contract Addresses (Polygon Mainnet):
- CTF Exchange: 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
- NegRisk CTF Exchange: 0xC5d563A36AE78145C45a50134d48A1215220f80a
- NegRisk Adapter: 0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296
- USDC: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
- Conditional Tokens (CTF): 0x4D97DCd97eC945f40cF65F87097ACe5EA0476045
"""

import logging
import os
from typing import Dict, Any, List, Optional
from web3 import Web3
from eth_account import Account
import requests

logger = logging.getLogger(__name__)

# Contract Addresses on Polygon Mainnet
CONTRACTS = {
    "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "CTF": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
    "CTF_EXCHANGE": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "NEG_RISK_CTF_EXCHANGE": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "NEG_RISK_ADAPTER": "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
}

# Spender contracts that need approval
SPENDER_CONTRACTS = [
    ("CTF_EXCHANGE", CONTRACTS["CTF_EXCHANGE"]),
    ("NEG_RISK_CTF_EXCHANGE", CONTRACTS["NEG_RISK_CTF_EXCHANGE"]),
    ("NEG_RISK_ADAPTER", CONTRACTS["NEG_RISK_ADAPTER"]),
]

# ERC20 ABI for allowance and approve functions
ERC20_ABI = [
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ERC1155 ABI for setApprovalForAll (used by CTF token)
ERC1155_ABI = [
    {
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Maximum uint256 for unlimited approval
MAX_UINT256 = 2**256 - 1

# Polygon RPC fallback
POLYGON_RPC_FALLBACK = "https://polygon-rpc.com"


def get_polygon_rpc_urls() -> list:
    """Get Polygon RPC URLs from environment or use defaults."""
    primary = os.environ.get('POLYGON_RPC')
    if primary:
        return [primary, POLYGON_RPC_FALLBACK]
    return [POLYGON_RPC_FALLBACK]


class AllowanceManager:
    """Manages token allowances for Polymarket trading."""

    def __init__(self, private_key: str, address: str, rpc_url: Optional[str] = None):
        """
        Initialize AllowanceManager.

        Args:
            private_key: Wallet private key (hex string without 0x prefix)
            address: Wallet address
            rpc_url: Optional custom RPC URL (defaults to POLYGON_RPC env var or public RPC)
        """
        self.private_key = private_key if private_key.startswith("0x") else f"0x{private_key}"
        self.address = Web3.to_checksum_address(address)

        # Initialize Web3 with proxy support
        rpc_urls = get_polygon_rpc_urls()
        rpc_url = rpc_url or rpc_urls[0]

        # Check for proxy settings
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')

        # Create session with proxy if needed
        session = requests.Session()
        if https_proxy:
            # For SOCKS proxy, we need to use a different approach
            if 'socks' in https_proxy.lower():
                try:
                    import socks
                    import socket
                    # Parse SOCKS proxy URL
                    proxy_parts = https_proxy.replace('socks5://', '').replace('socks4://', '').split(':')
                    proxy_host = proxy_parts[0]
                    proxy_port = int(proxy_parts[1]) if len(proxy_parts) > 1 else 1080

                    # Configure SOCKS proxy
                    socks.set_default_proxy(socks.SOCKS5, proxy_host, proxy_port)
                    socket.socket = socks.socksocket
                    logger.info(f"Using SOCKS proxy: {proxy_host}:{proxy_port}")
                except ImportError:
                    logger.warning("SOCKS proxy configured but PySocks not available, trying direct connection")
            else:
                session.proxies = {'http': http_proxy, 'https': https_proxy}

        # Try each RPC endpoint
        self.w3 = None
        for rpc in [rpc_url] + get_polygon_rpc_urls():
            try:
                provider = Web3.HTTPProvider(rpc, session=session)
                w3 = Web3(provider)
                if w3.is_connected():
                    self.w3 = w3
                    logger.info(f"Connected to RPC: {rpc}")
                    break
            except Exception as e:
                logger.warning(f"Failed to connect to {rpc}: {e}")
                continue

        if not self.w3:
            raise RuntimeError("Failed to connect to any Polygon RPC endpoint")

        # Initialize contracts
        self.usdc = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["USDC"]),
            abi=ERC20_ABI
        )
        self.ctf = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["CTF"]),
            abi=ERC1155_ABI
        )

        logger.info(f"AllowanceManager initialized for {self.address}")

    async def get_usdc_balance(self) -> Dict[str, Any]:
        """
        Get USDC balance for the wallet.

        Returns:
            Dict with balance in raw and formatted amounts
        """
        try:
            balance_raw = self.usdc.functions.balanceOf(self.address).call()
            # USDC has 6 decimals
            balance_formatted = balance_raw / 1e6

            return {
                "success": True,
                "token": "USDC",
                "address": CONTRACTS["USDC"],
                "balance_raw": str(balance_raw),
                "balance": balance_formatted,
                "decimals": 6
            }
        except Exception as e:
            logger.error(f"Failed to get USDC balance: {e}")
            return {"success": False, "error": str(e)}

    async def get_matic_balance(self) -> Dict[str, Any]:
        """
        Get MATIC (native token) balance for gas fees.

        Returns:
            Dict with balance info
        """
        try:
            balance_raw = self.w3.eth.get_balance(self.address)
            balance_formatted = self.w3.from_wei(balance_raw, 'ether')

            return {
                "success": True,
                "token": "MATIC",
                "balance_raw": str(balance_raw),
                "balance": float(balance_formatted),
                "decimals": 18
            }
        except Exception as e:
            logger.error(f"Failed to get MATIC balance: {e}")
            return {"success": False, "error": str(e)}

    async def check_all_allowances(self) -> Dict[str, Any]:
        """
        Check all required allowances for trading.

        Returns:
            Dict with allowance status for each contract
        """
        try:
            results = {
                "success": True,
                "address": self.address,
                "usdc_allowances": [],
                "ctf_approvals": [],
                "all_approved": True,
                "needs_approval": []
            }

            # Check USDC allowances
            for name, spender in SPENDER_CONTRACTS:
                allowance_raw = self.usdc.functions.allowance(
                    self.address,
                    Web3.to_checksum_address(spender)
                ).call()
                allowance = allowance_raw / 1e6  # USDC has 6 decimals

                is_approved = allowance_raw >= 1e12  # At least 1M USDC approved
                results["usdc_allowances"].append({
                    "spender_name": name,
                    "spender_address": spender,
                    "allowance_raw": str(allowance_raw),
                    "allowance": allowance,
                    "is_approved": is_approved,
                    "is_unlimited": allowance_raw == MAX_UINT256
                })

                if not is_approved:
                    results["all_approved"] = False
                    results["needs_approval"].append(f"USDC -> {name}")

            # Check CTF (ERC1155) approvals
            for name, operator in SPENDER_CONTRACTS:
                is_approved = self.ctf.functions.isApprovedForAll(
                    self.address,
                    Web3.to_checksum_address(operator)
                ).call()

                results["ctf_approvals"].append({
                    "operator_name": name,
                    "operator_address": operator,
                    "is_approved": is_approved
                })

                if not is_approved:
                    results["all_approved"] = False
                    results["needs_approval"].append(f"CTF -> {name}")

            return results

        except Exception as e:
            logger.error(f"Failed to check allowances: {e}")
            return {"success": False, "error": str(e)}

    async def approve_usdc(
        self,
        spender_name: str,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Approve USDC for a spender contract.

        Args:
            spender_name: Name of spender (CTF_EXCHANGE, NEG_RISK_CTF_EXCHANGE, NEG_RISK_ADAPTER)
            amount: Amount to approve in USDC (None = unlimited)

        Returns:
            Dict with transaction result
        """
        try:
            # Find spender address
            spender_address = None
            for name, addr in SPENDER_CONTRACTS:
                if name.upper() == spender_name.upper():
                    spender_address = addr
                    break

            if not spender_address:
                return {
                    "success": False,
                    "error": f"Unknown spender: {spender_name}. Valid options: {[n for n, _ in SPENDER_CONTRACTS]}"
                }

            # Determine approval amount
            if amount is None:
                approval_amount = MAX_UINT256
                amount_desc = "unlimited"
            else:
                approval_amount = int(amount * 1e6)  # USDC has 6 decimals
                amount_desc = f"{amount} USDC"

            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.address)
            gas_price = self.w3.eth.gas_price

            tx = self.usdc.functions.approve(
                Web3.to_checksum_address(spender_address),
                approval_amount
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': gas_price,
                'chainId': 137  # Polygon
            })

            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            return {
                "success": receipt['status'] == 1,
                "token": "USDC",
                "spender_name": spender_name,
                "spender_address": spender_address,
                "amount": amount_desc,
                "tx_hash": tx_hash.hex(),
                "block_number": receipt['blockNumber'],
                "gas_used": receipt['gasUsed']
            }

        except Exception as e:
            logger.error(f"Failed to approve USDC: {e}")
            return {"success": False, "error": str(e)}

    async def approve_ctf(self, operator_name: str) -> Dict[str, Any]:
        """
        Approve CTF (Conditional Tokens) for an operator.

        Args:
            operator_name: Name of operator (CTF_EXCHANGE, NEG_RISK_CTF_EXCHANGE, NEG_RISK_ADAPTER)

        Returns:
            Dict with transaction result
        """
        try:
            # Find operator address
            operator_address = None
            for name, addr in SPENDER_CONTRACTS:
                if name.upper() == operator_name.upper():
                    operator_address = addr
                    break

            if not operator_address:
                return {
                    "success": False,
                    "error": f"Unknown operator: {operator_name}. Valid options: {[n for n, _ in SPENDER_CONTRACTS]}"
                }

            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.address)
            gas_price = self.w3.eth.gas_price

            tx = self.ctf.functions.setApprovalForAll(
                Web3.to_checksum_address(operator_address),
                True
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': gas_price,
                'chainId': 137  # Polygon
            })

            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            return {
                "success": receipt['status'] == 1,
                "token": "CTF",
                "operator_name": operator_name,
                "operator_address": operator_address,
                "approved": True,
                "tx_hash": tx_hash.hex(),
                "block_number": receipt['blockNumber'],
                "gas_used": receipt['gasUsed']
            }

        except Exception as e:
            logger.error(f"Failed to approve CTF: {e}")
            return {"success": False, "error": str(e)}

    async def approve_all(self) -> Dict[str, Any]:
        """
        Approve all required allowances for trading (USDC and CTF for all exchange contracts).

        Returns:
            Dict with results for each approval transaction
        """
        results = {
            "success": True,
            "transactions": [],
            "failed": [],
            "skipped": []
        }

        # First check current allowances
        current = await self.check_all_allowances()
        if not current["success"]:
            return {"success": False, "error": current.get("error", "Failed to check allowances")}

        # Approve USDC for each spender that needs it
        for allowance_info in current["usdc_allowances"]:
            if not allowance_info["is_approved"]:
                result = await self.approve_usdc(allowance_info["spender_name"])
                if result["success"]:
                    results["transactions"].append({
                        "type": "USDC_APPROVAL",
                        **result
                    })
                else:
                    results["success"] = False
                    results["failed"].append({
                        "type": "USDC_APPROVAL",
                        "spender": allowance_info["spender_name"],
                        "error": result.get("error")
                    })
            else:
                results["skipped"].append(f"USDC -> {allowance_info['spender_name']} (already approved)")

        # Approve CTF for each operator that needs it
        for approval_info in current["ctf_approvals"]:
            if not approval_info["is_approved"]:
                result = await self.approve_ctf(approval_info["operator_name"])
                if result["success"]:
                    results["transactions"].append({
                        "type": "CTF_APPROVAL",
                        **result
                    })
                else:
                    results["success"] = False
                    results["failed"].append({
                        "type": "CTF_APPROVAL",
                        "operator": approval_info["operator_name"],
                        "error": result.get("error")
                    })
            else:
                results["skipped"].append(f"CTF -> {approval_info['operator_name']} (already approved)")

        results["total_transactions"] = len(results["transactions"])
        results["total_failed"] = len(results["failed"])
        results["total_skipped"] = len(results["skipped"])

        return results


def get_allowance_tool_definitions() -> List[Dict[str, Any]]:
    """Get MCP tool definitions for allowance management."""
    return [
        {
            "name": "get_wallet_balances",
            "description": "Get USDC and MATIC balances for the trading wallet. MATIC is needed for gas fees.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "check_trading_allowances",
            "description": "Check all required token allowances for Polymarket trading. Shows USDC and CTF approvals for all exchange contracts.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "approve_usdc_for_trading",
            "description": "Approve USDC spending for a Polymarket exchange contract. Required before trading.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "spender": {
                        "type": "string",
                        "description": "Exchange contract name: CTF_EXCHANGE, NEG_RISK_CTF_EXCHANGE, or NEG_RISK_ADAPTER",
                        "enum": ["CTF_EXCHANGE", "NEG_RISK_CTF_EXCHANGE", "NEG_RISK_ADAPTER"]
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount to approve in USDC. Omit for unlimited approval."
                    }
                },
                "required": ["spender"]
            }
        },
        {
            "name": "approve_ctf_for_trading",
            "description": "Approve Conditional Token (CTF) transfers for a Polymarket exchange contract. Required for selling positions.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "operator": {
                        "type": "string",
                        "description": "Exchange contract name: CTF_EXCHANGE, NEG_RISK_CTF_EXCHANGE, or NEG_RISK_ADAPTER",
                        "enum": ["CTF_EXCHANGE", "NEG_RISK_CTF_EXCHANGE", "NEG_RISK_ADAPTER"]
                    }
                },
                "required": ["operator"]
            }
        },
        {
            "name": "approve_all_for_trading",
            "description": "Approve all required allowances for Polymarket trading in one operation. Sets unlimited USDC and CTF approvals for all exchange contracts.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]
