# Tutorial 2: Adding Neo4j Memory

**Objective:** Master persistent memory with Neo4j—store facts, relationships, and retrieve them across sessions.

**Time:** 20 minutes  
**Difficulty:** Intermediate  
**Prerequisites:** Completed Tutorial 1, Neo4j running

---

## What You'll Build

A chatbot that:
- Stores user facts and preferences persistently
- Builds a knowledge graph of user information
- Retrieves relevant memories for context
- Searches across stored facts
- Maintains conversation history automatically

---

## Prerequisites Checklist

```bash
# 1. Complete Tutorial 1
cd my_chatbot

# 2. Verify Neo4j connection
docker ps | grep neo4j

# 3. Access Neo4j Browser (optional, for visualization)
# Open: http://localhost:7474 (default: neo4j / password)

# 4. Install additional tools
pip install neo4j  # Already included with agentic-brain
```

---

## Part 1: Understanding Neo4j Memory

Neo4j is a **graph database** that stores data as **nodes** and **relationships**:

```
┌─────────────────────────────────────────────────┐
│           Neo4j Graph Structure                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  [User: alice_001]                             │
│       ├─ WORKS_IN → [Role: Engineer]           │
│       ├─ LIKES → [Tech: Python]                │
│       ├─ KNOWS → [Skill: FastAPI]              │
│       └─ PREFERS → [Style: Detailed]           │
│                                                 │
│  [Conversation: 2024-01-15]                    │
│       ├─ PARTICIPATED_BY → [User: alice_001]  │
│       ├─ ABOUT_TOPIC → [Topic: API Design]    │
│       └─ HAD_MESSAGE → [Message: "..."]       │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Why Neo4j for AI Memory?**
- Fast queries: Find related facts instantly
- Natural structure: Facts become relationships
- Scalable: Handle thousands of users with millions of facts
- Queryable: Use Cypher language to search

---

## Part 2: Memory Data Types

Create `memory_types.py`:

```python
"""
Data types for Neo4j memory storage.

Defines what types of information we store and how they relate.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class MemoryType(Enum):
    """Types of memories we can store."""
    PREFERENCE = "preference"       # "I like Python"
    EXPERIENCE = "experience"       # "I built a web app"
    FACT = "fact"                   # "I work in marketing"
    RELATIONSHIP = "relationship"   # "I know Alice"
    SKILL = "skill"                 # "I know Python"
    CONTEXT = "context"             # Current conversation context


@dataclass
class UserMemory:
    """A single piece of user memory."""
    user_id: str
    memory_type: MemoryType
    content: str
    source: str = "chat"  # Where this came from (chat, import, etc.)
    confidence: float = 0.8  # How confident are we in this memory?
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "type": self.memory_type.value,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp
        }


@dataclass
class UserProfile:
    """Complete user profile from memories."""
    user_id: str
    preferences: List[str]
    experiences: List[str]
    facts: List[str]
    skills: List[str]
    relationships: Dict[str, str]
    
    @classmethod
    def from_memories(cls, user_id: str, memories: List[UserMemory]) -> "UserProfile":
        """Construct profile from individual memories."""
        profile = cls(
            user_id=user_id,
            preferences=[],
            experiences=[],
            facts=[],
            skills=[],
            relationships={}
        )
        
        for memory in memories:
            if memory.memory_type == MemoryType.PREFERENCE:
                profile.preferences.append(memory.content)
            elif memory.memory_type == MemoryType.EXPERIENCE:
                profile.experiences.append(memory.content)
            elif memory.memory_type == MemoryType.FACT:
                profile.facts.append(memory.content)
            elif memory.memory_type == MemoryType.SKILL:
                profile.skills.append(memory.content)
        
        return profile


@dataclass
class ConversationContext:
    """Context for a conversation turn."""
    user_id: str
    messages: List[str]  # Last N messages
    relevant_memories: List[str]  # Memories relevant to current query
    conversation_summary: Optional[str] = None
    
    def to_prompt(self) -> str:
        """Format context for LLM prompt."""
        prompt = ""
        
        if self.relevant_memories:
            prompt += "Relevant facts about the user:\n"
            for mem in self.relevant_memories:
                prompt += f"- {mem}\n"
            prompt += "\n"
        
        if self.messages:
            prompt += "Recent conversation:\n"
            for msg in self.messages[-3:]:  # Last 3 messages
                prompt += f"- {msg}\n"
        
        return prompt
```

---

## Part 3: Extended Neo4j Memory Class

Create `advanced_memory.py`:

```python
"""
Advanced memory management with Neo4j.

