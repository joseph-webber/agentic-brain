# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""Base classes for business entity models with Neo4j integration."""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
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

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
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
                try:
                    data_copy[key] = datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    pass

        # Filter to only include fields defined in the dataclass
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data_copy.items() if k in valid_fields}

        return cls(**filtered_data)

    def to_neo4j(self) -> Dict[str, Any]:
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

    entity_class: Type[T]
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
    def search(self, **criteria: Any) -> List[T]:
        """
        Search for entities matching criteria.
        
        Args:
            **criteria: Field name and value pairs to match.
            
        Returns:
            List of matching entities.
        """
        pass

    def save_batch(self, entities: List[T]) -> List[T]:
        """
        Save multiple entities.
        
        Args:
            entities: List of entities to save.
            
        Returns:
            List of saved entities.
        """
        return [self.save(entity) for entity in entities]

    def load_batch(self, entity_ids: List[str]) -> List[T]:
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

    def delete_batch(self, entity_ids: List[str]) -> int:
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
