# Query Routing

The `agentic_brain.routing` package adds intelligent query routing for search and retrieval.

## Components

- `QueryClassifier` — scores a query and picks `vector`, `graph`, `hybrid`, or `web`
- `QueryDecomposer` — breaks multi-part queries into smaller sub-queries
- `QueryPlanner` — turns a query into an ordered execution plan
- `QueryRouter` — selects a route, applies fallbacks, and can execute handlers

## Route types

- **vector**: semantic/document search
- **graph**: relationship or multi-hop search
- **hybrid**: mixed semantic + graph retrieval
- **web**: fresh or time-sensitive lookup

## Example

```python
from agentic_brain.routing import QueryRouter, RouteType

router = QueryRouter()
decision = router.route("Find the policy and check the latest update")
print(decision.route)
print(decision.confidence)
print(decision.fallback_routes)
```

## Fallback behavior

The router keeps a ranked list of fallback routes derived from confidence scores.
If the preferred route is unavailable or below the configured threshold, the router
will try the next best available route.

## Planning

Multi-part queries are decomposed into steps so each part can use the best route.
For example, a query that mixes document lookup and relationship traversal may be
planned as a hybrid orchestration with per-step routing.

## Execution

`QueryRouter.execute()` accepts route handlers and will:

1. choose a primary route
2. execute planned steps
3. fall back to alternate routes when a handler fails or is unavailable

Handlers can be sync or async callables that accept the sub-query text.
