# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""Comprehensive tests for JDL-inspired ADL features.

Covers:
- Entity relationships (OneToMany, ManyToMany, OneToOne)
- Enum support
- Validation constraints (required, unique, minlength, maxlength, min, max)
- Pagination / DTO / Service directives
- Deployment options
- All four generators (Neo4j, Python, API, React)
- Integration tests combining parser + generators
"""

import textwrap

import pytest

from agentic_brain.adl.generators.api_routes import ApiRouteGenerator
from agentic_brain.adl.generators.neo4j_schema import Neo4jSchemaGenerator
from agentic_brain.adl.generators.python_models import PythonModelGenerator
from agentic_brain.adl.generators.react_components import ReactComponentGenerator
from agentic_brain.adl.parser import (
    ADLConfig,
    ADLParseError,
    DtoDef,
    EntityDef,
    EnumDef,
    FieldDef,
    PaginationDef,
    RelationshipDef,
    RelationshipEnd,
    ServiceDef,
    Validator,
    parse_adl,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_JDL_ADL = textwrap.dedent(
    """\
    application MyBrain {
      name "Knowledge Brain"
      version "2.0.0"
    }

    llm Primary {
      provider ollama
      model "llama3.2:3b"
      temperature 0.5
      maxTokens 2048
    }

    enum NodeType {
      DOCUMENT, CONCEPT, PERSON, LOCATION
    }

    enum Priority {
      LOW, MEDIUM, HIGH, CRITICAL
    }

    entity KnowledgeNode {
      content String required
      embedding Vector
      source String
      nodeType String
      priority String
    }

    entity Tag {
      name String required unique minlength(1) maxlength(50)
    }

    entity User {
      name String required minlength(2) maxlength(100)
      email String required unique
    }

    entity Post {
      title String required minlength(1) maxlength(200)
      content TextBlob
      score Float min(0) max(100)
    }

    relationship OneToMany {
      User{posts} to Post{author}
    }

    relationship ManyToMany {
      KnowledgeNode{tags} to Tag{nodes}
    }

    relationship OneToOne {
      User{profile} to KnowledgeNode{owner}
    }

    paginate Post, KnowledgeNode with pagination
    paginate Tag with infinite-scroll
    dto * with mapstruct
    service all with serviceImpl

    deployment {
      deploymentType docker-compose
      dockerRepositoryName "myrepo"
    }
"""
)

MINIMAL_ENTITY_ADL = textwrap.dedent(
    """\
    application Test {
      name "Test"
    }

    llm Primary {
      provider ollama
      model "llama3.2:3b"
    }

    entity Simple {
      name String required
    }
"""
)


# ===========================================================================
# Parser Tests — Entities
# ===========================================================================


class TestEntityParsing:
    def test_simple_entity(self):
        cfg = parse_adl(MINIMAL_ENTITY_ADL)
        assert "Simple" in cfg.entities
        entity = cfg.entities["Simple"]
        assert len(entity.fields) == 1
        assert entity.fields[0].name == "name"
        assert entity.fields[0].type == "String"

    def test_multiple_entities(self):
        cfg = parse_adl(FULL_JDL_ADL)
        assert "KnowledgeNode" in cfg.entities
        assert "Tag" in cfg.entities
        assert "User" in cfg.entities
        assert "Post" in cfg.entities

    def test_entity_field_types(self):
        cfg = parse_adl(FULL_JDL_ADL)
        post = cfg.entities["Post"]
        field_map = {f.name: f for f in post.fields}
        assert field_map["title"].type == "String"
        assert field_map["content"].type == "TextBlob"
        assert field_map["score"].type == "Float"

    def test_entity_with_annotations(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }

            @readOnly
            entity Config {
              key String required unique
              value String
            }
        """
        )
        cfg = parse_adl(adl)
        assert "Config" in cfg.entities
        assert any(a.name == "readOnly" for a in cfg.entities["Config"].annotations)


# ===========================================================================
# Parser Tests — Validators
# ===========================================================================


