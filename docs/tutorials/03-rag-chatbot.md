# Tutorial 3: RAG Chatbot (Retrieval-Augmented Generation)

**Objective:** Build a chatbot that grounds responses in documents—perfect for knowledge bases, FAQs, and product documentation.

**Time:** 25 minutes  
**Difficulty:** Intermediate  
**Prerequisites:** Completed Tutorials 1-2, Neo4j running

---

## What You'll Build

A chatbot that:
- Loads documents from files or URLs
- Splits large documents into chunks
- Retrieves relevant chunks based on user queries
- Uses retrieved context to ground LLM responses
- Cites sources in responses

**Use Cases:**
- Customer support (grounded in ticket history)
- Technical Q&A (grounded in documentation)
- Legal assistant (grounded in contracts)
- Product recommendations (grounded in catalogs)

---

## Why RAG?

**Without RAG:**
```
User: "What's your refund policy?"
Bot: "I don't have specific information about that."
❌ Not helpful
```

**With RAG:**
```
User: "What's your refund policy?"
System retrieves: "We offer 30-day refunds for all items"
Bot: "According to our policy, we offer 30-day refunds for all items."
✅ Accurate and helpful!
```

---

## Prerequisites Checklist

```bash
# 1. Install additional packages
pip install agentic-brain[rag]

# Or install individually:
pip install langchain sentence-transformers chromadb

# 2. Verify dependencies
python -c "import langchain; import chromadb; print('✅ RAG ready')"

# 3. Neo4j should still be running
docker ps | grep neo4j
```

---

## Part 1: Document Management

Create `documents.py`:

```python
"""
Document management for RAG.

Handles loading, chunking, and storing documents.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A single document chunk."""
    id: str
    content: str
    source: str  # Filename or URL
    metadata: Dict[str, Any]
    chunk_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "metadata": self.metadata,
            "chunk_index": self.chunk_index
        }


class DocumentLoader:
    """Load documents from various sources."""
    
    @staticmethod
    def load_from_file(file_path: str, chunk_size: int = 500) -> List[Document]:
        """
        Load and chunk a text file.
        
        Args:
            file_path: Path to text file
            chunk_size: Characters per chunk
            
        Returns:
            List of Document objects
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            documents = DocumentLoader.chunk_text(
                content,
                file_path,
                chunk_size
            )
            logger.info(f"📄 Loaded {file_path}: {len(documents)} chunks")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return []
    
    @staticmethod
    def load_from_directory(
        directory: str,
        chunk_size: int = 500,
        pattern: str = "*.txt"
    ) -> List[Document]:
        """
        Load all text files from a directory.
        
        Args:
            directory: Directory path
            chunk_size: Characters per chunk
            pattern: File pattern (*.txt, *.md, etc.)
            
        Returns:
            List of all Document objects
        """
        documents = []
        
        for file_path in Path(directory).glob(pattern):
            docs = DocumentLoader.load_from_file(
                str(file_path),
                chunk_size
            )
            documents.extend(docs)
        
        logger.info(f"📂 Loaded {directory}: {len(documents)} total chunks")
        return documents
    
    @staticmethod
    def chunk_text(
        text: str,
        source: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[Document]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text to chunk
            source: Document source (filename)
            chunk_size: Characters per chunk
            overlap: Overlap between chunks
            
        Returns:
            List of Document chunks
        """
        documents = []
        chunks = []
        
        # Simple chunking: split by sentences/lines with overlap
        lines = text.split('\n')
        current_chunk = ""
        
        for line in lines:
            if len(current_chunk) + len(line) < chunk_size:
                current_chunk += line + "\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                current_chunk = current_chunk[-overlap:] + line + "\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Create Document objects
        for i, chunk in enumerate(chunks):
            if chunk:  # Skip empty chunks
                doc = Document(
                    id=f"{source}_chunk_{i}",
                    content=chunk,
                    source=source,
                    metadata={
                        "chunk_index": i,
                        "chunk_count": len(chunks),
                        "source_type": "text"
                    },
                    chunk_index=i
                )
                documents.append(doc)
        
        return documents


class DocumentStore:
    """Store and retrieve documents efficiently."""
    
    def __init__(self, storage_dir: str = "./document_store"):
        """Initialize document store."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.documents: Dict[str, Document] = {}
    
    def add_documents(self, documents: List[Document]) -> int:
        """
        Add documents to store.
        
        Args:
            documents: List of Document objects
            
        Returns:
            Number of documents added
        """
        for doc in documents:
            self.documents[doc.id] = doc
        
        logger.info(f"📚 Added {len(documents)} documents. Total: {len(self.documents)}")
        return len(documents)
    
    def search_documents(self, query: str, limit: int = 5) -> List[Document]:
        """
        Simple keyword search (in production, use semantic search).
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of relevant documents
        """
        query_words = set(query.lower().split())
        scored_docs = []
        
        for doc in self.documents.values():
            content_words = set(doc.content.lower().split())
            # Score = number of matching words
            score = len(query_words & content_words)
            if score > 0:
                scored_docs.append((doc, score))
        
        # Sort by score and return top results
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored_docs[:limit]]
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific document by ID."""
        return self.documents.get(doc_id)
    
    def list_documents(self) -> List[str]:
        """List all unique source documents."""
        sources = set()
        for doc in self.documents.values():
            sources.add(doc.source)
        return sorted(list(sources))
```

