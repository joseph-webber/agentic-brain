# 📦 Data Loaders Reference

> **54 data loaders** to ingest ANY data source into your knowledge graph.

Agentic Brain provides production-ready data loaders for documents, code, media, web, databases, cloud storage, and enterprise systems. Every loader outputs standardized `Document` objects ready for chunking, embedding, and GraphRAG indexing.

---

## Quick Start

```python
from agentic_brain.rag.loaders import PDFLoader, NotionLoader, S3Loader

# Load a PDF
docs = await PDFLoader().load("./report.pdf")

# Load from Notion
notion = NotionLoader(api_key="secret_xxx")
docs = await notion.load_database("knowledge-base")

# Load from S3
s3 = S3Loader(bucket="my-data", prefix="documents/")
docs = await s3.load_all()

# Ingest into GraphRAG
from agentic_brain.rag import RAGPipeline
rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
await rag.ingest_documents(docs)
```

---

## 📑 Document Loaders (11)

File-based loaders for common document formats.

| # | Loader | Extensions | Features |
|---|--------|------------|----------|
| 1 | **PDFLoader** | `.pdf` | OCR fallback, table extraction, page metadata |
| 2 | **DOCXLoader** | `.docx`, `.doc` | Styles, headers/footers, track changes |
| 3 | **PPTXLoader** | `.pptx`, `.ppt` | Slide notes, speaker notes, embedded media |
| 4 | **XLSXLoader** | `.xlsx`, `.xls`, `.csv` | Sheet selection, formula evaluation, pivot tables |
| 5 | **TXTLoader** | `.txt` | Encoding detection, line splitting |
| 6 | **MarkdownLoader** | `.md`, `.mdx` | Frontmatter parsing, code block extraction |
| 7 | **HTMLLoader** | `.html`, `.htm` | Tag stripping, link extraction, table parsing |
| 8 | **XMLLoader** | `.xml` | XPath queries, namespace handling |
| 9 | **JSONLoader** | `.json`, `.jsonl` | JSONPath queries, nested extraction |
| 10 | **YAMLLoader** | `.yaml`, `.yml` | Multi-document, anchor resolution |
| 11 | **CSVLoader** | `.csv`, `.tsv` | Column selection, type inference |

### Usage Examples

```python
from agentic_brain.rag.loaders import (
    PDFLoader, DOCXLoader, PPTXLoader, XLSXLoader,
    TXTLoader, MarkdownLoader, HTMLLoader, XMLLoader,
    JSONLoader, YAMLLoader, CSVLoader
)

# PDF with OCR for scanned documents
pdf = PDFLoader(ocr_enabled=True, extract_tables=True)
docs = await pdf.load("./scanned-contract.pdf")
print(f"Extracted {len(docs)} pages with {sum(d.metadata.get('tables', 0) for d in docs)} tables")

# Excel with specific sheets
xlsx = XLSXLoader(sheets=["Q1 Sales", "Q2 Sales"])
docs = await xlsx.load("./quarterly-report.xlsx")

# JSON with JSONPath extraction
json_loader = JSONLoader(jq_filter=".results[].content")
docs = await json_loader.load("./api-response.json")

# Markdown with frontmatter
md = MarkdownLoader(parse_frontmatter=True)
docs = await md.load("./blog-post.md")
print(f"Title: {docs[0].metadata['title']}")
```

---

## 💻 Code Loaders (12)

Language-aware loaders that preserve structure, extract docstrings, and understand imports.