class TestValidatorParsing:
    def test_required_validator(self):
        cfg = parse_adl(FULL_JDL_ADL)
        tag = cfg.entities["Tag"]
        name_field = tag.fields[0]
        validators = {v.name for v in name_field.validators}
        assert "required" in validators

    def test_unique_validator(self):
        cfg = parse_adl(FULL_JDL_ADL)
        tag = cfg.entities["Tag"]
        name_field = tag.fields[0]
        validators = {v.name for v in name_field.validators}
        assert "unique" in validators

    def test_minlength_validator(self):
        cfg = parse_adl(FULL_JDL_ADL)
        tag = cfg.entities["Tag"]
        name_field = tag.fields[0]
        minlen = [v for v in name_field.validators if v.name == "minlength"]
        assert len(minlen) == 1
        assert minlen[0].args == [1]

    def test_maxlength_validator(self):
        cfg = parse_adl(FULL_JDL_ADL)
        tag = cfg.entities["Tag"]
        name_field = tag.fields[0]
        maxlen = [v for v in name_field.validators if v.name == "maxlength"]
        assert len(maxlen) == 1
        assert maxlen[0].args == [50]

    def test_min_max_validators(self):
        cfg = parse_adl(FULL_JDL_ADL)
        post = cfg.entities["Post"]
        score = [f for f in post.fields if f.name == "score"][0]
        min_v = [v for v in score.validators if v.name == "min"]
        max_v = [v for v in score.validators if v.name == "max"]
        assert min_v[0].args == [0]
        assert max_v[0].args == [100]

    def test_multiple_validators_on_field(self):
        cfg = parse_adl(FULL_JDL_ADL)
        user = cfg.entities["User"]
        name_field = [f for f in user.fields if f.name == "name"][0]
        validator_names = {v.name for v in name_field.validators}
        assert validator_names == {"required", "minlength", "maxlength"}


# ===========================================================================
# Parser Tests — Enums
# ===========================================================================


class TestEnumParsing:
    def test_simple_enum(self):
        cfg = parse_adl(FULL_JDL_ADL)
        assert "NodeType" in cfg.enums
        assert cfg.enums["NodeType"].values == [
            "DOCUMENT",
            "CONCEPT",
            "PERSON",
            "LOCATION",
        ]

    def test_multiple_enums(self):
        cfg = parse_adl(FULL_JDL_ADL)
        assert "NodeType" in cfg.enums
        assert "Priority" in cfg.enums

    def test_priority_enum(self):
        cfg = parse_adl(FULL_JDL_ADL)
        assert cfg.enums["Priority"].values == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_empty_enum(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            enum Empty { }
        """
        )
        cfg = parse_adl(adl)
        assert cfg.enums["Empty"].values == []

    def test_enum_with_annotations(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            @deprecated
            enum OldStatus { ACTIVE, INACTIVE }
        """
        )
        cfg = parse_adl(adl)
        assert any(a.name == "deprecated" for a in cfg.enums["OldStatus"].annotations)


# ===========================================================================
# Parser Tests — Relationships
# ===========================================================================


class TestRelationshipParsing:
    def test_one_to_many(self):
        cfg = parse_adl(FULL_JDL_ADL)
        otm = [r for r in cfg.relationships if r.kind == "OneToMany"]
        assert len(otm) == 1
        assert otm[0].from_end.entity == "User"
        assert otm[0].from_end.field == "posts"
        assert otm[0].to_end.entity == "Post"
        assert otm[0].to_end.field == "author"

    def test_many_to_many(self):
        cfg = parse_adl(FULL_JDL_ADL)
        mtm = [r for r in cfg.relationships if r.kind == "ManyToMany"]
        assert len(mtm) == 1
        assert mtm[0].from_end.entity == "KnowledgeNode"
        assert mtm[0].from_end.field == "tags"
        assert mtm[0].to_end.entity == "Tag"
        assert mtm[0].to_end.field == "nodes"

    def test_one_to_one(self):
        cfg = parse_adl(FULL_JDL_ADL)
        oto = [r for r in cfg.relationships if r.kind == "OneToOne"]
        assert len(oto) == 1
        assert oto[0].from_end.entity == "User"
        assert oto[0].to_end.entity == "KnowledgeNode"

    def test_relationship_without_fields(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            entity A { name String }
            entity B { name String }
            relationship OneToMany {
              A to B
            }
        """
        )
        cfg = parse_adl(adl)
        rel = cfg.relationships[0]
        assert rel.from_end.entity == "A"
        assert rel.from_end.field is None
        assert rel.to_end.entity == "B"
        assert rel.to_end.field is None

    def test_multiple_relationships_in_block(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            entity A { name String }
            entity B { name String }
            entity C { name String }
            relationship OneToMany {
              A{items} to B{parent}
              A{children} to C{root}
            }
        """
        )
        cfg = parse_adl(adl)
        assert len(cfg.relationships) == 2


# ===========================================================================
# Parser Tests — Pagination / DTO / Service Directives
# ===========================================================================


