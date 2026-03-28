# Office RAG Loaders

Unified RAG loaders that integrate office document processors with the agentic-brain RAG system.

## Overview

The office RAG loaders provide seamless integration between office document formats and the RAG (Retrieval-Augmented Generation) system. They support:

- **Microsoft Office**: Word (.docx), Excel (.xlsx), PowerPoint (.pptx)
- **Apple iWork**: Pages (.pages), Numbers (.numbers), Keynote (.keynote, .key)
- **OpenDocument**: ODT (.odt), ODS (.ods), ODP (.odp)

## Features

- ✅ **Unified Interface**: Single loader for all formats with automatic detection
- ✅ **Format-Specific Loaders**: Specialized loaders for each format type
- ✅ **Intelligent Chunking**: Multiple chunking strategies (semantic, markdown, recursive, fixed)
- ✅ **Rich Metadata**: Extract document metadata (title, author, dates, etc.)
- ✅ **Batch Processing**: Load entire directories recursively
- ✅ **RAG Integration**: Compatible with existing RAG DocumentStore
- ✅ **Structure Preservation**: Maintains document structure (headings, tables, slides)

## Installation

The loaders are part of the agentic-brain package. Ensure you have the required dependencies:

```bash
pip install python-docx openpyxl python-pptx
```

## Quick Start

### Load a Single Document

```python
from agentic_brain.documents.services.office import load_office_document

# Load any supported office document
doc = load_office_document("report.docx")

print(f"Loaded: {doc.filename}")
print(f"Content: {doc.content[:200]}...")
print(f"Metadata: {doc.metadata}")
```

### Load a Directory

```python
from agentic_brain.documents.services.office import load_office_directory

# Load all office documents from a directory
docs = load_office_directory("/documents", recursive=True)

print(f"Loaded {len(docs)} documents")
for doc in docs:
    print(f"  - {doc.filename}")
```

### Load and Chunk

```python
from agentic_brain.documents.services.office import load_and_chunk_office
from agentic_brain.rag.chunking import ChunkingStrategy

# Load document and split into chunks
chunks = load_and_chunk_office(
    "report.docx",
    chunk_size=512,
    overlap=50,
    strategy=ChunkingStrategy.SEMANTIC,
)

print(f"Created {len(chunks)} chunks")
```

## Using the Unified Loader

The `UnifiedOfficeLoader` automatically detects document format and uses the appropriate processor:

```python
from agentic_brain.documents.services.office import UnifiedOfficeLoader

loader = UnifiedOfficeLoader(base_path="/documents")

# Check if format is supported
if loader.supports_format("report.docx"):
    doc = loader.load_document("report.docx")

# Load all documents from folder
docs = loader.load_folder("reports/", recursive=True)

# Load specific documents
paths = ["report.docx", "data.xlsx", "presentation.pptx"]
docs = loader.load_multiple(paths)
```

## Format-Specific Loaders

Use format-specific loaders when you only need to work with one format:

### Word Documents

```python
from agentic_brain.documents.services.office import WordRAGLoader

loader = WordRAGLoader(base_path="/documents")
docs = loader.load_folder("reports/")
```

### Excel Spreadsheets

```python
from agentic_brain.documents.services.office import ExcelRAGLoader

loader = ExcelRAGLoader(
    base_path="/documents",
    max_worksheet_rows=1000,  # Limit rows per sheet
)
docs = loader.load_folder("data/")
```

### PowerPoint Presentations

```python
from agentic_brain.documents.services.office import PowerPointRAGLoader

loader = PowerPointRAGLoader(base_path="/documents")
docs = loader.load_folder("presentations/")
```

### Apple iWork Documents

```python
from agentic_brain.documents.services.office import (
    PagesRAGLoader,
    NumbersRAGLoader,
    KeynoteRAGLoader,
)

# Pages documents
pages_loader = PagesRAGLoader(base_path="/documents")
pages_docs = pages_loader.load_folder("reports/")

# Numbers spreadsheets
numbers_loader = NumbersRAGLoader(base_path="/documents")
numbers_docs = numbers_loader.load_folder("data/")

# Keynote presentations
keynote_loader = KeynoteRAGLoader(base_path="/documents")
keynote_docs = keynote_loader.load_folder("presentations/")
```

### OpenDocument Formats

