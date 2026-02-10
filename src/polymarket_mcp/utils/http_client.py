"""
HTTP client utilities with SOCKS proxy support.

Provides a centralized way to create httpx AsyncClient instances.
Proxy is ONLY used for CLOB API (clob.polymarket.com) due to IP restrictions.
Other APIs (data-api, gamma-api) use direct connections.
"""
import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

import httpx

logger = logging.getLogger(__name__)

# Track if proxy has been configured for py_clob_client
_py_clob_client_proxy_configured = False

# CLOB API host that requires proxy
CLOB_API_HOST = "clob.polymarket.com"


def get_proxy_url() -> Optional[str]:
    """
    Get CLOB proxy URL from environment variables.

    Checks CLOB_PROXY first (recommended), then falls back to HTTPS_PROXY/HTTP_PROXY.
    Only CLOB API requires proxy due to IP restrictions.

    Returns:
        Proxy URL string or None if not configured
    """
    # Prefer CLOB_PROXY for explicit CLOB-only proxy configuration
    proxy = os.environ.get('CLOB_PROXY')
    if proxy:
        return proxy

    # Fall back to standard proxy env vars
    proxy = (
        os.environ.get('HTTPS_PROXY') or
        os.environ.get('https_proxy') or
        os.environ.get('HTTP_PROXY') or
        os.environ.get('http_proxy')
    )
    return proxy


def configure_py_clob_client_proxy() -> bool:
    """
    Configure py_clob_client's global HTTP client to use SOCKS proxy.

    py_clob_client uses a global httpx.Client in http_helpers/helpers.py.
    This function replaces it with a proxy-configured client.

    This is needed because CLOB API has IP restrictions.

    Returns:
        True if proxy was configured, False otherwise
    """
    global _py_clob_client_proxy_configured

    if _py_clob_client_proxy_configured:
        logger.debug("py_clob_client proxy already configured")
        return True

    proxy_url = get_proxy_url()
    if not proxy_url:
        logger.debug("No proxy configured for py_clob_client")
        return False

    try:
        # Import the module that contains the global _http_client
        from py_clob_client.http_helpers import helpers as clob_helpers

        if 'socks' in proxy_url.lower():
            try:
                from httpx_socks import SyncProxyTransport

                transport = SyncProxyTransport.from_url(proxy_url)
                new_client = httpx.Client(transport=transport, http2=True)
                clob_helpers._http_client = new_client
                logger.info(f"Configured py_clob_client with SOCKS proxy: {proxy_url}")
                _py_clob_client_proxy_configured = True
                return True
            except ImportError:
                logger.warning(
                    "httpx-socks not installed, py_clob_client SOCKS proxy will not work. "
                    "Install with: pip install httpx-socks"
                )
                return False
        else:
            # Standard HTTP/HTTPS proxy
            new_client = httpx.Client(proxy=proxy_url, http2=True)
            clob_helpers._http_client = new_client
            logger.info(f"Configured py_clob_client with HTTP proxy: {proxy_url}")
            _py_clob_client_proxy_configured = True
            return True

    except Exception as e:
        logger.error(f"Failed to configure py_clob_client proxy: {e}")
        return False


def create_async_client(timeout: float = 30.0, use_proxy: bool = False, **kwargs) -> httpx.AsyncClient:
    """
    Create an httpx AsyncClient.

    By default, creates a direct connection client.
    Only uses proxy when use_proxy=True (for CLOB API).

    Args:
        timeout: Request timeout in seconds (default: 30.0)
        use_proxy: Whether to use proxy (default: False, only True for CLOB API)
        **kwargs: Additional arguments passed to AsyncClient

    Returns:
        Configured httpx.AsyncClient instance
    """
    if not use_proxy:
        # Direct connection (for data-api, gamma-api, etc.)
        return httpx.AsyncClient(timeout=timeout, **kwargs)

    # Proxy connection (for CLOB API)
    proxy_url = get_proxy_url()

    if proxy_url and 'socks' in proxy_url.lower():
        try:
            from httpx_socks import AsyncProxyTransport

            transport = AsyncProxyTransport.from_url(proxy_url)
            logger.debug(f"Using SOCKS proxy: {proxy_url}")

            return httpx.AsyncClient(
                transport=transport,
                timeout=timeout,
                **kwargs
            )
        except ImportError:
            logger.warning(
                "httpx-socks not installed, SOCKS proxy will not work. "
                "Install with: pip install httpx-socks"
            )
    elif proxy_url:
        # Standard HTTP/HTTPS proxy
        logger.debug(f"Using HTTP proxy: {proxy_url}")
        return httpx.AsyncClient(
            proxy=proxy_url,
            timeout=timeout,
            **kwargs
        )

    # No proxy configured, fall back to direct
    return httpx.AsyncClient(timeout=timeout, **kwargs)


@asynccontextmanager
async def async_client(timeout: float = 30.0, use_proxy: bool = False, **kwargs):
    """
    Async context manager for creating httpx AsyncClient.

    By default uses direct connection. Set use_proxy=True for CLOB API.

    Usage:
        # Direct connection (default)
        async with async_client() as client:
            response = await client.get("https://data-api.polymarket.com/...")

        # With proxy (for CLOB API)
        async with async_client(use_proxy=True) as client:
            response = await client.get("https://clob.polymarket.com/...")

    Args:
        timeout: Request timeout in seconds (default: 30.0)
        use_proxy: Whether to use proxy (default: False)
        **kwargs: Additional arguments passed to AsyncClient

    Yields:
        Configured httpx.AsyncClient instance
    """
    client = create_async_client(timeout=timeout, use_proxy=use_proxy, **kwargs)
    try:
        yield client
    finally:
        await client.aclose()