| # | Loader | Languages | Features |
|---|--------|-----------|----------|
| 12 | **PythonLoader** | `.py`, `.pyi` | AST parsing, docstrings, type hints, imports |
| 13 | **JavaScriptLoader** | `.js`, `.jsx`, `.mjs` | ES modules, JSDoc, React components |
| 14 | **TypeScriptLoader** | `.ts`, `.tsx` | Type definitions, interfaces, decorators |
| 15 | **JavaLoader** | `.java` | Classes, methods, Javadoc, annotations |
| 16 | **GoLoader** | `.go` | Packages, interfaces, godoc comments |
| 17 | **RustLoader** | `.rs` | Modules, traits, doc comments, macros |
| 18 | **CppLoader** | `.cpp`, `.hpp`, `.c`, `.h` | Classes, templates, Doxygen |
| 19 | **CSharpLoader** | `.cs` | Namespaces, LINQ, XML docs |
| 20 | **SwiftLoader** | `.swift` | Protocols, extensions, SwiftDoc |
| 21 | **KotlinLoader** | `.kt`, `.kts` | Data classes, coroutines, KDoc |
| 22 | **RubyLoader** | `.rb` | Classes, modules, YARD docs |
| 23 | **PHPLoader** | `.php` | Classes, namespaces, PHPDoc |

### Usage Examples

```python
from agentic_brain.rag.loaders import (
    PythonLoader, TypeScriptLoader, JavaLoader, RustLoader
)

# Python with full AST analysis
py = PythonLoader(
    extract_docstrings=True,
    extract_imports=True,
    extract_classes=True,
    extract_functions=True
)
docs = await py.load_directory("./src/")

# Each doc includes rich metadata
for doc in docs:
    print(f"File: {doc.metadata['file_path']}")
    print(f"Classes: {doc.metadata.get('classes', [])}")
    print(f"Functions: {doc.metadata.get('functions', [])}")
    print(f"Imports: {doc.metadata.get('imports', [])}")

# TypeScript with React component detection
ts = TypeScriptLoader(detect_react=True)
docs = await ts.load_directory("./components/")

# Java with Javadoc extraction
java = JavaLoader(extract_javadoc=True)
docs = await java.load_directory("./src/main/java/")
```

---

## 🖼️ Media Loaders (3)

Process images, audio, and video with AI-powered extraction.

| # | Loader | Formats | Features |
|---|--------|---------|----------|
| 24 | **ImageLoader** | `.png`, `.jpg`, `.gif`, `.webp`, `.svg` | OCR, EXIF, alt-text generation, object detection |
| 25 | **AudioLoader** | `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg` | Whisper transcription, speaker diarization |
| 26 | **VideoLoader** | `.mp4`, `.mov`, `.avi`, `.webm`, `.mkv` | Frame extraction, audio transcription, scene detection |

### Usage Examples

```python
from agentic_brain.rag.loaders import ImageLoader, AudioLoader, VideoLoader

# Image with OCR and description
img = ImageLoader(
    ocr_enabled=True,
    generate_description=True,  # Uses vision LLM
    extract_exif=True
)
docs = await img.load("./whiteboard-photo.jpg")
print(f"OCR Text: {docs[0].content}")
print(f"Description: {docs[0].metadata['description']}")
print(f"Taken: {docs[0].metadata['exif']['DateTimeOriginal']}")

# Audio transcription with Whisper
audio = AudioLoader(
    model="whisper-large-v3",
    language="en",
    diarize=True  # Identify speakers
)
docs = await audio.load("./meeting-recording.mp3")
print(f"Transcript: {docs[0].content}")
print(f"Speakers: {docs[0].metadata['speakers']}")

# Video with full analysis
video = VideoLoader(
    transcribe=True,
    extract_frames=True,
    frame_interval=30,  # Every 30 seconds
    detect_scenes=True
)
docs = await video.load("./tutorial.mp4")
```

---

## 🌐 Web Loaders (4)

Crawl and parse web content with intelligent extraction.

| # | Loader | Source | Features |
|---|--------|--------|----------|
| 27 | **URLLoader** | Single URLs | JavaScript rendering, readability extraction |
| 28 | **SitemapLoader** | XML sitemaps | Concurrent crawling, priority filtering |
| 29 | **RSSLoader** | RSS/Atom feeds | Full article extraction, date parsing |
| 30 | **APILoader** | REST APIs | Pagination, auth, rate limiting |

### Usage Examples

