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

"""Base classes for business entity models with Neo4j integration."""

import contextlib
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar
from uuid import uuid4

T = TypeVar("T", bound="BusinessEntity")


@dataclass
class BusinessEntity(ABC):
    """
    Abstract base class for all business entities.

    Provides common functionality for data serialization, deserialization,
    and Neo4j graph database integration.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """
        Convert entity to dictionary.

        Returns:
            Dictionary representation of the entity with all fields.
        """
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """
        Create entity from dictionary.

        Args:
            data: Dictionary containing entity fields.

        Returns:
            Instance of the entity.

        Raises:
            ValueError: If required fields are missing.
        """
        # Convert ISO format strings back to datetime
        data_copy = data.copy()
        for key, value in data_copy.items():
            if isinstance(value, str) and key.endswith("_at"):
                with contextlib.suppress(ValueError, TypeError):
                    data_copy[key] = datetime.fromisoformat(value)

        # Filter to only include fields defined in the dataclass
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data_copy.items() if k in valid_fields}

        return cls(**filtered_data)

    def to_neo4j(self) -> dict[str, Any]:
        """
        Convert entity to Neo4j node properties.

        Returns:
            Dictionary suitable for Neo4j property assignment.
        """
        data = self.to_dict()
        # Ensure all values are Neo4j-compatible types
        neo4j_data = {}
        for key, value in data.items():
            if value is None:
                continue
            elif isinstance(value, (str, int, float, bool)):
                neo4j_data[key] = value
            elif isinstance(value, (list, tuple)):
                neo4j_data[key] = list(value)
            elif isinstance(value, dict):
                neo4j_data[key] = value
            else:
                neo4j_data[key] = str(value)
        return neo4j_data

    @property
    def entity_label(self) -> str:
        """
        Get the Neo4j label for this entity.

        Returns:
            Class name to use as Neo4j node label.
        """
        return self.__class__.__name__

    def update_timestamp(self) -> None:
        """Update the modified timestamp to current time."""
        self.updated_at = datetime.now(timezone.utc)


class Repository(ABC, Generic[T]):
    """
    Abstract repository for CRUD operations with Neo4j backend.

    Provides interface for database persistence of business entities.
    """

    entity_class: type[T]
    neo4j_driver: Optional[Any] = None

    def __init__(self, neo4j_driver: Optional[Any] = None):
        """
        Initialize repository.

        Args:
            neo4j_driver: Neo4j driver instance for database operations.
        """
        self.neo4j_driver = neo4j_driver

    @abstractmethod
    def save(self, entity: T) -> T:
        """
        Save entity to database.

        Args:
            entity: Entity to save.

        Returns:
            Saved entity with potentially updated fields.
        """
        pass

    @abstractmethod
    def load(self, entity_id: str) -> Optional[T]:
        """
        Load entity from database by ID.

        Args:
            entity_id: ID of entity to load.

        Returns:
            Entity if found, None otherwise.
        """
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Delete entity from database.

        Args:
            entity_id: ID of entity to delete.

        Returns:
            True if entity was deleted, False if not found.
        """
        pass

    @abstractmethod
    def search(self, **criteria: Any) -> list[T]:
        """
        Search for entities matching criteria.

        Args:
            **criteria: Field name and value pairs to match.

        Returns:
            List of matching entities.
        """
        pass

    def save_batch(self, entities: list[T]) -> list[T]:
        """
        Save multiple entities.

        Args:
            entities: List of entities to save.

        Returns:
            List of saved entities.
        """
        return [self.save(entity) for entity in entities]

    def load_batch(self, entity_ids: list[str]) -> list[T]:
        """
        Load multiple entities by IDs.

        Args:
            entity_ids: List of entity IDs to load.

        Returns:
            List of loaded entities (excluding not found).
        """
        results = []
        for entity_id in entity_ids:
            entity = self.load(entity_id)
            if entity:
                results.append(entity)
        return results

    def delete_batch(self, entity_ids: list[str]) -> int:
        """
        Delete multiple entities.

        Args:
            entity_ids: List of entity IDs to delete.

        Returns:
            Number of entities deleted.
        """
        count = 0
        for entity_id in entity_ids:
            if self.delete(entity_id):
                count += 1
        return count
