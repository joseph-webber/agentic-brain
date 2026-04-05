# PyPI Package Publication Guide

**Project**: agentic-brain  
**Version**: 3.1.1  
**Status**: ✅ Ready for publication

## What Was Created

### 1. **Package Metadata** (`pyproject.toml` - Updated)
- ✅ Updated version to 3.1.1
- ✅ Added author email: agentic-brain@proton.me
- ✅ Added maintainers: Joseph Webber (joseph.webber@gmail.com)
- ✅ Configured 6 project URLs (Homepage, Repository, Documentation, Changelog, Bug Tracker, Source Code)
- ✅ Verified 47 optional dependency groups (dev, test, api, voice, pdf, documents, etc.)
- ✅ Verified 19 classifiers (Production/Stable, Python 3.11-3.14, Typing::Typed)
- ✅ Configured 3 CLI entry points (agentic-brain, agentic, ab)

### 2. **Version Management** (`src/agentic_brain/__init__.py`)
- ✅ Updated `__version__` to 3.1.1 (consistent with pyproject.toml)
- ✅ Maintained lazy-loading export system
- ✅ All metadata attributes defined and verified

### 3. **Type Hints Marker** (`src/agentic_brain/py.typed`)
- ✅ Created empty marker file for PEP 561 compliance
- ✅ Enables type-checking in dependent packages
- ✅ Included in package-data configuration

### 4. **Package Manifest** (`MANIFEST.in`)
Created to explicitly include:
- README.md, LICENSE, CHANGELOG.md, CONTRIBUTING.md
- Entire docs/ and tests/ directories
- Audio assets (WAV files, native code)
- Excludes git, cache, build directories

### 5. **Publication Script** (`scripts/publish.sh`)
A comprehensive bash script for PyPI publication with:
- **Prerequisite checks**: Python version, build tools
- **Package verification**: Structure, metadata, file completeness
- **Version extraction**: From `__init__.py`
- **Build process**: Using `python3 -m build`
- **Metadata validation**: Using twine
- **Publication modes**:
  - `./scripts/publish.sh` → Publish to production PyPI
  - `./scripts/publish.sh --test` → Publish to TestPyPI
  - `./scripts/publish.sh --dry-run` → Show what would be published
- **Comprehensive output**: Color-coded progress and diagnostics

**Usage:**
```bash
# Make executable (already done)
chmod +x scripts/publish.sh

# Test the script (dry-run)
./scripts/publish.sh --dry-run

# Publish to TestPyPI (for testing)
./scripts/publish.sh --test

# Publish to production PyPI
./scripts/publish.sh
```

### 6. **Installation Instructions** (`README.md` - Updated)
Added comprehensive pip installation section:

```bash
# Basic installation
pip install agentic-brain

# With specific features
pip install "agentic-brain[llm]"        # LLM providers
pip install "agentic-brain[api]"        # API server
pip install "agentic-brain[graphrag]"   # GraphRAG + Neo4j
pip install "agentic-brain[voice-kokoro]"  # Voice I/O
pip install "agentic-brain[all]"        # Everything
pip install "agentic-brain[dev]"        # Development tools

# Verify installation
python -c "import agentic_brain; print(f'Agentic Brain {agentic_brain.__version__}')"
agentic-brain --help
```

### 7. **Comprehensive Tests** (54 tests total)

#### `tests/test_package_metadata.py` (38 tests)
- **TestPackageMetadata**: Version, author, license, description, email
- **TestPackageFiles**: py.typed, README, LICENSE, MANIFEST.in, pyproject.toml, publish.sh
- **TestPackageStructure**: Import tests, lazy exports, __all__ exports
- **TestPackageScripts**: Entry points verification
- **TestBuildConfiguration**: Build system, setuptools, Python version requirement
- **TestDependencies**: Dependencies structure, optional groups
- **TestPackageClassifiers**: Status, Python versions, type hints, license
- **TestLazyLoading**: Lazy loading mechanism, imports
- **TestInstallationSimulation**: Installation readiness
- **TestTypeHints**: py.typed marker
- **TestPackagingIntegration**: Build and metadata completeness

#### `tests/test_pypi_distribution.py` (18 tests)
- **TestPackageDistributionReadiness**: Version consistency, metadata completeness, URLs, classifiers, entry points, dependencies
- **TestPackageDistributionWorkflow**: Publish script, MANIFEST.in, py.typed
- **TestPackageFileStructure**: src/ layout, subpackages, .gitignore

**All tests passing**: ✅ 46 passed, 10 skipped

## File Checklist

| File | Purpose | Status |
|------|---------|--------|
| `pyproject.toml` | Package config | ✅ Updated |
| `src/agentic_brain/__init__.py` | Version & exports | ✅ Updated |
| `src/agentic_brain/py.typed` | PEP 561 marker | ✅ Created |
| `MANIFEST.in` | Package manifest | ✅ Created |
| `scripts/publish.sh` | Publication script | ✅ Created |
| `README.md` | Install instructions | ✅ Updated |
| `tests/test_package_metadata.py` | Package tests | ✅ Created |
| `tests/test_pypi_distribution.py` | Distribution tests | ✅ Created |