class TestDirectiveParsing:
    def test_paginate_multiple_entities(self):
        cfg = parse_adl(FULL_JDL_ADL)
        pag = [p for p in cfg.paginations if p.style == "pagination"]
        assert len(pag) == 1
        assert set(pag[0].entities) == {"Post", "KnowledgeNode"}

    def test_paginate_infinite_scroll(self):
        cfg = parse_adl(FULL_JDL_ADL)
        pag = [p for p in cfg.paginations if p.style == "infinite-scroll"]
        assert len(pag) == 1
        assert pag[0].entities == ["Tag"]

    def test_dto_wildcard(self):
        cfg = parse_adl(FULL_JDL_ADL)
        assert len(cfg.dtos) == 1
        assert cfg.dtos[0].entities == ["*"]
        assert cfg.dtos[0].mapper == "mapstruct"

    def test_service_all(self):
        cfg = parse_adl(FULL_JDL_ADL)
        assert len(cfg.services) == 1
        assert cfg.services[0].entities == ["all"]
        assert cfg.services[0].impl == "serviceImpl"

    def test_paginate_all_with_pager(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            entity X { name String }
            paginate all with pager
        """
        )
        cfg = parse_adl(adl)
        assert len(cfg.paginations) == 1
        assert cfg.paginations[0].entities == ["all"]
        assert cfg.paginations[0].style == "pager"


# ===========================================================================
# Parser Tests — Deployment
# ===========================================================================


class TestDeploymentParsing:
    def test_deployment_block(self):
        cfg = parse_adl(FULL_JDL_ADL)
        assert cfg.deployment is not None
        assert cfg.deployment.values["deploymentType"] == "docker-compose"
        assert cfg.deployment.values["dockerRepositoryName"] == "myrepo"

    def test_deployment_with_extra_options(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            deployment {
              deploymentType kubernetes
              dockerRepositoryName "ghcr.io/my-org"
              kubernetesNamespace brain
              ingressDomain "brain.example.com"
            }
        """
        )
        cfg = parse_adl(adl)
        d = cfg.deployment.values
        assert d["deploymentType"] == "kubernetes"
        assert d["kubernetesNamespace"] == "brain"


# ===========================================================================
# Generator Tests — Neo4j Schema
# ===========================================================================


