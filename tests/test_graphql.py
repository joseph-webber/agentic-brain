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

"""Tests for GraphQL API in the RAG module."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from agentic_brain.rag import graphql_api

pytestmark = pytest.mark.skipif(
    not graphql_api.STRAWBERRY_AVAILABLE,
    reason="Strawberry GraphQL not installed",
)


@pytest.fixture(autouse=True)
def reset_graphql_context():
    """Reset the in-memory GraphQL context between tests."""
    context = graphql_api.get_context()
    context._collections.clear()
    context._loaders.clear()
    yield
    context._collections.clear()
    context._loaders.clear()


async def execute_graphql(query: str, variables: dict | None = None):
    """Execute a GraphQL query and assert no errors."""
    result = await graphql_api.schema.execute(query, variable_values=variables)
    assert result.errors is None
    assert result.data is not None
    return result.data


# Test GraphQL schema exists
@pytest.mark.asyncio
async def test_graphql_schema_exists():
    """Test that GraphQL schema is defined."""
    assert graphql_api.schema is not None
    assert graphql_api.get_schema() is graphql_api.schema


# Test query types
@pytest.mark.asyncio
async def test_graphql_query_types():
    """Test GraphQL query types are defined."""
    data = await execute_graphql(
        """
        query {
            collections {
                name
                documentCount
                sources
            }
            pipelineStatus {
                isReady
                vectorStoreConnected
                llmConnected
                loadersAvailable
                documentsIndexed
            }
        }
        """
    )

    assert data["collections"] == []
    assert data["pipelineStatus"]["isReady"] is True
    assert data["pipelineStatus"]["vectorStoreConnected"] is True
    assert data["pipelineStatus"]["llmConnected"] is True


# Test mutations if any
@pytest.mark.asyncio
async def test_graphql_mutations():
    """Test GraphQL mutations work."""
    data = await execute_graphql(
        """
        mutation {
            createCollection(name: "test") {
                name
                documentCount
            }
        }
        """
    )

    assert data["createCollection"]["name"] == "test"
    assert data["createCollection"]["documentCount"] == 0

    data = await execute_graphql(
        """
        mutation {
            addDocument(
                collection: "test"
                content: "GraphQL is great"
                source: "local"
                sourceId: "doc-1"
                filename: "doc.txt"
            ) {
                id
                content
                source
                sourceId
                filename
            }
        }
        """
    )

    assert data["addDocument"]["content"] == "GraphQL is great"
    assert data["addDocument"]["source"] == "local"
    assert data["addDocument"]["sourceId"] == "doc-1"
    assert data["addDocument"]["filename"] == "doc.txt"

    data = await execute_graphql(
        """
        query {
            documents(collection: "test") {
                id
                content
                source
                sourceId
            }
        }
        """
    )

    assert len(data["documents"]) == 1
    assert data["documents"][0]["content"] == "GraphQL is great"


# Test RAG query via GraphQL
@pytest.mark.asyncio
async def test_graphql_rag_query():
    """Test RAG queries via GraphQL endpoint."""
    await execute_graphql(
        """
        mutation {
            addDocument(
                collection: "default"
                content: "GraphQL supports schema introspection."
                source: "local"
                sourceId: "doc-2"
            ) {
                id
            }
        }
        """
    )

    data = await execute_graphql(
        """
        mutation Ask($input: RAGInput!) {
            ask(input: $input) {
                answer
                confidence
                tokensUsed
                latencyMs
                sources {
                    content
                    source
                }
            }
        }
        """,
        variables={
            "input": {
                "question": "GraphQL",
                "collections": ["default"],
                "maxSources": 3,
                "temperature": 0.7,
            }
        },
    )

    assert "GraphQL" in data["ask"]["answer"]
    assert data["ask"]["confidence"] > 0
    assert len(data["ask"]["sources"]) == 1
    assert data["ask"]["sources"][0]["source"] == "local"


# Test introspection
@pytest.mark.asyncio
async def test_graphql_introspection():
    """Test GraphQL introspection works."""
    data = await execute_graphql(
        """
        query {
            __schema {
                queryType {
                    name
                }
                mutationType {
                    name
                }
                subscriptionType {
                    name
                }
            }
        }
        """
    )

    assert data["__schema"]["queryType"]["name"] == "Query"
    assert data["__schema"]["mutationType"]["name"] == "Mutation"
    assert data["__schema"]["subscriptionType"]["name"] == "Subscription"