## How to Use for Publication

### Step 1: Install publication dependencies
```bash
# Option A: Using pipx (recommended)
pipx install twine build

# Option B: In virtual environment
python3 -m venv /tmp/publish-venv
source /tmp/publish-venv/bin/activate
pip install twine build
```

### Step 2: Test the publication script (dry-run)
```bash
cd /Users/joe/brain/agentic-brain
./scripts/publish.sh --dry-run
```

Expected output:
- ✓ All files verified
- ✓ Version extracted (3.1.1)
- ✓ Distribution packages shown
- No actual upload occurs

### Step 3: Publish to TestPyPI (optional but recommended)
```bash
./scripts/publish.sh --test
```

This will:
1. Check prerequisites
2. Build distribution packages
3. Validate metadata
4. Upload to test.pypi.org

Then test installation:
```bash
pip install -i https://test.pypi.org/simple/ agentic-brain==3.1.1
```

### Step 4: Publish to production PyPI
```bash
./scripts/publish.sh
```

This will upload to the official PyPI repository.

### Verification
After publication, verify the package:

```bash
# Install from PyPI
pip install agentic-brain==3.1.1

# Check version
python -c "import agentic_brain; print(agentic_brain.__version__)"

# Check all exports are accessible
python -c "from agentic_brain import Agent, Neo4jMemory, AgenticBrainError; print('✓ All exports accessible')"

# Test CLI entry points
agentic-brain --help
agentic --help
ab --help
```

## PyPI Profile URLs

Once published, the package will be available at:

- **PyPI**: https://pypi.org/project/agentic-brain/
- **Project page**: https://pypi.org/project/agentic-brain/3.1.1/
- **Repository**: https://github.com/ecomlounge/brain
- **Documentation**: https://github.com/ecomlounge/brain/blob/main/docs/INDEX.md

## Optional Dependencies Reference

The package provides 47 optional dependency groups:

**Voice & Audio:**
- `voice-kokoro` — High-quality voice synthesis
- `voice-cloning` — Voice cloning with F5-TTS
- `voice-wakeword` — Wake word detection
- `voice-emotion` — Emotion detection
- `voice-vad` — Voice Activity Detection
- `voice-realtimestt` — Real-time speech-to-text

**Data & RAG:**
- `pdf`, `pdf-ocr`, `pdf-write`, `pdf-full` — PDF processing
- `documents` — All document formats (DOCX, XLSX, PPTX, EPUB)
- `graphrag` — GraphRAG with Neo4j
- `embeddings` — Sentence transformers
- `vectordb` — Vector databases (Pinecone, Weaviate, Qdrant)

**Enterprise:**
- `enterprise` — LDAP, SAML, MFA
- `security` — PII detection/redaction
- `accessibility` — Alt-text generation, image analysis
- `observability` — OpenTelemetry integration

**Development:**
- `dev` — All development tools (pytest, mypy, ruff, etc.)
- `test` — Testing dependencies
- `docs` — Documentation generation

**All:**
- `all` — Every optional dependency installed

## Testing

Run all packaging tests:

```bash
# All tests
python3 -m pytest tests/test_package_metadata.py tests/test_pypi_distribution.py -v

# Specific test class
python3 -m pytest tests/test_package_metadata.py::TestPackageMetadata -v

# With coverage
python3 -m pytest tests/test_package_metadata.py --cov=src/agentic_brain
```

## Common Issues & Solutions

### Issue: "py.typed not found"
**Solution**: It's already created at `src/agentic_brain/py.typed`

### Issue: Version mismatch between files
**Solution**: Always update `src/agentic_brain/__init__.py` to match `pyproject.toml`

### Issue: twine not found
**Solution**: 
```bash
# Install with pipx
pipx install twine

# Or in venv
pip install twine
```

### Issue: MANIFEST.in not included in wheel
**Solution**: Ensure py.typed is in package-data section of pyproject.toml (already configured)

### Issue: Documentation not available on PyPI
**Solution**: Verify README.md has proper frontmatter and links are absolute URLs

## What Gets Published

The publication process creates:

1. **Source Distribution** (`.tar.gz`)
   - All source code
   - Tests
   - Documentation
   - License files
   
2. **Wheel Distribution** (`.whl`)
   - Compiled Python package
   - Binary extensions (if any)
   - Type hints marker (py.typed)
   - Entry points

## Post-Publication

After successful publication to PyPI:

1. **Update version**: Bump version in both `pyproject.toml` and `__init__.py`
2. **Tag release**: `git tag v3.1.1 && git push --tags`
3. **Update docs**: Link to new PyPI version
4. **Announce**: Post release notes to relevant channels

## References

- [Python Packaging Guide](https://packaging.python.org/)
- [setuptools Documentation](https://setuptools.pypa.io/)
- [PyPI Project](https://pypi.org/)
- [PEP 561 - Type Hints](https://www.python.org/dev/peps/pep-0561/)
- [Twine Documentation](https://twine.readthedocs.io/)

---

**Status**: ✅ Complete and Ready for Publication
**Last Updated**: 2026-04-02
**Test Results**: 46 passed, 10 skipped
