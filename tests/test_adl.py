# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
import textwrap
from pathlib import Path

from agentic_brain.adl import ADLConfig, generate_from_adl, parse_adl

EXAMPLE_ADL = textwrap.dedent(
    """\
    // brain.adl - Configure your AI brain

    application AgenticBrain {
      name "My Enterprise AI"
      version "1.0.0"
      license Apache-2.0
    }

    llm Primary {
      provider OpenAI
      model gpt-4o
      temperature 0.7
      maxTokens 4096
      fallback Local
    }

    rag KnowledgeBase {
      enabled true
      vectorStore Neo4j
      embeddingModel "sentence-transformers/all-MiniLM-L6-v2"
      chunkSize 512
      chunkOverlap 50

      loaders [
        PDF, Markdown, Code, JIRA, Confluence, Slack
      ]
    }

    voice Assistant {
      provider system
      defaultVoice "auto"
      rate 155
      fallbackVoice "Daniel"
    }

    api REST {
      port 8000
      cors ["*"]
    }

    security {
      authentication JWT
      sso [Google, Microsoft, GitHub]
      saml enabled
      rateLimit strict
    }
    """
)


def test_parse_example_adl() -> None:
    cfg = parse_adl(EXAMPLE_ADL)
    assert isinstance(cfg, ADLConfig)
    assert cfg.application is not None
    assert cfg.application.values["name"] == "My Enterprise AI"

    assert "Primary" in cfg.llms
    primary = cfg.llms["Primary"].values
    assert primary["provider"] == "OpenAI"
    assert primary["model"] == "gpt-4o"

    assert cfg.security is not None
    assert cfg.security.values["authentication"] == "JWT"


def test_generate_from_adl(tmp_path: Path) -> None:
    adl_path = tmp_path / "brain.adl"
    adl_path.write_text(EXAMPLE_ADL, encoding="utf-8")

    result = generate_from_adl(adl_path)

    assert result.config_module.exists()
    assert result.env_file.exists()
    assert result.docker_compose.exists()
    assert result.api_module.exists()

    env_text = result.env_file.read_text(encoding="utf-8")
    assert "LLM_DEFAULT_MODEL=gpt-4o" in env_text
    assert (
        "APP_NAME=My Enterprise AI" in env_text
        or 'APP_NAME="My Enterprise AI"' in env_text
    )


def test_parse_modelling_blocks_and_annotations() -> None:
    adl = textwrap.dedent(
        """\
        @priority(high)
        llm Primary {
          provider OpenAI
        }

        enum SourceType {
          DATABASE, API, FILE, STREAM
        }

        entity KnowledgeSource {
          name String required
          type SourceType
          url String
          refreshInterval Duration
        }

        relationship OneToMany {
          Agent{sources} to KnowledgeSource
        }

        deployment {
          deploymentType docker-compose
          dockerRepositoryName "mycompany"
          kubernetesNamespace ai-brain
        }
        """
    )

    cfg = parse_adl(adl)

    assert cfg.llms["Primary"].annotations
    assert cfg.llms["Primary"].annotations[0].name == "priority"
    assert cfg.llms["Primary"].annotations[0].args == ["high"]

    assert "SourceType" in cfg.enums
    assert cfg.enums["SourceType"].values == ["DATABASE", "API", "FILE", "STREAM"]

    assert "KnowledgeSource" in cfg.entities
    entity = cfg.entities["KnowledgeSource"]
    assert [f.name for f in entity.fields] == ["name", "type", "url", "refreshInterval"]
    name_field = entity.fields[0]
    assert name_field.type == "String"
    assert any(v.name == "required" for v in name_field.validators)

    assert cfg.relationships
    rel = cfg.relationships[0]
    assert rel.kind == "OneToMany"
    assert rel.from_end.entity == "Agent"
    assert rel.from_end.field == "sources"
    assert rel.to_end.entity == "KnowledgeSource"

    assert cfg.deployment is not None
    assert cfg.deployment.values["deploymentType"] == "docker-compose"
    assert cfg.deployment.values["dockerRepositoryName"] == "mycompany"
    assert cfg.deployment.values["kubernetesNamespace"] == "ai-brain"
