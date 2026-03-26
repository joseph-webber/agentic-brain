# Tutorial 4: Multi-User SaaS Chatbot

**Objective:** Build a production SaaS chatbot with proper customer isolation, data scoping, and multi-tenancy.

**Time:** 30 minutes  
**Difficulty:** Advanced  
**Prerequisites:** Completed Tutorials 1-3

---

## What You'll Build

A multi-tenant chatbot system that:
- Isolates data by customer/organization
- Enforces access control (can't access other customer data)
- Manages separate billing/usage per customer
- Scales to hundreds of customers
- Provides customer analytics

**Use Cases:**
- Customer support SaaS
- AI assistant for multiple clients
- Multi-tenant knowledge base
- White-label chatbot platform

---

## Multi-Tenancy Fundamentals

```
WITHOUT Multi-Tenancy:
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Customer A     │ │  Customer B     │ │  Customer C     │
│  (Separate DB)  │ │  (Separate DB)  │ │  (Separate DB)  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
❌ Expensive: N databases
❌ Slow: N connections
❌ Hard to manage: N instances

WITH Multi-Tenancy:
┌──────────────────────────────────────────┐
│           Single Database                │
├──────────────────────────────────────────┤
│ Customer A  │ Customer B  │ Customer C   │
│ (tenant_id) │ (tenant_id) │ (tenant_id)  │
└──────────────────────────────────────────┘
✅ Efficient: 1 database
✅ Fast: 1 connection
✅ Simple: 1 instance
```

---

## Part 1: Tenant Model

Create `tenant.py`:

```python
"""
Tenant management for SaaS.

Handles customer isolation and access control.
"""

import logging
import secrets
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TenantTier(Enum):
    """SaaS pricing tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserRole(Enum):
    """Roles within a tenant."""
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


@dataclass
class Tenant:
    """
    A customer/organization.
    
    All data is scoped to a tenant.
    """
    tenant_id: str
    name: str
    tier: TenantTier = TenantTier.FREE
    api_key: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Limits based on tier
    monthly_api_calls_limit: int = 10000
    max_users: int = 5
    max_conversations: int = 100
    enable_custom_models: bool = False
    
    # Current usage
    current_api_calls: int = 0
    current_users: int = 0
    current_conversations: int = 0
    
    # Settings
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["tier"] = self.tier.value
        return data
    
    @staticmethod
    def from_tier(tenant_id: str, name: str, tier: TenantTier) -> "Tenant":
        """Create tenant with limits based on tier."""
        tier_limits = {
            TenantTier.FREE: {
                "monthly_api_calls_limit": 10000,
                "max_users": 1,
                "max_conversations": 10,
                "enable_custom_models": False
            },
            TenantTier.PRO: {
                "monthly_api_calls_limit": 100000,
                "max_users": 10,
                "max_conversations": 1000,
                "enable_custom_models": True
            },
            TenantTier.ENTERPRISE: {
                "monthly_api_calls_limit": 1000000,
                "max_users": 100,
                "max_conversations": 100000,
                "enable_custom_models": True
            }
        }
        
        limits = tier_limits[tier]
        tenant = Tenant(tenant_id=tenant_id, name=name, tier=tier)
        
        for key, value in limits.items():
            setattr(tenant, key, value)
        
        return tenant
    
    def check_rate_limit(self) -> bool:
        """Check if tenant is within API call limits."""
        return self.current_api_calls < self.monthly_api_calls_limit
    
    def check_user_limit(self) -> bool:
        """Check if tenant can add more users."""
        return self.current_users < self.max_users
    
    def check_conversation_limit(self) -> bool:
        """Check if tenant can start more conversations."""
        return self.current_conversations < self.max_conversations


@dataclass
class TenantUser:
    """User within a tenant."""
    user_id: str
    tenant_id: str
    email: str
    role: UserRole = UserRole.VIEWER
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        return data


class TenantManager:
    """Manage tenants and access control."""
    
    def __init__(self, neo4j_memory):
        """
        Initialize tenant manager.
        
        Args:
            neo4j_memory: Neo4jMemory instance for persistence
        """
        self.memory = neo4j_memory
        self.tenants: Dict[str, Tenant] = {}
        self.users: Dict[str, TenantUser] = {}
    
    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        tier: TenantTier = TenantTier.FREE
    ) -> Tenant:
        """
        Create new tenant.
        
        Args:
            tenant_id: Unique tenant identifier
            name: Customer name
            tier: Pricing tier
            
        Returns:
            New Tenant object
        """
        if tenant_id in self.tenants:
            raise ValueError(f"Tenant {tenant_id} already exists")
        
        tenant = Tenant.from_tier(tenant_id, name, tier)
        self.tenants[tenant_id] = tenant
        
        logger.info(f"✅ Created tenant: {tenant_id} ({name}) - {tier.value}")
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self.tenants.get(tenant_id)
    
    def add_user_to_tenant(
        self,
        tenant_id: str,
        user_id: str,
        email: str,
        role: UserRole = UserRole.VIEWER
    ) -> Optional[TenantUser]:
        """
        Add user to tenant.
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            email: User email
            role: User role
            
        Returns:
            TenantUser object or None if failed
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            logger.error(f"Tenant not found: {tenant_id}")
            return None
        
        if not tenant.check_user_limit():
            logger.error(f"Tenant {tenant_id} has reached user limit")
            return None
        
        tenant_user = TenantUser(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role
        )
        
        self.users[user_id] = tenant_user
        tenant.current_users += 1
        
        logger.info(f"✅ Added user {user_id} to tenant {tenant_id}")
        return tenant_user
    
    def record_api_call(self, tenant_id: str) -> bool:
        """
        Record API call for rate limiting.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            True if within limits, False if rate limited
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        if not tenant.check_rate_limit():
            logger.warning(f"Tenant {tenant_id} rate limited")
            return False
        
        tenant.current_api_calls += 1
        return True
    
    def get_user_tenants(self, user_id: str) -> List[Tenant]:
        """Get all tenants a user belongs to."""
        tenant_user = self.users.get(user_id)
        if not tenant_user:
            return []
        
        tenant = self.get_tenant(tenant_user.tenant_id)
        return [tenant] if tenant else []
    
    def has_access(
        self,
        user_id: str,
        tenant_id: str,
        required_role: Optional[UserRole] = None
    ) -> bool:
        """
        Check if user has access to tenant.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            required_role: Minimum required role (None = any role)
            
        Returns:
            True if user can access tenant
        """
        tenant_user = self.users.get(user_id)
        if not tenant_user or tenant_user.tenant_id != tenant_id:
            return False
        
        if required_role is None:
            return True
        
        # Simple role hierarchy
        role_hierarchy = {
            UserRole.VIEWER: 0,
            UserRole.DEVELOPER: 1,
            UserRole.ADMIN: 2
        }
        
        user_level = role_hierarchy.get(tenant_user.role, -1)
        required_level = role_hierarchy.get(required_role, -1)
        
        return user_level >= required_level
    
    def list_tenants(self) -> List[Tenant]:
        """List all tenants."""
        return list(self.tenants.values())
    
    def get_tenant_analytics(self, tenant_id: str) -> Dict[str, Any]:
        """Get analytics for a tenant."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {}
        
        return {
            "tenant_id": tenant_id,
            "name": tenant.name,
            "tier": tenant.tier.value,
            "usage": {
                "api_calls": f"{tenant.current_api_calls}/{tenant.monthly_api_calls_limit}",
                "users": f"{tenant.current_users}/{tenant.max_users}",
                "conversations": f"{tenant.current_conversations}/{tenant.max_conversations}"
            },
            "limits_exceeded": {
                "api_calls": not tenant.check_rate_limit(),
                "users": not tenant.check_user_limit(),
                "conversations": not tenant.check_conversation_limit()
            }
        }
```

---

## Part 2: Multi-Tenant Bot

Create `multitenant_bot.py`:

```python
"""
Multi-tenant chatbot with isolation.

Each tenant has isolated conversation history and memories.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from agentic_brain import Agent, Neo4jMemory
from tenant import Tenant, TenantManager, UserRole
import config

logger = logging.getLogger(__name__)


class SaaS ChatBot:
    """Chatbot service with multi-tenant support."""
    
    def __init__(self, tenant_manager: TenantManager):
        """
        Initialize SaaS chatbot.
        
        Args:
            tenant_manager: TenantManager instance
        """
        self.tenant_manager = tenant_manager
        
        # Initialize shared memory (all tenants use same DB, isolated by tenant_id)
        try:
            self.memory = Neo4jMemory(
                uri=config.NEO4J_URI,
                username=config.NEO4J_USERNAME,
                password=config.NEO4J_PASSWORD
            )
            logger.info("✅ Multi-tenant memory initialized")
        except Exception as e:
            logger.error(f"Memory initialization failed: {e}")
            self.memory = None
        
        # Cache for active bots (real systems use Redis)
        self.active_bots: Dict[str, Agent] = {}
    
    def _get_bot_id(self, tenant_id: str, user_id: str) -> str:
        """Get unique bot ID for tenant+user."""
        return f"{tenant_id}#{user_id}"
    
    def _ensure_bot(self, tenant_id: str, user_id: str) -> Optional[Agent]:
        """Ensure bot is initialized for this tenant+user."""
        bot_id = self._get_bot_id(tenant_id, user_id)
        
        if bot_id in self.active_bots:
            return self.active_bots[bot_id]
        
        try:
            bot = Agent(
                name=f"bot_{tenant_id}",
                memory=self.memory,
                llm_provider=config.LLM_PROVIDER,
                llm_model=config.LLM_MODEL,
                system_prompt=f"""You are a helpful assistant for {tenant_id}.
                Remember tenant-specific context and preferences."""
            )
            
            self.active_bots[bot_id] = bot
            logger.info(f"✅ Bot initialized: {bot_id}")
            return bot
            
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            return None
    
    def chat(
        self,
        tenant_id: str,
        user_id: str,
        message: str,
        require_role: Optional[UserRole] = None
    ) -> Dict[str, Any]:
        """
        Chat with tenant isolation.
        
        Args:
            tenant_id: Customer ID
            user_id: User ID within tenant
            message: User message
            require_role: Minimum required role
            
        Returns:
            Response dict with message and metadata
        """
        # 1. Access control
        if not self.tenant_manager.has_access(user_id, tenant_id, require_role):
            return {
                "error": "Access denied",
                "code": "unauthorized"
            }
        
        # 2. Rate limiting
        if not self.tenant_manager.record_api_call(tenant_id):
            return {
                "error": "Rate limit exceeded",
                "code": "rate_limited"
            }
        
        # 3. Get or create bot for this tenant
        bot = self._ensure_bot(tenant_id, user_id)
        if not bot:
            return {
                "error": "Bot unavailable",
                "code": "bot_error"
            }
        
        # 4. Chat (using tenant_id-scoped user ID)
        scoped_user_id = f"{tenant_id}#{user_id}"
        
        try:
            response = bot.chat(
                message=message,
                user_id=scoped_user_id  # Isolate memories by tenant
            )
            
            logger.info(f"✅ Chat: {tenant_id}#{user_id} - {len(response)} chars")
            
            return {
                "success": True,
                "message": response,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {
                "error": str(e),
                "code": "chat_error"
            }
    
    def get_conversation_history(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get conversation history (isolated by tenant).
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            limit: Max messages
            
        Returns:
            Conversation history or error
        """
        if not self.tenant_manager.has_access(user_id, tenant_id):
            return {"error": "Access denied"}
        
        scoped_user_id = f"{tenant_id}#{user_id}"
        
        try:
            # In a real system, retrieve from Neo4j
            return {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "messages": []  # Would retrieve from memory
            }
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return {"error": str(e)}


def main():
    """Demo multi-tenant chatbot."""
    
    print("\n" + "="*60)
    print("🏢 Multi-Tenant SaaS Chatbot Demo")
    print("="*60 + "\n")
    
    # Initialize tenant manager
    tenant_manager = TenantManager(neo4j_memory=None)
    
    # Create customers
    print("📊 Setting up tenants...\n")
    
    customer_a = tenant_manager.create_tenant(
        "acme_corp",
        "ACME Corporation",
        tier=TenantTier.PRO
    )
    
    customer_b = tenant_manager.create_tenant(
        "widgets_inc",
        "Widgets Inc",
        tier=TenantTier.FREE
    )
    
    # Add users to tenants
    print("👥 Adding users...\n")
    
    tenant_manager.add_user_to_tenant(
        "acme_corp",
        "alice",
        "alice@acme.com",
        role=UserRole.ADMIN
    )
    
    tenant_manager.add_user_to_tenant(
        "acme_corp",
        "bob",
        "bob@acme.com",
        role=UserRole.DEVELOPER
    )
    
    tenant_manager.add_user_to_tenant(
        "widgets_inc",
        "charlie",
        "charlie@widgets.com",
        role=UserRole.ADMIN
    )
    
    # Show tenant analytics
    print("📈 Tenant Analytics:\n")
    for tenant in tenant_manager.list_tenants():
        analytics = tenant_manager.get_tenant_analytics(tenant.tenant_id)
        print(f"Tenant: {analytics['name']}")
        print(f"  Tier: {analytics['tier']}")
        print(f"  Usage: {analytics['usage']}")
        print()
    
    # Demonstrate access control
    print("🔐 Access Control Tests:\n")
    
    # ✅ Alice can access ACME
    can_access = tenant_manager.has_access("alice", "acme_corp")
    print(f"Alice accessing ACME: {can_access} ✅")
    
    # ❌ Charlie can't access ACME
    can_access = tenant_manager.has_access("charlie", "acme_corp")
    print(f"Charlie accessing ACME: {can_access} ❌")
    
    # ✅ Charlie can access Widgets
    can_access = tenant_manager.has_access("charlie", "widgets_inc")
    print(f"Charlie accessing Widgets: {can_access} ✅\n")
    
    # Demonstrate rate limiting
    print("⏱️  Rate Limiting Test:\n")
    
    # Set artificial limit for demo
    customer_a.monthly_api_calls_limit = 3
    
    for i in range(5):
        success = tenant_manager.record_api_call("acme_corp")
        status = "✅ OK" if success else "❌ RATE LIMITED"
        print(f"API call {i+1}: {status}")
    
    print("\n" + "="*60)
    print("✅ Multi-tenant demo complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    from tenant import TenantTier
    main()
```

---

## Part 3: API Endpoint Protection

Create `saas_api.py`:

```python
"""
SaaS API with multi-tenant protection.

FastAPI routes with tenant isolation.
"""

from fastapi import FastAPI, Depends, HTTPException, Header, APIRouter
from typing import Optional
from multitenant_bot import SaaSChatBot
from tenant import TenantManager, UserRole

app = FastAPI(title="Multi-Tenant Chatbot API")

# Initialize (in production, use dependency injection)
tenant_manager = TenantManager(neo4j_memory=None)
chatbot = SaaSChatBot(tenant_manager)


async def verify_api_key(
    x_api_key: str = Header(None)
) -> str:
    """Verify API key and return tenant_id."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Find tenant by API key
    for tenant in tenant_manager.list_tenants():
        if tenant.api_key == x_api_key:
            return tenant.tenant_id
    
    raise HTTPException(status_code=401, detail="Invalid API key")


@app.post("/chat")
async def chat_endpoint(
    message: str,
    user_id: str,
    tenant_id: str = Depends(verify_api_key)
):
    """
    Chat endpoint with authentication.
    
    Usage:
    ```bash
    curl -X POST http://localhost:8000/chat \
      -H "X-API-Key: YOUR_KEY" \
      -H "Content-Type: application/json" \
      -d '{"message": "Hello", "user_id": "alice"}'
    ```
    """
    result = chatbot.chat(
        tenant_id=tenant_id,
        user_id=user_id,
        message=message
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.get("/tenant/{tenant_id}/analytics")
async def analytics_endpoint(
    tenant_id: str = Depends(verify_api_key)
):
    """Get analytics for tenant."""
    analytics = tenant_manager.get_tenant_analytics(tenant_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return analytics


# Testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Run with:
```bash
pip install fastapi uvicorn
python saas_api.py

# Test:
curl -X POST http://localhost:8000/chat \
  -H "X-API-Key: API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "user_id": "alice"}'
```

---

## 🆘 Troubleshooting

### ❌ "User doesn't have access"

```python
# Verify user is added to tenant
tenant_manager.add_user_to_tenant(
    "tenant_id",
    "user_id",
    "email@example.com"
)

# Check access
tenant_manager.has_access("user_id", "tenant_id")
```

### ❌ "Rate limit exceeded immediately"

```python
# Check tenant limits
tenant = tenant_manager.get_tenant("tenant_id")
print(tenant.monthly_api_calls_limit)
print(tenant.current_api_calls)

# Reset (dev only)
tenant.current_api_calls = 0
```

### ❌ "Can't isolate conversations"

Ensure user_id is scoped by tenant:
```python
scoped_user_id = f"{tenant_id}#{user_id}"  # ✅ Correct
bot.chat(message, user_id=scoped_user_id)
```

---

## ✅ What You've Learned

- ✅ Model tenants and users
- ✅ Implement access control
- ✅ Enforce rate limiting per customer
- ✅ Isolate conversations by tenant
- ✅ Build multi-tenant APIs
- ✅ Handle customer analytics

---

## 🚀 Next: Production Deployment

Proceed to [Tutorial 5: Deployment](./05-deployment.md) to learn:
- Docker containerization
- Kubernetes scaling
- Monitoring and logging
- Production security

---

**Questions?** See [multi-tenancy best practices](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/) or [OWASP guidelines](https://owasp.org/www-project-multi-tenant-service-checklist/)

Happy building! 🚀