```python
from agentic_brain.rag.loaders import URLLoader, SitemapLoader, RSSLoader, APILoader

# Single page with JS rendering
url = URLLoader(render_js=True, extract_links=True)
docs = await url.load("https://docs.example.com/guide")

# Full site via sitemap
sitemap = SitemapLoader(
    max_pages=1000,
    concurrent=10,
    filter_pattern=r"/docs/.*"
)
docs = await sitemap.load("https://example.com/sitemap.xml")
print(f"Loaded {len(docs)} pages")

# RSS feed
rss = RSSLoader(extract_full_content=True)
docs = await rss.load("https://blog.example.com/feed.xml")

# REST API with pagination
api = APILoader(
    headers={"Authorization": "Bearer xxx"},
    pagination_key="next_page",
    data_path="$.items[*]"
)
docs = await api.load("https://api.example.com/v1/articles")
```

---

## 🗄️ Database Loaders (4)

Query databases and convert results to documents.

| # | Loader | Database | Features |
|---|--------|----------|----------|
| 31 | **PostgreSQLLoader** | PostgreSQL | Connection pooling, JSONB support |
| 32 | **MySQLLoader** | MySQL/MariaDB | Prepared statements, bulk fetch |
| 33 | **SQLiteLoader** | SQLite | Local files, in-memory support |
| 34 | **MongoDBLoader** | MongoDB | Aggregation pipelines, ObjectId handling |

### Usage Examples

```python
from agentic_brain.rag.loaders import (
    PostgreSQLLoader, MySQLLoader, SQLiteLoader, MongoDBLoader
)

# PostgreSQL with custom query
pg = PostgreSQLLoader(
    host="localhost",
    database="knowledge",
    user="reader",
    password="xxx"
)
docs = await pg.load_query("""
    SELECT title, content, created_at, author
    FROM articles
    WHERE published = true
    ORDER BY created_at DESC
    LIMIT 1000
""")

# MongoDB with aggregation
mongo = MongoDBLoader(uri="mongodb://localhost:27017", database="docs")
docs = await mongo.load_collection(
    "articles",
    filter={"status": "published"},
    projection={"title": 1, "content": 1, "tags": 1}
)

# SQLite from local file
sqlite = SQLiteLoader(path="./local.db")
docs = await sqlite.load_table("notes")
```

---

## ☁️ Cloud Storage Loaders (3)

Load documents from cloud storage providers.

| # | Loader | Provider | Features |
|---|--------|----------|----------|
| 35 | **S3Loader** | AWS S3 | IAM auth, prefix filtering, versioning |
| 36 | **GCSLoader** | Google Cloud Storage | Service account, signed URLs |
| 37 | **AzureBlobLoader** | Azure Blob Storage | SAS tokens, container filtering |

### Usage Examples

```python
from agentic_brain.rag.loaders import S3Loader, GCSLoader, AzureBlobLoader

# AWS S3 with prefix
s3 = S3Loader(
    bucket="company-docs",
    prefix="legal/contracts/",
    region="us-west-2"
)
docs = await s3.load_all(extensions=[".pdf", ".docx"])

# Google Cloud Storage
gcs = GCSLoader(
    bucket="knowledge-base",
    credentials_file="./service-account.json"
)
docs = await gcs.load_all()

# Azure Blob
azure = AzureBlobLoader(
    account_name="myaccount",
    container="documents",
    connection_string="DefaultEndpointsProtocol=https;..."
)
docs = await azure.load_all()
```

---

## 🏢 Enterprise Loaders (17)

Connect to enterprise systems where your data lives.

### Productivity & Collaboration (6)

| # | Loader | Platform | Features |
|---|--------|----------|----------|
| 38 | **SharePointLoader** | Microsoft SharePoint | Sites, lists, document libraries |
| 39 | **ConfluenceLoader** | Atlassian Confluence | Spaces, pages, attachments, comments |
| 40 | **NotionLoader** | Notion | Databases, pages, blocks, relations |
| 41 | **GoogleDriveLoader** | Google Drive | Folders, shared drives, permissions |
| 42 | **DropboxLoader** | Dropbox | Personal, team, paper docs |
| 43 | **OneDriveLoader** | Microsoft OneDrive | Personal, business, shared |

### Communication (5)

