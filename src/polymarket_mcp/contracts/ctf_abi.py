"""
CTF (Conditional Token Framework) contract ABI and constants.

The CTF contract is used for redeeming winning outcome tokens.
Reference: https://docs.polymarket.com/developers/CTF/redeem
"""

# CTF Contract Address on Polygon mainnet
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# USDC.e (Bridged USDC from Ethereum) Address on Polygon
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Minimal CTF ABI - just the redeemPositions function
CTF_ABI = [
    {
        "inputs": [
            {
                "internalType": "contract IERC20",
                "name": "collateralToken",
                "type": "address"
            },
            {
                "internalType": "bytes32",
                "name": "parentCollectionId",
                "type": "bytes32"
            },
            {
                "internalType": "bytes32",
                "name": "conditionId",
                "type": "bytes32"
            },
            {
                "internalType": "uint256[]",
                "name": "indexSets",
                "type": "uint256[]"
            }
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "owner",
                "type": "address"
            },
            {
                "internalType": "bytes32",
                "name": "conditionId",
                "type": "bytes32"
            },
            {
                "internalType": "uint256",
                "name": "indexSet",
                "type": "uint256"
            }
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]
