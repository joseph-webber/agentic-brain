# Document Loaders

Comprehensive document loader system for the Agentic Brain platform. Supports multiple file formats with extensible architecture.

## Overview

The document loader system provides a unified interface for loading documents from various file formats into a standardized `Document` format. This enables seamless integration of diverse data sources into the AI brain's knowledge base.

### Key Features

- **Multiple Format Support**: PDF, DOCX, HTML, Markdown, CSV, JSON, JSONL, and plain text
- **Async/Sync Operations**: Both async and synchronous loading APIs
- **Flexible Splitting**: Load entire files or split by logical units (PDF pages, Markdown headings, CSV rows, etc.)
- **Metadata Extraction**: Automatic extraction of document metadata
- **Batch Loading**: Directory traversal with glob pattern support
- **Extensible**: Easy to add custom loaders for new formats
- **Error Handling**: Comprehensive error handling and logging

## Installation

The loaders require additional dependencies for different formats:

```bash
# For all document formats
pip install -e ".[documents,pdf-full]"

# Or install specific format dependencies
pip install beautifulsoup4 markdown  # For HTML and Markdown
pip install pypdf                    # For PDFs
pip install python-docx              # For Word documents
```

## Core Classes

### Document

Represents a loaded document with content and metadata.

```python
from agentic_brain.loaders import Document

doc = Document(
    content="Document text content",
    source="path/to/file.pdf",
    metadata={"page": 1, "title": "Example"}
)
```

**Attributes:**
- `content: str` - The document text content
- `source: Optional[str]` - Source file path or identifier
- `metadata: dict[str, Any]` - Document metadata
- `loaded_at: datetime` - Timestamp when document was loaded

**Methods:**
- `to_dict() -> dict[str, Any]` - Convert to dictionary representation

### DocumentLoader (ABC)

Abstract base class for all loaders.

```python
from agentic_brain.loaders import DocumentLoader

class CustomLoader(DocumentLoader):
    async def load(self, source: str | Path) -> list[Document]:
        """Load and return documents."""
        pass

    def supported_extensions(self) -> list[str]:
        """Return list of supported extensions."""
        return [".custom"]
```

**Methods:**
- `async load(source) -> list[Document]` - Load documents from source
- `supported_extensions() -> list[str]` - Return supported file extensions
- `can_load(source) -> bool` - Check if loader can load source

## Format-Specific Loaders

### Text Files

```python
from agentic_brain.loaders import TextLoader

loader = TextLoader()
documents = await loader.load("file.txt")
# or sync
documents = loader.load_sync("file.txt")
```

**Supported Extensions:** `.txt`, `.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`

### Markdown

Two strategies for Markdown files:

#### MarkdownLoader - Load entire file

```python
from agentic_brain.loaders import MarkdownLoader

loader = MarkdownLoader()
documents = await loader.load("readme.md")
# Returns one document with entire content
# Extracts: title, links, code block count
```

#### MarkdownHeadingLoader - Split by headings

```python
from agentic_brain.loaders import MarkdownHeadingLoader

loader = MarkdownHeadingLoader()
documents = await loader.load("readme.md")
# Returns separate document for each heading
# Metadata includes: heading, heading_level
```

### HTML

```python
from agentic_brain.loaders import HTMLLoader

loader = HTMLLoader(
    extract_links=True,        # Include URLs in metadata
    extract_metadata=True      # Extract title, description
)
documents = await loader.load("page.html")
# Automatically removes scripts and styles
# Extracts: title, description, links
```

### PDF

Two strategies for PDFs:

#### PDFLoader - Load entire file

```python
from agentic_brain.loaders import PDFLoader

loader = PDFLoader(extract_metadata=True)
documents = await loader.load("document.pdf")
# Returns one document with all pages concatenated
# Metadata includes: num_pages, title, author, subject
```

#### PDFPageLoader - One document per page

```python
from agentic_brain.loaders import PDFPageLoader

loader = PDFPageLoader()
documents = await loader.load("document.pdf")
# Returns separate document for each page
# Metadata includes: page number, total pages
```

### Word Documents (DOCX)