---

## Part 2: Semantic Search with Embeddings

Create `embeddings.py`:

```python
"""
Semantic search using embeddings.

Uses sentence-transformers for better document retrieval.
"""

import logging
from typing import List, Tuple
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer, util
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logging.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")

from documents import Document, DocumentStore

logger = logging.getLogger(__name__)


class EmbeddingStore:
    """Store and search documents using embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding store.
        
        Args:
            model_name: Sentence transformer model to use
                       (smaller: all-MiniLM-L6-v2, better: all-mpnet-base-v2)
        """
        if not EMBEDDINGS_AVAILABLE:
            raise ImportError("Install sentence-transformers: pip install sentence-transformers")
        
        self.model = SentenceTransformer(model_name)
        self.document_embeddings: dict = {}
        logger.info(f"✅ Loaded embedding model: {model_name}")
    
    def add_documents(self, documents: List[Document]) -> None:
        """
        Compute and store embeddings for documents.
        
        Args:
            documents: List of Document objects
        """
        if not documents:
            return
        
        # Extract content
        contents = [doc.content for doc in documents]
        
        # Compute embeddings
        logger.info(f"Computing embeddings for {len(documents)} documents...")
        embeddings = self.model.encode(contents, show_progress_bar=True)
        
        # Store embeddings with document IDs
        for doc, embedding in zip(documents, embeddings):
            self.document_embeddings[doc.id] = {
                "document": doc,
                "embedding": embedding
            }
        
        logger.info(f"✅ Stored {len(self.document_embeddings)} document embeddings")
    
    def search(self, query: str, limit: int = 5) -> List[Tuple[Document, float]]:
        """
        Semantic search using embeddings.
        
        Args:
            query: Natural language query
            limit: Maximum results
            
        Returns:
            List of (Document, similarity_score) tuples
        """
        if not self.document_embeddings:
            logger.warning("No documents indexed. Add documents first.")
            return []
        
        # Encode query
        query_embedding = self.model.encode(query)
        
        # Compute similarity with all documents
        results = []
        for doc_id, data in self.document_embeddings.items():
            doc_embedding = data["embedding"]
            # Cosine similarity
            similarity = util.pytorch_cos_sim(query_embedding, doc_embedding).item()
            results.append((data["document"], similarity))
        
        # Sort by similarity and return top results
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by minimum similarity threshold (0.1)
        results = [(doc, score) for doc, score in results if score > 0.1]
        
        return results[:limit]
    
    def get_stats(self) -> dict:
        """Get store statistics."""
        return {
            "total_documents": len(self.document_embeddings),
            "model": self.model.get_sentence_embedding_dimension(),
            "ready": len(self.document_embeddings) > 0
        }
```

---

## Part 3: RAG Chatbot

Create `rag_bot.py`:

