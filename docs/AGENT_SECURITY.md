# Agent Security Model

## Overview

**Every autonomous agent in agentic-brain MUST respect the 4-tier security model.**

This isn't just for chatbots—it applies to ALL agent types:
- Task agents
- Explore agents
- Background workers
- API handlers
- Event processors
- Workflow agents
- Swarm agents

## The 4-Tier Security Model

| Role | Level | Use Case | Permissions |
|------|-------|----------|-------------|
| **FULL_ADMIN** | 3 | Joseph only | Complete unrestricted access. No guardrails. Can execute any command, access any file, modify any config. |
| **SAFE_ADMIN** | 2 | Developers, Trusted admins | Full access with safety guardrails. Can do everything except dangerous commands (rm -rf /, DROP DATABASE, etc.). |
| **USER** | 1 | Customers, Employees | **API-only access**. Can call WordPress/WooCommerce APIs but CANNOT access machine/filesystem/shell. |
| **GUEST** | 0 | Anonymous visitors | Very restricted. Read-only access to FAQ/help docs. No APIs except public WordPress content. |

## Key Principle: API-Only Mode for USER Role

The critical insight: **Customer chatbots should ONLY access APIs, not machines.**

```python
# USER role configuration
SecurityRole.USER: RolePermissions(
    # NO machine access
    can_yolo=False,
    can_execute_code=False,
    can_execute_arbitrary_shell=False,
    can_write_files=False,
    can_read_all_files=False,
    
    # API-ONLY MODE
    api_only_mode=True,
    allowed_apis=frozenset({"wordpress", "woocommerce"}),
    
    # Chat-level LLM access
    llm_access_level="chat_only",
)
```

## How to Implement a Secure Agent

### 1. Inherit from BaseSecureAgent

```python
from agentic_brain.security import BaseSecureAgent, SecurityRole

class MyAgent(BaseSecureAgent):
    """My custom agent with built-in security."""
    
    def _execute_impl(self, action: str, **kwargs):
        """Implement agent-specific logic."""
        if action == "process_data":
            data = kwargs.get("data")
            # Your implementation here
            return {"result": "processed"}
        
        elif action == "call_api":
            api_name = kwargs.get("api")
            # API call implementation
            return {"api_result": "success"}
        
        else:
            raise ValueError(f"Unknown action: {action}")
```

### 2. Create Agent with Security Role

```python
# Create agent with USER role (API-only)
agent = MyAgent(security_role=SecurityRole.USER, agent_id="customer-chatbot-1")

# Execute actions - security is enforced automatically
result = agent.execute("call_api", api="woocommerce", method="get_products")
```

### 3. Security is Enforced Automatically

```python
# This will FAIL for USER role (no shell access)
try:
    agent.execute("execute_command", command="ls -la")
except SecurityViolation as e:
    print(f"Blocked: {e}")
    # Output: "Blocked: Shell command execution not permitted for this role"

# This will SUCCEED for USER role (allowed API)
result = agent.execute("call_api", api="woocommerce")
# Output: {"api_result": "success"}
```

## Agent Type Examples

### Task Agent (SAFE_ADMIN)

```python
from agentic_brain.security import BaseSecureAgent, SecurityRole

class DataProcessingAgent(BaseSecureAgent):
    """Background agent for processing data pipelines."""
    
    def _execute_impl(self, action: str, **kwargs):
        if action == "transform_data":
            input_path = kwargs.get("input_path")
            output_path = kwargs.get("output_path")
            
            # Read file (allowed for SAFE_ADMIN)
            data = self._read_data(input_path)
            
            # Transform data
            transformed = self._transform(data)
            
            # Write result (allowed for SAFE_ADMIN)
            self._write_data(output_path, transformed)
            
            return {"status": "success", "rows": len(transformed)}

# Usage
agent = DataProcessingAgent(security_role=SecurityRole.SAFE_ADMIN)
result = agent.execute(
    "transform_data",
    input_path="~/brain/data/input.csv",
    output_path="~/brain/output/result.csv"
)
```

### Explore Agent (USER or SAFE_ADMIN)

