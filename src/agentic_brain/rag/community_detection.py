# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Community detection helpers powered by Neo4j Graph Data Science."""


def detect_communities(session) -> dict[int, list[str]]:
    # Project graph
    session.run(
        """
        CALL gds.graph.project('entity-graph', 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
    """
    )

    # Run Leiden algorithm
    result = session.run(
        """
        CALL gds.leiden.stream('entity-graph')
        YIELD nodeId, communityId
        RETURN gds.util.asNode(nodeId).name AS entity, communityId
    """
    )

    communities: dict[int, list[str]] = {}
    for record in result:
        cid = record["communityId"]
        if cid not in communities:
            communities[cid] = []
        communities[cid].append(record["entity"])

    # Cleanup
    session.run("CALL gds.graph.drop('entity-graph')")
    return communities


async def detect_communities_async(session) -> dict[int, list[str]]:
    """Async wrapper for community detection using Neo4j GDS."""
    await session.run(
        """
        CALL gds.graph.project('entity-graph', 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
    """
    )

    result = await session.run(
        """
        CALL gds.leiden.stream('entity-graph')
        YIELD nodeId, communityId
        RETURN gds.util.asNode(nodeId).name AS entity, communityId
    """
    )

    communities: dict[int, list[str]] = {}
    async for record in result:
        cid = record["communityId"]
        if cid not in communities:
            communities[cid] = []
        communities[cid].append(record["entity"])

    await session.run("CALL gds.graph.drop('entity-graph')")
    return communities