```python
"""
RAG Chatbot - grounded in documents.

Retrieves relevant documents before generating responses.
"""

import logging
from typing import List, Optional, Dict, Any

from agentic_brain import Agent, Neo4jMemory
from documents import Document, DocumentStore, DocumentLoader
from embeddings import EmbeddingStore, EMBEDDINGS_AVAILABLE
import config

logger = logging.getLogger(__name__)


class RAGChatbot:
    """
    Retrieval-Augmented Generation chatbot.
    
    Workflow:
    1. User asks a question
    2. System retrieves relevant documents
    3. System uses retrieved docs as context
    4. LLM generates grounded response
    """
    
    def __init__(
        self,
        name: str,
        user_id: str,
        documents_dir: Optional[str] = None,
        use_embeddings: bool = True
    ):
        """
        Initialize RAG chatbot.
        
        Args:
            name: Bot name
            user_id: User identifier
            documents_dir: Directory containing knowledge base documents
            use_embeddings: Use semantic search (requires sentence-transformers)
        """
        self.name = name
        self.user_id = user_id
        self.use_embeddings = use_embeddings and EMBEDDINGS_AVAILABLE
        
        # Initialize memory
        try:
            self.memory = Neo4jMemory(
                uri=config.NEO4J_URI,
                username=config.NEO4J_USERNAME,
                password=config.NEO4J_PASSWORD
            )
            logger.info("✅ Memory initialized")
        except Exception as e:
            logger.error(f"Memory initialization failed: {e}")
            self.memory = None
        
        # Initialize agent
        try:
            self.agent = Agent(
                name=name,
                memory=self.memory,
                llm_provider=config.LLM_PROVIDER,
                llm_model=config.LLM_MODEL,
                system_prompt=self._get_rag_system_prompt()
            )
            logger.info("✅ Agent initialized")
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            raise
        
        # Initialize document stores
        self.doc_store = DocumentStore()
        self.embedding_store = None
        if self.use_embeddings:
            try:
                self.embedding_store = EmbeddingStore()
                logger.info("✅ Embeddings initialized")
            except Exception as e:
                logger.warning(f"Embeddings unavailable: {e}")
                self.use_embeddings = False
        
        # Load documents if provided
        if documents_dir:
            self.load_knowledge_base(documents_dir)
    
    def _get_rag_system_prompt(self) -> str:
        """System prompt for RAG chatbot."""
        return """You are a helpful assistant with access to a knowledge base.

Instructions:
- Answer questions based on the provided documents
- Cite sources when using information from documents
- If information isn't in the knowledge base, say so clearly
- Be honest about the limits of your knowledge
- Provide specific, detailed answers
- Format citations like: (Source: document_name)"""
    
    def load_knowledge_base(self, documents_dir: str) -> int:
        """
        Load documents from directory.
        
        Args:
            documents_dir: Path to directory with .txt or .md files
            
        Returns:
            Number of documents loaded
        """
        logger.info(f"Loading knowledge base from {documents_dir}...")
        
        # Load text files
        documents = DocumentLoader.load_from_directory(
            documents_dir,
            chunk_size=500,
            pattern="*.txt"
        )
        
        # Also load markdown
        documents.extend(
            DocumentLoader.load_from_directory(
                documents_dir,
                chunk_size=500,
                pattern="*.md"
            )
        )
        
        if not documents:
            logger.warning(f"No documents found in {documents_dir}")
            return 0
        
        # Add to stores
        self.doc_store.add_documents(documents)
        
        if self.use_embeddings and self.embedding_store:
            self.embedding_store.add_documents(documents)
        
        logger.info(f"✅ Loaded {len(documents)} documents")
        return len(documents)
    
    def retrieve_context(self, query: str, limit: int = 3) -> List[Document]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: User's question
            limit: Max documents to retrieve
            
        Returns:
            List of relevant documents
        """
        if self.use_embeddings and self.embedding_store:
            # Use semantic search
            results = self.embedding_store.search(query, limit)
            docs = [doc for doc, _ in results]
            logger.info(f"🔍 Retrieved {len(docs)} documents via embeddings")
            return docs
        else:
            # Fall back to keyword search
            docs = self.doc_store.search_documents(query, limit)
            logger.info(f"🔍 Retrieved {len(docs)} documents via keywords")
            return docs
    
    def chat(self, message: str) -> str:
        """
        Chat with RAG-enhanced response.
        
        Args:
            message: User's message
            
        Returns:
            Bot's response with citations
        """
        try:
            logger.info(f"User ({self.user_id}): {message}")
            
            # Retrieve relevant documents
            documents = self.retrieve_context(message, limit=3)
            
            # Build context from documents
            context = ""
            sources_used = set()
            
            if documents:
                context = "Relevant information:\n\n"
                for i, doc in enumerate(documents, 1):
                    context += f"[{i}] {doc.content}\n\n"
                    sources_used.add(doc.source)
            else:
                context = "(No relevant documents found in knowledge base)\n"
            
            # Create enhanced prompt with context
            enhanced_prompt = f"""{message}

{context}
Based on the information above, provide a helpful response. If using information from the sources, cite them."""
            
            # Get response from agent
            response = self.agent.chat(
                message=enhanced_prompt,
                user_id=self.user_id
            )
            
            # Add citations
            if sources_used:
                response += f"\n\n📚 Sources: {', '.join(sources_used)}"
            
            logger.info(f"Bot ({self.name}): Generated response")
            return response
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Sorry, I encountered an error: {e}"
    
    def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded knowledge base."""
        stats = {
            "total_documents": len(self.doc_store.documents),
            "sources": self.doc_store.list_documents(),
            "using_embeddings": self.use_embeddings
        }
        
        if self.use_embeddings and self.embedding_store:
            stats.update(self.embedding_store.get_stats())
        
        return stats


def main():
    """Demo RAG chatbot."""
    
    print("\n" + "="*60)
    print("🤖 RAG Chatbot Demo")
    print("="*60 + "\n")
    
    # Create sample knowledge base
    print("📚 Creating sample knowledge base...")
    sample_docs_dir = "./sample_kb"
    import os
    os.makedirs(sample_docs_dir, exist_ok=True)
    
    # Create sample documents
    sample_docs = {
        "api_guide.txt": """API Documentation

Authentication:
Our API uses Bearer token authentication. Include your token in the Authorization header:
Authorization: Bearer YOUR_TOKEN

Rate Limits:
- Free tier: 100 requests per hour
- Pro tier: 1000 requests per hour
- Enterprise: Unlimited

Error Codes:
- 400: Bad request
- 401: Unauthorized
- 429: Rate limit exceeded
- 500: Server error""",
        
        "refund_policy.txt": """Refund Policy

We offer a 30-day refund policy for all purchases.

Eligibility:
- Items must be returned within 30 days of purchase
- Items must be in original condition
- Digital purchases are non-refundable

Process:
1. Contact support with your order number
2. We'll send you a return label
3. Ship the item back
4. Refund processed within 5-7 business days"""
    }
    
    for filename, content in sample_docs.items():
        with open(f"{sample_docs_dir}/{filename}", "w") as f:
            f.write(content)
    
    print(f"✅ Created {len(sample_docs)} sample documents\n")
    
    # Initialize RAG bot
    bot = RAGChatbot(
        name="support_agent",
        user_id="demo_user",
        documents_dir=sample_docs_dir,
        use_embeddings=EMBEDDINGS_AVAILABLE
    )
    
    # Print knowledge base stats
    stats = bot.get_knowledge_base_stats()
    print(f"📊 Knowledge Base Stats:")
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Sources: {stats['sources']}")
    print(f"   Using embeddings: {stats['using_embeddings']}\n")
    
    # Example questions
    questions = [
        "How do I authenticate with your API?",
        "What's your refund policy?",
        "What are the rate limits?"
    ]
    
    for question in questions:
        print(f"👤 You: {question}")
        response = bot.chat(question)
        print(f"🤖 Bot: {response}\n")
        print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
```

