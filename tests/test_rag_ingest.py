# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_brain.rag import IngestResult, RAGPipeline
from agentic_brain.rag.store import Document, InMemoryDocumentStore


@pytest.fixture(scope="module")
def sample_docs_path() -> Path:
    return Path(__file__).parent / "fixtures" / "rag_ingest"


@pytest.mark.asyncio()
async def test_ingest_directory_counts_documents(sample_docs_path: Path):
    store = InMemoryDocumentStore(chunk_size=256, chunk_overlap=32)
    pipeline = RAGPipeline(document_store=store)

    result = await pipeline.ingest(str(sample_docs_path))

    assert isinstance(result, IngestResult)
    assert result.documents_processed == 3
    assert result.chunks_created > 0
    assert result.errors == []
    assert store.count() == 3


@pytest.mark.asyncio()
async def test_ingest_documents_adds_existing_documents():
    store = InMemoryDocumentStore(chunk_size=128, chunk_overlap=16)
    pipeline = RAGPipeline(document_store=store)

    docs = [
        Document(id="alpha", content="Alpha document body for ingestion."),
        Document(id="beta", content="Beta document with a second sentence."),
    ]

    result = await pipeline.ingest_documents(docs)

    assert result.documents_processed == 2
    assert result.chunks_created >= 2
    assert result.errors == []
    assert store.count() == 2
