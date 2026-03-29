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

"""Temporal activity definitions for reusable tasks."""

from __future__ import annotations

from typing import Any

# Optional dependency - graceful fallback if not installed
try:
    from temporalio import activity

    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False

    # Create stub for activity decorator
    class _ActivityStub:
        @staticmethod
        def defn(fn):
            return fn

        class logger:
            @staticmethod
            def info(msg):
                pass

        @staticmethod
        def heartbeat(*args):
            pass

    activity = _ActivityStub()


@activity.defn
async def llm_query(
    prompt: str,
    context: Any,
    model: str = "gpt-4",
) -> dict[str, Any]:
    """Execute LLM query with context.

    Args:
        prompt: Query prompt.
        context: Additional context.
        model: LLM model to use.

    Returns:
        LLM response.
    """
    activity.logger.info(f"Executing LLM query with model: {model}")

    # TODO: Integrate with actual LLM service
    # This is a placeholder implementation
    return {
        "response": f"Response to: {prompt}",
        "model": model,
        "context_used": bool(context),
    }


@activity.defn
async def vector_search(
    query: str,
    collection: str = "default",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search vector store for relevant documents.

    Args:
        query: Search query.
        collection: Collection to search.
        top_k: Number of results.

    Returns:
        Retrieved documents with scores.
    """
    activity.logger.info(f"Searching collection '{collection}' for: {query}")

    # Send heartbeat for long-running searches
    activity.heartbeat()

    # TODO: Integrate with actual vector store (Qdrant/Chroma)
    # This is a placeholder implementation
    return [
        {
            "id": f"doc_{i}",
            "text": f"Relevant document {i} for {query}",
            "score": 0.9 - (i * 0.1),
        }
        for i in range(top_k)
    ]


@activity.defn
async def database_operation(
    operation: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Execute database operation.

    Args:
        operation: Operation name.
        params: Operation parameters.

    Returns:
        Operation result.
    """
    activity.logger.info(f"Executing database operation: {operation}")

    # Send heartbeat for long-running operations
    activity.heartbeat()

    # TODO: Integrate with actual database
    # This is a placeholder implementation
    return {
        "operation": operation,
        "success": True,
        "result": params,
    }


@activity.defn
async def external_api_call(
    api: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Call external API.

    Args:
        api: API endpoint name.
        params: API parameters.

    Returns:
        API response.
    """
    activity.logger.info(f"Calling external API: {api}")

    # Send heartbeat for long-running API calls
    activity.heartbeat()

    # TODO: Integrate with actual external APIs
    # This is a placeholder implementation
    return {
        "api": api,
        "success": True,
        "response": params,
    }


@activity.defn
async def process_file(
    operation: str,
    file_path: str,
    offset: int = 0,
    limit: int = 1000,
) -> dict[str, Any]:
    """Process file with specified operation.

    Args:
        operation: Processing operation.
        file_path: Path to file.
        offset: Record offset.
        limit: Record limit.

    Returns:
        Processing result.
    """
    activity.logger.info(
        f"Processing file: {file_path} ({operation}) " f"offset={offset} limit={limit}"
    )

    # Send periodic heartbeats for long-running file processing
    activity.heartbeat({"progress": offset})

    # TODO: Integrate with actual file processing
    # This is a placeholder implementation
    return {
        "operation": operation,
        "file": file_path,
        "processed_records": limit,
        "success": True,
    }


@activity.defn
async def send_notification(
    notification_type: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Send notification (email, SMS, push, etc).

    Args:
        notification_type: Type of notification.
        data: Notification data.

    Returns:
        Send result.
    """
    activity.logger.info(f"Sending notification: {notification_type}")

    # TODO: Integrate with actual notification service
    # This is a placeholder implementation
    return {
        "type": notification_type,
        "sent": True,
        "recipient": data.get("recipient", "unknown"),
    }
