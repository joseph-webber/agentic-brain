# Agentic Brain Security Roles

## Overview

Agentic Brain uses a **four-tier security role system** to control access to powerful features like shell execution, file system writes, admin APIs, and LLM capabilities.

The implementation has two complementary layers:

- **Runtime guard** in `agentic_brain.security.roles`, `guards`, and `auth`
- **LLM guard** in `agentic_brain.security.llm_guard`

Both layers use the same four role names: **admin**, **developer**, **user**, and **guest**.

## Quick Comparison

| Feature | GUEST | USER | DEVELOPER | ADMIN |
|---------|-------|------|-----------|-------|
| **Purpose** | Help desk | Safe coding | Full dev with guardrails | Full power |
| **Shell commands** | ❌ None | ✅ Safe only | ✅ Safe only | ✅ All |
| **File writes** | ❌ None | ⚠️ Output dirs only | ✅ Dev areas | ✅ Anywhere |
| **Git operations** | ❌ None | ✅ Safe only | ✅ Safe only | ✅ Including force |
| **System config** | ❌ None | ❌ None | ⚠️ Project only | ✅ All |
| **Secrets access** | ❌ None | ❌ None | ❌ None | ✅ All |
| **Rate limit/min** | 20 | 100 | 500 | 10000 |
| **GitHub Copilot level** | None | Basic | Advanced | Full |

## Security Roles

### 🔓 ADMIN Mode (Full Access - GitHub Copilot Equivalent)

**Who it's for:** System owners, trusted developers, local power users

**Runtime guard capabilities:**

- ✅ Full YOLO mode
- ✅ Write to any file or directory
- ✅ Read any file
- ✅ Execute code and arbitrary shell commands
- ✅ Modify configuration
- ✅ Access secrets and admin APIs
- ✅ Effectively no practical rate limit (`10000/min`)

**LLM guard capabilities:**

- ✅ All configured providers
- ✅ Code execution enabled
- ✅ File modification requests enabled
- ✅ Consensus / multi-LLM features enabled
- ✅ YOLO-style LLM actions enabled
- ✅ No LLM request rate limit
- ✅ No prompt filtering

**Typical use case:** local development, debugging, infrastructure work, and trusted automation.

**GitHub Copilot equivalence:** ADMIN mode gives you **everything GitHub Copilot can do, plus more**:
- ✅ All GitHub Copilot features (code completion, chat, agents)
- ✅ Plus: Direct system access, secrets management, admin APIs
- ✅ Plus: No restrictions or guardrails
- ✅ Plus: Effectively unlimited rate limits

### 💻 DEVELOPER Mode (Power User with Guardrails)

**Who it's for:** Experienced developers who want full coding power but with safety nets to prevent accidents

**Runtime guard capabilities:**

- ✅ YOLO mode available
- ⚠️ Dangerous commands blocked (same as USER, but broader write access)
- ✅ Write access to all development areas:
  - `~/brain/agentic-brain/**` (entire project)
  - `~/brain/web/**` (frontend)
  - `~/brain/backend/**` (backend)
  - `~/brain/skills/**` (skills development)
  - `~/brain/scripts/**` (automation)
  - `~/brain/tests/**` (test files)
  - Plus: data, logs, cache, output directories
- ✅ Read access is broad
- ✅ Full code execution with restrictions
- ✅ Can modify **project** configuration (not system)
- ❌ Cannot access system secrets
- ❌ Cannot access admin APIs
- ✅ Higher rate limit: `500/min`

**LLM guard capabilities:**

- ✅ Full LLM access (all providers)
- ✅ Code execution enabled
- ✅ File modification enabled (within allowed paths)
- ✅ Consensus features enabled
- ✅ Advanced GitHub Copilot features
- ✅ LLM rate limit: `100/min`
- ⚠️ Light prompt filtering (safety only)

**What DEVELOPER can do:**

- ✅ Build entire features end-to-end
- ✅ Refactor code across the project
- ✅ Create new skills and scripts
- ✅ Run comprehensive test suites
- ✅ Modify project config (package.json, requirements.txt)
- ✅ Git operations (commit, push, pull, merge)
- ✅ Install dependencies (npm, pip)
- ✅ Database migrations

**What DEVELOPER cannot do:**

