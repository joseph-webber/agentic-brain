# 🚀 Enhanced Installer - Quick Reference

**Version**: 2.0.0 | **Status**: ✅ Production Ready

---

## Quick Start

```bash
# Interactive setup (recommended)
agentic-brain setup

# Or directly
python3 -m agentic_brain.installer_enhanced

# Non-interactive (CI/CD)
agentic-brain setup --non-interactive

# Accessibility mode
agentic-brain setup --no-color
```

---

## What It Does

| Feature | Description | Required |
|---------|-------------|----------|
| **Environment Detection** | OS, Python, GPU, voices, timezone | Auto |
| **User Profile** | Timezone, name, location, email (privacy-first) | Timezone only |
| **LLM Configuration** | API keys, connectivity tests, fallback chain | Yes |
| **ADL Initialization** | Creates `brain.adl` and `config.json` | Auto |
| **Health Check** | Verifies everything works | Auto |

---

## Files Created

```
~/.config/agentic-brain/          (or OS equivalent)
├── brain.adl                     # ADL config
├── config.json                   # System config
├── .env.user                     # Env vars (mode 600)
└── private/
    └── user_profile.json         # Profile (mode 600)
```

---

## Detection Summary

✅ **OS**: Darwin 23.4.0 (arm64)  
✅ **Python**: 3.14.3  
✅ **GPU**: Apple Silicon MPS  
✅ **Voices**: 145 (macOS say)  
✅ **Timezone**: ACDT (UTC+10:30)  
✅ **LLM**: Ollama, Groq  

---

## Health Check

| Component | Status | Fix |
|-----------|--------|-----|
| Python ≥3.9 | ✅ Required | Upgrade Python |
| Virtual Env | ⚠️ Recommended | Create venv |
| GPU | ✅ Optional | Install drivers |
| LLM | ✅ Required | Install Ollama or add API key |
| Config Files | ✅ Required | Re-run installer |
| Profile | ✅ Required | Set timezone |

---

## Troubleshooting

### No LLM Found
```bash
# Install Ollama (free, local)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:8b
```

### Python Too Old
```bash
# macOS
brew install python@3.11

# Or use pyenv
pyenv install 3.11.0
```

### GPU Not Detected
```bash
# Apple Silicon
pip install torch torchvision torchaudio

# NVIDIA CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

---

## Next Steps

```bash
# 1. Start chatting
agentic-brain chat

# 2. Check config
agentic-brain config

# 3. View status
agentic-brain status

# 4. Test LLMs
agentic-brain check
```

---

## Accessibility

✅ Screen reader compatible  
✅ Auto-disables colors if needed  
✅ Keyboard-only navigation  
✅ Clear audio feedback  
✅ `--no-color` flag available  
✅ `NO_COLOR` env var respected  

---

## Privacy

✅ All data stored **locally**  
✅ Secure file permissions (mode 600)  
✅ `.env.user` git-ignored  
✅ **Nothing transmitted** during setup  

---

## Documentation

📖 **Full Guide**: `ENHANCED_INSTALLER.md`  
📖 **API Docs**: Docstrings in code  
📖 **Tests**: `tests/test_installer_enhanced.py`  
📖 **Summary**: `INSTALLER_ENHANCEMENT_COMPLETE.md`  

---

## Support

🐛 **Issues**: https://github.com/agentic-brain-project/agentic-brain/issues  
💬 **Discussions**: https://github.com/agentic-brain-project/agentic-brain/discussions  
📧 **Email**: agentic-brain@proton.me  

---

**Built by Agentic Brain Contributors**  
**License**: Apache-2.0