```python
class CodeExplorerAgent(BaseSecureAgent):
    """Agent for exploring and analyzing codebases."""
    
    def _execute_impl(self, action: str, **kwargs):
        if action == "explore_module":
            module_path = kwargs.get("module_path")
            
            # Read code files (allowed based on role)
            files = self._scan_directory(module_path)
            analysis = self._analyze_code(files)
            
            return {
                "module": module_path,
                "files": files,
                "analysis": analysis
            }

# For developer use
dev_agent = CodeExplorerAgent(security_role=SecurityRole.SAFE_ADMIN)
result = dev_agent.execute("explore_module", module_path="src/agentic_brain")

# For customer use (read-only, limited paths)
customer_agent = CodeExplorerAgent(security_role=SecurityRole.USER)
# Will only work on public docs
result = customer_agent.execute("explore_module", module_path="docs/public")
```

### Background Worker (USER for API workers, SAFE_ADMIN for system workers)

```python
class WooCommerceWorker(BaseSecureAgent):
    """Background worker for WooCommerce sync tasks."""
    
    def _execute_impl(self, action: str, **kwargs):
        if action == "sync_products":
            # Call WooCommerce API (allowed for USER role)
            products = self._call_woo_api("GET", "/products")
            
            # Store in database (API call, not file write)
            self._store_products_db(products)
            
            return {
                "synced": len(products),
                "status": "complete"
            }

# This worker only needs API access, so USER role is appropriate
worker = WooCommerceWorker(
    security_role=SecurityRole.USER,
    agent_id="woo-sync-worker-1"
)
result = worker.execute("sync_products")
```

### Event Processor (Role depends on event source)

```python
class WebhookProcessor(BaseSecureAgent):
    """Process incoming webhooks from external services."""
    
    def _execute_impl(self, action: str, **kwargs):
        if action == "process_webhook":
            event = kwargs.get("event", {})
            event_type = event.get("type")
            
            if event_type == "order.created":
                # Call API to process order
                return self._handle_order_webhook(event)
            
            elif event_type == "product.updated":
                # Call API to sync product
                return self._handle_product_webhook(event)
            
            return {"status": "ignored", "event_type": event_type}

# Webhook processors handling customer data should use USER role (API-only)
processor = WebhookProcessor(
    security_role=SecurityRole.USER,
    agent_id="webhook-processor"
)

# Process incoming webhook
result = processor.execute(
    "process_webhook",
    event={"type": "order.created", "order_id": 12345}
)
```

## Permission Matrix

### What Each Role Can Do

| Action | GUEST | USER | SAFE_ADMIN | FULL_ADMIN |
|--------|-------|------|------------|-----------|
| Read public docs | ✅ | ✅ | ✅ | ✅ |
| Read all files | ❌ | ❌ | ✅ | ✅ |
| Write files | ❌ | ❌ | ✅ (limited paths) | ✅ |
| Execute commands | ❌ | ❌ | ✅ (safe commands) | ✅ |
| Execute code | ❌ | ❌ | ✅ | ✅ |
| Call APIs | ✅ (public only) | ✅ (registered APIs) | ✅ | ✅ |
| Access secrets | ❌ | ❌ | ❌ | ✅ |
| Modify config | ❌ | ❌ | ✅ (project only) | ✅ |
| Admin API | ❌ | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ❌ | ✅ |

### API Access by Role

| API | GUEST | USER | SAFE_ADMIN | FULL_ADMIN |
|-----|-------|------|------------|-----------|
| WordPress (public) | ✅ | ✅ | ✅ | ✅ |
| WordPress (admin) | ❌ | ❌ | ✅ | ✅ |
| WooCommerce | ❌ | ✅ | ✅ | ✅ |
| Custom APIs | ❌ | ❌ | ✅ | ✅ |
| System APIs | ❌ | ❌ | ❌ | ✅ |

## Security Checks Performed

Every agent action goes through these security checks:

1. **Action Type Check**: Is this action type allowed for the role?
2. **Resource Check**: If accessing a resource (file, API, etc.), is it allowed?
3. **Rate Limit Check**: Has the agent exceeded its rate limit?
4. **Command Safety Check**: For SAFE_ADMIN, block dangerous commands
5. **API Allowlist Check**: For API-only roles, verify API is in allowed list

## Audit Logging

Every security decision is logged:

```python
# Get audit log for an agent
audit_log = agent.get_audit_log()

for entry in audit_log:
    print(f"{entry['timestamp']}: {entry['action']} - {'ALLOWED' if entry['allowed'] else 'BLOCKED'}")
    if not entry['allowed']:
        print(f"  Reason: {entry['reason']}")

# Example output:
# 2026-04-02T10:30:15Z: execute_command - BLOCKED
#   Reason: Shell command execution not permitted for this role
# 2026-04-02T10:30:20Z: call_api - ALLOWED
# 2026-04-02T10:30:22Z: call_api - ALLOWED
```

## Best Practices

### 1. Use the Appropriate Role

```python
# ❌ BAD: Using FULL_ADMIN for everything
agent = MyAgent(security_role=SecurityRole.FULL_ADMIN)

# ✅ GOOD: Use the minimum role needed
agent = MyAgent(security_role=SecurityRole.USER)  # For API-only customer bots
agent = MyAgent(security_role=SecurityRole.SAFE_ADMIN)  # For developer tools
```

### 2. Fail Fast on Security Violations

```python
# ❌ BAD: Catching and ignoring security violations
try:
    agent.execute("execute_command", command="rm -rf /")
except SecurityViolation:
    pass  # Silently ignore

# ✅ GOOD: Let security violations propagate
agent.execute("call_api", api="woocommerce")  # Will raise SecurityViolation if not allowed
```

### 3. Check Permissions Before Starting Work

```python
# ✅ GOOD: Check permissions upfront
permissions = agent.get_permissions_summary()
if not permissions["can_write_files"]:
    raise ValueError("This agent cannot write files")

# Then proceed with work
agent.execute("process_task", ...)
```

### 4. Use Audit Logs for Debugging

```python
# When something goes wrong, check the audit log
try:
    agent.execute("some_action", ...)
except SecurityViolation as e:
    # Get full context
    audit = agent.get_audit_log()
    recent = audit[-5:]  # Last 5 events
    logger.error(f"Security violation: {e}")
    logger.error(f"Recent audit log: {recent}")
```

### 5. Set Appropriate Agent IDs

```python
# ✅ GOOD: Meaningful agent IDs for audit trail
agent = MyAgent(
    security_role=SecurityRole.USER,
    agent_id="customer-chatbot-acme-corp"
)

# Now audit logs clearly show which agent did what
# "customer-chatbot-acme-corp attempted to execute_command - BLOCKED"
```

## Common Patterns

### Pattern 1: API-Only Customer Agent

```python
class CustomerChatbot(BaseSecureAgent):
    """Chatbot for customers - API access only."""
    
    def _execute_impl(self, action: str, **kwargs):
        if action == "answer_question":
            question = kwargs.get("question")
            
            # Search WordPress docs via API
            docs = self._search_wp_docs(question)
            
            # Search products via WooCommerce API
            products = self._search_products(question)
            
            # Generate response using LLM
            response = self._generate_response(question, docs, products)
            
            return {"answer": response}

# Always use USER role for customer bots
bot = CustomerChatbot(
    security_role=SecurityRole.USER,
    agent_id=f"customer-{customer_id}"
)
```

### Pattern 2: Developer Tool with Safe Commands

```python
class DeveloperAssistant(BaseSecureAgent):
    """Assistant for developers - safe commands only."""
    
    def _execute_impl(self, action: str, **kwargs):
        if action == "run_tests":
            test_path = kwargs.get("test_path")
            
            # Read test files (allowed)
            tests = self._discover_tests(test_path)
            
            # Run tests (safe command)
            results = self._run_test_command(tests)
            
            return {"tests_run": len(tests), "results": results}

# Use SAFE_ADMIN for developer tools
assistant = DeveloperAssistant(
    security_role=SecurityRole.SAFE_ADMIN,
    agent_id="dev-assistant"
)

# Can run tests
assistant.execute("run_tests", test_path="tests/")

# But cannot run dangerous commands
# assistant.execute("execute_command", command="rm -rf /")  # BLOCKED
```

