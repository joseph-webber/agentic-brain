# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

from __future__ import annotations

# SPDX-License-Identifier: GPL-3.0-or-later
"""
HTTP request utilities for router.
"""


import json
import logging
import time
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


async def post_request(
    url: str,
    json_data: dict,
    headers: dict | None = None,
    timeout: float = 60,
    pool: Any | None = None,
    pool_requests_counter: list[int] | None = None,
    direct_requests_counter: list[int] | None = None,
) -> tuple[int, dict | str]:
    """
    Make a POST request using HTTP pool if available, else direct aiohttp.

    This centralizes HTTP request handling to:
    - Use connection pooling when available (keep-alive, retries)
    - Fall back to direct requests when pool not started
    - Provide consistent error handling

    Args:
        url: Request URL
        json_data: JSON payload
        headers: Request headers
        timeout: Request timeout
        pool: Optional HTTP pool instance
        pool_requests_counter: Mutable list [count] to increment for pool requests
        direct_requests_counter: Mutable list [count] to increment for direct requests

    Returns:
        Tuple of (status_code, response_data)
        response_data is dict if JSON, str if text

    Raises:
        aiohttp.ClientError: Connection failed
        asyncio.TimeoutError: Request timed out
    """
    start_time = time.time()

    if pool:
        # Use connection pool (preferred - keep-alive, retries, metrics)
        try:
            logger.debug(f"POST request via pool to {url}")
            response = await pool.post(
                url, json=json_data, headers=headers, timeout=timeout
            )
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON response from pool POST: {e}",
                    extra={"url": url, "status": response.status},
                )
                data = response.text
            elapsed = time.time() - start_time
            if pool_requests_counter is not None:
                pool_requests_counter[0] += 1
            logger.debug(f"Pool POST completed: {response.status} in {elapsed:.3f}s")
            return response.status, data
        except Exception as e:
            elapsed = time.time() - start_time
            logger.debug(
                f"Pool request failed in {elapsed:.3f}s, falling back to direct: {e}"
            )
            # Fall through to direct request

    # Direct request (fallback)
    logger.debug(f"POST request via direct session to {url}")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=json_data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            try:
                data = await response.json()
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON response from direct POST: {e}",
                    extra={"url": url, "status": response.status},
                )
                data = await response.text()
            elapsed = time.time() - start_time
            if direct_requests_counter is not None:
                direct_requests_counter[0] += 1
            logger.debug(f"Direct POST completed: {response.status} in {elapsed:.3f}s")
            return response.status, data


async def get_request(
    url: str,
    headers: dict | None = None,
    timeout: float = 60,
    pool: Any | None = None,
    pool_requests_counter: list[int] | None = None,
    direct_requests_counter: list[int] | None = None,
) -> tuple[int, dict | str]:
    """
    Make a GET request using HTTP pool if available.

    Args:
        url: Request URL
        headers: Request headers
        timeout: Request timeout
        pool: Optional HTTP pool instance
        pool_requests_counter: Mutable list [count] to increment for pool requests
        direct_requests_counter: Mutable list [count] to increment for direct requests

    Returns:
        Tuple of (status_code, response_data)
    """
    start_time = time.time()

    if pool:
        try:
            logger.debug(f"GET request via pool to {url}")
            response = await pool.get(url, headers=headers, timeout=timeout)
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON response from pool GET: {e}",
                    extra={"url": url, "status": response.status},
                )
                data = response.text
            elapsed = time.time() - start_time
            if pool_requests_counter is not None:
                pool_requests_counter[0] += 1
            logger.debug(f"Pool GET completed: {response.status} in {elapsed:.3f}s")
            return response.status, data
        except Exception as e:
            elapsed = time.time() - start_time
            logger.debug(
                f"Pool request failed in {elapsed:.3f}s, falling back to direct: {e}"
            )

    logger.debug(f"GET request via direct session to {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            try:
                data = await response.json()
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON response from direct GET: {e}",
                    extra={"url": url, "status": response.status},
                )
                data = await response.text()
            elapsed = time.time() - start_time
            if direct_requests_counter is not None:
                direct_requests_counter[0] += 1
            logger.debug(f"Direct GET completed: {response.status} in {elapsed:.3f}s")
            return response.status, data