Provides methods to store, retrieve, and search user memories.
"""

import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from agentic_brain import Neo4jMemory
from memory_types import UserMemory, UserProfile, MemoryType, ConversationContext

logger = logging.getLogger(__name__)


class AdvancedMemory(Neo4jMemory):
    """Extended Neo4j memory with intelligent storage and retrieval."""
    
    def __init__(self, uri: str, username: str, password: str):
        """Initialize advanced memory."""
        super().__init__(uri=uri, username=username, password=password)
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create necessary Neo4j indexes and constraints."""
        try:
            with self.driver.session() as session:
                # Create indexes for fast queries
                session.run("""
                    CREATE INDEX user_id_idx IF NOT EXISTS FOR (u:User) ON (u.user_id)
                """)
                session.run("""
                    CREATE INDEX memory_timestamp_idx IF NOT EXISTS 
                    FOR (m:Memory) ON (m.timestamp)
                """)
                logger.info("✅ Neo4j schema initialized")
        except Exception as e:
            logger.warning(f"Schema initialization: {e}")
    
    def store_memory(self, memory: UserMemory) -> bool:
        """
        Store a single memory for a user.
        
        Args:
            memory: The UserMemory object to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.driver.session() as session:
                session.run("""
                    MERGE (u:User {user_id: $user_id})
                    CREATE (m:Memory {
                        content: $content,
                        type: $type,
                        source: $source,
                        confidence: $confidence,
                        timestamp: $timestamp,
                        created_at: datetime()
                    })
                    CREATE (u)-[:HAS_MEMORY]->(m)
                """, {
                    "user_id": memory.user_id,
                    "content": memory.content,
                    "type": memory.memory_type.value,
                    "source": memory.source,
                    "confidence": memory.confidence,
                    "timestamp": memory.timestamp or datetime.now().isoformat()
                })
                logger.info(f"📝 Stored {memory.memory_type.value} for {memory.user_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return False
    
    def store_memories(self, memories: List[UserMemory]) -> int:
        """
        Store multiple memories efficiently.
        
        Args:
            memories: List of UserMemory objects
            
        Returns:
            Number of memories successfully stored
        """
        count = 0
        for memory in memories:
            if self.store_memory(memory):
                count += 1
        return count
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Get complete user profile from stored memories.
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            UserProfile object or None if user not found
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)
                    RETURN m.content as content, m.type as type, m.confidence as confidence
                    ORDER BY m.created_at DESC
                """, {"user_id": user_id})
                
                memories = []
                for record in result:
                    memory = UserMemory(
                        user_id=user_id,
                        memory_type=MemoryType(record["type"]),
                        content=record["content"],
                        confidence=record["confidence"]
                    )
                    memories.append(memory)
                
                if not memories:
                    logger.warning(f"No memories found for {user_id}")
                    return None
                
                profile = UserProfile.from_memories(user_id, memories)
                logger.info(f"📊 Retrieved profile for {user_id}: {len(memories)} memories")
                return profile
                
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None
    
    def search_memories(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 5
    ) -> List[str]:
        """
        Search user's memories by text (full-text search).
        
        Args:
            user_id: The user's ID
            query: Search query (e.g., "Python")
            limit: Maximum results
            
        Returns:
            List of matching memories
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)
                    WHERE toLower(m.content) CONTAINS toLower($query)
                    RETURN m.content as content
                    ORDER BY m.confidence DESC
                    LIMIT $limit
                """, {
                    "user_id": user_id,
                    "query": query,
                    "limit": limit
                })
                
                matches = [record["content"] for record in result]
                logger.info(f"🔍 Found {len(matches)} memories matching '{query}'")
                return matches
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_context_for_message(
        self,
        user_id: str,
        current_message: str,
        history_limit: int = 5,
        memory_limit: int = 3
    ) -> ConversationContext:
        """
        Get relevant context for responding to a user message.
        
        Combines recent history with relevant memories.
        
        Args:
            user_id: The user's ID
            current_message: The current user message
            history_limit: How many recent messages to include
            memory_limit: How many relevant memories to include
            
        Returns:
            ConversationContext object
        """
        try:
            # Get conversation history
            with self.driver.session() as session:
                history_result = session.run("""
                    MATCH (u:User {user_id: $user_id})-[:SENT_MESSAGE]->(msg:Message)
                    RETURN msg.content as content, msg.role as role
                    ORDER BY msg.timestamp DESC
                    LIMIT $limit
                """, {
                    "user_id": user_id,
                    "limit": history_limit
                })
                
                messages = []
                for record in history_result:
                    role = record.get("role", "user")
                    msg = record.get("content", "")
                    messages.append(f"{role}: {msg}")
                messages.reverse()
            
            # Search for relevant memories based on keywords in current message
            keywords = current_message.split()[:5]  # First 5 words
            relevant_memories = []
            
            for keyword in keywords:
                if len(keyword) > 3:  # Only search for meaningful words
                    matches = self.search_memories(user_id, keyword, limit=1)
                    relevant_memories.extend(matches)
            
            # Remove duplicates while preserving order
            relevant_memories = list(dict.fromkeys(relevant_memories))[:memory_limit]
            
            context = ConversationContext(
                user_id=user_id,
                messages=messages,
                relevant_memories=relevant_memories
            )
            
            logger.debug(f"Context prepared: {len(messages)} messages, {len(relevant_memories)} memories")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return ConversationContext(
                user_id=user_id,
                messages=[],
                relevant_memories=[]
            )
    
    def delete_old_memories(self, user_id: str, days: int = 30) -> int:
        """
        Delete memories older than N days (for privacy).
        
        Args:
            user_id: The user's ID
            days: Delete memories older than this many days
            
        Returns:
            Number of memories deleted
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)
                    WHERE duration.inDays(m.created_at, datetime()).days > $days
                    DETACH DELETE m
                    RETURN count(m) as deleted
                """, {
                    "user_id": user_id,
                    "days": days
                })
                
                deleted = result.single()["deleted"] if result else 0
                logger.info(f"🗑️  Deleted {deleted} old memories for {user_id}")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to delete memories: {e}")
            return 0
    
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export all user data (for GDPR compliance).
        
        Args:
            user_id: The user's ID
            
        Returns:
            Dictionary with all user data
        """
        try:
            profile = self.get_user_profile(user_id)
            if not profile:
                return {}
            
            return {
                "user_id": user_id,
                "profile": {
                    "facts": profile.facts,
                    "preferences": profile.preferences,
                    "experiences": profile.experiences,
                    "skills": profile.skills
                },
                "exported_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return {}
```

---

## Part 4: Use It All Together

Create `memory_demo.py`:

```python
"""
Demonstration of advanced memory capabilities.
"""

import logging
from advanced_memory import AdvancedMemory
from memory_types import UserMemory, MemoryType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_basic_memory_storage():
    """Store and retrieve memories."""
    print("\n" + "="*60)
    print("Demo 1: Basic Memory Storage")
    print("="*60 + "\n")
    
    # Initialize advanced memory
    memory = AdvancedMemory(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password"
    )
    
    # Create some memories
    memories = [
        UserMemory(
            user_id="dev_alice",
            memory_type=MemoryType.FACT,
            content="Alice works as a backend engineer"
        ),
        UserMemory(
            user_id="dev_alice",
            memory_type=MemoryType.SKILL,
            content="Expert in Python and FastAPI"
        ),
        UserMemory(
            user_id="dev_alice",
            memory_type=MemoryType.PREFERENCE,
            content="Prefers detailed explanations with code examples"
        ),
        UserMemory(
            user_id="dev_alice",
            memory_type=MemoryType.EXPERIENCE,
            content="Built production systems with 100K+ users"
        )
    ]
    
    # Store them
    count = memory.store_memories(memories)
    print(f"✅ Stored {count} memories for dev_alice\n")
    
    # Retrieve profile
    profile = memory.get_user_profile("dev_alice")
    if profile:
        print(f"📊 Retrieved Profile for {profile.user_id}:")
        print(f"   Facts: {profile.facts}")
        print(f"   Skills: {profile.skills}")
        print(f"   Preferences: {profile.preferences}")
        print(f"   Experiences: {profile.experiences}\n")


def demo_memory_search():
    """Search through memories."""
    print("\n" + "="*60)
    print("Demo 2: Memory Search")
    print("="*60 + "\n")
    
    memory = AdvancedMemory(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password"
    )
    
    # Search for memories about Python
    print("Searching for memories about 'Python':\n")
    results = memory.search_memories("dev_alice", "Python", limit=5)
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result}")
    print()


def demo_context_building():
    """Get context for responding to messages."""
    print("\n" + "="*60)
    print("Demo 3: Context Building for Conversation")
    print("="*60 + "\n")
    
    memory = AdvancedMemory(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password"
    )
    
    # Build context for a question
    question = "I need help with my Python API project. Should I use FastAPI?"
    
    context = memory.get_context_for_message(
        user_id="dev_alice",
        current_message=question,
        history_limit=5,
        memory_limit=3
    )
    
    print(f"Question: {question}\n")
    print("Context prepared for LLM:")
    
    prompt = context.to_prompt()
    print(prompt)


def demo_data_export():
    """Export user data for GDPR."""
    print("\n" + "="*60)
    print("Demo 4: Data Export (GDPR)")
    print("="*60 + "\n")
    
    memory = AdvancedMemory(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password"
    )
    
    # Export all user data
    export = memory.export_user_data("dev_alice")
    
    print(f"✅ Exported data for {export.get('user_id')}:")
    import json
    print(json.dumps(export, indent=2))


if __name__ == "__main__":
    try:
        demo_basic_memory_storage()
        demo_memory_search()
        demo_context_building()
        demo_data_export()
        
        print("\n" + "="*60)
        print("✅ All memory demos completed!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
```

---

## Part 5: Integrate with Your Chatbot

Update `bot.py` to use advanced memory:

```python
from advanced_memory import AdvancedMemory
from memory_types import UserMemory, MemoryType

class EnhancedChatbot(SimpleChatbot):
    """Chatbot with advanced memory features."""
    
    def __init__(self, name: str, user_id: str):
        # Initialize like before but with advanced memory
        self.memory = AdvancedMemory(
            uri=config.NEO4J_URI,
            username=config.NEO4J_USERNAME,
            password=config.NEO4J_PASSWORD
        )
        
        self.agent = Agent(
            name=name,
            memory=self.memory,
            llm_provider=config.LLM_PROVIDER,
            llm_model=config.LLM_MODEL,
            system_prompt=config.SYSTEM_PROMPT
        )
        
        self.name = name
        self.user_id = user_id
    
    def extract_and_store_facts(self, message: str) -> None:
        """
        Extract facts from a message and store them.
        
        In production, you'd use NLP/LLM to extract facts.
        For now, simple heuristics.
        """
        # Example: Extract statements starting with "I"
        if message.lower().startswith("i "):
            # Determine memory type
            if any(word in message.lower() for word in ["prefer", "like", "love", "hate"]):
                memory_type = MemoryType.PREFERENCE
            elif any(word in message.lower() for word in ["know", "skilled", "expert"]):
                memory_type = MemoryType.SKILL
            elif any(word in message.lower() for word in ["work", "job", "role"]):
                memory_type = MemoryType.FACT
            elif any(word in message.lower() for word in ["built", "created", "made", "done"]):
                memory_type = MemoryType.EXPERIENCE
            else:
                memory_type = MemoryType.FACT
            
            # Store it
            memory = UserMemory(
                user_id=self.user_id,
                memory_type=memory_type,
                content=message,
                source="chat_extraction"
            )
            self.memory.store_memory(memory)
```

---

## Step 6: Run the Memory Demo

```bash
python memory_demo.py
```

**Expected Output:**

```
============================================================
Demo 1: Basic Memory Storage
============================================================

✅ Stored 4 memories for dev_alice

📊 Retrieved Profile for dev_alice:
   Facts: ['Alice works as a backend engineer']
   Skills: ['Expert in Python and FastAPI']
   Preferences: ['Prefers detailed explanations with code examples']
   Experiences: ['Built production systems with 100K+ users']

============================================================
Demo 2: Memory Search
============================================================

Searching for memories about 'Python':

  1. Expert in Python and FastAPI

============================================================
Demo 3: Context Building for Conversation
============================================================

Question: I need help with my Python API project. Should I use FastAPI?

Context prepared for LLM:
Relevant facts about the user:
- Expert in Python and FastAPI
- Alice works as a backend engineer

============================================================
Demo 4: Data Export (GDPR)
============================================================

✅ Exported data for dev_alice:
{
  "user_id": "dev_alice",
  "profile": {
    "facts": ["Alice works as a backend engineer"],
    "preferences": ["Prefers detailed explanations with code examples"],
    "experiences": ["Built production systems with 100K+ users"],
    "skills": ["Expert in Python and FastAPI"]
  },
  "exported_at": "2024-01-15T10:30:00.123456"
}

============================================================
✅ All memory demos completed!
============================================================
```

---

## Neo4j Queries Reference

Access your memories directly via Neo4j Browser (http://localhost:7474):

```cypher
# Find all memories for a user
MATCH (u:User {user_id: "dev_alice"})-[:HAS_MEMORY]->(m:Memory)
RETURN m.content, m.type, m.created_at
ORDER BY m.created_at DESC

# Count memories by type
MATCH (u:User {user_id: "dev_alice"})-[:HAS_MEMORY]->(m:Memory)
RETURN m.type, COUNT(*) as count
GROUP BY m.type

# Find users with specific skills
MATCH (u:User)-[:HAS_MEMORY]->(m:Memory)
WHERE m.type = "skill" AND m.content CONTAINS "Python"
RETURN u.user_id, m.content

# Find recent memories across all users
MATCH (u:User)-[:HAS_MEMORY]->(m:Memory)
WHERE m.created_at > datetime() - duration({days: 7})
RETURN u.user_id, m.content, m.created_at
ORDER BY m.created_at DESC
```

---

## 🆘 Troubleshooting

### ❌ "Memory not being saved"

```python
# Verify memory operations are working
memory = AdvancedMemory(...)
memory.store_memory(UserMemory(...))

# Check in Neo4j Browser
# Run: MATCH (u:User) RETURN count(u)
```

### ❌ "Neo4j schema creation fails"

```python
# Clear and reinitialize (dev only!)
# In Neo4j Browser: MATCH (n) DETACH DELETE n
memory._ensure_schema()  # Retry
```

### ❌ "Search returns no results"

```python
# Verify data exists first
profile = memory.get_user_profile(user_id)
print(profile)  # Should show memories

# Search is case-insensitive but requires exact substring match
results = memory.search_memories(user_id, "Python")  # ✅
results = memory.search_memories(user_id, "python")  # Also ✅
```

---

## ✅ What You've Learned

- ✅ Store multiple types of memories (facts, skills, preferences, experiences)
- ✅ Retrieve complete user profiles from Neo4j
- ✅ Search memories by keyword
- ✅ Build conversational context from memories
- ✅ Export user data for GDPR compliance
- ✅ Query Neo4j directly with Cypher

---

## 🚀 Next Steps

1. **[Tutorial 3: RAG Chatbot](./03-rag-chatbot.md)** - Ground responses in documents
2. **[Tutorial 4: Multi-User SaaS](./04-multi-user.md)** - Tenant isolation
3. **[Tutorial 5: Production Deployment](./05-deployment.md)** - Docker & scaling

---

**Questions?** Check the [Neo4j documentation](https://neo4j.com/docs/) or [Cypher guide](https://neo4j.com/docs/cypher-manual/)

Happy coding! 🧠
