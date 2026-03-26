#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
#
# This file is part of Agentic Brain.
"""
Example: Cloud Document Loaders

This example demonstrates how to use the cloud document loaders
to load documents from Google Drive, Gmail, and iCloud for RAG pipelines.

Prerequisites:
- Google Drive/Gmail: OAuth2 credentials from Google Cloud Console
- iCloud: Apple ID and app-specific password (recommended)

Setup:
1. Google API setup:
   - Create a project at https://console.cloud.google.com
   - Enable Google Drive API and Gmail API
   - Create OAuth2 credentials (Desktop app)
   - Download as 'client_secrets.json'

2. iCloud setup:
   - Generate an app-specific password at https://appleid.apple.com
   - Set ICLOUD_APPLE_ID and ICLOUD_PASSWORD env vars (or pass directly)

Run:
    python3 examples/06_cloud_loaders.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentic_brain.rag import (
    # Core loaders
    GoogleDriveLoader,
    GmailLoader,
    iCloudLoader,
    # Factory functions
    create_loader,
    load_from_multiple_sources,
    # Data class
    LoadedDocument,
    # Availability flags
    GOOGLE_API_AVAILABLE,
    PYICLOUD_AVAILABLE,
)


def example_google_drive():
    """Example: Loading documents from Google Drive."""
    print("\n" + "=" * 60)
    print("GOOGLE DRIVE LOADER")
    print("=" * 60)

    if not GOOGLE_API_AVAILABLE:
        print("❌ Google API libraries not installed.")
        print(
            "   Install with: pip install google-auth google-auth-oauthlib google-api-python-client"
        )
        return

    # Check for credentials
    credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "client_secrets.json")
    if not os.path.exists(credentials_path):
        print(f"⚠️  Credentials file not found: {credentials_path}")
        print("   Create OAuth2 credentials in Google Cloud Console")
        print("   and download as 'client_secrets.json'")
        return

    try:
        # Initialize loader
        loader = GoogleDriveLoader(
            credentials_path=credentials_path,
            token_path="gdrive_token.json",
            max_file_size_mb=50,
        )

        # Authenticate (will open browser on first use)
        print("\n📁 Authenticating with Google Drive...")
        if not loader.authenticate():
            print("❌ Authentication failed")
            return

        print("✅ Authentication successful!")

        # List root folders
        print("\n📂 Root folders:")
        folders = loader.list_folders()
        for folder in folders[:5]:  # Show first 5
            print(f"   - {folder['name']}")

        # Load a folder
        folder_name = input(
            "\nEnter folder name to load (or press Enter to skip): "
        ).strip()
        if folder_name:
            print(f"\n📄 Loading documents from '{folder_name}'...")
            docs = loader.load_folder(folder_name, recursive=True)

            print(f"   Found {len(docs)} documents:")
            for doc in docs[:5]:  # Show first 5
                print(f"   - {doc.filename} ({doc.mime_type}, {doc.size_bytes} bytes)")
                if doc.content:
                    preview = doc.content[:100].replace("\n", " ")
                    print(f"     Preview: {preview}...")

        # Search
        query = input("\nEnter search query (or press Enter to skip): ").strip()
        if query:
            print(f"\n🔍 Searching for '{query}'...")
            results = loader.search(query, max_results=5)

            print(f"   Found {len(results)} results:")
            for doc in results:
                print(f"   - {doc.filename}")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_gmail():
    """Example: Loading emails from Gmail."""
    print("\n" + "=" * 60)
    print("GMAIL LOADER")
    print("=" * 60)

    if not GOOGLE_API_AVAILABLE:
        print("❌ Google API libraries not installed.")
        print(
            "   Install with: pip install google-auth google-auth-oauthlib google-api-python-client"
        )
        return

    credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "client_secrets.json")
    if not os.path.exists(credentials_path):
        print(f"⚠️  Credentials file not found: {credentials_path}")
        return

    try:
        # Initialize loader
        loader = GmailLoader(
            credentials_path=credentials_path,
            token_path="gmail_token.json",
            include_attachments=True,
            max_attachment_size_mb=10,
        )

        # Authenticate
        print("\n📧 Authenticating with Gmail...")
        if not loader.authenticate():
            print("❌ Authentication failed")
            return

        print("✅ Authentication successful!")

        # List labels
        print("\n🏷️  Labels:")
        labels = loader.list_labels()
        for label in labels[:10]:  # Show first 10
            print(f"   - {label['name']}")

        # Load recent emails
        print("\n📨 Loading recent emails (last 7 days)...")
        emails = loader.load_recent(days=7, max_results=5)

        print(f"   Found {len(emails)} emails:")
        for email in emails:
            subject = email.metadata.get("subject", "No Subject")
            from_addr = email.metadata.get("from", "Unknown")
            print(f"   - {subject}")
            print(f"     From: {from_addr}")

        # Search
        query = input("\nEnter Gmail search query (or press Enter to skip): ").strip()
        if query:
            print(f"\n🔍 Searching for '{query}'...")
            results = loader.search(query, max_results=5)

            print(f"   Found {len(results)} results:")
            for email in results:
                subject = email.metadata.get("subject", "No Subject")
                print(f"   - {subject}")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_icloud():
    """Example: Loading documents from iCloud Drive."""
    print("\n" + "=" * 60)
    print("ICLOUD LOADER")
    print("=" * 60)

    if not PYICLOUD_AVAILABLE:
        print("❌ pyicloud library not installed.")
        print("   Install with: pip install pyicloud")
        return

    # Get credentials
    apple_id = os.environ.get("ICLOUD_APPLE_ID")
    password = os.environ.get("ICLOUD_PASSWORD")

    if not apple_id:
        apple_id = input("Enter Apple ID (or press Enter to skip): ").strip()
        if not apple_id:
            print("⏭️  Skipping iCloud example")
            return

    if not password:
        import getpass

        password = getpass.getpass("Enter password (app-specific recommended): ")

    try:
        # Initialize loader
        loader = iCloudLoader(
            apple_id=apple_id,
            password=password,
            cookie_directory=".icloud",
            max_file_size_mb=50,
        )

        # Authenticate (may require 2FA)
        print("\n☁️  Authenticating with iCloud...")
        if not loader.authenticate():
            print("❌ Authentication failed")
            return

        print("✅ Authentication successful!")

        # List root folders
        print("\n📂 Root folders:")
        folders = loader.list_folders()
        for folder in folders[:5]:
            print(f"   - {folder['name']}")

        # Load a folder
        folder_path = input(
            "\nEnter folder path to load (or press Enter to skip): "
        ).strip()
        if folder_path:
            print(f"\n📄 Loading documents from '{folder_path}'...")
            docs = loader.load_folder(folder_path, recursive=True)

            print(f"   Found {len(docs)} documents:")
            for doc in docs[:5]:
                print(f"   - {doc.filename} ({doc.size_bytes} bytes)")

        # Search
        query = input("\nEnter search query (or press Enter to skip): ").strip()
        if query:
            print(f"\n🔍 Searching for '{query}'...")
            results = loader.search(query, max_results=5)

            print(f"   Found {len(results)} results:")
            for doc in results:
                print(f"   - {doc.filename}")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_factory():
    """Example: Using the factory function."""
    print("\n" + "=" * 60)
    print("FACTORY FUNCTION")
    print("=" * 60)

    print(
        """
