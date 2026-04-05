# Quick Reference: Publishing agentic-brain to PyPI

## 📋 Pre-Publication Checklist

```bash
✅ All tests passing
cd /Users/joe/brain/agentic-brain
python3 -m pytest tests/test_package_metadata.py tests/test_pypi_distribution.py -v

✅ Verification passed
python3 << 'EOF'
import agentic_brain
print(f"✅ Version: {agentic_brain.__version__}")
print(f"✅ Author: {agentic_brain.__author__}")
EOF

✅ All required files exist
ls -la MANIFEST.in src/agentic_brain/py.typed scripts/publish.sh
```

## 🚀 Publication Steps

### Step 1: Dry-Run (Verify, No Upload)
```bash
cd /Users/joe/brain/agentic-brain
./scripts/publish.sh --dry-run
```
Expected: Shows distribution files that would be created (no upload)

### Step 2: Test PyPI (Optional but Recommended)
```bash
./scripts/publish.sh --test
```

After upload, test installation:
```bash
pip install -i https://test.pypi.org/simple/ agentic-brain==3.1.1
python -c "import agentic_brain; print(f'✅ {agentic_brain.__version__}')"
pip uninstall agentic-brain  # Cleanup
```

### Step 3: Production PyPI (Final)
```bash
./scripts/publish.sh
```

## ✅ Post-Publication Verification

```bash
# Install from PyPI
pip install agentic-brain==3.1.1

# Verify version
python -c "import agentic_brain; print(f'Installed: {agentic_brain.__version__}')"

# Test CLI entry points
agentic-brain --help
agentic --help
ab --help

# Test imports
python -c "from agentic_brain import Agent, Neo4jMemory, AgenticBrainError; print('✅ All imports work')"
```

## 📦 What Gets Published

1. **Source distribution** (`agentic_brain-3.1.1.tar.gz`)
   - Full source code
   - Tests and documentation
   - License file

2. **Wheel distribution** (`agentic_brain-3.1.1-py3-*.whl`)
   - Compiled Python package
   - py.typed marker for type hints
   - Entry points for CLI commands

## 🔗 Post-Publication Links

Once published:
- PyPI Project: https://pypi.org/project/agentic-brain/
- PyPI Version: https://pypi.org/project/agentic-brain/3.1.1/
- Repository: https://github.com/ecomlounge/brain
- GitHub Release: Add git tag `git tag v3.1.1 && git push --tags`

## 📊 Package Statistics

| Item | Value |
|------|-------|
| Package Name | agentic-brain |
| Version | 3.1.1 |
| Python | >=3.11 |
| License | Apache-2.0 |
| Base Dependencies | 16 |
| Optional Groups | 47 |
| Entry Points | 3 |
| Status | Production/Stable |
| Type Hints | Yes (PEP 561) |

## 🆘 Troubleshooting

**Issue**: twine/build not found
```bash
# Install with pipx (recommended)
pipx install twine build

# Or use pip in venv
python3 -m venv /tmp/pb && source /tmp/pb/bin/activate && pip install twine build
```

**Issue**: Authentication error when uploading
```bash
# Create ~/.pypirc with PyPI token
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...
```

**Issue**: Version mismatch
```bash
# Always sync these:
# 1. pyproject.toml: version = "3.1.1"
# 2. src/agentic_brain/__init__.py: __version__ = "3.1.1"
```

## 📝 Files Involved

| File | Purpose | Status |
|------|---------|--------|
| pyproject.toml | Package config | ✅ Updated |
| src/agentic_brain/__init__.py | Version | ✅ Updated |
| src/agentic_brain/py.typed | Type hints | ✅ Created |
| MANIFEST.in | Includes | ✅ Created |
| scripts/publish.sh | Publish tool | ✅ Created |
| README.md | Install docs | ✅ Updated |
| tests/ | Test suite | ✅ Created |

## 🎯 Installation Examples for Users

```bash
# Basic
pip install agentic-brain

# With features
pip install "agentic-brain[llm]"
pip install "agentic-brain[api,graphrag]"
pip install "agentic-brain[voice-kokoro]"

# Everything
pip install "agentic-brain[all]"

# Development
pip install "agentic-brain[dev]"
```

## ✨ Success Indicators

After running `./scripts/publish.sh`:
- ✅ Shows version 3.1.1
- ✅ Finds MANIFEST.in
- ✅ Creates tar.gz and .whl
- ✅ Validates metadata with twine
- ✅ Uploads to PyPI (or test.pypi)

## 🔄 Update Cycle for Next Release

When ready for 3.1.2:

1. Update version in both files:
   - `pyproject.toml` → version = "3.1.2"
   - `src/agentic_brain/__init__.py` → __version__ = "3.1.2"

2. Run tests:
   ```bash
   pytest tests/test_package_metadata.py -v
   ```

3. Publish:
   ```bash
   ./scripts/publish.sh
   ```

---

**Quick Links:**
- 📖 Full Guide: PYPI_PACKAGING_GUIDE.md
- 📊 Summary: PYPI_PUBLICATION_SUMMARY.txt
- 📦 PyPI: https://pypi.org/project/agentic-brain/
- 🔗 GitHub: https://github.com/ecomlounge/brain
