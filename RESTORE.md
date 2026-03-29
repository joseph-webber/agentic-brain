# Agentic Brain Restore Guide

Use this guide to recover a self-hosted Agentic Brain installation after a crash, failed deploy, host loss, or corrupted database. It is written for public release and assumes you have the repository plus a backup of your data and configuration.

> Scope: Docker Compose recovery for the default self-hosted stack. The same process also works for the dev and production Compose profiles if you use the correct file and Neo4j service name.

## Before You Start

Work from the repository root and choose the Compose profile you are restoring:

| Profile | Compose file | Env file | Neo4j service |
| --- | --- | --- | --- |
| Default stack | `docker-compose.yml` | `.env.docker` | `neo4j` |
| Dev infra only | `docker/docker-compose.dev.yml` | `.env.dev` | `neo4j-dev` |
| Production profile | `docker/docker-compose.prod.yml` | `.env.docker` | `neo4j-prod` |

Export the profile you want to use:

```bash
# Default stack (recommended starting point)
export COMPOSE_FILE=docker-compose.yml
export ENV_FILE=.env.docker
export NEO4J_SERVICE=neo4j
export APP_SERVICE=agentic-brain

set -a
source "$ENV_FILE"
set +a
```

If you are restoring a different profile, change those three variables first.

---

## 1. EMERGENCY RECOVERY CHECKLIST

If the brain crashes and you need the fastest path back:

1. **Do not delete volumes yet.** Avoid `docker compose down -v` unless you have already decided to replace data from backup.
2. **Check container state.**
   ```bash
   docker compose -f "$COMPOSE_FILE" ps
   ```
3. **Check recent logs.**
   ```bash
   docker compose -f "$COMPOSE_FILE" logs --tail=200
   ```
4. **Try the app health endpoint.**
   ```bash
   curl -fsS http://localhost:8000/health || true
   curl -fsS http://localhost:8000/infra/health || true
   ```
5. **Restart the stack without wiping data.**
   ```bash
   docker compose -f "$COMPOSE_FILE" down
   docker compose -f "$COMPOSE_FILE" up -d
   ```
6. **Re-check health.**
   ```bash
   docker compose -f "$COMPOSE_FILE" ps
   curl -fsS http://localhost:8000/health || true
   ```
7. **If Neo4j is unhealthy or data is missing/corrupt, stop here and do the full restore below.**

Quick rule of thumb:
- **App down, database healthy** -> restart services.
- **Neo4j auth, corruption, or missing graph data** -> restore Neo4j from backup.
- **App boots but config is wrong** -> restore config only.

---

## 2. FULL RESTORE FROM BACKUP

A full recovery restores:
- Neo4j graph data
- environment/config files
- optional app extras such as plugin config or voice cache

### Step 1: Recreate the codebase

```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
```

If you already have the repo, update it to the version you want to restore.

### Step 2: Restore configuration

Restore your backed-up config files first. At minimum, you need the env file for your chosen profile.

Recommended files to restore if you have them:
- `.env.docker`
- `.env.dev`
- `.env`
- `plugins.yaml`
- any Compose override files you created

If you do **not** have a config backup, recreate it from the shipped examples:

```bash
cp .env.docker.example .env.docker
# or, for dev only:
# cp .env.dev.example .env.dev
```

Then set the required values:

```bash
# Required for the default stack
# - NEO4J_PASSWORD
# - REDIS_PASSWORD
# - JWT_SECRET
```

Optional provider keys such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GROQ_API_KEY` can be added later.

### Step 3: Load the env file into your shell

```bash
set -a
source "$ENV_FILE"
set +a
```

### Step 4: Place backups in predictable locations

A clean layout is:

```text
backups/
├── neo4j/
│   ├── neo4j.dump
│   └── neo4j-data/        # optional raw /data snapshot instead of a dump
├── config/
│   ├── .env.docker
│   └── plugins.yaml
└── voice-cache/
```

This guide assumes your Neo4j backup is either:
- a **dump file** created with `neo4j-admin database dump`, or
- a **raw `/data` snapshot** taken while Neo4j was stopped.

### Step 5: Stop the stack

```bash
docker compose -f "$COMPOSE_FILE" down
```

### Step 6: Restore Neo4j

#### Preferred: restore from `neo4j.dump`

```bash
docker compose -f "$COMPOSE_FILE" run --rm \
  -v "$(pwd)/backups/neo4j:/backups:ro" \
  "$NEO4J_SERVICE" \
  bash -lc 'rm -rf /data/databases/* /data/transactions/* && neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true'
```

#### Alternative: restore from a raw `/data` snapshot

Use this only if your backup contains the full Neo4j data directory and was captured with Neo4j offline.

```bash
docker compose -f "$COMPOSE_FILE" run --rm \
  -v "$(pwd)/backups/neo4j/neo4j-data:/restore:ro" \
  "$NEO4J_SERVICE" \
  bash -lc 'rm -rf /data/* && cp -a /restore/. /data/'
```

### Step 7: Restore config files from backup if needed

```bash
cp backups/config/.env.docker .env.docker 2>/dev/null || true
cp backups/config/.env.dev .env.dev 2>/dev/null || true
cp backups/config/.env .env 2>/dev/null || true
cp backups/config/plugins.yaml plugins.yaml 2>/dev/null || true
```

### Step 8: Restore optional voice cache

Agentic Brain can run **without** a voice cache. If you persist generated audio or pre-rendered voice assets, restore them now to the same path your deployment uses.

Common self-hosted layout:

```bash
mkdir -p data/voice-cache
cp -R backups/voice-cache/. data/voice-cache/ 2>/dev/null || true
```

If your deployment uses a different path or Docker volume, copy the files there instead and keep the mount path unchanged.

### Step 9: Bring the stack back up

```bash
docker compose -f "$COMPOSE_FILE" up -d
```

### Step 10: Verify the restore

Go straight to the verification section below.

---

## 3. PARTIAL RECOVERY

### Restore just Neo4j

Use this when the app code and env files are fine but the graph is damaged or empty.

```bash
docker compose -f "$COMPOSE_FILE" down
set -a; source "$ENV_FILE"; set +a

