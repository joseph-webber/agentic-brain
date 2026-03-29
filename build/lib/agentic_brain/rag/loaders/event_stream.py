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

"""Event stream loaders for RAG pipelines.

Supports:
- Kafka (distributed event streaming)
- Redpanda (Kafka-compatible event streaming)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

# Check for Kafka
try:
    from kafka import KafkaConsumer, KafkaProducer

    KAFKA_AVAILABLE = True
except ImportError:
    KafkaConsumer = None
    KafkaProducer = None
    KAFKA_AVAILABLE = False

# Redpanda uses the same Kafka protocol
REDPANDA_AVAILABLE = KAFKA_AVAILABLE


class KafkaLoader(BaseLoader):
    """Load messages from Kafka topics.

    Example:
        loader = KafkaLoader(
            bootstrap_servers="localhost:9092",
            topic="my-topic",
            group_id="my-group"
        )
        docs = loader.load_folder("my-topic")
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        topic: Optional[str] = None,
        group_id: Optional[str] = None,
        max_messages: int = 1000,
        auto_offset_reset: str = "earliest",
    ):
        """Initialize Kafka loader.

        Args:
            bootstrap_servers: Kafka bootstrap servers (comma-separated)
            topic: Topic name
            group_id: Consumer group ID
            max_messages: Maximum messages to read
            auto_offset_reset: Where to start reading ('earliest' or 'latest')
        """
        if not KAFKA_AVAILABLE:
            raise ImportError(
                "kafka-python package is required. Install with: pip install kafka-python"
            )

        self.bootstrap_servers = (
            bootstrap_servers or os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        ).split(",")
        self.topic = topic or os.environ.get("KAFKA_TOPIC", "")
        self.group_id = group_id or os.environ.get("KAFKA_GROUP_ID", "default-group")
        self.max_messages = max_messages
        self.auto_offset_reset = auto_offset_reset
        self._consumer = None

    def source_name(self) -> str:
        return "kafka"

    def authenticate(self) -> bool:
        """Create Kafka consumer."""
        try:
            self._consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda m: m.decode("utf-8") if m else None,
                consumer_timeout_ms=5000,
            )
            logger.info(
                f"Connected to Kafka at {','.join(self.bootstrap_servers)}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False

    def close(self) -> None:
        """Close Kafka consumer."""
        if self._consumer:
            self._consumer.close()

    @with_rate_limit(requests_per_minute=100)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a document by offset/timestamp (simplified).

        Args:
            doc_id: Message offset as string

        Returns:
            Loaded message
        """
        logger.warning("Direct message lookup not supported. Use load_folder instead.")
        return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load messages from a Kafka topic.

        Args:
            folder_path: Topic name (overrides configured topic)
            recursive: Unused

        Returns:
            List of message documents
        """
        if not self._consumer:
            return []

        documents = []
        topic_name = folder_path or self.topic

        try:
            # Subscribe to topic
            self._consumer.subscribe([topic_name])

            message_count = 0
            for message in self._consumer:
                if message_count >= self.max_messages:
                    break

                content = message.value if message.value else ""

                # Try to parse as JSON
                try:
                    data = json.loads(content)
                    metadata = data
                except json.JSONDecodeError:
                    metadata = {"raw": content}

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        **metadata,
                        "topic": message.topic,
                        "partition": message.partition,
                        "offset": message.offset,
                        "timestamp": message.timestamp,
                    },
                    source="kafka",
                    source_id=f"{message.topic}-{message.partition}-{message.offset}",
                    filename=f"message_{message_count}",
                    mime_type="application/json" if isinstance(metadata, dict) else "text/plain",
                    created_at=datetime.fromtimestamp(message.timestamp / 1000) if message.timestamp else None,
                )
                documents.append(doc)
                message_count += 1

            logger.info(f"Loaded {len(documents)} Kafka messages from {topic_name}")
        except Exception as e:
            logger.error(f"Error loading Kafka topic: {e}")
        finally:
            self._consumer.unsubscribe()

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Kafka messages by content.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching messages
        """
        if not self._consumer:
            return []

        documents = []
        try:
            topic_name = self.topic

            self._consumer.subscribe([topic_name])

            for message in self._consumer:
                if len(documents) >= max_results:
                    break

                content = message.value if message.value else ""

                if query.lower() in content.lower():
                    try:
                        data = json.loads(content)
                        metadata = data
                    except json.JSONDecodeError:
                        metadata = {"raw": content}

                    doc = LoadedDocument(
                        content=content,
                        metadata={
                            **metadata,
                            "topic": message.topic,
                            "offset": message.offset,
                        },
                        source="kafka",
                        source_id=f"{message.topic}-{message.partition}-{message.offset}",
                        filename=f"message_{message.offset}",
                        mime_type="text/plain",
                    )
                    documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching Kafka: {e}")
        finally:
            self._consumer.unsubscribe()

        return documents


class RedpandaLoader(BaseLoader):
    """Load messages from Redpanda (Kafka-compatible event streaming).

    Redpanda is a Kafka-compatible streaming platform, so we use the same
    Kafka protocol with Redpanda-specific optimizations.

    Example:
        loader = RedpandaLoader(
            bootstrap_servers="localhost:9092",
            topic="my-topic"
        )
        docs = loader.load_folder("my-topic")
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        topic: Optional[str] = None,
        group_id: Optional[str] = None,
        max_messages: int = 1000,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
    ):
        """Initialize Redpanda loader.

        Args:
            bootstrap_servers: Redpanda bootstrap servers (comma-separated)
            topic: Topic name
            group_id: Consumer group ID
            max_messages: Maximum messages to read
            auto_offset_reset: Where to start reading
            enable_auto_commit: Auto-commit offsets
        """
        if not REDPANDA_AVAILABLE:
            raise ImportError(
                "kafka-python package is required. Install with: pip install kafka-python"
            )

        self.bootstrap_servers = (
            bootstrap_servers or os.environ.get("REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092")
        ).split(",")
        self.topic = topic or os.environ.get("REDPANDA_TOPIC", "")
        self.group_id = group_id or os.environ.get("REDPANDA_GROUP_ID", "default-group")
        self.max_messages = max_messages
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self._consumer = None

    def source_name(self) -> str:
        return "redpanda"

    def authenticate(self) -> bool:
        """Create Redpanda consumer."""
        try:
            self._consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                value_deserializer=lambda m: m.decode("utf-8") if m else None,
                consumer_timeout_ms=5000,
            )
            logger.info(
                f"Connected to Redpanda at {','.join(self.bootstrap_servers)}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redpanda: {e}")
            return False

    def close(self) -> None:
        """Close Redpanda consumer."""
        if self._consumer:
            self._consumer.close()

    @with_rate_limit(requests_per_minute=100)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a document by offset (simplified).

        Args:
            doc_id: Message offset as string

        Returns:
            Loaded message
        """
        logger.warning("Direct message lookup not supported. Use load_folder instead.")
        return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load messages from a Redpanda topic.

        Args:
            folder_path: Topic name (overrides configured topic)
            recursive: Unused

        Returns:
            List of message documents
        """
        if not self._consumer:
            return []

        documents = []
        topic_name = folder_path or self.topic

        try:
            self._consumer.subscribe([topic_name])

            message_count = 0
            for message in self._consumer:
                if message_count >= self.max_messages:
                    break

                content = message.value if message.value else ""

                # Try to parse as JSON
                try:
                    data = json.loads(content)
                    metadata = data
                except json.JSONDecodeError:
                    metadata = {"raw": content}

                doc = LoadedDocument(
                    content=content,
                    metadata={
                        **metadata,
                        "topic": message.topic,
                        "partition": message.partition,
                        "offset": message.offset,
                        "timestamp": message.timestamp,
                    },
                    source="redpanda",
                    source_id=f"{message.topic}-{message.partition}-{message.offset}",
                    filename=f"message_{message_count}",
                    mime_type="application/json" if isinstance(metadata, dict) else "text/plain",
                    created_at=datetime.fromtimestamp(message.timestamp / 1000) if message.timestamp else None,
                )
                documents.append(doc)
                message_count += 1

            logger.info(f"Loaded {len(documents)} Redpanda messages from {topic_name}")
        except Exception as e:
            logger.error(f"Error loading Redpanda topic: {e}")
        finally:
            self._consumer.unsubscribe()

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Redpanda messages by content.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching messages
        """
        if not self._consumer:
            return []

        documents = []
        try:
            topic_name = self.topic

            self._consumer.subscribe([topic_name])

            for message in self._consumer:
                if len(documents) >= max_results:
                    break

                content = message.value if message.value else ""

                if query.lower() in content.lower():
                    try:
                        data = json.loads(content)
                        metadata = data
                    except json.JSONDecodeError:
                        metadata = {"raw": content}

                    doc = LoadedDocument(
                        content=content,
                        metadata={
                            **metadata,
                            "topic": message.topic,
                            "offset": message.offset,
                        },
                        source="redpanda",
                        source_id=f"{message.topic}-{message.partition}-{message.offset}",
                        filename=f"message_{message.offset}",
                        mime_type="text/plain",
                    )
                    documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching Redpanda: {e}")
        finally:
            self._consumer.unsubscribe()

        return documents


__all__ = [
    "KafkaLoader",
    "RedpandaLoader",
    "KAFKA_AVAILABLE",
    "REDPANDA_AVAILABLE",
]