The create_loader() factory function makes it easy to create
loaders by name:

    from agentic_brain.rag import create_loader
    
    # Create Google Drive loader
    drive = create_loader('google_drive', credentials_path='creds.json')
    
    # Create Gmail loader
    gmail = create_loader('gmail', credentials_path='creds.json')
    
    # Create iCloud loader
    icloud = create_loader('icloud', apple_id='me@icloud.com', password='xxx')
    
    # Aliases work too
    drive = create_loader('drive', ...)
    email = create_loader('email', ...)
    icloud = create_loader('icloud_drive', ...)
"""
    )


def example_multiple_sources():
    """Example: Loading from multiple sources."""
    print("\n" + "=" * 60)
    print("LOADING FROM MULTIPLE SOURCES")
    print("=" * 60)

    print(
        """
The load_from_multiple_sources() function loads documents from
multiple cloud sources in one call:

    from agentic_brain.rag import load_from_multiple_sources
    
    sources = [
        {
            'type': 'google_drive',
            'credentials_path': 'creds.json',
            'folder': 'Work/Projects'
        },
        {
            'type': 'gmail',
            'credentials_path': 'creds.json',
            'query': 'from:boss@company.com has:attachment'
        },
        {
            'type': 'icloud',
            'apple_id': 'me@icloud.com',
            'password': 'app-password',
            'folder': 'Documents/Reports'
        },
    ]
    
    # Load all documents (with deduplication)
    all_docs = load_from_multiple_sources(sources, deduplicate=True)
    
    print(f"Loaded {len(all_docs)} unique documents")
    
    for doc in all_docs:
        print(f"- {doc.source}: {doc.filename}")