- ❌ Force push or hard reset git history
- ❌ Modify system configuration (/etc, ~/.bashrc)
- ❌ Access API keys and secrets
- ❌ Run destructive system commands (rm -rf /, sudo)
- ❌ Modify file permissions to world-writable
- ❌ Access admin-only APIs

**Typical use case:** Active development sessions where you want to move fast but not accidentally nuke something important.

**GitHub Copilot equivalence:** DEVELOPER mode gives you **~95% of GitHub Copilot's power**:
- ✅ Code generation and completion
- ✅ Multi-file editing
- ✅ Test generation
- ✅ Refactoring across files
- ✅ Terminal command assistance (with safety)
- ⚠️ Some operations require ADMIN (force operations, secrets)

### 👤 USER Mode (Safe Coding Assistant)

**Who it's for:** Users who need coding help but should not modify the system or core framework

**Who it's for:** Trusted users who need powerful assistance without unrestricted system control

**Runtime guard capabilities:**

- ✅ YOLO mode available (with restrictions)
- ⚠️ Dangerous commands are blocked by pattern-based safeguards
- ⚠️ Writes are **very limited** - output directories only:
  - `~/brain/output`
  - `~/brain/test-results`
  - `~/brain/session-artifacts`
  - `~/brain/agentic-brain/output`
  - `~/brain/agentic-brain/.test-artifacts`
  - `~/brain/agentic-brain/test-results`
- ✅ Read access is broad (can read code to learn/assist)
- ✅ Code execution allowed (for testing snippets)
- ✅ Shell commands allowed (safe operations only)
- ❌ Cannot modify source code files
- ❌ Cannot modify configuration
- ❌ Cannot access secrets
- ❌ Cannot access admin APIs
- ✅ Runtime rate limit: `100/min`

**LLM guard capabilities:**

- ✅ Chat access across standard providers
- ✅ Can ask for coding advice and examples
- ✅ Can analyze code and suggest improvements
- ⚠️ Can execute code in sandboxed/safe contexts
- ⚠️ Cannot modify files through LLM (read-only coding assistant)
- ❌ Cannot use consensus features
- ❌ Cannot use YOLO LLM actions
- ✅ LLM rate limit: `60/min`
- ✅ Standard prompt filtering

**What USER mode CAN do (useful coding assistance):**

- ✅ Answer coding questions and explain concepts
- ✅ Review code and suggest improvements
- ✅ Generate code examples (you paste them in)
- ✅ Debug issues and suggest fixes
- ✅ Explain errors and stack traces
- ✅ Run safe shell commands (ls, grep, find, etc.)
- ✅ Execute test code snippets
- ✅ Analyze logs and data files
- ✅ Generate documentation
- ✅ Create diagrams and flowcharts
- ✅ Write to output/test directories

**What USER mode CANNOT do (prevented for safety):**

- ❌ Modify source code files directly
- ❌ Modify framework or system files
- ❌ Run destructive commands (rm -rf, sudo, chmod 777)
- ❌ Force push or hard reset git
- ❌ Access API keys or secrets
- ❌ Modify configuration files
- ❌ Install system packages
- ❌ Change file permissions
- ❌ Write to system directories

**Dangerous command examples blocked for USER mode:**

- `rm -rf /` or `rm -rf ~`
- `sudo ...` (any sudo)
- `chmod 777 ...` (world-writable)
- `dd ... of=/dev/...` (disk operations)
- `mkfs ...` (filesystem formatting)
- `git push --force` or `git push -f`
- `git reset --hard`
- `> /etc/...` (redirects to /etc)
- `DROP DATABASE` or `TRUNCATE TABLE`
- Fork bombs and infinite loops

**Typical use case:** Customer/client coding assistance where you want to help them code effectively but prevent any possibility of harming their system or your framework.

### 👋 Guest Mode (Help Desk)

**Who it's for:** demos, public entry points, anonymous users, and untrusted sessions

**Runtime guard capabilities:**

- ❌ No YOLO mode
- ❌ No file writing
- ❌ No code execution
- ❌ No arbitrary shell commands
- ❌ No config changes
- ❌ No secret or admin API access
- ⚠️ Read access is limited to public documentation paths
- ✅ Runtime rate limit: `20/min`

**LLM guard capabilities:**