| # | Loader | Platform | Features |
|---|--------|----------|----------|
| 44 | **SlackLoader** | Slack | Channels, threads, files, reactions |
| 45 | **TeamsLoader** | Microsoft Teams | Channels, chats, meetings, files |
| 46 | **DiscordLoader** | Discord | Servers, channels, threads, attachments |
| 47 | **GmailLoader** | Gmail | Labels, threads, attachments |
| 48 | **OutlookLoader** | Microsoft Outlook | Folders, categories, attachments |

### Project Management (3)

| # | Loader | Platform | Features |
|---|--------|----------|----------|
| 49 | **JiraLoader** | Atlassian Jira | Issues, comments, attachments, sprints |
| 50 | **AsanaLoader** | Asana | Tasks, projects, comments |
| 51 | **LinearLoader** | Linear | Issues, projects, comments, cycles |

### CRM & Business (3)

| # | Loader | Platform | Features |
|---|--------|----------|----------|
| 52 | **SalesforceLoader** | Salesforce | Objects, reports, knowledge articles |
| 53 | **HubSpotLoader** | HubSpot | Contacts, deals, tickets, knowledge base |
| 54 | **ZendeskLoader** | Zendesk | Tickets, articles, macros |

### Usage Examples

```python
from agentic_brain.rag.loaders import (
    NotionLoader, SlackLoader, JiraLoader, ConfluenceLoader,
    SharePointLoader, GmailLoader, SalesforceLoader
)

# Notion database
notion = NotionLoader(api_key="secret_xxx")
docs = await notion.load_database(
    database_id="abc123",
    filter={"Status": {"equals": "Published"}}
)

# Slack channel history
slack = SlackLoader(token="xoxb-xxx")
docs = await slack.load_channel(
    channel="engineering",
    days=30,
    include_threads=True
)

# Jira project
jira = JiraLoader(
    server="https://company.atlassian.net",
    email="bot@company.com",
    api_token="xxx"
)
docs = await jira.load_project(
    project="ENG",
    jql="status != Done AND updated >= -30d"
)

# Confluence space
confluence = ConfluenceLoader(
    url="https://company.atlassian.net/wiki",
    username="bot@company.com",
    api_token="xxx"
)
docs = await confluence.load_space("DOCS", include_attachments=True)

# SharePoint document library
sharepoint = SharePointLoader(
    site_url="https://company.sharepoint.com/sites/docs",
    client_id="xxx",
    client_secret="xxx"
)
docs = await sharepoint.load_library("Shared Documents/Policies")

# Gmail with label filtering
gmail = GmailLoader(credentials_file="./gmail-creds.json")
docs = await gmail.load_messages(
    label="important",
    days=7,
    include_attachments=True
)

# Salesforce knowledge base
sf = SalesforceLoader(
    username="bot@company.com",
    password="xxx",
    security_token="xxx"
)
docs = await sf.load_knowledge_articles(category="Product")
```

---

## 🔧 Common Patterns

### Directory Loading

All file-based loaders support directory scanning:

```python
from agentic_brain.rag.loaders import DirectoryLoader

# Load all supported files from a directory
loader = DirectoryLoader(
    path="./documents/",
    glob="**/*",  # Recursive
    exclude=["*.tmp", "node_modules/**"],
    show_progress=True
)
docs = await loader.load()
print(f"Loaded {len(docs)} documents from {loader.files_found} files")
```

### Multi-Source Loading

Combine multiple loaders:

```python
from agentic_brain.rag.loaders import MultiLoader

loader = MultiLoader([
    PDFLoader().for_directory("./contracts/"),
    NotionLoader(api_key="...").for_database("kb"),
    SlackLoader(token="...").for_channel("engineering"),
])

docs = await loader.load_all()
```

### Document Filtering

Filter documents after loading:

```python
from agentic_brain.rag.loaders import PDFLoader

docs = await PDFLoader().load_directory("./docs/")

# Filter by metadata
recent_docs = [d for d in docs if d.metadata.get("created") > "2024-01-01"]
english_docs = [d for d in docs if d.metadata.get("language") == "en"]
```

### Incremental Loading

Only load new/changed documents:

```python
from agentic_brain.rag.loaders import NotionLoader
from agentic_brain.rag import RAGPipeline

notion = NotionLoader(api_key="...")
rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")

# Load incrementally (only new pages since last sync)
new_docs = await notion.load_database(
    "knowledge-base",
    since=rag.get_last_sync_time("notion-kb")
)

if new_docs:
    await rag.ingest_documents(new_docs)
    rag.set_last_sync_time("notion-kb")
```

---

## 📊 Loader Output Format

All loaders return `Document` objects with consistent structure:

```python
@dataclass
class Document:
    content: str           # The text content
    metadata: dict         # Source-specific metadata
    source: str            # Source identifier (file path, URL, etc.)
    doc_type: str          # "pdf", "notion", "slack", etc.
    created_at: datetime   # Document creation time
    chunk_id: str | None   # Assigned during chunking
    embedding: list | None # Assigned during embedding
```

### Metadata by Source Type

| Source | Common Metadata Fields |
|--------|------------------------|
| PDF | `page_num`, `total_pages`, `author`, `title`, `tables`, `images` |
| Code | `language`, `file_path`, `functions`, `classes`, `imports`, `line_count` |
| Notion | `page_id`, `title`, `last_edited`, `created_by`, `parent_id` |
| Slack | `channel`, `user`, `timestamp`, `thread_ts`, `reactions` |
| Jira | `issue_key`, `summary`, `status`, `assignee`, `project`, `labels` |
| Email | `from`, `to`, `subject`, `date`, `thread_id`, `attachments` |

---

## 🚀 Performance Tips

### Concurrent Loading

```python
import asyncio
from agentic_brain.rag.loaders import PDFLoader

# Load multiple files concurrently
loader = PDFLoader()
files = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]

docs = await asyncio.gather(*[
    loader.load(f) for f in files
])
docs = [d for batch in docs for d in batch]  # Flatten
```

### Batch Processing

```python
from agentic_brain.rag.loaders import NotionLoader

notion = NotionLoader(api_key="...")

# Process in batches to avoid memory issues
async for batch in notion.load_database_batched(
    "large-database",
    batch_size=100
):
    await rag.ingest_documents(batch)
    print(f"Processed batch of {len(batch)} docs")
```

### Caching

```python
from agentic_brain.rag.loaders import PDFLoader

# Enable caching for repeated loads
loader = PDFLoader(cache_dir="./loader_cache/")
docs = await loader.load("big-report.pdf")  # Cached after first load
```

---

## 🔗 Integration with GraphRAG

All loaders integrate seamlessly with the GraphRAG pipeline:

```python
from agentic_brain.rag import RAGPipeline
from agentic_brain.rag.loaders import (
    PDFLoader, NotionLoader, SlackLoader, JiraLoader
)

# Initialize GraphRAG pipeline
rag = RAGPipeline(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)

# Load from multiple sources
pdf_docs = await PDFLoader().load_directory("./policies/")
notion_docs = await NotionLoader(api_key="...").load_database("wiki")
slack_docs = await SlackLoader(token="...").load_channel("support", days=90)
jira_docs = await JiraLoader(...).load_project("SUPPORT")

# Combine all documents
all_docs = pdf_docs + notion_docs + slack_docs + jira_docs

# Ingest into knowledge graph
await rag.ingest_documents(
    all_docs,
    chunk_strategy="semantic",  # Smart chunking
    extract_entities=True,       # Entity extraction for graph
    extract_relationships=True   # Relationship extraction for graph
)

# Now query across ALL sources with GraphRAG
result = await rag.graph_query(
    "What is our refund policy and how do customers typically ask about it?"
)
print(result.answer)
print(f"Sources: {result.sources}")  # Shows PDF policy + Slack questions
```

---

## 📚 See Also

- [RAG Guide](./RAG_GUIDE.md) — GraphRAG concepts and query strategies
- [RAG Reference](./RAG.md) — Complete RAG pipeline documentation
- [Architecture](./architecture.md) — System architecture overview
- [Neo4j Integration](./integrations/NEO4J.md) — Knowledge graph setup

---

<div align="center">

**54 loaders. Infinite possibilities.**

*Load anything. Graph everything. Query intelligently.*

</div>