---

## Step 4: Create Sample Knowledge Base

Create `setup_kb.py`:

```bash
mkdir knowledge_base

cat > knowledge_base/getting_started.md << 'EOF'
# Getting Started

## Installation
1. Install package: pip install our-service
2. Create account
3. Get API key
4. Start building!

## Quick Start
```python
from our_service import Client
client = Client(api_key="your_key")
result = client.query("Hello!")
```

## Support
Email: support@example.com
EOF

cat > knowledge_base/pricing.txt << 'EOF'
PRICING PLANS

Starter: $29/month
- 10,000 API calls
- Email support
- 1 user account

Professional: $99/month
- 100,000 API calls
- Priority support
- 5 user accounts

Enterprise: Custom
- Unlimited calls
- Dedicated support
- Custom SLA
EOF
```

---

## Step 5: Run the RAG Bot

```bash
python rag_bot.py
```

**Expected Output:**

```
============================================================
🤖 RAG Chatbot Demo
============================================================

📚 Creating sample knowledge base...
✅ Created 2 sample documents

✅ Embeddings initialized
📄 Loaded sample_kb/api_guide.txt: 3 chunks
📄 Loaded sample_kb/refund_policy.txt: 2 chunks
✅ Loaded 5 documents

📊 Knowledge Base Stats:
   Total documents: 5
   Sources: ['sample_kb/api_guide.txt', 'sample_kb/refund_policy.txt']
   Using embeddings: True

👤 You: How do I authenticate with your API?
🔍 Retrieved 1 documents via embeddings
🤖 Bot: According to the API documentation, you should use Bearer token authentication. Include your token in the Authorization header like this:

Authorization: Bearer YOUR_TOKEN

This ensures your requests are properly authenticated with our API.

📚 Sources: sample_kb/api_guide.txt

------------------------------------------------------------

👤 You: What's your refund policy?
🔍 Retrieved 1 documents via embeddings
🤖 Bot: Our refund policy allows returns within 30 days of purchase. Here are the key points:

Eligibility Requirements:
- Items must be returned within 30 days of purchase
- Items must be in original condition
- Digital purchases are non-refundable

The Refund Process:
1. Contact support with your order number
2. We'll send you a return label
3. Ship the item back
4. Your refund will be processed within 5-7 business days

📚 Sources: sample_kb/refund_policy.txt

------------------------------------------------------------
```

