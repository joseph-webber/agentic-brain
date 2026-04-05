# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
SSL Bypass Utility for Corporate Networks

Corporate networks often use SSL inspection proxies that cause
CERTIFICATE_VERIFY_FAILED errors. This module provides utilities
to bypass SSL verification when needed.

Usage:
    from agentic_brain.utils.ssl_bypass import get_ssl_context, should_verify_ssl
    
    # For aiohttp:
    async with aiohttp.ClientSession() as session:
        ssl_ctx = get_ssl_context()
        async with session.get(url, ssl=ssl_ctx) as resp:
            ...
    
    # For requests:
    import requests
    requests.get(url, verify=should_verify_ssl())
"""
import os
import ssl
from typing import Union


def should_verify_ssl() -> bool:
    """Check if SSL verification should be enabled."""
    # Check multiple environment variables
    if os.environ.get("PYTHONHTTPSVERIFY", "1") == "0":
        return False
    if os.environ.get("SSL_VERIFY", "1").lower() in ("0", "false", "no"):
        return False
    if os.environ.get("REQUESTS_CA_BUNDLE", "") == "":
        # Empty string means no CA bundle = no verification
        verify = os.environ.get("SSL_VERIFY", "1")
        if verify.lower() in ("0", "false", "no"):
            return False
    return True


def get_ssl_context() -> Union[ssl.SSLContext, bool]:
    """Get SSL context for aiohttp/httpx.
    
    Returns:
        ssl.SSLContext with verification disabled, or False to skip SSL entirely
    """
    if not should_verify_ssl():
        # Create unverified context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return True  # Use default SSL verification


def patch_ssl_globally() -> None:
    """Patch SSL globally for all requests.
    
    Call this at application startup if you need to bypass SSL everywhere.
    WARNING: This is insecure and should only be used in development!
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Patch ssl default context
    ssl._create_default_https_context = ssl._create_unverified_context


# Auto-patch if PYTHONHTTPSVERIFY=0
if os.environ.get("PYTHONHTTPSVERIFY", "1") == "0":
    patch_ssl_globally()