docker compose -f "$COMPOSE_FILE" run --rm \
  -v "$(pwd)/backups/neo4j:/backups:ro" \
  "$NEO4J_SERVICE" \
  bash -lc 'rm -rf /data/databases/* /data/transactions/* && neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true'

docker compose -f "$COMPOSE_FILE" up -d
```

### Restore just config

Use this when the graph is intact but the app is failing because a secret, endpoint, or feature flag changed.

```bash
cp backups/config/.env.docker .env.docker   # adjust for your profile
cp backups/config/.env .env 2>/dev/null || true
cp backups/config/plugins.yaml plugins.yaml 2>/dev/null || true

docker compose -f "$COMPOSE_FILE" up -d --force-recreate
```

Typical config problems fixed by this path:
- wrong `NEO4J_PASSWORD`
- wrong `REDIS_PASSWORD`
- missing `JWT_SECRET`
- bad LLM provider keys
- missing plugin config

### Restore just voice cache

Use this only if your voice layer depends on pre-generated assets. If not, skip it.

```bash
mkdir -p data/voice-cache
cp -R backups/voice-cache/. data/voice-cache/
```

After restoring the cache, restart the app service:

```bash
docker compose -f "$COMPOSE_FILE" restart "$APP_SERVICE"
```

If your profile does not define the default `agentic-brain` service name, set `APP_SERVICE` first and restart that service instead.

---

## 4. VERIFICATION

Run these checks after any restore.

### A. Container health

```bash
docker compose -f "$COMPOSE_FILE" ps
```

You want the core services to be `Up` and, where supported, `healthy`.

### B. API health checks

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/infra/health
curl -fsS http://localhost:8000/infra/health/neo4j
```

Expected result:
- `/health` returns HTTP 200 and `"status": "healthy"`
- `/infra/health` shows healthy Redis, Neo4j, and Redpanda when those services are part of your profile

### C. Neo4j connectivity

```bash
set -a; source "$ENV_FILE"; set +a

docker compose -f "$COMPOSE_FILE" exec "$NEO4J_SERVICE" \
  cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1 AS ok"

docker compose -f "$COMPOSE_FILE" exec "$NEO4J_SERVICE" \
  cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "MATCH (n) RETURN count(n) AS total_nodes"
```

### D. Redis and Redpanda checks

Default stack:

```bash
docker compose -f "$COMPOSE_FILE" exec redis redis-cli -a "$REDIS_PASSWORD" ping
docker compose -f "$COMPOSE_FILE" exec redpanda rpk cluster health
```

Dev profile does not include Redpanda in `docker/docker-compose.dev.yml`, so skip that check there.

### E. Functional smoke test

```bash
curl -fsS http://localhost:8000/docs > /dev/null
curl -fsS http://localhost:8000/healthz
```

If all of the above pass and your node count looks correct, the restore worked.

---

## 5. COMMON ISSUES

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `docker compose up` starts but `/health` returns 503 | One dependency is still unhealthy | Run `curl http://localhost:8000/infra/health` and inspect the failing service |
| `Neo.ClientError.Security.Unauthorized` | `NEO4J_PASSWORD` in the env file does not match the restored database | Fix the env file, then restart the stack |
| Neo4j restores but graph is empty | Wrong backup artifact or wrong database loaded | Re-run the restore with the correct `neo4j.dump`; verify with `MATCH (n) RETURN count(n)` |
| `database load` fails because destination exists | Old database files still present | Make sure the restore command includes `--overwrite-destination=true` and that the stack is down |
| `Permission denied` inside `/data` | Snapshot copied with wrong ownership or host permissions | Re-run using the one-off container commands in this guide so Docker writes through the service volume |
| Redis is unhealthy after restore | `REDIS_PASSWORD` is missing or changed | Restore the correct env file and restart Redis + app |
| No sound after restore | Voice cache not restored or audio provider not configured | Restore your optional cache, then validate the OS/provider voice setup; the app itself does not require a voice cache to boot |
| Data disappeared after troubleshooting | `docker compose down -v` was run | Recreate the stack and restore Neo4j from backup; do not use `-v` during normal recovery |

### Known gotchas

- **Do not wipe volumes unless you mean it.** `down -v` removes persistent data.
- **A raw Neo4j `/data` backup is only safe if Neo4j was stopped first.** If that was not true, use a dump instead.
- **The dev profile is infra-only.** If you use `docker/docker-compose.dev.yml`, you still need to run the app separately.
- **Keep the same env values after restore.** Password mismatches are the most common post-restore failure.
- **Voice cache is optional.** Missing cache should not block the core platform from starting.

---

## 6. CONTACT / SUPPORT

If this guide does not get you back online:

- **Bug reports / restore failures:** https://github.com/agentic-brain-project/agentic-brain/issues
- **Questions / community help:** https://github.com/agentic-brain-project/agentic-brain/discussions
- **Project homepage:** https://github.com/agentic-brain-project/agentic-brain

When opening an issue, include:
1. the Compose profile you used
2. whether you restored from `neo4j.dump` or a raw snapshot
3. output from `docker compose -f "$COMPOSE_FILE" ps`
4. output from `curl http://localhost:8000/infra/health`
5. the exact failing command and error message

That information is usually enough for someone else to reproduce and help fix the problem.
