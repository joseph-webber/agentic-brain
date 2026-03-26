#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""Basic RAG (Retrieval Augmented Generation) example.

Demonstrates:
- Document ingestion and chunking
- Query processing with retrieval
- Streaming responses
- Statistics and management
"""

from agentic_brain.rag import RAGPipeline, InMemoryDocumentStore, ChunkingStrategy


def main():
    print("🧠 Agentic Brain - RAG Example")
    print("=" * 50)

    # Create document store with chunking config
    store = InMemoryDocumentStore(
        chunking_strategy=ChunkingStrategy.RECURSIVE, chunk_size=512, chunk_overlap=50
    )

    # Create RAG pipeline with store
    rag = RAGPipeline(document_store=store)

    # Sample documents
    docs = [
        {
            "content": """Agentic Brain is a production-ready AI framework.
            It provides RAG capabilities, multi-agent orchestration, and enterprise features.
            The framework supports multiple LLM providers including Ollama and OpenAI.""",
            "metadata": {"title": "About Agentic Brain", "type": "overview"},
        },
        {
            "content": """RAG (Retrieval Augmented Generation) combines retrieval with generation.
            Documents are chunked, embedded, and stored in a vector database.
            Queries retrieve relevant chunks which provide context for the LLM.""",
            "metadata": {"title": "RAG Explained", "type": "technical"},
        },
        {
            "content": """The chunking strategies available are:
            1. Fixed - splits at fixed character intervals
            2. Semantic - splits at sentence boundaries
            3. Recursive - uses multiple separators (paragraphs, sentences, words)
            4. Markdown - preserves markdown structure""",
            "metadata": {"title": "Chunking Strategies", "type": "reference"},
        },
    ]

    # Add documents
    print("\n📄 Adding documents...")
    for doc in docs:
        result = rag.add_document(doc["content"], doc["metadata"])
        print(f"  ✅ Added: {doc['metadata']['title']} ({len(result.chunks)} chunks)")

    # Show stats
    stats = rag.get_stats()
    print(f"\n📊 Stats: {stats['document_count']} docs, {stats['total_chunks']} chunks")

    # Interactive query loop
    print("\n" + "=" * 50)
    print("💬 Ask questions (type 'quit' to exit, 'list' for docs, 'stats' for stats)")
    print("=" * 50)

    while True:
        try:
            query = input("\n❓ Your question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query:
            continue

        if query.lower() == "quit":
            break

        if query.lower() == "list":
            docs = rag.list_documents()
            print(f"\n📚 Documents ({len(docs)}):")
            for doc in docs:
                print(f"  - {doc.id}: {doc.metadata.get('title', 'Untitled')}")
            continue

        if query.lower() == "stats":
            stats = rag.get_stats()
            print(f"\n📊 Pipeline Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            continue

        # Query with streaming
        print("\n🤖 Response: ", end="", flush=True)
        for token in rag.query_stream(query):
            print(token, end="", flush=True)
        print()  # newline after streaming


if __name__ == "__main__":
    main()
