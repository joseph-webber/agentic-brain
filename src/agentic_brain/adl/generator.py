# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""ADL configuration generator.

Takes a parsed :class:`ADLConfig` and materialises concrete runtime
configuration for Agentic Brain:

* Python config module (``adl_config.py``)
* ``.env`` entries derived from ADL
* ``docker-compose.yml`` skeleton
* Optional FastAPI entrypoint with ADL-aware defaults

The generator is intentionally conservative:

* It **never overwrites** existing files unless ``overwrite=True``.
* It keeps the generated code small and explicit so that users can
  inspect and customise the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List

from .parser import ADLConfig, parse_adl_file


@dataclass
class ADLGenerationResult:
    """Summary of generated artefacts."""

    config_module: Path
    env_file: Path
    docker_compose: Path
    api_module: Path


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _collect_env_from_adl(cfg: ADLConfig) -> Dict[str, str]:
    """Map ADL config → runtime environment variables.

    ADL parsing already applied defaults, so this always produces a runnable
    baseline configuration.
    """

    env: Dict[str, str] = {}

    # Application
    app = cfg.application.values if cfg.application else {}
    env.setdefault("APP_NAME", str(app.get("name", "Agentic Brain")))
    env.setdefault("APP_VERSION", str(app.get("version", "1.0.0")))
    env.setdefault("APP_LICENSE", str(app.get("license", "Apache-2.0")))
    if "persona" in app:
        env.setdefault("APP_PERSONA", str(app["persona"]))

    # LLM (primary)
    primary_llm = next(iter(cfg.llms.values()), None)
    if primary_llm is not None:
        llm_vals = primary_llm.values
        provider = str(llm_vals.get("provider", "auto")).strip().lower()
        model = str(llm_vals.get("model", "llama3.2:3b")).strip()

        env.setdefault("LLM_DEFAULT_PROVIDER", provider)
        env.setdefault("LLM_DEFAULT_MODEL", model)

        base_url = llm_vals.get("baseUrl") or llm_vals.get("baseURL")
        if base_url:
            env.setdefault("OLLAMA_HOST", str(base_url))

    # RAG (only emit env when enabled)
    primary_rag = next(iter(cfg.rags.values()), None)
    if primary_rag is not None:
        rag_vals = primary_rag.values
        rag_enabled = bool(rag_vals.get("enabled", False))
        if rag_enabled:
            vector_store = rag_vals.get("vectorStore")
            if vector_store:
                env.setdefault("RAG_VECTOR_STORE", str(vector_store))
            embedding_model = rag_vals.get("embeddingModel")
            if embedding_model:
                env.setdefault("RAG_EMBEDDING_MODEL", str(embedding_model))
            if "chunkSize" in rag_vals:
                env.setdefault("RAG_CHUNK_SIZE", str(int(rag_vals["chunkSize"])))
            if "chunkOverlap" in rag_vals:
                env.setdefault("RAG_CHUNK_OVERLAP", str(int(rag_vals["chunkOverlap"])))
            loaders = rag_vals.get("loaders")
            if isinstance(loaders, list):
                env.setdefault("RAG_LOADERS", ",".join(str(x) for x in loaders))

    # Voice
    primary_voice = next(iter(cfg.voices.values()), None)
    if primary_voice is not None:
        v = primary_voice.values
        env.setdefault(
            "AGENTIC_BRAIN_VOICE_ENABLED",
            "true" if bool(v.get("enabled", True)) else "false",
        )
        if "defaultVoice" in v:
            env.setdefault("AGENTIC_BRAIN_VOICE", str(v["defaultVoice"]))
        if "rate" in v:
            env.setdefault("AGENTIC_BRAIN_RATE", str(int(v["rate"])))
        if "provider" in v:
            env.setdefault("AGENTIC_BRAIN_VOICE_PROVIDER", str(v["provider"]).lower())

    # API
    primary_api = next(iter(cfg.apis.values()), None)
    if primary_api is not None:
        a = primary_api.values
        env.setdefault(
            "API_ENABLED", "true" if bool(a.get("enabled", True)) else "false"
        )
        if "port" in a:
            env.setdefault("SERVER_PORT", str(int(a["port"])))

        cors = a.get("cors")
        if isinstance(cors, bool):
            env.setdefault("SECURITY_CORS_ORIGINS", "*" if cors else "")
        elif isinstance(cors, list) and cors:
            env.setdefault("SECURITY_CORS_ORIGINS", ",".join(str(x) for x in cors))

    # Security
    if cfg.security is not None:
        s = cfg.security.values
        env.setdefault(
            "SECURITY_AUTH_ENABLED",
            "true" if bool(s.get("auth", False)) else "false",
        )
        env.setdefault(
            "SECURITY_RATE_LIMIT_ENABLED",
            "true" if bool(s.get("rateLimit", True)) else "false",
        )

    return env


