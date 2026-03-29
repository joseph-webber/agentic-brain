# Enhanced Agentic Brain Installer

**Perfect User Experience • Accessible • Privacy-First**

## Features

The enhanced installer provides:

### 1. **Environment Detection** 🔍
- Operating System (macOS, Linux, Windows)
- Python version verification
- GPU acceleration (Apple Silicon MPS, NVIDIA CUDA, AMD ROCm)
- Text-to-Speech voices (macOS `say`, Linux `espeak`, Windows SAPI)
- System timezone detection

### 2. **User Profile Setup** 👤
- **Privacy-first**: All data stored locally
- **Required**: Timezone (system auto-detected as default)
- **Optional**: Name, location, email, date of birth
- Saves to `~/.agentic-brain/private/user_profile.json` (mode 600)
- Creates `.env.user` for environment variables (git-ignored)

### 3. **LLM Configuration** 🤖
- Auto-detects available API keys (OpenAI, Anthropic, Gemini, Groq, Ollama)
- Tests connectivity for each provider
- Sets up intelligent fallback chain
- Configures default provider based on availability
- Priority order: Ollama → Groq → OpenAI → Anthropic → Gemini

### 4. **ADL Initialization** 📝
- Creates `brain.adl` configuration file
- Generates `config.json` with user preferences
- Sets up intelligent model routing (fast/balanced/smart)
- Configures memory and voice settings

### 5. **Health Check** 🏥
- Verifies Python version (3.9+ required)
- Checks virtual environment status
- Validates GPU acceleration
- Tests LLM provider connectivity
- Confirms configuration files present
- Shows comprehensive status dashboard

## Quick Start

### Interactive Mode (Recommended)

```bash
# Run the enhanced setup wizard
agentic-brain setup

# Or directly with Python
python -m agentic_brain.installer_enhanced
```

### Non-Interactive Mode

```bash
# Use defaults, no prompts (CI/CD friendly)
agentic-brain setup --non-interactive

# Or
python -m agentic_brain.installer_enhanced --non-interactive
```

### Accessibility Mode

```bash
# Disable colors for screen readers
agentic-brain setup --no-color

# Or set environment variable
NO_COLOR=1 agentic-brain setup
```

## What Gets Created

### Configuration Directory

**macOS**: `~/Library/Application Support/agentic-brain/`  
**Linux**: `~/.config/agentic-brain/`  
**Windows**: `%LOCALAPPDATA%\agentic-brain\`

### Files Created

```
~/.config/agentic-brain/          (or equivalent on your OS)
├── brain.adl                     # ADL configuration
├── config.json                   # System configuration
├── .env.user                     # User environment variables (mode 600)
└── private/
    └── user_profile.json         # User profile (mode 600)
```

### Example `brain.adl`

```yaml
# Agentic Brain ADL Configuration
agent:
  name: "MyBrain"
  version: "1.0.0"
  description: "My personal AI assistant"

user:
  timezone: "Australia/Adelaide"
  location: "Adelaide, SA"

llm:
  default_provider: "ollama"
  fallback_chain: ["ollama", "groq", "openai"]
  
  models:
    fast: "llama3.2:3b"      # Quick responses
    balanced: "llama3.1:8b"  # Good quality
    smart: "claude-sonnet"   # Best reasoning

chat:
  temperature: 0.7
  max_tokens: 2048
  persist_sessions: true
  
memory:
  enabled: true
  vector_search: true
  threshold: 0.75

voice:
  enabled: true
  system: "macOS say"
  default_voice: "Samantha"
```

## Accessibility Features

The installer is designed for **screen reader compatibility**:

1. **Plain text output** - No emoji-only indicators
2. **Auto-disable colors** - Detects terminal capabilities
3. **Clear feedback** - Every action announces success/failure
4. **Keyboard-only** - No mouse required
5. **Descriptive prompts** - Clear instructions at every step
6. **Graceful error handling** - Helpful error messages

### Testing with VoiceOver (macOS)

```bash
# Enable VoiceOver
Cmd + F5

# Run installer
agentic-brain setup

# Navigate with:
# - VO + Right Arrow: Move forward
# - VO + Left Arrow: Move backward
# - Return: Submit input
```

## Detection Details

### GPU Detection

The installer detects:

| Platform | Detection Method | Capability |
|----------|------------------|------------|
| **Apple Silicon** | `torch.backends.mps.is_available()` | Metal Performance Shaders |
| **NVIDIA** | `torch.cuda.is_available()` | CUDA acceleration |
| **AMD** | `rocm-smi --showproductname` | ROCm acceleration (Linux) |

### Voice Detection

| Platform | System | Detection Method |
|----------|--------|------------------|
| **macOS** | `say` | `say -v ?` lists voices |
| **Linux** | `espeak` | `espeak --voices` lists voices |
| **Windows** | SAPI | PowerShell speech synthesis query |

### Timezone Detection

Uses Python's `time` module to detect:
- Timezone name (e.g., "ACDT", "PST")
- UTC offset (e.g., "+10:30", "-08:00")
- Daylight saving time status

## Health Check Criteria

| Component | Check | Required | Fix If Failed |
|-----------|-------|----------|---------------|
| **Python** | Version ≥ 3.9 | ✅ Yes | Upgrade Python |
| **Virtual Env** | Active venv | ⚠️ Recommended | Create venv |
| **GPU** | Acceleration available | ❌ No | Install GPU drivers |
| **LLM** | At least 1 provider | ✅ Yes | Install Ollama or add API key |
| **Config Files** | All present | ✅ Yes | Re-run installer |
| **Profile** | Timezone set | ✅ Yes | Configure profile |

## Privacy & Security

### What Gets Stored

**Locally Only** (never transmitted):
- User profile (name, location, timezone, email, DOB) - all optional except timezone
- LLM API keys (stored in `.env.user`)
- Configuration preferences

**File Permissions**:
- `user_profile.json` - Mode 600 (read/write owner only)
- `.env.user` - Mode 600 (read/write owner only)
- Config directory - Mode 755 (standard)

### What Gets Transmitted

**Nothing from the installer** - All data stays local.

When you use the brain:
- Chat messages → Your chosen LLM provider (per their privacy policy)
- Neo4j data → Your local or hosted Neo4j instance

## Troubleshooting

### Python Version Too Old

```bash
# Check current version
python --version