```python
from agentic_brain.documents.services.office import OpenDocumentRAGLoader

loader = OpenDocumentRAGLoader(base_path="/documents")
docs = loader.load_folder("opendocs/")  # .odt, .ods, .odp
```

## RAG System Integration

Integrate loaded documents with the RAG DocumentStore:

```python
from agentic_brain.rag.store import InMemoryDocumentStore, Document
from agentic_brain.rag.chunking import ChunkingStrategy
from agentic_brain.documents.services.office import load_office_directory

# 1. Load office documents
loaded_docs = load_office_directory("/documents")

# 2. Create RAG store with auto-chunking
store = InMemoryDocumentStore(
    chunking_strategy=ChunkingStrategy.SEMANTIC,
    chunk_size=512,
    chunk_overlap=50,
)

# 3. Add documents to store
for loaded_doc in loaded_docs:
    doc = Document(
        id=loaded_doc.source_id,
        content=loaded_doc.content,
        metadata=loaded_doc.metadata,
    )
    store.add(doc)

# 4. Search the store
results = store.search("quarterly report", top_k=5)
for result in results:
    print(f"Found: {result.metadata['filename']}")
    print(f"Score: {result.score:.3f}")
```

## Chunking Strategies

The loaders support multiple chunking strategies from the RAG system:

### Semantic Chunking (Recommended)

Respects natural language boundaries (paragraphs, sentences):

```python
chunks = load_and_chunk_office(
    "document.docx",
    chunk_size=512,
    overlap=50,
    strategy=ChunkingStrategy.SEMANTIC,
)
```

### Markdown Chunking

Preserves markdown structure (headers, code blocks, lists):

```python
chunks = load_and_chunk_office(
    "document.docx",
    chunk_size=512,
    overlap=50,
    strategy=ChunkingStrategy.MARKDOWN,
)
```

### Recursive Chunking

Uses multiple separators for mixed content:

```python
chunks = load_and_chunk_office(
    "document.docx",
    chunk_size=512,
    overlap=50,
    strategy=ChunkingStrategy.RECURSIVE,
)
```

### Fixed Chunking

Simple fixed-size chunks with overlap:

```python
chunks = load_and_chunk_office(
    "document.docx",
    chunk_size=512,
    overlap=50,
    strategy=ChunkingStrategy.FIXED,
)
```

## Advanced Usage

### Custom Loader Configuration

```python
from agentic_brain.documents.services.office import UnifiedOfficeLoader

loader = UnifiedOfficeLoader(
    base_path="/documents",
    max_table_rows=100,        # Max rows per table
    max_worksheet_rows=1000,   # Max rows per worksheet
    include_images=False,      # Skip image descriptions
)

docs = loader.load_folder("reports/")
```

### Batch Processing with Progress

```python
from pathlib import Path
from agentic_brain.documents.services.office import UnifiedOfficeLoader

loader = UnifiedOfficeLoader(base_path="/documents")

# Find all office documents
document_paths = []
for ext in [".docx", ".xlsx", ".pptx", ".pages", ".numbers"]:
    document_paths.extend(Path("/documents").rglob(f"*{ext}"))

# Load with progress tracking
docs = []
for i, path in enumerate(document_paths, 1):
    print(f"Loading {i}/{len(document_paths)}: {path.name}")
    doc = loader.load_document(str(path))
    if doc:
        docs.append(doc)

print(f"Successfully loaded {len(docs)} documents")
```

### Chunking with Custom Metadata

```python
from agentic_brain.documents.services.office import UnifiedOfficeLoader
from agentic_brain.rag.chunking import create_chunker, ChunkingStrategy

loader = UnifiedOfficeLoader(base_path="/documents")
doc = loader.load_document("report.docx")

# Create custom chunker
chunker = create_chunker(
    strategy=ChunkingStrategy.SEMANTIC,
    chunk_size=512,
    overlap=50,
)

# Chunk with additional metadata
custom_metadata = {
    **doc.metadata,
    "department": "Engineering",
    "priority": "high",
}

chunks = chunker.chunk(doc.content, metadata=custom_metadata)

for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {chunk.content[:50]}...")
    print(f"Metadata: {chunk.metadata}")
```

## Document Structure

### LoadedDocument Format

Each loaded document returns a `LoadedDocument` with:

```python
@dataclass
class LoadedDocument:
    content: str                          # Extracted text content
    id: str                               # Document ID (auto-generated)
    metadata: dict[str, Any]              # Rich metadata
    source: str                           # Source type (e.g., "office")
    source_id: str                        # Original file path
    filename: str                         # Original filename
    mime_type: str                        # Content type
    created_at: Optional[datetime]        # Creation time
    modified_at: Optional[datetime]       # Modification time
    size_bytes: int                       # File size
```

### Metadata Fields

Standard metadata included for all documents:

```python
metadata = {
    "source_path": "/path/to/document.docx",
    "filename": "document.docx",
    "format": "docx",
    "file_extension": ".docx",
    "title": "Document Title",
    "author": "Author Name",
    "subject": "Document Subject",
    "keywords": "keyword1, keyword2",
    "created_at": "2024-01-01T00:00:00",
    "modified_at": "2024-01-02T00:00:00",
    "company": "Company Name",
    "paragraph_count": 50,
    "table_count": 3,
    "image_count": 5,
    "slide_count": 0,          # For presentations
    "worksheet_count": 0,      # For spreadsheets
}
```

## Content Formatting

The loaders format document content with structure preservation:

### Word Documents

```
# Heading 1

Body paragraph text...

## Heading 2

More content...

**Table:**
| Header 1 | Header 2 | Header 3 |
| --- | --- | --- |
| Cell 1 | Cell 2 | Cell 3 |
```

### PowerPoint/Keynote

```
## Slide 1: Title Slide

Main content paragraph...

**Table:**
| Data | Values |
| --- | --- |
| A | 1 |

**Speaker Notes:**
These are speaker notes...

## Slide 2: Next Slide
...
```

### Excel/Numbers

```
## Sheet: Sheet1

Row 1: Header1 | Header2 | Header3
Row 2: Data1 | Data2 | Data3
Row 3: Data4 | Data5 | Data6

*(Worksheet truncated - showing 1000 of 5000 rows)*
```

## Error Handling

The loaders handle errors gracefully:

```python
from agentic_brain.documents.services.office import UnifiedOfficeLoader

loader = UnifiedOfficeLoader(base_path="/documents")

# Returns None for missing files
doc = loader.load_document("nonexistent.docx")
if doc is None:
    print("Document not found")

# Skips unsupported formats
doc = loader.load_document("image.png")
if doc is None:
    print("Unsupported format")

# Logs errors for corrupted files
doc = loader.load_document("corrupted.docx")
if doc is None:
    print("Failed to load document")
```

## Performance Tips

1. **Use Format-Specific Loaders**: When processing only one format, use the specific loader for better performance.

2. **Limit Table/Worksheet Rows**: For large spreadsheets, limit the number of rows:
   ```python
   loader = ExcelRAGLoader(max_worksheet_rows=500)
   ```

3. **Skip Images**: Disable image processing if not needed:
   ```python
   loader = UnifiedOfficeLoader(include_images=False)
   ```

4. **Batch Processing**: Load multiple documents together:
   ```python
   docs = loader.load_multiple(paths)  # More efficient
   ```

5. **Chunking Strategy**: Choose the right strategy:
   - **SEMANTIC**: Best for natural language (slower)
   - **FIXED**: Fastest, uniform chunks
   - **MARKDOWN**: Good for structured documents
   - **RECURSIVE**: Balanced approach

## Troubleshooting

### Document Not Loading

Check if the document exists and format is supported:

```python
from pathlib import Path

path = Path("document.docx")
if not path.exists():
    print("File not found")
elif not loader.supports_format(path):
    print("Unsupported format")
```

### Empty Content

Some documents may have no extractable text. Check metadata:

```python
doc = loader.load_document("document.docx")
if doc and not doc.content.strip():
    print("Document has no text content")
    print(f"Tables: {doc.metadata.get('table_count', 0)}")
    print(f"Images: {doc.metadata.get('image_count', 0)}")
```

### Memory Issues with Large Files

For very large documents, use chunking:

```python
# Load and chunk large document
chunks = load_and_chunk_office(
    "large_document.xlsx",
    chunk_size=512,
    strategy=ChunkingStrategy.FIXED,  # Faster
)

# Process chunks individually
for chunk in chunks:
    # Process each chunk
    pass
```

## Examples

See `examples/office_rag_loader_demo.py` for complete working examples.

## API Reference

See the module docstrings for detailed API documentation:

```python
from agentic_brain.documents.services.office import rag_loaders
help(rag_loaders.UnifiedOfficeLoader)
```

## License

This module is part of agentic-brain and follows the same license.
