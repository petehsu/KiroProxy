"""Shared HTTP client settings for outbound requests.

Provides centralized configuration for httpx clients including:
- TLS verification settings
- VPN/Proxy support (HTTP and SOCKS5)
- Connection pooling configuration
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Union

import httpx

from .logger import get_logger
from .env_config import VPN_PROXY_URL

logger = get_logger("http_client")

_warned_insecure = False


def get_httpx_verify_setting() -> Union[bool, str]:
    """Return httpx `verify` setting.

    Priority:
    1) `KIRO_PROXY_CA_BUNDLE` -> custom CA bundle path
    2) `KIRO_PROXY_INSECURE_TLS` truthy -> disable TLS verification
    3) default -> enable TLS verification
    """
    ca_bundle = os.getenv("KIRO_PROXY_CA_BUNDLE", "").strip()
    if ca_bundle:
        return ca_bundle

    insecure = os.getenv("KIRO_PROXY_INSECURE_TLS", "").strip().lower()
    if insecure in {"1", "true", "yes", "on"}:
        global _warned_insecure
        if not _warned_insecure:
            logger.warning("TLS verification disabled by KIRO_PROXY_INSECURE_TLS")
            _warned_insecure = True
        return False

    return True


def get_proxy_url() -> Optional[str]:
    """Return the configured VPN/proxy URL, or None if not set.

    Normalizes the URL to include scheme if missing.
    Supports HTTP and SOCKS5 protocols.

    Examples:
        http://127.0.0.1:7890
        socks5://127.0.0.1:1080
        http://user:password@proxy.company.com:8080
        192.168.1.100:8080 (defaults to http://)
    """
    url = VPN_PROXY_URL.strip()
    if not url:
        return None

    # Add http:// scheme if missing
    if not url.startswith(("http://", "https://", "socks5://", "socks4://")):
        url = f"http://{url}"

    return url


def get_httpx_proxy_config() -> Optional[str]:
    """Return proxy configuration for httpx client.

    Returns the proxy URL string for httpx's proxy parameter,
    or None if no proxy is configured.
    """
    proxy = get_proxy_url()
    if proxy:
        logger.info(f"Using proxy: {proxy.split('@')[-1]}")  # Hide credentials in log
    return proxy


def create_async_client(
    timeout: float = 30.0,
    follow_redirects: bool = True,
    account_proxy_url: Optional[str] = None,
    **kwargs,
) -> httpx.AsyncClient:
    """Create a configured httpx.AsyncClient with proxy and TLS settings.

    This is the recommended way to create HTTP clients for Kiro API calls.
    Per-account proxy takes priority over the global proxy.

    Args:
        timeout: Request timeout in seconds.
        follow_redirects: Whether to follow redirects.
        account_proxy_url: Per-account proxy URL. Takes priority over global proxy.
        **kwargs: Additional kwargs passed to httpx.AsyncClient.

    Returns:
        Configured httpx.AsyncClient instance.
    """
    proxy = account_proxy_url or get_httpx_proxy_config()
    verify = get_httpx_verify_setting()

    client_kwargs = {
        "verify": verify,
        "timeout": timeout,
        "follow_redirects": follow_redirects,
    }

    if proxy:
        client_kwargs["proxy"] = proxy

    client_kwargs.update(kwargs)
    return httpx.AsyncClient(**client_kwargs)