def _merge_env_file(
    env_path: Path, new_env: Dict[str, str], *, preserve_existing: bool = True
) -> None:
    existing: Dict[str, str] = {}
    if preserve_existing and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            existing[key.strip()] = value.strip()

    merged = dict(existing)
    for k, v in new_env.items():
        merged.setdefault(k, v)

    lines = [
        "# Generated from ADL by agentic-brain",
        "# Existing values are preserved; new keys appended below.",
    ]
    for key, value in sorted(merged.items()):
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_python_config(config_path: Path, cfg: ADLConfig) -> None:
    _ensure_parent(config_path)

    def _ann_list(anns) -> list[dict[str, Any]]:
        return [
            {"name": a.name, "args": list(getattr(a, "args", []) or [])}
            for a in (anns or [])
        ]

    application = cfg.application.values if cfg.application else {}
    application_annotations = (
        _ann_list(cfg.application.annotations) if cfg.application else []
    )

    deployment = cfg.deployment.values if cfg.deployment else {}
    deployment_annotations = (
        _ann_list(cfg.deployment.annotations) if cfg.deployment else []
    )

    # Process all LLMs
    llms_dict: Dict[str, Any] = {}
    llm_annotations: Dict[str, List[Dict[str, Any]]] = {}
    for name, block in cfg.llms.items():
        llms_dict[name] = block.values
        llm_annotations[name] = _ann_list(block.annotations)

    # Process all Voices
    voices_dict: Dict[str, Any] = {}
    voice_annotations: Dict[str, List[Dict[str, Any]]] = {}
    for name, block in cfg.voices.items():
        voices_dict[name] = block.values
        voice_annotations[name] = _ann_list(block.annotations)

    # Modelling constructs
    enums_dict: Dict[str, Any] = {
        name: {"values": e.values, "annotations": _ann_list(e.annotations)}
        for name, e in cfg.enums.items()
    }

    entities_dict: Dict[str, Any] = {}
    for name, e in cfg.entities.items():
        entities_dict[name] = {
            "annotations": _ann_list(e.annotations),
            "fields": [
                {
                    "name": f.name,
                    "type": f.type,
                    "annotations": _ann_list(f.annotations),
                    "validators": [
                        {"name": v.name, "args": list(getattr(v, "args", []) or [])}
                        for v in (f.validators or [])
                    ],
                }
                for f in e.fields
            ],
        }

    relationships_list: List[Dict[str, Any]] = []
    for r in cfg.relationships:
        relationships_list.append(
            {
                "kind": r.kind,
                "from": {"entity": r.from_end.entity, "field": r.from_end.field},
                "to": {"entity": r.to_end.entity, "field": r.to_end.field},
                "options": list(r.options or []),
                "annotations": _ann_list(r.annotations),
            }
        )

    primary_llm_name = next(iter(cfg.llms.keys()), None)
    primary_llm = cfg.llms[primary_llm_name].values if primary_llm_name else {}

    primary_voice_name = next(iter(cfg.voices.keys()), None)
    primary_voice = cfg.voices[primary_voice_name].values if primary_voice_name else {}

    primary_rag_name, primary_rag = next(iter(cfg.rags.items()), (None, None))
    primary_api_name, primary_api = next(iter(cfg.apis.items()), (None, None))

    text = f"""# Auto-generated by agentic-brain from ADL.
# Source: brain.adl (or custom path)

from __future__ import annotations

from typing import Any, Dict, Optional, List

from agentic_brain.router.config import Provider, RouterConfig, LLMConfig
from agentic_brain.rag.graph_rag import GraphRAGConfig
from agentic_brain.voice.config import VoiceConfig, VoiceQuality
from agentic_brain.config.settings import Settings


APPLICATION: Dict[str, Any] = {application!r}
APPLICATION_ANNOTATIONS: List[Dict[str, Any]] = {application_annotations!r}

DEPLOYMENT: Dict[str, Any] = {deployment!r}
DEPLOYMENT_ANNOTATIONS: List[Dict[str, Any]] = {deployment_annotations!r}

LLMS: Dict[str, Any] = {llms_dict!r}
LLM_ANNOTATIONS: Dict[str, List[Dict[str, Any]]] = {llm_annotations!r}

VOICES: Dict[str, Any] = {voices_dict!r}
VOICE_ANNOTATIONS: Dict[str, List[Dict[str, Any]]] = {voice_annotations!r}

ENUMS: Dict[str, Any] = {enums_dict!r}
ENTITIES: Dict[str, Any] = {entities_dict!r}
RELATIONSHIPS: List[Dict[str, Any]] = {relationships_list!r}

PRIMARY_LLM_NAME: Optional[str] = {primary_llm_name!r}
PRIMARY_LLM: Dict[str, Any] = {primary_llm!r}

PRIMARY_RAG_NAME: Optional[str] = {primary_rag_name!r}
PRIMARY_RAG: Dict[str, Any] = {primary_rag.values if primary_rag else {}!r}

PRIMARY_VOICE_NAME: Optional[str] = {primary_voice_name!r}
PRIMARY_VOICE: Dict[str, Any] = {primary_voice!r}

PRIMARY_API_NAME: Optional[str] = {primary_api_name!r}
PRIMARY_API: Dict[str, Any] = {primary_api.values if primary_api else {}!r}


def create_router_config() -> RouterConfig:
    "Create RouterConfig from the ADL LLM blocks."

    base = RouterConfig()

    # 1. Set defaults from Primary LLM
    if PRIMARY_LLM:
        data = PRIMARY_LLM
        provider_str = str(data.get("provider", base.default_provider.value)).lower()
        # Simple mapping or use Enum
        try:
            base.default_provider = Provider(provider_str)
        except ValueError:
            pass

        base.default_model = str(data.get("model", base.default_model))

        base_url = data.get("baseUrl") or data.get("baseURL")
        if base_url:
            base.ollama_host = str(base_url)

    # 2. Populate models dict
    for name, data in LLMS.items():
        provider_str = str(data.get("provider", "ollama")).lower()
        try:
            provider = Provider(provider_str)
        except ValueError:
            provider = Provider.OLLAMA # fallback

        model_name = str(data.get("model", "unknown"))

        config = LLMConfig(
            provider=provider.value,
            model=model_name,
            base_url=data.get("baseUrl") or data.get("baseURL"),
            api_key=data.get("apiKey"),
            temperature=float(data.get("temperature", 0.7)),
            max_tokens=int(data.get("maxTokens", 4096)) if "maxTokens" in data else None,
            fallback=str(data.get("fallback")) if "fallback" in data else None
        )
        base.models[name] = config

    return base


def create_graph_rag_config() -> GraphRAGConfig:
    "Create GraphRAGConfig from the primary ADL RAG block."

    base = GraphRAGConfig()
    return base


def create_voice_config() -> VoiceConfig:
    "Create VoiceConfig from the primary ADL voice block."

    base = VoiceConfig()
    data = PRIMARY_VOICE or {{}}

    if "defaultVoice" in data:
        base.voice_name = str(data["defaultVoice"])
    if "rate" in data:
        try:
            base.rate = int(data["rate"])
        except Exception:
            pass
    if "provider" in data:
        base.provider = str(data["provider"]).lower()

    # Extra fields
    if "regional" in data and isinstance(data["regional"], dict):
        base.regional_map = {{str(k): str(v) for k, v in data["regional"].items()}}

    if "robotVoices" in data and isinstance(data["robotVoices"], list):
        base.robot_voices = [str(v) for v in data["robotVoices"]]

    if "fallbackVoice" in data:
        base.fallback_voice = str(data["fallbackVoice"])

    return base


def apply_api_settings(settings: Settings) -> Settings:
    'Apply ADL API settings onto Settings instance.'

    data = PRIMARY_API or {{}}
    if "port" in data:
        try:
            settings.server.port = int(data["port"])
        except Exception:
            pass
    cors = data.get("cors")
    if isinstance(cors, list) and cors:
        settings.security.cors_origins = [str(x) for x in cors]
    return settings
"""
    config_path.write_text(dedent(text), encoding="utf-8")


