#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
RAG-Enabled Chatbot Example
============================

A chatbot that answers questions based on loaded documents using
Retrieval-Augmented Generation (RAG). The chatbot retrieves relevant
document chunks and uses them as context for answering questions.

Features:
- Load documents into RAG pipeline
- Retrieve relevant context for questions
- Answer questions with source citations
- Interactive Q&A session
- Beautiful formatted output with sources

Run with: python examples/rag_chat.py

Requirements:
- Ollama running locally (for embeddings and LLM)
  * ollama pull nomic-embed-text (for embeddings)
  * ollama pull llama3.1:8b (for chat)
- Neo4j running (optional, for document storage)
- Documents in a directory (.txt, .md, .py files)

Quick Start:
    1. Put some documents in a folder (e.g., docs/)
    2. Run: python examples/rag_chat.py docs/
    3. Type questions about your documents
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
from agentic_brain.rag import RAGPipeline
from agentic_brain.chat import Chatbot, ChatConfig


class RAGChatbot:
    """
    A chatbot that uses RAG to answer questions based on documents.
    
    This is a wrapper around both RAGPipeline and Chatbot that combines:
    - Document retrieval (RAG)
    - Conversational context (Chat)
    
    Usage:
        # Create and load documents
        bot = RAGChatbot()
        bot.load_documents("docs/")
        
        # Ask questions
        response = bot.ask("What is the deployment process?")
        print(response)
    """
    
    def __init__(
        self,
        llm_provider: str = "ollama",
        llm_model: str = "llama3.1:8b",
        embedding_model: str = "nomic-embed-text",
        neo4j_uri: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """
        Initialize the RAG chatbot.
        
        Args:
            llm_provider: LLM provider ("ollama" or "openai")
            llm_model: LLM model name
            embedding_model: Embedding model name
            neo4j_uri: Optional Neo4j connection URI
            neo4j_password: Optional Neo4j password
        """
        # Initialize RAG pipeline for document retrieval
        self.rag = RAGPipeline(
            neo4j_uri=neo4j_uri,
            neo4j_password=neo4j_password,
            llm_provider=llm_provider,
            llm_model=llm_model
        )
        
        # Initialize chatbot for conversation
        config = ChatConfig.minimal()
        self.chatbot = Chatbot("rag-assistant", config=config)
        
        # Track loaded documents
        self.loaded_documents = []
        self.document_chunks = {}
        
        print(f"✅ RAG Chatbot initialized")
        print(f"   LLM: {llm_provider}/{llm_model}")
        print(f"   Embeddings: {embedding_model}")
    
    def load_documents_from_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None
    ) -> int:
        """
        Load documents from a directory into the RAG pipeline.
        
        Supports: .txt, .md, .py, .json files
        Each file is treated as a separate document source.
        
        Args:
            directory: Path to directory containing documents
            extensions: File extensions to load (default: .txt, .md, .py)
            
        Returns:
            Number of documents loaded
            
        Example:
            num_docs = bot.load_documents_from_directory("docs/")
            print(f"Loaded {num_docs} documents")
        """
        extensions = extensions or [".txt", ".md", ".py", ".json"]
        dir_path = Path(directory)
        
        if not dir_path.exists():
            print(f"❌ Directory not found: {directory}")
            return 0
        
        docs_loaded = 0
        
        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                try:
                    content = file_path.read_text()
                    
                    # Store document
                    doc_id = f"{file_path.name}:{docs_loaded}"
                    self.loaded_documents.append({
                        "id": doc_id,
                        "path": str(file_path),
                        "name": file_path.name,
                        "extension": ext,
                        "size": len(content),
                        "preview": content[:200] + "..." if len(content) > 200 else content
                    })
                    
                    # Split into chunks if large
                    if len(content) > 2000:
                        chunks = self._chunk_document(content, chunk_size=2000)
                        self.document_chunks[doc_id] = chunks
                    else:
                        self.document_chunks[doc_id] = [content]
                    
                    docs_loaded += 1
                    print(f"  ✓ Loaded: {file_path.name} ({len(content)} chars)")
                    
                except Exception as e:
                    print(f"  ⚠️  Failed to load {file_path.name}: {e}")
        
        print(f"✅ Loaded {docs_loaded} documents")
        return docs_loaded
    
    def load_documents_from_strings(self, documents: dict) -> int:
        """
        Load documents from a dictionary of name -> content.
        
        Useful for programmatic document loading or testing.
        
        Args:
            documents: Dict mapping document names to content
            
        Returns:
            Number of documents loaded
            
        Example:
            docs = {
                "deployment.txt": "To deploy, run: ./deploy.sh",
                "api_docs.txt": "API endpoints are at /api/v1/..."
            }
            bot.load_documents_from_strings(docs)
        """
        docs_loaded = 0
        
        for name, content in documents.items():
            try:
                doc_id = f"{name}:{docs_loaded}"
                self.loaded_documents.append({
                    "id": doc_id,
                    "name": name,
                    "size": len(content),
                    "preview": content[:200] + "..." if len(content) > 200 else content
                })
                
                # Split into chunks
                if len(content) > 2000:
                    chunks = self._chunk_document(content, chunk_size=2000)
                    self.document_chunks[doc_id] = chunks
                else:
                    self.document_chunks[doc_id] = [content]
                
                docs_loaded += 1
                print(f"  ✓ Loaded: {name}")
                
            except Exception as e:
                print(f"  ⚠️  Failed to load {name}: {e}")
        
        print(f"✅ Loaded {docs_loaded} documents")
        return docs_loaded
    
    def _chunk_document(self, content: str, chunk_size: int = 2000) -> List[str]:
        """
        Split a document into chunks for better retrieval.
        
        Args:
            content: Document content
            chunk_size: Target chunk size in characters
            
        Returns:
            List of chunks
        """
        chunks = []
        current_chunk = ""
        
        for line in content.split("\n"):
            if len(current_chunk) + len(line) > chunk_size:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def ask(
        self,
        question: str,
        k: int = 5,
        include_sources: bool = True
    ) -> str:
        """
        Ask a question about the loaded documents.
        
        The question is answered using RAG:
        1. Retrieve relevant document chunks
        2. Use LLM to generate answer with context
        3. Include source citations
        
        Args:
            question: The question to ask
            k: Number of document chunks to retrieve
            include_sources: Whether to include source citations
            
        Returns:
            Answer with optional source citations
            
        Example:
            answer = bot.ask("How do I deploy?")
            print(answer)
        """
        if not self.loaded_documents:
            return "❌ No documents loaded. Load documents first with load_documents()."
        
        try:
            # Query the RAG pipeline
            result = self.rag.query(
                query=question,
                k=k,
                use_cache=True
            )
            
            # Format response
            if include_sources and result.has_sources:
                response = result.format_with_citations()
            else:
                response = result.answer
            
            # Also add to chat history for context
            self.chatbot.chat(question, metadata={"type": "rag_query"})
            
            return response
            
        except Exception as e:
            print(f"❌ Error querying: {e}")
            return f"Sorry, I encountered an error while answering your question: {e}"
    
    def list_documents(self) -> None:
        """
        Print a list of loaded documents.
        
        Shows document names, sizes, and previews.
        """
        if not self.loaded_documents:
            print("No documents loaded.")
            return
        
        print("\n" + "=" * 70)
        print("📚 LOADED DOCUMENTS")
        print("=" * 70)
        
        for i, doc in enumerate(self.loaded_documents, 1):
            print(f"\n{i}. {doc['name']}")
            print(f"   Size: {doc['size']} chars")
            print(f"   Preview: {doc['preview']}")
        
        print("\n" + "=" * 70)
    
    def get_stats(self) -> dict:
        """
        Get statistics about loaded documents and chatbot.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "documents_loaded": len(self.loaded_documents),
            "total_chunks": sum(len(chunks) for chunks in self.document_chunks.values()),
            "total_content_chars": sum(doc["size"] for doc in self.loaded_documents),
            "chatbot_stats": self.chatbot.get_stats()
        }


def demo_with_sample_documents():
    """
    Demo RAG chatbot with sample documents.
    
    This function creates sample documents in memory and demonstrates
    how to use the RAG chatbot without requiring external files.
    """
    print("\n" + "=" * 70)
    print("🤖 RAG-Enabled Chatbot Demo")
    print("=" * 70)
    
    # Create sample documents
    sample_docs = {
        "deployment.txt": """
