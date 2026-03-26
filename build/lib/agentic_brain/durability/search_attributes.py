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

"""
Search Attributes - Custom searchable fields on workflows.

Enables workflows to have custom searchable attributes
that can be queried for workflow discovery and filtering.

Features:
- Custom attribute types (keyword, text, int, float, datetime, bool)
- Indexed search across workflows
- Attribute updates during execution
- Query builder for complex searches
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union


class SearchAttributeType(Enum):
    """Types of search attributes."""

    KEYWORD = "keyword"  # Exact match
    TEXT = "text"  # Full-text search
    INT = "int"
    FLOAT = "float"
    DATETIME = "datetime"
    BOOL = "bool"
    KEYWORD_LIST = "keyword_list"  # List of keywords


@dataclass
class SearchAttributeDefinition:
    """Definition of a search attribute."""

    name: str
    attribute_type: SearchAttributeType
    description: Optional[str] = None
    indexed: bool = True
    required: bool = False
    default: Optional[Any] = None


@dataclass
class SearchAttributeValue:
    """A search attribute with its value."""

    name: str
    attribute_type: SearchAttributeType
    value: Any
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def matches(self, query_value: Any, operator: str = "eq") -> bool:
        """Check if this attribute matches a query value."""
        if self.value is None:
            return query_value is None

        if operator == "eq":
            return self.value == query_value
        elif operator == "ne":
            return self.value != query_value
        elif operator == "gt":
            return self.value > query_value
        elif operator == "gte":
            return self.value >= query_value
        elif operator == "lt":
            return self.value < query_value
        elif operator == "lte":
            return self.value <= query_value
        elif operator == "contains":
            if self.attribute_type == SearchAttributeType.TEXT:
                return str(query_value).lower() in str(self.value).lower()
            elif self.attribute_type == SearchAttributeType.KEYWORD_LIST:
                return query_value in self.value
            return False
        elif operator == "starts_with":
            return str(self.value).startswith(str(query_value))
        elif operator == "ends_with":
            return str(self.value).endswith(str(query_value))
        elif operator == "in":
            return self.value in query_value
        elif operator == "between":
            low, high = query_value
            return low <= self.value <= high

        return False


@dataclass
class WorkflowSearchAttributes:
    """Search attributes for a workflow instance."""

    workflow_id: str
    workflow_type: str
    attributes: Dict[str, SearchAttributeValue] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def get(self, name: str) -> Optional[Any]:
        """Get attribute value."""
        attr = self.attributes.get(name)
        return attr.value if attr else None

    def set(
        self,
        name: str,
        value: Any,
        attribute_type: Optional[SearchAttributeType] = None,
    ) -> None:
        """Set attribute value."""
        # Infer type if not provided
        if attribute_type is None:
            attribute_type = self._infer_type(value)

        self.attributes[name] = SearchAttributeValue(
            name=name, attribute_type=attribute_type, value=value
        )
        self.updated_at = datetime.now(timezone.utc)

    def _infer_type(self, value: Any) -> SearchAttributeType:
        """Infer attribute type from value."""
        if isinstance(value, bool):
            return SearchAttributeType.BOOL
        elif isinstance(value, int):
            return SearchAttributeType.INT
        elif isinstance(value, float):
            return SearchAttributeType.FLOAT
        elif isinstance(value, datetime):
            return SearchAttributeType.DATETIME
        elif isinstance(value, list):
            return SearchAttributeType.KEYWORD_LIST
        else:
            return SearchAttributeType.KEYWORD

    def upsert(self, updates: Dict[str, Any]) -> None:
        """Update multiple attributes."""
        for name, value in updates.items():
            self.set(name, value)

    def remove(self, name: str) -> bool:
        """Remove an attribute."""
        if name in self.attributes:
            del self.attributes[name]
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {name: attr.value for name, attr in self.attributes.items()}


@dataclass
class SearchQuery:
    """Query for searching workflows by attributes."""

    conditions: List[tuple] = field(default_factory=list)  # (name, op, value)
    workflow_type: Optional[str] = None
    order_by: Optional[str] = None
    order_desc: bool = False
    limit: int = 100
    offset: int = 0

    def where(self, name: str, operator: str, value: Any) -> "SearchQuery":
        """Add a condition."""
        self.conditions.append((name, operator, value))
        return self

    def eq(self, name: str, value: Any) -> "SearchQuery":
        """Equality condition."""
        return self.where(name, "eq", value)

    def ne(self, name: str, value: Any) -> "SearchQuery":
        """Not equal condition."""
        return self.where(name, "ne", value)

    def gt(self, name: str, value: Any) -> "SearchQuery":
        """Greater than condition."""
        return self.where(name, "gt", value)

    def gte(self, name: str, value: Any) -> "SearchQuery":
        """Greater than or equal condition."""
        return self.where(name, "gte", value)

    def lt(self, name: str, value: Any) -> "SearchQuery":
        """Less than condition."""
        return self.where(name, "lt", value)

    def lte(self, name: str, value: Any) -> "SearchQuery":
        """Less than or equal condition."""
        return self.where(name, "lte", value)

    def contains(self, name: str, value: Any) -> "SearchQuery":
        """Contains condition (for text/lists)."""
        return self.where(name, "contains", value)

    def starts_with(self, name: str, value: str) -> "SearchQuery":
        """Starts with condition."""
        return self.where(name, "starts_with", value)

    def between(self, name: str, low: Any, high: Any) -> "SearchQuery":
        """Between condition (inclusive)."""
        return self.where(name, "between", (low, high))

    def of_type(self, workflow_type: str) -> "SearchQuery":
        """Filter by workflow type."""
        self.workflow_type = workflow_type
        return self

    def sort(self, name: str, desc: bool = False) -> "SearchQuery":
        """Set sort order."""
        self.order_by = name
        self.order_desc = desc
        return self

    def page(self, limit: int, offset: int = 0) -> "SearchQuery":
        """Set pagination."""
        self.limit = limit
        self.offset = offset
        return self


class SearchAttributeIndex:
    """
    Index for searching workflows by attributes.

    Features:
    - Register attribute definitions
    - Index workflow attributes
    - Execute search queries
    """

    def __init__(self):
        self.definitions: Dict[str, SearchAttributeDefinition] = {}
        self.workflows: Dict[str, WorkflowSearchAttributes] = {}
        self._type_index: Dict[str, Set[str]] = {}  # workflow_type -> workflow_ids
        self._attribute_index: Dict[str, Dict[Any, Set[str]]] = (
            {}
        )  # attr_name -> value -> workflow_ids

    def register_attribute(
        self,
        name: str,
        attribute_type: SearchAttributeType,
        description: Optional[str] = None,
        required: bool = False,
        default: Optional[Any] = None,
    ) -> None:
        """Register a search attribute definition."""
        self.definitions[name] = SearchAttributeDefinition(
            name=name,
            attribute_type=attribute_type,
            description=description,
            required=required,
            default=default,
        )

    def index_workflow(
        self, workflow_id: str, workflow_type: str, attributes: Dict[str, Any]
    ) -> WorkflowSearchAttributes:
        """Index a workflow's search attributes."""
        workflow_attrs = WorkflowSearchAttributes(
            workflow_id=workflow_id, workflow_type=workflow_type
        )

        # Apply defaults
        for name, defn in self.definitions.items():
            if name not in attributes and defn.default is not None:
                attributes[name] = defn.default

        # Set attributes
        for name, value in attributes.items():
            if name in self.definitions:
                workflow_attrs.set(name, value, self.definitions[name].attribute_type)
            else:
                workflow_attrs.set(name, value)

        self.workflows[workflow_id] = workflow_attrs

        # Update type index
        if workflow_type not in self._type_index:
            self._type_index[workflow_type] = set()
        self._type_index[workflow_type].add(workflow_id)

        # Update attribute indexes
        for name, attr in workflow_attrs.attributes.items():
            if attr.attribute_type == SearchAttributeType.KEYWORD:
                if name not in self._attribute_index:
                    self._attribute_index[name] = {}
                if attr.value not in self._attribute_index[name]:
                    self._attribute_index[name][attr.value] = set()
                self._attribute_index[name][attr.value].add(workflow_id)

        return workflow_attrs

    def update_attributes(self, workflow_id: str, updates: Dict[str, Any]) -> bool:
        """Update a workflow's search attributes."""
        if workflow_id not in self.workflows:
            return False

        self.workflows[workflow_id].upsert(updates)
        return True

    def remove_workflow(self, workflow_id: str) -> bool:
        """Remove a workflow from the index."""
        if workflow_id not in self.workflows:
            return False

        workflow = self.workflows[workflow_id]

        # Remove from type index
        if workflow.workflow_type in self._type_index:
            self._type_index[workflow.workflow_type].discard(workflow_id)

        # Remove from attribute indexes
        for name, attr in workflow.attributes.items():
            if name in self._attribute_index:
                if attr.value in self._attribute_index[name]:
                    self._attribute_index[name][attr.value].discard(workflow_id)

        del self.workflows[workflow_id]
        return True

    def search(self, query: SearchQuery) -> List[WorkflowSearchAttributes]:
        """Execute a search query."""
        # Start with all workflows or type-filtered
        if query.workflow_type:
            workflow_ids = self._type_index.get(query.workflow_type, set())
        else:
            workflow_ids = set(self.workflows.keys())

        # Apply conditions
        results = []
        for wid in workflow_ids:
            workflow = self.workflows.get(wid)
            if not workflow:
                continue

            matches = True
            for name, op, value in query.conditions:
                attr = workflow.attributes.get(name)
                if attr is None:
                    if op == "eq" and value is None:
                        continue
                    matches = False
                    break

                if not attr.matches(value, op):
                    matches = False
                    break

            if matches:
                results.append(workflow)

        # Sort
        if query.order_by:
            results.sort(
                key=lambda w: (w.get(query.order_by) or ""), reverse=query.order_desc
            )

        # Paginate
        return results[query.offset : query.offset + query.limit]

    def count(self, query: SearchQuery) -> int:
        """Count matching workflows."""
        query.limit = 999999
        query.offset = 0
        return len(self.search(query))

    def get_attribute_values(self, name: str) -> List[Any]:
        """Get all unique values for an attribute."""
        if name in self._attribute_index:
            return list(self._attribute_index[name].keys())

        values = set()
        for workflow in self.workflows.values():
            attr = workflow.attributes.get(name)
            if attr is not None:
                values.add(attr.value)

        return list(values)


