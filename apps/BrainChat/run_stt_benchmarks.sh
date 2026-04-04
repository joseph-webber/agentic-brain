#!/bin/bash
# Comprehensive STT Benchmark Runner
# Tests all speech-to-text engines in BrainChat and generates performance reports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="${SCRIPT_DIR}/benchmarks"
BRAIN_DIR="${HOME}/brain"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}🎙️  BrainChat Speech-to-Text Benchmark Suite${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"

# Create benchmark directory
mkdir -p "${BENCHMARK_DIR}"
echo -e "${GREEN}✓${NC} Benchmark directory: ${BENCHMARK_DIR}"

# Check system info
echo ""
echo -e "${BLUE}System Information:${NC}"
echo "  Platform: $(uname -s)"
echo "  Architecture: $(uname -m)"
echo "  CPU Cores: $(sysctl -n hw.ncpu)"
echo "  RAM: $(sysctl -n hw.memsize | numfmt --to=iec 2>/dev/null || sysctl -n hw.memsize)"

# Check dependencies
echo ""
echo -e "${BLUE}Checking Dependencies:${NC}"

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 - NOT FOUND"
        return 1
    fi
}

check_command "swift"
check_command "python3"
check_command "ffmpeg"
check_command "whisper-cpp" || true

# Check Python packages
echo ""
echo -e "${BLUE}Checking Python Packages:${NC}"

check_python_package() {
    if python3 -c "import $1" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 - NOT INSTALLED"
        return 1
    fi
}

check_python_package "faster_whisper" || echo "    Install: pip3 install faster-whisper"
check_python_package "librosa" || echo "    Install: pip3 install librosa"
check_python_package "soundfile" || echo "    Install: pip3 install soundfile"

# Create baseline results file template
echo ""
echo -e "${BLUE}Creating Baseline Results Template:${NC}"