"""
    )


def example_rag_integration():
    """Example: Integrating with RAG pipeline."""
    print("\n" + "=" * 60)
    print("RAG PIPELINE INTEGRATION")
    print("=" * 60)

    print(
        """
Cloud loaders can be integrated with the RAG pipeline to
build knowledge bases from cloud documents:

    from agentic_brain.rag import (
        RAGPipeline,
        GoogleDriveLoader,
        create_chunker,
        ChunkingStrategy,
    )
    
    # Load documents from Google Drive
    loader = GoogleDriveLoader(credentials_path='creds.json')
    docs = loader.load_folder('Knowledge Base')
    
    # Create chunker
    chunker = create_chunker(ChunkingStrategy.RECURSIVE)
    
    # Process documents into chunks
    all_chunks = []
    for doc in docs:
        chunks = chunker.chunk(doc.content)
        for chunk in chunks:
            chunk.metadata.update({
                'source': doc.source,
                'filename': doc.filename,
                'source_id': doc.source_id,
            })
        all_chunks.extend(chunks)
    
    # Index chunks in RAG pipeline
    rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
    
    # Now you can query across all cloud documents!
    result = rag.query("What are the project deadlines?")
    print(result.answer)
"""
    )


def example_loaded_document():
    """Example: Working with LoadedDocument."""
    print("\n" + "=" * 60)
    print("LOADED DOCUMENT DATACLASS")
    print("=" * 60)

    from datetime import datetime, timezone

    # Create a document
    doc = LoadedDocument(
        content="This is the document content...",
        metadata={"author": "John Doe", "department": "Engineering"},
        source="google_drive",
        source_id="abc123xyz",
        filename="report.pdf",
        mime_type="application/pdf",
        created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        modified_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
        size_bytes=15000,
    )

    print("Created LoadedDocument:")
    print(f"  Filename: {doc.filename}")
    print(f"  Source: {doc.source}")
    print(f"  MIME Type: {doc.mime_type}")
    print(f"  Size: {doc.size_bytes} bytes")
    print(f"  Created: {doc.created_at}")
    print(f"  Content preview: {doc.content[:50]}...")

    # Serialize to dict
    print("\nSerialized to dict:")
    data = doc.to_dict()
    print(f"  Keys: {list(data.keys())}")

    # Restore from dict
    restored = LoadedDocument.from_dict(data)
    print(f"\nRestored from dict:")
    print(f"  Filename: {restored.filename}")
    print(f"  Content matches: {restored.content == doc.content}")


def main():
    """Run all examples."""
    print("=" * 60)
    print("CLOUD DOCUMENT LOADERS - EXAMPLES")
    print("=" * 60)

    print(
        """
This example demonstrates the cloud document loaders for RAG.

Available loaders:
- GoogleDriveLoader: Load from Google Drive
- GmailLoader: Load from Gmail
- iCloudLoader: Load from iCloud Drive

What would you like to try?
1. Google Drive
2. Gmail
3. iCloud
4. Factory function (documentation)
5. Multiple sources (documentation)
6. RAG integration (documentation)
7. LoadedDocument dataclass
8. Run all interactive examples
9. Exit
"""
    )

    while True:
        choice = input("\nEnter choice (1-9): ").strip()

        if choice == "1":
            example_google_drive()
        elif choice == "2":
            example_gmail()
        elif choice == "3":
            example_icloud()
        elif choice == "4":
            example_factory()
        elif choice == "5":
            example_multiple_sources()
        elif choice == "6":
            example_rag_integration()
        elif choice == "7":
            example_loaded_document()
        elif choice == "8":
            example_google_drive()
            example_gmail()
            example_icloud()
        elif choice == "9":
            print("\n👋 Goodbye!")
            break
        else:
            print("Invalid choice. Enter 1-9.")


if __name__ == "__main__":
    main()