def _write_docker_compose(path: Path, cfg: ADLConfig) -> None:
    _ensure_parent(path)

    env = _collect_env_from_adl(cfg)
    dep = cfg.deployment.values if cfg.deployment else {}

    def _as_bool(value: object, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "enabled", "yes", "1"}

    compose_version = str(dep.get("composeVersion", "3.8"))
    service_name = str(dep.get("serviceName", "agentic-brain"))
    image = str(dep.get("image") or "")
    if not image:
        repo = dep.get("dockerRepositoryName")
        image = f"{repo}/{service_name}:latest" if repo else "agentic-brain:latest"
    restart = str(dep.get("restart", "unless-stopped"))

    port = dep.get("apiPort", env.get("SERVER_PORT", "8000"))
    try:
        port = str(int(port))
    except Exception:
        port = str(port)

    llm_provider = env.get("LLM_DEFAULT_PROVIDER", "auto")
    llm_model = env.get("LLM_DEFAULT_MODEL", "llama3.2:3b")
    ollama_host = (
        dep.get("ollamaApiBase")
        or env.get("OLLAMA_HOST")
        or "http://host.docker.internal:11434"
    )

    # RAG/Neo4j optional by default
    primary_rag = next(iter(cfg.rags.values()), None)
    rag_vals = primary_rag.values if primary_rag is not None else {}
    rag_enabled = bool(rag_vals.get("enabled", False))
    vector_store = str(rag_vals.get("vectorStore", "memory")).strip().lower()
    needs_neo4j = rag_enabled and vector_store == "neo4j"

    neo4j_service = str(dep.get("neo4jServiceName", "neo4j"))
    neo4j_image = str(dep.get("neo4jImage", "neo4j:5"))
    neo4j_password_default = str(dep.get("neo4jPasswordDefault", "change-me"))
    publish_neo4j_ports = _as_bool(dep.get("publishNeo4jPorts"), True)

    try:
        neo4j_browser_port = int(dep.get("neo4jBrowserPort", 7474))
    except Exception:
        neo4j_browser_port = 7474
    try:
        neo4j_bolt_port = int(dep.get("neo4jBoltPort", 7687))
    except Exception:
        neo4j_bolt_port = 7687

    neo4j_auth = dep.get(
        "neo4jAuth",
        f"neo4j/${{NEO4J_PASSWORD:-{neo4j_password_default}}}",
    )

    neo4j_ports = ""
    if needs_neo4j and publish_neo4j_ports:
        neo4j_ports = (
            "    ports:\\n"
            f'      - \\"{neo4j_browser_port}:{neo4j_browser_port}\\"\\n'
            f'      - \\"{neo4j_bolt_port}:{neo4j_bolt_port}\\"\\n'
        )

    env_lines = [
        f"      - LLM_DEFAULT_PROVIDER={llm_provider}",
        f"      - LLM_DEFAULT_MODEL={llm_model}",
        f"      - OLLAMA_HOST={ollama_host}",
        f"      - SERVER_PORT={port}",
        f"      - AGENTIC_BRAIN_VOICE={env.get('AGENTIC_BRAIN_VOICE', 'auto')}",
        f"      - AGENTIC_BRAIN_VOICE_ENABLED={env.get('AGENTIC_BRAIN_VOICE_ENABLED', 'true')}",
    ]

    cors_val = env.get("SECURITY_CORS_ORIGINS")
    if cors_val is not None:
        env_lines.append(f"      - SECURITY_CORS_ORIGINS={cors_val}")

    if needs_neo4j:
        env_lines.extend(
            [
                f"      - NEO4J_URI=bolt://{neo4j_service}:7687",
                "      - NEO4J_USER=neo4j",
                f"      - NEO4J_PASSWORD=${{NEO4J_PASSWORD:-{neo4j_password_default}}}",
            ]
        )

    depends_on = f"\n    depends_on:\n      - {neo4j_service}\n" if needs_neo4j else ""

    neo4j_block = ""
    if needs_neo4j:
        neo4j_block = f"""

  {neo4j_service}:
    image: {neo4j_image}
    restart: {restart}
    environment:
      - NEO4J_AUTH={neo4j_auth}
{neo4j_ports}"""

    service_env = "\n".join(env_lines)

    text = f"""# Auto-generated docker-compose for Agentic Brain (ADL)
version: '{compose_version}'

services:
  {service_name}:
    image: {image}
    restart: {restart}
    environment:
{service_env}
    ports:
      - \"{port}:{port}\"{depends_on}{neo4j_block}
"""

    path.write_text(text, encoding="utf-8")