- ⚠️ Limited provider set: `groq`, `ollama`, `openrouter`
- ❌ No code execution
- ❌ No file modification
- ❌ No consensus features
- ❌ No YOLO LLM actions
- ⚠️ Heavy rate limiting: `10/min`
- ⚠️ Strict prompt filtering

**Typical use case:** onboarding, documentation, simple troubleshooting, and safe public chat.

**GitHub Copilot equivalence:** GUEST mode is like having **no GitHub Copilot at all** - just a basic chatbot for documentation questions.

## How Roles Are Enforced

### Runtime guard

The runtime guard checks:

- shell commands
- file reads and writes
- code execution
- configuration changes
- secrets access
- admin API access
- request rate limits

Key files:

- `src/agentic_brain/security/roles.py`
- `src/agentic_brain/security/guards.py`
- `src/agentic_brain/security/auth.py`

### LLM guard

The LLM guard checks:

- which providers can be used
- whether prompts need filtering
- whether LLM code execution is allowed
- whether LLM-driven file modification is allowed
- whether consensus features are available
- per-user request limits

Key files:

- `src/agentic_brain/security/llm_guard.py`
- `src/agentic_brain/router/routing.py`

## Switching Roles

### Python runtime

```python
from agentic_brain.security.roles import SecurityRole
from agentic_brain.security.guards import SecurityGuard

# For day-to-day development with guardrails
guard = SecurityGuard(SecurityRole.DEVELOPER)
allowed, reason = guard.check_command("git commit -m 'feature'")

# For safe customer assistance
guard = SecurityGuard(SecurityRole.USER)
allowed, reason = guard.check_command("ls -la")

# For full power (Platform Administrator)
guard = SecurityGuard(SecurityRole.ADMIN)
allowed, reason = guard.check_command("git push --force")
```

### LLM routing

```python
from agentic_brain.security.llm_guard import LLMSecurityGuard, SecurityRole

guard = LLMSecurityGuard(SecurityRole.GUEST)
```

### Via authentication helpers

```python
from agentic_brain.security.auth import authenticate_request

guard = authenticate_request(user_id="joseph")  # admin by default
```

### Via environment

```bash
# Set role for different scenarios
export AGENTIC_BRAIN_ADMIN_MODE=true  # Full admin access
export AGENTIC_BRAIN_DEFAULT_ROLE=developer  # Developer mode with guardrails
export AGENTIC_BRAIN_DEFAULT_ROLE=user  # Safe customer assistance mode
export AGENTIC_BRAIN_DEFAULT_LLM_ROLE=developer  # Developer mode for LLM
```

### Important note

There is **not currently** a single universal `AGENTIC_BRAIN_ROLE` switch wired across the entire codebase. The active role is determined by the specific security layer you use:

- runtime auth/session logic for command and file access
- `AGENTIC_BRAIN_DEFAULT_LLM_ROLE` or explicit constructor arguments for LLM access

The four roles (`GUEST`, `USER`, `DEVELOPER`, `ADMIN`) are defined and enforced, but the switching mechanism is per-layer.

## Authentication

### Admin authentication sources

Admin access can be established through:

- environment variable: `AGENTIC_BRAIN_ADMIN_KEY`
- config file: `~/.brain/admin.key`
- known admin user IDs such as `joseph`
- extra admin users from `AGENTIC_BRAIN_ADMIN_USER`
- explicit local override: `AGENTIC_BRAIN_ADMIN_MODE=true`

### Default behavior

- `authenticate_request()` with no auth inputs returns **GUEST**
- valid admin key returns **ADMIN**
- a non-admin API key with sufficient length currently maps to **USER**
- developers can explicitly request **DEVELOPER** role
- `authenticate_request(user_id="joseph")` returns **ADMIN**
- `LLMSecurityGuard` falls back to `AGENTIC_BRAIN_DEFAULT_LLM_ROLE` when available
- if no LLM auth context exists and no default env is set, `LLMSecurityGuard` currently falls back to **ADMIN**

## API-Based Access Model

For Customer and User modes, BrainChat uses an API-based security model:

### No Direct Machine Access
- ❌ No shell commands
- ❌ No file system access
- ❌ No YOLO mode
- ❌ No database queries
- ✅ Only API calls to authorized services