### Pattern 3: Privileged System Agent

```python
class SystemMonitor(BaseSecureAgent):
    """System monitoring agent - needs full access."""
    
    def _execute_impl(self, action: str, **kwargs):
        if action == "collect_metrics":
            # Need to read system files
            cpu = self._read_cpu_stats()
            memory = self._read_memory_stats()
            disk = self._read_disk_stats()
            
            # Write to monitoring database
            self._store_metrics(cpu, memory, disk)
            
            return {"status": "collected"}

# Only use FULL_ADMIN when absolutely necessary
monitor = SystemMonitor(
    security_role=SecurityRole.FULL_ADMIN,
    agent_id="system-monitor"
)
```

## Testing Security

### Unit Tests for Agent Security

```python
import pytest
from agentic_brain.security import SecurityViolation, SecurityRole

def test_user_agent_cannot_execute_commands():
    """USER role agents cannot execute shell commands."""
    agent = MyAgent(security_role=SecurityRole.USER)
    
    with pytest.raises(SecurityViolation) as exc_info:
        agent.execute("execute_command", command="ls -la")
    
    assert "not permitted" in str(exc_info.value)

def test_user_agent_can_call_apis():
    """USER role agents CAN call allowed APIs."""
    agent = MyAgent(security_role=SecurityRole.USER)
    
    # Should succeed
    result = agent.execute("call_api", api="woocommerce")
    assert result["api_result"] == "success"

def test_safe_admin_blocked_dangerous_commands():
    """SAFE_ADMIN is blocked from dangerous commands."""
    agent = MyAgent(security_role=SecurityRole.SAFE_ADMIN)
    
    with pytest.raises(SecurityViolation):
        agent.execute("execute_command", command="rm -rf /")

def test_full_admin_unrestricted():
    """FULL_ADMIN can do anything."""
    agent = MyAgent(security_role=SecurityRole.FULL_ADMIN)
    
    # Even dangerous commands are allowed for FULL_ADMIN
    # (In test environment, not actually executed)
    # This just verifies the security check passes
    agent._check_action_allowed("execute_command", command="rm -rf /tmp/test")
```

## Migration Guide

### Updating Existing Agents

1. **Identify all agent classes**:
   ```bash
   find . -name "*.py" | xargs grep "class.*Agent"
   ```

2. **Update each agent to inherit from BaseSecureAgent**:
   ```python
   # Before
   class MyAgent:
       def __init__(self):
           pass
       
       def execute(self, action):
           # Implementation
           pass
   
   # After
   from agentic_brain.security import BaseSecureAgent, SecurityRole
   
   class MyAgent(BaseSecureAgent):
       def __init__(self, security_role=SecurityRole.USER):
           super().__init__(security_role=security_role)
       
       def _execute_impl(self, action, **kwargs):
           # Move implementation here
           pass
   ```

3. **Update instantiation to specify role**:
   ```python
   # Before
   agent = MyAgent()
   
   # After
   agent = MyAgent(security_role=SecurityRole.USER)
   ```

4. **Add tests**:
   ```python
   def test_agent_respects_security():
       agent = MyAgent(security_role=SecurityRole.USER)
       assert agent.security_role == SecurityRole.USER
       assert not agent.guard.permissions.can_yolo
   ```

## Summary

**Every autonomous agent MUST:**
1. Inherit from `BaseSecureAgent`
2. Implement `_execute_impl()` (not `execute()`)
3. Be instantiated with an appropriate `SecurityRole`
4. Respect the security checks enforced by the base class

**Remember:**
- GUEST = FAQ/help only
- USER = API-only (no machine access)
- SAFE_ADMIN = Full access with guardrails
- FULL_ADMIN = Unrestricted (Joseph only)

The security model applies to ALL agent types—chatbots, workers, processors, everything.