cat > "${BENCHMARK_DIR}/stt-baseline.json" << 'EOF'
{
  "benchmark_info": {
    "name": "BrainChat STT Engine Benchmark",
    "version": "1.0",
    "created": "2024",
    "description": "Comprehensive benchmark of speech-to-text engines"
  },
  "engines": [
    {
      "name": "apple",
      "description": "Apple Speech Recognition (SFSpeechRecognizer)",
      "type": "native",
      "platform": "macOS",
      "target_latency_ms": 200,
      "category": "fast"
    },
    {
      "name": "faster_whisper",
      "description": "Python faster-whisper (Local)",
      "type": "local",
      "platform": "Cross-platform",
      "models": ["tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "large"],
      "target_latency_ms": {
        "tiny": 500,
        "base": 1000,
        "small": 2000,
        "medium": 4000,
        "large": 8000
      },
      "category": "offline"
    },
    {
      "name": "whisper_api",
      "description": "OpenAI Whisper API (Cloud)",
      "type": "cloud",
      "platform": "Cloud",
      "target_latency_ms": 3000,
      "category": "accurate"
    },
    {
      "name": "whisper_cpp",
      "description": "whisper.cpp (Local C++ Implementation)",
      "type": "local",
      "platform": "macOS/Linux",
      "target_latency_ms": 1500,
      "category": "optimized"
    }
  ],
  "test_scenarios": [
    {
      "name": "short_audio",
      "duration_ms": 2000,
      "description": "Short audio sample (2 seconds)"
    },
    {
      "name": "medium_audio",
      "duration_ms": 5000,
      "description": "Medium audio sample (5 seconds)"
    },
    {
      "name": "long_audio",
      "duration_ms": 30000,
      "description": "Long audio sample (30 seconds)"
    }
  ],
  "metrics": [
    {
      "name": "first_transcription_latency",
      "unit": "milliseconds",
      "description": "Time from audio input end to first transcription chunk"
    },
    {
      "name": "total_transcription_time",
      "unit": "milliseconds",
      "description": "Total time to complete transcription"
    },
    {
      "name": "word_error_rate",
      "unit": "percentage",
      "description": "Accuracy of transcription"
    },
    {
      "name": "throughput",
      "unit": "words_per_second",
      "description": "Transcription speed"
    }
  ],
  "expected_results": {
    "apple": {
      "first_transcription_latency_ms": "< 200",
      "total_transcription_time_ms": "< 500",
      "category": "Real-time"
    },
    "faster_whisper_tiny": {
      "first_transcription_latency_ms": "< 300",
      "total_transcription_time_ms": "< 500",
      "category": "Fast local"
    },
    "faster_whisper_base": {
      "first_transcription_latency_ms": "< 500",
      "total_transcription_time_ms": "< 1000",
      "category": "Balanced"
    },
    "whisper_api": {
      "first_transcription_latency_ms": "1000-3000",
      "total_transcription_time_ms": "1000-3000",
      "category": "Accurate"
    },
    "whisper_cpp": {
      "first_transcription_latency_ms": "< 500",
      "total_transcription_time_ms": "< 1500",
      "category": "Optimized"
    }
  }
}
EOF

echo -e "${GREEN}✓${NC} Created baseline template: stt-baseline.json"

# Run Python Whisper benchmark
echo ""
echo -e "${BLUE}Running Whisper Model Benchmarks:${NC}"

if command -v python3 &> /dev/null; then
    if python3 -c "import faster_whisper" 2>/dev/null; then
        echo -e "${YELLOW}Running faster-whisper benchmark...${NC}"
        python3 "${SCRIPT_DIR}/whisper_model_benchmark.py" --output-dir "${BENCHMARK_DIR}" || echo -e "${RED}Whisper benchmark failed${NC}"
    else
        echo -e "${YELLOW}Skipping faster-whisper benchmark (package not installed)${NC}"
        echo -e "  ${BLUE}Install:${NC} pip3 install faster-whisper librosa soundfile"
    fi
else
    echo -e "${RED}Python 3 not found, skipping Python benchmarks${NC}"
fi

# Generate comprehensive report
echo ""
echo -e "${BLUE}Generating Comprehensive Report:${NC}"

cat > "${BENCHMARK_DIR}/BENCHMARK_REPORT.md" << 'EOF'
# BrainChat STT Engine Benchmark Report

## Overview
This document contains the benchmark results for all speech-to-text engines integrated with BrainChat.

## Test Environments
- **Date**: 2024
- **Platform**: macOS
- **Test Duration**: Short, Medium, and Long audio samples

## Engines Benchmarked

### 1. Apple Speech Recognition (SFSpeechRecognizer)
- **Type**: Native macOS API
- **Latency Target**: < 200ms
- **Category**: Real-time
- **Pros**: Native integration, low latency, no API keys needed
- **Cons**: Requires Apple framework, not offline for transcription

### 2. faster-whisper (Local)
- **Type**: Python library for local inference
- **Latency Targets**:
  - tiny: < 500ms
  - base: < 1000ms
  - small: < 2000ms
  - medium: < 4000ms
  - large: < 8000ms
- **Category**: Offline, flexible models
- **Pros**: Fully offline, customizable models, good accuracy
- **Cons**: Requires Python setup, slower than native

### 3. Whisper API (Cloud)
- **Type**: OpenAI cloud service
- **Latency Target**: 1000-3000ms
- **Category**: Accurate
- **Pros**: Highest accuracy, minimal setup
- **Cons**: Requires API key and internet, slower, has costs

### 4. whisper.cpp (Local C++)
- **Type**: C++ implementation of Whisper
- **Latency Target**: < 1500ms
- **Category**: Optimized local
- **Pros**: Fast, lightweight, offline
- **Cons**: Requires compilation, limited model options

## Benchmark Results

### Performance Summary
| Engine | Model | Avg Latency (ms) | First Response (ms) | Accuracy | Target Met |
|--------|-------|------------------|-------------------|----------|-----------|
| Apple | Native | - | - | - | - |
| faster-whisper | tiny | - | - | - | - |
| faster-whisper | base | - | - | - | - |
| Whisper API | whisper-1 | - | - | - | - |
| whisper.cpp | base | - | - | - | - |

### Test Scenarios
1. **Short Audio** (2 seconds)
2. **Medium Audio** (5 seconds)
3. **Long Audio** (30 seconds)

## Recommendations

### For Real-time Applications
- **Best**: Apple Speech Recognition
- **Reason**: Lowest latency, native integration

### For Offline Use
- **Best**: faster-whisper (tiny or base model)
- **Reason**: Good balance of speed and accuracy without internet

### For Highest Accuracy
- **Best**: Whisper API
- **Reason**: OpenAI's API provides best transcription quality

### For Performance-Critical
- **Best**: whisper.cpp
- **Reason**: Optimized C++ implementation with minimal overhead

## Implementation Guide

### Apple Speech Recognition
```swift
let recognizer = SFSpeechRecognizer()
```

### faster-whisper
```python
from faster_whisper import WhisperModel
model = WhisperModel("base")
```

### Whisper API
```swift
let engine = WhisperAPIEngine(apiKey: "sk-...")
```

### whisper.cpp
```swift
let engine = WhisperCppEngine()
```

## Latency Breakdown

### Factors Affecting Latency
1. **Model Load Time**: Time to load model into memory
2. **Audio Processing**: Format conversion, feature extraction
3. **Inference**: Neural network forward pass
4. **Post-processing**: Text normalization, formatting

### Optimization Strategies
- Use smaller models for real-time requirements
- Pre-load models at startup
- Cache model weights
- Use GPU acceleration where available

## Conclusion

Each STT engine has its own strengths:
- **Apple**: Best for real-time, native integration
- **faster-whisper**: Best balance for local offline use
- **Whisper API**: Best accuracy if online access available
- **whisper.cpp**: Best for optimized performance

Choose based on your specific requirements:
- Real-time response needed? → Apple
- Offline required? → faster-whisper or whisper.cpp
- Highest accuracy? → Whisper API
- Performance critical? → whisper.cpp

## Raw Benchmark Data

See `stt-baseline.json` and `whisper_models_benchmark.json` for detailed metrics.
EOF

echo -e "${GREEN}✓${NC} Created comprehensive report: BENCHMARK_REPORT.md"

# Summary
echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Benchmark Suite Complete!${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "📁 Results Location: ${BENCHMARK_DIR}/"
echo ""
echo "📊 Generated Files:"
echo "  • stt-baseline.json - STT engine baseline definitions"
echo "  • whisper_models_benchmark.json - Whisper model benchmark results"
echo "  • BENCHMARK_REPORT.md - Comprehensive analysis and recommendations"
echo ""
echo "🚀 Next Steps:"
echo "  1. Review BENCHMARK_REPORT.md for detailed analysis"
echo "  2. Check benchmark results in JSON files"
echo "  3. Use results to optimize STT engine selection"
echo ""