# Convenience function for creating queries
def query() -> SearchQuery:
    """Create a new search query."""
    return SearchQuery()


# Pre-built search attribute definitions
COMMON_ATTRIBUTES = [
    SearchAttributeDefinition(
        name="status",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Workflow status",
    ),
    SearchAttributeDefinition(
        name="customer_id",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Customer identifier",
    ),
    SearchAttributeDefinition(
        name="order_id",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Order identifier",
    ),
    SearchAttributeDefinition(
        name="priority",
        attribute_type=SearchAttributeType.INT,
        description="Priority level (1-10)",
    ),
    SearchAttributeDefinition(
        name="tags",
        attribute_type=SearchAttributeType.KEYWORD_LIST,
        description="Workflow tags",
    ),
    SearchAttributeDefinition(
        name="created_by",
        attribute_type=SearchAttributeType.KEYWORD,
        description="User who created the workflow",
    ),
    SearchAttributeDefinition(
        name="environment",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Execution environment",
    ),
    SearchAttributeDefinition(
        name="region",
        attribute_type=SearchAttributeType.KEYWORD,
        description="Geographic region",
    ),
]


def create_standard_index() -> SearchAttributeIndex:
    """Create an index with common attribute definitions."""
    index = SearchAttributeIndex()

    for defn in COMMON_ATTRIBUTES:
        index.register_attribute(
            name=defn.name,
            attribute_type=defn.attribute_type,
            description=defn.description,
            required=defn.required,
            default=defn.default,
        )

    return index