```python
from agentic_brain.loaders import DocxLoader

loader = DocxLoader()
documents = await loader.load("document.docx")
# Extracts paragraphs and tables
# Metadata includes: title, author, subject
```

### CSV

Two strategies for CSV files:

#### CSVLoader - Load entire file

```python
from agentic_brain.loaders import CSVLoader

loader = CSVLoader()
documents = await loader.load("data.csv")
# Returns one document with formatted table
# Metadata includes: row_count, column_count
```

#### CSVRowLoader - One document per row

```python
from agentic_brain.loaders import CSVRowLoader

loader = CSVRowLoader()
documents = await loader.load("data.csv")
# Returns separate document for each row
# Metadata includes: row_number, total_rows
```

### JSON

#### JSONLoader - Load entire file with optional filtering

```python
from agentic_brain.loaders import JSONLoader

# Load entire file
loader = JSONLoader()
documents = await loader.load("data.json")

# Load specific nested data using dot notation
loader = JSONLoader(jq_filter="data.items")
documents = await loader.load("data.json")
```

#### JSONLinesLoader - Load JSONL file as single document

```python
from agentic_brain.loaders import JSONLinesLoader

loader = JSONLinesLoader()
documents = await loader.load("data.jsonl")
# Metadata includes: line_count
```

#### JSONLinesRowLoader - One document per line

```python
from agentic_brain.loaders import JSONLinesRowLoader

loader = JSONLinesRowLoader()
documents = await loader.load("data.jsonl")
# Returns separate document for each line
# Metadata includes: line_number
```

## Batch Loading

### DirectoryLoader

Load all documents from a directory with automatic format detection:

```python
from agentic_brain.loaders import DirectoryLoader

loader = DirectoryLoader(
    glob_pattern="**/*.pdf",     # Glob pattern for files
    recursive=True,              # Search subdirectories
    max_workers=4                # Concurrent loaders
)

# Async loading
documents = await loader.load("/path/to/docs")

# Sync loading
documents = loader.load_sync("/path/to/docs")
```

**Features:**
- Automatic format detection by file extension
- Parallel loading with configurable worker count
- Recursive directory traversal
- Error handling per file

### Custom Loader Registration

```python
from agentic_brain.loaders import DirectoryLoader

loader = DirectoryLoader()

# Add custom loader
loader.add_loader(".custom", CustomDocumentLoader())

documents = await loader.load("/path/to/mixed/formats")
```

## Usage Examples

### Load and Process Documents

```python
from agentic_brain.loaders import PDFPageLoader

loader = PDFPageLoader()
documents = await loader.load("report.pdf")

for doc in documents:
    print(f"Page {doc.metadata['page']}: {len(doc.content)} chars")
    # Process each page separately for RAG
```

### Split Large Files

```python
from agentic_brain.loaders import MarkdownHeadingLoader, CSVRowLoader

# Split Markdown by sections
md_loader = MarkdownHeadingLoader()
sections = await md_loader.load("large_document.md")

# Split CSV by rows for processing
csv_loader = CSVRowLoader()
rows = await csv_loader.load("data.csv")

# Each document can be embedded and stored separately
```

### Mixed Format Directory

```python
from agentic_brain.loaders import DirectoryLoader

loader = DirectoryLoader(glob_pattern="**/*")
documents = await loader.load("/path/to/knowledge/base")

# documents now contains PDFs, Word docs, Markdown, CSVs, etc.
# All in standardized Document format with metadata
```

### Extract Nested JSON

```python
from agentic_brain.loaders import JSONLoader

loader = JSONLoader(jq_filter="results.data.items")
documents = await loader.load("api_response.json")

# Only loads the specified nested data
```

## Metadata

Each loaded document includes automatically extracted metadata:

### Common Metadata
- `filename` - Original filename
- `source` - Full source path
- `size` - File size in bytes
- `loaded_at` - Timestamp

### Format-Specific Metadata

**PDF:**
- `num_pages` - Total pages
- `page` - Current page (PDFPageLoader only)
- `title` - PDF title
- `author` - PDF author

**Markdown:**
- `title` - First heading
- `heading` - Section heading (MarkdownHeadingLoader)
- `heading_level` - Heading level 1-6
- `links` - List of links in document
- `code_block_count` - Number of code blocks

