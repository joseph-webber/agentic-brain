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

"""WordPress Multisite helpers.

The WordPress REST API is per-site; Multisite adds a network layer where a
single WP installation hosts multiple sites.

This module provides:

- Site discovery (enumerate blogs on a network)
- Cross-site operations (run an operation across many sites)
- Network admin integration (best-effort endpoints; requires plugins on some installs)
- Site-specific configuration overlay

The implementation intentionally fails safely: when multisite endpoints are not
available, discovery can fall back to a configured list of site base URLs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Mapping

from .client import WordPressClient, WordPressConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WordPressSite:
    """Represents a site in a multisite network."""

    site_id: int
    base_url: str
    name: str | None = None
    path: str | None = None


class WordPressMultisiteClient:
    """Best-effort multisite network client.

    Multisite network operations are not part of core WP REST v2.
    Many installs expose one of:

    - a custom endpoint (plugin)
    - an admin AJAX endpoint

    For durability and portability, we support two approaches:

    1. Discovery via wp-json endpoints when available.
    2. Explicit configuration: caller provides a list of site configs.
    """

    def __init__(
        self,
        network: WordPressConfig,
        *,
        sites: Iterable[WordPressSite] | None = None,
    ) -> None:
        self.network = network
        self._client = WordPressClient(network)
        self._explicit_sites = list(sites or [])

    async def discover_sites(self) -> list[WordPressSite]:
        """Discover network sites.

        If the network does not expose a multisite discovery endpoint, returns
        the explicitly configured sites.
        """

        if self._explicit_sites:
            return list(self._explicit_sites)

        # Common plugin pattern: /wp-json/wp/v2/sites
        try:
            payload = await self._client.request(
                "GET",
                "/wp/v2/sites",
                raw=True,
            )
            if isinstance(payload, list):
                sites: list[WordPressSite] = []
                for item in payload:
                    try:
                        site_id = int(item.get("id") or item.get("blog_id") or 0)
                        base_url = str(item.get("url") or item.get("home") or "")
                    except Exception:
                        continue
                    if site_id and base_url:
                        sites.append(
                            WordPressSite(
                                site_id=site_id,
                                base_url=base_url.rstrip("/"),
                                name=item.get("name"),
                                path=item.get("path"),
                            )
                        )
                if sites:
                    return sites
        except Exception as exc:  # pragma: no cover - optional endpoint
            logger.debug("Multisite discovery via /sites failed: %s", exc)

        logger.info(
            "No multisite discovery endpoint detected for %s; returning empty site list",
            self.network.url,
        )
        return []

    async def for_each_site(
        self,
        op: Callable[[WordPressClient, WordPressSite], Awaitable[Any]],
        *,
        sites: Iterable[WordPressSite] | None = None,
    ) -> dict[int, Any]:
        """Run an operation for each site and return results keyed by site_id."""

        discovered = list(sites or await self.discover_sites())
        results: dict[int, Any] = {}
        for site in discovered:
            cfg = self.network.model_copy(update={"base_url": site.base_url})
            client = WordPressClient(cfg)
            results[site.site_id] = await op(client, site)
        return results

    @staticmethod
    def overlay_site_config(
        base: WordPressConfig,
        overrides: Mapping[str, Any] | None = None,
    ) -> WordPressConfig:
        """Return a new WordPressConfig with site-specific overrides."""

        overrides = dict(overrides or {})
        update: dict[str, Any] = {}
        if "url" in overrides or "base_url" in overrides:
            update["base_url"] = str(overrides.get("base_url") or overrides.get("url"))
        for key in (
            "api_namespace",
            "username",
            "application_password",
            "user_password",
            "jwt_token",
            "jwt_token_endpoint",
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_token_url",
            "oauth_scope",
            "timeout",
            "verify_ssl",
            "user_agent",
            "rate_limit_per_minute",
            "rate_limit_per_hour",
            "rate_limit_per_day",
            "cooldown_seconds",
        ):
            if key in overrides:
                update[key] = overrides[key]
        return base.model_copy(update=update)