### How It Works

1. **Admin configures APIs** - Sets up which APIs the chatbot can access
2. **API keys are scoped** - Each key has minimum required permissions
3. **User authenticates** - Via WordPress, OAuth, or API key
4. **Chatbot relays requests** - Passes user's auth to the API
5. **API enforces permissions** - WordPress/WooCommerce check user's role
6. **Results returned** - Chatbot formats response for user

### Example: WooCommerce Customer

The chatbot for a WooCommerce customer can:
- ✅ Call GET /wp-json/wc/v3/orders?customer=123 (own orders)
- ❌ Cannot call GET /wp-json/wc/v3/orders (all orders)
- ❌ Cannot call DELETE /wp-json/wc/v3/products/456
- ❌ Cannot run `ls /var/www/` on the server

### Allowed System Information

Even without machine access, USER mode can access:
- Current time/date (harmless)
- Chatbot version info
- Configured API endpoints (names only)
- Rate limit status

## BrainChat Swift Notes

BrainChat currently exposes backend authentication settings and a YOLO toggle. It does **not yet** provide a dedicated Admin/Developer/User/Guest role picker in `SettingsView.swift`, so role selection happens through backend auth and server-side guard configuration.

## Feature Comparison Table

### Core Capabilities

| Capability | GUEST | USER | DEVELOPER | ADMIN |
|------------|-------|------|-----------|-------|
| **Read source code** | ⚠️ Docs only | ✅ All files | ✅ All files | ✅ All files |
| **Write source code** | ❌ Never | ❌ No | ✅ Dev areas | ✅ Anywhere |
| **Execute shell commands** | ❌ Never | ✅ Safe only | ✅ Safe only | ✅ All |
| **Run code snippets** | ❌ Never | ✅ Yes | ✅ Yes | ✅ Yes |
| **Install packages** | ❌ Never | ❌ No | ✅ Yes (npm, pip) | ✅ Yes (all) |
| **Git operations** | ❌ Never | ✅ Basic | ✅ Advanced | ✅ All including force |
| **Modify config files** | ❌ Never | ❌ No | ✅ Project only | ✅ All |
| **Access secrets/keys** | ❌ Never | ❌ No | ❌ No | ✅ Yes |
| **System administration** | ❌ Never | ❌ No | ❌ No | ✅ Yes |

### GitHub Copilot Feature Parity

| Feature | GUEST | USER | DEVELOPER | ADMIN |
|---------|-------|------|-----------|-------|
| **Code completion** | ❌ | ✅ Read-only examples | ✅ Full | ✅ Full |
| **Chat assistance** | ✅ Docs only | ✅ Full coding advice | ✅ Full | ✅ Full |
| **Explain code** | ⚠️ Limited | ✅ Yes | ✅ Yes | ✅ Yes |
| **Generate tests** | ❌ | ⚠️ Examples only | ✅ Can write files | ✅ Can write files |
| **Fix bugs** | ❌ | ⚠️ Suggest only | ✅ Can fix files | ✅ Can fix files |
| **Refactor code** | ❌ | ❌ | ✅ Multi-file | ✅ Multi-file |
| **Terminal commands** | ❌ | ✅ Safe only | ✅ Safe only | ✅ All |
| **Multi-file edits** | ❌ | ❌ | ✅ Dev areas | ✅ Anywhere |
| **Workspace analysis** | ⚠️ Docs only | ✅ Read all | ✅ Read all | ✅ Read all |
| **Commit assistance** | ❌ | ⚠️ Messages only | ✅ Full | ✅ Full |

### LLM and AI Features

| Feature | GUEST | USER | DEVELOPER | ADMIN |
|---------|-------|------|-----------|-------|
| **LLM providers** | ⚠️ Limited | ✅ Standard | ✅ All | ✅ All |
| **Code execution via LLM** | ❌ | ⚠️ Sandboxed | ✅ Yes | ✅ Yes |
| **File modification via LLM** | ❌ | ❌ | ✅ Dev areas | ✅ Anywhere |
| **Consensus/multi-LLM** | ❌ | ❌ | ✅ Yes | ✅ Yes |
| **YOLO mode** | ❌ | ❌ | ⚠️ With guards | ✅ Full |
| **Rate limit (requests/min)** | 10-20 | 60-100 | 100-500 | No limit |

