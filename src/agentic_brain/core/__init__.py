# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Core shared infrastructure for Agentic Brain."""

from .cache_manager import CacheManager
from .neo4j_first import neo4j_first
from .neo4j_pool import (
    Neo4jPoolConfig,
)
from .neo4j_pool import (
    close_pool as close_neo4j_pool,
)
from .neo4j_pool import (
    configure_pool as configure_neo4j_pool,
)
from .neo4j_pool import (
    get_driver as get_neo4j_driver,
)
from .neo4j_pool import (
    get_session as get_neo4j_session,
)
from .neo4j_pool import (
    health_check as neo4j_pool_health,
)
from .neo4j_pool import (
    query as neo4j_query,
)
from .neo4j_pool import (
    query_single as neo4j_query_single,
)
from .neo4j_pool import (
    query_value as neo4j_query_value,
)
from .neo4j_pool import (
    write as neo4j_write,
)
from .polymorphic import (
    BehaviorProfile,
    ComplianceMode,
    ContextType,
    EnvironmentType,
    PolymorphicBrain,
    UserType,
)
from .redis_pool import RedisConfig, RedisCoordination, RedisPoolManager, get_redis_pool

__all__ = [
    "CacheManager",
    "BehaviorProfile",
    "ComplianceMode",
    "ContextType",
    "EnvironmentType",
    "PolymorphicBrain",
    "RedisConfig",
    "RedisCoordination",
    "RedisPoolManager",
    "UserType",
    "get_redis_pool",
    "Neo4jPoolConfig",
    "configure_neo4j_pool",
    "close_neo4j_pool",
    "get_neo4j_driver",
    "get_neo4j_session",
    "neo4j_query",
    "neo4j_query_single",
    "neo4j_query_value",
    "neo4j_write",
    "neo4j_pool_health",
    "neo4j_first",
]

# Rate limit management
from agentic_brain.core.rate_limiter import (
    RateLimitManager,
    RateLimitStrategy,
    ProviderQuota,
    get_rate_limit_manager,
    calculate_safe_agent_count,
    can_deploy_agents,
    get_deployment_recommendation,
)