---

## 🆘 Troubleshooting

### ❌ "sentence_transformers not installed"

```bash
pip install sentence-transformers
# If that's slow, you can use CPU-only:
pip install sentence-transformers onnxruntime
```

### ❌ "No documents found"

```python
# Check documents directory exists
import os
print(os.listdir("knowledge_base"))

# Verify file extensions are .txt or .md
for f in os.listdir("knowledge_base"):
    print(f)  # Should end in .txt or .md
```

### ❌ "Embeddings taking too long"

This is normal! First embedding computation caches the model (~120MB).

```python
# Subsequent runs will be fast (cached)
# Can disable if speed matters:
bot = RAGChatbot(..., use_embeddings=False)  # Falls back to keyword search
```

### ❌ "Retrieved documents not relevant"

```python
# Increase search results and let LLM filter
documents = bot.retrieve_context(query, limit=5)  # Instead of 3

# Or check document quality
for doc in bot.doc_store.documents.values():
    print(doc.content)  # Verify documents are useful
```

---

## ✅ What You've Learned

- ✅ Load and chunk documents
- ✅ Store documents efficiently
- ✅ Use semantic search with embeddings
- ✅ Retrieve relevant context for queries
- ✅ Ground LLM responses in documents
- ✅ Cite sources in responses

---

## 🚀 Next Steps

1. **[Tutorial 4: Multi-User SaaS](./04-multi-user.md)** - Tenant isolation patterns
2. **[Tutorial 5: Production Deployment](./05-deployment.md)** - Docker & scaling
3. Add more documents to your knowledge base
4. Fine-tune retrieval by adjusting chunk_size and limits

---

**Questions?** Check [RAG best practices](https://python.langchain.com/docs/modules/data_connection/retrieval/) or [embeddings guide](https://www.sbert.net/)

Happy building! 🚀