### Write Permissions by Directory

| Directory | GUEST | USER | DEVELOPER | ADMIN |
|-----------|-------|------|-----------|-------|
| `/etc/*` | ❌ | ❌ | ❌ | ✅ |
| `~/.bashrc`, `~/.zshrc` | ❌ | ❌ | ❌ | ✅ |
| `~/brain/agentic-brain/src/**` | ❌ | ❌ | ✅ | ✅ |
| `~/brain/web/**` | ❌ | ❌ | ✅ | ✅ |
| `~/brain/backend/**` | ❌ | ❌ | ✅ | ✅ |
| `~/brain/skills/**` | ❌ | ❌ | ✅ | ✅ |
| `~/brain/tests/**` | ❌ | ❌ | ✅ | ✅ |
| `~/brain/output/**` | ❌ | ✅ | ✅ | ✅ |
| `~/brain/test-results/**` | ❌ | ✅ | ✅ | ✅ |
| `~/brain/session-artifacts/**` | ❌ | ✅ | ✅ | ✅ |
| `~/brain/data/**` | ❌ | ❌ | ✅ | ✅ |
| `~/brain/logs/**` | ❌ | ❌ | ✅ | ✅ |

### Dangerous Operations

| Operation | GUEST | USER | DEVELOPER | ADMIN |
|-----------|-------|------|-----------|-------|
| `rm -rf /` or `~/` | ❌ | ❌ | ❌ | ⚠️ Allowed (YOLO) |
| `sudo` commands | ❌ | ❌ | ❌ | ✅ |
| `chmod 777` | ❌ | ❌ | ❌ | ✅ |
| `git push --force` | ❌ | ❌ | ❌ | ✅ |
| `git reset --hard` | ❌ | ❌ | ❌ | ✅ |
| `DROP DATABASE` | ❌ | ❌ | ❌ | ✅ |
| Disk operations (`dd`, `mkfs`) | ❌ | ❌ | ❌ | ✅ |
| System service control | ❌ | ❌ | ❌ | ✅ |

### Recommended Use Cases

| Role | Best For | Examples |
|------|----------|----------|
| **GUEST** | Anonymous users, demos, public help desk | "How do I install this?", "What does this error mean?" |
| **USER** | Safe coding assistance without modification | Customer coding help, read-only code review, learn-to-code scenarios |
| **DEVELOPER** | Active development with safety nets | Building features, refactoring, testing, most day-to-day work |
| **ADMIN** | Full system control, trusted operators | Infrastructure work, debugging production, emergency fixes, authorized administrator |

## Security Best Practices

1. **Never share the admin key.**
2. **Use DEVELOPER for day-to-day development** - it has guardrails to prevent accidents.
3. **Use USER for customer/client assistance** - safe coding help without modification rights.
4. **Use GUEST for demos and anonymous access** - documentation and basic troubleshooting only.
5. **Keep ADMIN for trusted operators only** - authorized administrators, emergency fixes, infrastructure work.
6. **Review blocked-command logs and audit events regularly.**
7. **Pass roles explicitly in code when behavior must be deterministic.**
8. **Start with lower privilege and escalate only when needed.**

## Choosing the Right Role

**Use ADMIN when:**
- You are an authorized administrator or another system owner
- You need to modify system configuration
- You need to access secrets/API keys
- You need to perform infrastructure work
- You need to do emergency debugging/fixes
- You trust yourself completely

**Use DEVELOPER when:**
- You are actively developing features
- You want full coding power with safety nets
- You want to prevent accidental damage
- You need to modify source code
- You want most GitHub Copilot features
- You trust yourself mostly

**Use USER when:**
- You are helping customers/clients with code
- You want to provide coding assistance without modification
- You need to prevent any file modifications
- You want safe command execution only
- You are in a learning/teaching scenario
- You want to be extra cautious

**Use GUEST when:**
- You are running a public demo
- You have anonymous/untrusted users
- You only need documentation and help desk features
- You want read-only assistance
- You are onboarding new users
- You want maximum safety

## For Developers

- [Security implementation details](./SECURITY_IMPLEMENTATION.md)
- [Security quick start](./SECURITY_QUICKSTART.md)
- [General security guide](./SECURITY.md)