def _write_api_module(path: Path, cfg: ADLConfig) -> None:
    _ensure_parent(path)
    app_vals = cfg.application.values if cfg.application else {}
    api_vals = next(iter(cfg.apis.values())).values if cfg.apis else {}
    title = app_vals.get("name", "Agentic Brain API")
    version = app_vals.get("version", "1.0.0")

    cors_val = api_vals.get("cors", ["*"])
    if isinstance(cors_val, bool):
        cors = ["*"] if cors_val else []
    elif isinstance(cors_val, list):
        cors = cors_val
    else:
        cors = ["*"]

    text = f"""# Auto-generated FastAPI entrypoint from ADL.

from __future__ import annotations

from fastapi import FastAPI

from agentic_brain.api.server import create_app as _create_app


def create_adl_app() -> FastAPI:
    'Create a FastAPI app using ADL defaults.'

    cors_origins = {cors!r}
    return _create_app(
        title={title!r},
        version={version!r},
        cors_origins=cors_origins,
    )


app = create_adl_app()
"""
    path.write_text(dedent(text), encoding="utf-8")


def generate_config_from_adl(
    cfg: ADLConfig,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> ADLGenerationResult:
    """Generate config artefacts from a parsed ADL config."""

    config_module = output_dir / "adl_config.py"
    env_file = output_dir / ".env"
    docker_compose = output_dir / "docker-compose.yml"
    api_module = output_dir / "adl_api.py"

    if not config_module.exists() or overwrite:
        _write_python_config(config_module, cfg)

    env = _collect_env_from_adl(cfg)
    if env and (not env_file.exists() or overwrite):
        _merge_env_file(env_file, env, preserve_existing=not overwrite)

    if not docker_compose.exists() or overwrite:
        _write_docker_compose(docker_compose, cfg)

    if not api_module.exists() or overwrite:
        _write_api_module(api_module, cfg)

    return ADLGenerationResult(
        config_module=config_module,
        env_file=env_file,
        docker_compose=docker_compose,
        api_module=api_module,
    )


def generate_from_adl(
    adl_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> ADLGenerationResult:
    """Generate config artefacts from an ADL file.

    Args:
        adl_path: Path to the ``.adl`` file
        output_dir: Directory for generated artefacts (defaults to ADL directory)
        overwrite: If ``True``, existing files will be replaced

    Returns:
        :class:`ADLGenerationResult` describing generated paths.
    """

    adl_path = Path(adl_path)
    cfg = parse_adl_file(adl_path)

    base_dir = Path(output_dir) if output_dir is not None else adl_path.parent

    config_module = base_dir / "adl_config.py"
    env_file = base_dir / ".env"
    docker_compose = base_dir / "docker-compose.yml"
    api_module = base_dir / "adl_api.py"

    if not config_module.exists() or overwrite:
        _write_python_config(config_module, cfg)

    env = _collect_env_from_adl(cfg)
    if env and (not env_file.exists() or overwrite):
        _merge_env_file(env_file, env, preserve_existing=not overwrite)

    if not docker_compose.exists() or overwrite:
        _write_docker_compose(docker_compose, cfg)

    if not api_module.exists() or overwrite:
        _write_api_module(api_module, cfg)

    return ADLGenerationResult(
        config_module=config_module,
        env_file=env_file,
        docker_compose=docker_compose,
        api_module=api_module,
    )
