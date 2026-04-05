# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Jinja2-backed prompt template utilities."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, meta


class PromptError(ValueError):
    """Base prompt error."""


class PromptValidationError(PromptError):
    """Raised when a template fails validation."""


class PromptRenderError(PromptError):
    """Raised when rendering fails."""


_ENVIRONMENT = Environment(
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


@dataclass
class PromptTemplate:
    """A reusable prompt template with default variables."""

    name: str
    template: str
    description: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    @classmethod
    def from_file(cls, path: str | Path, *, name: str | None = None) -> PromptTemplate:
        """Create a template from a file."""
        file_path = Path(path)
        return cls(name=name or file_path.stem, template=file_path.read_text())

    @classmethod
    def from_string(
        cls,
        name: str,
        template: str,
        *,
        description: str = "",
        variables: Mapping[str, Any] | None = None,
        tags: tuple[str, ...] = (),
    ) -> PromptTemplate:
        """Create a template from a string."""
        return cls(
            name=name,
            template=template,
            description=description,
            variables=dict(variables or {}),
            tags=tags,
        )

    @property
    def required_variables(self) -> tuple[str, ...]:
        """Return required template variables."""
        return tuple(sorted(self._undeclared_variables() - set(self.variables)))

    def _undeclared_variables(self) -> set[str]:
        try:
            parsed = _ENVIRONMENT.parse(self.template)
        except TemplateSyntaxError as exc:
            raise PromptValidationError(
                f"Template '{self.name}' has invalid Jinja2 syntax: {exc.message}"
            ) from exc
        return set(meta.find_undeclared_variables(parsed))

    def validate(self, context: Mapping[str, Any] | None = None) -> list[str]:
        """Validate the template and optionally a render context."""
        errors: list[str] = []
        if not self.name.strip():
            errors.append("Template name cannot be empty.")
        if not self.template.strip():
            errors.append("Template text cannot be empty.")

        try:
            required = self.required_variables
        except PromptValidationError as exc:
            errors.append(str(exc))
            return errors

        merged = dict(self.variables)
        if context is not None:
            merged.update(context)

        missing = [name for name in required if name not in merged]
        if missing:
            errors.append(f"Missing variables: {', '.join(sorted(missing))}")
        return errors

    def assert_valid(self, context: Mapping[str, Any] | None = None) -> None:
        """Raise if the template or context is invalid."""
        errors = self.validate(context)
        if errors:
            raise PromptValidationError("; ".join(errors))

    def bind(self, **variables: Any) -> PromptTemplate:
        """Return a copy with additional default variables."""
        merged = dict(self.variables)
        merged.update(variables)
        return replace(self, variables=merged)

    def render(self, **variables: Any) -> str:
        """Render the template with merged defaults and injected variables."""
        context = dict(self.variables)
        context.update(variables)
        self.assert_valid(context)
        try:
            return _ENVIRONMENT.from_string(self.template).render(**context)
        except Exception as exc:  # pragma: no cover - defensive
            raise PromptRenderError(f"Failed to render template '{self.name}': {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Serialize the template to a dictionary."""
        return {
            "name": self.name,
            "template": self.template,
            "description": self.description,
            "variables": dict(self.variables),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PromptTemplate:
        """Deserialize a template from a dictionary."""
        return cls(
            name=str(data["name"]),
            template=str(data["template"]),
            description=str(data.get("description", "")),
            variables=dict(data.get("variables", {})),
            tags=tuple(data.get("tags", ())),
        )