# Install Python 3.9+ (macOS with Homebrew)
brew install python@3.11

# Or use pyenv
pyenv install 3.11.0
pyenv global 3.11.0
```

### No LLM Providers Found

**Quick fix - Install Ollama (free, local)**:

```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download

# Pull a model
ollama pull llama3.1:8b

# Verify
ollama list
```

**Or add API key**:

```bash
# Groq (free)
export GROQ_API_KEY="your_key_here"

# OpenAI
export OPENAI_API_KEY="your_key_here"

# Add to ~/.bashrc or ~/.zshrc to persist
```

### GPU Not Detected

**Apple Silicon (M1/M2/M3)**:
```bash
# Install PyTorch with MPS support
pip install torch torchvision torchaudio
```

**NVIDIA CUDA**:
```bash
# Install CUDA toolkit
# Visit: https://developer.nvidia.com/cuda-downloads

# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**AMD ROCm** (Linux only):
```bash
# Install ROCm
# Visit: https://rocmdocs.amd.com/

# Install PyTorch with ROCm
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.6
```

### Voices Not Detected

**macOS**:
```bash
# Verify say command works
say "Hello world"

# List available voices
say -v ?
```

**Linux**:
```bash
# Install espeak
sudo apt-get install espeak

# Test
espeak "Hello world"
```

**Windows**:
```powershell
# Test SAPI
Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.Speak("Hello world")
```

## Status Dashboard Example

After successful installation:

```
╔══════════════════════════════════════════════════════════════╗
║              AGENTIC BRAIN - STATUS DASHBOARD                ║
╚══════════════════════════════════════════════════════════════╝

Environment:
  OS: Darwin 23.3.0 (arm64)
  Python: 3.11.5
  GPU: Apple Silicon - Metal Performance Shaders (MPS)

User Profile:
  Timezone: ACDT (UTC+10:30)
  Name: Agentic Brain Contributors
  Location: Adelaide, SA

LLM Configuration:
  Default: Ollama
  Providers: Ollama, Groq, OpenAI
  Fallback: Ollama → Groq → OpenAI

Text-to-Speech:
  System: macOS say
  Voices: 87 available
  Recommended: Samantha, Karen, Daniel

Health Status:
  ✓ Python
  ✓ Venv
  ✓ Gpu
  ✓ Llm
  ✓ Config
  ✓ Profile

Configuration:
  Directory: /Users/joe/Library/Application Support/agentic-brain
  Profile: .../private/user_profile.json
  ADL Config: .../brain.adl
```

## Next Steps After Setup

```bash
# 1. Start a chat session
agentic-brain chat

# 2. Check your configuration
agentic-brain config

# 3. View status anytime
agentic-brain status

# 4. Test LLM providers
agentic-brain check

# 5. Run a health check
agentic-brain health
```

## For Developers

### Integrate in Your App

```python
from agentic_brain.installer_enhanced import (
    detect_os,
    detect_python,
    detect_gpu,
    detect_voices,
    detect_timezone,
    detect_llm_keys,
    run_environment_detection,
)

# Run full detection
env = run_environment_detection()

# Or individual checks
os_info = detect_os()
python_info = detect_python()
gpu_info = detect_gpu()
voices_info = detect_voices()
timezone_info = detect_timezone()
llm_keys = detect_llm_keys()

# Use results
if gpu_info["can_accelerate"]:
    print(f"GPU acceleration available: {gpu_info['type']}")
else:
    print("CPU-only mode")
```

### Custom Health Checks

```python
from agentic_brain.installer_enhanced import (
    test_llm_connection,
    run_health_check,
)

# Test specific provider
success, message = test_llm_connection("ollama")
print(f"Ollama: {message}")

# Run full health check
health = run_health_check(env, profile, llm_config)
if health["overall"]:
    print("System ready!")
else:
    print("Setup incomplete")
```

## Contributing

The enhanced installer is in:
- `src/agentic_brain/installer_enhanced.py`

Improvements welcome:
- Additional GPU detection methods
- Better voice system detection
- Enhanced error messages
- More accessibility features

## Support

- **Issues**: https://github.com/agentic-brain-project/agentic-brain/issues
- **Discussions**: https://github.com/agentic-brain-project/agentic-brain/discussions
- **Email**: agentic-brain@proton.me

## License

Apache-2.0 - See LICENSE file

---

**Version**: 2.0.0  
**Last Updated**: 2026-03-25  
**Status**: Production Ready ✅