**HTML:**
- `title` - Page title
- `description` - Meta description
- `links` - List of links

**CSV:**
- `row_count` - Number of data rows
- `column_count` - Number of columns
- `row_number` - Current row (CSVRowLoader)

**DOCX:**
- `title` - Document title
- `author` - Document author
- `subject` - Document subject

**JSON:**
- `jq_filter` - Applied filter (if any)

## Error Handling

Loaders handle errors gracefully:

```python
from agentic_brain.loaders import PDFLoader

loader = PDFLoader()

try:
    documents = await loader.load("missing.pdf")
except FileNotFoundError:
    print("File not found")
except ValueError as e:
    print(f"Error parsing file: {e}")
```

**Common Exceptions:**
- `FileNotFoundError` - Source file doesn't exist
- `ValueError` - Failed to parse file format
- `ImportError` - Required library not installed

## Performance Considerations

### Async Loading

Use async for better performance with multiple files:

```python
import asyncio
from agentic_brain.loaders import DirectoryLoader

loader = DirectoryLoader(max_workers=8)
documents = await loader.load("/large/doc/directory")
```

### Streaming Large Files

For very large files, consider splitting:

```python
from agentic_brain.loaders import PDFPageLoader

loader = PDFPageLoader()
for doc in await loader.load("large.pdf"):
    # Process one page at a time
    process_document(doc)
```

### Caching

Consider caching loaded documents:

```python
from pathlib import Path
from agentic_brain.loaders import DirectoryLoader

loader = DirectoryLoader()
cache_path = Path("cache.pkl")

if cache_path.exists():
    import pickle
    documents = pickle.load(open(cache_path, "rb"))
else:
    documents = await loader.load("/docs")
    pickle.dump(documents, open(cache_path, "wb"))
```

## Extending with Custom Loaders

Create custom loaders for proprietary formats:

```python
from agentic_brain.loaders import DocumentLoader, Document
from pathlib import Path

class CustomFormatLoader(DocumentLoader):
    async def load(self, source: str | Path) -> list[Document]:
        path = Path(source)
        
        # Your custom parsing logic
        content = parse_custom_format(path)
        
        return [
            Document(
                content=content,
                source=str(path),
                metadata={"format": "custom", "processed": True}
            )
        ]
    
    def supported_extensions(self) -> list[str]:
        return [".custom"]

# Use in DirectoryLoader
loader = DirectoryLoader()
loader.add_loader(".custom", CustomFormatLoader())
documents = await loader.load("/docs")
```

## Testing

Run the comprehensive test suite:

```bash
# All loader tests
pytest tests/loaders/ -v

# Specific loader tests
pytest tests/loaders/test_loaders.py::TestPDFLoader -v

# With coverage
pytest tests/loaders/ --cov=agentic_brain.loaders --cov-report=html
```

## Architecture

```
loaders/
├── base.py          # Abstract base classes and Document model
├── pdf.py           # PDF loading (PDFLoader, PDFPageLoader)
├── docx.py          # Word document loading
├── html.py          # HTML parsing
├── markdown.py      # Markdown loading with heading split
├── csv.py           # CSV loading with row split
├── json.py          # JSON, JSONL loading with filters
├── directory.py     # Batch loading with format detection
└── __init__.py      # Public API exports
```

## Best Practices

1. **Choose the Right Loader**: Use page/row loaders for better RAG performance
2. **Metadata Extraction**: Always check metadata for document context
3. **Error Handling**: Implement try-catch for batch operations
4. **Async First**: Use async for production workloads
5. **Custom Loaders**: Create loaders for domain-specific formats
6. **Caching**: Cache loaded documents for frequently accessed data
7. **Logging**: Enable debug logging to track document loading

## Contributing

To add support for new formats:

1. Create new loader in `src/agentic_brain/loaders/format_name.py`
2. Inherit from `DocumentLoader` or `SyncDocumentLoader`
3. Implement `load()` and `supported_extensions()`
4. Add tests in `tests/loaders/test_loaders.py`
5. Update documentation
6. Submit PR

## License

Apache 2.0 - See LICENSE file