# Deployment Guide

## Quick Start
To deploy the application:
1. Run `./deploy.sh`
2. Wait for the build to complete
3. Access the app at https://localhost:3000

## Requirements
- Docker 20.10+
- Node.js 18+
- PostgreSQL 13+

## Configuration
Set these environment variables:
- DATABASE_URL: PostgreSQL connection string
- API_KEY: Your API key
- LOG_LEVEL: debug, info, warn, error

## Troubleshooting
If deployment fails:
1. Check Docker is running
2. Verify DATABASE_URL is correct
3. Run `./deploy.sh --debug` for more info
""",
        "api_endpoints.txt": """
# API Endpoints

## Users API
GET /api/users - List all users
GET /api/users/{id} - Get user by ID
POST /api/users - Create new user
PUT /api/users/{id} - Update user
DELETE /api/users/{id} - Delete user

## Authentication
POST /api/auth/login - Login with email/password
POST /api/auth/refresh - Refresh access token
POST /api/auth/logout - Logout

## Rate Limiting
All endpoints are rate limited to 100 requests per minute per user.
Rate limit headers:
- X-RateLimit-Limit: 100
- X-RateLimit-Remaining: remaining requests
- X-RateLimit-Reset: reset timestamp
""",
        "database.txt": """
# Database Schema

