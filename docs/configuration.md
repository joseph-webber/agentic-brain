# Configuration

Agentic Brain uses a layered, Pydantic-validated config system.

## Load order

Highest priority wins:

1. Environment variables
2. `.env` / `.env.<profile>` files
3. YAML or TOML config file
4. Profile defaults
5. Built-in defaults

## Profiles

Built-in profiles live in `src/agentic_brain/config/profiles.py`:

- `development`
- `staging`
- `production`
- `testing`
- `custom`

Example:

```python
from agentic_brain.config import CustomProfile, Settings

settings = Settings.from_sources(
    profile=CustomProfile(
        name="eu-ops",
        defaults={"server": {"port": 9010}},
    )
)
```

## YAML / TOML config

Use either `brain-config.yaml` or `brain-config.toml`.

```yaml
profile: development
app_name: Agentic Brain
server:
  port: 8000
  cors_origins:
    - http://localhost:3000
```

The loader also accepts the legacy `api:` section and normalizes it to `server:`.

## Environment files

`Settings.from_sources()` looks for:

- `.env`
- `.env.<profile>`

You can also pass `env_file=` explicitly.

## Common env vars

- `BRAIN_PROFILE`
- `BRAIN_CONFIG_FILE`
- `BRAIN_ENV_FILE`
- `APP_NAME`
- `SERVER_PORT`
- `NEO4J_URI`
- `LLM_DEFAULT_MODEL`
- `VOICE_RATE`
- `SECURITY_JWT_SECRET`
- `CACHE_BACKEND`

## Validation

Validation is strict:

- invalid URIs fail
- invalid ports fail
- invalid log levels fail
- production rejects weak JWT secrets and wildcard CORS

## Python usage

```python
from agentic_brain.config import get_settings

settings = get_settings()
print(settings.server.port)
```

## Notes

- `CORS_ORIGINS` populates both server and security allow-lists.
- Use `env_file=Path("/nonexistent")` in tests when you want to skip file loading.