class TestCypherSchemaGenerator:
    def test_generates_constraints_for_unique(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = Neo4jSchemaGenerator()
        schema = gen.generate(cfg)
        assert "tag_name_unique" in schema
        assert "IS UNIQUE" in schema

    def test_generates_constraints_for_required(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = Neo4jSchemaGenerator()
        schema = gen.generate(cfg)
        assert "IS NOT NULL" in schema

    def test_generates_fulltext_index(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            entity Doc {
              title String required searchable
              body String searchable
            }
        """
        )
        cfg = parse_adl(adl)
        gen = Neo4jSchemaGenerator()
        schema = gen.generate(cfg)
        assert "FULLTEXT INDEX" in schema
        assert "doc_fulltext" in schema

    def test_includes_relationship_comments(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = Neo4jSchemaGenerator()
        schema = gen.generate(cfg)
        assert ":User" in schema
        assert ":Post" in schema

    def test_includes_enum_comments(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = Neo4jSchemaGenerator()
        schema = gen.generate(cfg)
        assert "NodeType" in schema
        assert "DOCUMENT" in schema

    def test_migration_is_idempotent(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = Neo4jSchemaGenerator()
        migration = gen.generate_migration(cfg)
        assert "IF NOT EXISTS" in migration


# ===========================================================================
# Generator Tests — Python Models
# ===========================================================================


class TestPythonModelGenerator:
    def test_generates_all_entities(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        assert "class KnowledgeNode(BaseModel)" in code
        assert "class Tag(BaseModel)" in code
        assert "class User(BaseModel)" in code
        assert "class Post(BaseModel)" in code

    def test_generates_enums(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        assert "class NodeType(str, Enum)" in code
        assert 'DOCUMENT = "DOCUMENT"' in code

    def test_required_field_no_optional(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        # Tag.name is required, should not be Optional
        assert "    name: str" in code

    def test_optional_field(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        # KnowledgeNode.source is optional
        assert "Optional[str]" in code

    def test_field_constraints_in_code(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        assert "min_length=" in code
        assert "max_length=" in code

    def test_dto_generation(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        # dto * with mapstruct should generate DTOs for all entities
        assert "DTO(BaseModel)" in code

    def test_pagination_config_hint(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        assert 'pagination = "pagination"' in code

    def test_min_max_numeric_constraints(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = PythonModelGenerator()
        code = gen.generate(cfg)
        assert "ge=0" in code
        assert "le=100" in code


# ===========================================================================
# Generator Tests — API Routes
# ===========================================================================


class TestApiRouteGenerator:
    def test_generates_crud_routes(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ApiRouteGenerator()
        code = gen.generate(cfg)
        assert "create_knowledge_node" in code
        assert "list_knowledge_nodes" in code
        assert "get_knowledge_node" in code
        assert "delete_knowledge_node" in code

    def test_pagination_routes(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ApiRouteGenerator()
        code = gen.generate(cfg)
        # Post has pagination, should have page/size params
        assert "page: int" in code
        assert "size: int" in code

    def test_non_paginated_routes(self):
        cfg = parse_adl(MINIMAL_ENTITY_ADL)
        gen = ApiRouteGenerator()
        code = gen.generate(cfg)
        assert "skip: int" in code
        assert "limit: int" in code

    def test_router_prefixes(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ApiRouteGenerator()
        code = gen.generate(cfg)
        assert "/knowledge_nodes" in code
        assert "/tags" in code
        assert "/users" in code
        assert "/posts" in code


# ===========================================================================
# Generator Tests — React Components
# ===========================================================================


class TestReactComponentGenerator:
    def test_generates_list_component(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ReactComponentGenerator()
        code = gen.generate(cfg)
        assert "KnowledgeNodeList" in code
        assert "TagList" in code

    def test_generates_form_component(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ReactComponentGenerator()
        code = gen.generate(cfg)
        assert "KnowledgeNodeForm" in code
        assert "TagForm" in code

    def test_accessibility_labels(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ReactComponentGenerator()
        code = gen.generate(cfg)
        assert "aria-label" in code
        assert 'scope="col"' in code

    def test_required_fields_marked(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ReactComponentGenerator()
        code = gen.generate(cfg)
        assert "required" in code

    def test_pagination_controls(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ReactComponentGenerator()
        code = gen.generate(cfg)
        # Post has pagination
        assert "Previous page" in code or "pagination" in code

    def test_semantic_html(self):
        cfg = parse_adl(FULL_JDL_ADL)
        gen = ReactComponentGenerator()
        code = gen.generate(cfg)
        assert "<table" in code
        assert "<thead>" in code
        assert "<form" in code


# ===========================================================================
# Integration Tests — Full Pipeline
# ===========================================================================


class TestIntegration:
    def test_full_parse_and_generate_all(self):
        """Parse a full ADL and generate all four artefact types."""
        cfg = parse_adl(FULL_JDL_ADL)

        neo4j = Neo4jSchemaGenerator().generate(cfg)
        python = PythonModelGenerator().generate(cfg)
        api = ApiRouteGenerator().generate(cfg)
        react = ReactComponentGenerator().generate(cfg)

        # All should produce non-empty output
        assert len(neo4j) > 100
        assert len(python) > 100
        assert len(api) > 100
        assert len(react) > 100

    def test_roundtrip_entity_names(self):
        """Entity names should appear in all generators."""
        cfg = parse_adl(FULL_JDL_ADL)
        for name in cfg.entities:
            neo4j = Neo4jSchemaGenerator().generate(cfg)
            python = PythonModelGenerator().generate(cfg)
            api = ApiRouteGenerator().generate(cfg)
            react = ReactComponentGenerator().generate(cfg)

            assert name in neo4j, f"{name} missing from Neo4j schema"
            assert name in python, f"{name} missing from Python models"

    def test_enum_values_in_python(self):
        """Enum values parsed should appear in generated Python."""
        cfg = parse_adl(FULL_JDL_ADL)
        python = PythonModelGenerator().generate(cfg)
        for val in cfg.enums["NodeType"].values:
            assert val in python

    def test_relationship_in_cypher_schema(self):
        """Relationships should generate Neo4j schema comments."""
        cfg = parse_adl(FULL_JDL_ADL)
        neo4j = Neo4jSchemaGenerator().generate(cfg)
        assert "User" in neo4j
        assert "Post" in neo4j
        assert "KnowledgeNode" in neo4j

    def test_directives_dont_break_parsing(self):
        """All directive types should parse cleanly."""
        cfg = parse_adl(FULL_JDL_ADL)
        assert len(cfg.paginations) == 2
        assert len(cfg.dtos) == 1
        assert len(cfg.services) == 1
        assert len(cfg.entities) == 4
        assert len(cfg.enums) == 2
        assert len(cfg.relationships) == 3


# ===========================================================================
# Error Handling
# ===========================================================================


class TestErrorHandling:
    def test_missing_entity_name(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            entity { name String }
        """
        )
        with pytest.raises(ADLParseError):
            parse_adl(adl)

    def test_unterminated_entity(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            entity Broken {
              name String
        """
        )
        with pytest.raises(ADLParseError):
            parse_adl(adl)

    def test_missing_relationship_to(self):
        adl = textwrap.dedent(
            """\
            application T { name "T" }
            llm P { provider ollama model "llama3.2:3b" }
            relationship OneToMany {
              A B
            }
        """
        )
        with pytest.raises(ADLParseError):
            parse_adl(adl)