## Users Table
- id (UUID, primary key)
- email (VARCHAR, unique)
- name (VARCHAR)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

## Sessions Table
- id (UUID, primary key)
- user_id (UUID, foreign key)
- token (VARCHAR)
- expires_at (TIMESTAMP)
- created_at (TIMESTAMP)

## Indexes
- users.email (unique)
- sessions.user_id
- sessions.token

## Migrations
Run migrations with: `./scripts/migrate.sh`
Rollback with: `./scripts/rollback.sh`
"""
    }
    
    # Create chatbot
    bot = RAGChatbot()
    print()
    
    # Load sample documents
    print("Loading sample documents...")
    bot.load_documents_from_strings(sample_docs)
    print()
    
    # List loaded documents
    bot.list_documents()
    
    # Ask sample questions
    sample_questions = [
        "How do I deploy the application?",
        "What are the API endpoints?",
        "What environment variables do I need?",
        "How do I list all users?",
        "What are the database tables?"
    ]
    
    print("\n" + "=" * 70)
    print("❓ SAMPLE QUESTIONS")
    print("=" * 70)
    
    for i, question in enumerate(sample_questions, 1):
        print(f"\nQ{i}: {question}")
        print("-" * 70)
        answer = bot.ask(question)
        print(answer)
        print()


def interactive_mode(document_dir: Optional[str] = None):
    """
    Run interactive RAG chat session.
    
    Args:
        document_dir: Optional directory with documents to load
    """
    print("\n" + "=" * 70)
    print("🤖 Interactive RAG Chatbot")
    print("=" * 70)
    print("Commands:")
    print("  'docs'  - List loaded documents")
    print("  'stats' - Show statistics")
    print("  'quit'  - Exit")
    print()
    
    # Create chatbot
    bot = RAGChatbot()
    print()
    
    # Load documents if directory provided
    if document_dir:
        print(f"Loading documents from {document_dir}...")
        num_docs = bot.load_documents_from_directory(document_dir)
        if num_docs == 0:
            print("⚠️  No documents loaded. Using demo documents...")
            demo_with_sample_documents()
            return
        print()
    else:
        print("Using demo documents...")
        sample_docs = {
            "deployment.txt": "To deploy, run: ./deploy.sh\nWait for the build to complete.\nAccess the app at https://localhost:3000",
            "api.txt": "API endpoints:\nGET /api/users - List users\nPOST /api/users - Create user"
        }
        bot.load_documents_from_strings(sample_docs)
        print()
    
    # Interactive loop
    while True:
        try:
            user_input = input("\n❓ Ask a question: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("Goodbye! 👋")
                break
            
            if user_input.lower() == 'docs':
                bot.list_documents()
                continue
            
            if user_input.lower() == 'stats':
                stats = bot.get_stats()
                print("\n📊 Statistics:")
                print(f"  Documents: {stats['documents_loaded']}")
                print(f"  Total chunks: {stats['total_chunks']}")
                print(f"  Total content: {stats['total_content_chars']} chars")
                continue
            
            # Ask the question
            print("\n🔍 Retrieving context and generating answer...\n")
            answer = bot.ask(user_input)
            print(answer)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break


def main():
    """
    Main entry point.
    
    Usage:
        python examples/rag_chat.py              # Demo mode
        python examples/rag_chat.py /path/to/docs  # Load from directory
        python examples/rag_chat.py --interactive   # Interactive mode
    """
    print()
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--demo":
            # Run demo with sample documents
            demo_with_sample_documents()
        
        elif arg == "--interactive":
            # Interactive mode without documents
            interactive_mode()
        
        else:
            # Treat as document directory
            if os.path.isdir(arg):
                interactive_mode(arg)
            else:
                print(f"❌ Directory not found: {arg}")
                print("\nUsage:")
                print("  python examples/rag_chat.py              # Demo mode")
                print("  python examples/rag_chat.py /path/to/docs  # Load from directory")
                print("  python examples/rag_chat.py --interactive   # Interactive mode")
    else:
        # Default: demo mode
        demo_with_sample_documents()
        
        # Then offer interactive session
        print("\n" + "=" * 70)
        response = input("Would you like to start an interactive session? (y/n): ").strip().lower()
        if response == 'y':
            interactive_mode()


if __name__ == "__main__":
    main()
